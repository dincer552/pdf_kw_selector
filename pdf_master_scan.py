"""Single-pass master scan and cache for engineering PDFs."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re
from pypdf import PdfReader
from ahu_matching import AHUDiscovery, EquipmentOccurrence, _equipment_from_filename, discover_equipment_from_text, normalize_equipment_id
from app_logger import exception, info, warning
from project_discovery import ProjectDiscovery, discover_project_from_text
from pdf1_field_discovery import discover_pdf1_project, discover_pdf1_unit_reference
from stage1_page_discovery import MotorPowerResult, build_stage1_motor_records, extract_rated_motor_powers_from_page, extract_model_brand, _dedupe_motor_results
from stage2_pdf_discovery import PDF2MotorResult, _apply_summary_quantities, _dedupe, _equipment_id, _extract_connection_page, _fallback_connection_page, _summary_only_results, _summary_quantities, _unit_number_from_lines, build_pdf2_motor_records

@dataclass(frozen=True)
class MasterPDFScan:
    path:str; side:str; page_texts:tuple[str,...]; project:ProjectDiscovery; equipment:AHUDiscovery
    pdf1_motors:tuple[MotorPowerResult,...]=(); pdf2_motors:tuple[PDF2MotorResult,...]=(); pdf1_ebm_pages:tuple[int,...]=()
    @property
    def page_count(self): return len(self.page_texts)
    def to_dict(self): return {"path":self.path,"side":self.side,"page_count":self.page_count,"project":self.project.to_dict(),"equipment":self.equipment.to_dict(),"pdf1_motors":[x.to_dict() for x in self.pdf1_motors],"pdf2_motors":[x.to_dict() for x in self.pdf2_motors],"pdf1_ebm_pages":list(self.pdf1_ebm_pages)}

def _read_pages_once(path): return tuple(page.extract_text() or "" for page in PdfReader(str(path)).pages)
def _scan_pdf1_motors(pages):
    rows=[]
    for n,text in enumerate(pages,1): rows.extend(extract_rated_motor_powers_from_page(text,n))
    return tuple(_dedupe_motor_results(rows))
def _filename_equipment(path):
    stem=Path(path).stem.strip(); match=re.fullmatch(r"(HKS|KS|SS|PW)[_ -]?([A-Z]?\d+(?:\.\d+)?)",stem,re.I)
    if not match:return None
    raw=f"{match.group(1).upper()}-{match.group(2).upper()}"; normalized=normalize_equipment_id(raw)
    return EquipmentOccurrence(raw,normalized,1,"filename") if normalized else None
def _pdf2_unit_number_equipment(pages):
    for page_no,text in enumerate(pages,1):
        value=_unit_number_from_lines(text)
        if value:return EquipmentOccurrence(value,value,page_no,"unit_number")
        inline=re.search(r"\bunit\s+number\s*[:=]?\s*(?P<value>[A-Z0-9][A-Z0-9_.-]*)",text or "",re.I)
        if inline:
            raw=inline.group("value").strip(".,;:()[]{}"); normalized=normalize_equipment_id(raw)
            if normalized and re.search(r"\d",normalized):return EquipmentOccurrence(raw,normalized,page_no,"unit_number")
    return None
def _scan_pdf2_motors(pages,equipment_id=None):
    ids=[v for text in pages if (v:=_equipment_id(text))]; equipment_id=equipment_id or (ids[0] if ids else None)
    if not equipment_id:warning("PDF2 master scan: equipment ID bulunamadı")
    summary=_summary_quantities(list(pages)); rows=[]
    for n,text in enumerate(pages,1):
        row=_extract_connection_page(text,n,equipment_id) or _fallback_connection_page(text,n,equipment_id,summary)
        if row:rows.append(row)
    rows=_dedupe(rows)
    if not rows and summary:rows=_summary_only_results(equipment_id,summary,page_number=1)
    return tuple(_apply_summary_quantities(rows,summary))
def _scan_single_pdf(path,side):
    side=side.upper().strip(); resolved=Path(path).expanduser().resolve()
    if side not in {"PDF1","PDF2"}:raise ValueError("side must be PDF1 or PDF2")
    info("Master PDF scan başladı",path=str(resolved),side=side); pages=_read_pages_once(resolved)
    if side=="PDF1":
        project=discover_pdf1_project(list(pages)); equipment=discover_pdf1_unit_reference(list(pages)); motors=_scan_pdf1_motors(pages)
        if not equipment.unique_ids():
            fallback=_filename_equipment(resolved) or _equipment_from_filename(resolved)
            if fallback:equipment=AHUDiscovery((fallback,))
        ebm=tuple(p for p,text in enumerate(pages,1) if extract_model_brand(text)=="EBM-Papst")
        info("PDF1 sabit alan keşfi",path=str(resolved),project=project.project_name,unit_reference=list(equipment.unique_ids()),ebm_pages=list(ebm))
        return MasterPDFScan(str(resolved),side,pages,project,equipment,pdf1_motors=motors,pdf1_ebm_pages=ebm)
    project=discover_project_from_text(list(pages)); unit_number=_pdf2_unit_number_equipment(pages)
    equipment=AHUDiscovery((unit_number,)) if unit_number else discover_equipment_from_text(list(pages))
    if not equipment.unique_ids():
        fallback=_filename_equipment(resolved) or _equipment_from_filename(resolved)
        if fallback:equipment=AHUDiscovery((fallback,))
    equipment_id=equipment.unique_ids()[0] if equipment.unique_ids() else None
    info("PDF2 sabit alan keşfi",path=str(resolved),project=project.project_name,unit_number=list(equipment.unique_ids()))
    return MasterPDFScan(str(resolved),side,pages,project,equipment,pdf2_motors=_scan_pdf2_motors(pages,equipment_id))
@lru_cache(maxsize=128)
def scan_pdf(path,side):
    try:return _scan_single_pdf(path,side)
    except Exception as exc:
        exception("Master PDF scan başarısız",exc,path=str(Path(path).expanduser().resolve()),side=str(side).upper().strip());raise
def scan_pdfs(paths_and_sides,progress_callback=None):
    unique={}
    for raw_path,raw_side in paths_and_sides:
        key=(str(Path(raw_path).expanduser().resolve()),str(raw_side).upper().strip());unique.setdefault(key,key)
    if not unique:return {}
    info("Paralel master scan başladı",file_count=len(unique),worker_count=min(8,len(unique)));scans_by_key={}
    with ThreadPoolExecutor(max_workers=min(8,len(unique)),thread_name_prefix="pdf-scan") as ex:
        futures={ex.submit(scan_pdf,*key):key for key in unique.values()}
        for completed,future in enumerate(as_completed(futures),1):
            key=futures[future];scans_by_key[key]=future.result()
            if progress_callback:progress_callback("scan",completed,len(unique),Path(key[0]).name)
    scans=[scans_by_key[key] for key in unique.values()];return dict(zip(unique.keys(),scans))
def clear_master_scan_cache():scan_pdf.cache_clear()
def build_physical_motor_records(scan):
    records=[];next_index_by_component={}
    if scan.side=="PDF1":
        for result in scan.pdf1_motors:
            component=result.component_type or result.component_role or "motor";start_index=next_index_by_component.get(component,1);created=build_stage1_motor_records(result,start_index=start_index);records.extend(created);next_index_by_component[component]=start_index+len(created)
    else:
        for result in scan.pdf2_motors:
            component=result.component_type or result.component_role or "motor";start_index=next_index_by_component.get(component,1);created=build_pdf2_motor_records(result,start_index=start_index);records.extend(created);next_index_by_component[component]=start_index+len(created)
    return records
__all__=["MasterPDFScan","scan_pdf","scan_pdfs","clear_master_scan_cache","build_physical_motor_records"]
