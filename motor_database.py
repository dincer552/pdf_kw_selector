"""Local motor database and equipment list builder for PDF 1.

The database stores each physical motor as an individual record.  A notation
such as ``2x1`` means two motors in the group, so the parser expands it to
Motor 1 and Motor 2.  The first number is the motor count; the second is kept
as the source grouping quantity and is not treated as an additional motor
count.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass


GROUP_RE = re.compile(
    r"(?P<count>\d+)\s*[x×]\s*(?P<groups>\d+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class MotorRecord:
    equipment_id: str
    equipment_type: str
    component_type: str
    component_index: int
    component_label: str
    power_kw: float | None
    source_group: str
    motor_count: int
    source_page: int | None = None
    confidence: str = "high"

    def to_dict(self) -> dict:
        return asdict(self)


def parse_motor_group(value: str) -> tuple[int, int] | None:
    """Return (motor_count, group_count) from strings such as 1x1 or 2×1."""
    match = GROUP_RE.search(value.replace(" ", ""))
    if not match:
        return None
    return int(match.group("count")), int(match.group("groups"))


def expand_motor_group(
    *,
    equipment_id: str,
    equipment_type: str,
    component_type: str,
    group: str,
    power_kw: float | None,
    source_page: int | None = None,
) -> list[MotorRecord]:
    """Expand a motor group into one record per physical motor.

    Examples:
      1x1 -> one motor
      2x1 -> two motors
      3x1 -> three motors
    """
    parsed = parse_motor_group(group)
    if parsed is None:
        raise ValueError(f"Invalid motor group: {group!r}")

    motor_count, group_count = parsed
    records: list[MotorRecord] = []
    normalized_component = component_type.strip().lower()
    label_prefix = "Vant" if normalized_component in {"vantilatör", "vant", "supply fan", "fan"} else "Asp" if normalized_component in {"aspiratör", "asp", "extractor", "exhaust fan"} else component_type.strip()

    for index in range(1, motor_count + 1):
        records.append(
            MotorRecord(
                equipment_id=equipment_id,
                equipment_type=equipment_type,
                component_type=component_type,
                component_index=index,
                component_label=f"{label_prefix} {index}",
                power_kw=power_kw,
                source_group=group,
                motor_count=motor_count,
                source_page=source_page,
            )
        )
    return records


def build_comparison_key(record: MotorRecord) -> tuple[str, str, int]:
    """Stable key used later by the PDF-1/PDF-2 comparison stage."""
    return (
        record.equipment_id.upper(),
        record.component_type.strip().lower(),
        record.component_index,
    )
