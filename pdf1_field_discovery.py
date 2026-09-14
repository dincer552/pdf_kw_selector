from __future__ import annotations
import re
from pathlib import Path
import fitz
from ahu_matching import AHUDiscovery,EquipmentOccurrence,normalize_equipment_id
from project_discovery import ProjectCandidate,ProjectDiscovery,normalize_project_name
R=re.compile(r'\b(?:[A-Z0-9]+[_ -]+AHU[_ -]?[A-Z]?\d+(?:\.\d+)?|HKS[_ -]?\d+|KS[_ -]?[A-Z]?\d+(?:\.\d+)?|SS[_ -]?[A-Z]?\d+(?:\.\d+)?|PW[_ -]?\d+(?:\.\d+)?|AHU(?:[_ -]+[A-Z0-9_.-]+|\d[A-Z0-9_.-]*))\b',re.I)
def _fields(path):
 p=[];u=[];d=fitz.open(str(path))
 try:
  for pn,page in enumerate(d,1):
   groups={}
   for w in page.get_text('words'):groups.setdefault((w[5],w[6]),[]).append(w)
   for line in groups.values():
    line.sort(key=lambda w:w[0])
    for i,w in enumerate(line):
     t=w[4].strip().lower()
     if t=='project':
      a=[x for x in line[i+1:] if x[0]>=w[2]-0.5]; v=' '.join(x[4] for x in a)
      v=re.split(r'\b(?:creation\s+date|revision\s+date|revision\s+no)\b',v,1,flags=re.I)[0].strip(); n=normalize_project_name(v)
      if v and len(n.split())>=2:p.append(ProjectCandidate(v,n,'project_coordinates',pn,'HIGH'))
     if t=='unit' and i+1<len(line) and line[i+1][4].strip().lower()=='reference':
      for x in line[i+2:]:
       if x[0]<line[i+1][2]-.5:continue
       m=R.search(x[4])
       if m:
        raw=m.group(0).strip(' .,:;)]}'); n=normalize_equipment_id(raw)
        if n:u.append(EquipmentOccurrence(raw,n,pn,'unit_reference_coordinates'))
        break
 finally:d.close()
 return p,u
def discover_pdf1_project(pages,path=None):
 if path is None:return ProjectDiscovery(None,None,None,None,'REVIEW',())
 a,_=_fields(path); seen=set();a=[x for x in a if not(x.normalized in seen or seen.add(x.normalized))]
 if not a:return ProjectDiscovery(None,None,None,None,'REVIEW',())
 x=a[0];return ProjectDiscovery(x.value,x.normalized,x.source,x.page,x.confidence,tuple(a))
def discover_pdf1_unit_reference(pages,path=None):
 if path is None:return AHUDiscovery(())
 _,a=_fields(path);seen=set();a=[x for x in a if not((x.normalized,x.page) in seen or seen.add((x.normalized,x.page)))]
 return AHUDiscovery(tuple(a))
