"""Single-pass master scan and cache for engineering PDFs."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re
from pypdf import PdfReader
from ahu_matching import AHUDiscovery, EquipmentOccurrence, _equipment_from_filename, discover_equipment_from_text, normalize_equipment_id
from app_logger import exception, info, warning, debug
from project_discovery import ProjectDiscovery, ProjectCandidate, discover_project_from_text, normalize_project_name
from pdf1_field_discovery import discover_pdf1_project, discover_pdf1_unit_reference
from stage1_page_discovery import MotorPowerResult, build_stage1_motor_records, extract_rated_motor_powers_from_page, extract_model_brand, _dedupe_motor_results
from stage2_pdf_discovery import PDF2MotorResult, _apply_summary_quantities, _dedupe, _equipment_id, _extract_connection_page, _fallback_connection_page, _summary_only_results, _summary_quantities, _unit_number_from_lines, build_pdf2_motor_records
from coordinate_motor_discovery import discover_coordinate_motor_powers

@dataclass(frozen=True)
class MasterPDFScan:
    path:str; side:str; page_texts:tuple[str,...]; project:ProjectDiscovery; equipment:AHUDiscovery
    pdf1_motors:tuple[MotorPowerResult,...]=(); pdf2_motors:tuple[PDF2MotorResult,...]=(); pdf1_ebm_pages:tuple[int,...]=()
    @property
    def page_count(self): return len(self.page_texts)
    def to_dict(self): return {"path":self.path,"side":self.side,"page_count":self.page_count,"project":self.project.to_dict(),"equipment":self.equipment.to_dict(),"pdf1_motors":[x.to_dict() for x in self.pdf1_motors],"pdf2_motors":[x.to_dict() for x in self.pdf2_motors],"pdf1_ebm_pages":list(self.pdf1_ebm_pages)}

def _read_pages_once(path):
    # Preserve the visual horizontal relationship between field labels and values.
    return tuple(page.extract_text(extraction_mode="layout") or "" for page in PdfReader(str(path)).pages)

_DIRECTION_COMPONENTS = {
    "supply": ("Vantilatör", "supply_fan"),
    "exhaust": ("Aspiratör", "exhaust_fan"),
    "return": ("Aspiratör", "return_fan"),
}

def _pdf1_coordinate_selection(text, raw_value=None):
    """Legacy text-layout selector retained as fallback when coordinate extraction is unavailable."""
    lines = (text or "").splitlines(); headers = []; rated_rows = []
    for y, line in enumerate(lines):
        header = re.search(r"\b(?:plug\s+fan|fan)\b.*?\b(supply|exhaust|return)\s+air(?=section|\s|$)", line, re.IGNORECASE)
        if not header: header = re.search(r"\b(supply|exhaust|return)\s+air(?=section|\s|$)", line, re.IGNORECASE)
        if header: headers.append((y, header.start(1), header.group(1).casefold(), line))
        if re.search(r"\brated\s+power\b", line, re.IGNORECASE):
            value_match = re.search(re.escape(str(raw_value)), line, re.IGNORECASE) if raw_value else None
            rated_rows.append((y, line.find("Rated Power"), value_match.start() if value_match else None, line))
    if not headers or not rated_rows: return None
    rated = rated_rows[0]
    if raw_value:
        for candidate in rated_rows:
            if candidate[2] is not None: rated = candidate; break
    prior = [header for header in headers if header[0] <= rated[0]]
    if not prior: return None
    selected = prior[-1]; component = _DIRECTION_COMPONENTS.get(selected[2])
    if not component: return None
    debug("PDF1 legacy coordinate selection fallback", header_y=selected[0], header_x=selected[1], rated_power_y=rated[0], rated_power_x=rated[1], direction=selected[2], raw_value=raw_value)
    return component

def _scan_pdf1_motors(pages, equipment_id=None, path=None):
    """Prefer real PDF word coordinates; fall back to existing text parser page-by-page."""
    rows=[]
    coordinate_rows = {}
    if path:
        try:
            coordinate_rows = discover_coordinate_motor_powers(path)
            info("PDF1 koordinat motor taraması",path=str(path),pages=len(coordinate_rows),results=sum(len(v) for v in coordinate_rows.values()))
        except Exception as exc:
            warning("PDF1 koordinat motor taraması başarısız, metin fallback kullanılacak",path=str(path),error=str(exc))
    for n,text in enumerate(pages,1):
        page_rows = coordinate_rows.get(n) or extract_rated_motor_powers_from_page(text,n)
        for result in page_rows:
            if not result.equipment_id and equipment_id:
                result = result.__class__(page_number=result.page_number, value_kw=result.value_kw, raw_value=result.raw_value, quantity=result.quantity, field=result.field, confidence=result.confidence, source_text=result.source_text, component_type=result.component_type, component_role=result.component_role, equipment_id=equipment_id, model_brand=result.model_brand)
            rows.append(result)
    return tuple(_dedupe_motor_results(rows))

def _filename_equipment(path):
    stem = re.sub(r"\s+", "_", Path(path).stem.strip())
    # Prefixed AHU filenames (AD_AHU_01, PR-AHU-01, U1-AHU-01) are distinct equipment.
    m = re.fullmatch(r"([A-Z0-9]+)[_ -]+AHU[_ -]?([A-Z]?\d+(?:\.\d+)?)", stem, re.I)
    if m:
        raw = f"{m.group(1).upper()}-AHU-{m.group(2).upper()}"
        return EquipmentOccurrence(raw, normalize_equipment_id(raw), 1, "filename")
    m=re.fullmatch(r"(HKS|KS|SS|PW)[_ -]?([A-Z]?\d+(?:\.\d+)?)",Path(path).stem.strip(),re.I)
    if not m:return None
    raw=f"{m.group(1).upper()}-{m.group(2).upper()}"; return EquipmentOccurrence(raw,normalize_equipment_id(raw),1,"filename")

_TOKEN_RE=re.compile(r"(?<![A-Z0-9])(?:VE\.A\.D\.\d+|HKS[_ -]?\d+|KS[_ -]?[A-Z]?\d+(?:\.\d+)?|SS[_ -]?[A-Z]?\d+(?:\.\d+)?|PW[_ -]?[A-Z]?\d+(?:\.\d+)?|AHU(?:[_ -]+[A-Z0-9_.-]+|\d[A-Z0-9_.-]*))\b",re.I)
def _valid_equipment(value):
    if not value:return None
    n=normalize_equipment_id(value.strip(" .,:;()[]{}"))
    if not n or not re.search(r"\d",n):return None
    if re.fullmatch(r"(?:HKS|KS|SS|PW)-[A-Z]?\d+(?:\.\d+)?",n):return n
    if n.startswith("AHU-") or n.startswith("VE.A.D."):return n
    if re.fullmatch(r"[A-Z0-9]+-AHU-[A-Z]?\d+(?:\.\d+)?",n):return n
    return None

def _pdf2_unit_number_equipment(pages,path=None):
    # Prefer the Unit Number field. Layout extraction keeps its value on the same visual row.
    # Filename and generic token discovery are controlled fallbacks only.
    for page_no,text in enumerate(pages,1):
        m=re.search(r"\bunit\s+number\s*[:=]?\s*([A-Z0-9][A-Z0-9_.-]*)",text or "",re.I)
        if m:
            n=_valid_equipment(m.group(1))
            if n:return EquipmentOccurrence(m.group(1),n,page_no,"unit_number")
        v=_unit_number_from_lines(text or ""); n=_valid_equipment(v)
        if n:return EquipmentOccurrence(v,n,page_no,"unit_number")
    if path is not None:
        f=_filename_equipment(Path(path))
        if f:return f
    for page_no,text in enumerate(pages[:3],1):
        m=_TOKEN_RE.search(text or "")
        if m:
            n=_valid_equipment(m.group(0))
            if n:return EquipmentOccurrence(m.group(0),n,page_no,"equipment_token")
    return None

def _safe_pdf2_project(pages,discovered):
    current=discovered.project_name or ""
    if current and not re.search(r"\bkw\b|m[³3]\s*/?\s*h|\bstage\b|\b(?:fan|motor|power)\b|^www\.|\bsystemair\b",current,re.I):return discovered
    candidates=[]
    for page_no,text in enumerate(pages[:3],1):
        for raw in (text or "").splitlines():
            value=re.sub(r"\s+"," ",raw).strip(" :-\t"); norm=normalize_project_name(value)
            if len(norm.split())<2 or re.search(r"\bkw\b|m[³3]\s*/?\s*h|\bstage\b|\b(?:fan|motor|power|air volume)\b|^www\.|\bsystemair\b|\b(?:address|adres|telefon|fax)\b",value,re.I):continue
            if re.fullmatch(r"(?:HKS|KS|SS|PW)[-_ ]?[A-Z]?\d+(?:\.\d+)?",value,re.I):continue
            candidates.append((sum(c.isalpha() for c in value)+len(value)+(20 if value.upper()==value else 0),value,page_no))
    if not candidates:return discovered
    _,value,page_no=max(candidates,key=lambda x:x[0]); c=ProjectCandidate(value,normalize_project_name(value),"project_name_field",page_no,"HIGH")
    return ProjectDiscovery(value,c.normalized,c.source,page_no,"HIGH",tuple(list(discovered.candidates)+[c]))

def _scan_pdf2_motors(pages,equipment_id=None):
    equipment_id=equipment_id or next((v for text in pages if (v:=_equipment_id(text))),None)
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
    filename_equipment=_filename_equipment(resolved)
    if side=="PDF1":
        project=discover_pdf1_project(list(pages)); discovered_equipment=discover_pdf1_unit_reference(list(pages))
        # A filename prefix is authoritative when the document itself only says generic AHU-1.
        # AD-AHU-01 and PR-AHU-01 are different physical units and must never collapse to AHU-1.
        if filename_equipment and re.fullmatch(r"[A-Z0-9]+-AHU-[A-Z]?\d+(?:\.\d+)?", filename_equipment.normalized):
            equipment=AHUDiscovery((filename_equipment,))
        else:
            equipment=discovered_equipment
        if not equipment.unique_ids():
            f=filename_equipment or _equipment_from_filename(resolved)
            if f:equipment=AHUDiscovery((f,))
        equipment_id=equipment.unique_ids()[0] if equipment.unique_ids() else None
        motors=_scan_pdf1_motors(pages,equipment_id,path=resolved)
        ebm=tuple(p for p,text in enumerate(pages,1) if extract_model_brand(text)=="EBM-Papst")
        info("PDF1 sabit alan keşfi",path=str(resolved),project=project.project_name,unit_reference=list(equipment.unique_ids()),ebm_pages=list(ebm))
        return MasterPDFScan(str(resolved),side,pages,project,equipment,pdf1_motors=motors,pdf1_ebm_pages=ebm)
    project=_safe_pdf2_project(pages,discover_project_from_text(list(pages)))
    unit=_pdf2_unit_number_equipment(pages,resolved)
    # Same rule on PDF2: when the electrical drawing filename carries AD/PR/U1/U2,
    # preserve that family instead of collapsing every AHU-1 Unit Number together.
    if filename_equipment and re.fullmatch(r"[A-Z0-9]+-AHU-[A-Z]?\d+(?:\.\d+)?", filename_equipment.normalized):
        unit=filename_equipment
    equipment=AHUDiscovery((unit,)) if unit else (AHUDiscovery((filename_equipment,)) if filename_equipment else discover_equipment_from_text(list(pages)))
    if not equipment.unique_ids() and filename_equipment:equipment=AHUDiscovery((filename_equipment,))
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
    return {key:scans_by_key[key] for key in unique}

def clear_master_scan_cache():scan_pdf.cache_clear()
def build_physical_motor_records(scan):
    records=[];next_index_by_component={}
    if scan.side=="PDF1":
        for result in scan.pdf1_motors:
            component=result.component_type or result.component_role or "motor";start=next_index_by_component.get(component,1);created=build_stage1_motor_records(result,start_index=start);records.extend(created);next_index_by_component[component]=start+len(created)
    else:
        for result in scan.pdf2_motors:
            component=result.component_type or result.component_role or "motor";start=next_index_by_component.get(component,1);created=build_pdf2_motor_records(result,start_index=start);records.extend(created);next_index_by_component[component]=start+len(created)
    return records
__all__=["MasterPDFScan","scan_pdf","scan_pdfs","clear_master_scan_cache","build_physical_motor_records"]
