#!/usr/bin/env python3
"""Read-only Windows GAIA readiness audit: python tools/gaia_preflight.py [--json]."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lumen-pc'))
from gaia_readiness import run, to_text

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--json', action='store_true')
    args = p.parse_args()
    result = run()
    print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else to_text(result))
