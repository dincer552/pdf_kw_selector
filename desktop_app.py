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
from pdf_viewer import open_pdf_at_page
from updater import check_for_update, download_update, restart_with_update
from ahu_matching import normalize_equipment_id
from build_info import BUILD_SHA, BUILD_VERSION
from pdf_hover_indicator import get_cell_hover_box
from status import apply_status_tag, install_status_display, status_display_text

VERSION = BUILD_VERSION
UPDATE_CHECK_INTERVAL_MS = 15 * 60 * 1000


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"AHU Match {VERSION} — PDF / AHU / Motor Analysis")
        self.geometry("1300x820")
        self._set_app_icon()
        self.minsize(1100, 700)
        self._cell_hover_box = get_cell_hover_box()
        self.pdf1_inputs: list[PdfInput] = []
        self.pdf2_inputs: list[PdfInput] = []
        self.analysis = None
        self._analysis_running = False
        self._update_check_running = False
        self._available_update = None
        self._update_available = False
        self._manual_update_button = None
        self._update_button = None
        self._update_build_label = None
        self._progress_lock = threading.Lock()
        self._progress_pending = False
        self._progress_latest = None
        self._analysis_json = ""
        self._init_modern_theme()
        self._build_ui()
        install_status_display(self)
        install_pdf_drop_targets(self, self.pdf1_box, self.pdf2_box)
        self.after(5000, self._schedule_update_check)

    def _set_app_icon(self):
        """Use the packaged AHU Match icon for the title bar and taskbar."""
        try:
            base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
            icon_path = base / "favicon.ico"
            if icon_path.exists():
                self.iconbitmap(default=str(icon_path))
        except Exception as exc:
            try:
                from app_logger import debug
                debug("AHU Match icon yüklenemedi", error=str(exc))
            except Exception:
                pass

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
        style.configure("UpdateBuild.TLabel", background=card_bg, foreground=primary_color, font=("Segoe UI", 8, "bold"))

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
        ttk.Label(title_box, text="AHU MATCH", style="Title.TLabel").pack(anchor="w")
        ttk.Label(title_box, text="Project → AHU → Motor Anma Gücü Karşılaştırma ve Doğrulama", style="Muted.TLabel").pack(anchor="w")

        update_controls = ttk.Frame(header, style="White.TFrame")
        update_controls.pack(side="right", padx=(6, 0))
        self._manual_update_button = ttk.Button(
            update_controls, text="↻", width=2,
            command=self._manual_update_check, style="Secondary.TButton"
        )
        self._manual_update_button.grid(row=0, column=0, padx=(0, 6), sticky="s")
        self._update_button = ttk.Button(
            update_controls, text="Güncelle", width=9,
            command=self.download_available_update, style="Secondary.TButton",
            state="disabled"
        )
        self._update_button.grid(row=0, column=1, sticky="s")
        self._update_build_label = ttk.Label(update_controls, text="", style="UpdateBuild.TLabel")
        self._update_build_label.grid(row=1, column=1, pady=(2, 0), sticky="n")
        ttk.Label(header, text=f"{VERSION}", style="Badge.TLabel").pack(side="right", padx=(0, 6))

        # PDF Drop / Selection Boxes
        boxes = ttk.Frame(self, padding=(10, 0))
        boxes.pack(fill="x")
        self.pdf1_label, self.pdf1_box = self._file_box(boxes, "Seçim Çıktısı (PDF1)", "PDF1")
        self.pdf2_label, self.pdf2_box = self._file_box(boxes, "Elektrik Projesi (PDF2)", "PDF2")
        self.pdf1_box.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.pdf2_box.pack(side="left", fill="x", expand=True, padx=(5, 0))

        # Reserve a dedicated bottom dock so actions stay visible when the
        # window is vertically resized.
        action_dock = ttk.Frame(self, style="White.TFrame", padding=(10, 6))
        action_dock.pack(side="bottom", fill="x", padx=10, pady=(6, 0))
        self.action_dock = action_dock

        # Notebook tabs
        tabs = ttk.Notebook(self)
        tabs.pack(fill="both", expand=True, padx=10, pady=(8, 0))
        tabs.bind("<<NotebookTabChanged>>", self._on_tab_changed, add="+")
        self.tabs = tabs
        result_tab = ttk.Frame(tabs, style="White.TFrame")
        unmatched_tab = ttk.Frame(tabs, style="White.TFrame")
        log_tab = ttk.Frame(tabs, style="White.TFrame")
        self.log_tab = log_tab
        tabs.add(result_tab, text="DANFOSS / MOTOR")
        tabs.add(unmatched_tab, text="EŞLEŞMEYEN PDF'LER (0)")
        tabs.add(log_tab, text=">_ LOGLAR")

        cols = ("Proje", "AHU", "Motor", "Seçim kW", "Elektrik P. kW", "Durum")
        self.tree = ttk.Treeview(result_tab, columns=cols, show="headings")
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self._tree_cell_data: dict[str, dict] = {}
        self.tree.bind("<Button-1>", self._on_tree_cell_click)
        self.tree.bind("<Motion>", self._on_tree_cell_motion)
        self.tree.bind("<Leave>", lambda e: (self.tree.configure(cursor=""), self._cell_hover_box.hide()))
        self.tree.bind("<MouseWheel>", lambda e: self._cell_hover_box.hide(), add="+")

        unmatched_cols = ("Taraf", "PDF", "Proje", "AHU", "Neden")
        self.unmatched_tree = ttk.Treeview(unmatched_tab, columns=unmatched_cols, show="headings")
        widths = {"Taraf": 90, "PDF": 420, "Proje": 300, "AHU": 260, "Neden": 260}
        for col in unmatched_cols:
            self.unmatched_tree.heading(col, text=col)
            self.unmatched_tree.column(col, width=widths[col], anchor="w")
        unmatched_scroll = ttk.Scrollbar(unmatched_tab, orient="vertical", command=lambda *args: (self.unmatched_tree.yview(*args), self._cell_hover_box.hide()))
        self.unmatched_tree.configure(yscrollcommand=unmatched_scroll.set)
        self.unmatched_tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        unmatched_scroll.pack(side="right", fill="y", padx=(0, 8), pady=8)
        self._unmatched_cell_data: dict[str, dict] = {}
        self.unmatched_tree.bind("<Button-1>", self._on_unmatched_cell_click)
        self.unmatched_tree.bind("<Double-1>", self._on_unmatched_click)
        self.unmatched_tree.bind("<Motion>", self._on_unmatched_cell_motion)
        self.unmatched_tree.bind("<Leave>", lambda e: (self.unmatched_tree.configure(cursor=""), self._cell_hover_box.hide()))
        self.unmatched_tree.bind("<MouseWheel>", lambda e: self._cell_hover_box.hide(), add="+")

        detail_frame = ttk.LabelFrame(log_tab, text="Sonuç JSON / Teknik Detay", padding=6)
        log_tab.grid_rowconfigure(1, weight=1)
        log_tab.grid_columnconfigure(0, weight=1)
        detail_frame.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        self.detail = tk.Text(detail_frame, height=6, wrap="none", bg="#f8fafc", fg="#0f172a", font=("Consolas", 9), relief="flat")
        self.detail.pack(fill="both", expand=True)
        self.detail.configure(state="disabled")

        self.update_progress = tk.DoubleVar(value=0)
        self.update_detail = tk.StringVar(value="Güncelleme hazır")
        style = ttk.Style(self)
        style.configure("Update.Horizontal.TProgressbar", troughcolor="#e2e8f0", background="#1a56db")
        update_area = ttk.Frame(action_dock, style="White.TFrame", width=720, height=58)
        update_area.pack(side="right", fill="y", padx=(12, 0))
        update_area.pack_propagate(False)
        self.update_area = update_area
        progress = ttk.Frame(update_area, padding=(8, 0))
        self.update_panel = progress
        ttk.Label(progress, textvariable=self.update_detail, anchor="e").pack(side="left", fill="x", expand=True)
        self.update_bar = ttk.Progressbar(progress, style="Update.Horizontal.TProgressbar", variable=self.update_progress, maximum=100, length=360)
        self.update_bar.pack(side="right", padx=8)
        progress.pack(fill="x", expand=False)
        style.configure("Small.Secondary.TButton", padding=(7, 2), font=("Segoe UI", 8))

        # Action Buttons bar
        buttons = ttk.Frame(action_dock, padding=(0, 2))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="▶ ANALİZ BAŞLA", style="Primary.TButton", command=self.compare).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="↺ TEMİZLE", style="Secondary.TButton", command=self.clear_inputs).pack(side="left", padx=3)

        self.status = ttk.Label(buttons, text="Hazır", anchor="e")
        self.status.pack(side="right")

        self.log_text = tk.Text(log_tab, wrap="none", bg="#f8fafc", fg="#0f172a", font=("Consolas", 9), relief="flat")
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        log_buttons = ttk.Frame(log_tab, padding=6)
        log_buttons.grid(row=2, column=0, sticky="ew", padx=5, pady=(4, 5))
        ttk.Button(log_buttons, text="JSON KAYDET", style="Secondary.TButton", command=self.save_json).pack(side="left", padx=3)
        ttk.Button(log_buttons, text="LOGLARI YENİLE", style="Secondary.TButton", command=self.refresh_logs).pack(side="left", padx=3)
        ttk.Button(log_buttons, text="LOG DOSYASINI AÇ", style="Secondary.TButton", command=self.open_log_file).pack(side="left", padx=3)
        ttk.Button(log_buttons, text="LOG KLASÖRÜNÜ AÇ", style="Secondary.TButton", command=self.open_log_directory).pack(side="left", padx=3)
        ttk.Button(log_buttons, text="LOGLARI TEMİZLE", style="Secondary.TButton", command=self.clear_logs).pack(side="left", padx=3)
        self.refresh_logs()

    def _manual_update_check(self):
        if self._update_check_running or getattr(self, "_download_running", False): return
        self._update_check_running = True
        self._manual_check_active = True
        self._update_check_spinner_index = 0
        self._spin_update_check_button()
        self.status.configure(text="Hazır")
        self.update_detail.set("Güncellemeler kontrol ediliyor...")
        self.update_panel.pack(fill="x")
        self.update_idletasks()
        threading.Thread(target=self._check_updates_background, daemon=True).start()

    def _spin_update_check_button(self):
        if not getattr(self, "_manual_check_active", False):
            if self._manual_update_button is not None:
                self._manual_update_button.configure(text="↻", state="normal")
            return
        symbols = ("↻", "⟳", "↺", "⟲")
        index = self._update_check_spinner_index % len(symbols)
        if self._manual_update_button is not None:
            self._manual_update_button.configure(text=symbols[index], state="disabled")
        self._update_check_spinner_index += 1
        self.after(180, self._spin_update_check_button)

    def _schedule_update_check(self):
        if not self._update_check_running:self._update_check_running=True; threading.Thread(target=self._check_updates_background,daemon=True).start()
        self.after(UPDATE_CHECK_INTERVAL_MS,self._schedule_update_check)
    def _check_updates_background(self):
        try: info_data=check_for_update(Path(sys.executable),VERSION,BUILD_SHA); self.after(0,self._update_check_finished,info_data,None)
        except Exception as exc:self.after(0,self._update_check_finished,None,exc)
    def _update_check_finished(self,info_data,exc):
        self._update_check_running = False
        self._manual_check_active = False
        if self._manual_update_button is not None:
            self._manual_update_button.configure(text="↻", state="normal")
        if exc:
            self._update_available = False
            self._available_update = None
            if self._update_button is not None:
                self._update_button.configure(text="Güncelle", state="disabled")
            if self._update_build_label is not None:
                self._update_build_label.configure(text="")
            exception("Arka plan güncelleme kontrolü hatası",exc)
            return

        available = bool(info_data and info_data.get("available"))
        self._update_available = available
        self._available_update = info_data if available else None
        if self._update_button is not None:
            self._update_button.configure(text="Güncelle", state="normal" if available else "disabled")
        if self._update_build_label is not None:
            if available and info_data:
                version = str(info_data.get("version") or "").strip().lstrip("vV")
                self._update_build_label.configure(text=f"v{version}" if version else "Yeni sürüm")
            else:
                self._update_build_label.configure(text="")
        if available and info_data:
            self.update_detail.set("Yeni sürüm hazır")
            self.status.configure(text=f"Yeni sürüm bulundu: {info_data['version']}")
            info("Yeni sürüm bulundu",version=info_data["version"],build_sha=info_data.get("build_sha"))
        else:
            self.update_detail.set("Güncelleme hazır")

    def download_available_update(self):
        if not self._update_available or self._update_check_running or getattr(self,"_download_running",False): return
        self._update_check_running = True
        self._download_running = True
        if self._update_button is not None:
            self._update_button.configure(text="Kontrol...", state="disabled")
        self.status.configure(text="Hazır")
        self.update_detail.set("En güncel sürüm kontrol ediliyor...")
        self.update_panel.pack(fill="x")
        self.update_idletasks()
        threading.Thread(target=self._refresh_update_before_download,daemon=True).start()

    def _refresh_update_before_download(self):
        try:
            info_data=check_for_update(Path(sys.executable),VERSION,BUILD_SHA)
            self.after(0,self._download_check_finished,info_data,None)
        except Exception as exc:
            self.after(0,self._download_check_finished,None,exc)

    def _download_check_finished(self,info_data,exc):
        self._update_check_running=False
        if exc:
            self._download_running=False
            self._update_available=False
            self._available_update=None
            if self._update_button is not None:
                self._update_button.configure(text="Güncelle",state="disabled")
            if self._update_build_label is not None:
                self._update_build_label.configure(text="")
            exception("İndirme öncesi güncelleme kontrolü hatası",exc)
            messagebox.showerror("Güncelleme",f"Güncel sürüm kontrol edilemedi:\n{type(exc).__name__}: {exc}")
            self.status.configure(text="Güncelleme kontrolü başarısız")
            return
        if not info_data or not info_data.get("available"):
            self._download_running=False
            self._update_available=False
            self._available_update=None
            if self._update_button is not None:
                self._update_button.configure(text="Güncelle",state="disabled")
            if self._update_build_label is not None:
                self._update_build_label.configure(text="")
            self.update_detail.set("Program güncel")
            self.status.configure(text="Program güncel")
            info("İndirme öncesi kontrolde yeni güncelleme bulunamadı")
            return

        self._available_update=info_data
        if self._update_button is not None:
            self._update_button.configure(text="İndiriliyor...",state="disabled")
        if self._update_build_label is not None:
            version=str(info_data.get("version") or "").strip().lstrip("vV")
            self._update_build_label.configure(text=f"v{version}" if version else "Yeni sürüm")
        self.status.configure(text="Yeni sürüm indiriliyor...")
        self.update_progress.set(0)
        self.update_detail.set("İndirme başlıyor...")
        threading.Thread(target=self._download_update_background,args=(info_data,),daemon=True).start()

    def _download_update_background(self,info_data):
        try:
            temp_exe=download_update(
                info_data["download_url"],
                expected_digest=info_data.get("digest"),
                asset_id=info_data.get("asset_id"),
                browser_download_url=info_data.get("browser_download_url"),
                expected_size=info_data.get("asset_size"),
                asset_name=info_data.get("asset_name"),
                chunks=info_data.get("chunks"),
                progress_callback=lambda stage,done,total,speed:self.after(0,self._update_progress,stage,done,total,speed),
            )
            self.after(0,self._update_install,temp_exe,info_data)
        except Exception as exc:
            self.after(0,self._update_failed,exc,info_data)

    def _update_progress(self,stage,done,total,speed):
        percent=(done/total*100) if total else 0; total_mb=f"{total/1048576:.1f}" if total else "?"; done_mb=f"{done/1048576:.1f}"; speed_mb=speed/1048576; self.update_progress.set(percent); self.update_detail.set(f"İndirme %{percent:.1f} • {done_mb}/{total_mb} MB • {speed_mb:.2f} MB/sn"); info("Güncelleme indirme ilerlemesi",percent=round(percent,1),downloaded_mb=round(done/1048576,2),total_mb=round(total/1048576,2) if total else None,speed_mb_s=round(speed_mb,2)); self.refresh_logs()
    def _update_install(self,temp_exe,info_data):
        self._download_running=False
        self._update_available=False
        self.update_progress.set(100)
        self.update_detail.set("Kurulum hazırlanıyor...")
        self.status.configure(text="Güncelleme kuruluyor...")
        if self._update_button is not None:
            self._update_button.configure(text="Yüklendi",state="disabled")
        info("Güncelleme kurulumu başlıyor",temp=str(temp_exe))
        self.refresh_logs()
        restart_with_update(temp_exe,Path(sys.executable))
    def _update_failed(self,exc,info_data):
        self._download_running=False
        self._update_available=bool(info_data and info_data.get("available"))
        exception("GUI güncelleme uygulama hatası",exc,version=info_data.get("version") if info_data else None,asset_id=info_data.get("asset_id") if info_data else None,asset_name=info_data.get("asset_name") if info_data else None)
        if self._update_button is not None:
            self._update_button.configure(text="Güncelle",state="normal" if self._update_available else "disabled")
        messagebox.showerror("Güncelleme",f"Güncelleme başarısız:\n{type(exc).__name__}: {exc}\n\nDetay HATA / İŞLEM LOGLARI sekmesinde.")
        self.status.configure(text="Güncelleme başarısız")
        self.update_detail.set("Güncelleme başarısız")
        self.refresh_logs()
    @staticmethod
    def _fmt(value): return "-" if value is None else f"{value:g}"
    def _on_tab_changed(self, _event=None):
        self._cell_hover_box.hide()
        if self.tabs.select() != str(self.log_tab):
            return
        # Tk can skip repainting Text widgets on an inactive Notebook page
        # after a long background analysis. Reload both panels when opened.
        if self._analysis_json:
            self._set_detail(self._analysis_json)
        self.refresh_logs()

    def _set_detail(self,text):
        self.detail.configure(state="normal"); self.detail.delete("1.0","end")
        if text:self.detail.insert("1.0",str(text))
        self.detail.configure(state="disabled"); self.detail.update_idletasks()
    def refresh_logs(self):
        try:
            if not hasattr(self,"log_text"):return
            text=read_log() or "Henüz görüntülenecek log kaydı yok."
            self.log_text.configure(state="normal"); self.log_text.delete("1.0","end"); self.log_text.insert("1.0",text); self.log_text.see("end"); self.log_text.update_idletasks()
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

    def open_pdf_document(self, file_path: str | Path | None, page: int | None = 1, description: str = "") -> bool:
        if not file_path:
            messagebox.showinfo("PDF Bilgisi", f"{description or 'PDF'} için dosya yolu bulunamadı.")
            return False
        p = Path(file_path)
        if not p.exists():
            messagebox.showwarning("Dosya Bulunamadı", f"PDF dosyası mevcut konumda bulunamadı:\n{file_path}")
            return False
        display_page = page or 1
        self.status.configure(text=f"PDF açılıyor: {p.name} (Sayfa {display_page})...")
        info("Kullanıcı PDF bağlantısına tıkladı, PDF açılıyor", description=description, path=str(p), page=display_page)
        ok = open_pdf_at_page(p, display_page)
        if ok:
            self.status.configure(text=f"PDF açıldı: {p.name} (Sayfa {display_page})")
        else:
            self.status.configure(text=f"PDF açılırken bir sorun oluştu: {p.name}")
        return ok

    def _on_tree_cell_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        col = self.tree.identify_column(event.x)
        row_id = self.tree.identify_row(event.y)
        if not row_id or col not in ("#4", "#5"):
            return

        values = self.tree.item(row_id, "values")
        if not values or len(values) < 5:
            return

        data = getattr(self, "_tree_cell_data", {}).get(row_id, {})

        if col == "#4":
            # Seçim kW (PDF1)
            kw_val = values[3] if len(values) > 3 else ""
            if not kw_val or str(kw_val).strip() in ("", "-"):
                return
            pdf_path = data.get("pdf1_path") or (values[6] if len(values) > 6 and values[6] else None)
            raw_page = data.get("pdf1_page") or (values[7] if len(values) > 7 and values[7] else None)
            side_name = "Seçim çıktısı (PDF1)"
        else:
            # Elektrik P. kW (PDF2)
            kw_val = values[4] if len(values) > 4 else ""
            if not kw_val or str(kw_val).strip() in ("", "-"):
                return
            pdf_path = data.get("pdf2_path") or (values[8] if len(values) > 8 and values[8] else None)
            raw_page = data.get("pdf2_page") or (values[9] if len(values) > 9 and values[9] else None)
            side_name = "Elektrik projesi (PDF2)"

        try:
            page = int(raw_page) if raw_page is not None and str(raw_page).strip().isdigit() else None
        except (ValueError, TypeError):
            page = None

        self.open_pdf_document(pdf_path, page, side_name)

    def _on_tree_cell_motion(self, event):
        region = self.tree.identify_region(event.x, event.y)
        col = self.tree.identify_column(event.x)
        row_id = self.tree.identify_row(event.y)
        if region == "cell" and col in ("#4", "#5") and row_id:
            values = self.tree.item(row_id, "values")
            idx = 3 if col == "#4" else 4
            if values and len(values) > idx and str(values[idx]).strip() not in ("", "-"):
                self.tree.configure(cursor="hand2")
                self._cell_hover_box.show(self.tree, row_id, col)
                return
        self.tree.configure(cursor="")
        self._cell_hover_box.hide()

    def _on_unmatched_cell_click(self, event):
        region = self.unmatched_tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        col = self.unmatched_tree.identify_column(event.x)
        row_id = self.unmatched_tree.identify_row(event.y)
        if not row_id or col != "#2":  # Sadece "PDF" sütununa (#2) tıklandığında
            return
        data = getattr(self, "_unmatched_cell_data", {}).get(row_id, {})
        path = data.get("path")
        if not path:
            tags = self.unmatched_tree.item(row_id, "tags")
            if tags and len(tags) > 0 and tags[0]:
                path = tags[0]
        if path:
            self.open_pdf_document(path, data.get("page", 1), f"Eşleşmeyen PDF ({data.get('name', Path(path).name)})")

    def _on_unmatched_cell_motion(self, event):
        region = self.unmatched_tree.identify_region(event.x, event.y)
        col = self.unmatched_tree.identify_column(event.x)
        row_id = self.unmatched_tree.identify_row(event.y)
        if region == "cell" and col == "#2" and row_id:
            self.unmatched_tree.configure(cursor="hand2")
            self._cell_hover_box.show(self.unmatched_tree, row_id, col)
            return
        self.unmatched_tree.configure(cursor="")
        self._cell_hover_box.hide()

    def _on_unmatched_click(self, event):
        row_id = self.unmatched_tree.identify_row(event.y)
        if not row_id:
            return
        data = getattr(self, "_unmatched_cell_data", {}).get(row_id, {})
        path = data.get("path")
        if not path:
            tags = self.unmatched_tree.item(row_id, "tags")
            if tags and len(tags) > 0 and tags[0]:
                path = tags[0]
        if path:
            self.open_pdf_document(path, data.get("page", 1), f"Eşleşmeyen PDF ({data.get('name', Path(path).name)})")
