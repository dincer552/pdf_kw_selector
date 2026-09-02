"""Stage 1: discover rated motor-power pages and fan direction.

Project rules:
- Supply air -> Vantilatör (Vant)
- Return air / Exhaust air -> Aspiratör (Asp)
- 1x1 -> one physical motor; 2x1 -> two; 3x1 -> three.

The selector targets the explicit ``Rated Power [kW]`` / ``Anma gücü [kW]``
field rather than arbitrary nearby kW values.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

from motor_database import expand_motor_group
from pdf_kw_selector import normalize_power

RATED_POWER_RE = re.compile(
    r"(?:anma\s*g[üu]c[üu]|rated\s*power)\s*\[?\s*kW\s*\]?\s*[:=\-]?\s*"
    r"(?P<value>\d+(?:[.,]\d+)?)"
    r"(?:\s*[x×]\s*\(?\s*(?P<quantity>\d+(?:[.,]\d+)?(?:\s*[x×]\s*\d+)?)\s*\)?)?",
    re.IGNORECASE,
)

PAGE_POSITIVE_TERMS = {
    "anma gücü": 60, "rated power": 60, "motor data": 35, "fan data": 25,
    "plug fan": 20, "supply air": 15, "return air": 15, "exhaust air": 15,
    "nominal rpm": 8, "model / miktar": 8, "fan motor power": 45,
}
PAGE_NEGATIVE_TERMS = {
    "cooling capacity": -25, "heating capacity": -25, "shaft power": -15,
    "vfd dahil": -12, "vfd hariç": -12, "unit total power": -20,
    "tot. abs. power": -15,
}


@dataclass(frozen=True)
class PageCandidate:
    page_number: int
    score: int
    text: str
    matched_terms: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class MotorPowerResult:
    page_number: int
    value_kw: float
    raw_value: str
    quantity: str | None
    field: str
    confidence: str
    source_text: str
    component_type: str | None = None
    component_role: str | None = None
    equipment_id: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _page_score(text: str) -> tuple[int, tuple[str, ...]]:
    lowered = _clean(text).lower()
    score, matched = 0, []
    for term, weight in PAGE_POSITIVE_TERMS.items():
        if term in lowered:
            score += weight
            matched.append(f"+{term}")
    for term, weight in PAGE_NEGATIVE_TERMS.items():
        if term in lowered:
            score += weight
            matched.append(f"{weight}:{term}")
    if RATED_POWER_RE.search(lowered):
        score += 80
        matched.append("+explicit rated power")
    return score, tuple(matched)


def discover_motor_power_page(page_texts: list[str]) -> list[PageCandidate]:
    candidates = []
    for index, text in enumerate(page_texts, start=1):
        score, matched = _page_score(text)
        candidates.append(PageCandidate(index, score, _clean(text), matched))
    return sorted(candidates, key=lambda item: (-item.score, item.page_number))


def _normalize_quantity(quantity: str | None) -> str | None:
    if not quantity:
        return None
    return re.sub(r"\s*[x×]\s*", "x", quantity.strip())


def detect_component_type(text: str) -> tuple[str | None, str | None]:
    """Map airflow direction to the project's component terminology.

    Project rules:
      Supply air -> Vantilatör
      Return air -> Aspiratör
      Exhaust air -> Aspiratör

    ``exhaust_fan`` is used for the explicit Exhaust air source label, while
    ``return_fan`` is retained for Return air so existing downstream logic is
    backward-compatible.
    """
    lowered = _clean(text).lower()
    supply = bool(re.search(r"\bsupply\s+air\b", lowered))
    return_air = bool(re.search(r"\breturn\s+air\b", lowered))
    exhaust_air = bool(re.search(r"\bexhaust\s+air\b", lowered))

    if supply and not (return_air or exhaust_air):
        return "Vantilatör", "supply_fan"
    if exhaust_air and not supply:
        return "Aspiratör", "exhaust_fan"
    if return_air and not supply:
        return "Aspiratör", "return_fan"
    return None, None


def extract_equipment_id(text: str) -> str | None:
    match = re.search(r"\bAHU\s*[-_ ]?\s*0*(\d+)\b", text, re.IGNORECASE)
    return f"AHU{int(match.group(1))}" if match else None


def extract_rated_motor_power_from_page(text: str, page_number: int) -> MotorPowerResult | None:
    cleaned = _clean(text)
    match = RATED_POWER_RE.search(cleaned)
    if not match:
        return None
    raw_value = match.group("value")
    value = normalize_power(float(raw_value.replace(",", ".")), "kw")
    quantity = _normalize_quantity(match.group("quantity"))
    component_type, component_role = detect_component_type(cleaned)
    start = max(0, match.start() - 120)
    end = min(len(cleaned), match.end() + 120)
    return MotorPowerResult(
        page_number=page_number,
        value_kw=value,
        raw_value=raw_value,
        quantity=quantity,
        field="fan_motor_power",
        confidence="high",
        source_text=cleaned[start:end],
        component_type=component_type,
        component_role=component_role,
        equipment_id=extract_equipment_id(cleaned),
    )


def find_rated_motor_powers_in_pdf(path: str | Path) -> list[MotorPowerResult]:
    """Find all distinct rated-power fan sections in PDF 1."""
    from pypdf import PdfReader

    pages = [page.extract_text() or "" for page in PdfReader(str(path)).pages]
    results: list[MotorPowerResult] = []
    seen: set[tuple[int, str | None, float, str | None]] = set()

    for candidate in discover_motor_power_page(pages):
        result = extract_rated_motor_power_from_page(candidate.text, candidate.page_number)
        if result is None or result.component_role is None:
            continue
        key = (result.page_number, result.component_role, result.value_kw, result.quantity)
        if key in seen:
            continue
        seen.add(key)
        results.append(result)

    return sorted(results, key=lambda item: item.page_number)


def find_rated_motor_power_in_pdf(path: str | Path) -> MotorPowerResult | None:
    results = find_rated_motor_powers_in_pdf(path)
    return results[0] if results else None


def build_stage1_motor_records(result: MotorPowerResult):
    """Create one database record per physical motor in the selected group."""
    if not result.component_type or not result.quantity or not result.equipment_id:
        return []
    return expand_motor_group(
        equipment_id=result.equipment_id,
        equipment_type="AHU",
        component_type=result.component_type,
        group=result.quantity,
        power_kw=result.value_kw,
        source_page=result.page_number,
    )


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Find rated motor power in PDF 1")
    parser.add_argument("pdf", help="PDF file")
    args = parser.parse_args()
    results = find_rated_motor_powers_in_pdf(args.pdf)
    output = []
    for result in results:
        item = result.to_dict()
        item["motors"] = [r.to_dict() for r in build_stage1_motor_records(result)]
        output.append(item)
    print(json.dumps(output, ensure_ascii=False, indent=2))
