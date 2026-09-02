"""Compare engineering PDF power data using semantic field context."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from pdf_kw_selector import extract_pdf_text, normalize_equipment_id


FIELD_ALIASES = {
    "fan_motor_power": (
        "fan motor power",
        "supply fan motor power",
        "fan motor",
        "motor power",
        "motor rating",
        "motor gucu",
        "motor guc",
        "anma gucu",
        "rated power",
    ),
    "unit_total_power": (
        "unit total power",
        "total power",
        "unit power",
    ),
}

POWER_RE = re.compile(r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>kw|kva|w)\b", re.I)
EQUIPMENT_RE = re.compile(r"\b([A-Z]{2,8})[\s_-]*0*(\d{1,4})\b", re.I)


def _normalize_text(value: str) -> str:
    """Normalize accents so Turkish labels match ASCII aliases reliably."""
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(ch)
    ).lower()


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
    return value / 1000 if unit.lower() == "w" else value


def _field_for_line(line: str) -> str | None:
    normalized = _normalize_text(line)
    # Specific fields must win over generic "power" labels.
    for field, aliases in FIELD_ALIASES.items():
        if any(_normalize_text(alias) in normalized for alias in aliases):
            return field
    return None


def _equipment_for_line(line: str, fallback: str | None) -> str | None:
    match = EQUIPMENT_RE.search(line)
    if match:
        return normalize_equipment_id(match.group(0))
    return fallback


def extract_power_records(text: str) -> list[PowerRecord]:
    """Extract power values line-by-line so unrelated nearby kW values do not merge."""
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

        for match in POWER_RE.finditer(line):
            value = _to_kw(float(match.group("value").replace(",", ".")), match.group("unit"))
            records.append(
                PowerRecord(
                    equipment=_equipment_for_line(line, current_equipment),
                    field=field,
                    value_kw=value,
                    raw_value=match.group(0),
                    source_line=line,
                )
            )
    return records


def extract_power_records_from_pdf(path: str | Path) -> list[PowerRecord]:
    return extract_power_records(extract_pdf_text(path))


def _index(records: Iterable[PowerRecord]) -> dict[tuple[str | None, str], PowerRecord]:
    result: dict[tuple[str | None, str], PowerRecord] = {}
    for record in records:
        key = (record.equipment, record.field)
        result.setdefault(key, record)
    return result


def compare_records(records_a: Iterable[PowerRecord], records_b: Iterable[PowerRecord], tolerance_kw: float = 0.01) -> list[Comparison]:
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
            status = "ONLY_IN_PDF_B"
            diff = None
        elif right is None:
            status = "ONLY_IN_PDF_A"
            diff = None
        else:
            diff = abs(lv - rv)
            status = "MATCH" if diff <= tolerance_kw else "MISMATCH"

        output.append(
            Comparison(
                equipment=equipment or "UNKNOWN",
                field=field,
                pdf_a_kw=lv,
                pdf_b_kw=rv,
                difference_kw=diff,
                status=status,
                source_a=left.source_line if left else None,
                source_b=right.source_line if right else None,
            )
        )
    return output


def compare_pdfs(path_a: str | Path, path_b: str | Path, tolerance_kw: float = 0.01) -> list[Comparison]:
    return compare_records(
        extract_power_records_from_pdf(path_a),
        extract_power_records_from_pdf(path_b),
        tolerance_kw=tolerance_kw,
    )
