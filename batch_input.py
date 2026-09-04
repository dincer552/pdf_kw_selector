"""Multi-PDF input discovery for batch processing.

This module deliberately does not analyze PDF contents. It only builds a
stable, duplicate-free input manifest from selected files and folders so the
later project/AHU matching stages can consume the same representation.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass(frozen=True)
class PdfInput:
    path: str
    filename: str
    source: str
    size_bytes: int

    def to_dict(self) -> dict:
        return asdict(self)


def discover_pdfs(
    paths: list[str | Path],
    *,
    recursive: bool = True,
) -> list[PdfInput]:
    """Collect PDF files from individual files and directories.

    Directories are scanned recursively by default. Files are normalized to
    absolute paths and duplicate paths are removed while preserving order.
    Non-PDF files and missing paths are ignored.
    """
    result: list[PdfInput] = []
    seen: set[str] = set()

    for raw in paths:
        path = Path(raw).expanduser()
        if not path.exists():
            continue

        candidates = [path] if path.is_file() else (
            sorted(path.rglob("*.pdf"), key=lambda p: str(p).lower())
            if recursive
            else sorted(path.glob("*.pdf"), key=lambda p: str(p).lower())
        )

        for candidate in candidates:
            if not candidate.is_file() or candidate.suffix.lower() != ".pdf":
                continue
            absolute = candidate.resolve()
            key = str(absolute).casefold()
            if key in seen:
                continue
            seen.add(key)
            result.append(
                PdfInput(
                    path=str(absolute),
                    filename=absolute.name,
                    source="file" if path.is_file() else "folder",
                    size_bytes=absolute.stat().st_size,
                )
            )

    return result
