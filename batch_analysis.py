"""Project -> AHU -> motor batch analysis orchestration."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from ahu_matching import AHUMatch, discover_equipment, match_ahu_lists, normalize_equipment_id
from motor_compare import MotorComparison, compare_motor_records
from project_discovery import ProjectDiscovery, discover_project
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
    for raw in paths:
        path = Path(raw).expanduser().resolve()
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


def _extract_side_motors(paths: tuple[str, ...], side: str, target_ahu: str | None):
    records = []
    target = normalize_equipment_id(target_ahu) if target_ahu else None
    for path in paths:
        if side == "PDF1":
            found = find_rated_motor_powers_in_pdf(path)
            records.extend(record for result in found for record in build_stage1_motor_records(result))
        else:
            found = find_pdf2_motor_powers(path)
            counters: dict[tuple[str, str], int] = {}
            for result in found:
                key = (normalize_equipment_id(result.equipment_id), result.component_type)
                start = counters.get(key, 1)
                expanded = build_pdf2_motor_records(result, start_index=start)
                records.extend(expanded)
                counters[key] = start + len(expanded)
    if target is None:
        return records
    return [r for r in records if normalize_equipment_id(r.equipment_id) == target]


def _pair_project_groups(left_groups, right_groups):
    candidates = []
    for left_key, left_docs in left_groups.items():
        left = left_docs[0].project
        for right_key, right_docs in right_groups.items():
            right = right_docs[0].project
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


def analyze_batch(pdf1_paths: list[str | Path], pdf2_paths: list[str | Path]) -> BatchAnalysis:
    """Analyze a PDF batch as Project -> AHU -> physical motor comparisons."""
    left_docs = _discover_documents(pdf1_paths, "PDF1")
    right_docs = _discover_documents(pdf2_paths, "PDF2")
    left_groups = _group_documents(left_docs)
    right_groups = _group_documents(right_docs)

    project_matches: list[ProjectMatch] = []
    ahu_batches: list[BatchAHU] = []
    motor_comparisons: list[MotorComparison] = []

    left_by_key = left_groups
    right_by_key = right_groups
    for left_key, right_key, project_match in _pair_project_groups(left_by_key, right_by_key):
        project_matches.append(project_match)
        left_group = left_by_key[left_key]
        right_group = right_by_key[right_key]

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
