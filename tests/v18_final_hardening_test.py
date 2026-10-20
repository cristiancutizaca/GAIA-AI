from __future__ import annotations
import os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lumen-core')); sys.path.insert(0, str(ROOT / 'lumen-pc'))
from desktop_shell import DesktopShell, ShellConfig
from desktop_api import DEFAULT_URL
from config import CORE_URL, PORT
assert DEFAULT_URL == f'http://127.0.0.1:{PORT}'
assert CORE_URL == f'http://127.0.0.1:{PORT}'
api = object()
shell = DesktopShell(ShellConfig(core_url=CORE_URL, orb_mode='wake_only'), api=api)
assert shell.api is api and shell.config.orb_mode == 'wake_only'
shell.toggle_mic(); assert shell.health()['microphone'] is False
shell.toggle_mic(); assert shell.health()['microphone'] is True
text = (ROOT / 'lumen-pc' / 'desktop_shell.py').read_text(encoding='utf-8')
assert 'self.orb.show()' in text and 'QIcon()' not in text and 'self.quick_command_window' in text
startup = (ROOT / 'tools' / 'gaia_startup.py').read_text(encoding='utf-8')
assert 'sys.executable' in startup and 'GAIA_PYTHON' in startup
print('V18 FINAL HARDENING TEST PASS')
