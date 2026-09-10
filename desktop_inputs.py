"""Backward-compatible desktop input API.

The desktop GUI historically imported PdfInput/discover_pdfs from this module.
The canonical implementation now lives in batch_input; re-export it here so
packaged desktop builds and older imports remain compatible.
"""
from batch_input import PdfInput, discover_pdfs

__all__ = ["PdfInput", "discover_pdfs"]
