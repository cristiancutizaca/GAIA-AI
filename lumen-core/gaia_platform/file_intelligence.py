from __future__ import annotations
import hashlib,os
from pathlib import Path
class FileIntelligence:
 def __init__(self,root:Path): self.root=Path(root).resolve()
 def _safe(self,p):
  p=(self.root/p).resolve()
  if self.root not in p.parents and p!=self.root: raise PermissionError('path traversal')
  return p
 def search(self,pattern='*'): return [str(p.relative_to(self.root)) for p in self.root.rglob(pattern) if p.is_file() and not any(x in p.parts for x in {'.git','.venv','secrets','tokens'})][:1000]
 def metadata(self,relative):
  p=self._safe(relative); s=p.stat(); return {'path':str(p.relative_to(self.root)),'size':s.st_size,'mtime':s.st_mtime,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
 def read_text(self,relative,max_bytes=1_000_000): return self._safe(relative).read_bytes()[:max_bytes].decode('utf-8','replace')
 def safe_rename(self,src,dst,*,confirmed=False):
  if not confirmed: raise PermissionError('rename requires confirmation')
  a,b=self._safe(src),self._safe(dst); b.parent.mkdir(parents=True,exist_ok=True); a.rename(b); return str(b.relative_to(self.root))
