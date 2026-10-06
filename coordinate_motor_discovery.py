from __future__ import annotations
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import fitz
from pdf_kw_selector import normalize_power
from stage1_page_discovery import MotorPowerResult
from motor_brand import normalize_motor_brand
_DIRECTION_RECT=(175.0,694.0,91.0,16.0)
_RATED_POWER_RECT=(429.0,634.0,131.0,13.0)
_MODEL_BRAND_RECT=(429.0,656.0,131.0,12.0)
_SELECTION_MODEL_RECT=(163.0,634.0,126.0,25.0)
_SELECTION_CURRENT_RECT=(429.0,578.0,129.0,13.0)
_QTY_RE=re.compile(r"\(\s*(\d+)\s*[x×]\s*(\d+)\s*\)",re.I)
_POWER_QTY_RE=re.compile(r"^\s*([0-9]+(?:[.,][0-9]+)?)\s*[x×]\s*\(\s*(\d+)\s*[x×]\s*(\d+)\s*\)\s*$",re.I)
_POWER_ONLY_RE=re.compile(r"^\s*([0-9]+(?:[.,][0-9]+)?)\s*$")
_CURRENT_VALUE_RE=re.compile(r"\s*([0-9]+(?:[.,][0-9]+)?)\s*A?\s*",re.I)
_SELECTION_QUANTITY_RE=re.compile(r"(?<!\d)(\d+)\s*[x×]\s*(\d+)(?!\d)",re.I)
_MODEL_TOKEN_RE=re.compile(r"(?<![\w])(?P<model>[A-Z0-9][A-Z0-9./-]*[A-Z0-9])(?![\w])",re.I)
_MODEL_LABEL_TOKENS={"FAN","EBM","PAPST","ZIEHL","ABEGG"}
_SUPPLIER_QUANTITY_RE=re.compile(
 r"Supplier\s*/\s*Model\s*/\s*Quantity\s+in\s+WxH\s*/?\s*"
 r"(?P<quantity>\d+\s*[x×]\s*\d+)",
 re.I,
)
_SUPPLIER_LABEL_RE=re.compile(r"Supplier\s*/\s*Model\s*/\s*Quantity\s+in\s+WxH\b",re.I)
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

def _rect_text_lines(page,box):
 if not isinstance(page,fitz.Page):
  return ()
 words=page.get_text("words",clip=_viewer_rect(page,box))
 lines={}
 for word in words:
  lines.setdefault((word[5],word[6]),[]).append(word)
 ordered=sorted(lines.values(),key=lambda line:(min(word[1] for word in line),min(word[0] for word in line)))
 return tuple(
  " ".join(word[4].strip() for word in sorted(line,key=lambda item:item[0]) if word[4].strip()).strip()
  for line in ordered if any(word[4].strip() for word in line)
 )

def _is_plug_fan_page(page):
 return bool(re.search(r"\bplug\s+fan\b",page.get_text("text") or "",re.I))

def _page_fan_direction(page_text):
 text=re.sub(r"\s+"," ",str(page_text or ""))
 plug_match=re.search(r"\bplug\s+fan\b",text,re.I)
 if plug_match:
  nearby=text[plug_match.end():plug_match.end()+240]
  direction_match=re.search(r"\b(supply|exhaust)\s+air\b",nearby,re.I)
  if direction_match:return f"{direction_match.group(1)} air".casefold()
 return None

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
   value_kw,raw_value,quantity=parsed;model_brand=normalize_motor_brand(_rect_text(page,_MODEL_BRAND_RECT))
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
   model_lines=_rect_text_lines(page,_SELECTION_MODEL_RECT)
   current_text=_rect_text(page,_SELECTION_CURRENT_RECT)
   page_text=page.get_text("text") or ""
   if direction not in {"supply air","exhaust air"}:
    direction=_page_fan_direction(page_text) or direction
   if not _CURRENT_VALUE_RE.fullmatch(current_text):
    current_match=_RATED_CURRENT_RE.search(page_text)
    current_text=current_match.group(1) if current_match else current_text
   model_result=parse_selection_motor_model(model_text,direction,page_number,current_text,page_text,model_lines)
   if model_result is not None:result.append(model_result)
 finally:
  if owns_document:doc.close()
 return tuple(result)

def _model_from_line(text):
 line=re.sub(r"\s+"," ",str(text or "")).strip()
 if not line:return None
 candidates=[
  match.group("model").strip().rstrip(".,;")
  for match in _MODEL_TOKEN_RE.finditer(_SELECTION_QUANTITY_RE.sub("",line))
  if match.group("model").strip(".,;").upper() not in _MODEL_LABEL_TOKENS
 ]
 if not candidates:return None
 return next((candidate for candidate in candidates if re.search(r"[A-Z]",candidate,re.I) and re.search(r"\d",candidate)),candidates[0])

def parse_selection_motor_model(text,direction,page_number=1,current_text="",page_text="",model_lines=()):
 component_role={"supply air":"supply_fan","exhaust air":"exhaust_fan"}.get(
  re.sub(r"\s+"," ",str(direction or "")).strip().casefold()
 )
 if component_role is None:return None
 raw_text=str(text or "")
 cleaned=re.sub(r"\s+"," ",raw_text)
 lines=tuple(str(line).strip() for line in model_lines if str(line).strip())
 if not lines:
  lines=tuple(line.strip() for line in raw_text.splitlines() if line.strip())
 # The top row is the motor model; the lower row may be only a supplier part number.
 model=_model_from_line(lines[0]) if lines else None
 normalized_page_text=re.sub(r"\s+"," ",str(page_text or ""))
 if model is None:return None
 quantity_matches=list(_SELECTION_QUANTITY_RE.finditer(cleaned))
 quantity_match=quantity_matches[-1] if quantity_matches else None
 if quantity_match is None:
  supplier_quantity=_SUPPLIER_QUANTITY_RE.search(normalized_page_text)
  if supplier_quantity:
   quantity_match=_SELECTION_QUANTITY_RE.search(supplier_quantity.group("quantity"))
  else:
   supplier_label=_SUPPLIER_LABEL_RE.search(normalized_page_text)
   if supplier_label:
    supplier_matches=list(_SELECTION_QUANTITY_RE.finditer(normalized_page_text[supplier_label.end():supplier_label.end()+160]))
    if supplier_matches:quantity_match=supplier_matches[-1]
 quantity=f"{quantity_match.group(1)}x{quantity_match.group(2)}" if quantity_match else None
 source_text=f"{model} / {quantity}" if quantity else model
 cleaned_current=re.sub(r"^[\s,:;|]+|[\s,:;|]+$","",str(current_text or ""))
 current_match=_CURRENT_VALUE_RE.fullmatch(cleaned_current)
 current=current_match.group(1) if current_match else None
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
