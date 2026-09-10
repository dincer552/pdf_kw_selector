"""Desktop GUI for PDF kW Selector - Project -> AHU -> Motor batch analysis."""
from __future__ import annotations
import hashlib
import json
import os
import re
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from pypdf import PdfReader

from ahu_matching import normalize_equipment_id, discover_equipment, match_ahu_lists, match_ahu_ids
from app_logger import clear_log, exception, info, log_directory, log_file, read_log, startup, warning
from batch_analysis import analyze_batch
from batch_input import discover_pdfs
from project_discovery import discover_project, normalize_project_name
from project_matching import match_project_names
from updater import apply_update, check_for_update, download_update, restart_with_update

VERSION = "v0.5.3"

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"PDF kW Selector {VERSION} — Batch Motor Analysis")
        self.geometry("1320x800")
        self.minsize(1120, 700)
        self.pdf1_inputs=[]; self.pdf2_inputs=[]; self.analysis=None; self._log_refresh_job=None
        self.report_callback_exception=self._report_callback_exception
        self._project_approved_variants:set[tuple[str,str]]=set(); self._ahu_approved_variants:set[tuple[str,str]]=set()
        self._build(); self.refresh_logs(); self._schedule_log_refresh(); info("GUI hazır",pdf1_count=0,pdf2_count=0)

    def _report_callback_exception(self,exc,value,tb):
        try:
            import traceback
            exception("YAKALANMAMIŞ GUI CALLBACK HATASI",value,callback_exception_type=getattr(exc,"__name__",str(exc)),traceback_text="".join(traceback.format_exception(exc,value,tb))); self.refresh_logs()
        except Exception as log_exc: exception("GUI callback hatası loglanırken ikinci hata oluştu",log_exc)
    def _schedule_log_refresh(self):
        try:
            if self.winfo_exists(): self._log_refresh_job=self.after(1000,self._scheduled_log_refresh)
        except Exception as exc: exception("Otomatik log yenileme zamanlayıcısı başlatılamadı",exc)
    def _scheduled_log_refresh(self):
        try: self.refresh_logs()
        except Exception as exc: exception("Otomatik log yenileme hatası",exc)
        finally: self._schedule_log_refresh()

    def _build(self):
        outer=ttk.Frame(self,padding=12); outer.pack(fill="both",expand=True); outer.columnconfigure(0,weight=1); outer.rowconfigure(2,weight=1)
        header=ttk.Frame(outer); header.grid(row=0,column=0,sticky="ew"); ttk.Label(header,text="PDF kW SELECTOR",font=("Segoe UI",19,"bold")).pack(side="left"); ttk.Label(header,text=f"{VERSION} • Project → AHU → Motor",font=("Segoe UI",10)).pack(side="right")
        top=ttk.Frame(outer); top.grid(row=1,column=0,sticky="ew",pady=(10,8)); top.columnconfigure(0,weight=1); top.columnconfigure(1,weight=1)
        self.pdf1_label=self._file_box(top,"PDF 1 — Seçim / Referans",0,self.add_pdf1_files,self.add_pdf1_folder); self.pdf2_label=self._file_box(top,"PDF 2 — Elektrik / Üretim",1,self.add_pdf2_files,self.add_pdf2_folder)
        notebook=ttk.Notebook(outer); notebook.grid(row=2,column=0,sticky="nsew")
        result=ttk.Frame(notebook,padding=8); result.columnconfigure(0,weight=1); result.rowconfigure(0,weight=1); notebook.add(result,text="SONUÇLAR")
        cols=("project","ahu","motor","type","pdf1","pdf2","diff","status","page1","page2"); headings={"project":"Proje","ahu":"AHU","motor":"Motor","type":"Tip","pdf1":"PDF1 kW","pdf2":"PDF2 kW","diff":"Fark","status":"Durum","page1":"PDF1","page2":"PDF2"}; widths={"project":220,"ahu":105,"motor":80,"type":110,"pdf1":80,"pdf2":80,"diff":70,"status":125,"page1":60,"page2":60}
        self.tree=ttk.Treeview(result,columns=cols,show="headings")
        for col in cols: self.tree.heading(col,text=headings[col]); self.tree.column(col,width=widths[col],anchor="center")
        self.tree.tag_configure("group_a",background="#f7f7f7"); self.tree.tag_configure("group_b",background="#ffffff"); self.tree.grid(row=0,column=0,sticky="nsew")
        scroll=ttk.Scrollbar(result,orient="vertical",command=self.tree.yview); scroll.grid(row=0,column=1,sticky="ns"); self.tree.configure(yscrollcommand=scroll.set)
        detail_frame=ttk.Frame(result); detail_frame.grid(row=1,column=0,columnspan=2,sticky="ew",pady=(8,0)); detail_frame.columnconfigure(0,weight=1); ttk.Label(detail_frame,text="Sonuç JSON / teknik detay").grid(row=0,column=0,sticky="w"); self.detail=tk.Text(detail_frame,height=7,wrap="word",font=("Consolas",9)); self.detail.grid(row=1,column=0,sticky="ew"); self.detail.configure(state="disabled")
        log_tab=ttk.Frame(notebook,padding=8); log_tab.columnconfigure(0,weight=1); log_tab.rowconfigure(1,weight=1); notebook.add(log_tab,text="HATA / İŞLEM LOGLARI"); ttk.Label(log_tab,text=f"Log dosyası: {log_file()}").grid(row=0,column=0,sticky="w",pady=(0,6)); self.log_text=tk.Text(log_tab,wrap="none",font=("Consolas",9)); self.log_text.grid(row=1,column=0,sticky="nsew")
        log_scroll_y=ttk.Scrollbar(log_tab,orient="vertical",command=self.log_text.yview); log_scroll_y.grid(row=1,column=1,sticky="ns"); log_scroll_x=ttk.Scrollbar(log_tab,orient="horizontal",command=self.log_text.xview); log_scroll_x.grid(row=2,column=0,sticky="ew"); self.log_text.configure(yscrollcommand=log_scroll_y.set,xscrollcommand=log_scroll_x.set)
        log_actions=ttk.Frame(log_tab); log_actions.grid(row=3,column=0,sticky="ew",pady=(6,0)); ttk.Button(log_actions,text="LOGLARI YENİLE",command=self.refresh_logs).pack(side="left"); ttk.Button(log_actions,text="LOG DOSYASINI AÇ",command=self.open_log_file).pack(side="left",padx=6); ttk.Button(log_actions,text="LOG KLASÖRÜ",command=self.open_log_directory).pack(side="left"); ttk.Button(log_actions,text="LOGLARI TEMİZLE",command=self.clear_logs).pack(side="left",padx=6)
        actions=ttk.Frame(outer); actions.grid(row=3,column=0,sticky="ew",pady=8); ttk.Button(actions,text="TOPLU ANALİZ",command=self.compare).pack(side="left"); ttk.Button(actions,text="SEÇİMLERİ TEMİZLE",command=self.clear_inputs).pack(side="left",padx=8); ttk.Button(actions,text="JSON KAYDET",command=self.save_json).pack(side="left"); ttk.Button(actions,text="GÜNCELLEME KONTROL ET",command=self.check_updates).pack(side="left",padx=8); self.status=ttk.Label(actions,text="PDF 1 ve PDF 2 tarafına dosya veya klasör ekleyin."); self.status.pack(side="right")
    def _file_box(self,parent,title,column,file_command,folder_command):
        box=ttk.LabelFrame(parent,text=title,padding=8); box.grid(row=0,column=column,sticky="nsew",padx=(0,5) if column==0 else (5,0)); label=ttk.Label(box,text="0 PDF seçildi",width=75); label.grid(row=0,column=0,columnspan=2,sticky="ew",pady=(0,6)); ttk.Button(box,text="PDF EKLE",command=file_command).grid(row=1,column=0,sticky="w"); ttk.Button(box,text="KLASÖR EKLE",command=folder_command).grid(row=1,column=1,sticky="w",padx=6); box.columnconfigure(0,weight=1); return label
    def _add_inputs(self,target):
        try:
            info("Dosya seçici açılıyor",target=target); paths=filedialog.askopenfilenames(title=f"{target} PDF dosyalarını seç",filetypes=[("PDF files","*.pdf"),("All files","*.*")]); info("Dosya seçici kapandı",target=target,selected_count=len(paths));
            if paths:self._merge_inputs(target,list(paths))
        except Exception as exc: exception("PDF dosya seçme hatası",exc,target=target); messagebox.showerror("Dosya seçme hatası",f"{type(exc).__name__}: {exc}")
    def _add_folder(self,target):
        try:
            info("Klasör seçici açılıyor",target=target); path=filedialog.askdirectory(title=f"{target} PDF klasörünü seç"); info("Klasör seçici kapandı",target=target,selected=path or None)
            if path:self._merge_inputs(target,[path])
        except Exception as exc: exception("PDF klasör seçme hatası",exc,target=target); messagebox.showerror("Klasör seçme hatası",f"{type(exc).__name__}: {exc}")
    def _merge_inputs(self,target,paths):
        try:
            current=self.pdf1_inputs if target=="PDF1" else self.pdf2_inputs; merged=discover_pdfs([item.path for item in current]+list(paths),recursive=True)
            if target=="PDF1":self.pdf1_inputs=merged;self._update_label(self.pdf1_label,merged)
            else:self.pdf2_inputs=merged;self._update_label(self.pdf2_label,merged)
            info("PDF giriş listesi güncellendi",target=target,count=len(merged),paths=[item.path for item in merged]);self.status.configure(text=f"{target}: {len(merged)} PDF hazır");self.refresh_logs()
        except Exception as exc: exception("PDF girişleri hazırlanamadı",exc,target=target,paths=list(paths));messagebox.showerror("PDF hazırlama hatası",f"{type(exc).__name__}: {exc}");self.refresh_logs()
    def _update_label(self,label,items):
        if not items:label.configure(text="0 PDF seçildi");return
        names=[Path(item.path).name for item in items[:3]];suffix=" ..." if len(items)>3 else "";label.configure(text=f"{len(items)} PDF: "+", ".join(names)+suffix)
    def add_pdf1_files(self):self._add_inputs("PDF1")
    def add_pdf1_folder(self):self._add_folder("PDF1")
    def add_pdf2_files(self):self._add_inputs("PDF2")
    def add_pdf2_folder(self):self._add_folder("PDF2")
    def clear_inputs(self):
        self.pdf1_inputs,self.pdf2_inputs=[],[];self.analysis=None;self._project_approved_variants.clear();self._ahu_approved_variants.clear();self._update_label(self.pdf1_label,[]);self._update_label(self.pdf2_label,[]);[self.tree.delete(i) for i in self.tree.get_children()];self._set_detail("");self.status.configure(text="Seçimler temizlendi.");info("PDF seçimleri temizlendi");self.refresh_logs()

    def _read_pages(self,path):
        return [(page.extract_text() or "") for page in PdfReader(str(path)).pages]
    def _read_project_text(self,path):
        try:return discover_project(path).project_name
        except Exception as exc:warning("Proje adı GUI tarafında okunamadı",path=str(path),reason=str(exc));return None

    def _project_variants(self):
        pdf1={};pdf2={}
        for item in self.pdf1_inputs:
            p=self._read_project_text(item.path)
            if p:pdf1.setdefault(normalize_project_name(p),p)
        for item in self.pdf2_inputs:
            p=self._read_project_text(item.path)
            if p:pdf2.setdefault(normalize_project_name(p),p)
        pairs=[]
        for ln,lv in pdf1.items():
            for rn,rv in pdf2.items():
                if ln==rn: continue
                m=match_project_names(lv,rv); pairs.append((m.score,lv,rv,ln,rn))
        return sorted(pairs,key=lambda x:x[0],reverse=True)

    def _confirm_projects(self):
        # Never silently discard a differently named project. Ask once per exact normalized variant pair.
        for score,left,right,ln,rn in self._project_variants():
            key=(ln,rn)
            if key in self._project_approved_variants: continue
            answer=messagebox.askyesno("Proje eşleşmesi onayı",f"PDF1 Projesi:\n\n{left}\n\nPDF2 Projesi:\n\n{right}\n\nBunlar aynı proje mi?\n\nBenzerlik: {score:.0%}")
            if not answer:
                warning("Kullanıcı proje eşleşmesini reddetti",left=left,right=right,score=score); return False
            self._project_approved_variants.add(key);info("Kullanıcı proje eşleşmesini onayladı",left=left,right=right,score=score)
        return True

    @staticmethod
    def _ahu_family(value):
        n=normalize_equipment_id(value)
        return re.sub(r"\d+","#",n)
    def _discover_project_ahu_ids(self,documents):
        ids=[]
        for document in documents:
            try: ids.extend(discover_equipment(document.path).equipment_ids)
            except Exception as exc: exception("AHU keşfi kullanıcı onayından önce başarısız",exc,path=document.path)
        return ids
    def _confirm_ahu_pairs(self):
        # Build actual AHU candidates directly from selected files, so ONLY_IN_PDF entries are also reviewable.
        left_ids=self._discover_project_ahu_ids(self.pdf1_inputs);right_ids=self._discover_project_ahu_ids(self.pdf2_inputs)
        left_unique={x.normalized:x for x in left_ids};right_unique={x.normalized:x for x in right_ids}
        ordered=[]
        for lid,lo in left_unique.items():
            for rid,ro in right_unique.items():
                m=match_ahu_ids(lid,rid,left_page=lo.page,right_page=ro.page)
                # Show plausible variants; once a family is approved, the same structural mapping is reused.
                if m.status in {"REVIEW_REQUIRED","NO_MATCH"}:
                    family_score=1.0 if self._ahu_family(lid)==self._ahu_family(rid) else m.score
                    if family_score>=0.35: ordered.append((family_score,lid,rid))
        ordered.sort(key=lambda x:x[0],reverse=True)
        for score,lid,rid in ordered:
            key=(lid,rid)
            if key in self._ahu_approved_variants: continue
            answer=messagebox.askyesno("AHU eşleşmesi onayı",f"PDF1 AHU:\n\n{lid}\n\nPDF2 AHU:\n\n{rid}\n\nBunlar aynı AHU mu?\n\nBen bu onaydan sonra aynı adlandırma farkını diğer numaralı AHU'larda da kullanacağım.")
            if not answer:
                warning("Kullanıcı AHU eşleşmesini reddetti",left=lid,right=rid,score=score); return False
            self._ahu_approved_variants.add(key);info("Kullanıcı AHU eşleşmesini onayladı",left=lid,right=rid,score=score)
        return True

    def compare(self):
        if not self.pdf1_inputs or not self.pdf2_inputs:
            messagebox.showwarning("PDF eksik","PDF 1 ve PDF 2 tarafına en az bir PDF veya klasör ekleyin.");return
        try:
            if not self._confirm_projects():self.status.configure(text="Proje eşleşmesi kullanıcı tarafından reddedildi.");return
            # The batch engine must already see the approved project relation. Patch project pairing only for this run.
            from batch_analysis import match_discoveries as _original_project_match
            import batch_analysis as ba
            original_pd_match=ba.match_discoveries
            def project_match_with_user_approval(left,right):
                m=original_pd_match(left,right)
                key=(normalize_project_name(left.project_name or ""),normalize_project_name(right.project_name or ""))
                if key in self._project_approved_variants:
                    return type(m)(m.left_name,m.right_name,m.left_normalized,m.right_normalized,max(m.score,0.90),"APPROVED_FLEXIBLE", "user-approved project variant",m.left_source,m.right_source)
                return m
            ba.match_discoveries=project_match_with_user_approval
            try:self.analysis=analyze_batch(self.pdf1_inputs,self.pdf2_inputs)
            finally:ba.match_discoveries=original_pd_match
            if not self._confirm_ahu_pairs():
                self.status.configure(text="AHU eşleşmesi kullanıcı tarafından reddedildi.");return
            original_ahu_match=ba.match_ahu_lists
            try:ba.match_ahu_lists=lambda left,right: match_ahu_lists(left,right,approved_variants=self._ahu_approved_variants);self.analysis=analyze_batch(self.pdf1_inputs,self.pdf2_inputs)
            finally:ba.match_ahu_lists=original_ahu_match
            self._render_results()
        except Exception as exc:
            exception("GUI toplu analiz hatası",exc);messagebox.showerror("Analiz hatası",f"{type(exc).__name__}: {exc}");self.refresh_logs()

    # Existing render/log/save/update methods remain part of the class in the repository's generated build.
