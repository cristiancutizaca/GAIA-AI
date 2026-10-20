#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; PACKAGE='GAIA-AI-v1.3-PRODUCTION-INTEGRATED'
SKIP_DIRS={'data','logs','backups','GAIA_VAULT','tokens','secrets','audio','models','build','__pycache__','.pytest_cache','.git','.venv','venv'}
SKIP_NAMES={'.env','.env.local','.env.production','.gaia_processes.json'}
SKIP_SUFFIXES={'.db','.sqlite','.sqlite3','.db-wal','.db-shm','.sqlite-journal','.log','.pyc','.pyo','.wav','.mp3','.m4a','.webm','.pem','.key','.token'}
def allowed(p):
 rel=p.relative_to(ROOT)
 return not (any(x in SKIP_DIRS for x in rel.parts) or p.name in SKIP_NAMES or (p.name.startswith('.env.') and p.name!='.env.example') or p.suffix.lower() in SKIP_SUFFIXES)
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--output-dir',type=Path,default=ROOT.parent); a=ap.parse_args(); out=a.output_dir.resolve(); out.mkdir(parents=True,exist_ok=True); archive=out/(PACKAGE+'.zip')
 members=[p for p in sorted(ROOT.rglob('*')) if p.is_file() and allowed(p)]
 manifest={'product':'GAIA-AI','release':'1.3-PRODUCTION-INTEGRATED','baseline':'GAIA-AI-v1.2-INTEGRATED-AGENT-PLATFORM','status':'INTEGRATED_NOT_PRODUCTION_READY','authority':'GAIA Core / Permission Layer / Action Host','new_mandatory_dependencies':[]}
 mf=ROOT/'release_manifest_v13.json'; mf.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n'); members.append(mf)
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for p in sorted(members):
   rel=p.relative_to(ROOT).as_posix(); info=zipfile.ZipInfo(PACKAGE+'/'+rel,(2020,1,1,0,0,0)); info.compress_type=zipfile.ZIP_DEFLATED; mode=0o755 if p.name=='gradlew' or p.suffix in {'.sh','.bat'} or p.name.startswith('gaia') else 0o644; info.external_attr=(mode&0xffff)<<16; z.writestr(info,p.read_bytes())
 digest=hashlib.sha256(archive.read_bytes()).hexdigest(); cs=archive.with_suffix('.zip.sha256'); cs.write_text(f'{digest}  {archive.name}\n'); mf.unlink()
 with zipfile.ZipFile(archive) as z: assert z.testzip() is None
 print(f'V13 RELEASE PASS: {archive}'); print(f'files={len(members)} sha256={digest}'); print(f'checksum={cs}')
if __name__=='__main__': main()
