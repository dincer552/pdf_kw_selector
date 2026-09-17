"""Launch the integrated C# TestKontrolProg application."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox, ttk


INTEGRATED_TEST_CONTROL = "dincer552/umut-test-pro@d5950497f49a43a1fe0a7a34e79b4ee316b777ac"


def _candidate_paths() -> list[Path]:
    candidates: list[Path] = []
    if getattr(sys, "_MEIPASS", None):
        candidates.append(Path(sys._MEIPASS) / "TestKontrolProg" / "TestKontrolProg.exe")
    executable_dir = Path(sys.executable).resolve().parent
    candidates.append(executable_dir / "TestKontrolProg" / "TestKontrolProg.exe")
    source_root = Path(__file__).resolve().parent
    candidates.append(source_root / "TestKontrolProg" / "bin" / "Release" / "TestKontrolProg.exe")
    candidates.append(source_root / "TestKontrolProg" / "TestKontrolProg.exe")
    return candidates


def find_test_control_exe() -> Path | None:
    for candidate in _candidate_paths():
        if candidate.is_file():
            return candidate
    return None


def open_test_control(parent: tk.Misc | None = None) -> None:
    exe = find_test_control_exe()
    if exe is None:
        messagebox.showerror(
            "TEST KONTROL",
            "Test Kontrol uygulaması bulunamadı.\n\n"
            "Windows paketini kullanıyorsanız uygulama build'e dahil edilmemiş olabilir.\n"
            "GitHub Actions ile yeni Windows EXE oluşturun.",
            parent=parent,
        )
        return

    try:
        subprocess.Popen([str(exe)], cwd=str(exe.parent), close_fds=True)
    except OSError as exc:
        messagebox.showerror(
            "TEST KONTROL",
            f"Test Kontrol başlatılamadı:\n{exc}",
            parent=parent,
        )


def install_test_control_button(app: tk.Misc) -> None:
    """Add TEST KONTROL to the upper-right of the existing PDF Check header."""
    header = getattr(app, "_header_frame", None)
    if header is None:
        for child in app.winfo_children():
            try:
                if child.winfo_class() == "TFrame" and str(child.cget("style")) == "White.TFrame":
                    header = child
                    break
            except tk.TclError:
                continue

    if header is None:
        return

    button = ttk.Button(
        header,
        text="TEST KONTROL",
        command=lambda: open_test_control(app),
        style="Primary.TButton",
    )
    button.pack(side="right", padx=(6, 0))
    app.test_control_button = button
