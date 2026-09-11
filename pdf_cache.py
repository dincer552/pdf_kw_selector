"""Process-local PDF reader cache shared by discovery and comparison stages.

A selected PDF is parsed once and the same PdfReader instance is reused by
project, equipment, motor and confirmation discovery. This avoids reopening
and re-extracting every page several times during one analysis.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pypdf import PdfReader as _PdfReader


@lru_cache(maxsize=128)
def PdfReader(path: str | Path):
    """Return a cached PdfReader for the normalized file path."""
    normalized = str(Path(path).expanduser().resolve())
    return _PdfReader(normalized)


def clear_pdf_cache() -> None:
    """Drop cached readers, useful after a PDF is replaced during a session."""
    PdfReader.cache_clear()
