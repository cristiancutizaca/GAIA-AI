#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, os, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PACKAGE='GAIA-AI-v1.5-MAXIMUM-INTEGRATION'
EXCLUDED_DIRS={'.git','.venv','venv','node_modules','__pycache__','data','logs','backups','diagnostics','physical-validation','release','tmp','secrets','tokens'}
EXCLUDED_NAMES={'.env','.env.local'}

def files():
    out=[]
    for p in ROOT.rglob('*'):
        if not p.is_file(): continue
        rel=p.relative_to(ROOT)
        if any(part in EXCLUDED_DIRS for part in rel.parts): continue
        if p.name in EXCLUDED_NAMES or p.suffix in {'.pyc','.db','.sqlite','.zip','.mp3','.wav','.mp4'}: continue
        if p.name.startswith('~$'): continue
        out.append(rel)
    return sorted(out,key=lambda x:str(x))

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output-dir',type=Path,default=ROOT.parent/'release'); args=ap.parse_args(); args.output_dir.mkdir(parents=True,exist_ok=True)
    archive=args.output_dir/(PACKAGE+'.zip'); entries=[]
    for rel in files():
        data=(ROOT/rel).read_bytes(); entries.append({'path':str(rel),'size':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    manifest={'product':'GAIA-AI','release':'1.5-MAXIMUM-INTEGRATION','status':'INTEGRATED_NOT_PHYSICALLY_VALIDATED','baseline':'GAIA-AI-v1.3-PRODUCTION-INTEGRATED','authority':'GAIA Core / Permission Layer / Action Host','created_at':dt.datetime.now(dt.timezone.utc).isoformat(),'excluded':['credentials','secrets','venv','node_modules','downloaded models','caches','temporary workspaces','build garbage'],'files':entries}
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('MANIFEST.json',json.dumps(manifest,ensure_ascii=False,sort_keys=True,indent=2))
        for rel in files(): z.write(ROOT/rel,PACKAGE+'/'+str(rel))
    verify=hashlib.sha256(archive.read_bytes()).hexdigest(); print(json.dumps({'archive':str(archive),'files':len(entries),'sha256':verify,'status':'PASS'},ensure_ascii=False))
if __name__=='__main__': main()
