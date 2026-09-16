"""Grouped desktop entry point for PDF kW Selector."""
from __future__ import annotations
from pathlib import Path
import re
import sys
import time
from tkinter import ttk, messagebox
import desktop_app as desktop_module
from app_logger import exception, info, startup
from desktop_app import App as BaseApp, VERSION
from drag_drop import install_pdf_drop_targets
from pdf_viewer import open_pdf_at_page
from result_grouping import group_result_rows
from updater import apply_update
from confirmation_workflow import analyze_with_confirmations
from pdf_master_scan import scan_pdf
from status import install_status_display

def _path_strings(items): return [str(getattr(item,"path",item)) for item in (items or [])]
def _confirmed_analyze(pdf1_inputs,pdf2_inputs,progress_callback=None):
    p1,p2=_path_strings(pdf1_inputs),_path_strings(pdf2_inputs); info("Onaylı analiz girişleri normalize edildi",pdf1_count=len(p1),pdf2_count=len(p2)); return analyze_with_confirmations(p1,p2,progress_callback=progress_callback)
desktop_module.analyze_batch=_confirmed_analyze

class GroupedApp(BaseApp):
    def __init__(self):
        super().__init__(); self._analysis_started_at=None; self._grouped_pdf1_scan_cache={}; self._ebm_pdf_keys=set(); self._vocclean_pdf_keys=set(); self._sysreco_pdf_keys=set(); self._unmatched_pdf_keys=set(); self._pdf_accounting_error_shown=False; self._build_ebm_tab(); self._build_voclean_tab(); self._build_sysreco_tab(); self.tabs.tab(0,text="DANFOS"); self.tabs.insert(1,self.ebm_tab); self.tabs.insert(2,self.voclean_tab); self.tabs.insert(3,self.sysreco_tab); self.unmatched_tab_index=lambda:4; self.tree.tag_configure("mismatch",background="#ffb3b3",foreground="#000000"); install_pdf_drop_targets(self,self.pdf1_box,self.pdf2_box); install_status_display(self)
    def _build_ebm_tab(self):
        tab=ttk.Frame(self.tabs, style="White.TFrame"); self.tabs.add(tab,text="EBM-PAPST (0)"); cols=("Proje","AHU","Seçim çıktısı","Elektrik p.","Durum"); self.ebm_tree=ttk.Treeview(tab,columns=cols,show="headings"); widths={"Proje":300,"AHU":120,"Seçim çıktısı":300,"Elektrik p.":420,"Durum":260}
        for col in cols:self.ebm_tree.heading(col,text=col);self.ebm_tree.column(col,width=widths[col],anchor="w")
        scroll=ttk.Scrollbar(tab,orient="vertical",command=lambda *args: (self.ebm_tree.yview(*args), self._cell_hover_box.hide()));self.ebm_tree.configure(yscrollcommand=scroll.set);self.ebm_tree.pack(side="left",fill="both",expand=True,padx=(5,0),pady=5);scroll.pack(side="right",fill="y",padx=(0,5),pady=5);self.ebm_tab=tab
        self._ebm_cell_data: dict[str, dict] = {}
        self.ebm_tree.bind("<Button-1>", self._on_ebm_cell_click)
        self.ebm_tree.bind("<Double-1>", self._on_ebm_cell_click)
        self.ebm_tree.bind("<Motion>", self._on_ebm_cell_motion)
        self.ebm_tree.bind("<Leave>", lambda e: (self.ebm_tree.configure(cursor=""), self._cell_hover_box.hide()))
        self.ebm_tree.bind("<MouseWheel>", lambda e: self._cell_hover_box.hide(), add="+")
    def _build_voclean_tab(self):
        tab=ttk.Frame(self.tabs, style="White.TFrame"); self.tabs.add(tab,text="VOCLEAN (0)"); cols=("Proje","PDF1","VOClean kW","PDF1 Sayfa","PDF2","AHU","Durum"); self.voclean_tree=ttk.Treeview(tab,columns=cols,show="headings"); widths={"Proje":260,"PDF1":300,"VOClean kW":100,"PDF1 Sayfa":90,"PDF2":300,"AHU":180,"Durum":280}
        for col in cols:self.voclean_tree.heading(col,text=col);self.voclean_tree.column(col,width=widths[col],anchor="w")
        scroll=ttk.Scrollbar(tab,orient="vertical",command=lambda *args: (self.voclean_tree.yview(*args), self._cell_hover_box.hide()));self.voclean_tree.configure(yscrollcommand=scroll.set);self.voclean_tree.pack(side="left",fill="both",expand=True,padx=(5,0),pady=5);scroll.pack(side="right",fill="y",padx=(0,5),pady=5);self.voclean_tab=tab
        self._vocclean_cell_data: dict[str, dict] = {}
        self.voclean_tree.bind("<Button-1>", self._on_voclean_cell_click)
        self.voclean_tree.bind("<Double-1>", self._on_voclean_cell_click)
        self.voclean_tree.bind("<Motion>", self._on_voclean_cell_motion)
        self.voclean_tree.bind("<Leave>", lambda e: (self.voclean_tree.configure(cursor=""), self._cell_hover_box.hide()))
        self.voclean_tree.bind("<MouseWheel>", lambda e: self._cell_hover_box.hide(), add="+")
    def _build_sysreco_tab(self):
        tab=ttk.Frame(self.tabs, style="White.TFrame"); self.tabs.add(tab,text="SYSRECO (0)"); cols=("Proje","AHU","PDF","SysReco Model"); self.sysreco_tree=ttk.Treeview(tab,columns=cols,show="headings"); widths={"Proje":320,"AHU":180,"PDF":420,"SysReco Model":180}
        for col in cols:self.sysreco_tree.heading(col,text=col);self.sysreco_tree.column(col,width=widths[col],anchor="w")
        scroll=ttk.Scrollbar(tab,orient="vertical",command=lambda *args: (self.sysreco_tree.yview(*args), self._cell_hover_box.hide()));self.sysreco_tree.configure(yscrollcommand=scroll.set);self.sysreco_tree.pack(side="left",fill="both",expand=True,padx=(5,0),pady=5);scroll.pack(side="right",fill="y",padx=(0,5),pady=5);self.sysreco_tab=tab
        self._sysreco_cell_data: dict[str, dict] = {}
        self.sysreco_tree.bind("<Button-1>", self._on_sysreco_cell_click)
        self.sysreco_tree.bind("<Double-1>", self._on_sysreco_cell_click)
        self.sysreco_tree.bind("<Motion>", self._on_sysreco_cell_motion)
        self.sysreco_tree.bind("<Leave>", lambda e: (self.sysreco_tree.configure(cursor=""), self._cell_hover_box.hide()))
        self.sysreco_tree.bind("<MouseWheel>", lambda e: self._cell_hover_box.hide(), add="+")
    def _grouped_scan_pdf1(self,document):
        key=str(document.path).casefold(); scan=self._grouped_pdf1_scan_cache.get(key)
        if scan is None: scan=scan_pdf(document.path,"PDF1"); self._grouped_pdf1_scan_cache[key]=scan
        return scan
    def _special_pdf_sets(self):
        ebm=set(); voc=set(); sysr=set(); accepted={"EXACT","NORMALIZED_MATCH","USER_APPROVED"}
        for document in self.analysis.pdf1_documents:
            key=("PDF1",str(document.path).casefold()); scan=self._grouped_scan_pdf1(document)
            if scan.pdf1_ebm_pages: ebm.add(key)
            if any(self._is_voclean_text(text) for text in scan.page_texts): voc.add(key)
            if self._is_sysreco_text("\n".join(scan.page_texts)): sysr.add(key)
        for ahu in self.analysis.ahu_matches:
            if getattr(ahu.match,"status","") not in accepted: continue
            pdf1_keys={("PDF1",str(p).casefold()) for p in ahu.pdf1_files}
            if pdf1_keys & ebm: ebm.update(("PDF2",str(p).casefold()) for p in ahu.pdf2_files)
        for document in self.analysis.pdf2_documents:
            if self._is_voclean_document(document,"PDF2"): voc.add(("PDF2",str(document.path).casefold()))
        voc-=ebm; sysr-=ebm; sysr-=voc
        self._ebm_pdf_keys=ebm; self._vocclean_pdf_keys=voc; self._sysreco_pdf_keys=sysr
        return ebm,voc,sysr
    @staticmethod
    def _vocclean_power_prefix(value_kw): return f"BA{int(round(float(value_kw)*100)):03d}-"
    @staticmethod
    def _is_voclean_text(text): return bool(re.search(r"\bVOC\s*LEAN\b",text or "",re.I))
    def _is_voclean_document(self,document,side=None):