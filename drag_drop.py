"""Drag-and-drop support for the PDF input boxes."""
from __future__ import annotations

from pathlib import Path

from app_logger import exception, info, warning

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:  # pragma: no cover
    DND_FILES = None
    TkinterDnD = None

_drag_depth = {"PDF1": 0, "PDF2": 0}
_leave_jobs = {"PDF1": None, "PDF2": None}


def parse_drop_data(tk_root, data: str) -> list[str]:
    """Parse TkDnD's Tcl-list payload into filesystem paths."""
    if not data:
        return []
    try:
        return [str(Path(path)) for path in tk_root.tk.splitlist(data) if str(path).strip()]
    except Exception as exc:
        exception("Sürükle-bırak yolu ayrıştırma hatası", exc, data=data)
        raise


def register_drop_target_tree(app, widget, target: str) -> int:
    """Register widget and all its children as drop targets with drag enter/leave tracking."""
    if DND_FILES is None or TkinterDnD is None:
        return 0

    def _bind(w):
        try:
            if not getattr(w, "_drop_registered", False):
                w.drop_target_register(DND_FILES)
                w._drop_registered = True
            w.dnd_bind("<<DropEnter>>", lambda event, t=target: _on_drag_enter(app, event, t))
            w.dnd_bind("<<DropPosition>>", lambda event, t=target: _on_drag_position(app, event, t))
            w.dnd_bind("<<DropLeave>>", lambda event, t=target: _on_drag_leave(app, event, t))
            w.dnd_bind("<<Drop>>", lambda event, t=target: _on_drop(app, event, t))
        except Exception as exc:
            pass

    count = 0
    _bind(widget)
    count += 1
    try:
        for child in widget.winfo_children():
            count += register_drop_target_tree(app, child, target)
    except Exception:
        pass
    return count


def install_pdf_drop_targets(app, pdf1_widget, pdf2_widget) -> bool:
    """Register both PDF input boxes, including all child controls, as drop targets."""
    if DND_FILES is None or TkinterDnD is None:
        warning("Sürükle-bırak devre dışı: tkinterdnd2 bulunamadı")
        return False
    try:
        TkinterDnD.require(app)
    except Exception as exc:
        exception("TkDnD root entegrasyonu başarısız", exc)
        return False

    pdf1_count = register_drop_target_tree(app, pdf1_widget, "PDF1")
    pdf2_count = register_drop_target_tree(app, pdf2_widget, "PDF2")

    # Expose registration hook for dynamically added file card widgets
    app._register_drop_target = lambda w, t: register_drop_target_tree(app, w, t)

    info(
        "PDF kutularında sürükle-bırak etkin",
        targets=["PDF1", "PDF2"],
        pdf1_widget_count=pdf1_count,
        pdf2_widget_count=pdf2_count,
    )
    return True


def _on_drag_enter(app, event, target: str):
    _record_drag_enter(app, target)
    return getattr(event, "action", "copy")


def _on_drag_position(app, event, target: str):
    _record_drag_enter(app, target)
    return getattr(event, "action", "copy")


def _on_drag_leave(app, event, target: str):
    _record_drag_leave(app, target)
    return getattr(event, "action", "copy")


def _record_drag_enter(app, target: str):
    global _drag_depth, _leave_jobs
    job = _leave_jobs.get(target)
    if job is not None:
        try:
            app.after_cancel(job)
        except Exception:
            pass
        _leave_jobs[target] = None

    _drag_depth[target] = _drag_depth.get(target, 0) + 1

    # Ensure other box is deactivated immediately for separated activation
    other = "PDF2" if target == "PDF1" else "PDF1"
    if _drag_depth.get(other, 0) > 0:
        _drag_depth[other] = 0
        set_fn = getattr(app, "set_drag_active", None)
        if set_fn:
            set_fn(other, False)

    set_fn = getattr(app, "set_drag_active", None)
    if set_fn:
        set_fn(target, True)


def _record_drag_leave(app, target: str):
    global _drag_depth, _leave_jobs
    _drag_depth[target] = max(0, _drag_depth.get(target, 0) - 1)
    if _drag_depth[target] == 0:
        job = _leave_jobs.get(target)
        if job is not None:
            try:
                app.after_cancel(job)
            except Exception:
                pass

        def _check():
            _leave_jobs[target] = None
            if _drag_depth.get(target, 0) == 0:
                set_fn = getattr(app, "set_drag_active", None)
                if set_fn:
                    set_fn(target, False)

        try:
            _leave_jobs[target] = app.after(80, _check)
        except Exception:
            _check()


def _on_drop(app, event, target: str):
    global _drag_depth, _leave_jobs
    _drag_depth[target] = 0
    job = _leave_jobs.get(target)
    if job is not None:
        try:
            app.after_cancel(job)
        except Exception:
            pass
        _leave_jobs[target] = None

    set_fn = getattr(app, "set_drag_active", None)
    if set_fn:
        set_fn(target, False)

    try:
        paths = parse_drop_data(app, event.data)
        if not paths:
            warning("Boş sürükle-bırak olayı alındı", target=target)
            return
        info("PDF kutusuna sürükle-bırak alındı", target=target, count=len(paths), paths=paths)
        app._merge_inputs(target, paths)
    except Exception as exc:
        exception("PDF sürükle-bırak işleme hatası", exc, target=target, data=getattr(event, "data", None))

