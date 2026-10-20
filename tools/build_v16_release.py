#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PACKAGE='GAIA-AI-v1.7-DESKTOP-UPSTREAM-INTEGRATION'
EXCLUDED_DIRS={'.git','.venv','venv','node_modules','__pycache__','data','logs','backups','diagnostics','physical-validation','release','tmp','secrets','tokens','coding-workspaces','.pytest_cache'}
EXCLUDED_NAMES={'.env','.env.local'}
EXCLUDED_SUFFIXES={'.pyc','.db','.sqlite','.zip','.mp3','.wav','.mp4','.bin','.pt','.onnx'}
def files():
    out=[]
    for p in ROOT.rglob('*'):
        if not p.is_file(): continue
        rel=p.relative_to(ROOT)
        if any(part in EXCLUDED_DIRS for part in rel.parts) or p.name in EXCLUDED_NAMES or p.suffix.lower() in EXCLUDED_SUFFIXES or p.name.startswith('~$'): continue
        out.append(rel)
    return sorted(out,key=str)
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output-dir',type=Path,default=ROOT.parent.parent/'release_v16'); args=ap.parse_args(); args.output_dir.mkdir(parents=True,exist_ok=True)
    archive=args.output_dir/(PACKAGE+'.zip'); entries=[]; selected=files()
    for rel in selected:
        data=(ROOT/rel).read_bytes(); entries.append({'path':str(rel),'size':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    manifest={'product':'GAIA-AI','release':'1.7-DESKTOP-UPSTREAM-INTEGRATION','status':'BROWSER_LOCAL_E2E_PASS_DESKTOP_PHYSICAL_VALIDATION_PENDING','baseline':'GAIA-AI-v1.6-REAL-BACKEND-INTEGRATION','authority':'GAIA Core / Permission Layer / Action Host','created_at':dt.datetime.now(dt.timezone.utc).isoformat(),'excluded':['credentials','secrets','venv','node_modules','downloaded models','caches','temporary workspaces','build garbage'],'files':entries}
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('MANIFEST.json',json.dumps(manifest,ensure_ascii=False,sort_keys=True,indent=2))
        for rel in selected: z.write(ROOT/rel,PACKAGE+'/'+str(rel))
    digest=hashlib.sha256(archive.read_bytes()).hexdigest(); (archive.with_suffix('.zip.sha256')).write_text(f'{digest}  {archive.name}\n',encoding='utf-8')
    print(json.dumps({'archive':str(archive),'files':len(entries),'sha256':digest,'status':'PASS'},ensure_ascii=False))
if __name__=='__main__': main()
