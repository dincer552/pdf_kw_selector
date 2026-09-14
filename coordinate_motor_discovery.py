"""Coordinate-aware discovery for PDF fan sections and rated power cells."""
from __future__ import annotations

import re
from pathlib import Path

import fitz

from pdf_kw_selector import normalize_power
from stage1_page_discovery import MotorPowerResult, extract_equipment_id, extract_model_brand

_NUM_RE = re.compile(r"^\d+(?:[.,]\d+)?$")
_QTY_RE = re.compile(r"^\(\s*(\d+)\s*[x×]\s*(\d+)\s*\)$", re.I)


def _same_line(a, b, tolerance=2.5):
    return abs(((a[1] + a[3]) / 2) - ((b[1] + b[3]) / 2)) <= tolerance


def _words_on_lines(words):
    lines = {}
    for word in words:
        lines.setdefault((word[6], word[7]), []).append(word)
    for key in lines:
        lines[key].sort(key=lambda w: w[0])
    return list(lines.values())


def _header_direction(line):
    texts = [w[4].strip().lower() for w in line]
    for i in range(len(texts) - 1):
        if texts[i] in {"supply", "exhaust", "return"} and texts[i + 1] == "air":
            # This must be a component header, not an arbitrary mention elsewhere.
            prior = texts[:i]
            if "plug" in prior and "fan" in prior:
                return texts[i]
    return None


def _rated_value(line):
    for i in range(len(line) - 1):
        if line[i][4].strip().lower() != "rated":
            continue
        if line[i + 1][4].strip().lower() != "power":
            continue
        label_end = line[i + 1][2]
        value_index = None
        for j in range(i + 2, len(line)):
            token = line[j][4].strip()
            if line[j][0] < label_end:
                continue
            if _NUM_RE.fullmatch(token):
                value_index = j
                break
        if value_index is None:
            continue
        raw = line[value_index][4]
        quantity = None
        if value_index + 2 < len(line) and line[value_index + 1][4].strip().lower() in {"x", "×"}:
            qm = _QTY_RE.fullmatch(line[value_index + 2][4].strip())
            if qm:
                quantity = f"{qm.group(1)}x{qm.group(2)}"
        return raw, quantity, line[i][0], line[i + 1][2], line[value_index][0], line[value_index][2]
    return None


def discover_coordinate_motor_powers(path: str | Path):
    """Return coordinate-confirmed fan motor powers keyed by PDF page number."""
    result = {}
    doc = fitz.open(str(path))
    try:
        for page_number, page in enumerate(doc, 1):
            words = page.get_text("words")
            lines = _words_on_lines(words)
            direction = None
            rated = None
            for line in lines:
                d = _header_direction(line)
                if d:
                    direction = d
                r = _rated_value(line)
                if r:
                    rated = r
            if not direction or not rated:
                continue
            raw, quantity, label_x0, label_x1, value_x0, value_x1 = rated
            page_text = page.get_text("text") or ""
            role_map = {
                "supply": ("Vantilatör", "supply_fan"),
                "exhaust": ("Aspiratör", "exhaust_fan"),
                "return": ("Aspiratör", "return_fan"),
            }
            component_type, component_role = role_map[direction]
            result.setdefault(page_number, []).append(
                MotorPowerResult(
                    page_number=page_number,
                    value_kw=normalize_power(float(raw.replace(",", ".")), "kw"),
                    raw_value=raw,
                    quantity=quantity,
                    field="fan_motor_power",
                    confidence="high",
                    source_text=f"Rated Power [kW] {raw} x ({quantity})" if quantity else f"Rated Power [kW] {raw}",
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
