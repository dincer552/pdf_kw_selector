from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
import fitz
from ahu_matching import AHUDiscovery, EquipmentOccurrence, normalize_equipment_id
from app_logger import exception, info, warning
from project_discovery import ProjectDiscovery, ProjectCandidate, normalize_project_name
from pdf1_field_discovery import discover_pdf1_project, discover_pdf1_unit_reference
from stage1_page_discovery import MotorPowerResult, build_stage1_motor_records, _dedupe_motor_results
from stage2_pdf_discovery import PDF2MotorResult, discover_coordinate_pdf2_motor_powers, build_pdf2_motor_records
from coordinate_motor_discovery import discover_coordinate_motor_powers

_PDF2_PROJECT_BOX = (376.0, 508.0, 344.0, 27.0)
_PDF2_AHU_BOX = (380.0, 448.0, 326.0, 33.0)


def _viewer_rect(page: fitz.Page, box) -> fitz.Rect:
    x, y, width, height = box
    page_height = float(page.rect.height)
    return fitz.Rect(x, page_height - (y + height), x + width, page_height - y)


def _coordinate_text(page: fitz.Page, box) -> str:
    words = page.get_text("words", clip=_viewer_rect(page, box))
    words.sort(key=lambda w: (w[1], w[0]))
    return " ".join(w[4].strip() for w in words if w[4].strip()).strip()


def _pdf2_coordinate_project(document: fitz.Document) -> ProjectDiscovery:
    if not document or len(document) < 1:
        return ProjectDiscovery(None, None, None, None, "REVIEW", ())
    value = _coordinate_text(document[0], _PDF2_PROJECT_BOX)
    if not value:
        return ProjectDiscovery(None, None, None, 1, "REVIEW", ())
    normalized = normalize_project_name(value)
    candidate = ProjectCandidate(value, normalized, "project_coordinates", 1, "HIGH")
    return ProjectDiscovery(value, normalized, "project_coordinates", 1, "HIGH", (candidate,))


def _pdf2_coordinate_ahu(document: fitz.Document) -> AHUDiscovery:
    if not document or len(document) < 1:
        return AHUDiscovery(())
    value = _coordinate_text(document[0], _PDF2_AHU_BOX)
    if not value:
        return AHUDiscovery(())
    normalized = normalize_equipment_id(value) or value
    return AHUDiscovery((EquipmentOccurrence(value, normalized, 1, "ahu_coordinates"),))


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
    def page_count(self):
        return len(self.page_texts)

    def to_dict(self):
        return {
            "path": self.path, "side": self.side, "page_count": self.page_count,
            "project": self.project.to_dict(), "equipment": self.equipment.to_dict(),
            "pdf1_motors": [x.to_dict() for x in self.pdf1_motors],
            "pdf2_motors": [x.to_dict() for x in self.pdf2_motors],
            "pdf1_ebm_pages": list(self.pdf1_ebm_pages),
        }


def _scan_pdf1_motors(pages, equipment_id=None, path=None, document=None):
    rows = []
    try:
        coord = discover_coordinate_motor_powers(path=path, document=document)
    except Exception as exc:
        warning("PDF1 koordinat motor taraması başarısız", path=str(path) if path else None, error=str(exc))
        coord = {}
    for results in coord.values():
        for result in results or ():
            if not result.equipment_id and equipment_id:
                result = result.__class__(page_number=result.page_number, value_kw=result.value_kw,
                    raw_value=result.raw_value, quantity=result.quantity, field=result.field,
                    confidence=result.confidence, source_text=result.source_text, component_type=result.component_type,
                    component_role=result.component_role, equipment_id=equipment_id, model_brand=result.model_brand)
            rows.append(result)
    return tuple(_dedupe_motor_results(rows))


def _scan_pdf2_motors(document, equipment_id=None):
    if not equipment_id:
        return ()
    return discover_coordinate_pdf2_motor_powers(document, equipment_id)


def _scan_single_pdf(path, side):
    side = side.upper().strip()
    resolved = Path(path).expanduser().resolve()
    doc = fitz.open(str(resolved))
    try:
        if side == "PDF1":
            pages = tuple(page.get_text("text") or "" for page in doc)
            project = discover_pdf1_project(list(pages), document=doc)
            equipment = discover_pdf1_unit_reference(list(pages), document=doc)
            ids = equipment.unique_ids(); equipment_id = ids[0] if ids else None
            motors = _scan_pdf1_motors(pages, equipment_id, path=resolved, document=doc)
            ebm_pages = tuple(sorted({r.page_number for r in motors if (r.model_brand or "").strip().casefold() == "ebm-papst"}))
            return MasterPDFScan(str(resolved), side, pages, project, equipment, pdf1_motors=motors, pdf1_ebm_pages=ebm_pages)
        if side == "PDF2":
            pages = tuple(page.get_text("text") or "" for page in doc)
            project = _pdf2_coordinate_project(doc); equipment = _pdf2_coordinate_ahu(doc)
            ids = equipment.unique_ids(); equipment_id = ids[0] if ids else None
            motors = _scan_pdf2_motors(doc, equipment_id)
            return MasterPDFScan(str(resolved), side, pages, project, equipment, pdf2_motors=motors)
        raise ValueError(f"Unknown PDF side: {side}")
    finally:
        doc.close()


# Cache key includes file modification time and size: unchanged PDFs are reused safely.
@lru_cache(maxsize=512)
def _scan_pdf_cached(path, side, mtime_ns, size):
    return _scan_single_pdf(path, side)


def scan_pdf(path, side):
    resolved = Path(path).expanduser().resolve()
    stat = resolved.stat()
    return _scan_pdf_cached(str(resolved), str(side).upper().strip(), stat.st_mtime_ns, stat.st_size)


def scan_pdfs(items, progress_callback=None):
    keys = {}
    for path, side in items:
        resolved = Path(path).expanduser().resolve()
        try:
            stat = resolved.stat()
        except OSError:
            continue
        keys.setdefault((str(resolved), str(side).upper().strip(), stat.st_mtime_ns, stat.st_size), 1)
    if not keys:
        return {}
    output = {}
    with ThreadPoolExecutor(max_workers=min(8, len(keys))) as executor:
        futures = {executor.submit(_scan_pdf_cached, *key): key for key in keys}
        for index, future in enumerate(as_completed(futures), 1):
            key = futures[future]; output[(key[0], key[1])] = future.result()
            if progress_callback:
                progress_callback("scan", index, len(keys), Path(key[0]).name)
    return output


def clear_master_scan_cache():
    _scan_pdf_cached.cache_clear()


def build_physical_motor_records(scan):
    output = []; indexes = {}
    results = scan.pdf1_motors if scan.side == "PDF1" else scan.pdf2_motors
    builder = build_stage1_motor_records if scan.side == "PDF1" else build_pdf2_motor_records
    for result in results:
        component = result.component_type or result.component_role or "motor"
        start_index = indexes.get(component, 1); made = builder(result, start_index=start_index)
        for r in made:
            if not getattr(r, "source_path", None) and getattr(scan, "path", None):
                r = replace(r, source_path=str(scan.path))
            output.append(r)
        indexes[component] = start_index + len(made)
    return output


__all__ = ["MasterPDFScan", "scan_pdf", "scan_pdfs", "clear_master_scan_cache", "build_physical_motor_records"]
