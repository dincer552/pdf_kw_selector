"""AHU / equipment reference discovery and conservative matching."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from difflib import SequenceMatcher
import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader


_UNIT_PATTERNS = [
    ("unit_reference", re.compile(r"\bunit\s+reference\s*[:=]?\s*([A-Z0-9][A-Z0-9_-]{1,})", re.I)),
    ("unit_number", re.compile(r"\bunit\s+number\s*[:=]?\s*([A-Z0-9][A-Z0-9_-]{1,})", re.I)),
    ("ahu_token", re.compile(r"\b(AHU[_ -]?[A-Z0-9][A-Z0-9_-]{0,})\b", re.I)),
]


def normalize_equipment_id(value: str | None) -> str:
    """Normalize AHU/equipment identifiers while preserving significant suffixes."""
    value = unicodedata.normalize("NFKC", value or "").upper().strip()
    value = re.sub(r"\s+", "", value)
    value = value.replace("_", "-")
    value = re.sub(r"-+", "-", value)
    if value.startswith("AHU-"):
        tail = value[4:]
        tail = re.sub(r"(?<=-)(0+)(\d+)", r"\2", tail)
        return "AHU-" + tail
    if value.startswith("AHU") and not value.startswith("AHU-"):
        tail = value[3:].lstrip("-")
        tail = re.sub(r"(?<=-)(0+)(\d+)", r"\2", tail)
        return "AHU-" + tail
    return re.sub(r"(?<=-)(0+)(\d+)", r"\2", value)


@dataclass(frozen=True)
class EquipmentOccurrence:
    equipment_id: str
    normalized: str
    page: int
    source: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class AHUDiscovery:
    equipment_ids: tuple[EquipmentOccurrence, ...]

    def unique_ids(self) -> tuple[str, ...]:
        seen = set()
        out = []
        for item in self.equipment_ids:
            if item.normalized not in seen:
                seen.add(item.normalized)
                out.append(item.normalized)
        return tuple(out)

    def to_dict(self) -> dict:
        return {"equipment_ids": [x.to_dict() for x in self.equipment_ids], "unique_ids": list(self.unique_ids())}


def discover_equipment_from_text(pages: list[str]) -> AHUDiscovery:
    occurrences: list[EquipmentOccurrence] = []
    seen_page: set[tuple[str, int]] = set()
    for page_no, text in enumerate(pages, start=1):
        for source, pattern in _UNIT_PATTERNS:
            for match in pattern.finditer(text or ""):
                raw = match.group(1).strip(" .,:;)]}")
                if source == "ahu_token":
                    raw = raw.replace("_", "-")
                if not raw:
                    continue
                normalized = normalize_equipment_id(raw)
                if not normalized.startswith("AHU-") or len(normalized) < 6:
                    continue
                key = (normalized, page_no)
                if key in seen_page:
                    continue
                seen_page.add(key)
                occurrences.append(EquipmentOccurrence(raw, normalized, page_no, source))
    occurrences.sort(key=lambda x: (x.page, x.normalized, x.source))
    return AHUDiscovery(tuple(occurrences))


def discover_equipment(path: str | Path) -> AHUDiscovery:
    reader = PdfReader(str(path))
    return discover_equipment_from_text([(page.extract_text() or "") for page in reader.pages])


@dataclass(frozen=True)
class AHUMatch:
    left_id: str | None
    right_id: str | None
    left_normalized: str | None
    right_normalized: str | None
    score: float
    status: str
    reason: str
    left_page: int | None = None
    right_page: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _suffix_tokens(value: str) -> list[str]:
    normalized = normalize_equipment_id(value)
    tail = normalized[4:] if normalized.startswith("AHU-") else normalized
    return [x for x in re.split(r"[-_ ]+", tail) if x]


def score_ahu_ids(left: str | None, right: str | None) -> tuple[float, str, str]:
    l = normalize_equipment_id(left)
    r = normalize_equipment_id(right)
    if not l or not r:
        return 0.0, "NO_MATCH", "missing equipment reference"
    if l == r:
        return 1.0, "EXACT", "normalized equipment references are identical"
    lt = _suffix_tokens(l)
    rt = _suffix_tokens(r)
    if lt and rt and lt == rt:
        return 0.98, "NORMALIZED_MATCH", "same AHU suffix after normalization"

    lnums = re.findall(r"\d+", l)
    rnums = re.findall(r"\d+", r)
    if lnums and rnums and lnums[-1] != rnums[-1]:
        return 0.2, "NO_MATCH", "AHU numeric suffix differs"

    seq = SequenceMatcher(None, l, r).ratio()
    if seq >= 0.90:
        return seq, "REVIEW_REQUIRED", "very similar but not identical equipment reference"
    return seq, "NO_MATCH", "insufficient equipment-reference agreement"


def match_ahu_ids(left: str | None, right: str | None, *, left_page: int | None = None, right_page: int | None = None) -> AHUMatch:
    score, status, reason = score_ahu_ids(left, right)
    return AHUMatch(left, right, normalize_equipment_id(left) or None, normalize_equipment_id(right) or None, round(score, 4), status, reason, left_page, right_page)


def match_ahu_lists(left: list[EquipmentOccurrence], right: list[EquipmentOccurrence]) -> list[AHUMatch]:
    left_unique = {}
    right_unique = {}
    for item in left:
        left_unique.setdefault(item.normalized, item)
    for item in right:
        right_unique.setdefault(item.normalized, item)

    pairs: list[tuple[float, str, str, AHUMatch]] = []
    for lid, lo in left_unique.items():
        for rid, ro in right_unique.items():
            m = match_ahu_ids(lid, rid, left_page=lo.page, right_page=ro.page)
            pairs.append((m.score, lid, rid, m))

    output: list[AHUMatch] = []
    used_l: set[str] = set()
    used_r: set[str] = set()
    for _, lid, rid, m in sorted(pairs, key=lambda x: x[0], reverse=True):
        if lid in used_l or rid in used_r:
            continue
        if m.status == "NO_MATCH":
            continue
        output.append(m)
        used_l.add(lid)
        used_r.add(rid)

    for lid, item in left_unique.items():
        if lid not in used_l:
            output.append(AHUMatch(item.equipment_id, None, lid, None, 0.0, "ONLY_IN_PDF1", "equipment exists only on left side", item.page, None))
    for rid, item in right_unique.items():
        if rid not in used_r:
            output.append(AHUMatch(None, item.equipment_id, None, rid, 0.0, "ONLY_IN_PDF2", "equipment exists only on right side", None, item.page))

    return output
