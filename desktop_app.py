"""Desktop GUI for PDF kW Selector - Project -> AHU -> Motor batch analysis."""
from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ahu_matching import normalize_equipment_id
from batch_analysis import analyze_batch
from batch_input import discover_pdfs

VERSION = "v0.5.3"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"PDF kW Selector {VERSION} — Batch Motor Analysis")
        self.geometry("1320x800")
        self.minsize(1120, 700)
        self.pdf1_inputs = []
        self.pdf2_inputs = []
        self.analysis = None
        self._build()

    def _build(self):
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)

        header = ttk.Frame(outer)
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text="PDF kW SELECTOR", font=("Segoe UI", 19, "bold")).pack(side="left")
        ttk.Label(header, text=f"{VERSION} • Project → AHU → Motor", font=("Segoe UI", 10)).pack(side="right")

        top = ttk.Frame(outer)
        top.grid(row=1, column=0, sticky="ew", pady=(10, 8))
        top.columnconfigure(0, weight=1)
        top.columnconfigure(1, weight=1)
        self.pdf1_label = self._file_box(top, "PDF 1 — Seçim / Referans", 0, self.add_pdf1_files, self.add_pdf1_folder)
        self.pdf2_label = self._file_box(top, "PDF 2 — Elektrik / Üretim", 1, self.add_pdf2_files, self.add_pdf2_folder)

        result = ttk.LabelFrame(outer, text="Toplu Motor Karşılaştırması", padding=8)
        result.grid(row=2, column=0, sticky="nsew")
        result.columnconfigure(0, weight=1)
        result.rowconfigure(0, weight=1)
        cols = ("project", "ahu", "motor", "type", "pdf1", "pdf2", "diff", "status", "page1", "page2")
        headings = {"project":"Proje", "ahu":"AHU", "motor":"Motor", "type":"Tip", "pdf1":"PDF1 kW", "pdf2":"PDF2 kW", "diff":"Fark", "status":"Durum", "page1":"PDF1", "page2":"PDF2"}
        widths = {"project":220, "ahu":105, "motor":80, "type":110, "pdf1":80, "pdf2":80, "diff":70, "status":125, "page1":60, "page2":60}
        self.tree = ttk.Treeview(result, columns=cols, show="headings")
        for col in cols:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor="center")
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(result, orient="vertical", command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)

        actions = ttk.Frame(outer)
        actions.grid(row=3, column=0, sticky="ew", pady=8)
        ttk.Button(actions, text="TOPLU ANALİZ", command=self.compare).pack(side="left")
        ttk.Button(actions, text="SEÇİMLERİ TEMİZLE", command=self.clear_inputs).pack(side="left", padx=8)
        ttk.Button(actions, text="JSON KAYDET", command=self.save_json).pack(side="left")
        self.status = ttk.Label(actions, text="PDF 1 ve PDF 2 tarafına dosya veya klasör ekleyin.")
        self.status.pack(side="right")

        self.detail = tk.Text(outer, height=8, wrap="word", font=("Consolas", 9))
        self.detail.grid(row=4, column=0, sticky="ew")
        self.detail.configure(state="disabled")

    def _file_box(self, parent, title, column, file_command, folder_command):
        box = ttk.LabelFrame(parent, text=title, padding=8)
        box.grid(row=0, column=column, sticky="nsew", padx=(0, 5) if column == 0 else (5, 0))
        label = ttk.Label(box, text="0 PDF seçildi", width=75)
        label.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        ttk.Button(box, text="PDF EKLE", command=file_command).grid(row=1, column=0, sticky="w")
        ttk.Button(box, text="KLASÖR EKLE", command=folder_command).grid(row=1, column=1, sticky="w", padx=6)
        box.columnconfigure(0, weight=1)
        return label

    def _add_inputs(self, target: str):
        paths = filedialog.askopenfilenames(title=f"{target} PDF dosyalarını seç", filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")])
        if paths:
            self._merge_inputs(target, list(paths))

    def _add_folder(self, target: str):
        path = filedialog.askdirectory(title=f"{target} PDF klasörünü seç")
        if path:
            self._merge_inputs(target, [path])

    def _merge_inputs(self, target: str, paths):
        current = self.pdf1_inputs if target == "PDF1" else self.pdf2_inputs
        merged = discover_pdfs([item.path for item in current] + list(paths), recursive=True)
        if target == "PDF1":
            self.pdf1_inputs = merged
            self._update_label(self.pdf1_label, merged)
        else:
            self.pdf2_inputs = merged
            self._update_label(self.pdf2_label, merged)
        self.status.configure(text=f"{target}: {len(merged)} PDF hazır")

    def _update_label(self, label, items):
        if not items:
            label.configure(text="0 PDF seçildi")
            return
        names = [Path(item.path).name for item in items[:3]]
        suffix = " ..." if len(items) > 3 else ""
        label.configure(text=f"{len(items)} PDF: " + ", ".join(names) + suffix)

    def add_pdf1_files(self): self._add_inputs("PDF1")
    def add_pdf1_folder(self): self._add_folder("PDF1")
    def add_pdf2_files(self): self._add_inputs("PDF2")
    def add_pdf2_folder(self): self._add_folder("PDF2")

    def clear_inputs(self):
        self.pdf1_inputs, self.pdf2_inputs = [], []
        self.analysis = None
        self._update_label(self.pdf1_label, [])
        self._update_label(self.pdf2_label, [])
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._set_detail("")
        self.status.configure(text="Seçimler temizlendi.")

    def compare(self):
        if not self.pdf1_inputs or not self.pdf2_inputs:
            messagebox.showwarning("PDF eksik", "PDF 1 ve PDF 2 tarafına en az bir PDF veya klasör ekleyin.")
            return
        try:
            self.status.configure(text="Project → AHU → Motor toplu analizi yapılıyor...")
            self.update_idletasks()
            self.analysis = analyze_batch(
                [item.path for item in self.pdf1_inputs],
                [item.path for item in self.pdf2_inputs],
            )
        except Exception as exc:
            messagebox.showerror("Toplu analiz hatası", str(exc))
            self.status.configure(text="Toplu analiz hatası")
            return

        for item in self.tree.get_children():
            self.tree.delete(item)

        counts = {"MATCH": 0, "MISMATCH": 0, "ONLY_IN_PDF1": 0, "ONLY_IN_PDF2": 0}
        ahu_context = {}
        for batch_ahu in self.analysis.ahu_matches:
            left = normalize_equipment_id(batch_ahu.match.left_normalized)
            right = normalize_equipment_id(batch_ahu.match.right_normalized)
            if left:
                ahu_context[left] = batch_ahu.project_name or "-"
            if right:
                ahu_context[right] = batch_ahu.project_name or "-"

        for comparison in self.analysis.motor_comparisons:
            counts[comparison.status] = counts.get(comparison.status, 0) + 1
            ahu = normalize_equipment_id(comparison.equipment_id)
            project = ahu_context.get(ahu, "-")
            self.tree.insert(
                "",
                "end",
                values=(
                    project,
                    ahu,
                    comparison.component_label,
                    comparison.component_type,
                    self._fmt(comparison.pdf1_kw),
                    self._fmt(comparison.pdf2_kw),
                    self._fmt(comparison.difference_kw),
                    comparison.status,
                    comparison.pdf1_page or "-",
                    comparison.pdf2_page or "-",
                ),
            )

        self.status.configure(
            text=(
                f"✓ Proje {len(self.analysis.project_matches)} | AHU {len(self.analysis.ahu_matches)} | "
                f"Motor {len(self.analysis.motor_comparisons)} | "
                f"MATCH {counts['MATCH']} | MISMATCH {counts['MISMATCH']} | "
                f"PDF1 {counts['ONLY_IN_PDF1']} | PDF2 {counts['ONLY_IN_PDF2']}"
            )
        )
        self._set_detail(json.dumps(self.analysis.to_dict(), ensure_ascii=False, indent=2))

    @staticmethod
    def _fmt(value): return "-" if value is None else f"{value:g}"

    def _set_detail(self, text):
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        if text:
            self.detail.insert("1.0", text)
        self.detail.configure(state="disabled")

    def save_json(self):
        if self.analysis is None:
            messagebox.showwarning("Sonuç yok", "Önce TOPLU ANALİZ çalıştırın.")
            return
        path = filedialog.asksaveasfilename(title="Toplu analizi kaydet", defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        Path(path).write_text(json.dumps(self.analysis.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        messagebox.showinfo("Kaydedildi", f"Sonuç kaydedildi:\n{path}")


if __name__ == "__main__":
    App().mainloop()
