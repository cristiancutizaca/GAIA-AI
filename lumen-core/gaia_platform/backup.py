from __future__ import annotations
import hashlib,json,zipfile,datetime
from pathlib import Path
class BackupManager:
 def __init__(self,root:Path): self.root=Path(root)
 def create(self,output:Path,paths:list[Path],*,version='1.2',owner='local'):
  files=[]
  for base in paths:
   base=Path(base)
   if base.is_file(): candidates=[base]
   elif base.is_dir(): candidates=list(base.rglob('*'))
   else: continue
   for p in candidates:
    if not p.is_file() or p.name in {'.env','.env.local'} or any(x in {'secrets','tokens'} for x in p.parts): continue
    data=p.read_bytes(); rel=str(p.relative_to(self.root)) if p.is_relative_to(self.root) else p.name; files.append({'path':rel,'sha256':hashlib.sha256(data).hexdigest(),'size':len(data)})
  manifest={'format':1,'version':version,'owner':owner,'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':files}
  output=Path(output); output.parent.mkdir(parents=True,exist_ok=True)
  with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
   z.writestr('manifest.json',json.dumps(manifest,sort_keys=True,indent=2));
   for item in files:
    p=self.root/item['path']; z.write(p,'payload/'+item['path'])
  return manifest
 def verify(self,archive:Path):
  with zipfile.ZipFile(archive) as z:
   m=json.loads(z.read('manifest.json'));
   for item in m['files']:
    data=z.read('payload/'+item['path']);
    if hashlib.sha256(data).hexdigest()!=item['sha256']: raise ValueError('backup checksum mismatch')
  return m
 def restore(self,archive:Path,target:Path):
  m=self.verify(archive); target=Path(target); target.mkdir(parents=True,exist_ok=True)
  with zipfile.ZipFile(archive) as z:
   for item in m['files']:
    out=target/item['path']; out.parent.mkdir(parents=True,exist_ok=True); out.write_bytes(z.read('payload/'+item['path']))
  return m
