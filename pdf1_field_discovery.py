"""Strict field-based discovery for PDF1 selection documents."""
from __future__ import annotations

import re
from pathlib import Path

import fitz

from ahu_matching import AHUDiscovery, EquipmentOccurrence, normalize_equipment_id
from project_discovery import ProjectCandidate, ProjectDiscovery, normalize_project_name

_FIELD_STOP_RE = re.compile(
    r"\s+(?:creation\s+date|revision\s+date|revision\s+no|designer|model|airflow\s+rate)\b",
    re.I,
)
_SUPPORTED_UNIT_RE = re.compile(
    r"\b(?:[A-Z0-9]+[_ -]+AHU[_ -]?[A-Z]?\d+(?:\.\d+)?|HKS[_ -]?\d+|KS[_ -]?[A-Z]?\d+(?:\.\d+)?|SS[_ -]?[A-Z]?\d+(?:\.\d+)?|PW[_ -]?[A-Z]?\d+(?:\.\d+)?|AHU(?:[_ -]+[A-Z0-9_.-]+|\d[A-Z0-9_.-]*))\b",
    re.I,
)


def _value_after_label(lines: list[str], index: int, label: str) -> str:
    line = lines[index].strip()
    match = re.match(rf"^\s*{label}\s*[:=]?\s*(.*?)\s*$", line, re.I)
    value = match.group(1).strip(" :-\t") if match else ""
    if value:
        return value
    for candidate in lines[index + 1:index + 6]:
        candidate = candidate.strip(" :-\t")
        if not candidate:
            continue
        if re.match(r"^(?:project|unit\s+reference|creation\s+date|revision\s+date|revision\s+no)\b", candidate, re.I):
            break
        return candidate
    for candidate in reversed(lines[max(0, index - 8):index]):
        candidate = candidate.strip(" :-\t")
        if not candidate:
            continue
        if re.match(r"^(?:project|unit\s+reference|creation\s+date|revision\s+date|revision\s+no)\b", candidate, re.I):
            continue
        return candidate
    return ""


def _coordinate_unit_reference(path: str | Path) -> list[EquipmentOccurrence]:
    """Read Unit Reference using real PDF word coordinates when text extraction splits the row."""
    occurrences = []
    seen = set()
    doc = fitz.open(str(path))
    try:
        for page_no, page in enumerate(doc, 1):
            words = page.get_text("words")
            # word tuple: x0, y0, x1, y1, text, block_no, line_no, word_no
            lines = {}
            for word in words:
                lines.setdefault((word[5], word[6]), []).append(word)
            for line in lines.values():
                line.sort(key=lambda w: w[0])
            for line in lines.values():
                texts = [w[4].strip() for w in line]
                for i, token in enumerate(texts):
                    if token.casefold() != "unit":
                        continue
                    if i + 1 >= len(texts) or texts[i + 1].casefold() != "reference":
                        continue
                    label_right = line[i + 1][2]
                    # First prefer a valid token on the same visual row and to the right.
                    candidates = []
                    for word in line[i + 2:]:
                        if word[0] + 0.5 < label_right:
                            continue
                        match = _SUPPORTED_UNIT_RE.search(word[4])
                        if match:
                            candidates.append(match.group(0))
                    # If the value is on the next visual row, find the nearest valid token
                    # below the label, constrained to a small vertical distance and x range.
                    if not candidates:
                        label_x = (line[i][0] + line[i + 1][2]) / 2
                        label_y = (line[i][1] + line[i][3]) / 2
                        nearby = []
                        for other in lines.values():
                            if other is line:
                                continue
                            for word in other:
                                word_y = (word[1] + word[3]) / 2
                                if word_y <= label_y or word_y - label_y > 45:
                                    continue
                                if abs(((word[0] + word[2]) / 2) - label_x) > 180:
                                    continue
                                match = _SUPPORTED_UNIT_RE.search(word[4])
                                if match:
                                    nearby.append((word_y - label_y, match.group(0)))
                        nearby.sort(key=lambda x: x[0])
                        candidates = [nearby[0][1]] if nearby else []
                    for raw in candidates[:1]:
                        raw = raw.strip(" .,:;)]}")
                        normalized = normalize_equipment_id(raw)
                        if not normalized:
                            continue
                        key = (normalized, page_no)
                        if key in seen:
                            continue
                        seen.add(key)
                        occurrences.append(EquipmentOccurrence(raw, normalized, page_no, "unit_reference_coordinates"))
    finally:
        doc.close()
    return occurrences


def discover_pdf1_unit_reference(pages: list[str], path: str | Path | None = None) -> AHUDiscovery:
    occurrences = []
    seen = set()
    for page_no, text in enumerate(pages, 1):
        lines = (text or "").splitlines()
        for index, line in enumerate(lines):
            if not re.match(r"^\s*unit\s+reference\b", line, re.I):
                continue
            value = _value_after_label(lines, index, r"unit\s+reference")
            match = _SUPPORTED_UNIT_RE.search(value)
            if not match:
                window = "\n".join(lines[max(0, index - 8):min(len(lines), index + 8)])
                match = _SUPPORTED_UNIT_RE.search(window)
            if not match:
                continue
            raw = match.group(0).strip(" .,:;)]}")
            normalized = normalize_equipment_id(raw)
            key = (normalized, page_no)
            if normalized and key not in seen:
                seen.add(key)
                occurrences.append(EquipmentOccurrence(raw, normalized, page_no, "unit_reference"))
    # Coordinate fallback is deliberately after text discovery: it fixes scrambled
    # extraction without changing the fast path for normal PDFs.
    if not occurrences and path is not None:
        occurrences = _coordinate_unit_reference(path)
    occurrences.sort(key=lambda x: (x.page, x.normalized))
    return AHUDiscovery(tuple(occurrences))


def discover_pdf1_project(pages: list[str]) -> ProjectDiscovery:
    candidates = []
    for page_no, text in enumerate(pages, 1):
        lines = (text or "").splitlines()
        for index, line in enumerate(lines):
            if not re.match(r"^\s*project\b", line, re.I):
                continue
            value = _value_after_label(lines, index, r"project")
            value = _FIELD_STOP_RE.split(value, maxsplit=1)[0]
            value = re.sub(r"\s+", " ", value).strip(" :-\t")
            normalized = normalize_project_name(value)
            if value and normalized and len(normalized.split()) >= 2:
                candidates.append(ProjectCandidate(value, normalized, "project_field", page_no, "HIGH"))
    unique = []
    seen = set()
    for item in candidates:
        if item.normalized not in seen:
            seen.add(item.normalized)
            unique.append(item)
    selected = unique[0] if unique else None
    return ProjectDiscovery(
        selected.value if selected else None,
        selected.normalized if selected else None,
        selected.source if selected else None,
        selected.page if selected else None,
        selected.confidence if selected else "REVIEW",
        tuple(unique),
    )
