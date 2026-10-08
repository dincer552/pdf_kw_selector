"""Motor current to fuse-rating suitability rules."""
from __future__ import annotations

import math
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class FuseCurrentRange:
    rating_a: int
    minimum_current_a: float
    maximum_current_a: float

    def to_dict(self):
        return {
            "rating_a": self.rating_a,
            "minimum_current_a": self.minimum_current_a,
            "maximum_current_a": self.maximum_current_a,
        }


_FUSE_RATINGS_A = (10, 16, 20, 25, 32, 40)


def _maximum_current(rating_a: int) -> float:
    if rating_a == 10:
        return 7.0
    return math.floor(rating_a * 0.8 + 0.5)


DEFAULT_FUSE_CURRENT_RANGES = tuple(
    FuseCurrentRange(
        rating_a=rating,
        minimum_current_a=0.0 if index == 0 else _maximum_current(_FUSE_RATINGS_A[index - 1]),
        maximum_current_a=_maximum_current(rating),
    )
    for index, rating in enumerate(_FUSE_RATINGS_A)
)
FUSE_CURRENT_RANGES = DEFAULT_FUSE_CURRENT_RANGES


def _settings_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        return Path(base) / "PDF_KW_Selector" / "settings.json"
    return Path.home() / ".pdf_kw_selector" / "settings.json"


def validate_fuse_current_ranges(
    values: Iterable[FuseCurrentRange | dict],
) -> tuple[FuseCurrentRange, ...]:
    rows = []
    for value in values:
        if isinstance(value, FuseCurrentRange):
            rating, maximum = value.rating_a, value.maximum_current_a
        else:
            rating, maximum = value["rating_a"], value["maximum_current_a"]
        rating_number = float(rating)
        maximum_number = float(maximum)
        if not math.isfinite(rating_number) or not rating_number.is_integer() or rating_number <= 0:
            raise ValueError("Sigorta değeri pozitif bir tam sayı olmalıdır.")
        if not math.isfinite(maximum_number) or maximum_number <= 0:
            raise ValueError("Akım üst limiti sıfırdan büyük, geçerli bir sayı olmalıdır.")
        rows.append((int(rating_number), maximum_number))
    if not rows:
        raise ValueError("En az bir sigorta-akım kademesi girilmelidir.")
    ratings = [rating for rating, _ in rows]
    maximums = [maximum for _, maximum in rows]
    if len(set(ratings)) != len(ratings):
        raise ValueError("Sigorta değerleri birbirinden farklı olmalıdır.")
    if any(left >= right for left, right in zip(ratings, ratings[1:])):
        raise ValueError("Sigorta değerleri küçükten büyüğe sıralanmalıdır.")
    if any(left >= right for left, right in zip(maximums, maximums[1:])):
        raise ValueError("Akım üst limitleri küçükten büyüğe sıralanmalıdır.")
    return tuple(
        FuseCurrentRange(
            rating_a=rating,
            minimum_current_a=0.0 if index == 0 else maximums[index - 1],
            maximum_current_a=maximum,
        )
        for index, (rating, maximum) in enumerate(rows)
    )


def save_fuse_current_ranges(
    values: Iterable[FuseCurrentRange | dict],
    path: str | Path | None = None,
) -> tuple[FuseCurrentRange, ...]:
    ranges = validate_fuse_current_ranges(values)
    target = Path(path) if path is not None else _settings_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(
            {"fuse_current_ranges": [item.to_dict() for item in ranges]},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    temporary.replace(target)
    return ranges


def load_fuse_current_ranges(path: str | Path | None = None) -> tuple[FuseCurrentRange, ...]:
    target = Path(path) if path is not None else _settings_path()
    if not target.exists():
        return DEFAULT_FUSE_CURRENT_RANGES
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
        return validate_fuse_current_ranges(payload["fuse_current_ranges"])
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        from app_logger import warning
        warning("Sigorta-akım ayarları okunamadı; varsayılan değerler kullanılacak", path=str(target), error=str(exc))
        return DEFAULT_FUSE_CURRENT_RANGES


def set_fuse_current_ranges(values: Iterable[FuseCurrentRange | dict]) -> tuple[FuseCurrentRange, ...]:
    global FUSE_CURRENT_RANGES
    FUSE_CURRENT_RANGES = validate_fuse_current_ranges(values)
    return FUSE_CURRENT_RANGES

_FUSE_VALUE_RE = re.compile(
    r"(?<!\d)(?:(?P<poles>\d+)\s*[x×]\s*)?(?P<rating>\d+)\s*(?:A|AMP(?:ERE)?)\b",
    re.I,
)
_NUMBER_RE = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*(?:A|AMP(?:ERE)?)?\s*$", re.I)


@dataclass(frozen=True)
class FuseCurrentCheck:
    status: str
    fuse_rating_a: int | None
    current_a: float | None
    expected_fuse_rating_a: int | None
    explanation: str


def parse_fuse_rating(value: str | int | float | None) -> int | None:
    """Extract a supported fuse rating, accepting values such as C16 or 16 A."""
    if value is None:
        return None
    text = str(value).strip().upper()
    match = _FUSE_VALUE_RE.search(text)
    if match:
        return int(match.group("rating"))
    number = _NUMBER_RE.fullmatch(text)
    if number:
        numeric = float(number.group(1).replace(",", "."))
        if numeric.is_integer() and int(numeric) in {item.rating_a for item in FUSE_CURRENT_RANGES}:
            return int(numeric)
    return None


def _parse_current(current_a: str | int | float | None) -> float | None:
    if current_a is None:
        return None
    if isinstance(current_a, (int, float)):
        return float(current_a)
    text = str(current_a).strip().replace(",", ".")
    match = _NUMBER_RE.fullmatch(text)
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def expected_fuse_rating(current_a: str | int | float | None) -> int | None:
    """Return the fuse rating whose current band contains the motor current."""
    current = _parse_current(current_a)
    if current is None or not math.isfinite(current) or current < 0:
        return None
    for index, current_range in enumerate(FUSE_CURRENT_RANGES):
        upper_bound_matches = (
            current <= current_range.maximum_current_a
            if index == len(FUSE_CURRENT_RANGES) - 1
            else current < current_range.maximum_current_a
        )
        if current_range.minimum_current_a <= current and upper_bound_matches:
            return current_range.rating_a
    return None


def check_fuse_current(
    current_a: str | int | float | None,
    fuse_value: str | int | float | None,
) -> FuseCurrentCheck:
    current = _parse_current(current_a)
    rating = parse_fuse_rating(fuse_value)
    expected = expected_fuse_rating(current)
    if current is None or not math.isfinite(current) or current < 0:
        return FuseCurrentCheck("UNKNOWN", rating, current, expected, "Motor akımı okunamadı.")
    if rating is None:
        return FuseCurrentCheck("UNKNOWN", None, current, expected, "Sigorta değeri tanınamadı.")
    if rating not in {item.rating_a for item in FUSE_CURRENT_RANGES}:
        return FuseCurrentCheck(
            "MISMATCH", rating, current, expected,
            f"{rating} A desteklenen sigorta kademelerinde değil; en küçük kademe 10 A.",
        )
    if expected is None:
        return FuseCurrentCheck(
            "OUT_OF_RANGE", rating, current, None,
            "Motor akımı tanımlı sigorta aralıklarının dışında.",
        )
    if rating == expected:
        return FuseCurrentCheck(
            "MATCH", rating, current, expected,
            f"{current:g} A akım, {rating} A sigorta için tanımlı aralıkta.",
        )
    return FuseCurrentCheck(
        "MISMATCH", rating, current, expected,
        f"{current:g} A akım için {expected} A sigorta bekleniyor; projede {rating} A var.",
    )


__all__ = [
    "FUSE_CURRENT_RANGES",
    "DEFAULT_FUSE_CURRENT_RANGES",
    "FuseCurrentRange",
    "FuseCurrentCheck",
    "validate_fuse_current_ranges",
    "save_fuse_current_ranges",
    "load_fuse_current_ranges",
    "set_fuse_current_ranges",
    "parse_fuse_rating",
    "expected_fuse_rating",
    "check_fuse_current",
]
