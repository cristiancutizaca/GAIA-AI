from __future__ import annotations
import os, sys, tomllib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'lumen-core'),str(ROOT/'tools')]

def test_full_profile_keeps_conflicting_packages_out_of_main_venv():
    data=tomllib.loads((ROOT/'gaia_dependencies.toml').read_text(encoding='utf-8'))
    full=data['profiles']['full_computer']
    assert 'requirements-memory.txt' not in full['requirements']
    assert 'requirements-coding.txt' not in full['requirements']
    assert set(full['sidecars'])=={'browser','memory','coding'}

def test_sidecar_python_versions_are_explicit():
    data=tomllib.loads((ROOT/'gaia_dependencies.toml').read_text(encoding='utf-8'))
    assert data['sidecars']['browser']['python']=='3.11'
    assert data['sidecars']['memory']['python']=='3.11'
    assert data['sidecars']['coding']['python']=='3.12'

def test_browser_mem0_posthog_conflict_is_documented_by_isolation():
    browser=(ROOT/'requirements-browser.txt').read_text(encoding='utf-8').lower()
    memory=(ROOT/'requirements-memory.txt').read_text(encoding='utf-8').lower()
    assert 'browser-use' in browser and 'mem0ai' in memory
    installer=(ROOT/'install-gaia.ps1').read_text(encoding='utf-8')
    assert '.venv-browser' in installer and '.venv-memory' in installer and '.venv-coding' in installer
    assert 'Get-Python312' in installer

def test_providers_use_sidecar_interpreters_not_direct_imports():
    from gaia_platform.browser_real import _BrowserSidecarClient
    from gaia_platform.real_backends import Mem0MemoryProvider, OpenHandsCodingWorker
    _, browser_py, _ = _BrowserSidecarClient.paths()
    m=Mem0MemoryProvider(); o=OpenHandsCodingWorker(ROOT/'tmp-test-coding')
    assert '.venv-browser' in str(browser_py)
    assert '.venv-memory' in str(m.python)
    assert '.venv-coding' in str(o.python)
