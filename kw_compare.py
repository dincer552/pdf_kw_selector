"""Compare engineering PDF power data using semantic field context."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from app_logger import debug, exception, info, warning
from pdf_kw_selector import extract_pdf_text, normalize_equipment_id


FIELD_ALIASES = {
    "fan_motor_power": (
        "fan motor power", "supply fan motor power", "fan motor", "motor power",
        "motor rating", "motor gucu", "motor guc", "anma gucu", "rated power",
    ),
    "unit_total_power": ("unit total power", "total power", "unit power"),
}

POWER_RE = re.compile(r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>kw|kva|w)\b", re.I)
EQUIPMENT_RE = re.compile(r"\b([A-Z]{2,8})[\s_-]*0*(\d{1,4})\b", re.I)
FAN_MOTOR_FIELD_RE = re.compile(
    r"\b(?:supply\s+)?fan\s+motor\s+power\b|\bfan\s+motor\b|\b(?:motor\s+power|motor\s+rating|motor\s+gucu|motor\s+guc|anma\s+gucu|rated\s+power)\b",
    re.I,
)


def _normalize_text(value: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", value) if not unicodedata.combining(ch)).lower()


@dataclass(frozen=True)
class PowerRecord:
    equipment: str | None
    field: str
    value_kw: float
    raw_value: str
    source_line: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Comparison:
    equipment: str
    field: str
    pdf_a_kw: float | None
    pdf_b_kw: float | None
    difference_kw: float | None
    status: str
    source_a: str | None = None
    source_b: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _to_kw(value: float, unit: str) -> float:
    try:
        result = value / 1000 if unit.lower() == "w" else value
        debug("Legacy güç birimi dönüştürüldü", value=value, unit=unit, value_kw=result)
        return result
    except Exception as exc:
        exception("Legacy güç birimi dönüşüm hatası", exc, value=value, unit=unit)
        raise


def _field_for_line(line: str) -> str | None:
    normalized = _normalize_text(line)
    if FAN_MOTOR_FIELD_RE.search(normalized):
        return "fan_motor_power"
    for field, aliases in FIELD_ALIASES.items():
        if any(_normalize_text(alias) in normalized for alias in aliases):
            return field
    return None


def _equipment_for_line(line: str, fallback: str | None) -> str | None:
    try:
        field = _field_for_line(line)
        field_match = None
        if field:
            normalized = _normalize_text(line)
            aliases = FIELD_ALIASES[field]
            positions = [normalized.find(_normalize_text(alias)) for alias in aliases]
            positions = [p for p in positions if p >= 0]
            if positions:
                field_match = min(positions)

        for match in EQUIPMENT_RE.finditer(line):
            if field_match is not None and match.start() >= field_match:
                continue
            return normalize_equipment_id(match.group(0))
        return fallback
    except Exception as exc:
        exception("Equipment ID hesaplama hatası", exc, line=line, fallback=fallback)
        raise


def extract_power_records(text: str) -> list[PowerRecord]:
    """Extract power values line-by-line so unrelated nearby kW values do not merge."""
    try:
        records: list[PowerRecord] = []
        current_equipment: str | None = None
        for raw_line in text.splitlines():
            line = re.sub(r"\s+", " ", raw_line).strip()
            if not line:
                continue
            found_equipment = _equipment_for_line(line, None)
            if found_equipment:
                current_equipment = found_equipment
            field = _field_for_line(line)
            if not field:
                continue
            matches = list(POWER_RE.finditer(line))
            if not matches:
                warning("Semantik güç alanı bulundu fakat kW değeri bulunamadı", field=field, line=line)
            for match in matches:
                value = _to_kw(float(match.group("value").replace(",", ".")), match.group("unit"))
                records.append(PowerRecord(
                    equipment=_equipment_for_line(line, current_equipment),
                    field=field,
                    value_kw=value,
                    raw_value=match.group(0),
                    source_line=line,
                ))
        info("Legacy güç kayıtları çıkarıldı", record_count=len(records))
        return records
    except Exception as exc:
        exception("Legacy güç kayıtları çıkarma hesaplama hatası", exc, text_preview=(text or "")[:1000])
        raise


def extract_power_records_from_pdf(path: str | Path) -> list[PowerRecord]:
    try:
        return extract_power_records(extract_pdf_text(path))
    except Exception as exc:
        exception("Legacy PDF güç kayıtları çıkarılamadı", exc, path=str(path))
        raise


def _index(records: Iterable[PowerRecord]) -> dict[tuple[str | None, str], PowerRecord]:
    result: dict[tuple[str | None, str], PowerRecord] = {}
    for record in records:
        key = (record.equipment, record.field)
        if key in result:
            warning("Legacy karşılaştırmada duplicate kayıt; ilk kayıt korunuyor", key=key)
        result.setdefault(key, record)
    return result


def compare_records(records_a: Iterable[PowerRecord], records_b: Iterable[PowerRecord], tolerance_kw: float = 0.01) -> list[Comparison]:
    try:
        if tolerance_kw < 0:
            raise ValueError("tolerance_kw must be >= 0")
        a = _index(records_a)
        b = _index(records_b)
        keys = sorted(set(a) | set(b), key=lambda x: (x[0] or "", x[1]))
        output: list[Comparison] = []
        for equipment, field in keys:
            left = a.get((equipment, field))
            right = b.get((equipment, field))
            lv = left.value_kw if left else None
            rv = right.value_kw if right else None
            if left is None:
                status, diff = "ONLY_IN_PDF_B", None
            elif right is None:
                status, diff = "ONLY_IN_PDF_A", None
            else:
                diff = abs(lv - rv)
                status = "MATCH" if diff <= tolerance_kw else "MISMATCH"
            output.append(Comparison(equipment=equipment or "UNKNOWN", field=field, pdf_a_kw=lv, pdf_b_kw=rv, difference_kw=diff, status=status, source_a=left.source_line if left else None, source_b=right.source_line if right else None))
            debug("Legacy kW karşılaştırması", equipment=equipment, field=field, pdf_a_kw=lv, pdf_b_kw=rv, difference_kw=diff, status=status)
        info("Legacy kW karşılaştırması tamamlandı", comparison_count=len(output))
        return output
    except Exception as exc:
        exception("Legacy kW karşılaştırma hesaplama hatası", exc, tolerance_kw=tolerance_kw)
        raise


def compare_pdfs(path_a: str | Path, path_b: str | Path, tolerance_kw: float = 0.01) -> list[Comparison]:
    try:
        info("Legacy PDF karşılaştırması başladı", pdf_a=str(path_a), pdf_b=str(path_b), tolerance_kw=tolerance_kw)
        return compare_records(extract_power_records_from_pdf(path_a), extract_power_records_from_pdf(path_b), tolerance_kw=tolerance_kw)
    except Exception as exc:
        exception("Legacy PDF karşılaştırması başarısız", exc, pdf_a=str(path_a), pdf_b=str(path_b))
        raise
