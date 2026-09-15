"""Desktop GUI for PDF kW Selector."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from app_logger import exception, info, read_log, clear_log, log_file, log_directory, startup
from batch_analysis import analyze_batch
from desktop_inputs import PdfInput, discover_pdfs
from drag_drop import install_pdf_drop_targets
from pdf_master_scan import scan_pdfs
from updater import check_for_update, download_update, restart_with_update
from ahu_matching import normalize_equipment_id
from build_info import BUILD_SHA, BUILD_VERSION

VERSION = BUILD_VERSION
UPDATE_CHECK_INTERVAL_MS = 15 * 60 * 1000


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"PDF kW Selector {VERSION} — Batch Motor Analysis")
        self.geometry("1300x820")
        self.minsize(1100, 700)
        self.pdf1_inputs: list[PdfInput] = []
        self.pdf2_inputs: list[PdfInput] = []
        self.analysis = None
        self._analysis_running = False
        self._update_check_running = False
        self._available_update = None
        self._progress_lock = threading.Lock()
        self._progress_pending = False
        self._progress_latest = None
        self._init_modern_theme()
        self._build_ui()
        install_pdf_drop_targets(self, self.pdf1_box, self.pdf2_box)
        self.after(5000, self._schedule_update_check)

    def _init_modern_theme(self):
        try:
            self.configure(bg="#f0f4f9")
        except Exception:
            pass
        style = ttk.Style(self)
        try:
            if "clam" in style.theme_names():
                style.theme_use("clam")
        except Exception:
            pass

        bg_canvas = "#f0f4f9"
        card_bg = "#ffffff"
        border_color = "#e2e8f0"
        primary_color = "#1a56db"
        text_dark = "#0f172a"
        text_muted = "#64748b"

        style.configure(".", background=bg_canvas, foreground=text_dark, font=("Segoe UI", 9))
        style.configure("TFrame", background=bg_canvas)
        style.configure("White.TFrame", background=card_bg)
        style.configure("TLabel", background=bg_canvas, foreground=text_dark, font=("Segoe UI", 9))
        style.configure("White.TLabel", background=card_bg, foreground=text_dark, font=("Segoe UI", 9))
        style.configure("Muted.TLabel", background=card_bg, foreground=text_muted, font=("Segoe UI", 8))
        style.configure("Title.TLabel", background=card_bg, foreground=text_dark, font=("Segoe UI", 13, "bold"))
        style.configure("Badge.TLabel", background="#eff6ff", foreground=primary_color, font=("Segoe UI", 8, "bold"), padding=(6, 2))

        # Primary Button (ANALİZ BAŞLA)
        style.configure("Primary.TButton", background=primary_color, foreground="#ffffff", font=("Segoe UI", 9, "bold"), borderwidth=0, padding=(12, 6))
        style.map("Primary.TButton",
            background=[("active", "#1e40af"), ("disabled", "#cbd5e1")],
            foreground=[("disabled", "#94a3b8")]
        )

        # Secondary Button
        style.configure("Secondary.TButton", background="#ffffff", foreground="#334155", font=("Segoe UI", 9), borderwidth=1, bordercolor="#cbd5e1", padding=(8, 4))
        style.map("Secondary.TButton",
            background=[("active", "#f1f5f9"), ("disabled", "#f8fafc")],
            bordercolor=[("active", "#94a3b8")]
        )

        # Tabs / Notebook
        style.configure("TNotebook", background=bg_canvas, borderwidth=0)
        style.configure("TNotebook.Tab", background="#e2e8f0", foreground=text_muted, font=("Segoe UI", 9, "bold"), padding=(14, 7), borderwidth=0)
        style.map("TNotebook.Tab",
            background=[("selected", card_bg), ("active", "#e2e8f0")],
            foreground=[("selected", text_dark), ("active", text_dark)]
        )

        # Treeview (Tables)
        style.configure("Treeview", background="#ffffff", foreground=text_dark, fieldbackground="#ffffff", rowheight=26, font=("Segoe UI", 9), borderwidth=1, bordercolor=border_color)
        style.configure("Treeview.Heading", background="#f8fafc", foreground=text_dark, font=("Segoe UI", 9, "bold"), borderwidth=1, bordercolor=border_color, padding=6)
        style.map("Treeview.Heading", background=[("active", "#e2e8f0")])

        # LabelFrame
        style.configure("TLabelframe", background=card_bg, bordercolor=border_color, borderwidth=1, relief="solid")
        style.configure("TLabelframe.Label", background=card_bg, foreground=text_dark, font=("Segoe UI", 9, "bold"))
        style.configure("Card.TLabelframe", background=card_bg, bordercolor=border_color, borderwidth=1, relief="solid")
        style.configure("Card.TLabelframe.Label", background=card_bg, foreground=text_dark, font=("Segoe UI", 9, "bold"))

    def _build_ui(self):
        # Modern Header
        header = ttk.Frame(self, style="White.TFrame", padding=(12, 8))
        header.pack(fill="x", pady=(0, 8))
        
        kw_box = tk.Label(header, text="kW", bg="#1a56db", fg="#ffffff", font=("Segoe UI", 11, "bold"), width=3, height=1)
        kw_box.pack(side="left", padx=(0, 10))
        
        title_box = ttk.Frame(header, style="White.TFrame")
        title_box.pack(side="left")
        ttk.Label(title_box, text="PDF kW SELECTOR", style="Title.TLabel").pack(anchor="w")
        ttk.Label(title_box, text="Project → AHU → Motor Anma Gücü Karşılaştırma ve Doğrulama", style="Muted.TLabel").pack(anchor="w")

        self.update_check_button = ttk.Button(header, text="↻", width=3, command=self._manual_update_check, style="Secondary.TButton")
        self.update_check_button.pack(side="right", padx=(6, 0))
        ttk.Label(header, text=f"{VERSION}", style="Badge.TLabel").pack(side="right", padx=(0, 6))

        # PDF Drop / Selection Boxes
        boxes = ttk.Frame(self, padding=(10, 0))
        boxes.pack(fill="x")
        self.pdf1_label, self.pdf1_box = self._file_box(boxes, "Seçim Çıktısı (PDF1)", "PDF1")
        self.pdf2_label, self.pdf2_box = self._file_box(boxes, "Elektrik Projesi (PDF2)", "PDF2")
        self.pdf1_box.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.pdf2_box.pack(side="left", fill="x", expand=True, padx=(5, 0))

        # Notebook tabs
        tabs = ttk.Notebook(self)
        tabs.pack(fill="both", expand=True, padx=10, pady=(8, 0))
        self.tabs = tabs
        result_tab = ttk.Frame(tabs, style="White.TFrame")
        unmatched_tab = ttk.Frame(tabs, style="White.TFrame")
        log_tab = ttk.Frame(tabs, style="White.TFrame")
        tabs.add(result_tab, text="DANFOSS / MOTOR")
        tabs.add(unmatched_tab, text="EŞLEŞMEYEN PDF'LER (0)")
        tabs.add(log_tab, text=">_ LOGLAR")

        cols = ("Proje", "AHU", "Motor", "Seçim kW", "Elektrik P. kW", "Durum")
        self.tree = ttk.Treeview(result_tab, columns=cols, show="headings")
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)

        unmatched_cols = ("Taraf", "PDF", "Proje", "AHU", "Neden")
        self.unmatched_tree = ttk.Treeview(unmatched_tab, columns=unmatched_cols, show="headings")
        widths = {"Taraf": 90, "PDF": 420, "Proje": 300, "AHU": 260, "Neden": 260}
        for col in unmatched_cols:
            self.unmatched_tree.heading(col, text=col)
            self.unmatched_tree.column(col, width=widths[col], anchor="w")
        unmatched_scroll = ttk.Scrollbar(unmatched_tab, orient="vertical", command=self.unmatched_tree.yview)
        self.unmatched_tree.configure(yscrollcommand=unmatched_scroll.set)
        self.unmatched_tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        unmatched_scroll.pack(side="right", fill="y", padx=(0, 8), pady=8)

        detail_frame = ttk.LabelFrame(log_tab, text="Sonuç JSON / Teknik Detay", padding=6)
        detail_frame.pack(fill="both", expand=False, padx=8, pady=(8, 0))
        self.detail = tk.Text(detail_frame, height=6, wrap="none", bg="#f8fafc", fg="#0f172a", font=("Consolas", 9), relief="flat")
        self.detail.pack(fill="both", expand=True)
        self.detail.configure(state="disabled")

        self.update_progress = tk.DoubleVar(value=0)
        self.update_detail = tk.StringVar(value="Güncelleme hazır")
        style = ttk.Style(self)
        style.configure("Update.Horizontal.TProgressbar", troughcolor="#e2e8f0", background="#1a56db")
        progress = ttk.Frame(self, padding=(8, 0))
        self.update_panel = progress
        ttk.Label(progress, textvariable=self.update_detail, anchor="e").pack(side="right")
        self.update_bar = ttk.Progressbar(progress, style="Update.Horizontal.TProgressbar", variable=self.update_progress, maximum=100, length=360)
        self.update_bar.pack(side="right", padx=8)

        # Action Buttons bar
        buttons = ttk.Frame(self, padding=(10, 8))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="▶ ANALİZ BAŞLA", style="Primary.TButton", command=self.compare).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="↺ TEMİZLE", style="Secondary.TButton", command=self.clear_inputs).pack(side="left", padx=3)

        self.update_notice = ttk.Frame(buttons)
        self.update_notice.pack(side="right", padx=8)
        self.update_notice_label = ttk.Label(self.update_notice, text="Yeni sürüm mevcut", foreground="#16803d")
        self.update_notice_label.pack(side="left", padx=(0, 6))
        ttk.Button(self.update_notice, text="İNDİR", style="Secondary.TButton", command=self.download_available_update).pack(side="left")
        self.update_notice.pack_forget()

        self.status = ttk.Label(buttons, text="Hazır", anchor="e")
        self.status.pack(side="right")

        self.log_text = tk.Text(log_tab, wrap="none", bg="#f8fafc", fg="#0f172a", font=("Consolas", 9), relief="flat")
        self.log_text.pack(fill="both", expand=True, padx=8, pady=8)
        log_buttons = ttk.Frame(log_tab, padding=6)
        log_buttons.pack(fill="x")
        ttk.Button(log_buttons, text="JSON KAYDET", style="Secondary.TButton", command=self.save_json).pack(side="left", padx=3)
        ttk.Button(log_buttons, text="LOGLARI YENİLE", style="Secondary.TButton", command=self.refresh_logs).pack(side="left", padx=3)
        ttk.Button(log_buttons, text="LOG DOSYASINI AÇ", style="Secondary.TButton", command=self.open_log_file).pack(side="left", padx=3)
        ttk.Button(log_buttons, text="LOG KLASÖRÜNÜ AÇ", style="Secondary.TButton", command=self.open_log_directory).pack(side="left", padx=3)
        ttk.Button(log_buttons, text="LOGLARI TEMİZLE", style="Secondary.TButton", command=self.clear_logs).pack(side="left", padx=3)
        self.refresh_logs()

    def _manual_update_check(self):
        if self._update_check_running or getattr(self, "_download_running", False): return
        self._update_check_running = True; self._manual_check_active = True; self._update_check_spinner_index = 0; self._spin_update_check_button(); self.status.configure(text="Güncellemeler kontrol ediliyor..."); self.update_detail.set("Güncel sürüm kontrol ediliyor..."); self.update_panel.pack(fill="x"); self.update_idletasks(); threading.Thread(target=self._check_updates_background, daemon=True).start()

    def _spin_update_check_button(self):
        if not getattr(self, "_manual_check_active", False): self.update_check_button.configure(text="↻", state="normal"); return
        symbols=("↻","⟳","↺","⟲"); index=self._update_check_spinner_index % len(symbols); self.update_check_button.configure(text=symbols[index],state="disabled"); self._update_check_spinner_index+=1; self.after(180,self._spin_update_check_button)

    @staticmethod
    def _format_bytes(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"

    def _file_box(self, parent, title, side):
        frame = ttk.Frame(parent, style="White.TFrame", padding=10)
        # Inner border effect
        inner_box = tk.Frame(frame, bg="#ffffff", highlightbackground="#e2e8f0", highlightthickness=1, padx=8, pady=8)
        inner_box.pack(fill="both", expand=True)

        # Header inside the card
        head_row = tk.Frame(inner_box, bg="#ffffff")
        head_row.pack(fill="x", pady=(0, 6))

        badge_color = "#eff6ff" if side == "PDF1" else "#f5f3ff"
        badge_fg = "#2563eb" if side == "PDF1" else "#4f46e5"
        side_badge = tk.Label(head_row, text=f" {side} ", bg=badge_color, fg=badge_fg, font=("Segoe UI", 9, "bold"), relief="flat")
        side_badge.pack(side="left", padx=(0, 6))

        info_col = tk.Frame(head_row, bg="#ffffff")
        info_col.pack(side="left")
        tk.Label(info_col, text=title, font=("Segoe UI", 10, "bold"), bg="#ffffff", fg="#0f172a").pack(anchor="w")
        sub_desc = "Ekipman ve motor seçim dokümanları" if side == "PDF1" else "Bağlantı şemaları ve pano çizimleri"
        tk.Label(info_col, text=sub_desc, font=("Segoe UI", 8), bg="#ffffff", fg="#94a3b8").pack(anchor="w")

        btn_col = tk.Frame(head_row, bg="#ffffff")
        btn_col.pack(side="right")

        count_badge = tk.Label(btn_col, text="0 PDF", bg="#ffffff", fg="#475569", font=("Segoe UI", 8, "bold"), relief="solid", bd=1, padx=6, pady=2)
        count_badge.pack(side="left", padx=(0, 6))

        ttk.Button(btn_col, text="+ PDF EKLE", style="Secondary.TButton", command=lambda: self.add_files(side)).pack(side="left", padx=2)
        ttk.Button(btn_col, text="+ KLASÖR EKLE", style="Secondary.TButton", command=lambda: self.add_folder(side)).pack(side="left", padx=2)

        # Animated drop banner (hidden until files are dragged over this box)
        banner_bg = "#eff6ff" if side == "PDF1" else "#f5f3ff"
        banner_border = "#2563eb" if side == "PDF1" else "#7c3aed"
        banner_fg = "#1d4ed8" if side == "PDF1" else "#6d28d9"
        banner_text = "⬇  SEÇİM ÇIKTISI (PDF1) BURAYA BIRAKIN  ⬇" if side == "PDF1" else "⬇  ELEKTRİK PROJESİ (PDF2) BURAYA BIRAKIN  ⬇"

        drop_banner = tk.Frame(inner_box, bg=banner_bg, highlightbackground=banner_border, highlightthickness=2, padx=8, pady=6)
        banner_label = tk.Label(drop_banner, text=banner_text, bg=banner_bg, fg=banner_fg, font=("Segoe UI", 9, "bold"))
        banner_label.pack(fill="both", expand=True)

        # Inner scrollable list area
        list_container = tk.Frame(inner_box, bg="#f8fafc", highlightbackground="#e2e8f0", highlightthickness=1)
        list_container.pack(fill="both", expand=True, pady=(4, 0))

        canvas = tk.Canvas(list_container, bg="#f8fafc", highlightthickness=0, height=95)
        scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#f8fafc")

        scrollable_frame.bind(
            "<Configure>",
            lambda e, c=canvas: c.configure(scrollregion=c.bbox("all"))
        )
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        def _on_canvas_resize(event, c=canvas, cw=canvas_window):
            c.itemconfig(cw, width=event.width)
        canvas.bind("<Configure>", _on_canvas_resize)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Store references
        if side == "PDF1":
            self._pdf1_scroll_frame = scrollable_frame
            self._pdf1_canvas = canvas
            self._pdf1_badge = count_badge
            self._pdf1_inner_box = inner_box
            self._pdf1_drop_banner = drop_banner
            self._pdf1_banner_label = banner_label
            self._pdf1_list_container = list_container
            self._pdf1_head_row = head_row
            self._pdf1_is_drag_active = False
            self._pdf1_anim_job = None
        else:
            self._pdf2_scroll_frame = scrollable_frame
            self._pdf2_canvas = canvas
            self._pdf2_badge = count_badge
            self._pdf2_inner_box = inner_box
            self._pdf2_drop_banner = drop_banner
            self._pdf2_banner_label = banner_label
            self._pdf2_list_container = list_container
            self._pdf2_head_row = head_row
            self._pdf2_is_drag_active = False
            self._pdf2_anim_job = None

        self._refresh_file_list(side)
        return count_badge, frame

    def set_drag_active(self, side: str, active: bool):
        """Visually activate or deactivate the drop zone with clear animated feedback."""
        is_active = getattr(self, f"_{side.lower()}_is_drag_active", False)
        if is_active == active:
            return

        setattr(self, f"_{side.lower()}_is_drag_active", active)
        inner_box = getattr(self, f"_{side.lower()}_inner_box", None)
        drop_banner = getattr(self, f"_{side.lower()}_drop_banner", None)
        list_container = getattr(self, f"_{side.lower()}_list_container", None)
        head_row = getattr(self, f"_{side.lower()}_head_row", None)

        if not inner_box or not drop_banner:
            return

        # Cancel any active pulse animation timer
        anim_job = getattr(self, f"_{side.lower()}_anim_job", None)
        if anim_job is not None:
            try:
                self.after_cancel(anim_job)
            except Exception:
                pass
            setattr(self, f"_{side.lower()}_anim_job", None)

        if active:
            # Show animated banner above the list container
            drop_banner.pack(fill="x", pady=(0, 6), before=list_container)
            reg = getattr(self, "_register_drop_target", None)
            if reg:
                reg(drop_banner, side)

            tint_bg = "#eff6ff" if side == "PDF1" else "#f5f3ff"
            inner_box.configure(bg=tint_bg)
            if head_row:
                head_row.configure(bg=tint_bg)

            # Start pulsating animation loop
            self._run_drag_pulse_animation(side, 0)
        else:
            # Hide banner and restore clean normal appearance
            drop_banner.pack_forget()
            inner_box.configure(highlightbackground="#e2e8f0", highlightthickness=1, bg="#ffffff")
            if head_row:
                head_row.configure(bg="#ffffff")

    def _run_drag_pulse_animation(self, side: str, step: int):
        """Pulsating border color and icon animation during drag-over."""
        if not getattr(self, f"_{side.lower()}_is_drag_active", False):
            return

        inner_box = getattr(self, f"_{side.lower()}_inner_box", None)
        drop_banner = getattr(self, f"_{side.lower()}_drop_banner", None)
        banner_label = getattr(self, f"_{side.lower()}_banner_label", None)

        if not inner_box or not drop_banner:
            return

        if side == "PDF1":
            palette = ["#2563eb", "#3b82f6", "#60a5fa", "#3b82f6"]
            icons = ["⬇  SEÇİM ÇIKTISI (PDF1) BURAYA BIRAKIN  ⬇", "⤓  SEÇİM ÇIKTISI (PDF1) BURAYA BIRAKIN  ⤓"]
        else:
            palette = ["#7c3aed", "#8b5cf6", "#a78bfa", "#8b5cf6"]
            icons = ["⬇  ELEKTRİK PROJESİ (PDF2) BURAYA BIRAKIN  ⬇", "⤓  ELEKTRİK PROJESİ (PDF2) BURAYA BIRAKIN  ⤓"]

        color = palette[step % len(palette)]
        icon_text = icons[(step // 2) % len(icons)]

        try:
            inner_box.configure(highlightbackground=color, highlightthickness=2)
            drop_banner.configure(highlightbackground=color)
            if banner_label:
                banner_label.configure(text=icon_text)
        except Exception:
            pass

        job = self.after(130, lambda: self._run_drag_pulse_animation(side, step + 1))
        setattr(self, f"_{side.lower()}_anim_job", job)

    def remove_file(self, side: str, index: int):
        target = self.pdf1_inputs if side == "PDF1" else self.pdf2_inputs
        if 0 <= index < len(target):
            removed = target.pop(index)
            info("PDF girişi silindi", side=side, path=str(removed.path))
            self._refresh_file_list(side)

    def _refresh_file_list(self, side: str):
        target = self.pdf1_inputs if side == "PDF1" else self.pdf2_inputs
        scroll_frame = getattr(self, f"_{side.lower()}_scroll_frame", None)
        badge = getattr(self, f"_{side.lower()}_badge", None)
        if scroll_frame is None:
            return

        if badge:
            badge.configure(text=f"{len(target)} PDF")

        for child in scroll_frame.winfo_children():
            child.destroy()

        if not target:
            empty_lbl = tk.Label(
                scroll_frame,
                text="PDF dosyalarını buraya sürükleyin veya '+ PDF EKLE' butonunu kullanın",
                bg="#f8fafc",
                fg="#94a3b8",
                font=("Segoe UI", 8),
                pady=20
            )
            empty_lbl.pack(fill="both", expand=True)
            reg = getattr(self, "_register_drop_target", None)
            if reg:
                reg(empty_lbl, side)
            return

        for idx, item in enumerate(target):
            card = tk.Frame(scroll_frame, bg="#ffffff", highlightbackground="#e2e8f0", highlightthickness=1, padx=6, pady=4)
            card.pack(fill="x", expand=True, padx=4, pady=2)

            icon = tk.Label(card, text="📄", bg="#ffffff", fg="#2563eb", font=("Segoe UI", 10))
            icon.pack(side="left", padx=(0, 6))

            text_box = tk.Frame(card, bg="#ffffff")
            text_box.pack(side="left", fill="both", expand=True)

            fname = Path(item.path).name
            tk.Label(text_box, text=fname, bg="#ffffff", fg="#0f172a", font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x", anchor="w")

            size_str = self._format_bytes(getattr(item, "size_bytes", 0))
            sub_info = f"{size_str} • {str(item.path)}"
            if len(sub_info) > 60:
                sub_info = sub_info[:57] + "..."
            tk.Label(text_box, text=sub_info, bg="#ffffff", fg="#64748b", font=("Segoe UI", 8), anchor="w").pack(fill="x", anchor="w")

            # Silme butonu (Trash can button 🗑)
            del_btn = tk.Button(
                card,
                text="🗑",
                bg="#ffffff",
                fg="#94a3b8",
                activeforeground="#ef4444",
                activebackground="#fee2e2",
                font=("Segoe UI", 10),
                relief="flat",
                bd=0,
                cursor="hand2",
                command=lambda i=idx, s=side: self.remove_file(s, i)
            )
            del_btn.pack(side="right", padx=(4, 2))

        reg = getattr(self, "_register_drop_target", None)
        if reg:
            reg(scroll_frame, side)

    def add_files(self, side):
        self._merge_inputs(side, list(filedialog.askopenfilenames(title=f"{side} PDF seç", filetypes=[("PDF", "*.pdf")])))

    def add_folder(self, side):
        path = filedialog.askdirectory(title=f"{side} PDF klasörü seç")
        if path:
            self._merge_inputs(side, [path])

    def _merge_inputs(self, side, paths):
        discovered = discover_pdfs(paths, recursive=True)
        target = self.pdf1_inputs if side == "PDF1" else self.pdf2_inputs
        known = {str(x.path).casefold() for x in target}
        for path in discovered:
            if str(path).casefold() not in known:
                target.append(path)
                known.add(str(path).casefold())
        self._refresh_file_list(side)
        info("PDF girişleri güncellendi", side=side, count=len(target), paths=[str(x.path) for x in target])

    def clear_inputs(self):
        if self._analysis_running:
            return
        self.pdf1_inputs.clear()
        self.pdf2_inputs.clear()
        self._refresh_file_list("PDF1")
        self._refresh_file_list("PDF2")
        self.analysis = None
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._clear_unmatched()
        self._clear_analysis_detail()
        self.status.configure(text="Hazır")
        self.update_progress.set(0)
        self.update_detail.set("Güncelleme hazır")
        self.update_panel.pack_forget()
        self._clear_grouped_results()
        info("PDF seçimleri ve analiz sonuçları temizlendi")

    def _clear_analysis_detail(self): self._set_detail("")
    def _clear_grouped_results(self): return

    def compare(self):
        if self._analysis_running:return
        if not self.pdf1_inputs or not self.pdf2_inputs: messagebox.showwarning("Eksik seçim","PDF1 ve PDF2 tarafına en az birer PDF/klasör ekleyin."); return
        self._analysis_running=True; self.update_progress.set(0); self.update_detail.set("PDF taraması başlıyor..."); self.update_panel.pack(fill="x"); self.status.configure(text="PDF'ler taranıyor..."); self.update_idletasks(); pdf1=[str(x.path) for x in self.pdf1_inputs]; pdf2=[str(x.path) for x in self.pdf2_inputs]; threading.Thread(target=self._prepare_analysis,args=(pdf1,pdf2),daemon=True).start()

    def _queue_analysis_progress(self,stage,done,total,detail):
        with self._progress_lock:
            self._progress_latest=(stage,done,total,detail)
            if self._progress_pending:return
            self._progress_pending=True
        self.after(0,self._flush_analysis_progress)

    def _flush_analysis_progress(self):
        with self._progress_lock:
            latest=self._progress_latest; self._progress_pending=False
        if latest is not None:self._analysis_progress(*latest)

    def _prepare_analysis(self,pdf1_paths,pdf2_paths):
        try:
            scan_pdfs([(p,"PDF1") for p in pdf1_paths]+[(p,"PDF2") for p in pdf2_paths],progress_callback=self._queue_analysis_progress)
            self.after(0,self._run_analysis_after_scan,pdf1_paths,pdf2_paths)
        except Exception as exc:self.after(0,self._analysis_failed,exc)

    def _run_analysis_after_scan(self,pdf1_paths,pdf2_paths):
        self.status.configure(text="Eşleştirme ve motor analizi yapılıyor..."); self.update_detail.set("Eşleştirme ve motor analizi başlıyor..."); self.update_idletasks(); threading.Thread(target=self._analyze_background,args=(pdf1_paths,pdf2_paths),daemon=True).start()

    def _analyze_background(self,pdf1_paths,pdf2_paths):
        try:
            analysis=analyze_batch(pdf1_paths,pdf2_paths,progress_callback=self._queue_analysis_progress)
            self.after(0,self._analysis_finished,analysis)
        except Exception as exc:self.after(0,self._analysis_failed,exc)

    def _analysis_finished(self,analysis):
        try:
            self.analysis=analysis; self._render_analysis(); self._render_unmatched(); self._post_analysis(); self._analysis_running=False; self.update_detail.set("Analiz tamamlandı • %100"); self.update_progress.set(100); self.status.configure(text=self.status.cget("text")); self.refresh_logs()
        except Exception as exc:self._analysis_failed(exc)

    def _post_analysis(self):pass
    def _render_analysis(self):
        for item in self.tree.get_children(): self.tree.delete(item)
        counts={"MATCH":0,"MISMATCH":0,"ONLY_IN_PDF1":0,"ONLY_IN_PDF2":0}; ahu_context={}
        for batch_ahu in self.analysis.ahu_matches:
            left=normalize_equipment_id(batch_ahu.match.left_normalized); right=normalize_equipment_id(batch_ahu.match.right_normalized)
            if left:ahu_context[left]=batch_ahu.project_name or "-"
            if right:ahu_context[right]=batch_ahu.project_name or "-"
        comparisons=list(self.analysis.motor_comparisons); comparisons.sort(key=lambda item:(ahu_context.get(normalize_equipment_id(item.equipment_id),"-").casefold(),normalize_equipment_id(item.equipment_id).casefold(),item.component_type.casefold(),item.component_index)); previous_group=None; group_number=0
        for comparison in comparisons:
            counts[comparison.status]=counts.get(comparison.status,0)+1; ahu=normalize_equipment_id(comparison.equipment_id); project=ahu_context.get(ahu,"-"); group_key=(project.casefold(),ahu.casefold())
            if group_key!=previous_group: group_number+=1; previous_group=group_key
            tag="group_a" if group_number%2 else "group_b"; self.tree.insert("","end",tags=(tag,),values=(project,ahu,comparison.component_label,self._fmt(comparison.pdf1_kw),self._fmt(comparison.pdf2_kw),comparison.status))
        info("GUI sonuç tablosu oluşturuldu",comparisons=len(comparisons),counts=counts,grouped_ahu_count=group_number); self.status.configure(text=f"✓ Proje {len(self.analysis.project_matches)} | AHU {len(self.analysis.ahu_matches)} | Motor {len(self.analysis.motor_comparisons)} | MATCH {counts['MATCH']} | MISMATCH {counts['MISMATCH']} | PDF1 {counts['ONLY_IN_PDF1']} | PDF2 {counts['ONLY_IN_PDF2']}"); self._set_detail(json.dumps(self.analysis.to_dict(),ensure_ascii=False,indent=2)); self.refresh_logs()
    def _render_unmatched(self):
        for item in self.unmatched_tree.get_children(): self.unmatched_tree.delete(item)
        matched_paths=set()
        for ahu in self.analysis.ahu_matches:
            matched_paths.update(str(path).casefold() for path in ahu.pdf1_files); matched_paths.update(str(path).casefold() for path in ahu.pdf2_files)
        rows=[]
        for side,documents in (("PDF1",self.analysis.pdf1_documents),("PDF2",self.analysis.pdf2_documents)):
            for document in documents:
                if str(document.path).casefold() in matched_paths: continue
                project=document.project.project_name or "-"; ahus=", ".join(document.equipment) if document.equipment else "-"; reason="AHU eşleşmesine giremedi" if document.equipment else "Ekipman/AHU tespit edilemedi"; rows.append((side,Path(document.path).name,project,ahus,reason,str(document.path)))
        rows.sort(key=lambda row:(row[0],row[1].casefold()))
        for side,pdf,project,ahus,reason,path in rows:self.unmatched_tree.insert("","end",values=(side,pdf,project,ahus,reason),tags=(path,))
        self.tabs.tab(1,text=f"EŞLEŞMEYEN PDF'LER ({len(rows)})"); info("Eşleşmeyen PDF listesi oluşturuldu",unmatched_count=len(rows),matched_ahu_pdf_count=len(matched_paths),unmatched=[{"side":r[0],"path":r[5],"project":r[2],"ahu":r[3],"reason":r[4]} for r in rows])
    def _clear_unmatched(self):
        if not hasattr(self,"unmatched_tree"):return
        for item in self.unmatched_tree.get_children():self.unmatched_tree.delete(item)
        if hasattr(self,"tabs"):self.tabs.tab(1,text="EŞLEŞMEYEN PDF'LER (0)")
    def _analysis_failed(self,exc):
        self._analysis_running=False; exception("GUI sonuç tablosu oluşturma hatası",exc); messagebox.showerror("Sonuç gösterme hatası",f"{type(exc).__name__}: {exc}"); self.status.configure(text="Analiz başarısız"); self.update_detail.set("Analiz başarısız"); self.refresh_logs()
    def _analysis_progress(self,stage,done,total,detail):
        if stage=="scan": percent=done/max(total,1)*60; text=f"PDF tarama %{percent:.1f} • {done}/{total} dosya • {detail}"
        else: percent=60+done/max(total,1)*40; text=f"Karşılaştırma %{percent:.1f} • {detail}"
        self.update_progress.set(percent); self.update_detail.set(text)

    def _schedule_update_check(self):
        if not self._update_check_running:self._update_check_running=True; threading.Thread(target=self._check_updates_background,daemon=True).start()
        self.after(UPDATE_CHECK_INTERVAL_MS,self._schedule_update_check)
    def _check_updates_background(self):
        try: info_data=check_for_update(Path(sys.executable),VERSION,BUILD_SHA); self.after(0,self._update_check_finished,info_data,None)
        except Exception as exc:self.after(0,self._update_check_finished,None,exc)
    def _update_check_finished(self,info_data,exc):
        self._update_check_running=False; self._manual_check_active=False; self.update_check_button.configure(text="↻",state="normal")
        if exc: exception("Arka plan güncelleme kontrolü hatası",exc); return
        if not info_data["available"]: self._available_update=None; self.update_notice.pack_forget(); return
        self._available_update=info_data; self.update_notice_label.configure(text=f"Yeni sürüm mevcut: {info_data['version']}"); self.update_notice.pack(side="right",padx=8); info("Yeni sürüm bulundu",version=info_data["version"],build_sha=info_data.get("build_sha"))
    def download_available_update(self):
        if self._update_check_running or getattr(self,"_download_running",False):return
        self._update_check_running=True; self._download_running=True; self.status.configure(text="Güncel sürüm kontrol ediliyor..."); self.update_detail.set("En güncel sürüm kontrol ediliyor..."); self.update_panel.pack(fill="x"); self.update_idletasks(); threading.Thread(target=self._refresh_update_before_download,daemon=True).start()
    def _refresh_update_before_download(self):
        try: info_data=check_for_update(Path(sys.executable),VERSION,BUILD_SHA); self.after(0,self._download_check_finished,info_data,None)
        except Exception as exc:self.after(0,self._download_check_finished,None,exc)
    def _download_check_finished(self,info_data,exc):
        self._update_check_running=False
        if exc: self._download_running=False; self._available_update=None; self.update_panel.pack_forget(); exception("İndirme öncesi güncelleme kontrolü hatası",exc); messagebox.showerror("Güncelleme",f"Güncel sürüm kontrol edilemedi:\n{type(exc).__name__}: {exc}"); self.status.configure(text="Güncelleme kontrolü başarısız"); return
        if not info_data["available"]: self._download_running=False; self._available_update=None; self.update_notice.pack_forget(); self.update_panel.pack_forget(); self.status.configure(text="Program güncel"); self.update_detail.set("Program güncel"); info("İndirme öncesi kontrolde yeni güncelleme bulunamadı"); return
        self._available_update=info_data; self.update_notice_label.configure(text=f"Yeni sürüm mevcut: {info_data['version']}"); self.update_notice.pack_forget(); self.status.configure(text="Yeni sürüm indiriliyor..."); self.update_progress.set(0); self.update_detail.set("İndirme başlıyor..."); threading.Thread(target=self._download_update_background,args=(info_data,),daemon=True).start()
    def _download_update_background(self,info_data):
        try: temp_exe=download_update(info_data["download_url"],expected_digest=info_data.get("digest"),asset_id=info_data.get("asset_id"),browser_download_url=info_data.get("browser_download_url"),expected_size=info_data.get("asset_size"),asset_name=info_data.get("asset_name"),chunks=info_data.get("chunks"),progress_callback=lambda stage,done,total,speed:self.after(0,self._update_progress,stage,done,total,speed)); self.after(0,self._update_install,temp_exe,info_data)
        except Exception as exc:self.after(0,self._update_failed,exc,info_data)
    def _update_progress(self,stage,done,total,speed):
        percent=(done/total*100) if total else 0; total_mb=f"{total/1048576:.1f}" if total else "?"; done_mb=f"{done/1048576:.1f}"; speed_mb=speed/1048576; self.update_progress.set(percent); self.update_detail.set(f"İndirme %{percent:.1f} • {done_mb}/{total_mb} MB • {speed_mb:.2f} MB/sn"); info("Güncelleme indirme ilerlemesi",percent=round(percent,1),downloaded_mb=round(done/1048576,2),total_mb=round(total/1048576,2) if total else None,speed_mb_s=round(speed_mb,2)); self.refresh_logs()
    def _update_install(self,temp_exe,info_data):
        self._download_running=False; self.update_progress.set(100); self.update_detail.set("Kurulum hazırlanıyor..."); self.status.configure(text="Güncelleme kuruluyor..."); info("Güncelleme kurulumu başlıyor",temp=str(temp_exe)); self.refresh_logs(); restart_with_update(temp_exe,Path(sys.executable))
    def _update_failed(self,exc,info_data):
        self._download_running=False; exception("GUI güncelleme uygulama hatası",exc,version=info_data.get("version"),asset_id=info_data.get("asset_id"),asset_name=info_data.get("asset_name")); messagebox.showerror("Güncelleme",f"Güncelleme başarısız:\n{type(exc).__name__}: {exc}\n\nDetay HATA / İŞLEM LOGLARI sekmesinde."); self.status.configure(text="Güncelleme başarısız"); self.update_detail.set("Güncelleme başarısız"); self.refresh_logs()
    @staticmethod
    def _fmt(value): return "-" if value is None else f"{value:g}"
    def _set_detail(self,text):
        self.detail.configure(state="normal"); self.detail.delete("1.0","end")
        if text:self.detail.insert("1.0",text)
        self.detail.configure(state="disabled")
    def refresh_logs(self):
        try:
            if not hasattr(self,"log_text"):return
            text=read_log(); self.log_text.delete("1.0","end"); self.log_text.insert("1.0",text); self.log_text.see("end")
        except Exception as exc:exception("GUI log ekranı yenilenemedi",exc)
    def open_log_file(self):
        path=log_file(); path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():path.write_text("",encoding="utf-8")
        os.startfile(str(path)) if os.name=="nt" else subprocess.Popen(["xdg-open",str(path)])
    def open_log_directory(self):
        directory=log_directory(); directory.mkdir(parents=True,exist_ok=True); os.startfile(str(directory)) if os.name=="nt" else subprocess.Popen(["xdg-open",str(directory)])
    def clear_logs(self):
        if messagebox.askyesno("Logları temizle","Tüm mevcut uygulama logları temizlensin mi?"):clear_log(); self.refresh_logs()
    def save_json(self):
        if self.analysis is None:messagebox.showwarning("Sonuç yok","Önce ANALİZ BAŞLA çalıştırın."); return
        path=filedialog.asksaveasfilename(title="Toplu analizi kaydet",defaultextension=".json",filetypes=[("JSON","*.json")])
        if not path:return
        Path(path).write_text(json.dumps(self.analysis.to_dict(),ensure_ascii=False,indent=2),encoding="utf-8"); info("Analiz JSON kaydedildi",path=path); self.refresh_logs()
