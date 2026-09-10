"""Human-readable identity hints used before risky Project/AHU matching."""
from __future__ import annotations

from pathlib import Path
import re

from pypdf import PdfReader

from app_logger import debug, exception


_ORDER_PATTERNS = (
    re.compile(r"\b(?:order\s+(?:number|no)|sipari[sş]\s*(?:no|numaras[ıi]))\s*[:#=]?\s*([A-Z0-9][A-Z0-9./_-]{2,})", re.I),
    re.compile(r"\b(?:order|siparis)\s*[:#=]\s*([A-Z0-9][A-Z0-9./_-]{2,})", re.I),
)


def extract_identity_hints(path: str | Path) -> dict:
    """Extract order/project-like identifiers for a confirmation dialog.

    These hints never decide a match on their own; they are evidence shown to
    the user and recorded in logs so the final match remains user-approved.
    """
    try:
        reader = PdfReader(str(path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages[:4])
        orders: list[str] = []
        for pattern in _ORDER_PATTERNS:
            for match in pattern.finditer(text):
                value = match.group(1).strip(" .,:;)]}")
                if value and value not in orders:
                    orders.append(value)
        return {"path": str(path), "order_numbers": orders}
    except Exception as exc:
        exception("Kimlik ipucu keşfi başarısız", exc, path=str(path))
        return {"path": str(path), "order_numbers": []}


def shared_order_numbers(left_paths: list[str], right_paths: list[str]) -> list[str]:
    left = set()
    right = set()
    for path in left_paths:
        left.update(extract_identity_hints(path)["order_numbers"])
    for path in right_paths:
        right.update(extract_identity_hints(path)["order_numbers"])
    shared = sorted(left & right)
    debug("Ortak sipariş numarası ipuçları", left=sorted(left), right=sorted(right), shared=shared)
    return shared
