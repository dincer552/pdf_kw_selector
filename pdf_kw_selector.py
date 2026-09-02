"""Context-aware keyword/value selector for engineering PDFs.

The selector deliberately does not choose a number by proximity alone. It scores
candidate values using their surrounding text and rejects values that belong to
known aggregate fields (for example, a unit total power) when the requested
attribute is a fan motor power.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable


POWER_RE = re.compile(
    r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>kw|kva|w)\b",
    re.IGNORECASE,
)


def normalize_equipment_id(value: str) -> str:
    """Normalize IDs such as AHU-1, AHU_01 and AHU 001 to AHU1."""
    value = value.upper().strip()
    value = re.sub(r"\s+", "", value)
    value = re.sub(r"[_\-]+", "", value)
    match = re.fullmatch(r"([A-Z]+)0*(\d+)", value)
    if match:
        return f"{match.group(1)}{int(match.group(2))}"
    return value


def normalize_power(value: float, unit: str) -> float:
    unit = unit.lower()
    if unit == "w":
        return value / 1000.0
    return value


@dataclass(frozen=True)
class Candidate:
    value_kw: float
    raw_value: str
    unit: str
    context: str
    score: int
    rejected: bool = False
    reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


POSITIVE_TERMS = {
    "motor": 8,
    "fan motor": 12,
    "fan": 5,
    "motor power": 10,
    "power": 2,
    "kw": 1,
    "blower": 5,
}

NEGATIVE_TERMS = {
    "unit total power": -18,
    "total power": -14,
    "total heating": -10,
    "total cooling": -10,
    "electrical total": -12,
    "sum": -8,
    "capacity total": -10,
}


def _score_context(context: str, target_terms: Iterable[str]) -> tuple[int, str]:
    lowered = context.lower()
    score = 0
    reasons: list[str] = []

    for term, weight in POSITIVE_TERMS.items():
        if term in lowered:
            score += weight
            reasons.append(f"+{weight}:{term}")

    for term, weight in NEGATIVE_TERMS.items():
        if term in lowered:
            score += weight
            reasons.append(f"{weight}:{term}")

    for term in target_terms:
        if term.lower() in lowered:
            score += 6
            reasons.append(f"+6:{term}")

    return score, ", ".join(reasons)


def extract_power_candidates(text: str, *, context_chars: int = 140) -> list[Candidate]:
    """Extract every power value while retaining local context and score."""
    candidates: list[Candidate] = []
    for match in POWER_RE.finditer(text):
        start = max(0, match.start() - context_chars)
        end = min(len(text), match.end() + context_chars)
        context = re.sub(r"\s+", " ", text[start:end]).strip()
        value = normalize_power(float(match.group("value").replace(",", ".")), match.group("unit"))
        score, reasons = _score_context(context, ("fan motor", "motor power", "fan"))
        rejected = any(term in context.lower() for term in ("unit total power", "total heating", "total cooling"))
        if rejected:
            reason = "aggregate field"
            score -= 25
        else:
            reason = reasons
        candidates.append(
            Candidate(
                value_kw=value,
                raw_value=match.group("value"),
                unit=match.group("unit"),
                context=context,
                score=score,
                rejected=rejected,
                reason=reason,
            )
        )
    return candidates


def select_fan_motor_power(text: str) -> Candidate | None:
    """Return the best non-aggregate fan motor power candidate."""
    candidates = [c for c in extract_power_candidates(text) if not c.rejected]
    if not candidates:
        return None
    return max(candidates, key=lambda c: c.score)


def extract_pdf_text(path: str | Path) -> str:
    """Extract text from a PDF using pypdf."""
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def select_fan_motor_power_from_pdf(path: str | Path) -> Candidate | None:
    return select_fan_motor_power(extract_pdf_text(path))


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Select fan motor power from a PDF")
    parser.add_argument("pdf", help="PDF file")
    args = parser.parse_args()
    result = select_fan_motor_power_from_pdf(args.pdf)
    print(json.dumps(result.to_dict() if result else None, ensure_ascii=False, indent=2))
