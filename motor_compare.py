"""Compare physical motor records from PDF 1 and PDF 2."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from typing import Iterable
from app_logger import debug, exception, info, warning
from motor_database import MotorRecord

@dataclass(frozen=True)
class MotorComparison:
    equipment_id: str
    component_type: str
    component_label: str
    component_index: int
    pdf1_kw: float | None
    pdf2_kw: float | None
    difference_kw: float | None
    status: str
    pdf1_page: int | None = None
    pdf2_page: int | None = None
    pdf1_group: str | None = None
    pdf2_group: str | None = None
    explanation: str | None = None
    def to_dict(self) -> dict: return asdict(self)

def _canonical_key(record: MotorRecord) -> tuple[str, str, int]:
    return record.equipment_id.upper().replace("_", "-"), record.component_type.strip().lower(), record.component_index

def _index(records: Iterable[MotorRecord]) -> dict[tuple[str, str, int], MotorRecord]:
    result={}
    for record in records:
        key=_canonical_key(record)
        if key in result: warning("Aynı fiziksel motor anahtarı tekrar geldi; ilk kayıt korunuyor",key=key,existing=str(result[key]),duplicate=str(record))
        result.setdefault(key,record)
    return result

def _is_ebm_papst(record: MotorRecord | None) -> bool:
    if record is None:return False
    brand=(record.model_brand or "").casefold().replace(" ", "")
    return "ebm-papst" in brand or "ebmpapst" in brand

def _is_legacy_1_1_equivalent(pdf1_kw: float | None, pdf2_kw: float | None) -> bool:
    return pdf1_kw is not None and pdf2_kw is not None and abs(pdf1_kw-1.1)<=0.001 and abs(pdf2_kw-1.5)<=0.001

def compare_motor_records(pdf1_records: Iterable[MotorRecord], pdf2_records: Iterable[MotorRecord], tolerance_kw: float = 0.01) -> list[MotorComparison]:
    try:
        if tolerance_kw<0: raise ValueError("tolerance_kw must be >= 0")
        left,right=_index(pdf1_records),_index(pdf2_records)
        keys=sorted(set(left)|set(right),key=lambda key:(key[0],key[1],key[2])); output=[]
        info("Motor kW hesaplaması başladı",pdf1_motor_count=len(left),pdf2_motor_count=len(right),tolerance_kw=tolerance_kw)
        for key in keys:
            a,b=left.get(key),right.get(key); template=a or b; a_kw=a.power_kw if a else None; b_kw=b.power_kw if b else None; ebm=_is_ebm_papst(a)
            if a is None: status,difference,explanation="ONLY_IN_PDF2",None,"PDF1 tarafında karşılığı bulunamadı."
            elif b is None: status,difference,explanation="ONLY_IN_PDF1",None,"PDF2 tarafında karşılığı bulunamadı."
            elif ebm: status,difference,explanation="EBM_PAPST",None,"PDF1 Model Brand = EBM-Papst; normal kW karşılaştırması yapılmadı. PDF2 motoru eşleştirildi."
            else:
                difference=abs((a_kw or 0.0)-(b_kw or 0.0))
                if _is_legacy_1_1_equivalent(a_kw,b_kw):
                    status="MATCH"; explanation="Özel eşdeğerlik: PDF1 1.1 kW, PDF2 1.5 kW kabul edildi. Bu istisna yalnızca 1.1→1.5 için geçerlidir."
                else:
                    status="MATCH" if difference<=tolerance_kw else "MISMATCH"; explanation="Normal kW karşılaştırması yapıldı."
            label=template.component_label+(" [EBM]" if ebm else "")
            output.append(MotorComparison(template.equipment_id,template.component_type,label,template.component_index,a_kw,b_kw,difference,status,a.source_page if a else None,b.source_page if b else None,a.source_group if a else None,b.source_group if b else None,explanation))
            debug("Motor karşılaştırması",key=key,pdf1_kw=a_kw,pdf2_kw=b_kw,difference_kw=difference,status=status,pdf1_brand=a.model_brand if a else None,explanation=explanation)
        info("Motor kW hesaplaması bitti",comparison_count=len(output),match=sum(x.status=="MATCH" for x in output),mismatch=sum(x.status=="MISMATCH" for x in output),ebm_papst=sum(x.status=="EBM_PAPST" for x in output),only_pdf1=sum(x.status=="ONLY_IN_PDF1" for x in output),only_pdf2=sum(x.status=="ONLY_IN_PDF2" for x in output))
        return output
    except Exception as exc:
        exception("Motor kW karşılaştırma hesaplama hatası",exc,tolerance_kw=tolerance_kw); raise
