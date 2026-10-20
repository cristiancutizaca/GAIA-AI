#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PACKAGE='GAIA-AI-v1.1-EVOLUTION-FOUNDATION'
FORBIDDEN_NAMES={'.env','.env.local','.env.production','.git','.venv','venv','__pycache__','.pytest_cache','.gaia_processes.json'}
FORBIDDEN_DIRS={'data','logs','backups','GAIA_VAULT','tokens','secrets','audio','models','build'}
FORBIDDEN_SUFFIXES={'.db','.sqlite','.sqlite3','.db-wal','.db-shm','.sqlite-journal','.log','.pyc','.pyo','.wav','.mp3','.m4a','.webm','.pem','.key','.token','.bak','.tmp','.zip'}
TIME=(2020,1,1,0,0,0)
def allowed(p:Path)->bool:
    rel=p.relative_to(ROOT)
    if any(part in FORBIDDEN_DIRS for part in rel.parts): return False
    if p.name in FORBIDDEN_NAMES: return False
    if p.name.startswith('.env.') and p.name!='.env.example': return False
    return p.suffix.lower() not in FORBIDDEN_SUFFIXES
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output-dir',type=Path,default=ROOT.parent); a=ap.parse_args()
    out=a.output_dir.resolve(); out.mkdir(parents=True,exist_ok=True); archive=out/(PACKAGE+'.zip'); checksum=archive.with_suffix('.zip.sha256')
    members=[]
    for p in sorted(ROOT.rglob('*')):
        if p.is_file() and allowed(p): members.append(p)
    manifest={'product':'GAIA-AI','release':'1.1-EVOLUTION-FOUNDATION','base_release':'1.0-RC6-REPAIRED-STABLE','deterministic':True,'feature_flags_default':'all_disabled','security_authority':'GAIA Core / Permission Layer / Action Host'}
    manifest_path=ROOT/'release_manifest_v11.json'; manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8'); members.append(manifest_path)
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(members):
            rel=p.relative_to(ROOT).as_posix(); info=zipfile.ZipInfo(PACKAGE+'/'+rel,TIME); info.compress_type=zipfile.ZIP_DEFLATED; info.external_attr=((0o755 if p.suffix=='.sh' or p.name.startswith('gaia') else 0o644)&0xffff)<<16; z.writestr(info,p.read_bytes())
    digest=hashlib.sha256(archive.read_bytes()).hexdigest(); checksum.write_text(f'{digest}  {archive.name}\n',encoding='utf-8'); manifest_path.unlink()
    with zipfile.ZipFile(archive) as z: assert z.testzip() is None
    print(f'EVOLUTION RELEASE PASS: {archive}'); print(f'files={len(members)} sha256={digest}'); print(f'checksum={checksum}')
if __name__=='__main__': main()
