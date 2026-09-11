"""AHU / equipment reference discovery and conservative matching."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from difflib import SequenceMatcher
import re
import unicodedata
from pathlib import Path

from app_logger import debug, exception, info, warning
from pypdf import PdfReader

_UNIT_PATTERNS = [
    ("unit_reference", re.compile(r"\bunit\s+reference\s*[:=]?\s*([A-Z0-9][A-Z0-9_-]{1,})", re.I)),
    ("unit_number", re.compile(r"\bunit\s+number\s*[:=]?\s*([A-Z0-9][A-Z0-9_-]{1,})", re.I)),
    ("hks_token", re.compile(r"(?<![A-Z0-9])(HKS(?:[_ -]?\d+))\b", re.I)),
    ("ahu_token", re.compile(r"(?<![A-Z0-9])(AHU(?:[_ -]+[A-Z0-9][A-Z0-9_-]*|\d[A-Z0-9_-]*))\b", re.I)),
    ("ahu_embedded", re.compile(r"(?<![A-Z0-9])(?:[A-Z0-9]+[-_ ]+)(AHU(?:[_ -]+[A-Z0-9][A-Z0-9_-]*|\d[A-Z0-9_-]*))\b", re.I)),
]

_LABELLED_SOURCES = {"unit_reference", "unit_number"}


def _normalize_numeric_zeros(value: str) -> str:
    return re.sub(r"(?<![A-Z0-9])0+(?=\d)", "", value)


def normalize_equipment_id(value: str | None) -> str:
    value = unicodedata.normalize("NFKC", value or "").upper().strip()
    value = re.sub(r"\s+", "", value).replace("_", "-")
    value = re.sub(r"-+", "-", value)
    match = re.search(r"(?:^|-)AHU(?:-|$)(.*)$", value)
    if match:
        tail = _normalize_numeric_zeros(match.group(1).lstrip("-"))
        return "AHU-" + tail if tail else "AHU"
    if value.startswith("AHU"):
        tail = _normalize_numeric_zeros(value[3:].lstrip("-"))
        return "AHU-" + tail if tail else "AHU"
    return _normalize_numeric_zeros(value)


def _is_supported_equipment_id(normalized: str) -> bool:
    return normalized.startswith("AHU-") or bool(re.fullmatch(r"HKS-\d+", normalized))

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
        seen = set(); out = []
        for item in self.equipment_ids:
            if item.normalized not in seen:
                seen.add(item.normalized); out.append(item.normalized)
        return tuple(out)
    def to_dict(self) -> dict:
        return {"equipment_ids": [x.to_dict() for x in self.equipment_ids], "unique_ids": list(self.unique_ids())}


def discover_equipment_from_text(pages: list[str]) -> AHUDiscovery:
    try:
        occurrences = []
        labelled_occurrences = []
        seen_page = set()
        for page_no, text in enumerate(pages, start=1):
            for source, pattern in _UNIT_PATTERNS:
                for match in pattern.finditer(text or ""):
                    raw = match.group(1).strip(" .,:;)]}")
                    normalized = normalize_equipment_id(raw)
                    if not _is_supported_equipment_id(normalized) or len(normalized) < 5:
                        continue
                    key = (normalized, page_no)
                    if key in seen_page:
                        continue
                    seen_page.add(key)
                    item = EquipmentOccurrence(raw, normalized, page_no, source)
                    occurrences.append(item)
                    if source in _LABELLED_SOURCES:
                        labelled_occurrences.append(item)
        if labelled_occurrences:
            occurrences = labelled_occurrences
        occurrences.sort(key=lambda x: (x.page, x.normalized, x.source))
        result = AHUDiscovery(tuple(occurrences))
        info("AHU/equipment keşfi tamamlandı", page_count=len(pages), occurrence_count=len(occurrences), unique_ids=list(result.unique_ids()), labelled=bool(labelled_occurrences))
        if not result.unique_ids():
            warning("PDF'de geçerli AHU/equipment bulunamadı", page_count=len(pages))
        return result
    except Exception as exc:
        exception("AHU keşfi hesaplama hatası", exc, page_count=len(pages)); raise


def _equipment_from_filename(path: Path) -> EquipmentOccurrence | None:
    stem = re.sub(r"\s+", "_", path.stem.strip())
    match = re.fullmatch(r"HKS[_ -]?(\d+)", stem, re.I)
    if not match:
        return None
    raw = f"HKS-{match.group(1)}"
    normalized = normalize_equipment_id(raw)
    return EquipmentOccurrence(raw, normalized, 1, "filename")


def discover_equipment(path: str | Path) -> AHUDiscovery:
    try:
        path = Path(path).expanduser().resolve()
        reader = PdfReader(str(path))
        discovery = discover_equipment_from_text([(page.extract_text() or "") for page in reader.pages])
        if not discovery.unique_ids():
            filename_occurrence = _equipment_from_filename(path)
            if filename_occurrence is not None:
                discovery = AHUDiscovery((filename_occurrence,))
                info("Ekipman ID dosya adından keşfedildi", path=str(path), equipment_id=filename_occurrence.equipment_id, normalized=filename_occurrence.normalized)
        return discovery
    except Exception as exc:
        exception("PDF AHU keşfi başarısız", exc, path=str(path)); raise

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


def score_ahu_ids(left: str | None, right: str | None) -> tuple[float, str, str]:
    try:
        l = normalize_equipment_id(left); r = normalize_equipment_id(right)
        if not l or not r: return 0.0, "NO_MATCH", "missing equipment reference"
        if l == r: return 1.0, "EXACT", "normalized equipment references are identical"
        lt = _suffix_tokens(l); rt = _suffix_tokens(r)
        if lt and rt and lt == rt: return 0.98, "NORMALIZED_MATCH", "same equipment suffix after normalization"
        lnums = re.findall(r"\d+", l); rnums = re.findall(r"\d+", r)
        if lnums and rnums and lnums[-1] != rnums[-1]: return 0.2, "NO_MATCH", "equipment numeric suffix differs"
        seq = SequenceMatcher(None, l, r).ratio()
        if seq >= 0.78: return seq, "REVIEW_REQUIRED", "similar equipment reference requires user confirmation"
        return seq, "NO_MATCH", "insufficient equipment-reference agreement"
    except Exception as exc:
        exception("AHU eşleşme skoru hesaplanamadı", exc, left=left, right=right); raise


def match_ahu_ids(left: str | None, right: str | None, *, left_page: int | None = None, right_page: int | None = None) -> AHUMatch:
    score, status, reason = score_ahu_ids(left, right)
    return AHUMatch(left, right, normalize_equipment_id(left) or None, normalize_equipment_id(right) or None, round(score, 4), status, reason, left_page, right_page)


def _approved_family_match(left_id: str | None, right_id: str | None, approved_variants: set[tuple[str, str]]) -> tuple[bool, str]:
    left = normalize_equipment_id(left_id); right = normalize_equipment_id(right_id)
    if not left or not right: return False, ""
    for approved_left, approved_right in approved_variants:
        al = normalize_equipment_id(approved_left); ar = normalize_equipment_id(approved_right)
        if not al or not ar: continue
        lnums = re.findall(r"\d+", left); rnums = re.findall(r"\d+", right)
        alnums = re.findall(r"\d+", al); arnums = re.findall(r"\d+", ar)
        lprefix = re.sub(r"\d+", "#", left); rprefix = re.sub(r"\d+", "#", right)
        alprefix = re.sub(r"\d+", "#", al); arprefix = re.sub(r"\d+", "#", ar)
        if lprefix == alprefix and rprefix == arprefix:
            if lnums and rnums and alnums and arnums and lnums[-1] == rnums[-1]:
                return True, "same approved AHU naming family and numeric suffix"
    return False, ""


def match_ahu_lists(left: list[EquipmentOccurrence], right: list[EquipmentOccurrence], *, approved_variants: set[tuple[str, str]] | None = None) -> list[AHUMatch]:
    """Match exact normalized IDs first, then run fuzzy scoring only on leftovers."""
    approved_variants = approved_variants or set()
    left_unique = {}; right_unique = {}
    for item in left: left_unique.setdefault(item.normalized, item)
    for item in right: right_unique.setdefault(item.normalized, item)

    output = []
    used_l = set()
    used_r = set()

    # Fast path: normalized IDs that occur on both sides are unambiguous exact
    # matches. This avoids the O(N*M) scoring work for the common case.
    for normalized in left_unique.keys() & right_unique.keys():
        lo = left_unique[normalized]; ro = right_unique[normalized]
        output.append(match_ahu_ids(normalized, normalized, left_page=lo.page, right_page=ro.page))
        used_l.add(normalized); used_r.add(normalized)

    # Only unmatched IDs need fuzzy / approved-family comparison.
    pairs = []
    remaining_left = [(lid, lo) for lid, lo in left_unique.items() if lid not in used_l]
    remaining_right = [(rid, ro) for rid, ro in right_unique.items() if rid not in used_r]
    for lid, lo in remaining_left:
        for rid, ro in remaining_right:
            m = match_ahu_ids(lid, rid, left_page=lo.page, right_page=ro.page)
            approved, approved_reason = _approved_family_match(lid, rid, approved_variants)
            if approved and m.status not in {"EXACT", "NORMALIZED_MATCH"}:
                m = AHUMatch(m.left_id, m.right_id, m.left_normalized, m.right_normalized, max(m.score, 0.80), "APPROVED_FLEXIBLE", f"user-approved AHU variant family: {approved_reason}", m.left_page, m.right_page)
            elif (lid, rid) in approved_variants and m.status in {"NO_MATCH", "REVIEW_REQUIRED"}:
                m = AHUMatch(m.left_id, m.right_id, m.left_normalized, m.right_normalized, max(m.score, 0.80), "APPROVED_FLEXIBLE", "user-approved AHU variant", m.left_page, m.right_page)
            pairs.append((m.score, lid, rid, m))

    for _, lid, rid, m in sorted(pairs, key=lambda x: x[0], reverse=True):
        if lid in used_l or rid in used_r or m.status == "NO_MATCH":
            continue
        output.append(m); used_l.add(lid); used_r.add(rid)

    for lid, item in left_unique.items():
        if lid not in used_l:
            output.append(AHUMatch(item.equipment_id, None, lid, None, 0.0, "ONLY_IN_PDF1", "equipment exists only on left side", item.page, None))
    for rid, item in right_unique.items():
        if rid not in used_r:
            output.append(AHUMatch(None, item.equipment_id, None, rid, 0.0, "ONLY_IN_PDF2", "equipment exists only on right side", None, item.page))
    info("AHU eşleştirme hesaplandı", pdf1_unique=len(left_unique), pdf2_unique=len(right_unique), output_count=len(output), approved_variants=len(approved_variants), matches=[x.to_dict() for x in output])
    return output


def _suffix_tokens(value: str) -> list[str]:
    normalized = normalize_equipment_id(value)
    if normalized.startswith("AHU-"):
        tail = normalized[4:]
    else:
        tail = normalized
    return [x for x in re.split(r"[-_ ]+", tail) if x]
