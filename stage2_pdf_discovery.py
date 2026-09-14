"""PDF2 motor power discovery from explicit Motor Connections coordinates."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

import fitz
from motor_database import MotorRecord, expand_motor_group

# PDF2 coordinates are supplied in the PDF viewer coordinate system (origin bottom-left).
# PyMuPDF uses origin top-left, so Y is converted before clipping.
_MOTOR_KW_BOX = (23.0, 524.0, 69.0, 45.0)

_CONNECTION_LABELS = (
    ("Supply Motor Connections-1", "Vantilatör", "supply_fan"),
    ("Supply Motor Connections-2", "Vantilatör", "supply_fan"),
    ("Return Motor Connections-1", "Aspiratör", "return_fan"),
    ("Return Motor Connections-2", "Aspiratör", "return_fan"),
)

_KW_RE = re.compile(r"(?P<value>\d+(?:[.,]\d+)?)\s*kW\b", re.I)


@dataclass(frozen=True)
class PDF2MotorResult:
    equipment_id: str
    component_type: str
    component_role: str
    value_kw: float
    quantity: str
    source_page: int
    source_text: str
    confidence: str = "high"

    def to_dict(self) -> dict:
        return asdict(self)


def _viewer_rect(page: fitz.Page, box: tuple[float, float, float, float]) -> fitz.Rect:
    x, y, width, height = box
    page_height = float(page.rect.height)
    return fitz.Rect(x, page_height - (y + height), x + width, page_height - y)


def _coordinate_text(page: fitz.Page) -> str:
    words = page.get_text("words", clip=_viewer_rect(page, _MOTOR_KW_BOX))
    words.sort(key=lambda word: (word[1], word[0]))
    return " ".join(word[4].strip() for word in words if word[4].strip()).strip()


def _has_connection_label(page: fitz.Page, label: str) -> bool:
    text = page.get_text("text") or ""
    pattern = re.escape(label).replace(r"\-", r"\s*[-–—]\s*")
    return bool(re.search(pattern, text, re.I))


def discover_coordinate_pdf2_motor_powers(
    document: fitz.Document,
    equipment_id: str | None,
) -> tuple[PDF2MotorResult, ...]:
    """Find each requested connection label, then read kW ONLY from its fixed coordinate."""
    if not document or not equipment_id:
        return ()

    results: list[PDF2MotorResult] = []
    for label, component_type, component_role in _CONNECTION_LABELS:
        for page_number, page in enumerate(document, 1):
            if not _has_connection_label(page, label):
                continue

            coordinate_text = _coordinate_text(page)
            match = _KW_RE.search(coordinate_text)
            if not match:
                # Label was found, but the fixed coordinate contains no kW.
                # Do not search anywhere else on the page/document.
                continue

            value = float(match.group("value").replace(",", "."))
            results.append(
                PDF2MotorResult(
                    equipment_id=equipment_id,
                    component_type=component_type,
                    component_role=component_role,
                    value_kw=value,
                    quantity="1x1",
                    source_page=page_number,
                    source_text=coordinate_text,
                    confidence="high",
                )
            )
            break

    return tuple(results)


def build_pdf2_motor_records(result: PDF2MotorResult, start_index: int = 1) -> list[MotorRecord]:
    return expand_motor_group(
        equipment_id=result.equipment_id,
        equipment_type="AHU",
        component_type=result.component_type,
        group=result.quantity,
        power_kw=result.value_kw,
        source_page=result.source_page,
        start_index=start_index,
    )


__all__ = ["PDF2MotorResult", "discover_coordinate_pdf2_motor_powers", "build_pdf2_motor_records"]
