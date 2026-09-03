"""Stage 2: discover motor rated power in the second/electrical PDF.

PDF 2 is commonly an electrical/control drawing. Motor power is therefore
preferentially read from dedicated Supply/Return/Exhaust Motor Connections
pages. The title-page Fan Motor Power summary is used as a quantity fallback.

Important rule for multi-fan projects:
- A dedicated motor-connection page represents the physical motor(s) wired on
  that page.
- If the summary says 2x1 and there are two dedicated connection pages for the
  same fan family, keep both pages as separate 1x1 physical motors. This is
  required for drawings such as Return Motor Connections-1 and -2.
- Activation Motor Connections are deliberately NOT treated as return/exhaust
  fans; activation fans are a separate fan family.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

from pypdf import PdfReader

from motor_database import MotorRecord, expand_motor_group
from pdf_kw_selector import normalize_equipment_id

MOTOR_CONNECTION_RE = re.compile(
    r"\b(?P<direction>supply|return|exhaust)\s+motor\s+connections?\b", re.I
)
KW_3PH_RE = re.compile(r"(?P<value>\d+(?:[.,]\d+)?)\s*kW\s*3\s*~", re.I)
KW_SLASH_RE = re.compile(r"(?P<value>\d+(?:[.,]\d+)?)\s*kW\s*/", re.I)
SUMMARY_PAIR_RE = re.compile(
    r"fan\s+motor\s+power\s*/?\s*nominal\s+rpm\s*"
    r"(?P<supply_value>\d+(?:[.,]\d+)?)\s*\[?\s*kW\s*\]?\s*"
    r"\(\s*(?P<supply_quantity>\d+\s*[x×]\s*\d+)\s*\)"
    r".*?"
    r"(?P<return_value>\d+(?:[.,]\d+)?)\s*\[?\s*kW\s*\]?\s*"
    r"\(\s*(?P<return_quantity>\d+\s*[x×]\s*\d+)\s*\)",
    re.I,
)
EQUIPMENT_RE = re.compile(
    r"\bAHU[_-][A-Z0-9]+[_-]\d+\b|\bAHU[-_ ]?\d+\b", re.I
)


@dataclass(frozen=True)
class PDF2MotorResult:
    equipment_id: str
    component_type: str
    component_role: str
    value_kw: float
    quantity: str
    source_page: int
    source_text: str
    confidence: str = "high"

    def to_dict(self) -> dict:
        return asdict(self)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _equipment_id(text: str) -> str | None:
    match = EQUIPMENT_RE.search(text)
    if not match:
        return None
    raw = match.group(0).replace("_", "-").upper()
    if re.fullmatch(r"AHU-\d+", raw):
        return normalize_equipment_id(raw)
    return raw


def _component(direction: str) -> tuple[str, str]:
    direction = direction.lower()
    if direction == "supply":
        return "Vantilatör", "supply_fan"
    if direction == "return":
        return "Aspiratör", "return_fan"
    return "Aspiratör", "exhaust_fan"


def _quantity(value: str | None) -> str:
    return re.sub(r"\s*[x×]\s*", "x", value or "1x1")


def _quantity_count(value: str | None) -> int:
    normalized = _quantity(value)
    match = re.fullmatch(r"(\d+)x(\d+)", normalized)
    if not match:
        return 1
    return int(match.group(1)) * int(match.group(2))


def _summary_quantities(page_texts: list[str]) -> dict[str, tuple[float, str]]:
    found: dict[str, tuple[float, str]] = {}
    for text in page_texts[:5]:
        match = SUMMARY_PAIR_RE.search(_clean(text))
        if not match:
            continue
        found["supply_fan"] = (
            float(match.group("supply_value").replace(",", ".")),
            _quantity(match.group("supply_quantity")),
        )
        found["return_fan"] = (
            float(match.group("return_value").replace(",", ".")),
            _quantity(match.group("return_quantity")),
        )
    return found


def _extract_connection_page(
    text: str, page_number: int, equipment_id: str | None
) -> PDF2MotorResult | None:
    cleaned = _clean(text)
    direction_match = MOTOR_CONNECTION_RE.search(cleaned)
    if not direction_match or not equipment_id:
        return None

    component_type, component_role = _component(direction_match.group("direction"))
    matches = list(KW_3PH_RE.finditer(cleaned))
    if not matches:
        matches = list(KW_SLASH_RE.finditer(cleaned))
    if not matches:
        return None

    match = matches[-1]
    value = float(match.group("value").replace(",", "."))
    return PDF2MotorResult(
        equipment_id=equipment_id,
        component_type=component_type,
        component_role=component_role,
        value_kw=value,
        quantity="1x1",
        source_page=page_number,
        source_text=cleaned[max(0, match.start() - 140): min(len(cleaned), match.end() + 140)],
    )


def _apply_summary_quantities(
    results: list[PDF2MotorResult], summary: dict[str, tuple[float, str]]
) -> list[PDF2MotorResult]:
    """Apply summary quantities without merging distinct connection pages.

    If a 2x1 summary has two dedicated pages for the same role/value, each
    page is one physical motor. If only one page exists, its quantity remains
    2x1 so expansion still creates both physical motors.
    """
    grouped: dict[tuple[str, float], list[PDF2MotorResult]] = {}
    for result in results:
        grouped.setdefault((result.component_role, result.value_kw), []).append(result)

    output: list[PDF2MotorResult] = []
    for result in results:
        summary_item = summary.get(result.component_role)
        quantity = result.quantity
        if summary_item:
            _, summary_quantity = summary_item
            expected = _quantity_count(summary_quantity)
            same_group_count = len(grouped[(result.component_role, result.value_kw)])
            if expected > 1 and same_group_count >= expected:
                quantity = "1x1"
            else:
                quantity = summary_quantity
        output.append(
            PDF2MotorResult(
                result.equipment_id,
                result.component_type,
                result.component_role,
                result.value_kw,
                quantity,
                result.source_page,
                result.source_text,
                result.confidence,
            )
        )
    return output


def _dedupe(results: list[PDF2MotorResult]) -> list[PDF2MotorResult]:
    """Remove repeated extraction of the same page, but keep separate pages."""
    unique: list[PDF2MotorResult] = []
    seen: set[tuple[str, str, float, int]] = set()
    for result in results:
        key = (
            result.equipment_id.upper(),
            result.component_role,
            result.value_kw,
            result.source_page,
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(result)
    return unique


def find_pdf2_motor_powers(path: str | Path) -> list[PDF2MotorResult]:
    """Extract fan motor rated powers from PDF 2."""
    pages = [page.extract_text() or "" for page in PdfReader(str(path)).pages]
    equipment_id = next((_equipment_id(text) for text in pages if _equipment_id(text)), None)
    summary = _summary_quantities(pages)

    results: list[PDF2MotorResult] = []
    for page_number, text in enumerate(pages, 1):
        result = _extract_connection_page(text, page_number, equipment_id)
        if not result:
            continue
        results.append(result)

    results = _dedupe(results)
    results = _apply_summary_quantities(results, summary)

    if not results and summary and equipment_id:
        for role, (value, quantity) in summary.items():
            component_type = "Vantilatör" if role == "supply_fan" else "Aspiratör"
            results.append(
                PDF2MotorResult(
                    equipment_id,
                    component_type,
                    role,
                    value,
                    quantity,
                    1,
                    "Fan Motor Power / Nominal Rpm",
                )
            )
    return results


def build_pdf2_motor_records(result: PDF2MotorResult) -> list[MotorRecord]:
    """Expand PDF 2 motor groups to the same physical-motor shape as PDF 1."""
    return expand_motor_group(
        equipment_id=result.equipment_id,
        equipment_type="AHU",
        component_type=result.component_type,
        group=result.quantity,
        power_kw=result.value_kw,
        source_page=result.source_page,
    )
