#!/usr/bin/env python3
"""Prepare/verify GAIA wake-word assets without pretending a model already exists."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; TARGET=ROOT/'assets'/'wakeword'/'gaia.onnx'; CONFIG=ROOT/'assets'/'wakeword'/'gaia_training.yml'
def main():
 p=argparse.ArgumentParser(); p.add_argument('command',choices=['status','verify','config']); a=p.parse_args()
 if a.command=='config': print(CONFIG); return 0
 if not TARGET.is_file(): print(json.dumps({'status':'CONFIG_REQUIRED','model':str(TARGET),'training_config':str(CONFIG),'detail':'No trusted Gaia ONNX is bundled; train with current official openWakeWord workflow or install with setup_gaia_wakeword.py.'},indent=2)); return 2 if a.command=='verify' else 0
 digest=hashlib.sha256(TARGET.read_bytes()).hexdigest(); print(json.dumps({'status':'GAIA_MODEL_READY','model':str(TARGET),'sha256':digest},indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
