#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PACKAGE='GAIA-AI-v1.2-INTEGRATED-AGENT-PLATFORM'
FORBIDDEN_NAMES={'.env','.env.local','.env.production','.git','.venv','venv','__pycache__','.pytest_cache','.gaia_processes.json'}
FORBIDDEN_DIRS={'data','logs','backups','GAIA_VAULT','tokens','secrets','audio','models','build'}
FORBIDDEN_SUFFIXES={'.db','.sqlite','.sqlite3','.db-wal','.db-shm','.sqlite-journal','.log','.pyc','.pyo','.wav','.mp3','.m4a','.webm','.pem','.key','.token','.zip'}
def allowed(p):
 rel=p.relative_to(ROOT)
 return not (any(x in FORBIDDEN_DIRS for x in rel.parts) or p.name in FORBIDDEN_NAMES or (p.name.startswith('.env.') and p.name!='.env.example') or p.suffix.lower() in FORBIDDEN_SUFFIXES)
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--output-dir',type=Path,default=ROOT.parent); args=ap.parse_args(); out=args.output_dir.resolve(); out.mkdir(parents=True,exist_ok=True); archive=out/(PACKAGE+'.zip')
 members=[p for p in sorted(ROOT.rglob('*')) if p.is_file() and allowed(p)]
 manifest={'product':'GAIA-AI','release':'1.2-INTEGRATED-AGENT-PLATFORM','baseline':'GAIA-AI-v1.1-EVOLUTION-FOUNDATION','deterministic':True,'new_integrations_default':'disabled','authority':'GAIA Core / Permission Layer / Action Host'}
 tmp=ROOT/'release_manifest_v12.json'; tmp.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n'); members.append(tmp)
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for p in sorted(members):
   rel=p.relative_to(ROOT).as_posix(); info=zipfile.ZipInfo(PACKAGE+'/'+rel,(2020,1,1,0,0,0)); info.compress_type=zipfile.ZIP_DEFLATED; mode=0o755 if (p.name=='gradlew' or p.suffix in {'.sh','.bat'} or p.name.startswith('gaia')) else 0o644; info.external_attr=(mode&0xffff)<<16; z.writestr(info,p.read_bytes())
 digest=hashlib.sha256(archive.read_bytes()).hexdigest(); checksum=archive.with_suffix('.zip.sha256'); checksum.write_text(f'{digest}  {archive.name}\n'); tmp.unlink()
 with zipfile.ZipFile(archive) as z: assert z.testzip() is None
 print(f'V12 RELEASE PASS: {archive}'); print(f'files={len(members)} sha256={digest}'); print(f'checksum={checksum}')
if __name__=='__main__': main()
