"""Context-aware keyword/value selector for engineering PDFs."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

from app_logger import debug, exception, warning


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


def _normalize_text(value: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(ch)
    ).lower()


def normalize_power(value: float, unit: str) -> float:
    try:
        unit = unit.lower()
        if unit == "w":
            return value / 1000.0
        return value
    except Exception as exc:
        exception("Güç birimi normalizasyonu hesaplama hatası", exc, value=value, unit=unit)
        raise


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
    "fan motor power": 14,
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
    lowered = _normalize_text(context)
    score = 0
    reasons: list[str] = []

    for term, weight in POSITIVE_TERMS.items():
        if _normalize_text(term) in lowered:
            score += weight
            reasons.append(f"+{weight}:{term}")

    for term, weight in NEGATIVE_TERMS.items():
        if _normalize_text(term) in lowered:
            score += weight
            reasons.append(f"{weight}:{term}")

    for term in target_terms:
        if _normalize_text(term) in lowered:
            score += 6
            reasons.append(f"+6:{term}")

    return score, ", ".join(reasons)


def extract_power_candidates(text: str, *, context_chars: int = 140) -> list[Candidate]:
    """Extract every power value while retaining local context and line semantics."""
    try:
        candidates: list[Candidate] = []
        for match in POWER_RE.finditer(text):
            start = max(0, match.start() - context_chars)
            end = min(len(text), match.end() + context_chars)
            context = re.sub(r"\s+", " ", text[start:end]).strip()

            line_start = text.rfind("\n", 0, match.start()) + 1
            line_end = text.find("\n", match.end())
            if line_end == -1:
                line_end = len(text)
            source_line = re.sub(r"\s+", " ", text[line_start:line_end]).strip()
            normalized_line = _normalize_text(source_line)

            value = normalize_power(float(match.group("value").replace(",", ".")), match.group("unit"))
            score, reasons = _score_context(source_line, ("fan motor", "motor power", "fan"))

            rejected_field = any(
                _normalize_text(term) in normalized_line
                for term in ("unit total power", "total heating", "total cooling", "electrical total")
            )
            if rejected_field:
                reason = "aggregate field"
                score -= 25
                warning("Genel kW adayı aggregate alan olduğu için reddedildi", value_kw=value, source_line=source_line)
            else:
                reason = reasons

            candidates.append(
                Candidate(
                    value_kw=value,
                    raw_value=match.group("value"),
                    unit=match.group("unit"),
                    context=context,
                    score=score,
                    rejected=rejected_field,
                    reason=reason,
                )
            )
        debug("Genel kW adayları çıkarıldı", candidate_count=len(candidates))
        return candidates
    except Exception as exc:
        exception("Genel kW adayları çıkarma hesaplama hatası", exc, text_preview=(text or "")[:1000])
        raise


def select_fan_motor_power(text: str) -> Candidate | None:
    """Return the best non-aggregate fan motor power candidate."""
    try:
        candidates = [c for c in extract_power_candidates(text) if not c.rejected]
        if not candidates:
            warning("Genel kW seçiminde uygun fan motor adayı bulunamadı")
            return None
        result = max(candidates, key=lambda c: c.score)
        debug("Genel fan motor kW adayı seçildi", value_kw=result.value_kw, score=result.score, reason=result.reason)
        return result
    except Exception as exc:
        exception("Genel fan motor kW seçimi hesaplama hatası", exc)
        raise


def extract_pdf_text(path: str | Path) -> str:
    """Extract text from a PDF using pypdf."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        debug("PDF genel metin çıkarımı tamamlandı", path=str(path), pages=len(reader.pages), chars=len(text))
        return text
    except Exception as exc:
        exception("PDF genel metin çıkarımı başarısız", exc, path=str(path))
        raise


def select_fan_motor_power_from_pdf(path: str | Path) -> Candidate | None:
    try:
        return select_fan_motor_power(extract_pdf_text(path))
    except Exception as exc:
        exception("PDF'den fan motor kW seçimi başarısız", exc, path=str(path))
        raise


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Select fan motor power from a PDF")
    parser.add_argument("pdf", help="PDF file")
    args = parser.parse_args()
    result = select_fan_motor_power_from_pdf(args.pdf)
    print(json.dumps(result.to_dict() if result else None, ensure_ascii=False, indent=2))
