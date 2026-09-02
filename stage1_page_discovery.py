"""Stage 1: find and extract the explicit motor-rated power from PDF 1.

The selector is intentionally field-specific. It must prefer the value belonging
immediately to ``Anma gücü [kW]`` and must not confuse it with nearby shaft power,
VSD power, cooling capacity, or aggregate power values.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

from pdf_kw_selector import normalize_power


RATED_POWER_RE = re.compile(
    r"anma\s*g[üu]c[üu]\s*\[?\s*kW\s*\]?\s*[:\-]?\s*"
    r"(?P<value>\d+(?:[.,]\d+)?)"
    r"(?:\s*[x×]\s*\(?(?P<quantity>\d+(?:[.,]\d+)?(?:\s*[x×]\s*\d+(?:[.,]\d+)?)?)\)?\s*)?",
    re.IGNORECASE,
)

PAGE_POSITIVE_TERMS = {
    "anma gücü": 60,
    "motor data": 35,
    "fan data": 25,
    "plug fan": 20,
    "supply air": 10,
    "nominal rpm": 8,
    "model / miktar": 8,
    "fan motor power": 45,
}

PAGE_NEGATIVE_TERMS = {
    "cooling capacity": -25,
    "heating capacity": -25,
    "shaft power": -15,
    "vfd dahil": -12,
    "vfd hariç": -12,
    "unit total power": -20,
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

    def to_dict(self) -> dict:
        return asdict(self)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _page_score(text: str) -> tuple[int, tuple[str, ...]]:
    lowered = _clean(text).lower()
    score = 0
    matched: list[str] = []

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
    """Rank PDF pages for the explicit motor-rated-power target."""
    candidates: list[PageCandidate] = []
    for index, text in enumerate(page_texts, start=1):
        score, matched = _page_score(text)
        candidates.append(
            PageCandidate(
                page_number=index,
                score=score,
                text=_clean(text),
                matched_terms=matched,
            )
        )
    return sorted(candidates, key=lambda item: (-item.score, item.page_number))


def extract_rated_motor_power_from_page(text: str, page_number: int) -> MotorPowerResult | None:
    """Extract the value immediately belonging to ``Anma gücü [kW]``."""
    cleaned = _clean(text)
    match = RATED_POWER_RE.search(cleaned)
    if not match:
        return None

    value = normalize_power(
        float(match.group("value").replace(",", ".")),
        "kw",
    )
    quantity = match.group("quantity")

    start = max(0, match.start() - 70)
    end = min(len(cleaned), match.end() + 70)

    return MotorPowerResult(
        page_number=page_number,
        value_kw=value,
        raw_value=match.group("value"),
        quantity=quantity,
        field="fan_motor_power",
        confidence="high",
        source_text=cleaned[start:end],
    )


def find_rated_motor_power_in_pdf(path: str | Path) -> MotorPowerResult | None:
    """Stage-1 entry point: rank pages, then extract the explicit rated power."""
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]

    for candidate in discover_motor_power_page(pages):
        result = extract_rated_motor_power_from_page(candidate.text, candidate.page_number)
        if result is not None:
            return result
    return None


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Find rated motor power in PDF 1")
    parser.add_argument("pdf", help="PDF file")
    args = parser.parse_args()
    result = find_rated_motor_power_in_pdf(args.pdf)
    print(json.dumps(result.to_dict() if result else None, ensure_ascii=False, indent=2))
