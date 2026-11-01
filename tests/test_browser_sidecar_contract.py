from __future__ import annotations
from pathlib import Path
import sys, tomllib
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'lumen-core'))

def test_browser_profile_is_sidecar_only():
    data=tomllib.loads((ROOT/'gaia_dependencies.toml').read_text(encoding='utf-8'))
    full=data['profiles']['full_computer']
    assert 'requirements-browser.txt' not in full['requirements']
    assert 'browser' in full['sidecars']
    assert data['sidecars']['browser']['venv']=='.venv-browser'

def test_main_computer_requirements_do_not_override_browser_pillow():
    comp=(ROOT/'requirements-computer.txt').read_text(encoding='utf-8').lower()
    assert 'pillow' not in comp
    pc=(ROOT/'lumen-pc/requirements.txt').read_text(encoding='utf-8').lower()
    assert 'pillow==10.4.0' in pc

def test_browser_worker_is_json_sidecar_and_core_does_not_import_browser_use():
    worker=(ROOT/'tools/browser_sidecar.py').read_text(encoding='utf-8')
    core=(ROOT/'lumen-core/gaia_platform/browser_real.py').read_text(encoding='utf-8')
    assert "from browser_use import BrowserSession" in worker
    assert "from browser_use import BrowserSession" not in core
    assert '.venv-browser' in core
