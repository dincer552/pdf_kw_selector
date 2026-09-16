"""Compare physical motor records from PDF 1 and PDF 2."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from typing import Iterable
from app_logger import debug, exception, info, warning
from motor_database import MotorRecord
from status import decide_motor_status, is_match_status

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
    pdf1_path: str | None = None
    pdf2_path: str | None = None
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

def compare_motor_records(pdf1_records: Iterable[MotorRecord], pdf2_records: Iterable[MotorRecord], tolerance_kw: float = 0.01) -> list[MotorComparison]:
    try:
        if tolerance_kw<0: raise ValueError("tolerance_kw must be >= 0")
        left,right=_index(pdf1_records),_index(pdf2_records)
        keys=sorted(set(left)|set(right),key=lambda key:(key[0],key[1],key[2])); output=[]
        info("Motor kW hesaplaması başladı",pdf1_motor_count=len(left),pdf2_motor_count=len(right),tolerance_kw=tolerance_kw)
        for key in keys:
            a,b=left.get(key),right.get(key); template=a or b
            decision=decide_motor_status(a,b,tolerance_kw=tolerance_kw)
            a_kw=a.power_kw if a else None; b_kw=b.power_kw if b else None; ebm=decision.status=="EBM_PAPST"
            label=template.component_label+(" [EBM]" if ebm else "")
            output.append(MotorComparison(template.equipment_id,template.component_type,label,template.component_index,a_kw,b_kw,decision.difference_kw,decision.status,a.source_page if a else None,b.source_page if b else None,a.source_group if a else None,b.source_group if b else None,decision.explanation,getattr(a,"source_path",None) if a else None,getattr(b,"source_path",None) if b else None))
            debug("Motor karşılaştırması",key=key,pdf1_kw=a_kw,pdf2_kw=b_kw,difference_kw=decision.difference_kw,status=decision.status,pdf1_brand=a.model_brand if a else None,explanation=decision.explanation)
        info("Motor kW hesaplaması bitti",comparison_count=len(output),match=sum(is_match_status(x.status) for x in output),mismatch=sum(x.status=="MISMATCH" for x in output),ebm_papst=sum(x.status=="EBM_PAPST" for x in output),only_pdf1=sum(x.status=="ONLY_IN_PDF1" for x in output),only_pdf2=sum(x.status=="ONLY_IN_PDF2" for x in output))
        return output
    except Exception as exc:
        exception("Motor kW karşılaştırma hesaplama hatası",exc,tolerance_kw=tolerance_kw); raise
