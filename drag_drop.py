"""Drag-and-drop support for the PDF input boxes."""
from __future__ import annotations

from pathlib import Path

from app_logger import exception, info, warning

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:  # pragma: no cover
    DND_FILES = None
    TkinterDnD = None


def parse_drop_data(tk_root, data: str) -> list[str]:
    """Parse TkDnD's Tcl-list payload into filesystem paths."""
    if not data:
        return []
    try:
        return [str(Path(path)) for path in tk_root.tk.splitlist(data) if str(path).strip()]
    except Exception as exc:
        exception("Sürükle-bırak yolu ayrıştırma hatası", exc, data=data)
        raise


def install_pdf_drop_targets(app, pdf1_widget, pdf2_widget) -> bool:
    """Register both PDF input boxes as native TkDnD drop targets."""
    if DND_FILES is None or TkinterDnD is None:
        warning("Sürükle-bırak devre dışı: tkinterdnd2 bulunamadı")
        return False
    try:
        TkinterDnD.require(app)
    except Exception as exc:
        exception("TkDnD root entegrasyonu başarısız", exc)
        return False

    def bind(widget, target: str) -> None:
        widget.drop_target_register(DND_FILES)
        widget.dnd_bind("<<Drop>>", lambda event, target=target: _on_drop(app, event, target))

    bind(pdf1_widget, "PDF1")
    bind(pdf2_widget, "PDF2")
    info("PDF kutularında sürükle-bırak etkin", targets=["PDF1", "PDF2"])
    return True


def _on_drop(app, event, target: str):
    try:
        paths = parse_drop_data(app, event.data)
        if not paths:
            warning("Boş sürükle-bırak olayı alındı", target=target)
            return
        info("PDF kutusuna sürükle-bırak alındı", target=target, count=len(paths), paths=paths)
        app._merge_inputs(target, paths)
    except Exception as exc:
        exception("PDF sürükle-bırak işleme hatası", exc, target=target, data=getattr(event, "data", None))
