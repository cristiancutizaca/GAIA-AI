#!/usr/bin/env python3
"""Post-install GAIA setup.

Enables only capabilities whose local dependencies are actually present. Services
requiring credentials/external infrastructure stay fail-closed until configured.
"""
from __future__ import annotations
import argparse, importlib.util, json, os, platform, re, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ENV=ROOT/'.env'


def hasmod(name:str)->bool:
    try:return importlib.util.find_spec(name) is not None
    except (ImportError,ModuleNotFoundError,ValueError):return False


def _sidecar_has(venv_name:str, module:str)->bool:
    py=ROOT/venv_name/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not py.is_file(): return False
    try:
        proc=subprocess.run([str(py),'-c',f'import {module}'],capture_output=True,text=True,timeout=15)
        return proc.returncode==0
    except Exception:return False

def _read_env()->str:
    if ENV.exists(): return ENV.read_text(encoding='utf-8')
    example=ROOT/'.env.example'
    return example.read_text(encoding='utf-8') if example.exists() else ''

def _env_map(text:str)->dict[str,str]:
    out={}
    for raw in text.splitlines():
        line=raw.strip()
        if not line or line.startswith('#') or '=' not in line:continue
        k,v=line.split('=',1); out[k.strip()]=v.strip()
    return out

def _set(text:str,key:str,value:str)->str:
    line=f'{key}={value}'
    pattern=rf'(?m)^{re.escape(key)}=.*$'
    if re.search(pattern,text): return re.sub(pattern,line,text)
    return text.rstrip()+f'\n{line}\n'

def detect()->dict:
    windows=platform.system()=='Windows'; env_text=_read_env(); values=_env_map(env_text)
    def value(name:str)->str:return os.getenv(name,values.get(name,'')).strip()
    states={
      'GAIA_FEATURE_MCP': True,
      'GAIA_FEATURE_BROWSER': _sidecar_has('.venv-browser','browser_use') and _sidecar_has('.venv-browser','playwright'),
      'GAIA_FEATURE_VOICE_V2': False,  # direct /api/chat/voice is production; Pipecat realtime remains opt-in until configured.
      'GAIA_FEATURE_VAD': hasmod('silero_vad'),
      'GAIA_FEATURE_MEM0': _sidecar_has('.venv-memory','mem0') and bool(value('MEM0_CONFIG_JSON')),
      'GAIA_FEATURE_CODING_WORKER': _sidecar_has('.venv-coding','openhands.sdk'),
      'GAIA_FEATURE_COMPUTER_USE': hasmod('pyautogui') and (hasmod('pywinauto') if windows else True),
      'GAIA_FEATURE_GRAPH_MEMORY': hasmod('graphiti_core') and bool(value('GRAPHITI_NEO4J_URI')) and bool(value('GRAPHITI_NEO4J_PASSWORD')),
      'GAIA_FEATURE_VISUALIZER': hasmod('fastapi'),
      'GAIA_FEATURE_REALTIME_TRANSPORT': False,
    }
    wake=value('GAIA_WAKEWORD_MODEL')
    default_wake=ROOT/'assets'/'wakeword'/'gaia.onnx'
    wake_path=Path(wake).expanduser() if wake else default_wake
    return {'features':states,'wake_model':str(wake_path),'wake_ready':wake_path.is_file(),'platform':platform.system()}

def apply()->dict:
    data=detect(); text=_read_env()
    for key,val in data['features'].items(): text=_set(text,key,'true' if val else 'false')
    wake=Path(data['wake_model'])
    if data['wake_ready']:
        text=_set(text,'GAIA_WAKEWORD_MODEL',str(wake.resolve()))
        text=_set(text,'GAIA_WAKEWORD_ENABLED','true')
    else:
        text=_set(text,'GAIA_WAKEWORD_ENABLED','false')
    ENV.write_text(text,encoding='utf-8')
    data['status']='APPLIED'; data['env']=str(ENV); return data

def main(argv=None)->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--apply',action='store_true'); a=ap.parse_args(argv)
    data=apply() if a.apply else detect(); print(json.dumps(data,ensure_ascii=False,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
