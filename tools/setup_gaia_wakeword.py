#!/usr/bin/env python3
"""Install a user-supplied Gaia OpenWakeWord model; no Jarvis fallback is permitted."""
from __future__ import annotations
import argparse, hashlib, os, shutil
from pathlib import Path

def main():
    p=argparse.ArgumentParser(); p.add_argument("model", type=Path); p.add_argument("--sha256", required=True); p.add_argument("--output", type=Path, default=Path("assets/wakeword/gaia.onnx")); a=p.parse_args()
    if not a.model.is_file(): raise SystemExit(f"model not found: {a.model}")
    digest=hashlib.sha256(a.model.read_bytes()).hexdigest().lower()
    if digest != a.sha256.lower(): raise SystemExit(f"sha256 mismatch: got {digest}")
    if a.output.suffix.lower() != ".onnx": raise SystemExit("Gaia model must be ONNX")
    a.output.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(a.model,a.output)
    print(f"GAIA_WAKEWORD_MODEL={a.output.resolve()}")
if __name__ == "__main__": main()
