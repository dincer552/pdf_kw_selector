"""Strict coordinate-based PDF1 fan motor discovery."""
from __future__ import annotations

import re
from pathlib import Path

import fitz

from pdf_kw_selector import normalize_power
from stage1_page_discovery import MotorPowerResult, extract_equipment_id, extract_model_brand

# PDF1 Plug fan template coordinates supplied from the real selection PDF.
# Direction cell: x=197, y=695, w=68, h=15
# Rated Power cell: x=429, y=634, w=131, h=13
_DIRECTION_RECT = (197.0, 695.0, 265.0, 710.0)
_RATED_POWER_RECT = (429.0, 634.0, 560.0, 647.0)
_QTY_RE = re.compile(r"\(\s*(\d+)\s*[x×]\s*(\d+)\s*\)", re.I)
_POWER_QTY_RE = re.compile(r"^\s*([0-9]+(?:[.,][0-9]+)?)\s*[x×]\s*\(\s*(\d+)\s*[x×]\s*(\d+)\s*\)\s*$", re.I)
_POWER_ONLY_RE = re.compile(r"^\s*([0-9]+(?:[.,][0-9]+)?)\s*$")


def _rect_text(page: fitz.Page, rect_values) -> str:
    """Return text physically rendered inside the exact supplied PDF rectangle."""
    rect = fitz.Rect(*rect_values)
    words = page.get_text("words", clip=rect)
    words.sort(key=lambda w: (w[1], w[0]))
    return " ".join(w[4].strip() for w in words if w[4].strip()).strip()


def _is_plug_fan_page(page: fitz.Page) -> bool:
    # The page is first identified as a Plug fan page. All fan direction and
    # rated-power decisions are then made only from the two fixed rectangles.
    text = page.get_text("text") or ""
    return bool(re.search(r"\bplug\s+fan\b", text, re.I))


def _parse_rated_power(raw: str):
    compact = re.sub(r"\s+", " ", raw.strip())
    m = _POWER_QTY_RE.match(compact)
    if m:
        value = normalize_power(float(m.group(1).replace(",", ".")), "kw")
        quantity = f"{m.group(2)}x{m.group(3)}"
        return value, m.group(1), quantity
    m = _POWER_ONLY_RE.match(compact)
    if m:
        value = normalize_power(float(m.group(1).replace(",", ".")), "kw")
        return value, m.group(1), None
    # Some PDFs split the quantity into separate word objects; reconstruct it.
    number = re.search(r"([0-9]+(?:[.,][0-9]+)?)", compact)
    qty = _QTY_RE.search(compact)
    if number:
        value = normalize_power(float(number.group(1).replace(",", ".")), "kw")
        quantity = f"{qty.group(1)}x{qty.group(2)}" if qty else None
        return value, number.group(1), quantity
    return None


def discover_coordinate_motor_powers(path: str | Path):
    """Discover PDF1 fan motors using only the fixed template rectangles."""
    result = {}
    doc = fitz.open(str(path))
    try:
        for page_number, page in enumerate(doc, 1):
            if not _is_plug_fan_page(page):
                continue

            direction = re.sub(r"\s+", " ", _rect_text(page, _DIRECTION_RECT)).strip().casefold()
            if direction not in {"supply air", "exhaust air"}:
                continue

            rated_raw = _rect_text(page, _RATED_POWER_RECT)
            parsed = _parse_rated_power(rated_raw)
            if not parsed:
                continue
            value_kw, raw_value, quantity = parsed

            page_text = page.get_text("text") or ""
            if direction == "supply air":
                component_type, component_role = "Vantilatör", "supply_fan"
            else:
                component_type, component_role = "Aspiratör", "exhaust_fan"

            result.setdefault(page_number, []).append(
                MotorPowerResult(
                    page_number=page_number,
                    value_kw=value_kw,
                    raw_value=raw_value,
                    quantity=quantity,
                    field="fan_motor_power_coordinates",
                    confidence="high",
                    source_text=f"{direction.title()} | {rated_raw}",
                    component_type=component_type,
                    component_role=component_role,
                    equipment_id=extract_equipment_id(page_text),
                    model_brand=extract_model_brand(page_text),
                )
            )
    finally:
        doc.close()
    return result


__all__ = ["discover_coordinate_motor_powers"]
