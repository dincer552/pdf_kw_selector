"""Project-name discovery from Systemair engineering PDFs."""
from __future__ import annotations

from dataclasses import dataclass, asdict
import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader


_GENERIC_TOKENS = {
    "proje", "project", "name", "projectname", "prj", "projectno",
}
_LABEL_RE = re.compile(r"^\s*(?:proje\s*name|project\s*name)\s*:\s*(.*?)\s*$", re.I)
_HEADER_RE = re.compile(r"^\s*project\s+(.+?)\s*$", re.I)


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


def _candidate(value: str, source: str, page: int, confidence: str) -> ProjectCandidate | None:
    value = _clean_value(value)
    normalized = normalize_project_name(value)
    if not normalized or normalized in _GENERIC_TOKENS:
        return None
    return ProjectCandidate(value, normalized, source, page, confidence)


def discover_project_from_text(pages: list[str]) -> ProjectDiscovery:
    candidates: list[ProjectCandidate] = []

    for page_number, text in enumerate(pages, start=1):
        lines = [line.strip() for line in (text or "").splitlines()]
        for index, line in enumerate(lines):
            match = _LABEL_RE.match(line)
            if match:
                inline = _clean_value(match.group(1))
                value = inline
                if not value:
                    for next_line in lines[index + 1:index + 6]:
                        next_line = _clean_value(next_line)
                        if next_line and not re.match(
                            r"^(?:order\s+number|unit\s+number|unit\s+reference)\s*:",
                            next_line,
                            re.I,
                        ):
                            value = next_line
                            break
                item = _candidate(value, "project_name_field", page_number, "HIGH")
                if item:
                    candidates.append(item)
                continue

            match = _HEADER_RE.match(line)
            if match:
                item = _candidate(match.group(1), "project_header", page_number, "MEDIUM")
                if item:
                    candidates.append(item)

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
