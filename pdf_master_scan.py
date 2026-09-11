"""Single-pass master scan and cache for engineering PDFs."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from pypdf import PdfReader

from ahu_matching import AHUDiscovery, discover_equipment_from_text, _equipment_from_filename
from app_logger import exception, info, warning
from project_discovery import ProjectDiscovery, discover_project_from_text
from stage1_page_discovery import MotorPowerResult, build_stage1_motor_records, extract_rated_motor_powers_from_page, extract_model_brand, _dedupe_motor_results
from stage2_pdf_discovery import PDF2MotorResult, _apply_summary_quantities, _dedupe, _equipment_id, _extract_connection_page, _fallback_connection_page, _summary_only_results, _summary_quantities, build_pdf2_motor_records


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
        return {"path": self.path, "side": self.side, "page_count": self.page_count, "project": self.project.to_dict(), "equipment": self.equipment.to_dict(), "pdf1_motors": [x.to_dict() for x in self.pdf1_motors], "pdf2_motors": [x.to_dict() for x in self.pdf2_motors], "pdf1_ebm_pages": list(self.pdf1_ebm_pages)}


def _read_pages_once(path: Path) -> tuple[str, ...]:
    reader = PdfReader(str(path))
    return tuple(page.extract_text() or "" for page in reader.pages)


def _scan_pdf1_motors(pages: tuple[str, ...]) -> tuple[MotorPowerResult, ...]:
    results = []
    for page_number, text in enumerate(pages, 1):
        results.extend(extract_rated_motor_powers_from_page(text, page_number))
    return tuple(_dedupe_motor_results(results))


def _scan_pdf2_motors(pages: tuple[str, ...]) -> tuple[PDF2MotorResult, ...]:
    equipment_ids = [value for text in pages if (value := _equipment_id(text))]
    equipment_id = equipment_ids[0] if equipment_ids else None
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


def _scan_single_pdf(path: str | Path, side: str) -> MasterPDFScan:
    side = side.upper().strip()
    if side not in {"PDF1", "PDF2"}:
        raise ValueError("side must be PDF1 or PDF2")
    resolved = Path(path).expanduser().resolve()
    info("Master PDF scan başladı", path=str(resolved), side=side)
    pages = _read_pages_once(resolved)
    project = discover_project_from_text(list(pages))
    if side == "PDF1":
        # PDF1 equipment identity comes only from the value paired with the
        # fixed "Unit Reference" label. Do not infer it from AHU/HKS text or
        # the filename; AHU-KIT and similar incidental text is irrelevant.
        equipment = discover_equipment_from_text(list(pages), unit_reference_only=True)
        motors = _scan_pdf1_motors(pages)
        motor_pages = {result.page_number for result in motors}
        ebm_pages = tuple(page for page in sorted(motor_pages) if extract_model_brand(pages[page - 1]) == "EBM-Papst")
        return MasterPDFScan(str(resolved), side, pages, project, equipment, pdf1_motors=motors, pdf1_ebm_pages=ebm_pages)

    equipment = discover_equipment_from_text(list(pages))
    if not equipment.unique_ids():
        filename_occurrence = _equipment_from_filename(resolved)
        if filename_occurrence is not None:
            equipment = AHUDiscovery((filename_occurrence,))
    motors = _scan_pdf2_motors(pages)
    return MasterPDFScan(str(resolved), side, pages, project, equipment, pdf2_motors=motors)


@lru_cache(maxsize=128)
def scan_pdf(path: str | Path, side: str) -> MasterPDFScan:
    """Read and analyze a PDF once; subsequent calls reuse the complete scan."""
    try:
        return _scan_single_pdf(path, side)
    except Exception as exc:
        resolved = Path(path).expanduser().resolve()
        exception("Master PDF scan başarısız", exc, path=str(resolved), side=str(side).upper().strip())
        raise


def scan_pdfs(paths_and_sides: list[tuple[str | Path, str]]) -> dict[tuple[str, str], MasterPDFScan]:
    """Warm the master-scan cache for independent PDFs concurrently."""
    unique = {}
    for raw_path, raw_side in paths_and_sides:
        path = str(Path(raw_path).expanduser().resolve())
        side = str(raw_side).upper().strip()
        unique.setdefault((path, side), (path, side))
    if not unique:
        return {}
    workers = min(8, len(unique))
    info("Paralel master scan başladı", file_count=len(unique), worker_count=workers)
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="pdf-scan") as executor:
        scans = list(executor.map(lambda item: scan_pdf(*item), unique.values()))
    result = dict(zip(unique.keys(), scans))
    info("Paralel master scan tamamlandı", file_count=len(result))
    return result


def clear_master_scan_cache() -> None:
    scan_pdf.cache_clear()


def build_physical_motor_records(scan: MasterPDFScan):
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


__all__ = ["MasterPDFScan", "scan_pdf", "scan_pdfs", "clear_master_scan_cache", "build_physical_motor_records"]
