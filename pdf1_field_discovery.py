"""Strict field-based discovery for PDF1 selection documents."""
from __future__ import annotations

import re

from ahu_matching import AHUDiscovery, EquipmentOccurrence, normalize_equipment_id
from project_discovery import ProjectCandidate, ProjectDiscovery, normalize_project_name


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
            value = re.sub(r"\s+", " ", value).strip(" .,:;)]}")
            if not value or re.fullmatch(r"unit\s+reference", value, re.I):
                continue
            normalized = normalize_equipment_id(value)
            key = (normalized, page_no)
            if normalized and key not in seen:
                seen.add(key)
                occurrences.append(EquipmentOccurrence(value, normalized, page_no, "unit_reference"))
    occurrences.sort(key=lambda x: (x.page, x.normalized))
    return AHUDiscovery(tuple(occurrences))


def discover_pdf1_project(pages: list[str]) -> ProjectDiscovery:
    candidates = []
    for page_no, text in enumerate(pages, 1):
        lines = (text or "").splitlines()
        for index, line in enumerate(lines):
            if not re.match(r"^\s*project\s*(?:[:=]|$)", line, re.I):
                continue
            value = _value_after_label(lines, index, r"project")
            value = re.sub(r"\s+", " ", value).strip(" :-\t")
            value = re.split(r"\s+(?:creation\s+date|revision\s+date|revision\s+no)\b", value, maxsplit=1, flags=re.I)[0].strip()
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
