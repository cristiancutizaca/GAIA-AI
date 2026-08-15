"""Valida que los módulos de escritorio importen sin abrir una ventana."""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
result = subprocess.run([sys.executable, str(ROOT / "lumen-pc" / "gui.py"), "--check"], capture_output=True, text=True)
assert result.returncode == 0, result.stderr
assert "GUI IMPORT OK" in result.stdout
print("GUI IMPORT TEST OK")
