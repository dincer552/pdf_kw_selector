"""Interactive confirmation layer for uncertain Project/AHU matches."""
from __future__ import annotations

from difflib import SequenceMatcher
from pathlib import Path
import re

from tkinter import messagebox

import batch_analysis as batch
from ahu_matching import AHUMatch, normalize_equipment_id, score_ahu_ids
from app_logger import debug, exception, info, warning
from project_matching import ProjectMatch, match_discoveries
from pypdf import PdfReader


def _compact(value: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def _flexible_ahu_key(value: str | None) -> str:
    compact = _compact(value)
    return re.sub(r"0+(?=\d)", "", compact)


def _document_identity_tokens(document) -> set[str]:
    """Collect order/project identity codes from PDF text and its path."""
    tokens: set[str] = set()
    try:
        path_text = str(document.path)
        text = "\n".join((page.extract_text() or "") for page in PdfReader(document.path).pages)
        combined = f"{path_text}\n{text}"
        for match in re.findall(r"\b\d{2}[A-Z]{2,}\d{3,}\b", combined, flags=re.I):
            tokens.add(match.upper())
        for match in re.findall(r"(?:order\s+number|project\s+(?:no|number))\s*[:=]?\s*([A-Z0-9][A-Z0-9_-]+)", combined, flags=re.I):
            tokens.add(match.upper().strip("_-"))
    except Exception as exc:
        warning("Proje kimlik numarası keşfi başarısız", path=document.path, error=str(exc))
    return tokens


def _project_candidate(left_docs, right_docs):
    left_tokens = set().union(*(_document_identity_tokens(x) for x in left_docs)) if left_docs else set()
    right_tokens = set().union(*(_document_identity_tokens(x) for x in right_docs)) if right_docs else set()
    shared = left_tokens & right_tokens
    left = left_docs[0].project
    right = right_docs[0].project
    name_match = match_discoveries(left, right)
    return name_match, shared


def _ask_project(left_name: str, right_name: str, shared_tokens: set[str]) -> bool:
    identity = "\nOrtak kimlik: " + ", ".join(sorted(shared_tokens)) if shared_tokens else ""
    text = (
        "PDF1 ve PDF2 proje adları farklı görünüyor.\n\n"
        f"PDF1: {left_name}\n"
        f"PDF2: {right_name}"
        f"{identity}\n\n"
        "Bunlar aynı proje mi?\n\n"
        "EVET: Bu eşleştirmeyi onayla ve hesaplamaya devam et.\n"
        "HAYIR: Bu proje çiftini eşleştirme."
    )
    return bool(messagebox.askyesno("Proje eşleşmesi onayı", text))


def _ask_ahu(project: str | None, left: str, right: str, *, reused_rule: bool = False) -> bool:
    rule = "\n\nÖnceki AHU onayındaki esnek eşleştirme kuralı uygulanacak." if reused_rule else ""
    text = (
        "AHU referansları birebir aynı değil.\n\n"
        f"Proje: {project or '-'}\n"
        f"PDF1 AHU: {left}\n"
        f"PDF2 AHU: {right}\n\n"
        "Bunlar aynı AHU mu?\n\n"
        "EVET: Bu eşleştirmeyi onayla.\n"
        "HAYIR: Bu AHU çiftini eşleştirme."
        f"{rule}"
    )
    return bool(messagebox.askyesno("AHU eşleşmesi onayı", text))


def _project_confirmation_plan(left_groups, right_groups):
    approved: set[tuple[str, str]] = set()
    planned: list[tuple[str, str]] = []
    used_left: set[str] = set()
    used_right: set[str] = set()

    candidates = []
    for left_key, left_docs in left_groups.items():
        for right_key, right_docs in right_groups.items():
            try:
                match, shared = _project_candidate(left_docs, right_docs)
                candidates.append((bool(shared), len(shared), match.score, left_key, right_key, match, shared))
            except Exception as exc:
                exception("Proje onay adayı hesaplanamadı", exc, left=left_key, right=right_key)

    for has_identity, identity_count, score, left_key, right_key, match, shared in sorted(
        candidates, key=lambda x: (x[0], x[1], x[2]), reverse=True
    ):
        if left_key in used_left or right_key in used_right:
            continue
        if match.status != "NO_MATCH":
            continue
        # Strong identity match is the preferred confirmation trigger. If the batch is
        # one-project-vs-one-project, confirmation is still required even without it.
        if not has_identity and not (len(left_groups) == 1 and len(right_groups) == 1):
            continue
        left_name = left_groups[left_key][0].project.project_name or left_key
        right_name = right_groups[right_key][0].project.project_name or right_key
        if _ask_project(left_name, right_name, shared):
            approved.add((left_key, right_key))
            planned.append((left_key, right_key))
            used_left.add(left_key)
            used_right.add(right_key)
            info("Kullanıcı proje eşleşmesini onayladı", left=left_name, right=right_name, shared_identity=sorted(shared))
        else:
            warning("Kullanıcı proje eşleşmesini reddetti", left=left_name, right=right_name, shared_identity=sorted(shared))
    return approved, planned


def _ahu_confirmation_plan(project_pairs):
    approved: set[tuple[str, str]] = set()
    flexible_auto: set[tuple[str, str]] = set()
    flexible_rule_enabled = False

    for left_key, right_key in project_pairs:
        left_docs = batch._group_documents  # keep access to the same batch primitives for logging/debugging
        del left_docs
        # The actual documents are retrieved from the project groups passed by the caller.

    return approved, flexible_auto


def _build_ahu_confirmations(project_pair_docs):
    approved: set[tuple[str, str]] = set()
    flexible_auto: set[tuple[str, str]] = set()
    flexible_rule_enabled = False

    for project_name, left_group, right_group in project_pair_docs:
        left_occurrences = []
        right_occurrences = []
        for document in left_group:
            left_occurrences.extend(batch.discover_equipment(document.path).equipment_ids)
        for document in right_group:
            right_occurrences.extend(batch.discover_equipment(document.path).equipment_ids)

        left_unique = {x.normalized: x for x in left_occurrences}
        right_unique = {x.normalized: x for x in right_occurrences}
        unmatched_left = set(left_unique)
        unmatched_right = set(right_unique)

        # Existing normalizer already handles punctuation/underscore/dash/leading zeros.
        for lid in list(unmatched_left):
            for rid in list(unmatched_right):
                if _flexible_ahu_key(lid) == _flexible_ahu_key(rid):
                    unmatched_left.discard(lid)
                    unmatched_right.discard(rid)
                    break

        while unmatched_left and unmatched_right:
            pairs = []
            for lid in unmatched_left:
                for rid in unmatched_right:
                    score, status, reason = score_ahu_ids(lid, rid)
                    loose = SequenceMatcher(None, _flexible_ahu_key(lid), _flexible_ahu_key(rid)).ratio()
                    pairs.append((loose, score, lid, rid, reason))
            loose, score, lid, rid, reason = max(pairs, key=lambda x: (x[0], x[1]))
            if flexible_rule_enabled and loose >= 0.75:
                flexible_auto.add((lid, rid))
                unmatched_left.remove(lid)
                unmatched_right.remove(rid)
                info("Önceki AHU onay kuralı sonraki AHU'ya uygulandı", project=project_name, left=lid, right=rid, loose_score=round(loose, 4))
                continue

            if score < 0.45 and loose < 0.70:
                break
            if _ask_ahu(project_name, lid, rid, reused_rule=flexible_rule_enabled):
                approved.add((lid, rid))
                flexible_rule_enabled = True
                unmatched_left.remove(lid)
                unmatched_right.remove(rid)
                info("Kullanıcı AHU eşleşmesini onayladı", project=project_name, left=lid, right=rid, loose_score=round(loose, 4))
            else:
                warning("Kullanıcı AHU eşleşmesini reddetti", project=project_name, left=lid, right=rid, loose_score=round(loose, 4))
                unmatched_left.remove(lid)
                unmatched_right.remove(rid)

    return approved, flexible_auto


def analyze_with_confirmations(pdf1_paths, pdf2_paths):
    """Run batch analysis after interactive confirmation of uncertain project/AHU pairs."""
    left_docs = batch._discover_documents(list(pdf1_paths), "PDF1")
    right_docs = batch._discover_documents(list(pdf2_paths), "PDF2")
    left_groups = batch._group_documents(left_docs)
    right_groups = batch._group_documents(right_docs)

    approved_projects, _ = _project_confirmation_plan(left_groups, right_groups)

    # Determine which project groups will actually be analyzed, including user-approved pairs.
    project_pair_docs = []
    for left_key, left_docs_group in left_groups.items():
        for right_key, right_docs_group in right_groups.items():
            if (left_key, right_key) in approved_projects:
                project_pair_docs.append((left_docs_group[0].project.project_name, left_docs_group, right_docs_group))
                continue
            match = match_discoveries(left_docs_group[0].project, right_docs_group[0].project)
            if match.status != "NO_MATCH":
                project_pair_docs.append((left_docs_group[0].project.project_name, left_docs_group, right_docs_group))

    approved_ahus, flexible_ahus = _build_ahu_confirmations(project_pair_docs)
    all_approved_ahus = approved_ahus | flexible_ahus

    original_project_match = batch.match_discoveries
    original_ahu_match = batch.match_ahu_lists

    def confirmed_project_match(left, right):
        if (left.project_name_normalized, right.project_name_normalized) in approved_projects:
            return ProjectMatch(
                left_name=left.project_name,
                right_name=right.project_name,
                left_normalized=left.project_name_normalized,
                right_normalized=right.project_name_normalized,
                score=1.0,
                status="USER_APPROVED",
                reason="user confirmed project names refer to the same project",
                left_source=left.project_source,
                right_source=right.project_source,
            )
        return original_project_match(left, right)

    def confirmed_ahu_matches(left, right):
        base = original_ahu_match(left, right)
        occurrence_left = {x.normalized: x for x in left}
        occurrence_right = {x.normalized: x for x in right}
        used_left = {x.left_normalized for x in base if x.left_normalized}
        used_right = {x.right_normalized for x in base if x.right_normalized}
        extra = []
        for lid, rid in all_approved_ahus:
            if lid not in occurrence_left or rid not in occurrence_right:
                continue
            if lid in used_left or rid in used_right:
                continue
            lo = occurrence_left[lid]
            ro = occurrence_right[rid]
            extra.append(AHUMatch(lo.equipment_id, ro.equipment_id, lid, rid, 1.0, "USER_APPROVED", "user confirmed AHU references refer to the same equipment", lo.page, ro.page))
            used_left.add(lid)
            used_right.add(rid)

        if not extra:
            return base
        filtered = [
            item for item in base
            if not (item.status == "ONLY_IN_PDF1" and item.left_normalized in used_left)
            and not (item.status == "ONLY_IN_PDF2" and item.right_normalized in used_right)
        ]
        return filtered + extra

    batch.match_discoveries = confirmed_project_match
    batch.match_ahu_lists = confirmed_ahu_matches
    try:
        info("Onaylı eşleştirmelerle hesap başlıyor", approved_projects=list(approved_projects), approved_ahus=list(all_approved_ahus))
        return batch.analyze_batch(list(pdf1_paths), list(pdf2_paths))
    except Exception as exc:
        exception("Onaylı eşleştirmeler sonrası toplu analiz hatası", exc)
        raise
    finally:
        batch.match_discoveries = original_project_match
        batch.match_ahu_lists = original_ahu_match
