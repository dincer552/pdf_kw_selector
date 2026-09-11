"""Project-name discovery from Systemair engineering PDFs."""
from __future__ import annotations

from dataclasses import dataclass, asdict
import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader

from app_logger import debug, exception, info, warning

_GENERIC_TOKENS = {"proje", "project", "name", "projectname", "prj", "projectno", "order number", "unit number", "unit reference", "revision date", "creation date", "revision no", "date"}
_LABEL_RE = re.compile(r"^\s*(?:proje\s*name|project\s*name)\s*[:=]?\s*(.*?)\s*$", re.I)
_PROJECT_RE = re.compile(r"^\s*project\s*[:=]?\s*(.*?)\s*$", re.I)
_FIELD_LABEL_RE = re.compile(r"^\s*(?:project|proje|order\s+number|unit\s+(?:number|reference)|revision\s+(?:date|no)|creation\s+date)\s*[:=]?\s*$", re.I)
_TRAILING_HEADER_RE = re.compile(r"\s+(?:creation\s+date|revision\s+date|revision\s+no)\b.*$", re.I)
_NUMERIC_ONLY_RE = re.compile(r"^[\d\s./_-]+$")
_AHU_ONLY_RE = re.compile(r"^AHU[-_ ]?[A-Z0-9_-]+$", re.I)
_GENERIC_FAN_PROJECT_RE = re.compile(r"^(?:(?:supply|return|exhaust|activation|reactivation)(?:\s+[/ -]?\s*reactivation)?\s+fan\s+(?:air\s+volume|motor\s+power)|fan\s+(?:air\s+volume|motor\s+power))$", re.I)
_GENERIC_ENGINEERING_FIELD_PATTERNS = (
    re.compile(r"^(?:(?:supply|return|exhaust|activation|reactivation)\s+)?(?:fan\s+)?(?:air\s+volume|motor\s+power|power|capacity|nominal\s+rpm)$", re.I),
    re.compile(r"^(?:rotor\s+)?heat\s+recovery(?:\s+unit)?\s+motor\s+power$", re.I),
    re.compile(r"^electrical\s+(?:heater|heating)(?:\s+total)?\s+power(?:\s+stage\s+number)?$", re.I),
    re.compile(r"^unit\s+(?:total|overall)\s+power$", re.I),
    re.compile(r"^(?:total|electrical)\s+(?:heating|cooling|power)$", re.I),
    re.compile(r"^(?:shaft\s+power|vfd\s+(?:included|excluded|dahil|hariç)|nominal\s+rpm)$", re.I),
)
_GENERIC_FAN_PROJECT_SET = {"fan air volume", "supply fan air volume", "return fan air volume", "exhaust fan air volume", "activation fan air volume", "reactivation fan air volume", "activation reactivation fan air volume", "fan motor power", "supply fan motor power", "return fan motor power", "exhaust fan motor power", "activation fan motor power", "reactivation fan motor power", "activation reactivation fan motor power", "supply air volume", "return air volume", "exhaust air volume"}

@dataclass(frozen=True)
class ProjectCandidate:
    value: str
    normalized: str
    source: str
    page: int
    confidence: str
    def to_dict(self) -> dict: return asdict(self)

@dataclass(frozen=True)
class ProjectDiscovery:
    project_name: str | None
    project_name_normalized: str | None
    project_source: str | None
    project_page: int | None
    confidence: str
    candidates: tuple[ProjectCandidate, ...]
    def to_dict(self) -> dict:
        data = asdict(self); data["candidates"] = [candidate.to_dict() for candidate in self.candidates]; return data


def normalize_project_name(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").replace("İ", "I").replace("ı", "i").replace("–", "-").replace("—", "-").replace("−", "-").casefold()
    value = "".join(char for char in unicodedata.normalize("NFKD", value) if not unicodedata.combining(char))
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _clean_value(value: str) -> str: return re.sub(r"\s+", " ", value or "").strip(" :-\t")
def _is_field_label(value: str) -> bool: return bool(_FIELD_LABEL_RE.match(_clean_value(value)))

def _is_generic_project_name(value: str) -> bool:
    normalized = normalize_project_name(_clean_value(value))
    if not normalized: return False
    if normalized in _GENERIC_FAN_PROJECT_SET or bool(_GENERIC_FAN_PROJECT_RE.fullmatch(normalized)): return True
    return any(pattern.fullmatch(normalized) for pattern in _GENERIC_ENGINEERING_FIELD_PATTERNS)

def _looks_like_project_name(value: str) -> bool:
    value = _clean_value(value)
    if not value or _is_field_label(value) or _is_generic_project_name(value): return False
    if _NUMERIC_ONLY_RE.fullmatch(value) or _AHU_ONLY_RE.fullmatch(value): return False
    tokens = normalize_project_name(value).split()
    return len(tokens) >= 2 and sum(bool(re.search(r"[a-z]", token)) for token in tokens) >= 2

def _strip_header_metadata(value: str) -> str: return _clean_value(_TRAILING_HEADER_RE.sub("", value or ""))

def _candidate(value: str, source: str, page: int, confidence: str) -> ProjectCandidate | None:
    value = _strip_header_metadata(value)
    if not _looks_like_project_name(value): return None
    normalized = normalize_project_name(value)
    if not normalized or normalized in _GENERIC_TOKENS: return None
    return ProjectCandidate(value, normalized, source, page, confidence)

def _is_known_field_value(value: str) -> bool:
    value = _clean_value(value)
    return bool(_NUMERIC_ONLY_RE.fullmatch(value) or _AHU_ONLY_RE.fullmatch(value) or _is_generic_project_name(value))

def _find_multiline_project_name(lines: list[str], start_index: int) -> str:
    look = start_index + 1; limit = min(len(lines), start_index + 30)
    while look < limit:
        value = _clean_value(lines[look])
        if not value: look += 1; continue
        if _is_field_label(value) or _is_known_field_value(value):
            debug("Boş Project alanından sonra teknik alan atlandı", candidate=value, line_index=look); look += 1; continue
        if _looks_like_project_name(value): return _strip_header_metadata(value)
        look += 1
    warning("Project etiketi sonrasında geçerli proje adı bulunamadı", start_index=start_index); return ""


def discover_project_from_text(pages: list[str]) -> ProjectDiscovery:
    try:
        candidates: list[ProjectCandidate] = []
        fragments: list[tuple[int, str]] = []
        for page_number, text in enumerate(pages, start=1):
            for line in (text or "").splitlines(): fragments.append((page_number, line.strip()))
        for index, (page_number, line) in enumerate(fragments):
            match = _LABEL_RE.match(line)
            if match:
                value = _strip_header_metadata(match.group(1)) or _find_multiline_project_name([fragment for _, fragment in fragments], index)
                item = _candidate(value, "project_name_field", page_number, "HIGH")
                if item: candidates.append(item)
                continue
            match = _PROJECT_RE.match(line)
            if match:
                value = _strip_header_metadata(match.group(1)) or _find_multiline_project_name([fragment for _, fragment in fragments], index)
                item = _candidate(value, "project_field", page_number, "HIGH")
                if item: candidates.append(item)
                continue
        unique: list[ProjectCandidate] = []; seen: set[tuple[str, str]] = set()
        for item in candidates:
            key = (item.normalized, item.source)
            if key not in seen: seen.add(key); unique.append(item)
        explicit = [c for c in unique if c.source in {"project_name_field", "project_field"}]
        selected = explicit[0] if explicit else None
        result = ProjectDiscovery(selected.value if selected else None, selected.normalized if selected else None, selected.source if selected else None, selected.page if selected else None, selected.confidence if selected else "REVIEW", tuple(unique))
        if selected: info("Proje adı keşfedildi", project=selected.value, normalized=selected.normalized, source=selected.source, page=selected.page, confidence=selected.confidence, candidate_count=len(unique))
        else: warning("Proje adı keşfedilemedi", candidate_count=len(unique), candidates=[x.to_dict() for x in unique])
        return result
    except Exception as exc:
        exception("Proje keşfi hesaplama hatası", exc, page_count=len(pages)); raise


def discover_project(path: str | Path) -> ProjectDiscovery:
    try:
        reader = PdfReader(str(path)); pages = [(page.extract_text() or "") for page in reader.pages]; return discover_project_from_text(pages)
    except Exception as exc:
        exception("PDF proje keşfi başarısız", exc, path=str(path)); raise

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Discover project name from a PDF"); parser.add_argument("pdf"); args = parser.parse_args(); print(discover_project(args.pdf).to_dict())
