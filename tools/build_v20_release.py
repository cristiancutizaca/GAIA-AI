#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; PACKAGE='GAIA-AI-v2.0-RESIDENT-DESKTOP-ASSISTANT'
EXCLUDE_DIRS={'.git','.venv','venv','node_modules','__pycache__','data','logs','backups','diagnostics','physical-validation','tmp','secrets','tokens','coding-workspaces','.pytest_cache','release'}
EXCLUDE_SUFFIX={'.pyc','.pyo','.db','.sqlite','.sqlite3','.log','.wav','.mp3','.mp4','.zip','.bin','.pt','.onnx','.pem','.key','.token'}
def selected():
 out=[]
 for p in ROOT.rglob('*'):
  if not p.is_file(): continue
  r=p.relative_to(ROOT)
  if any(x in EXCLUDE_DIRS for x in r.parts) or p.name in {'.env','.env.local','.env.production'} or p.suffix.lower() in EXCLUDE_SUFFIX: continue
  out.append(r)
 return sorted(out,key=str)
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--output-dir',type=Path,default=ROOT.parent/'release_v20'); a=ap.parse_args(); a.output_dir.mkdir(parents=True,exist_ok=True); archive=a.output_dir/(PACKAGE+'.zip'); files=selected(); entries=[]
 for r in files:
  b=(ROOT/r).read_bytes(); entries.append({'path':r.as_posix(),'size':len(b),'sha256':hashlib.sha256(b).hexdigest()})
 manifest={'product':'GAIA-AI','version':'2.0.0','release':'2.0-RESIDENT-DESKTOP-ASSISTANT','protocol':'1.0-RC6','schema_min':8,'schema_max':9,'status':'AUTOMATED_SOFTWARE_GATES_PASS_PHYSICAL_WINDOWS_VALIDATION_PENDING','authority':'GAIA Core / Permission Layer / Action Host','files':entries}
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  z.writestr('MANIFEST.json',json.dumps(manifest,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
  for r in files: z.write(ROOT/r,PACKAGE+'/'+r.as_posix())
 digest=hashlib.sha256(archive.read_bytes()).hexdigest(); archive.with_suffix('.zip.sha256').write_text(f'{digest}  {archive.name}\n')
 print(json.dumps({'archive':str(archive),'files':len(files),'sha256':digest,'status':'PASS'})); return 0
if __name__=='__main__': raise SystemExit(main())
