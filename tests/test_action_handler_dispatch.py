"""Regression checks for real ActionEngine dispatch (not a dry run)."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lumen-pc'))
from action_engine import ActionEngine

def test_each_allowlisted_action_has_a_handler():
    missing = [name for name in ActionEngine.SAFE_ACTIONS if not callable(getattr(ActionEngine, f'_{name}', None))]
    assert missing == []

def test_file_listing_executes_and_observes(tmp_path):
    (tmp_path / 'sample.txt').write_text('test', encoding='utf-8')
    engine = ActionEngine(project_dir=tmp_path)
    result = engine.execute({'name': 'file_list', 'args': {'path': str(tmp_path)}})
    assert result.success and result.execution_verified
    assert any(entry['name'] == 'sample.txt' for entry in result.data['entries'])

def test_folder_creation_is_verified_inside_trusted_project_scope(tmp_path):
    engine = ActionEngine(project_dir=tmp_path)
    result = engine.execute({'name': 'folder_create', 'args': {'path': str(tmp_path / 'new-folder')}})
    assert result.success and result.effect_verified
    assert (tmp_path / 'new-folder').is_dir()

def test_file_open_dispatch_calls_safe_file_handler(tmp_path, monkeypatch):
    path = tmp_path / 'example.txt'
    path.write_text('demo', encoding='utf-8')
    opened=[]
    monkeypatch.setattr(ActionEngine, '_open_path', staticmethod(lambda p: opened.append(p)))
    engine=ActionEngine(project_dir=tmp_path)
    result=engine.execute({'name': 'file_open', 'args': {'path': str(path)}})
    assert result.success and opened == [path]
