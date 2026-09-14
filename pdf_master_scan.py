from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor,as_completed
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re
import fitz
from pypdf import PdfReader
from ahu_matching import AHUDiscovery,EquipmentOccurrence,_equipment_from_filename,discover_equipment_from_text,normalize_equipment_id
from app_logger import exception,info,warning
from project_discovery import ProjectDiscovery,ProjectCandidate,normalize_project_name,discover_project_from_text
from pdf1_field_discovery import discover_pdf1_project,discover_pdf1_unit_reference
from stage1_page_discovery import MotorPowerResult,build_stage1_motor_records,extract_rated_motor_powers_from_page,_dedupe_motor_results
from stage2_pdf_discovery import PDF2MotorResult,_apply_summary_quantities,_dedupe,_equipment_id,_extract_connection_page,_fallback_connection_page,_summary_only_results,_summary_quantities,_unit_number_from_lines,build_pdf2_motor_records
from coordinate_motor_discovery import discover_coordinate_motor_powers

# PDF2 viewer coordinates use the same bottom-left origin as the user's PDF viewer.
# PyMuPDF uses a top-left origin, so the Y axis is converted in _viewer_rect().
_PDF2_PROJECT_BOX=(381.0,508.0,383.0,26.0)
_PDF2_AHU_BOX=(381.0,508.0,383.0,26.0)

def _viewer_rect(page,box):
    x,y,w,h=box
    ph=float(page.rect.height)
    return fitz.Rect(x,ph-(y+h),x+w,ph-y)

def _pdf2_coordinate_text(page,box):
    words=page.get_text('words',clip=_viewer_rect(page,box))
    words.sort(key=lambda w:(w[1],w[0]))
    return ' '.join(w[4].strip() for w in words if w[4].strip()).strip()

def _pdf2_coordinate_project(document):
    if not document:
        return ProjectDiscovery(None,None,None,None,'REVIEW',())
    page=document[0]
    value=_pdf2_coordinate_text(page,_PDF2_PROJECT_BOX)
    if not value:
        return ProjectDiscovery(None,None,None,1,'REVIEW',())
    normalized=normalize_project_name(value)
    candidate=ProjectCandidate(value,normalized,'coordinate',1,'HIGH')
    return ProjectDiscovery(value,normalized,'coordinate',1,'HIGH',(candidate,))

@dataclass(frozen=True)
class MasterPDFScan:
 path:str;side:str;page_texts:tuple[str,...];project:ProjectDiscovery;equipment:AHUDiscovery
 pdf1_motors:tuple[MotorPowerResult,...]=();pdf2_motors:tuple[PDF2MotorResult,...]=();pdf1_ebm_pages:tuple[int,...]=()
 @property
 def page_count(self):return len(self.page_texts)
 def to_dict(self):return {'path':self.path,'side':self.side,'page_count':self.page_count,'project':self.project.to_dict(),'equipment':self.equipment.to_dict(),'pdf1_motors':[x.to_dict() for x in self.pdf1_motors],'pdf2_motors':[x.to_dict() for x in self.pdf2_motors],'pdf1_ebm_pages':list(self.pdf1_ebm_pages)}

def _read_pages_once(path):return tuple(p.extract_text(extraction_mode='layout') or '' for p in PdfReader(str(path)).pages)
def _filename_equipment(path):
 stem=re.sub(r'\s+','_',Path(path).stem.strip());m=re.fullmatch(r'([A-Z0-9]+)[_ -]+AHU[_ -]?([A-Z]?\d+(?:\.\d+)?)',stem,re.I)
 if m:
  raw=f'{m.group(1).upper()}-AHU-{m.group(2).upper()}';return EquipmentOccurrence(raw,normalize_equipment_id(raw),1,'filename')
 m=re.fullmatch(r'(HKS|KS|SS|PW)[_ -]?([A-Z]?\d+(?:\.\d+)?)',Path(path).stem.strip(),re.I)
 if not m:return None
 raw=f'{m.group(1).upper()}-{m.group(2).upper()}';return EquipmentOccurrence(raw,normalize_equipment_id(raw),1,'filename')
_TOKEN_RE=re.compile(r'(?<![A-Z0-9])(?:VE\.A\.D\.\d+|HKS[_ -]?\d+|KS[_ -]?[A-Z]?\d+(?:\.\d+)?|SS[_ -]?[A-Z]?\d+(?:\.\d+)?|PW[_ -]?\d+(?:\.\d+)?|AHU(?:[_ -]+[A-Z0-9_.-]+|\d[A-Z0-9_.-]*))\b',re.I)
def _valid_equipment(v):
 if not v:return None
 n=normalize_equipment_id(v.strip(' .,:;()[]{}'))
 if not n or not re.search(r'\d',n):return None
 if re.fullmatch(r'(?:HKS|KS|SS|PW)-[A-Z]?\d+(?:\.\d+)?',n):return n
 if n.startswith('AHU-') or n.startswith('VE.A.D.'):return n
 if re.fullmatch(r'[A-Z0-9]+-AHU-[A-Z]?\d+(?:\.\d+)?',n):return n
 return None
def _pdf2_unit_number_equipment(pages,path=None):
 for pn,text in enumerate(pages,1):
  m=re.search(r'\bunit\s+number\s*[:=]?\s*([A-Z0-9][A-Z0-9_.-]*)',text or '',re.I)
  if m:
   n=_valid_equipment(m.group(1))
   if n:return EquipmentOccurrence(m.group(1),n,pn,'unit_number')
  v=_unit_number_from_lines(text or '');n=_valid_equipment(v)
  if n:return EquipmentOccurrence(v,n,pn,'unit_number')
 if path:
  f=_filename_equipment(Path(path))
  if f:return f
 for pn,text in enumerate(pages[:3],1):
  m=_TOKEN_RE.search(text or '')
  if m:
   n=_valid_equipment(m.group(0))
   if n:return EquipmentOccurrence(m.group(0),n,pn,'equipment_token')
 return None

def _scan_pdf1_motors(pages,equipment_id=None,path=None,document=None):
 rows=[];coord={}
 try:
  coord=discover_coordinate_motor_powers(path=path,document=document)
 except Exception as e:warning('PDF1 koordinat motor taraması başarısız',path=str(path) if path else None,error=str(e))
 for n,text in enumerate(pages,1):
  for r in (coord.get(n) or ()):
   if not r.equipment_id and equipment_id:r=r.__class__(page_number=r.page_number,value_kw=r.value_kw,raw_value=r.raw_value,quantity=r.quantity,field=r.field,confidence=r.confidence,source_text=r.source_text,component_type=r.component_type,component_role=r.component_role,equipment_id=equipment_id,model_brand=r.model_brand)
   rows.append(r)
 return tuple(_dedupe_motor_results(rows))
def _scan_pdf2_motors(pages,equipment_id=None):
 equipment_id=equipment_id or next((v for text in pages if (v:=_equipment_id(text))),None);summary=_summary_quantities(list(pages));rows=[]
 for n,text in enumerate(pages,1):
  r=_extract_connection_page(text,n,equipment_id) or _fallback_connection_page(text,n,equipment_id,summary)
  if r:rows.append(r)
 rows=_dedupe(rows)
 if not rows and summary:rows=_summary_only_results(equipment_id,summary,page_number=1)
 return tuple(_apply_summary_quantities(rows,summary))

def _scan_single_pdf(path,side):
 side=side.upper().strip();resolved=Path(path).expanduser().resolve()
 if side=='PDF1':
  doc=fitz.open(str(resolved))
  try:
   pages=tuple(page.get_text('text') or '' for page in doc)
   project=discover_pdf1_project(list(pages),document=doc)
   equipment=discover_pdf1_unit_reference(list(pages),document=doc)
   eid=equipment.unique_ids()[0] if equipment.unique_ids() else None
   motors=_scan_pdf1_motors(pages,eid,document=doc)
   ebm=tuple(sorted({r.page_number for r in motors if (r.model_brand or '').strip().casefold()=='ebm-papst'}))
   return MasterPDFScan(str(resolved),side,pages,project,equipment,pdf1_motors=motors,pdf1_ebm_pages=ebm)
  finally:doc.close()

 # PDF2 now uses one shared PyMuPDF document for page text and coordinate fields.
 doc=fitz.open(str(resolved))
 try:
  pages=tuple(page.get_text('text') or '' for page in doc)
  project=_pdf2_coordinate_project(doc)
  # The supplied AHU coordinate is currently identical to the project rectangle.
  # Do not turn the project value into an AHU ID; a correct AHU coordinate is needed.
  unit=_pdf2_unit_number_equipment(pages,resolved)
  f=_filename_equipment(resolved)
  if f and re.fullmatch(r'[A-Z0-9]+-AHU-[A-Z]?\d+(?:\.\d+)?',f.normalized):unit=f
  equipment=AHUDiscovery((unit,)) if unit else (AHUDiscovery((f,)) if f else discover_equipment_from_text(list(pages)))
  eid=equipment.unique_ids()[0] if equipment.unique_ids() else None
  return MasterPDFScan(str(resolved),side,pages,project,equipment,pdf2_motors=_scan_pdf2_motors(pages,eid))
 finally:doc.close()

@lru_cache(maxsize=128)
def scan_pdf(path,side):return _scan_single_pdf(path,side)
def scan_pdfs(items,progress_callback=None):
 keys={};
 for p,s in items:keys.setdefault((str(Path(p).expanduser().resolve()),str(s).upper().strip()),1)
 out={}
 with ThreadPoolExecutor(max_workers=min(8,len(keys))) as ex:
  fs={ex.submit(scan_pdf,*k):k for k in keys}
  for i,f in enumerate(as_completed(fs),1):
   k=fs[f];out[k]=f.result()
   if progress_callback:progress_callback('scan',i,len(keys),Path(k[0]).name)
 return out
def clear_master_scan_cache():scan_pdf.cache_clear()
def build_physical_motor_records(scan):
 out=[];idx={};results=scan.pdf1_motors if scan.side=='PDF1' else scan.pdf2_motors;builder=build_stage1_motor_records if scan.side=='PDF1' else build_pdf2_motor_records
 for r in results:
  c=r.component_type or r.component_role or 'motor';start=idx.get(c,1);made=builder(r,start_index=start);out.extend(made);idx[c]=start+len(made)
 return out
__all__=['MasterPDFScan','scan_pdf','scan_pdfs','clear_master_scan_cache','build_physical_motor_records']
