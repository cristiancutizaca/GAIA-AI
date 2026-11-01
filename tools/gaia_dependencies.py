#!/usr/bin/env python3
"""Canonical dependency/profile inventory for installer + Doctor.

GAIA Core/Desktop/Voice remain on Python 3.11. Dependency-heavy providers
(Browser Use, Mem0 and OpenHands) live in isolated sidecar venvs.
"""
from __future__ import annotations
import argparse, importlib.util, json, os, platform, shutil, subprocess, sys, tomllib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; MANIFEST=ROOT/'gaia_dependencies.toml'

def load(): return tomllib.loads(MANIFEST.read_text(encoding='utf-8'))
def _profile(name:str):
    data=load(); profiles=data.get('profiles',{}); key=name.replace('-','_')
    return profiles.get(key) or profiles.get(name) or profiles.get('desktop',{})
def expand_profile(name:str): return list(dict.fromkeys(_profile(name).get('requirements',[])))
def sidecars_for_profile(name:str): return list(dict.fromkeys(_profile(name).get('sidecars',[])))
def _sidecar_python(name:str)->Path:
    cfg=load().get('sidecars',{}).get(name,{})
    venv=ROOT/cfg.get('venv',f'.venv-{name}')
    return venv/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
def _sidecar_import(name:str, module:str)->bool:
    py=_sidecar_python(name)
    if not py.is_file(): return False
    try:
        p=subprocess.run([str(py),'-c',f'import {module}'],capture_output=True,text=True,timeout=15)
        return p.returncode==0
    except Exception: return False

def component_status():
    out=[]
    for name,c in load().get('components',{}).items():
        required_platform=c.get('platform'); applicable=not required_platform or platform.system()==required_platform
        mod=c.get('import_name',''); sidecar=c.get('sidecar','')
        if not applicable: present=False; status='NOT_APPLICABLE'
        elif sidecar:
            present=_sidecar_import(sidecar,mod); status='READY' if present else 'MISSING'
        else:
            try: present=bool(importlib.util.find_spec(mod)) if mod else True
            except (ModuleNotFoundError,ValueError): present=False
            status='READY' if present else 'MISSING'
        detail={'name':name,'status':status,'distribution':c.get('distribution'),'import':mod,'profile':c.get('profile'),'external':c.get('external','')}
        if sidecar:
            detail['sidecar']=sidecar; detail['python']=str(_sidecar_python(sidecar))
        if c.get('model_env'):
            model=os.getenv(c['model_env'],''); detail['model']=model; detail['model_status']='READY' if model and Path(model).is_file() else 'MISSING'
        out.append(detail)
    return out

def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument('command',choices=['status','profiles','requirements','sidecars']); p.add_argument('--profile',default='desktop'); p.add_argument('--strict-python',action='store_true'); a=p.parse_args(argv)
    if a.command=='profiles': print(json.dumps(load().get('profiles',{}),indent=2)); return 0
    if a.command=='requirements': print(json.dumps(expand_profile(a.profile))); return 0
    if a.command=='sidecars': print(json.dumps(sidecars_for_profile(a.profile))); return 0
    data={'python':sys.version.split()[0],'expected_python':load().get('python'),'platform':platform.platform(),'profile':a.profile,'requirements':expand_profile(a.profile),'sidecars':sidecars_for_profile(a.profile),'components':component_status(),'system':{'ollama':shutil.which('ollama'),'git':shutil.which('git')}}
    print(json.dumps(data,ensure_ascii=False,indent=2))
    if a.strict_python and sys.version_info[:2]!=(3,11): return 2
    return 0
if __name__=='__main__': raise SystemExit(main())
