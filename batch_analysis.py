"""Project -> AHU -> motor batch analysis orchestration."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from ahu_matching import AHUMatch, discover_equipment, match_ahu_lists, normalize_equipment_id
from app_logger import debug, exception, info, warning
from motor_compare import MotorComparison, compare_motor_records
from motor_database import build_comparison_key
from project_discovery import ProjectDiscovery, discover_project, normalize_project_name
from project_matching import ProjectMatch, match_discoveries
from stage1_page_discovery import build_stage1_motor_records, find_rated_motor_powers_in_pdf
from stage2_pdf_discovery import build_pdf2_motor_records, find_pdf2_motor_powers


@dataclass(frozen=True)
class BatchDocument:
    path: str
    side: str
    project: ProjectDiscovery
    equipment: tuple[str, ...]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["project"] = self.project.to_dict()
        return data


@dataclass(frozen=True)
class BatchAHU:
    project_name: str | None
    match: AHUMatch
    pdf1_files: tuple[str, ...]
    pdf2_files: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "project_name": self.project_name,
            "match": self.match.to_dict(),
            "pdf1_files": list(self.pdf1_files),
            "pdf2_files": list(self.pdf2_files),
        }


@dataclass(frozen=True)
class BatchAnalysis:
    pdf1_documents: tuple[BatchDocument, ...]
    pdf2_documents: tuple[BatchDocument, ...]
    project_matches: tuple[ProjectMatch, ...]
    ahu_matches: tuple[BatchAHU, ...]
    motor_comparisons: tuple[MotorComparison, ...]

    def to_dict(self) -> dict:
        return {
            "pdf1_documents": [x.to_dict() for x in self.pdf1_documents],
            "pdf2_documents": [x.to_dict() for x in self.pdf2_documents],
            "project_matches": [x.to_dict() for x in self.project_matches],
            "ahu_matches": [x.to_dict() for x in self.ahu_matches],
            "motor_comparisons": [x.to_dict() for x in self.motor_comparisons],
        }


def _discover_documents(paths: list[str | Path], side: str) -> list[BatchDocument]:
    documents: list[BatchDocument] = []
    seen_paths: set[str] = set()
    info("PDF keşfi başladı", side=side, input_count=len(paths))
    for raw in paths:
        path = Path(raw).expanduser().resolve()
        key = str(path).casefold()
        if key in seen_paths:
            debug("Aynı PDF tekrar seçildi, atlandı", side=side, path=str(path))
            continue
        seen_paths.add(key)
        if not path.is_file():
            warning("PDF dosyası bulunamadı veya dosya değil", side=side, path=str(path))
            continue
        try:
            project = discover_project(path)
            equipment = discover_equipment(path)
            document = BatchDocument(str(path), side, project, equipment.unique_ids())
            documents.append(document)
            info(
                "PDF keşfi tamamlandı",
                side=side,
                path=str(path),
                project=project.project_name,
                project_source=project.project_source,
                project_confidence=project.confidence,
                equipment=list(document.equipment),
            )
            if not project.project_name:
                warning("PDF'de proje adı bulunamadı", side=side, path=str(path), candidates=[x.to_dict() for x in project.candidates])
            if not document.equipment:
                warning("PDF'de AHU/equipment referansı bulunamadı", side=side, path=str(path))
        except Exception as exc:
            exception("PDF keşfi başarısız; dosya analizin dışında bırakıldı", exc, side=side, path=str(path))
    info("PDF keşfi bitti", side=side, document_count=len(documents))
    return documents


def _group_documents(documents: list[BatchDocument]) -> dict[str, list[BatchDocument]]:
    grouped: dict[str, list[BatchDocument]] = {}
    for document in documents:
        key = document.project.project_name_normalized or f"__UNRESOLVED__:{document.path}"
        grouped.setdefault(key, []).append(document)
    debug("PDF'ler proje gruplarına ayrıldı", groups={k: len(v) for k, v in grouped.items()})
    return grouped


def _files_for_ahu(documents: list[BatchDocument], normalized_ahu: str | None) -> tuple[str, ...]:
    if not normalized_ahu:
        warning("AHU için dosya aranamadı: normalized AHU boş")
        return ()
    target = normalize_equipment_id(normalized_ahu)
    files = tuple(
        document.path
        for document in documents
        if target in {normalize_equipment_id(x) for x in document.equipment}
    )
    if not files:
        warning("AHU eşleşti fakat kaynak PDF bulunamadı", ahu=target, documents=[x.path for x in documents])
    return files


def _dedupe_motor_records(records):
    """Keep one physical motor per equipment/type/index across overlapping PDFs."""
    unique = {}
    for record in records:
        key = build_comparison_key(record)
        if key in unique:
            debug("Çakışan fiziksel motor kaydı dedupe edildi", key=key, kept_page=unique[key].source_page, dropped_page=record.source_page)
        unique.setdefault(key, record)
    return list(unique.values())


def _extract_side_motors(paths: tuple[str, ...], side: str, target_ahu: str | None):
    records = []
    counters: dict[tuple[str, str], int] = {}
    target = normalize_equipment_id(target_ahu) if target_ahu else None
    info("Motor keşfi başladı", side=side, target_ahu=target, file_count=len(paths))

    for path in paths:
        try:
            if side == "PDF1":
                found = find_rated_motor_powers_in_pdf(path)
                built = [record for result in found for record in build_stage1_motor_records(result)]
                records.extend(built)
                info("PDF1 motor keşfi tamamlandı", path=path, result_count=len(found), physical_motor_count=len(built), results=[x.to_dict() for x in found])
                if not found:
                    warning("PDF1'de motor anma gücü bulunamadı", path=path, ahu=target)
            else:
                found = find_pdf2_motor_powers(path)
                built_count = 0
                for result in found:
                    key = (normalize_equipment_id(result.equipment_id), result.component_type.strip().lower())
                    start = counters.get(key, 1)
                    expanded = build_pdf2_motor_records(result, start_index=start)
                    records.extend(expanded)
                    counters[key] = start + len(expanded)
                    built_count += len(expanded)
                info("PDF2 motor keşfi tamamlandı", path=path, result_count=len(found), physical_motor_count=built_count, results=[x.to_dict() for x in found])
                if not found:
                    warning("PDF2'de motor gücü bulunamadı", path=path, ahu=target)
        except Exception as exc:
            exception("Motor keşfi başarısız", exc, side=side, path=path, ahu=target)

    records = _dedupe_motor_records(records)
    if target is None:
        info("Motor keşfi bitti", side=side, motor_count=len(records))
        return records
    filtered = [record for record in records if normalize_equipment_id(record.equipment_id) == target]
    info("Motor keşfi bitti", side=side, ahu=target, motor_count=len(filtered), total_before_filter=len(records))
    if not filtered:
        warning("AHU bulundu ancak bu AHU için fiziksel motor kaydı oluşmadı", side=side, ahu=target)
    return filtered


def _pair_project_groups(left_groups, right_groups):
    """Pair named project groups using the conservative project-name matcher."""
    candidates = []
    for left_key, left_docs in left_groups.items():
        left = left_docs[0].project
        if not left.project_name_normalized:
            continue
        for right_key, right_docs in right_groups.items():
            right = right_docs[0].project
            if not right.project_name_normalized:
                continue
            try:
                match = match_discoveries(left, right)
                candidates.append((match.score, left_key, right_key, match))
                debug("Proje eşleşme adayı hesaplandı", left=left.project_name, right=right.project_name, score=match.score, status=match.status, reason=match.reason)
            except Exception as exc:
                exception("Proje eşleşme adayı hesaplanamadı", exc, left=left.project_name, right=right.project_name)

    used_left: set[str] = set()
    used_right: set[str] = set()
    output = []
    for _, left_key, right_key, match in sorted(candidates, reverse=True, key=lambda x: x[0]):
        if left_key in used_left or right_key in used_right:
            continue
        if match.status == "NO_MATCH":
            continue
        used_left.add(left_key)
        used_right.add(right_key)
        output.append((left_key, right_key, match))
    info("Proje grupları eşleştirildi", matched_count=len(output), candidate_count=len(candidates))
    if not output and left_groups and right_groups:
        warning("Hiçbir PDF1/PDF2 projesi eşleşmedi", pdf1_projects=list(left_groups), pdf2_projects=list(right_groups))
    return output


def _ahu_set(documents: list[BatchDocument]) -> set[str]:
    return {
        normalize_equipment_id(equipment)
        for document in documents
        for equipment in document.equipment
        if normalize_equipment_id(equipment)
    }


def _best_project_for_document(document: BatchDocument, left_groups):
    """Infer a project for an unnamed right-side PDF from unique AHU overlap."""
    right_ahus = _ahu_set([document])
    if not right_ahus:
        warning("PDF2 projesi AHU ile de çıkarılamadı", path=document.path)
        return None

    candidates = []
    for left_key, left_docs in left_groups.items():
        project = left_docs[0].project
        if not project.project_name_normalized:
            continue
        left_ahus = _ahu_set(left_docs)
        overlap = right_ahus & left_ahus
        if not overlap:
            continue
        coverage = len(overlap) / len(right_ahus)
        candidates.append((coverage, len(overlap), left_key, overlap))

    if not candidates:
        warning("PDF2 projesi için AHU örtüşmesi bulunamadı", path=document.path, ahus=list(right_ahus))
        return None
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    best = candidates[0]
    if len(candidates) > 1:
        second = candidates[1]
        if best[0] == second[0] and best[1] == second[1]:
            warning("PDF2 projesi AHU ile belirsiz: iki proje aynı örtüşmeye sahip", path=document.path, candidates=candidates)
            return None
    if best[0] < 0.50:
        warning("PDF2 projesi AHU örtüşmesi %50 altında", path=document.path, coverage=best[0], candidates=candidates)
        return None
    info("PDF2 projesi AHU üzerinden çıkarıldı", path=document.path, project_key=best[2], coverage=best[0], overlap=list(best[3]))
    return best


def _infer_unresolved_right_documents(left_groups, right_documents, already_matched_paths):
    """Assign unnamed PDF2 documents to projects when AHU references identify them."""
    assignments: dict[str, list[BatchDocument]] = {}
    for document in right_documents:
        if document.project.project_name_normalized or document.path in already_matched_paths:
            continue
        best = _best_project_for_document(document, left_groups)
        if best is None:
            continue
        _, _, left_key, _ = best
        assignments.setdefault(left_key, []).append(document)
    return assignments


def analyze_batch(pdf1_paths: list[str | Path], pdf2_paths: list[str | Path]) -> BatchAnalysis:
    """Analyze a PDF batch as Project -> AHU -> physical motor comparisons."""
    info("TOPLU ANALİZ başladı", pdf1_count=len(pdf1_paths), pdf2_count=len(pdf2_paths))
    try:
        left_docs = _discover_documents(pdf1_paths, "PDF1")
        right_docs = _discover_documents(pdf2_paths, "PDF2")
        left_groups = _group_documents(left_docs)
        right_groups = _group_documents(right_docs)

        named_pairs = _pair_project_groups(left_groups, right_groups)
        used_right_paths: set[str] = set()
        project_pair_docs: dict[str, tuple[ProjectMatch, list[BatchDocument], list[BatchDocument]]] = {}

        for left_key, right_key, project_match in named_pairs:
            left_group = left_groups[left_key]
            right_group = right_groups[right_key]
            used_right_paths.update(document.path for document in right_group)
            project_pair_docs[left_key] = (project_match, list(left_group), list(right_group))

        inferred = _infer_unresolved_right_documents(left_groups, right_docs, used_right_paths)
        for left_key, inferred_docs in inferred.items():
            if left_key in project_pair_docs:
                match, left_group, right_group = project_pair_docs[left_key]
                right_group.extend(inferred_docs)
                project_pair_docs[left_key] = (match, left_group, right_group)
                continue

            left_group = left_groups[left_key]
            project = left_group[0].project
            overlap_total = sum(len(_ahu_set([document]) & _ahu_set(left_group)) for document in inferred_docs)
            right_name = inferred_docs[0].project.project_name if inferred_docs[0].project.project_name else None
            inferred_match = ProjectMatch(
                left_name=project.project_name,
                right_name=right_name,
                left_normalized=project.project_name_normalized,
                right_normalized=normalize_project_name(right_name or "") or None,
                score=round(overlap_total / max(1, sum(len(_ahu_set([document])) for document in inferred_docs)), 4),
                status="INFERRED_FROM_AHU",
                reason="PDF2 project name is unavailable; project was inferred from AHU references",
                left_source=project.project_source,
                right_source=None,
            )
            project_pair_docs[left_key] = (inferred_match, list(left_group), list(inferred_docs))
            info("Proje eşleşmesi AHU üzerinden üretildi", project=project.project_name, inferred_documents=[x.path for x in inferred_docs], score=inferred_match.score)

        project_matches: list[ProjectMatch] = []
        ahu_batches: list[BatchAHU] = []
        motor_comparisons: list[MotorComparison] = []

        for project_match, left_group, right_group in project_pair_docs.values():
            project_matches.append(project_match)
            left_equipment = []
            right_equipment = []
            for document in left_group:
                left_equipment.extend(discover_equipment(document.path).equipment_ids)
            for document in right_group:
                right_equipment.extend(discover_equipment(document.path).equipment_ids)

            matches = match_ahu_lists(left_equipment, right_equipment)
            info("AHU eşleştirme tamamlandı", project=project_match.left_name, match_count=len(matches))
            for ahu_match in matches:
                left_files = _files_for_ahu(left_group, ahu_match.left_normalized)
                right_files = _files_for_ahu(right_group, ahu_match.right_normalized)
                ahu_batches.append(BatchAHU(project_match.left_name, ahu_match, left_files, right_files))
                info("AHU sonucu", project=project_match.left_name, left=ahu_match.left_normalized, right=ahu_match.right_normalized, score=ahu_match.score, status=ahu_match.status, reason=ahu_match.reason)
                if ahu_match.status not in {"EXACT", "NORMALIZED_MATCH"}:
                    continue
                try:
                    left_motors = _extract_side_motors(left_files, "PDF1", ahu_match.left_normalized)
                    right_motors = _extract_side_motors(right_files, "PDF2", ahu_match.right_normalized)
                    comparisons = compare_motor_records(left_motors, right_motors)
                    motor_comparisons.extend(comparisons)
                    info("Motor karşılaştırması tamamlandı", project=project_match.left_name, ahu=ahu_match.left_normalized, comparison_count=len(comparisons), statuses=[x.status for x in comparisons])
                except Exception as exc:
                    exception("Motor karşılaştırması başarısız", exc, project=project_match.left_name, ahu=ahu_match.left_normalized)

        result = BatchAnalysis(tuple(left_docs), tuple(right_docs), tuple(project_matches), tuple(ahu_batches), tuple(motor_comparisons))
        info("TOPLU ANALİZ tamamlandı", projects=len(project_matches), ahus=len(ahu_batches), motors=len(motor_comparisons))
        return result
    except Exception as exc:
        exception("TOPLU ANALİZ kritik hata ile sonlandı", exc)
        raise
