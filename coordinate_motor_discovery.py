from __future__ import annotations
import re
from pathlib import Path
import fitz
from pdf_kw_selector import normalize_power
from stage1_page_discovery import MotorPowerResult
_DIRECTION_RECT=(197.0,695.0,68.0,15.0)
_RATED_POWER_RECT=(429.0,634.0,131.0,13.0)
_MODEL_BRAND_RECT=(429.0,656.0,131.0,12.0)
_QTY_RE=re.compile(r"\(\s*(\d+)\s*[x×]\s*(\d+)\s*\)",re.I)
_POWER_QTY_RE=re.compile(r"^\s*([0-9]+(?:[.,][0-9]+)?)\s*[x×]\s*\(\s*(\d+)\s*[x×]\s*(\d+)\s*\)\s*$",re.I)
_POWER_ONLY_RE=re.compile(r"^\s*([0-9]+(?:[.,][0-9]+)?)\s*$")

def _viewer_rect(page,box):
 x,y,w,h=box; ph=float(page.rect.height)
 return fitz.Rect(x,ph-(y+h),x+w,ph-y)

def _rect_text(page,box):
 words=page.get_text("words",clip=_viewer_rect(page,box));words.sort(key=lambda w:(w[1],w[0]))
 return " ".join(w[4].strip() for w in words if w[4].strip()).strip()

def _is_plug_fan_page(page):
 return bool(re.search(r"\bplug\s+fan\b",page.get_text("text") or "",re.I))

def _parse_rated_power(raw):
 compact=re.sub(r"\s+"," ",raw.strip())
 m=_POWER_QTY_RE.match(compact)
 if m:return normalize_power(float(m.group(1).replace(",",".")),"kw"),m.group(1),f"{m.group(2)}x{m.group(3)}"
 m=_POWER_ONLY_RE.match(compact)
 if m:return normalize_power(float(m.group(1).replace(",",".")),"kw"),m.group(1),None
 number=re.search(r"([0-9]+(?:[.,][0-9]+)?)",compact);qty=_QTY_RE.search(compact)
 if number:return normalize_power(float(number.group(1).replace(",",".")),"kw"),number.group(1),(f"{qty.group(1)}x{qty.group(2)}" if qty else None)
 return None

def discover_coordinate_motor_powers(path: str|Path|None=None,document=None):
 result={};owns_document=document is None;doc=document if document is not None else fitz.open(str(path))
 try:
  for page_number,page in enumerate(doc,1):
   if not _is_plug_fan_page(page):continue
   direction=re.sub(r"\s+"," ",_rect_text(page,_DIRECTION_RECT)).strip().casefold()
   if direction not in {"supply air","exhaust air"}:continue
   rated_raw=_rect_text(page,_RATED_POWER_RECT);parsed=_parse_rated_power(rated_raw)
   if not parsed:continue
   value_kw,raw_value,quantity=parsed;model_brand=_rect_text(page,_MODEL_BRAND_RECT)
   if direction=="supply air":component_type,component_role="Vantilatör","supply_fan"
   else:component_type,component_role="Aspiratör","exhaust_fan"
   result.setdefault(page_number,[]).append(MotorPowerResult(page_number=page_number,value_kw=value_kw,raw_value=raw_value,quantity=quantity,field="fan_motor_power_coordinates",confidence="high",source_text=f"{direction.title()} | {rated_raw}",component_type=component_type,component_role=component_role,equipment_id=None,model_brand=model_brand or None))
 finally:
  if owns_document:doc.close()
 return result

__all__=["discover_coordinate_motor_powers"]
