from __future__ import annotations
from pathlib import Path
class Vault:
 def __init__(self,root:Path): self.root=Path(root); self.sections=('USER','PROJECTS','JOBS','KNOWLEDGE','DAILY','ARCHIVE')
 def init(self):
  for s in self.sections:(self.root/s).mkdir(parents=True,exist_ok=True)
  return self.root
 def write(self,section,name,content,*,confirmed=False):
  if section not in self.sections: raise ValueError('invalid vault section')
  if not confirmed: raise PermissionError('vault write requires explicit confirmation')
  p=(self.root/section/name).resolve(); p.parent.mkdir(parents=True,exist_ok=True)
  if self.root.resolve() not in p.parents: raise PermissionError('vault path traversal')
  p.write_text(content,encoding='utf-8'); return p
