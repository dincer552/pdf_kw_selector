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
from pdf_master_scan import scan_pdfs
from updater import check_for_update, download_update, restart_with_update
from ahu_matching import normalize_equipment_id
from build_info import BUILD_SHA, BUILD_VERSION
VERSION=BUILD_VERSION
UPDATE_CHECK_INTERVAL_MS=15*60*1000
class App(tk.Tk):
    def __init__(self):
        super().__init__(); self.title(f"PDF kW Selector {VERSION} — Batch Motor Analysis"); self.geometry("1300x820"); self.minsize(1100,700); self.pdf1_inputs=[]; self.pdf2_inputs=[]; self.analysis=None; self._analysis_running=False; self._update_check_running=False; self._available_update=None; self._build_ui(); self.after(5000,self._schedule_update_check)
    def _build_ui(self):
        top=ttk.Frame(self,padding=8); top.pack(fill="x"); ttk.Label(top,text="PDF kW SELECTOR",font=("Segoe UI",18,"bold")).pack(side="left"); ttk.Label(top,text=f"{VERSION} • Project → AHU → Motor").pack(side="right",pady=8); self.update_check_button=ttk.Button(top,text="↻",width=3,command=self._manual_update_check); self.update_check_button.pack(side="right",padx=(0,8))
        boxes=ttk.Frame(self,padding=(8,0)); boxes.pack(fill="x"); self.pdf1_label,self.pdf1_box=self._file_box(boxes,"Seçim çıktısı","PDF1"); self.pdf2_label,self.pdf2_box=self._file_box(boxes,"Elektrik projesi","PDF2"); self.pdf1_box.pack(side="left",fill="x",expand=True,padx=(0,5)); self.pdf2_box.pack(side="left",fill="x",expand=True,padx=(5,0))
        tabs=ttk.Notebook(self); tabs.pack(fill="both",expand=True,padx=8,pady=(6,0)); self.tabs=tabs; result_tab=ttk.Frame(tabs); unmatched_tab=ttk.Frame(tabs); log_tab=ttk.Frame(tabs); tabs.add(result_tab,text="SONUÇLAR"); tabs.add(unmatched_tab,text="EŞLEŞMEYEN PDF'LER (0)"); tabs.add(log_tab,text="HATA / İŞLEM LOGLARI")
        cols=("Proje","AHU","Motor","Seçim kW","Elektrik P. kW","Durum"); self.tree=ttk.Treeview(result_tab,columns=cols,show="headings"); [self.tree.heading(c,text=c) for c in cols]; self.tree.pack(fill="both",expand=True,padx=5,pady=5)
        unmatched_cols=("Taraf","PDF","Proje","AHU","Neden"); self.unmatched_tree=ttk.Treeview(unmatched_tab,columns=unmatched_cols,show="headings"); [self.unmatched_tree.heading(c,text=c) for c in unmatched_cols]; self.unmatched_tree.pack(fill="both",expand=True,padx=5,pady=5)
        detail_frame=ttk.LabelFrame(result_tab,text="Sonuç JSON / teknik detay",padding=5); detail_frame.pack(fill="both",expand=False,padx=8,pady=4); self.detail=tk.Text(detail_frame,height=6,wrap="none"); self.detail.pack(fill="both",expand=True); self.detail.configure(state="disabled")
        self.update_progress=tk.DoubleVar(value=0); self.update_detail=tk.StringVar(value="Güncelleme hazır"); progress=ttk.Frame(self,padding=(5,0)); self.update_panel=progress; ttk.Label(progress,textvariable=self.update_detail,anchor="e").pack(side="right"); self.update_bar=ttk.Progressbar(progress,variable=self.update_progress,maximum=100,length=360); self.update_bar.pack(side="right",padx=8)
        buttons=ttk.Frame(self,padding=5); buttons.pack(fill="x"); ttk.Button(buttons,text="TOPLU ANALİZ",command=self.compare).pack(side="left",padx=3); ttk.Button(buttons,text="SEÇİMLERİ TEMİZLE",command=self.clear_inputs).pack(side="left",padx=3); ttk.Button(buttons,text="JSON KAYDET",command=self.save_json).pack(side="left",padx=3); self.status=ttk.Label(buttons,text="Hazır",anchor="e"); self.status.pack(side="right")
        self.log_text=tk.Text(log_tab,wrap="none"); self.log_text.pack(fill="both",expand=True,padx=5,pady=5); self.refresh_logs()
    def _manual_update_check(self): return
    def _spin_update_check_button(self): return
    def _file_box(self,parent,title,side):
        frame=ttk.LabelFrame(parent,text=title,padding=6); label=ttk.Label(frame,text="0 PDF seçildi"); label.pack(side="left",fill="x",expand=True); ttk.Button(frame,text="PDF EKLE",command=lambda:self.add_files(side)).pack(side="right",padx=2); ttk.Button(frame,text="KLASÖR EKLE",command=lambda:self.add_folder(side)).pack(side="right",padx=2); return label,frame
    def add_files(self,side): self._merge_inputs(side,list(filedialog.askopenfilenames(title=f"{side} PDF seç",filetypes=[("PDF","*.pdf")])) )
    def add_folder(self,side):
        path=filedialog.askdirectory(title=f"{side} PDF klasörü seç");
        if path:self._merge_inputs(side,[path])
    def _merge_inputs(self,side,paths):
        discovered=discover_pdfs(paths,recursive=True); target=self.pdf1_inputs if side=="PDF1" else self.pdf2_inputs; known={str(x.path).casefold() for x in target}; target.extend(x for x in discovered if str(x.path).casefold() not in known); label=self.pdf1_label if side=="PDF1" else self.pdf2_label; label.configure(text=f"{len(target)} PDF")
    def clear_inputs(self): return
    def _clear_grouped_results(self): return
    def compare(self):
        if self._analysis_running:return
        if not self.pdf1_inputs or not self.pdf2_inputs: messagebox.showwarning("Eksik seçim","PDF1 ve PDF2 tarafına en az birer PDF/klasör ekleyin."); return
        self._analysis_running=True; threading.Thread(target=self._prepare_analysis,args=([str(x.path) for x in self.pdf1_inputs],[str(x.path) for x in self.pdf2_inputs]),daemon=True).start()
    def _prepare_analysis(self,pdf1_paths,pdf2_paths):
        try:self.analysis=analyze_batch(pdf1_paths,pdf2_paths); self.after(0,self._render_analysis)
        except Exception as exc:self.after(0,self._analysis_failed,exc)
    def _render_analysis(self):
        for item in self.tree.get_children():self.tree.delete(item)
        for c in self.analysis.motor_comparisons:self.tree.insert("","end",values=("-",c.equipment_id,c.component_label,self._fmt(c.pdf1_kw),self._fmt(c.pdf2_kw),c.status))
        self._analysis_running=False
    def _render_unmatched(self): return
    def _clear_unmatched(self): return
    def _analysis_failed(self,exc): self._analysis_running=False; messagebox.showerror("Analiz hatası",str(exc))
    def _analysis_progress(self,*args): pass
    def _set_detail(self,text): self.detail.configure(state="normal"); self.detail.delete("1.0","end"); self.detail.insert("1.0",text); self.detail.configure(state="disabled")
    def _fmt(self,value): return "-" if value is None else f"{value:g}"
    def _schedule_update_check(self): self.after(UPDATE_CHECK_INTERVAL_MS,self._schedule_update_check)
    def _check_updates_background(self): return
    def download_available_update(self): return
    def refresh_logs(self): return
    def open_log_file(self): return
    def open_log_directory(self): return
    def clear_logs(self): return
    def save_json(self): return
