from __future__ import annotations
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import fitz
from pdf_kw_selector import normalize_power
from stage1_page_discovery import MotorPowerResult
_DIRECTION_RECT=(175.0,694.0,91.0,16.0)
_RATED_POWER_RECT=(429.0,634.0,131.0,13.0)
_MODEL_BRAND_RECT=(429.0,656.0,131.0,12.0)
_SELECTION_MODEL_RECT=(162.0,634.0,127.0,25.0)
_SELECTION_CURRENT_RECT=(429.0,578.0,129.0,13.0)
_QTY_RE=re.compile(r"\(\s*(\d+)\s*[x×]\s*(\d+)\s*\)",re.I)
_POWER_QTY_RE=re.compile(r"^\s*([0-9]+(?:[.,][0-9]+)?)\s*[x×]\s*\(\s*(\d+)\s*[x×]\s*(\d+)\s*\)\s*$",re.I)
_POWER_ONLY_RE=re.compile(r"^\s*([0-9]+(?:[.,][0-9]+)?)\s*$")
_SELECTION_MODEL_RE=re.compile(
 r"\b(?P<model>[A-Z0-9][A-Z0-9.-]*(?:/[A-Z0-9.-]+)*)\s*/\s*"
 r"(?P<quantity>\d+\s*[x×]\s*\d+)",
 re.I,
)
_CURRENT_VALUE_RE=re.compile(r"\s*([0-9]+(?:[.,][0-9]+)?)\s*A?\s*",re.I)
_SELECTION_QUANTITY_RE=re.compile(r"(?<!\d)(\d+)\s*[x×]\s*(\d+)(?!\d)",re.I)
_FAN_TYPE_CODE_RE=re.compile(r"\b[A-Z0-9]+(?:-[A-Z0-9]+)+\b",re.I)
_FAN_TYPE_ROW_RE=re.compile(r"\bType\s+(?P<value>.*?)\s+Model\s+Brand\b",re.I|re.S)
_SUPPLIER_QUANTITY_RE=re.compile(
 r"Supplier\s*/\s*Model\s*/\s*Quantity\s+in\s+WxH\s*/?\s*"
 r"(?P<quantity>\d+\s*[x×]\s*\d+)",
 re.I,
)
_RATED_CURRENT_RE=re.compile(r"\bRated\s+Current\s*\[A\]\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)",re.I)

@dataclass(frozen=True)
class MotorModelResult:
 page_number:int
 component_role:str
 model:str
 quantity:str|None
 source_text:str
 current:str|None=None

 def to_dict(self):
  return {"page_number":self.page_number,"component_role":self.component_role,"model":self.model,"quantity":self.quantity,"current":self.current,"source_text":self.source_text}

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

def discover_selection_motor_models(path: str|Path|None=None,document=None):
 result=[];owns_document=document is None;doc=document if document is not None else fitz.open(str(path))
 try:
  for page_number,page in enumerate(doc,1):
   if not _is_plug_fan_page(page):continue
   direction=re.sub(r"\s+"," ",_rect_text(page,_DIRECTION_RECT)).strip().casefold()
   model_text=_rect_text(page,_SELECTION_MODEL_RECT)
   current_text=_rect_text(page,_SELECTION_CURRENT_RECT)
   page_text=page.get_text("text") or ""
   if direction not in {"supply air","exhaust air"}:
    direction_match=re.search(r"\bPlug\s+fan\s+(Supply\s+air|Exhaust\s+air)\b",page_text,re.I)
    direction=direction_match.group(1).casefold() if direction_match else direction
   if not _CURRENT_VALUE_RE.fullmatch(current_text):
    current_match=_RATED_CURRENT_RE.search(page_text)
    current_text=current_match.group(1) if current_match else current_text
   model_result=parse_selection_motor_model(model_text,direction,page_number,current_text,page_text)
   if model_result is not None:result.append(model_result)
 finally:
  if owns_document:doc.close()
 return tuple(result)

def parse_selection_motor_model(text,direction,page_number=1,current_text="",page_text=""):
 component_role={"supply air":"supply_fan","exhaust air":"exhaust_fan"}.get(
  re.sub(r"\s+"," ",str(direction or "")).strip().casefold()
 )
 if component_role is None:return None
 cleaned=re.sub(r"\s+"," ",str(text or ""))
 match=_SELECTION_MODEL_RE.search(cleaned)
 if match:
  model=match.group("model").strip().rstrip(".,;")
  quantity=re.sub(r"\s*[x×]\s*","x",match.group("quantity"))
 else:
  quantity_match=_SELECTION_QUANTITY_RE.search(cleaned)
  if quantity_match is None:
   supplier_quantity=_SUPPLIER_QUANTITY_RE.search(re.sub(r"\s+"," ",str(page_text or "")))
   if supplier_quantity:
    quantity_match=_SELECTION_QUANTITY_RE.search(supplier_quantity.group("quantity"))
  if quantity_match is None:return None
  quantity=f"{quantity_match.group(1)}x{quantity_match.group(2)}"
  type_row=_FAN_TYPE_ROW_RE.search(re.sub(r"\s+"," ",str(page_text or "")))
  if type_row is None:return None
  model_match=_FAN_TYPE_CODE_RE.search(type_row.group("value"))
  if model_match is None:return None
  model=model_match.group(0).strip()
 current_match=_CURRENT_VALUE_RE.fullmatch(str(current_text or ""))
 current=current_match.group(1) if current_match else None
  source_text=match.group(0) if match else f"{model} / {quantity}"
  return MotorModelResult(page_number,component_role,model,quantity,source_text,current)

def normalize_motor_model(model):
 return re.sub(r"[^A-Z0-9]","",str(model or "").upper())

def compare_motor_model_lists(selection_models,electrical_models):
 selection=[normalize_motor_model(model) for model in selection_models if normalize_motor_model(model)]
 electrical=[normalize_motor_model(model) for model in electrical_models if normalize_motor_model(model)]
 if not selection:return "Seçim çıktısında motor modeli bulunamadı"
 if not electrical:return "Elektrik projesinde motor modeli bulunamadı"
 return "MODEL EŞLEŞTİ" if Counter(selection)==Counter(electrical) else "MODEL UYUŞMAZ"

def expand_model_quantity(model_result):
 match=re.fullmatch(r"(\d+)x(\d+)",str(model_result.quantity or "1x1"),re.I)
 count=int(match.group(1))*int(match.group(2)) if match else 1
 return [model_result.model]*count

__all__=["MotorModelResult","discover_coordinate_motor_powers","discover_selection_motor_models","parse_selection_motor_model","normalize_motor_model","compare_motor_model_lists","expand_model_quantity"]
