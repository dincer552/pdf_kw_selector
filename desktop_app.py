"""Desktop GUI for PDF kW Selector - Stage 1 test release."""
from __future__ import annotations
import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from stage1_page_discovery import build_stage1_motor_records, find_rated_motor_powers_in_pdf
VERSION = "v0.2.6"
class App(tk.Tk):
    def __init__(self):
        super().__init__(); self.title(f"PDF kW Selector {VERSION} — PDF 1 Test"); self.geometry("1000x680"); self.minsize(880,600); self.pdf1=None; self.results=[]; self._build()
    def _build(self):
        outer=ttk.Frame(self,padding=18); outer.pack(fill="both",expand=True)
        ttk.Label(outer,text="PDF kW SELECTOR",font=("Segoe UI",20,"bold")).pack(anchor="w")
        ttk.Label(outer,text=f"{VERSION}  •  PDF 1 Motor Discovery  •  Otomatik Analiz",font=("Segoe UI",10)).pack(anchor="w",pady=(0,14))
        file_frame=ttk.LabelFrame(outer,text="PDF 1 — Referans Proje",padding=12); file_frame.pack(fill="x")
        self.file_label=ttk.Label(file_frame,text="Henüz PDF seçilmedi",width=90); self.file_label.grid(row=0,column=0,sticky="ew",padx=(0,10))
        ttk.Button(file_frame,text="PDF SEÇ",command=self.select_pdf).grid(row=0,column=1); file_frame.columnconfigure(0,weight=1)
        action=ttk.Frame(outer); action.pack(fill="x",pady=12)
        ttk.Button(action,text="JSON KAYDET",command=self.save_json).pack(side="left")
        ttk.Label(action,text="PDF seçildiği anda analiz başlar  •  PDF 2 + karşılaştırma: sonraki faz",foreground="#666").pack(side="right")
        result_frame=ttk.LabelFrame(outer,text="Motor Database Önizleme",padding=10); result_frame.pack(fill="both",expand=True)
        self.status=ttk.Label(result_frame,text="PDF seçin; analiz otomatik başlayacaktır.",font=("Segoe UI",11,"bold")); self.status.pack(anchor="w",pady=(0,8))
        cols=("motor","type","direction","kw","group","page","confidence"); self.tree=ttk.Treeview(result_frame,columns=cols,show="headings",height=14)
        headings={"motor":"Motor","type":"Tip","direction":"Hava Yönü","kw":"Anma Gücü (kW)","group":"Grup","page":"Sayfa","confidence":"Güven"}; widths={"motor":95,"type":130,"direction":145,"kw":125,"group":80,"page":65,"confidence":90}
        for col in cols: self.tree.heading(col,text=headings[col]); self.tree.column(col,width=widths[col],anchor="center")
        self.tree.pack(fill="both",expand=True,side="left"); scroll=ttk.Scrollbar(result_frame,orient="vertical",command=self.tree.yview); scroll.pack(fill="y",side="right"); self.tree.configure(yscrollcommand=scroll.set)
        self.detail=tk.Text(outer,height=7,wrap="word",font=("Consolas",9)); self.detail.pack(fill="x",pady=(10,0)); self.detail.configure(state="disabled")
    def select_pdf(self):
        path=filedialog.askopenfilename(title="PDF 1 seç",filetypes=[("PDF files","*.pdf"),("All files","*.*")])
        if not path: return
        self.pdf1=Path(path); self.file_label.configure(text=str(self.pdf1)); self.status.configure(text="PDF analiz ediliyor..."); self.update_idletasks(); self.analyze()
    def analyze(self):
        if not self.pdf1: return
        try: results=find_rated_motor_powers_in_pdf(self.pdf1)
        except Exception as exc: self.status.configure(text="ANALİZ HATASI"); messagebox.showerror("Analiz hatası",str(exc)); return
        self.results=results
        for item in self.tree.get_children(): self.tree.delete(item)
        if not results: self.status.configure(text="SONUÇ BULUNAMADI"); self._set_detail("Supply air / Return air / Exhaust air fan bloğunda Rated Power [kW] / Anma gücü [kW] bulunamadı."); return
        total_motors=0
        for result in results:
            records=build_stage1_motor_records(result); total_motors+=len(records); direction={"supply_fan":"Supply air → Vant","exhaust_fan":"Exhaust air → Asp","return_fan":"Return → Asp"}.get(result.component_role,"-")
            for record in records: self.tree.insert("","end",values=(record.component_label,record.component_type,direction,f"{record.power_kw:g}",record.source_group,record.source_page or "-",record.confidence.upper()))
        self.status.configure(text=f"✓ {len(results)} FAN BLOĞU — {total_motors} FİZİKSEL MOTOR")
        detail=[]
        for result in self.results:
            item=result.to_dict(); item["direction"]={"supply_fan":"Supply air → Vantilatör","exhaust_fan":"Exhaust air → Aspiratör","return_fan":"Return → Aspiratör"}.get(result.component_role,"-"); item["motors_created"]=[r.to_dict() for r in build_stage1_motor_records(result)]; detail.append(item)
        self._set_detail(json.dumps(detail,ensure_ascii=False,indent=2))
    def _set_detail(self,text):
        self.detail.configure(state="normal"); self.detail.delete("1.0","end"); self.detail.insert("1.0",text); self.detail.configure(state="disabled")
    def save_json(self):
        if not self.results: messagebox.showwarning("Sonuç yok","Önce bir PDF seçin ve analiz sonucunun oluşmasını bekleyin."); return
        path=filedialog.asksaveasfilename(title="Analiz sonucunu kaydet",defaultextension=".json",filetypes=[("JSON","*.json")])
        if not path: return
        payload=[]
        for result in self.results:
            item=result.to_dict(); item["motors"]=[r.to_dict() for r in build_stage1_motor_records(result)]; payload.append(item)
        Path(path).write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8"); messagebox.showinfo("Kaydedildi",f"Sonuç kaydedildi:\n{path}")
if __name__ == "__main__": App().mainloop()
