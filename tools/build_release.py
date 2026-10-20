#!/usr/bin/env python3
"""Compatibility entrypoint for the GAIA 2.0 deterministic release builder."""
from __future__ import annotations
import runpy
from pathlib import Path
TARGET = Path(__file__).with_name("build_v20_release.py")
if __name__ == "__main__":
    runpy.run_path(str(TARGET), run_name="__main__")
