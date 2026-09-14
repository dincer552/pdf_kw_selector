from __future__ import annotations

from pathlib import Path
import fitz

from ahu_matching import AHUDiscovery, EquipmentOccurrence, normalize_equipment_id
from project_discovery import ProjectCandidate, ProjectDiscovery, normalize_project_name

_PROJECT_BOX = (256.0, 763.0, 115.0, 18.0)
# PDF1 AHU / Unit Reference is now read ONLY from page 2 using this viewer coordinate.
_UNIT_REFERENCE_BOX = (253.0, 751.0, 117.0, 17.0)


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
        # PDF1 Project: ONLY page 1 and ONLY the fixed Project coordinate box.
        if len(doc) > 0:
            page = doc[0]
            project_value = _rect_text(page, _PROJECT_BOX)
            if project_value:
                normalized = normalize_project_name(project_value)
                if normalized:
                    projects.append(ProjectCandidate(project_value, normalized, "project_coordinates", 1, "HIGH"))

        # PDF1 AHU / Unit Reference: ONLY page 2 and ONLY the fixed coordinate box.
        # Whatever text is physically inside this box is the AHU name. No format,
        # regex, whitelist, filename, or other-page fallback is used.
        if len(doc) > 1:
            page = doc[1]
            unit_value = _rect_text(page, _UNIT_REFERENCE_BOX)
            if unit_value:
                normalized = normalize_equipment_id(unit_value)
                units.append(EquipmentOccurrence(unit_value, normalized or unit_value, 2, "unit_reference_coordinates"))
    finally:
        if owns_document:
            doc.close()
    return projects, units


def discover_pdf1_project(pages, path=None, document=None):
    """PDF1 Project is read ONLY from the fixed coordinate box on page 1."""
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
    return ProjectDiscovery(item.value, item.normalized, item.source, item.page, item.confidence, tuple(candidates))


def discover_pdf1_unit_reference(pages, path=None, document=None):
    """PDF1 Unit Reference is read ONLY from the fixed coordinate box on page 2."""
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
