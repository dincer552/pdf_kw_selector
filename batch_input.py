"""Multi-PDF input discovery for batch processing.

This module deliberately does not analyze PDF contents. It only builds a
stable, duplicate-free input manifest from selected files and folders so the
later project/AHU matching stages can consume the same representation.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path

from app_logger import debug, exception, info, warning


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
    Every skipped/invalid input is logged so an empty list is diagnosable.
    """
    try:
        result: list[PdfInput] = []
        seen: set[str] = set()
        info("PDF giriş keşfi başladı", input_count=len(paths), recursive=recursive)

        for raw in paths:
            path = Path(raw).expanduser()
            if not path.exists():
                warning("PDF giriş yolu bulunamadı", path=str(path))
                continue
            if not path.is_file() and not path.is_dir():
                warning("PDF giriş yolu dosya veya klasör değil", path=str(path))
                continue

            candidates = [path] if path.is_file() else (
                sorted(path.rglob("*.pdf"), key=lambda p: str(p).lower())
                if recursive
                else sorted(path.glob("*.pdf"), key=lambda p: str(p).lower())
            )
            debug("PDF adayları bulundu", input_path=str(path), candidate_count=len(candidates))

            if path.is_file() and path.suffix.lower() != ".pdf":
                warning("Seçilen dosya PDF değil, atlandı", path=str(path), suffix=path.suffix)

            for candidate in candidates:
                try:
                    if not candidate.is_file() or candidate.suffix.lower() != ".pdf":
                        warning("PDF olmayan aday atlandı", path=str(candidate))
                        continue
                    absolute = candidate.resolve()
                    key = str(absolute).casefold()
                    if key in seen:
                        debug("Tekrarlanan PDF giriş yolu atlandı", path=str(absolute))
                        continue
                    size_bytes = absolute.stat().st_size
                    if size_bytes <= 0:
                        warning("Boş PDF dosyası atlandı", path=str(absolute), size_bytes=size_bytes)
                        continue
                    seen.add(key)
                    item = PdfInput(
                        path=str(absolute),
                        filename=absolute.name,
                        source="file" if path.is_file() else "folder",
                        size_bytes=size_bytes,
                    )
                    result.append(item)
                    debug("PDF girişine eklendi", **item.to_dict())
                except Exception as exc:
                    exception("PDF adayı işlenemedi", exc, path=str(candidate))

        info("PDF giriş keşfi tamamlandı", input_count=len(paths), pdf_count=len(result), paths=[x.path for x in result])
        if not result:
            warning("PDF giriş keşfi sıfır sonuç verdi", inputs=[str(x) for x in paths])
        return result
    except Exception as exc:
        exception("PDF giriş keşfi hesaplama hatası", exc, input_count=len(paths), inputs=[str(x) for x in paths])
        raise
