"""Compare physical motor records from PDF 1 and PDF 2."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from motor_database import MotorRecord, build_comparison_key


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

    def to_dict(self) -> dict:
        return asdict(self)


def _canonical_key(record: MotorRecord) -> tuple[str, str, int]:
    equipment = record.equipment_id.upper().replace("_", "-")
    return equipment, record.component_type.strip().lower(), record.component_index


def _index(records: Iterable[MotorRecord]) -> dict[tuple[str, str, int], MotorRecord]:
    result: dict[tuple[str, str, int], MotorRecord] = {}
    for record in records:
        result.setdefault(_canonical_key(record), record)
    return result


def compare_motor_records(
    pdf1_records: Iterable[MotorRecord],
    pdf2_records: Iterable[MotorRecord],
    tolerance_kw: float = 0.01,
) -> list[MotorComparison]:
    """Compare one physical motor at a time using equipment/type/index as key."""
    left = _index(pdf1_records)
    right = _index(pdf2_records)
    keys = sorted(set(left) | set(right), key=lambda key: (key[0], key[1], key[2]))
    output: list[MotorComparison] = []

    for key in keys:
        a = left.get(key)
        b = right.get(key)
        template = a or b
        a_kw = a.power_kw if a else None
        b_kw = b.power_kw if b else None

        if a is None:
            status = "ONLY_IN_PDF2"
            difference = None
        elif b is None:
            status = "ONLY_IN_PDF1"
            difference = None
        else:
            difference = abs((a_kw or 0.0) - (b_kw or 0.0))
            status = "MATCH" if difference <= tolerance_kw else "MISMATCH"

        output.append(
            MotorComparison(
                equipment_id=template.equipment_id,
                component_type=template.component_type,
                component_label=template.component_label,
                component_index=template.component_index,
                pdf1_kw=a_kw,
                pdf2_kw=b_kw,
                difference_kw=difference,
                status=status,
                pdf1_page=a.source_page if a else None,
                pdf2_page=b.source_page if b else None,
                pdf1_group=a.source_group if a else None,
                pdf2_group=b.source_group if b else None,
            )
        )

    return output
