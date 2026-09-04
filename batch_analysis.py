"""Project -> AHU -> motor batch analysis orchestration."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from ahu_matching import AHUMatch, discover_equipment, match_ahu_lists, normalize_equipment_id
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
    for raw in paths:
        path = Path(raw).expanduser().resolve()
        key = str(path).casefold()
        if key in seen_paths or not path.is_file():
            continue
        seen_paths.add(key)
        project = discover_project(path)
        equipment = discover_equipment(path)
        documents.append(BatchDocument(str(path), side, project, equipment.unique_ids()))
    return documents


def _group_documents(documents: list[BatchDocument]) -> dict[str, list[BatchDocument]]:
    grouped: dict[str, list[BatchDocument]] = {}
    for document in documents:
        key = document.project.project_name_normalized or f"__UNRESOLVED__:{document.path}"
        grouped.setdefault(key, []).append(document)
    return grouped


def _files_for_ahu(documents: list[BatchDocument], normalized_ahu: str | None) -> tuple[str, ...]:
    if not normalized_ahu:
        return ()
    target = normalize_equipment_id(normalized_ahu)
    return tuple(
        document.path
        for document in documents
        if target in {normalize_equipment_id(x) for x in document.equipment}
    )


def _dedupe_motor_records(records):
    """Keep one physical motor per equipment/type/index across overlapping PDFs."""
    unique = {}
    for record in records:
        key = build_comparison_key(record)
        unique.setdefault(key, record)
    return list(unique.values())


def _extract_side_motors(paths: tuple[str, ...], side: str, target_ahu: str | None):
    records = []
    counters: dict[tuple[str, str], int] = {}
    target = normalize_equipment_id(target_ahu) if target_ahu else None

    for path in paths:
        if side == "PDF1":
            found = find_rated_motor_powers_in_pdf(path)
            records.extend(record for result in found for record in build_stage1_motor_records(result))
        else:
            found = find_pdf2_motor_powers(path)
            for result in found:
                key = (normalize_equipment_id(result.equipment_id), result.component_type.strip().lower())
                start = counters.get(key, 1)
                expanded = build_pdf2_motor_records(result, start_index=start)
                records.extend(expanded)
                counters[key] = start + len(expanded)

    records = _dedupe_motor_records(records)
    if target is None:
        return records
    return [record for record in records if normalize_equipment_id(record.equipment_id) == target]


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
            match = match_discoveries(left, right)
            candidates.append((match.score, left_key, right_key, match))

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
        return None
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    best = candidates[0]
    if len(candidates) > 1:
        second = candidates[1]
        if best[0] == second[0] and best[1] == second[1]:
            return None
    if best[0] < 0.50:
        return None
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
        overlap_total = sum(
            len(_ahu_set([document]) & _ahu_set(left_group))
            for document in inferred_docs
        )
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

        for ahu_match in match_ahu_lists(left_equipment, right_equipment):
            left_files = _files_for_ahu(left_group, ahu_match.left_normalized)
            right_files = _files_for_ahu(right_group, ahu_match.right_normalized)
            ahu_batches.append(BatchAHU(project_match.left_name, ahu_match, left_files, right_files))
            if ahu_match.status not in {"EXACT", "NORMALIZED_MATCH"}:
                continue
            left_motors = _extract_side_motors(left_files, "PDF1", ahu_match.left_normalized)
            right_motors = _extract_side_motors(right_files, "PDF2", ahu_match.right_normalized)
            motor_comparisons.extend(compare_motor_records(left_motors, right_motors))

    return BatchAnalysis(tuple(left_docs), tuple(right_docs), tuple(project_matches), tuple(ahu_batches), tuple(motor_comparisons))
