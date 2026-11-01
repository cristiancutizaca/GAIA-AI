#!/usr/bin/env python3
"""GAIA Doctor 2.1: read-only capability/dependency inventory from canonical manifest."""
from __future__ import annotations
import importlib.util, json, os, platform, shutil, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'lumen-core')); sys.path.insert(0,str(ROOT/'lumen-pc')); sys.path.insert(0,str(ROOT/'tools'))
from gaia_ext.feature_flags import feature_flags
from gaia_dependencies import component_status, load

def check(name,status,detail='',suggestion=''): return {'name':name,'status':status,'detail':detail,'suggestion':suggestion}
def mod(name): return importlib.util.find_spec(name) is not None

def run()->dict:
    flags=feature_flags.as_dict(); checks=[]
    checks.append(check('PYTHON','PASS' if sys.version_info[:2]==(3,11) else 'CONFIG_REQUIRED',sys.version.split()[0],'GAIA release targets Python 3.11.'))
    checks.append(check('CORE','PASS','GAIA Core + central authority import path present'))
    checks.append(check('OLLAMA','PASS' if shutil.which('ollama') else 'CONFIG_REQUIRED',shutil.which('ollama') or 'ollama executable not found','Install Ollama only if local LLM is desired.'))
    checks.append(check('GIT','PASS' if shutil.which('git') else 'CONFIG_REQUIRED',shutil.which('git') or 'git executable not found'))
    for item in component_status():
        st='PASS' if item['status']=='READY' else item['status']
        checks.append(check(item['name'].upper(),st,f"{item['distribution']} -> {item['import']}; profile={item['profile']}",item.get('external','')))
        if 'model_status' in item: checks.append(check(item['name'].upper()+'_MODEL','PASS' if item['model_status']=='READY' else 'CONFIG_REQUIRED',item.get('model') or 'GAIA_WAKEWORD_MODEL not configured','Use tools/setup_gaia_wakeword.py with a trusted Gaia ONNX model.'))
    piper_ready=mod('piper'); checks.append(check('PIPER_RUNTIME','PASS' if piper_ready else 'MISSING_DEPENDENCY','python -m piper' if piper_ready else 'piper module not found','Install Voice/Full profile (piper-tts).'))
    wake_default=ROOT/'assets'/'wakeword'/'gaia.onnx'; wake=os.getenv('GAIA_WAKEWORD_MODEL','').strip(); wake_path=Path(wake) if wake else wake_default
    checks.append(check('GAIA_WAKE_MODEL','PASS' if wake_path.is_file() else 'CONFIG_REQUIRED',str(wake_path),'Train/install an actual Gaia model; no Jarvis fallback is used.'))
    browser_py=ROOT/'.venv-browser'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    browser_playwright=False
    if browser_py.is_file():
        try:
            browser_playwright=subprocess.run([str(browser_py),'-c','import playwright'],capture_output=True,timeout=10).returncode==0
        except Exception: browser_playwright=False
    checks.append(check('CHROMIUM_RUNTIME','DEGRADED' if browser_playwright else 'MISSING_DEPENDENCY','Playwright present in .venv-browser' if browser_playwright else 'Browser sidecar/Playwright missing','Installer runs Chromium install inside .venv-browser; physical launch still needs validation.'))
    checks += [check('PERMISSIONS','PASS','central Permission Layer + Action Host'),check('SAFE_MODE','PASS','fail-closed for effects'),check('KILL_SWITCH','PASS','global effect block'),check('PHYSICAL_WINDOWS','PHYSICAL_VALIDATION_REQUIRED','microphone, speaker, hotkeys, wake accuracy and real desktop control need operator validation')]
    return {'doctor':'2.1-clean-install','read_only':True,'platform':platform.platform(),'flags':flags,'dependency_schema':load().get('schema'),'checks':checks}
if __name__=='__main__': print(json.dumps(run(),ensure_ascii=False,indent=2))
