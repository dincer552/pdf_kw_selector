from __future__ import annotations
import inspect,re
from pathlib import Path
import fitz
from ahu_matching import AHUDiscovery,EquipmentOccurrence,normalize_equipment_id
from project_discovery import ProjectCandidate,ProjectDiscovery,normalize_project_name
R=re.compile(r'\b(?:[A-Z0-9]+[_ -]+AHU[_ -]?[A-Z]?\d+(?:\.\d+)?|HKS[_ -]?\d+|KS[_ -]?[A-Z]?\d+(?:\.\d+)?|SS[_ -]?[A-Z]?\d+(?:\.\d+)?|PW[_ -]?\d+(?:\.\d+)?|AHU(?:[_ -]+[A-Z0-9_.-]+|\d[A-Z0-9_.-]*))\b',re.I)
def _path(path):
 if path:return Path(path)
 f=inspect.currentframe().f_back
 for _ in range(3):
  if f:
   p=f.f_locals.get('resolved') or f.f_locals.get('path')
   if p:return Path(p)
  f=f.f_back
 return None
def _fields(path):
 p=[];u=[];d=fitz.open(str(path))
 try:
  for pn,page in enumerate(d,1):
   groups={}
   for w in page.get_text('words'):groups.setdefault((w[5],w[6]),[]).append(w)
   for line in groups.values():
    line.sort(key=lambda w:w[0])
    for i,w in enumerate(line):
     t=w[4].strip().casefold()
     if t=='project':
      a=[x for x in line[i+1:] if x[0]>=w[2]-.5];v=' '.join(x[4] for x in a)
      v=re.split(r'\b(?:creation\s+date|revision\s+date|revision\s+no)\b',v,1,flags=re.I)[0].strip();n=normalize_project_name(v)
      if v and len(n.split())>=2:p.append(ProjectCandidate(v,n,'project_coordinates',pn,'HIGH'))
     if t=='unit' and i+1<len(line) and line[i+1][4].strip().casefold()=='reference':
      for x in line[i+2:]:
       if x[0]<line[i+1][2]-.5:continue
       m=R.search(x[4])
       if m:
        raw=m.group(0).strip(' .,:;)]}');n=normalize_equipment_id(raw)
        if n:u.append(EquipmentOccurrence(raw,n,pn,'unit_reference_coordinates'))
        break
 finally:d.close()
 return p,u
def discover_pdf1_project(pages,path=None):
 path=_path(path)
 if not path:return ProjectDiscovery(None,None,None,None,'REVIEW',())
 a,_=_fields(path);seen=set();q=[]
 for x in a:
  if x.normalized not in seen:seen.add(x.normalized);q.append(x)
 if not q:return ProjectDiscovery(None,None,None,None,'REVIEW',())
 x=q[0];return ProjectDiscovery(x.value,x.normalized,x.source,x.page,x.confidence,tuple(q))
def discover_pdf1_unit_reference(pages,path=None):
 path=_path(path)
 if not path:return AHUDiscovery(())
 _,a=_fields(path);seen=set();q=[]
 for x in a:
  k=(x.normalized,x.page)
  if k not in seen:seen.add(k);q.append(x)
 return AHUDiscovery(tuple(q))
