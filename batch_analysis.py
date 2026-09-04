"""Project -> AHU -> motor batch analysis orchestration.

This layer deliberately reuses the existing discovery and motor parsers.
It groups documents by discovered project, pairs projects one-to-one, pairs
AHUs inside each matched project, then compares only the motors belonging to
those matched AHUs.
"""
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
class BatchProject:
    project_name: str | None
    normalized: str | None
    side: str
    documents: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class BatchAHU:
    project_name: str | None
    left: AHUMatch | None
    right: AHUMatch | None
    pdf1_files: tuple[str, ...]
    pdf2_files: tuple[str, ...]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["left"] = self.left.to_dict() if self.left else None
        data["right"] = self.right.to_dict() if self.right else None
        return data


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
        documents.append(
            BatchDocument(
                path=str(path),
                side=side,
                project=project,
                equipment=equipment.unique_ids(),
            )
        )
    return documents


def _group_documents(documents: list[BatchDocument]) -> dict[str, list[BatchDocument]]:
    grouped: dict[str, list[BatchDocument]] = {}
    for document in documents:
        key = document.project.project_name_normalized or f"__UNRESOLVED__:{document.path}"
        grouped.setdefault(key, []).append(document)
    return grouped


def _group_to_discovery(documents: list[BatchDocument]) -> ProjectDiscovery:
    # The first document is the authoritative representative; all documents
    # in the group already share the same normalized project key.
    return documents[0].project


def _files_for_ahu(documents: list[BatchDocument], normalized_ahu: str | None) -> tuple[str, ...]:
    if not normalized_ahu:
        return ()
    return tuple(
        document.path
        for document in documents
        if normalized_ahu in {normalize_equipment_id(x) for x in document.equipment}
    )


def _extract_side_motors(paths: tuple[str, ...], side: str, target_ahu: str | None = None):
    records = []
    for path in paths:
        if side == "PDF1":
            results = find_rated_motor_powers_in_pdf(path)
            records.extend(record for result in results for record in build_stage1_motor_records(result))
        else:
            results = find_pdf2_motor_powers(path)
            counters: dict[tuple[str, str], int] = {}
            for result in results:
                key = (result.equipment_id, result.component_type)
                start = counters.get(key, 1)
                expanded = build_pdf2_motor_records(result, start_index=start)
                records.extend(expanded)
                counters[key] = start + len(expanded)
    if target_ahu is None:
        return records
    target = normalize_equipment_id(target_ahu)
    return [record for record in records if normalize_equipment_id(record.equipment_id) == target]


def analyze_batch(pdf1_paths: list[str | Path], pdf2_paths: list[str | Path]) -> BatchAnalysis:
    """Run the full project-aware batch motor pipeline."""
    left_docs = _discover_documents(pdf1_paths, "PDF1")
    right_docs = _discover_documents(pdf2_paths, "PDF2")
    left_groups = _group_documents(left_docs)
    right_groups = _group_documents(right_docs)

    left_group_items = [(_group_to_discovery(items), items) for items in left_groups.values()]
    right_group_items = [(_group_to_discovery(items), items) for items in right_groups.values()]

    project_matches: list[ProjectMatch] = []
    ahu_batches: list[BatchAHU] = []
    motor_comparisons: list[MotorComparison] = []

    project_pairs: list[tuple[ProjectDiscovery, list[BatchDocument], ProjectDiscovery, list[BatchDocument], ProjectMatch]] = []
    for left_discovery, left_documents in left_group_items:
        best: tuple[float, ProjectDiscovery, list[BatchDocument], ProjectMatch] | None = None
        for right_discovery, right_documents in right_group_items:
            match = match_discoveries(left_discovery, right_discovery)
            if best is None or match.score > best[0]:
                best = (match.score, right_discovery, right_documents, match)
        if best is not None and best[3].status != "NO_MATCH":
            project_pairs.append((left_discovery, left_documents, best[1], best[2], best[3]))

    # Enforce one-to-one project pairing after scoring.
    used_right: set[int] = set()
    ranked_pairs = sorted(project_pairs, key=lambda x: x[4].score, reverse=True)
    for left_discovery, left_documents, right_discovery, right_documents, project_match in ranked_pairs:
        right_id = id(right_documents)
        if right_id in used_right:
            continue
        used_right.add(right_id)
        project_matches.append(project_match)

        left_equipment = []
        right_equipment = []
        for document in left_documents:
            discovery = discover_equipment(document.path)
            left_equipment.extend(discovery.equipment_ids)
        for document in right_documents:
            discovery = discover_equipment(document.path)
            right_equipment.extend(discovery.equipment_ids)

        matches = match_ahu_lists(left_equipment, right_equipment)
        for ahu_match in matches:
            left_id = ahu_match.left_normalized
            right_id = ahu_match.right_normalized
            left_files = _files_for_ahu(left_documents, left_id)
            right_files = _files_for_ahu(right_documents, right_id)
            ahu_batches.append(BatchAHU(project_match.left_name, ahu_match, ahu_match if ahu_match.right_id else None, left_files, right_files))

            if ahu_match.status not in {"EXACT", "NORMALIZED_MATCH"}:
                continue
            left_motors = _extract_side_motors(left_files, "PDF1", left_id)
            right_motors = _extract_side_motors(right_files, "PDF2", right_id)
            motor_comparisons.extend(compare_motor_records(left_motors, right_motors))

    return BatchAnalysis(
        tuple(left_docs), tuple(right_docs), tuple(project_matches), tuple(ahu_batches), tuple(motor_comparisons)
    )
