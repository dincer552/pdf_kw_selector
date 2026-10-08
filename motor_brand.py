"""Motor-brand normalization shared by PDF discovery and comparison."""
from __future__ import annotations

import re


def normalize_motor_brand(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = " ".join(str(value).split()).strip()
    compact = re.sub(r"[^a-z0-9]", "", cleaned.casefold())
    if compact == "ebmpapst":
        return "EBM-Papst"
    if compact == "ziehlabegg":
        return "Ziehl-Abegg"
    if compact == "standard":
        return "Standard"
    return cleaned


def is_special_motor_brand(value: str | None) -> bool:
    return normalize_motor_brand(value) in {"EBM-Papst", "Ziehl-Abegg"}
