#!/usr/bin/env python3
"""GAIA model/runtime manager for reproducible local voice setup.

It deliberately does not download LLMs without an explicit command. The baseline
voice installer can prefetch Piper Spanish voice + faster-whisper model.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, os, subprocess, sys, wave
from io import BytesIO
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))
from config import LLM_MODEL, WHISPER_MODEL
from voice import _piper_data_dir, _piper_model

WAKE_DIR = ROOT / "assets" / "wakeword"
DEFAULT_PIPER = _piper_model()
DEFAULT_STT = WHISPER_MODEL


def _module(name:str)->bool:
    try:return importlib.util.find_spec(name) is not None
    except (ImportError,ModuleNotFoundError):return False

def _sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def status()->dict:
    voice=os.getenv('LUMEN_PIPER_MODEL',DEFAULT_PIPER)
    piper_model=_piper_data_dir()/f'{voice}.onnx'
    piper_cfg=Path(str(piper_model)+'.json')
    wake_raw=os.getenv('GAIA_WAKEWORD_MODEL','').strip()
    wake=Path(wake_raw).expanduser() if wake_raw else WAKE_DIR/'gaia.onnx'
    ollama_model=LLM_MODEL
    return {
      'status':'COMPONENTS_PRESENT' if _module('faster_whisper') and _module('piper') and piper_model.is_file() and piper_cfg.is_file() else 'PARTIAL',
      'stt':{'engine':'faster-whisper','package':_module('faster_whisper'),'model':DEFAULT_STT,'download':'explicit install stt / local Hugging Face cache'},
      'tts':{'engine':'piper','package':_module('piper'),'voice':voice,'model':str(piper_model),'model_ready':piper_model.is_file() and piper_cfg.is_file()},
      'wake':{'engine':'openwakeword','package':_module('openwakeword'),'model':str(wake),'model_ready':wake.is_file(),'sha256':_sha(wake) if wake.is_file() else ''},
      'ollama':{'model':ollama_model,'installed_by_this_tool':False,'note':'LLMs are never downloaded implicitly.'},
    }

def install_piper(voice:str)->dict:
    if not _module('piper'): raise RuntimeError('piper-tts is not installed; install the Voice/Full profile first')
    piper_dir = _piper_data_dir()
    cmd=[sys.executable,'-m','piper.download_voices','--data-dir',str(piper_dir),voice]
    subprocess.run(cmd,check=True,timeout=300)
    model=piper_dir/f'{voice}.onnx'; cfg=Path(str(model)+'.json')
    if not model.is_file() or not cfg.is_file(): raise RuntimeError('Piper download completed but expected model/config are missing')
    return {'status':'INSTALLED','component':'piper','voice':voice,'model':str(model),'sha256':_sha(model)}

def install_stt(model:str)->dict:
    if not _module('faster_whisper'): raise RuntimeError('faster-whisper is not installed; install the Voice/Full profile first')
    from faster_whisper import WhisperModel
    from faster_whisper.audio import decode_audio
    sample = BytesIO()
    with wave.open(sample, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(bytes(3200))
    sample.seek(0)
    if len(decode_audio(sample)) != 1600:
        raise RuntimeError("PyAV no pudo decodificar el WAV de prueba.")
    device=os.getenv('LUMEN_STT_DEVICE','cpu')
    compute=os.getenv('LUMEN_STT_COMPUTE_TYPE','int8' if device=='cpu' else 'float16')
    WhisperModel(model,device=device,compute_type=compute)
    return {'status':'READY','component':'stt','engine':'faster-whisper','model':model,'device':device,'compute_type':compute,'wav_decode_verified':True}

def main(argv=None)->int:
    ap=argparse.ArgumentParser(prog='gaia models')
    sub=ap.add_subparsers(dest='cmd',required=True)
    sub.add_parser('status')
    ins=sub.add_parser('install')
    ins.add_argument('component',choices=['piper','stt','baseline'])
    ins.add_argument('--voice',default=DEFAULT_PIPER)
    ins.add_argument('--stt-model',default=DEFAULT_STT)
    args=ap.parse_args(argv)
    try:
        if args.cmd=='status': out=status()
        elif args.component=='piper': out=install_piper(args.voice)
        elif args.component=='stt': out=install_stt(args.stt_model)
        else:
            out={'status':'READY','piper':install_piper(args.voice),'stt':install_stt(args.stt_model)}
        print(json.dumps(out,ensure_ascii=False,indent=2)); return 0
    except Exception as exc:
        print(json.dumps({'status':'ERROR','error':f'{type(exc).__name__}: {exc}'},ensure_ascii=False,indent=2)); return 2
if __name__=='__main__': raise SystemExit(main())
