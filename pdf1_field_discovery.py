from __future__ import annotations

from pathlib import Path
import fitz
import re

from ahu_matching import AHUDiscovery, EquipmentOccurrence, normalize_equipment_id
from project_discovery import ProjectCandidate, ProjectDiscovery, normalize_project_name

# PDF1 coordinates are supplied in the PDF viewer coordinate system (origin bottom-left).
# PyMuPDF uses origin top-left, so every rectangle is converted before reading.
_PROJECT_BOX = (256.0, 763.0, 115.0, 18.0)
_UNIT_REFERENCE_BOX = (257.0, 738.0, 134.0, 20.0)

# Unit Reference is a labelled coordinate field, so do not restrict it to AHU/HKS/etc.
# Project-specific equipment names such as PEF-01A, AD-AHU-01, PR-AHU-01, KS-00.02, etc.
# must all be accepted. The coordinate box itself is the source of truth.
_EQUIPMENT_RE = re.compile(
    r"(?<![A-Z0-9])([A-Z0-9]+(?:[-_][A-Z0-9.]+)+)(?![A-Z0-9])",
    re.I,
)


def _viewer_rect(page: fitz.Page, box) -> fitz.Rect:
    x, y, width, height = box
    page_height = float(page.rect.height)
    return fitz.Rect(x, page_height - (y + height), x + width, page_height - y)


def _rect_text(page: fitz.Page, box) -> str:
    words = page.get_text("words", clip=_viewer_rect(page, box))
    words.sort(key=lambda w: (w[1], w[0]))
    return " ".join(w[4].strip() for w in words if w[4].strip()).strip()


def _read_coordinate_fields(path=None, document=None):
    projects = []
    units = []
    owns_document = document is None
    doc = document if document is not None else fitz.open(str(Path(path)))
    try:
        for page_number, page in enumerate(doc, 1):
            project_value = _rect_text(page, _PROJECT_BOX)
            if project_value:
                normalized = normalize_project_name(project_value)
                if normalized:
                    projects.append(
                        ProjectCandidate(
                            project_value,
                            normalized,
                            "project_coordinates",
                            page_number,
                            "HIGH",
                        )
                    )

            unit_value = _rect_text(page, _UNIT_REFERENCE_BOX)
            match = _EQUIPMENT_RE.search(unit_value)
            if match:
                raw = match.group(1).strip(" .,:;)]}")
                normalized = normalize_equipment_id(raw)
                if normalized:
                    units.append(
                        EquipmentOccurrence(
                            raw,
                            normalized,
                            page_number,
                            "unit_reference_coordinates",
                        )
                    )
    finally:
        if owns_document:
            doc.close()
    return projects, units


def discover_pdf1_project(pages, path=None, document=None):
    """PDF1 Project is read ONLY from the fixed Project coordinate box."""
    if document is None and not path:
        return ProjectDiscovery(None, None, None, None, "REVIEW", ())
    projects, _ = _read_coordinate_fields(path, document)
    seen = set()
    candidates = []
    for item in projects:
        if item.normalized in seen:
            continue
        seen.add(item.normalized)
        candidates.append(item)
    if not candidates:
        return ProjectDiscovery(None, None, None, None, "REVIEW", ())
    item = candidates[0]
    return ProjectDiscovery(
        item.value,
        item.normalized,
        item.source,
        item.page,
        item.confidence,
        tuple(candidates),
    )


def discover_pdf1_unit_reference(pages, path=None, document=None):
    """PDF1 Unit Reference is read ONLY from the fixed Unit Reference coordinate box."""
    if document is None and not path:
        return AHUDiscovery(())
    _, units = _read_coordinate_fields(path, document)
    seen = set()
    candidates = []
    for item in units:
        key = (item.normalized, item.page)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(item)
    return AHUDiscovery(tuple(candidates))


__all__ = ["discover_pdf1_project", "discover_pdf1_unit_reference"]
