"""Interactive confirmation layer for uncertain Project/AHU matches."""
from __future__ import annotations

from difflib import SequenceMatcher
import re

from tkinter import messagebox

import batch_analysis as batch
from ahu_matching import AHUMatch, score_ahu_ids
from app_logger import exception, info, warning
from project_matching import ProjectMatch, match_discoveries
from pdf_master_scan import scan_pdf


def _compact(value: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def _flexible_ahu_key(value: str | None) -> str:
    compact = _compact(value)
    return re.sub(r"0+(?=\d)", "", compact)


def _raw_ahu_key(value: str | None) -> str:
    """Normalize only cosmetic separators for comparison-rule detection."""
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def _document_identity_tokens(document) -> set[str]:
    """Collect order/project identity codes from cached PDF text and its path."""
    tokens: set[str] = set()
    try:
        path_text = str(document.path)
        scan = scan_pdf(document.path, document.side)
        text = "\n".join(scan.page_texts)
        combined = f"{path_text}\n{text}"
        for match in re.findall(r"\b\d{2}[A-Z]{2,}\d{3,}\b", combined, flags=re.I):
            tokens.add(match.upper())
        lines = [line.strip() for line in combined.splitlines()]
        for index, line in enumerate(lines):
            if re.search(r"\b(?:order|project)\s*(?:number|no|num)\b", line, flags=re.I):
                tail = re.sub(r"^.*?\b(?:order|project)\s*(?:number|no|num)\b\s*[:=#-]?\s*", "", line, flags=re.I).strip()
                if tail and re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{2,}", tail, flags=re.I):
                    tokens.add(tail.strip("_- ").upper())
                elif index + 1 < len(lines):
                    nxt = lines[index + 1]
                    if re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{2,}", nxt, flags=re.I):
                        tokens.add(nxt.strip("_- ").upper())
    except Exception as exc:
        warning("Proje kimlik numarası keşfi başarısız", path=document.path, error=str(exc))
    return tokens


def _project_candidate(left_docs, right_docs):
    left_tokens = set().union(*(_document_identity_tokens(x) for x in left_docs)) if left_docs else set()
    right_tokens = set().union(*(_document_identity_tokens(x) for x in right_docs)) if right_docs else set()
    shared = left_tokens & right_tokens
    left = left_docs[0].project
    right = right_docs[0].project
    return match_discoveries(left, right), shared


def _ask_project(left_name: str, right_name: str, shared_tokens: set[str]) -> bool:
    identity = "\nOrtak kimlik: " + ", ".join(sorted(shared_tokens)) if shared_tokens else ""
    text = (
        "PDF1 ve PDF2 proje adları birebir aynı değil.\n\n"
        f"PDF1: {left_name}\n"
        f"PDF2: {right_name}"
        f"{identity}\n\n"
        "Bunlar aynı proje mi?\n\n"
        "EVET: Bu eşleştirmeyi onayla ve bu projedeki AHU'ları eşleştir.\n"
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
        "EVET: Bu eşleştirmeyi onayla ve aynı isimlendirme farkını kalan AHU'larda da kullan.\n"
        "HAYIR: Bu AHU çiftini eşleştirme."
        f"{rule}"
    )
    return bool(messagebox.askyesno("AHU eşleşmesi onayı", text))


def _project_confirmation_plan(left_groups, right_groups):
    """Return normalized project pairs explicitly approved by the user."""
    approved: set[tuple[str, str]] = set()
    used_left: set[str] = set()
    used_right: set[str] = set()
    candidates = []

    for left_key, left_docs in left_groups.items():
        for right_key, right_docs in right_groups.items():
            try:
                match, shared = _project_candidate(left_docs, right_docs)
                candidate = bool(shared) or match.score >= 0.45 or (len(left_groups) == 1 and len(right_groups) == 1)
                candidates.append((candidate, bool(shared), len(shared), match.score, left_key, right_key, match, shared))
            except Exception as exc:
                exception("Proje onay adayı hesaplanamadı", exc, left=left_key, right=right_key)

    for candidate, has_identity, identity_count, score, left_key, right_key, match, shared in sorted(
        candidates, key=lambda x: (x[1], x[2], x[3]), reverse=True
    ):
        if not candidate or left_key in used_left or right_key in used_right:
            continue
        if match.status == "EXACT":
            continue
        left_name = left_groups[left_key][0].project.project_name or left_key
        right_name = right_groups[right_key][0].project.project_name or right_key
        if _ask_project(left_name, right_name, shared):
            left_norm = left_groups[left_key][0].project.project_name_normalized
            right_norm = right_groups[right_key][0].project.project_name_normalized
            if left_norm and right_norm:
                approved.add((left_norm, right_norm))
            used_left.add(left_key)
            used_right.add(right_key)
            info("Kullanıcı proje eşleşmesini onayladı", left=left_name, right=right_name, shared_identity=sorted(shared), score=score)
        else:
            warning("Kullanıcı proje eşleşmesini reddetti", left=left_name, right=right_name, shared_identity=sorted(shared), score=score)
    return approved


def _build_ahu_confirmations(project_pair_docs):
    """Ask about AHUs whose raw references differ; reuse the approved rule afterwards."""
    approved: set[tuple[str, str]] = set()
    flexible_auto: set[tuple[str, str]] = set()
    flexible_rule: tuple[str, str] | None = None

    for project_name, left_group, right_group in project_pair_docs:
        left_occurrences = []
        right_occurrences = []
        for document in left_group:
            left_occurrences.extend(scan_pdf(document.path, document.side).equipment.equipment_ids)
        for document in right_group:
            right_occurrences.extend(scan_pdf(document.path, document.side).equipment.equipment_ids)

        left_unique: dict[str, object] = {}
        right_unique: dict[str, object] = {}
        for occurrence in left_occurrences:
            left_unique.setdefault(occurrence.normalized, occurrence)
        for occurrence in right_occurrences:
            right_unique.setdefault(occurrence.normalized, occurrence)

        unmatched_left = set(left_unique)
        unmatched_right = set(right_unique)

        for lid in list(unmatched_left):
            for rid in list(unmatched_right):
                lo = left_unique[lid]
                ro = right_unique[rid]
                raw_left = lo.equipment_id
                raw_right = ro.equipment_id
                if lid != rid:
                    continue
                if raw_left == raw_right:
                    unmatched_left.discard(lid)
                    unmatched_right.discard(rid)
                    continue
                if flexible_rule is not None and _flexible_ahu_key(lid) == _flexible_ahu_key(rid):
                    flexible_auto.add((lid, rid))
                    unmatched_left.discard(lid)
                    unmatched_right.discard(rid)
                    info("Önceki AHU onay kuralı uygulandı", project=project_name, left=raw_left, right=raw_right, rule=flexible_rule)
                elif _ask_ahu(project_name, raw_left, raw_right):
                    approved.add((lid, rid))
                    flexible_rule = (_raw_ahu_key(raw_left), _raw_ahu_key(raw_right))
                    unmatched_left.discard(lid)
                    unmatched_right.discard(rid)
                    info("Kullanıcı AHU isimlendirme farkını onayladı", project=project_name, left=raw_left, right=raw_right, rule=flexible_rule)
                else:
                    warning("Kullanıcı AHU isimlendirme farkını reddetti", project=project_name, left=raw_left, right=raw_right)
                    unmatched_left.discard(lid)
                    unmatched_right.discard(rid)
                break

        while unmatched_left and unmatched_right:
            pairs = []
            for lid in unmatched_left:
                for rid in unmatched_right:
                    score, _, reason = score_ahu_ids(lid, rid)
                    loose = SequenceMatcher(None, _flexible_ahu_key(lid), _flexible_ahu_key(rid)).ratio()
                    pairs.append((loose, score, lid, rid, reason))
            loose, score, lid, rid, reason = max(pairs, key=lambda x: (x[0], x[1]))

            if flexible_rule is not None and _flexible_ahu_key(lid) == _flexible_ahu_key(rid):
                flexible_auto.add((lid, rid))
                unmatched_left.remove(lid)
                unmatched_right.remove(rid)
                info("Önceki AHU onay kuralı sonraki AHU'ya uygulandı", project=project_name, left=lid, right=rid, loose_score=round(loose, 4))
                continue

            if score < 0.45 and loose < 0.70:
                break
            raw_left = left_unique[lid].equipment_id
            raw_right = right_unique[rid].equipment_id
            if _ask_ahu(project_name, raw_left, raw_right, reused_rule=flexible_rule is not None):
                approved.add((lid, rid))
                if flexible_rule is None:
                    flexible_rule = (_raw_ahu_key(raw_left), _raw_ahu_key(raw_right))
                unmatched_left.remove(lid)
                unmatched_right.remove(rid)
                info("Kullanıcı AHU eşleşmesini onayladı", project=project_name, left=raw_left, right=raw_right, loose_score=round(loose, 4), rule=flexible_rule)
            else:
                warning("Kullanıcı AHU eşleşmesini reddetti", project=project_name, left=raw_left, right=raw_right, loose_score=round(loose, 4))
                unmatched_left.remove(lid)
                unmatched_right.remove(rid)

    return approved, flexible_auto


def analyze_with_confirmations(pdf1_paths, pdf2_paths):
    """Run batch analysis after interactive confirmation of uncertain Project/AHU pairs."""
    left_docs = batch._discover_documents(list(pdf1_paths), "PDF1")
    right_docs = batch._discover_documents(list(pdf2_paths), "PDF2")
    left_groups = batch._group_documents(left_docs)
    right_groups = batch._group_documents(right_docs)

    approved_projects = _project_confirmation_plan(left_groups, right_groups)

    project_pair_docs = []
    for left_key, left_docs_group in left_groups.items():
        for right_key, right_docs_group in right_groups.items():
            left_project = left_docs_group[0].project
            right_project = right_docs_group[0].project
            pair_key = (left_project.project_name_normalized, right_project.project_name_normalized)
            if pair_key in approved_projects:
                project_pair_docs.append((left_project.project_name, left_docs_group, right_docs_group))
                continue
            match = match_discoveries(left_project, right_project)
            if match.status != "NO_MATCH":
                project_pair_docs.append((left_project.project_name, left_docs_group, right_docs_group))

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
        approved_keys = set(all_approved_ahus)
        extra = []
        used_left = set()
        used_right = set()
        for lid, rid in approved_keys:
            if lid not in occurrence_left or rid not in occurrence_right:
                continue
            lo = occurrence_left[lid]
            ro = occurrence_right[rid]
            extra.append(AHUMatch(lo.equipment_id, ro.equipment_id, lid, rid, 1.0, "EXACT", "user confirmed AHU references refer to the same equipment", lo.page, ro.page))
            used_left.add(lid)
            used_right.add(rid)

        if not extra:
            return base
        filtered = [
            item for item in base
            if not (item.left_normalized in used_left and item.right_normalized in used_right)
            and not (item.status == "ONLY_IN_PDF1" and item.left_normalized in used_left)
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
