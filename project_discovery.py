"""Project-name discovery from Systemair engineering PDFs."""
from __future__ import annotations

from dataclasses import dataclass, asdict
import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader


_GENERIC_TOKENS = {
    "proje", "project", "name", "projectname", "prj", "projectno",
    "order number", "unit number", "unit reference", "revision date",
    "creation date", "revision no", "date",
}
_LABEL_RE = re.compile(r"^\s*(?:proje\s*name|project\s*name)\s*[:=]?\s*(.*?)\s*$", re.I)
_HEADER_RE = re.compile(r"^\s*project\b.*$", re.I)
_FIELD_LABEL_RE = re.compile(
    r"^\s*(?:order\s+number|unit\s+(?:number|reference)|revision\s+(?:date|no)|creation\s+date)\s*[:=]?\s*$",
    re.I,
)
_TRAILING_HEADER_RE = re.compile(
    r"\s+(?:creation\s+date|revision\s+date|revision\s+no)\b.*$",
    re.I,
)
_NUMERIC_ONLY_RE = re.compile(r"^[\d\s./_-]+$")
_AHU_ONLY_RE = re.compile(r"^AHU[-_ ]?[A-Z0-9_-]+$", re.I)


@dataclass(frozen=True)
class ProjectCandidate:
    value: str
    normalized: str
    source: str
    page: int
    confidence: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ProjectDiscovery:
    project_name: str | None
    project_name_normalized: str | None
    project_source: str | None
    project_page: int | None
    confidence: str
    candidates: tuple[ProjectCandidate, ...]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["candidates"] = [candidate.to_dict() for candidate in self.candidates]
        return data


def normalize_project_name(value: str) -> str:
    """Normalize project names while preserving Turkish letter equivalence."""
    value = unicodedata.normalize("NFKC", value or "")
    value = value.replace("İ", "I").replace("ı", "i")
    value = value.replace("–", "-").replace("—", "-").replace("−", "-")
    value = value.casefold()
    value = "".join(
        char for char in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(char)
    )
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _clean_value(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip(" :-\t")


def _is_field_label(value: str) -> bool:
    return bool(_FIELD_LABEL_RE.match(_clean_value(value)))


def _looks_like_project_name(value: str) -> bool:
    value = _clean_value(value)
    if not value or _is_field_label(value):
        return False
    if _NUMERIC_ONLY_RE.fullmatch(value) or _AHU_ONLY_RE.fullmatch(value):
        return False
    normalized = normalize_project_name(value)
    tokens = normalized.split()
    return len(tokens) >= 2 and sum(bool(re.search(r"[a-z]", token)) for token in tokens) >= 2


def _strip_header_metadata(value: str) -> str:
    """Remove creation/revision columns appended to a mixed Systemair header."""
    return _clean_value(_TRAILING_HEADER_RE.sub("", value or ""))


def _candidate(value: str, source: str, page: int, confidence: str) -> ProjectCandidate | None:
    value = _strip_header_metadata(value)
    if not _looks_like_project_name(value):
        return None
    normalized = normalize_project_name(value)
    if not normalized or normalized in _GENERIC_TOKENS:
        return None
    return ProjectCandidate(value, normalized, source, page, confidence)


def _is_known_field_value(value: str) -> bool:
    value = _clean_value(value)
    return bool(
        _NUMERIC_ONLY_RE.fullmatch(value)
        or _AHU_ONLY_RE.fullmatch(value)
    )


def _find_multiline_project_name(lines: list[str], start_index: int) -> str:
    """Find the natural-language value belonging to an empty project-name field."""
    look = start_index + 1
    while look < min(len(lines), start_index + 30):
        value = _clean_value(lines[look])
        if not value:
            look += 1
            continue
        if _is_field_label(value):
            look += 1
            continue
        if _is_known_field_value(value):
            look += 1
            continue
        if _looks_like_project_name(value):
            return _strip_header_metadata(value)
        look += 1
    return ""


def discover_project_from_text(pages: list[str]) -> ProjectDiscovery:
    candidates: list[ProjectCandidate] = []

    for page_number, text in enumerate(pages, start=1):
        lines = [line.strip() for line in (text or "").splitlines()]
        index = 0
        while index < len(lines):
            line = lines[index]
            match = _LABEL_RE.match(line)
            if match:
                value = _strip_header_metadata(match.group(1))
                if not value:
                    value = _find_multiline_project_name(lines, index)
                item = _candidate(value, "project_name_field", page_number, "HIGH")
                if item:
                    candidates.append(item)
                index += 1
                continue

            if _HEADER_RE.match(line):
                item = _candidate(line, "project_header", page_number, "MEDIUM")
                if item:
                    candidates.append(item)

            index += 1

    unique: list[ProjectCandidate] = []
    seen: set[tuple[str, str]] = set()
    for item in candidates:
        key = (item.normalized, item.source)
        if key not in seen:
            seen.add(key)
            unique.append(item)

    explicit = [c for c in unique if c.source == "project_name_field"]
    headers = [c for c in unique if c.source == "project_header"]
    selected = explicit[0] if explicit else (headers[0] if headers else None)

    return ProjectDiscovery(
        project_name=selected.value if selected else None,
        project_name_normalized=selected.normalized if selected else None,
        project_source=selected.source if selected else None,
        project_page=selected.page if selected else None,
        confidence=selected.confidence if selected else "REVIEW",
        candidates=tuple(unique),
    )


def discover_project(path: str | Path) -> ProjectDiscovery:
    """Extract and discover the project name from a PDF."""
    reader = PdfReader(str(path))
    pages = [(page.extract_text() or "") for page in reader.pages]
    return discover_project_from_text(pages)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Discover project name from a PDF")
    parser.add_argument("pdf")
    args = parser.parse_args()
    print(discover_project(args.pdf).to_dict())
