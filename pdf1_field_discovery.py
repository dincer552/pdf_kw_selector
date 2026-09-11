"""Strict field-based discovery for PDF1 selection documents."""
from __future__ import annotations

import re

from ahu_matching import AHUDiscovery, EquipmentOccurrence, normalize_equipment_id
from project_discovery import ProjectCandidate, ProjectDiscovery, normalize_project_name

_FIELD_STOP_RE = re.compile(
    r"\s+(?:creation\s+date|revision\s+date|revision\s+no|designer|model|airflow\s+rate)\b",
    re.I,
)
_SUPPORTED_UNIT_RE = re.compile(
    r"\b(?:HKS[_ -]?\d+|KS[_ -]?[A-Z]?\d+(?:\.\d+)?|SS[_ -]?[A-Z]?\d+(?:\.\d+)?|PW[_ -]?[A-Z]?\d+(?:\.\d+)?|AHU(?:[_ -]+[A-Z0-9_.-]+|\d[A-Z0-9_.-]*))\b",
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
    # Handle exporters that place the field value before its label.
    for candidate in reversed(lines[max(0, index - 8):index]):
        candidate = candidate.strip(" :-\t")
        if not candidate:
            continue
        if re.match(r"^(?:project|unit\s+reference|creation\s+date|revision\s+date|revision\s+no)\b", candidate, re.I):
            continue
        return candidate
    return ""


def discover_pdf1_unit_reference(pages: list[str]) -> AHUDiscovery:
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
