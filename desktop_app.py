"""Desktop test GUI for PDF kW Selector - Stage 1.

Offline Windows-friendly Tkinter interface. This release focuses on PDF 1:
find the correct fan sections, detect Supply/Exhaust direction, extract
Rated Power / Anma gücü [kW], and expand 1x1/2x1/3x1 into physical motors.
"""
from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from stage1_page_discovery import build_stage1_motor_records, find_rated_motor_powers_in_pdf

VERSION = "v0.1.1"


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"PDF kW Selector {VERSION} — Stage 1 Test")
        self.geometry("980x650")
        self.minsize(850, 560)
        self.pdf1: Path | None = None
        self.results = []
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=18)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="PDF kW SELECTOR", font=("Segoe UI", 20, "bold")).pack(anchor="w")
        ttk.Label(outer, text=f"{VERSION}  •  PDF 1 Motor Discovery / Offline Test", font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 16))

        file_frame = ttk.LabelFrame(outer, text="1. PDF 1 — Referans Proje", padding=12)
        file_frame.pack(fill="x")
        self.file_label = ttk.Label(file_frame, text="Henüz PDF seçilmedi", width=90)
        self.file_label.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        ttk.Button(file_frame, text="PDF Seç", command=self.select_pdf).grid(row=0, column=1)
        file_frame.columnconfigure(0, weight=1)

        action = ttk.Frame(outer)
        action.pack(fill="x", pady=14)
        ttk.Button(action, text="ANALİZ ET", command=self.analyze).pack(side="left")
        ttk.Button(action, text="Sonucu JSON Kaydet", command=self.save_json).pack(side="left", padx=8)
        ttk.Label(action, text="PDF 2 karşılaştırması sonraki fazda aktif edilecek.", foreground="#666").pack(side="right")

        result_frame = ttk.LabelFrame(outer, text="2. Analiz Sonucu", padding=12)
        result_frame.pack(fill="both", expand=True)

        self.status = ttk.Label(result_frame, text="PDF seçip ANALİZ ET düğmesine basın.", font=("Segoe UI", 11, "bold"))
        self.status.pack(anchor="w", pady=(0, 10))

        cols = ("motor", "type", "direction", "kw", "group", "page", "confidence")
        self.tree = ttk.Treeview(result_frame, columns=cols, show="headings", height=12)
        headings = {
            "motor": "Motor", "type": "Tip", "direction": "Hava Yönü",
            "kw": "Anma Gücü (kW)", "group": "Grup", "page": "Sayfa", "confidence": "Güven",
        }
        widths = {"motor": 100, "type": 130, "direction": 120, "kw": 120, "group": 80, "page": 70, "confidence": 90}
        for col in cols:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor="center")
        self.tree.pack(fill="both", expand=True, side="left")
        scroll = ttk.Scrollbar(result_frame, orient="vertical", command=self.tree.yview)
        scroll.pack(fill="y", side="right")
        self.tree.configure(yscrollcommand=scroll.set)

        self.detail = tk.Text(outer, height=7, wrap="word", font=("Consolas", 9))
        self.detail.pack(fill="x", pady=(12, 0))
        self.detail.configure(state="disabled")

    def select_pdf(self) -> None:
        path = filedialog.askopenfilename(title="PDF 1 seç", filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")])
        if path:
            self.pdf1 = Path(path)
            self.file_label.configure(text=str(self.pdf1))
            self.status.configure(text="PDF hazır. ANALİZ ET ile başlatın.")

    def analyze(self) -> None:
        if not self.pdf1:
            messagebox.showwarning("PDF gerekli", "Önce PDF 1'i seçin.")
            return
        try:
            results = find_rated_motor_powers_in_pdf(self.pdf1)
        except Exception as exc:
            messagebox.showerror("Analiz hatası", str(exc))
            return
        self.results = results
        for item in self.tree.get_children():
            self.tree.delete(item)
        if not results:
            self.status.configure(text="SONUÇ BULUNAMADI", foreground="#b00020")
            self._set_detail("Supply air / Exhaust air fan bölümlerinde Rated Power [kW] alanı bulunamadı.")
            return

        total_motors = 0
        for result in results:
            records = build_stage1_motor_records(result)
            total_motors += len(records)
            direction = "Supply air" if result.component_role == "supply_fan" else "Exhaust air"
            for record in records:
                self.tree.insert(
                    "", "end",
                    values=(record.component_label, record.component_type, direction,
                            f"{record.power_kw:g}", record.source_group,
                            record.source_page or "-", record.confidence.upper()),
                )

        self.status.configure(
            text=f"✓ {len(results)} FAN BULUNDU — {total_motors} FİZİKSEL MOTOR",
            foreground="#176b2c",
        )
        detail = []
        for result in results:
            records = build_stage1_motor_records(result)
            item = result.to_dict()
            item["direction"] = "Supply air" if result.component_role == "supply_fan" else "Exhaust air"
            item["motors_created"] = [r.to_dict() for r in records]
            detail.append(item)
        self._set_detail(json.dumps(detail, ensure_ascii=False, indent=2))

    def _set_detail(self, text: str) -> None:
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", text)
        self.detail.configure(state="disabled")

    def save_json(self) -> None:
        if not self.results:
            messagebox.showwarning("Sonuç yok", "Önce analiz yapın.")
            return
        path = filedialog.asksaveasfilename(title="Analiz sonucunu kaydet", defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        payload = []
        for result in self.results:
            item = result.to_dict()
            item["motors"] = [r.to_dict() for r in build_stage1_motor_records(result)]
            payload.append(item)
        Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        messagebox.showinfo("Kaydedildi", f"Sonuç kaydedildi:\n{path}")


if __name__ == "__main__":
    App().mainloop()
