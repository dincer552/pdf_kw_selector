"""Desktop GUI for PDF kW Selector - PDF 1 + PDF 2 comparison."""
from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from motor_compare import MotorComparison, compare_motor_records
from stage1_page_discovery import build_stage1_motor_records, find_rated_motor_powers_in_pdf
from stage2_pdf_discovery import build_pdf2_motor_records, find_pdf2_motor_powers

VERSION = "v0.3.2"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"PDF kW Selector {VERSION} — PDF 1 + PDF 2")
        self.geometry("1120x720")
        self.minsize(980, 620)
        self.pdf1: Path | None = None
        self.pdf2: Path | None = None
        self.pdf1_results = []
        self.pdf2_results = []
        self.pdf1_motors = []
        self.pdf2_motors = []
        self.comparisons: list[MotorComparison] = []
        self._build()

    def _build(self):
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)

        top = ttk.Frame(outer)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(0, weight=1)
        top.columnconfigure(1, weight=1)
        self.pdf1_label = self._file_box(top, "PDF 1 — Seçim / ekipman", 0, self.select_pdf1)
        self.pdf2_label = self._file_box(top, "PDF 2 — Elektrik / sürücü", 1, self.select_pdf2)

        actions = ttk.Frame(outer)
        actions.grid(row=1, column=0, sticky="ew", pady=10)
        ttk.Button(actions, text="KARŞILAŞTIR", command=self.compare).pack(side="left")
        ttk.Button(actions, text="JSON KAYDET", command=self.save_json).pack(side="left", padx=8)
        self.status = ttk.Label(actions, text="Hazır")
        self.status.pack(side="right")

        result_frame = ttk.Frame(outer)
        result_frame.grid(row=2, column=0, sticky="nsew")
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)
        cols = ("label", "type", "pdf1", "pdf2", "diff", "status", "page1", "page2")
        headings = {
            "label": "Motor", "type": "Tip", "pdf1": "PDF 1 kW", "pdf2": "PDF 2 kW",
            "diff": "Fark", "status": "Durum", "page1": "PDF1 Sayfa", "page2": "PDF2 Sayfa",
        }
        widths = {"label": 110, "type": 110, "pdf1": 90, "pdf2": 90, "diff": 80, "status": 120, "page1": 90, "page2": 90}
        self.tree = ttk.Treeview(result_frame, columns=cols, show="headings", height=18)
        for col in cols:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor="center")
        self.tree.pack(fill="both", expand=True, side="left")
        scroll = ttk.Scrollbar(result_frame, orient="vertical", command=self.tree.yview)
        scroll.pack(fill="y", side="right")
        self.tree.configure(yscrollcommand=scroll.set)

        self.detail = tk.Text(outer, height=8, wrap="word", font=("Consolas", 9))
        self.detail.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        self.detail.configure(state="disabled")

    def _file_box(self, parent, title, column, command):
        box = ttk.LabelFrame(parent, text=title, padding=10)
        box.grid(row=0, column=column, sticky="nsew", padx=(0, 6) if column == 0 else (6, 0))
        label = ttk.Label(box, text="Henüz PDF seçilmedi", width=52)
        label.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(box, text="PDF SEÇ", command=command).grid(row=0, column=1)
        box.columnconfigure(0, weight=1)
        return label

    def select_pdf1(self):
        path = filedialog.askopenfilename(title="PDF 1 seç", filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")])
        if not path:
            return
        self.pdf1 = Path(path)
        self.pdf1_label.configure(text=str(self.pdf1))
        self._analyze_pdf1()

    def select_pdf2(self):
        path = filedialog.askopenfilename(title="PDF 2 seç", filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")])
        if not path:
            return
        self.pdf2 = Path(path)
        self.pdf2_label.configure(text=str(self.pdf2))
        self._analyze_pdf2()

    def _analyze_pdf1(self):
        try:
            self.pdf1_results = find_rated_motor_powers_in_pdf(self.pdf1)
            self.pdf1_motors = [record for result in self.pdf1_results for record in build_stage1_motor_records(result)]
            self.status.configure(text=f"PDF 1 hazır — {len(self.pdf1_motors)} fiziksel motor")
            self._set_detail(json.dumps([r.to_dict() for r in self.pdf1_motors], ensure_ascii=False, indent=2))
        except Exception as exc:
            self.status.configure(text="PDF 1 ANALİZ HATASI")
            messagebox.showerror("PDF 1 analiz hatası", str(exc))

    def _analyze_pdf2(self):
        try:
            self.pdf2_results = find_pdf2_motor_powers(self.pdf2)
            counters = {"Vantilatör": 0, "Aspiratör": 0}
            motors = []
            for result in self.pdf2_results:
                start_index = counters.get(result.component_type, 0) + 1
                records = build_pdf2_motor_records(result, start_index=start_index)
                motors.extend(records)
                counters[result.component_type] = start_index + len(records) - 1
            self.pdf2_motors = motors
            self.status.configure(text=f"PDF 2 hazır — {len(self.pdf2_motors)} fiziksel motor")
            self._set_detail(json.dumps([r.to_dict() for r in self.pdf2_motors], ensure_ascii=False, indent=2))
        except Exception as exc:
            self.status.configure(text="PDF 2 ANALİZ HATASI")
            messagebox.showerror("PDF 2 analiz hatası", str(exc))

    def compare(self):
        if not self.pdf1 or not self.pdf2:
            messagebox.showwarning("PDF eksik", "Karşılaştırma için hem PDF 1 hem PDF 2 seçilmelidir.")
            return
        self._analyze_pdf1()
        self._analyze_pdf2()
        self.comparisons = compare_motor_records(self.pdf1_motors, self.pdf2_motors)
        for item in self.tree.get_children():
            self.tree.delete(item)

        counts = {"MATCH": 0, "MISMATCH": 0, "ONLY_IN_PDF1": 0, "ONLY_IN_PDF2": 0}
        for result in self.comparisons:
            counts[result.status] = counts.get(result.status, 0) + 1
            self.tree.insert(
                "",
                "end",
                values=(
                    result.component_label,
                    result.component_type,
                    self._fmt(result.pdf1_kw),
                    self._fmt(result.pdf2_kw),
                    self._fmt(result.difference_kw),
                    result.status,
                    result.pdf1_page or "-",
                    result.pdf2_page or "-",
                ),
            )

        self.status.configure(
            text=(
                f"✓ {len(self.comparisons)} MOTOR — "
                f"EŞLEŞEN: {counts['MATCH']}  |  "
                f"FARKLI: {counts['MISMATCH']}  |  "
                f"SADECE PDF1: {counts['ONLY_IN_PDF1']}  |  "
                f"SADECE PDF2: {counts['ONLY_IN_PDF2']}"
            )
        )
        self._set_detail(json.dumps([r.to_dict() for r in self.comparisons], ensure_ascii=False, indent=2))

    @staticmethod
    def _fmt(value):
        return "-" if value is None else f"{value:g}"

    def _set_detail(self, text):
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", text)
        self.detail.configure(state="disabled")

    def save_json(self):
        if not self.comparisons:
            messagebox.showwarning("Sonuç yok", "Önce iki PDF seçip KARŞILAŞTIR çalıştırın.")
            return
        path = filedialog.asksaveasfilename(
            title="Karşılaştırma sonucunu kaydet",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return
        payload = {
            "version": VERSION,
            "pdf1": str(self.pdf1),
            "pdf2": str(self.pdf2),
            "pdf1_motors": [r.to_dict() for r in self.pdf1_motors],
            "pdf2_motors": [r.to_dict() for r in self.pdf2_motors],
            "comparison": [r.to_dict() for r in self.comparisons],
        }
        Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        messagebox.showinfo("Kaydedildi", f"Sonuç kaydedildi:\n{path}")


if __name__ == "__main__":
    App().mainloop()
