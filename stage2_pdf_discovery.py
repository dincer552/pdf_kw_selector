"""Stage 2: discover motor rated power in the second/electrical PDF.

Dedicated connection pages are authoritative when they contain a motor kW.
When no dedicated connection page is present, the title-page fan motor power
summary is used as a controlled fallback. Supply, Return and Activation are
kept as separate fan families.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

from pypdf import PdfReader

from motor_database import MotorRecord, expand_motor_group
from pdf_kw_selector import normalize_equipment_id

MOTOR_CONNECTION_RE = re.compile(
    r"\b(?P<direction>supply|return|exhaust|activation)\s+motor\s+connections?\b", re.I
)
KW_3PH_RE = re.compile(r"(?P<value>\d+(?:[.,]\d+)?)\s*kW\s*3\s*~", re.I)
KW_SLASH_RE = re.compile(r"(?P<value>\d+(?:[.,]\d+)?)\s*kW\s*/", re.I)
SUMMARY_GROUPED_KW_RE = re.compile(
    r"(?P<value>\d+(?:[.,]\d+)?)\s*\[?\s*kW\s*\]?\s*\(\s*"
    r"(?P<quantity>\d+\s*[x×]\s*\d+)\s*\)", re.I
)
SUMMARY_FAN_MOTOR_RE = re.compile(
    r"fan\s+motor\s+power\s*/?\s*nominal\s+rpm\s*"
    r"(?P<value>\d+(?:[.,]\d+)?)\s*\[?\s*kW\s*\]?\s*"
    r"\(\s*(?P<quantity>\d+\s*[x×]\s*\d+)\s*\)", re.I
)
SUMMARY_PAIR_RE = re.compile(
    r"fan\s+motor\s+power\s*/?\s*nominal\s+rpm\s*"
    r"(?P<supply_value>\d+(?:[.,]\d+)?)\s*\[?\s*kW\s*\]?\s*"
    r"\(\s*(?P<supply_quantity>\d+\s*[x×]\s*\d+)\s*\)"
    r".*?"
    r"(?P<return_value>\d+(?:[.,]\d+)?)\s*\[?\s*kW\s*\]?\s*"
    r"\(\s*(?P<return_quantity>\d+\s*[x×]\s*\d+)\s*\)", re.I
)
EQUIPMENT_RE = re.compile(
    r"\bVE\.A\.D\.\d+\b|\bAHU[_-][A-Z0-9]+[_-]\d+(?:[_-][A-Z0-9]+)?\b|\bAHU[-_ ]?\d+\b", re.I
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
    if direction in {"return", "exhaust"}:
        return "Aspiratör", "return_fan" if direction == "return" else "exhaust_fan"
    return "Reaktivasyon", "activation_fan"


def _quantity(value: str | None) -> str:
    return re.sub(r"\s*[x×]\s*", "x", value or "1x1")


def _quantity_count(value: str | None) -> int:
    match = re.fullmatch(r"(\d+)x(\d+)", _quantity(value))
    return int(match.group(1)) * int(match.group(2)) if match else 1


def _summary_quantities(page_texts: list[str]) -> dict[str, tuple[float, str]]:
    found: dict[str, tuple[float, str]] = {}
    for text in page_texts[:5]:
        cleaned = _clean(text)
        grouped = list(SUMMARY_GROUPED_KW_RE.finditer(cleaned))
        if re.search(r"activation\s+fan\s+motor\s+power", cleaned, re.I) and len(grouped) >= 3:
            for match, role in (
                (grouped[0], "supply_fan"),
                (grouped[1], "activation_fan"),
                (grouped[-1], "return_fan"),
            ):
                found[role] = (float(match.group("value").replace(",", ".")), _quantity(match.group("quantity")))
            continue
        pair = SUMMARY_PAIR_RE.search(cleaned)
        if pair:
            found["supply_fan"] = (float(pair.group("supply_value").replace(",", ".")), _quantity(pair.group("supply_quantity")))
            found["return_fan"] = (float(pair.group("return_value").replace(",", ".")), _quantity(pair.group("return_quantity")))
            continue
        single = SUMMARY_FAN_MOTOR_RE.search(cleaned)
        if single:
            found.setdefault("supply_fan", (float(single.group("value").replace(",", ".")), _quantity(single.group("quantity"))))
    return found


def _extract_connection_page(text: str, page_number: int, equipment_id: str | None) -> PDF2MotorResult | None:
    cleaned = _clean(text)
    direction_match = MOTOR_CONNECTION_RE.search(cleaned)
    if not direction_match or not equipment_id:
        return None
    component_type, component_role = _component(direction_match.group("direction"))
    matches = list(KW_3PH_RE.finditer(cleaned)) or list(KW_SLASH_RE.finditer(cleaned))
    if not matches:
        return None
    match = matches[-1]
    value = float(match.group("value").replace(",", "."))
    return PDF2MotorResult(
        equipment_id, component_type, component_role, value, "1x1", page_number,
        cleaned[max(0, match.start() - 140): min(len(cleaned), match.end() + 140)],
    )


def _fallback_connection_page(text: str, page_number: int, equipment_id: str | None, summary: dict[str, tuple[float, str]]) -> PDF2MotorResult | None:
    cleaned = _clean(text)
    direction_match = MOTOR_CONNECTION_RE.search(cleaned)
    if not direction_match or not equipment_id:
        return None
    _, role = _component(direction_match.group("direction"))
    item = summary.get(role)
    if not item:
        return None
    value, quantity = item
    return PDF2MotorResult(
        equipment_id, _component(direction_match.group("direction"))[0], role,
        value, quantity, page_number, "summary fallback: Fan Motor Power",
    )


def _apply_summary_quantities(results: list[PDF2MotorResult], summary: dict[str, tuple[float, str]]) -> list[PDF2MotorResult]:
    grouped: dict[tuple[str, float], list[PDF2MotorResult]] = {}
    for result in results:
        grouped.setdefault((result.component_role, result.value_kw), []).append(result)
    output = []
    for result in results:
        quantity = result.quantity
        summary_item = summary.get(result.component_role)
        if summary_item:
            _, summary_quantity = summary_item
            expected = _quantity_count(summary_quantity)
            same_group_count = len(grouped[(result.component_role, result.value_kw)])
            if expected > 1 and same_group_count >= expected:
                quantity = "1x1"
            elif result.quantity == "1x1" and same_group_count == 1:
                quantity = summary_quantity
        output.append(PDF2MotorResult(
            result.equipment_id, result.component_type, result.component_role,
            result.value_kw, quantity, result.source_page, result.source_text, result.confidence,
        ))
    return output


def _dedupe(results: list[PDF2MotorResult]) -> list[PDF2MotorResult]:
    unique = []
    seen: set[tuple[str, str, float, int]] = set()
    for result in results:
        key = (result.equipment_id.upper(), result.component_role, result.value_kw, result.source_page)
        if key in seen:
            continue
        seen.add(key)
        unique.append(result)
    return unique


def find_pdf2_motor_powers(path: str | Path) -> list[PDF2MotorResult]:
    pages = [page.extract_text() or "" for page in PdfReader(str(path)).pages]
    equipment_id = next((_equipment_id(text) for text in pages if _equipment_id(text)), None)
    summary = _summary_quantities(pages)
    results: list[PDF2MotorResult] = []
    for page_number, text in enumerate(pages, 1):
        result = _extract_connection_page(text, page_number, equipment_id)
        if not result:
            result = _fallback_connection_page(text, page_number, equipment_id, summary)
        if result:
            results.append(result)
    return _apply_summary_quantities(_dedupe(results), summary)


def build_pdf2_motor_records(result: PDF2MotorResult, start_index: int = 1) -> list[MotorRecord]:
    return expand_motor_group(
        equipment_id=result.equipment_id,
        equipment_type="AHU",
        component_type=result.component_type,
        group=result.quantity,
        power_kw=result.value_kw,
        source_page=result.source_page,
        start_index=start_index,
    )
