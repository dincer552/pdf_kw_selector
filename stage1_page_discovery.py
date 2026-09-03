"""Stage 1: discover rated motor-power pages and fan direction."""
from __future__ import annotations
import re
import unicodedata
from dataclasses import asdict, dataclass
from motor_database import expand_motor_group
from pdf_kw_selector import normalize_power
RATED_POWER_RE = re.compile(r"(?:anma\s+g(?:ü|u|�)c(?:ü|u|�)|anma\s+g[^a-z0-9\s]{0,2}c[^a-z0-9\s]{0,2}|rated\s+power)\s*\[?\s*kw\s*\]?\s*[:=\-]?\s*(?P<value>\d+(?:[.,]\d+)?)(?:\s*[x×]\s*\(?\s*(?P<quantity>\d+(?:[.,]\d+)?(?:\s*[x×]\s*\d+)?)\s*\)?)?", re.IGNORECASE)
FAN_MOTOR_POWER_RE = re.compile(r"fan\s+motor\s+power\s*[:=\-]?\s*(?P<value>\d+(?:[.,]\d+)?)\s*\[?\s*kw\s*\]?(?:\s*\(?\s*(?P<quantity>\d+(?:[.,]\d+)?(?:\s*[x×]\s*\d+)?)\s*\)?)?", re.IGNORECASE)
STANDALONE_MOTOR_POWER_RE = re.compile(r"(?:anma\s+g[^\s]{0,8}|rated\s+power|fan\s+motor\s+power)\s*\[?\s*kw\s*\]?\s*[:=\-]?\s*(?P<value>\d+(?:[.,]\d+)?)", re.IGNORECASE)
PAGE_POSITIVE_TERMS = {"anma gücü":60,"rated power":60,"motor data":35,"fan data":25,"plug fan":20,"supply air":15,"return air":15,"exhaust air":15,"nominal rpm":8,"model / miktar":8,"fan motor power":45}
PAGE_NEGATIVE_TERMS = {"cooling capacity":-25,"heating capacity":-25,"shaft power":-15,"vfd dahil":-12,"vfd hariç":-12,"unit total power":-20,"tot. abs. power":-15}
@dataclass(frozen=True)
class PageCandidate:
    page_number:int; score:int; text:str; matched_terms:tuple[str,...]=()
    def to_dict(self): return asdict(self)
@dataclass(frozen=True)
class MotorPowerResult:
    page_number:int; value_kw:float; raw_value:str; quantity:str|None; field:str; confidence:str; source_text:str; component_type:str|None=None; component_role:str|None=None; equipment_id:str|None=None
    def to_dict(self): return asdict(self)
def _clean(text): return re.sub(r"\s+"," ",text).strip()
def _ascii(text): return "".join(ch for ch in unicodedata.normalize("NFKD",text) if not unicodedata.combining(ch)).lower()
def _has_rated_power(text): return bool(RATED_POWER_RE.search(text) or FAN_MOTOR_POWER_RE.search(text) or STANDALONE_MOTOR_POWER_RE.search(text))
def _page_score(text):
    lowered=_clean(text).lower(); score=0; matched=[]
    for term,weight in PAGE_POSITIVE_TERMS.items():
        if term in lowered or _ascii(term) in _ascii(lowered): score+=weight; matched.append(f"+{term}")
    for term,weight in PAGE_NEGATIVE_TERMS.items():
        if term in lowered or _ascii(term) in _ascii(lowered): score+=weight; matched.append(f"{weight}:{term}")
    if _has_rated_power(lowered): score+=80; matched.append("explicit rated power")
    return score,tuple(matched)
def discover_motor_power_page(page_texts):
    return sorted([PageCandidate(i,score,_clean(t),matched) for i,t in enumerate(page_texts,1) for score,matched in [_page_score(t)]],key=lambda x:(-x.score,x.page_number))
def _normalize_quantity(q): return None if not q else re.sub(r"\s*[x×]\s*","x",q.strip())
def detect_component_type(text):
    lowered=_clean(text).lower(); supply=bool(re.search(r"\bsupply\s+air\b",lowered)); ret_air=bool(re.search(r"\breturn\s+air\b",lowered)); exhaust=bool(re.search(r"\bexhaust\s+air\b",lowered)); ret_short=bool(re.search(r"\breturn\b",lowered))
    if supply and not(ret_air or exhaust): return "Vantilatör","supply_fan"
    if exhaust and not supply: return "Aspiratör","exhaust_fan"
    if (ret_air or ret_short) and not supply: return "Aspiratör","return_fan"
    return None,None
def extract_equipment_id(text):
    cleaned=_clean(text); ref=re.search(r"(?:unit\s+reference|birim\s+referans[ıi])\s*[:#-]?\s*([A-Z0-9]+(?:[-_.]\s*[A-Z0-9]+)+|[A-Z]{2,}\s+\d+)\b",cleaned,re.I)
    if ref:
        raw=ref.group(1).strip(); compact=re.sub(r"[-_\s]+","-",raw).upper(); m=re.fullmatch(r"PW-0*(\d+)",compact); return f"PW{int(m.group(1))}" if m else compact
    m=re.search(r"\bAHU\s*[-_ ]?\s*(\d+)\b",cleaned,re.I); return f"AHU{int(m.group(1))}" if m else None
def _local_context(text,match):
    cleaned=_clean(text); before=cleaned[:match.start()]; directions=list(re.finditer(r"\b(?:supply|return|exhaust)\s+air\b",before,re.I)); start=directions[-1].start() if directions else max(0,match.start()-500); after=cleaned[match.end():]; nxt=re.search(r"\b(?:supply|return|exhaust)\s+air\b",after,re.I); end=match.end()+180 if not nxt else match.end()+nxt.start()
    if not directions:
        short_direction=list(re.finditer(r"\b(?:supply|return|exhaust)\b",before,re.I))
        if short_direction: start=short_direction[-1].start()
    return cleaned[start:end]
def _result_from_match(text,page_number,match):
    cleaned=_clean(text); raw=match.group("value"); value=normalize_power(float(raw.replace(",",".")),"kw"); q=_normalize_quantity(match.groupdict().get("quantity")); context=_local_context(cleaned,match); typ,role=detect_component_type(context)
    return MotorPowerResult(page_number,value,raw,q,"fan_motor_power","high" if role else "review",cleaned[max(0,match.start()-120):min(len(cleaned),match.end()+120)],typ,role,extract_equipment_id(cleaned))
def extract_rated_motor_powers_from_page(text,page_number):
    cleaned=_clean(text); matches=[]
    for p in (RATED_POWER_RE,FAN_MOTOR_POWER_RE): matches.extend((m.start(),m) for m in p.finditer(cleaned))
    results=[]; seen=set()
    for _,m in sorted(matches,key=lambda x:x[0]):
        r=_result_from_match(cleaned,page_number,m); key=(m.start(),r.raw_value,r.quantity)
        if r.component_role is None or key in seen: continue
        seen.add(key); results.append(r)
    return results
def extract_rated_motor_power_from_page(text,page_number):
    results=extract_rated_motor_powers_from_page(text,page_number)
    if results: return results[0]
    cleaned=_clean(text); m=STANDALONE_MOTOR_POWER_RE.search(cleaned)
    if m: return _result_from_match(cleaned,page_number,m)
    return None
def _dedupe_motor_results(results):
    unique=[]; seen=set()
    for result in results:
        family="Vantilatör" if result.component_type=="Vantilatör" else "Aspiratör" if result.component_type=="Aspiratör" else result.component_role
        key=(result.equipment_id,family,result.value_kw,result.quantity)
        if key in seen: continue
        seen.add(key); unique.append(result)
    return unique
def find_rated_motor_powers_in_pdf(path):
    from pypdf import PdfReader
    results=[]
    for page_number,page in enumerate(PdfReader(str(path)).pages,1): results.extend(extract_rated_motor_powers_from_page(page.extract_text() or "",page_number))
    return _dedupe_motor_results(results)
def find_rated_motor_power_in_pdf(path):
    results=find_rated_motor_powers_in_pdf(path); return results[0] if results else None
def build_stage1_motor_records(result):
    if not result.component_type or not result.quantity or not result.equipment_id: return []
    return expand_motor_group(equipment_id=result.equipment_id,equipment_type="AHU",component_type=result.component_type,group=result.quantity,power_kw=result.value_kw,source_page=result.page_number)
