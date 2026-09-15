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
from result_grouping import group_result_rows
from updater import apply_update
from confirmation_workflow import analyze_with_confirmations
from pdf_master_scan import scan_pdf

def _path_strings(items): return [str(getattr(item,"path",item)) for item in (items or [])]
def _confirmed_analyze(pdf1_inputs,pdf2_inputs,progress_callback=None):
    p1,p2=_path_strings(pdf1_inputs),_path_strings(pdf2_inputs); info("Onaylı analiz girişleri normalize edildi",pdf1_count=len(p1),pdf2_count=len(p2)); return analyze_with_confirmations(p1,p2,progress_callback=progress_callback)
desktop_module.analyze_batch=_confirmed_analyze

class GroupedApp(BaseApp):
    def __init__(self):
        super().__init__(); self._analysis_started_at=None; self._grouped_pdf1_scan_cache={}; self._ebm_pdf_keys=set(); self._vocclean_pdf_keys=set(); self._sysreco_pdf_keys=set(); self._unmatched_pdf_keys=set(); self._pdf_accounting_error_shown=False; self._build_ebm_tab(); self._build_voclean_tab(); self._build_sysreco_tab(); self.tabs.tab(0,text="DANFOS"); self.tabs.insert(1,self.ebm_tab); self.tabs.insert(2,self.voclean_tab); self.tabs.insert(3,self.sysreco_tab); self.unmatched_tab_index=lambda:4; self.tree.tag_configure("mismatch",background="#ffb3b3",foreground="#000000"); install_pdf_drop_targets(self,self.pdf1_box,self.pdf2_box)
    def _build_ebm_tab(self):
        tab=ttk.Frame(self.tabs, style="White.TFrame"); self.tabs.add(tab,text="EBM-PAPST (0)"); cols=("Proje","AHU","Seçim çıktısı","Elektrik p.","Durum"); self.ebm_tree=ttk.Treeview(tab,columns=cols,show="headings"); widths={"Proje":300,"AHU":120,"Seçim çıktısı":300,"Elektrik p.":420,"Durum":260}
        for col in cols:self.ebm_tree.heading(col,text=col);self.ebm_tree.column(col,width=widths[col],anchor="w")
        scroll=ttk.Scrollbar(tab,orient="vertical",command=self.ebm_tree.yview);self.ebm_tree.configure(yscrollcommand=scroll.set);self.ebm_tree.pack(side="left",fill="both",expand=True,padx=(5,0),pady=5);scroll.pack(side="right",fill="y",padx=(0,5),pady=5);self.ebm_tab=tab
    def _build_voclean_tab(self):
        tab=ttk.Frame(self.tabs, style="White.TFrame"); self.tabs.add(tab,text="VOCLEAN (0)"); cols=("Proje","PDF1","VOClean kW","PDF1 Sayfa","PDF2","AHU","Durum"); self.voclean_tree=ttk.Treeview(tab,columns=cols,show="headings"); widths={"Proje":260,"PDF1":300,"VOClean kW":100,"PDF1 Sayfa":90,"PDF2":300,"AHU":180,"Durum":280}
        for col in cols:self.voclean_tree.heading(col,text=col);self.voclean_tree.column(col,width=widths[col],anchor="w")
        scroll=ttk.Scrollbar(tab,orient="vertical",command=self.voclean_tree.yview);self.voclean_tree.configure(yscrollcommand=scroll.set);self.voclean_tree.pack(side="left",fill="both",expand=True,padx=(5,0),pady=5);scroll.pack(side="right",fill="y",padx=(0,5),pady=5);self.voclean_tab=tab
    def _build_sysreco_tab(self):
        tab=ttk.Frame(self.tabs, style="White.TFrame"); self.tabs.add(tab,text="SYSRECO (0)"); cols=("Proje","AHU","PDF","SysReco Model"); self.sysreco_tree=ttk.Treeview(tab,columns=cols,show="headings"); widths={"Proje":320,"AHU":180,"PDF":420,"SysReco Model":180}
        for col in cols:self.sysreco_tree.heading(col,text=col);self.sysreco_tree.column(col,width=widths[col],anchor="w")
        scroll=ttk.Scrollbar(tab,orient="vertical",command=self.sysreco_tree.yview);self.sysreco_tree.configure(yscrollcommand=scroll.set);self.sysreco_tree.pack(side="left",fill="both",expand=True,padx=(5,0),pady=5);scroll.pack(side="right",fill="y",padx=(0,5),pady=5);self.sysreco_tab=tab
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
        if side == "PDF2": return "voclean" in str(getattr(getattr(document,"project",None),"project_name","") or "").casefold()
        return ("PDF1",str(document.path).casefold()) in self._vocclean_pdf_keys
    @staticmethod
    def _is_sysreco_text(text): return bool(re.search(r"\bSysReco\b",text or "",re.I))
    @staticmethod
    def _sysreco_models(text): return list(dict.fromkeys(m.group(0).strip() for m in re.finditer(r"\bSysReco\s+FX\d+\b",text or "",re.I)))
    def _sysreco_documents(self):
        self._special_pdf_sets(); result=[]
        for document in self.analysis.pdf1_documents:
            if ("PDF1",str(document.path).casefold()) not in self._sysreco_pdf_keys: continue
            scan=self._grouped_scan_pdf1(document); result.append((document,"\n".join(scan.page_texts)))
        return result
    def _render_voclean(self):
        for item in self.voclean_tree.get_children(): self.voclean_tree.delete(item)
        self._special_pdf_sets(); rows=[]
        for document in self.analysis.pdf1_documents:
            key=("PDF1",str(document.path).casefold())
            if key not in self._vocclean_pdf_keys: continue
            scan=self._grouped_scan_pdf1(document); motor_results=list(scan.pdf1_motors)
            if not motor_results: rows.append((document.project.project_name or "-",Path(document.path).name,"-","-","-","-","VOClean bulundu; Plug fan kW bulunamadı")); continue
            for motor in motor_results:
                if motor.value_kw is None: continue
                prefix=self._vocclean_power_prefix(motor.value_kw).upper(); matches=[]
                for pdf2_document in self.analysis.pdf2_documents:
                    for ahu in pdf2_document.equipment:
                        ahu_text=str(ahu).strip()
                        if ahu_text.upper().startswith(prefix): matches.append((pdf2_document,ahu_text))
                if matches:
                    for pdf2_document,ahu_text in matches: rows.append((document.project.project_name or "-",Path(document.path).name,f"{motor.value_kw:g}",str(motor.page_number),Path(pdf2_document.path).name,ahu_text,f"BA kodu eşleşti ({prefix[:-1]})"))
                else: rows.append((document.project.project_name or "-",Path(document.path).name,f"{motor.value_kw:g}",str(motor.page_number),"-","-",f"PDF2 AHU eşleşmesi yok; beklenen {prefix[:-1]}-xxxxx"))
        rows.sort(key=lambda r:(str(r[0]).casefold(),str(r[1]).casefold(),str(r[3]),str(r[5]).casefold()))
        for row in rows:self.voclean_tree.insert("","end",values=row)
        self.tabs.tab(self.voclean_tab,text=f"VOCLEAN ({len(self._vocclean_pdf_keys)})")
    def _render_sysreco(self):
        for item in self.sysreco_tree.get_children(): self.sysreco_tree.delete(item)
        self._special_pdf_sets(); rows=[]
        for document,full_text in self._sysreco_documents():
            models=self._sysreco_models(full_text) or ["SysReco modeli bulunamadı"]
            for model in models: rows.append((document.project.project_name or "-",", ".join(str(value) for value in document.equipment) if document.equipment else "-",Path(document.path).name,model))
        rows.sort(key=lambda r:(str(r[0]).casefold(),str(r[1]).casefold(),str(r[2]).casefold(),str(r[3]).casefold()))
        for row in rows:self.sysreco_tree.insert("","end",values=row)
        self.tabs.tab(self.sysreco_tab,text=f"SYSRECO ({len(self._sysreco_pdf_keys)})")
    def _render_ebm(self):
        for item in self.ebm_tree.get_children(): self.ebm_tree.delete(item)
        self._special_pdf_sets(); rows=[]
        for document in self.analysis.pdf1_documents:
            key=("PDF1",str(document.path).casefold())
            if key not in self._ebm_pdf_keys: continue
            matching=[]
            for ahu in self.analysis.ahu_matches:
                if getattr(ahu.match,"status","") not in {"EXACT","NORMALIZED_MATCH","USER_APPROVED"}: continue
                if str(document.path).casefold() in {str(p).casefold() for p in ahu.pdf1_files}: matching.extend(ahu.pdf2_files)
            pdf2=", ".join(Path(p).name for p in dict.fromkeys(matching)) or "-"; status="PDF2 AHU eşleşti; motor kW karşılaştırması yapılmadı" if matching else "PDF2 AHU eşleşmesi yok"
            for ahu_id in tuple(document.equipment) or ("-",): rows.append((document.project.project_name or "-",ahu_id or "-",Path(document.path).name,pdf2,status))
        rows.sort(key=lambda r:(str(r[1]).casefold(),str(r[2]).casefold(),str(r[0]).casefold()))
        for row in rows:self.ebm_tree.insert("","end",values=row)
        self.tabs.tab(self.ebm_tab,text=f"EBM-PAPST ({len(self._ebm_pdf_keys)})")
    def _selected_pdf_keys(self):
        result=set()
        for side,inputs in (("PDF1",self.pdf1_inputs),("PDF2",self.pdf2_inputs)):
            for item in inputs: result.add((side,str(getattr(item,"path",item)).casefold()))
        return result
    def _matched_pdf_keys(self):
        result=set(); accepted={"EXACT","NORMALIZED_MATCH","USER_APPROVED"}
        for ahu in self.analysis.ahu_matches:
            if getattr(ahu.match,"status","") not in accepted: continue
            result.update(("PDF1",str(path).casefold()) for path in ahu.pdf1_files); result.update(("PDF2",str(path).casefold()) for path in ahu.pdf2_files)
        return result
    def _pdf_classification(self):
        all_keys=self._selected_pdf_keys(); ebm,voc,sysr=self._special_pdf_sets(); matched=self._matched_pdf_keys(); special=ebm|voc|sysr
        danfos=matched-special; unmatched=all_keys-special-matched; categories={"DANFOS":danfos,"EBM-PAPST":ebm,"VOCLEAN":voc,"SYSRECO":sysr,"EŞLEŞMEYEN":unmatched}
        return all_keys,categories
    def _validate_pdf_accounting(self):
        all_keys,categories=self._pdf_classification(); sets=list(categories.values()); overlaps=[]; names=list(categories)
        for i in range(len(sets)):
            for j in range(i+1,len(sets)):
                overlap=sets[i]&sets[j]
                if overlap: overlaps.append(f"{names[i]} ∩ {names[j]} = {len(overlap)}")
        classified=set().union(*sets) if sets else set(); missing=all_keys-classified; extra=classified-all_keys; total=sum(len(s) for s in sets); ok=(not overlaps and not missing and not extra and total==len(all_keys))
        if not ok:
            detail=f"Eklenen PDF: {len(all_keys)} | Sekmeler toplamı: {total} | Eksik: {len(missing)} | Fazla: {len(extra)}"
            if overlaps: detail += " | Çakışma: " + ", ".join(overlaps)
            self.status.configure(text="PDF HESAP HATASI: " + detail); info("PDF HESAP HATASI",selected_pdf_count=len(all_keys),classified_total=total,missing=list(missing),extra=list(extra),overlaps=overlaps)
            if not self._pdf_accounting_error_shown: self._pdf_accounting_error_shown=True; messagebox.showerror("PDF sınıflandırma hatası",detail)
        else: self._pdf_accounting_error_shown=False
        return ok,categories
    def _refresh_grouped_tab_counts(self):
        _,categories=self._validate_pdf_accounting(); counts={name:len(values) for name,values in categories.items()}; self._unmatched_pdf_keys=categories["EŞLEŞMEYEN"]
        self.tabs.tab(0,text=f"DANFOS ({counts['DANFOS']})"); self.tabs.tab(self.ebm_tab,text=f"EBM-PAPST ({counts['EBM-PAPST']})"); self.tabs.tab(self.voclean_tab,text=f"VOCLEAN ({counts['VOCLEAN']})"); self.tabs.tab(self.sysreco_tab,text=f"SYSRECO ({counts['SYSRECO']})"); self.tabs.tab(self.unmatched_tab_index(),text=f"EŞLEŞMEYEN PDF'LER ({counts['EŞLEŞMEYEN']})")
        info("PDF sekme sınıflandırması tamamlandı",selected_pdf_count=sum(counts.values()),**{f"{k.lower().replace('-','_').replace(' ','_')}_pdf_count":v for k,v in counts.items()})
    def _render_unmatched(self):
        for item in self.unmatched_tree.get_children(): self.unmatched_tree.delete(item)
        _,categories=self._validate_pdf_accounting(); unmatched=categories["EŞLEŞMEYEN"]; documents={("PDF1",str(d.path).casefold()):(d,"PDF1") for d in self.analysis.pdf1_documents}; documents.update({("PDF2",str(d.path).casefold()):(d,"PDF2") for d in self.analysis.pdf2_documents}); rows=[]
        for key in sorted(unmatched):
            item=documents.get(key)
            if item:
                document,side=item; project=document.project.project_name or "-"; ahus=", ".join(str(value) for value in document.equipment if str(value).strip()) if document.equipment else "-"; reason="AHU eşleşmesine giremedi" if document.equipment else "Ekipman/AHU tespit edilemedi"
            else: side,path=key; project=ahus="-"; reason="PDF analiz dışında kaldı"
            rows.append((side,Path(key[1]).name,project,ahus,reason,key[1]))
        for side,pdf,project,ahus,reason,path in rows:self.unmatched_tree.insert("","end",values=(side,pdf,project,ahus,reason),tags=(path,))
        self._unmatched_pdf_keys=unmatched
    def _clear_grouped_results(self):
        for item in self.ebm_tree.get_children(): self.ebm_tree.delete(item)
        for item in self.voclean_tree.get_children(): self.voclean_tree.delete(item)
        for item in self.sysreco_tree.get_children(): self.sysreco_tree.delete(item)
        self._grouped_pdf1_scan_cache.clear(); self._ebm_pdf_keys.clear(); self._vocclean_pdf_keys.clear(); self._sysreco_pdf_keys.clear(); self._unmatched_pdf_keys.clear(); self._pdf_accounting_error_shown=False; self.tabs.tab(0,text="DANFOS (0)"); self.tabs.tab(self.ebm_tab,text="EBM-PAPST (0)"); self.tabs.tab(self.voclean_tab,text="VOCLEAN (0)"); self.tabs.tab(self.sysreco_tab,text="SYSRECO (0)")
    def _post_analysis(self):
        try:
            self._render_ebm(); self._render_voclean(); self._render_sysreco(); self._render_unmatched(); rows=[self.tree.item(i,"values") for i in self.tree.get_children()]; grouped=group_result_rows(rows)
            for i in self.tree.get_children(): self.tree.delete(i)
            for row in grouped:self.tree.insert("","end",values=row,tags=("mismatch",) if len(row)>5 and str(row[5]).strip()=="MISMATCH" else ())
            self._refresh_grouped_tab_counts(); elapsed=time.perf_counter()-self._analysis_started_at if self._analysis_started_at is not None else None
            if elapsed is not None:self.status.configure(text=f"Analiz süresi: {elapsed:.2f} sn | PDF {len(self._selected_pdf_keys())} | AHU {len(self.analysis.ahu_matches)} | Motor {len(self.analysis.motor_comparisons)} | MATCH/MISMATCH sonuçları hazır"); info("Toplu analiz tamamlandı",elapsed_seconds=round(elapsed,3),selected_pdf_count=len(self._selected_pdf_keys()),ahu_count=len(self.analysis.ahu_matches),motor_count=len(self.analysis.motor_comparisons))
            self.refresh_logs()
        except Exception as exc: exception("Project/AHU sonuç gruplama hatası",exc); self.refresh_logs()
    def compare(self): self._analysis_started_at=time.perf_counter(); super().compare()

if __name__=="__main__":
    startup(VERSION)
    if len(sys.argv)>=2 and sys.argv[1]=="--apply-update":
        try: apply_update(sys.argv[2],sys.argv[3],int(sys.argv[4]))
        except Exception as exc: exception("Updater modu başarısız",exc,argv=sys.argv); raise
    else:
        try: GroupedApp().mainloop()
        except Exception as exc: exception("GUI ana döngüsü beklenmedik hata ile kapandı",exc); raise
