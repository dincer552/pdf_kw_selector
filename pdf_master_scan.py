"""Single-pass master scan for an engineering PDF.

The master scan opens a PDF once, extracts page text once, and computes the
Project/AHU/motor facts that downstream analysis needs from that in-memory
representation.  It intentionally keeps PDF1 EBM detection separate from
PDF2 because EBM-Papst classification is only required on the selection PDF.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from pypdf import PdfReader

from ahu_matching import AHUDiscovery, discover_equipment_from_text, _equipment_from_filename
from app_logger import exception, info, warning
from project_discovery import ProjectDiscovery, discover_project_from_text
from stage1_page_discovery import MotorPowerResult, build_stage1_motor_records, extract_rated_motor_powers_from_page, extract_model_brand
from stage2_pdf_discovery import (
    PDF2MotorResult,
    _apply_summary_quantities,
    _dedupe,
    _equipment_id,
    _extract_connection_page,
    _fallback_connection_page,
    _summary_only_results,
    _summary_quantities,
    build_pdf2_motor_records,
)


@dataclass(frozen=True)
class MasterPDFScan:
    path: str
    side: str
    page_texts: tuple[str, ...]
    project: ProjectDiscovery
    equipment: AHUDiscovery
    pdf1_motors: tuple[MotorPowerResult, ...] = ()
    pdf2_motors: tuple[PDF2MotorResult, ...] = ()
    pdf1_ebm_pages: tuple[int, ...] = ()

    @property
    def page_count(self) -> int:
        return len(self.page_texts)

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "side": self.side,
            "page_count": self.page_count,
            "project": self.project.to_dict(),
            "equipment": self.equipment.to_dict(),
            "pdf1_motors": [item.to_dict() for item in self.pdf1_motors],
            "pdf2_motors": [item.to_dict() for item in self.pdf2_motors],
            "pdf1_ebm_pages": list(self.pdf1_ebm_pages),
        }


def _read_pages_once(path: Path) -> tuple[str, ...]:
    """Open the PDF exactly once and extract every page exactly once."""
    reader = PdfReader(str(path))
    return tuple(page.extract_text() or "" for page in reader.pages)


def _scan_pdf1_motors(pages: tuple[str, ...]) -> tuple[MotorPowerResult, ...]:
    results = []
    for page_number, text in enumerate(pages, 1):
        results.extend(extract_rated_motor_powers_from_page(text, page_number))

    # Reuse Stage 1's existing de-duplication without reopening the PDF.
    from stage1_page_discovery import _dedupe_motor_results
    return tuple(_dedupe_motor_results(results))


def _scan_pdf2_motors(pages: tuple[str, ...]) -> tuple[PDF2MotorResult, ...]:
    equipment_id = next((_equipment_id(text) for text in pages if _equipment_id(text)), None)
    if not equipment_id:
        warning("PDF2 master scan: equipment ID bulunamadı")

    summary = _summary_quantities(list(pages))
    results = []
    for page_number, text in enumerate(pages, 1):
        result = _extract_connection_page(text, page_number, equipment_id)
        if not result:
            result = _fallback_connection_page(text, page_number, equipment_id, summary)
        if result:
            results.append(result)

    results = _dedupe(results)
    if not results and summary:
        results = _summary_only_results(equipment_id, summary, page_number=1)
    return tuple(_apply_summary_quantities(results, summary))


def scan_pdf(path: str | Path, side: str) -> MasterPDFScan:
    """Perform the complete first-pass scan for one PDF.

    ``side`` must be ``PDF1`` or ``PDF2``. PDF1 additionally records EBM pages;
    PDF2 deliberately performs no EBM scan.
    """
    side = side.upper().strip()
    if side not in {"PDF1", "PDF2"}:
        raise ValueError("side must be PDF1 or PDF2")

    resolved = Path(path).expanduser().resolve()
    try:
        info("Master PDF scan başladı", path=str(resolved), side=side)
        pages = _read_pages_once(resolved)
        project = discover_project_from_text(list(pages))
        equipment = discover_equipment_from_text(list(pages))
        if not equipment.unique_ids():
            filename_occurrence = _equipment_from_filename(resolved)
            if filename_occurrence is not None:
                from ahu_matching import AHUDiscovery
                equipment = AHUDiscovery((filename_occurrence,))

        if side == "PDF1":
            motors = _scan_pdf1_motors(pages)
            ebm_pages = tuple(
                page_number
                for page_number, text in enumerate(pages, 1)
                if extract_model_brand(text) == "EBM-Papst"
            )
            scan = MasterPDFScan(
                str(resolved), side, pages, project, equipment,
                pdf1_motors=motors,
                pdf1_ebm_pages=ebm_pages,
            )
        else:
            motors = _scan_pdf2_motors(pages)
            scan = MasterPDFScan(
                str(resolved), side, pages, project, equipment,
                pdf2_motors=motors,
            )

        info(
            "Master PDF scan tamamlandı",
            path=str(resolved), side=side, pages=len(pages),
            project=project.project_name,
            equipment=list(equipment.unique_ids()),
            motor_count=len(motors),
            ebm_pages=list(scan.pdf1_ebm_pages),
        )
        return scan
    except Exception as exc:
        exception("Master PDF scan başarısız", exc, path=str(resolved), side=side)
        raise


def build_physical_motor_records(scan: MasterPDFScan):
    """Build physical motor records entirely from the master-scan results."""
    records = []
    if scan.side == "PDF1":
        for result in scan.pdf1_motors:
            records.extend(build_stage1_motor_records(result))
    else:
        next_index = 1
        for result in scan.pdf2_motors:
            created = build_pdf2_motor_records(result, start_index=next_index)
            records.extend(created)
            next_index += len(created)
    return records


__all__ = ["MasterPDFScan", "scan_pdf", "build_physical_motor_records"]
