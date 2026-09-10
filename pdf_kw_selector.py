"""Context-aware keyword/value selector for engineering PDFs."""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

from app_logger import calculation_error, debug, exception, info, warning


POWER_RE = re.compile(
    r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>kw|kva|w)\b",
    re.IGNORECASE,
)


def normalize_equipment_id(value: str) -> str:
    """Normalize IDs such as AHU-1, AHU_01 and AHU 001 to AHU1."""
    try:
        original = value
        value = value.upper().strip()
        value = re.sub(r"\s+", "", value)
        value = re.sub(r"[_\-]+", "", value)
        match = re.fullmatch(r"([A-Z]+)0*(\d+)", value)
        result = f"{match.group(1)}{int(match.group(2))}" if match else value
        debug("Equipment ID normalize edildi", original=original, normalized=result)
        return result
    except Exception as exc:
        calculation_error("normalize_equipment_id", exc, value=repr(value))
        raise


def _normalize_text(value: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(ch)
    ).lower()


def normalize_power(value: float, unit: str) -> float:
    try:
        original_value = value
        original_unit = unit
        unit = unit.lower()
        if unit not in {"w", "kw", "kva"}:
            raise ValueError(f"Unsupported power unit: {unit!r}")
        if not math.isfinite(value) or value < 0:
            raise ValueError("Power value must be finite and >= 0")
        result = value / 1000.0 if unit == "w" else value
        debug("Güç birimi normalize edildi", value=original_value, unit=original_unit, value_kw=result)
        return result
    except Exception as exc:
        calculation_error("normalize_power", exc, value=value, unit=unit)
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
    try:
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
        debug("kW aday bağlam skoru hesaplandı", context=context[:300], score=score, reasons=reasons)
        return score, ", ".join(reasons)
    except Exception as exc:
        calculation_error("_score_context", exc, context=context[:500])
        raise


def extract_power_candidates(text: str, *, context_chars: int = 140) -> list[Candidate]:
    """Extract every power value while retaining local context and line semantics."""
    try:
        if context_chars < 0:
            raise ValueError("context_chars must be >= 0")
        candidates: list[Candidate] = []
        for match in POWER_RE.finditer(text or ""):
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
            reason = "aggregate field" if rejected_field else reasons
            if rejected_field:
                score -= 25
                warning("Genel kW adayı aggregate alan olduğu için reddedildi", value_kw=value, source_line=source_line)
            candidate = Candidate(value, match.group("value"), match.group("unit"), context, score, rejected_field, reason)
            candidates.append(candidate)
            debug("kW adayı çıkarıldı", candidate=candidate.to_dict(), source_line=source_line)
        info("Genel kW adayları çıkarıldı", candidate_count=len(candidates))
        if not candidates and (text or "").strip():
            warning("Metinde hiç kW/kVA/W adayı bulunamadı", text_preview=text[:500])
        return candidates
    except Exception as exc:
        calculation_error("extract_power_candidates", exc, text_preview=(text or "")[:1000], context_chars=context_chars)
        raise


def select_fan_motor_power(text: str) -> Candidate | None:
    """Return the best non-aggregate fan motor power candidate."""
    try:
        all_candidates = extract_power_candidates(text)
        candidates = [c for c in all_candidates if not c.rejected]
        if not candidates:
            warning("Genel kW seçiminde uygun fan motor adayı bulunamadı", candidate_count=len(all_candidates))
            return None
        result = max(candidates, key=lambda c: c.score)
        info("Genel fan motor kW adayı seçildi", value_kw=result.value_kw, score=result.score, reason=result.reason)
        return result
    except Exception as exc:
        calculation_error("select_fan_motor_power", exc, text_preview=(text or "")[:1000])
        raise


def extract_pdf_text(path: str | Path) -> str:
    """Extract text from a PDF using pypdf."""
    from pypdf import PdfReader
    try:
        path = Path(path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {path}")
        if not path.is_file():
            raise IsADirectoryError(f"PDF path is not a file: {path}")
        reader = PdfReader(str(path))
        pages: list[str] = []
        for page_number, page in enumerate(reader.pages, 1):
            try:
                text = page.extract_text() or ""
                pages.append(text)
                debug("PDF genel sayfa metni çıkarıldı", path=str(path), page=page_number, chars=len(text))
            except Exception as exc:
                exception("PDF genel sayfa metin çıkarma hatası", exc, path=str(path), page=page_number)
                raise
        result = "\n".join(pages)
        info("PDF genel metin çıkarımı tamamlandı", path=str(path), pages=len(pages), chars=len(result))
        if not result.strip():
            warning("PDF metin çıkarma boş sonuç verdi", path=str(path), pages=len(pages))
        return result
    except Exception as exc:
        exception("PDF genel metin çıkarımı başarısız", exc, path=str(path))
        raise


def select_fan_motor_power_from_pdf(path: str | Path) -> Candidate | None:
    try:
        info("PDF fan motor kW seçimi başladı", path=str(path))
        result = select_fan_motor_power(extract_pdf_text(path))
        info("PDF fan motor kW seçimi tamamlandı", path=str(path), result=result.to_dict() if result else None)
        return result
    except Exception as exc:
        calculation_error("select_fan_motor_power_from_pdf", exc, path=str(path))
        raise


if __name__ == "__main__":
    import argparse
    import json
    parser = argparse.ArgumentParser(description="Select fan motor power from a PDF")
    parser.add_argument("pdf", help="PDF file")
    args = parser.parse_args()
    result = select_fan_motor_power_from_pdf(args.pdf)
    print(json.dumps(result.to_dict() if result else None, ensure_ascii=False, indent=2))
