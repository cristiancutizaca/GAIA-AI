"""Behavioral regression tests for local first-run diagnostics and task dispatch."""
from __future__ import annotations
import asyncio
import json
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'lumen-core'),str(ROOT/'lumen-pc'),str(ROOT/'tools')]
from operator_intent import is_local_diagnostic_request
from gaia_desktop_tasks import execute_diagnostic, recent_tasks, describe_task
from gaia_readiness import _has_model, local_models, run, to_text

@pytest.mark.parametrize('text', [
    'GAIA, diagnostica mi PC', 'GAIA revisa mi GPU',
    'Revisa ComfyUI y ROCm', 'Inspecciona el sistema',
    'Verifica el estado de mi red',
])
def test_diagnostic_intent(text):
    assert is_local_diagnostic_request(text)

@pytest.mark.parametrize('text', [
    'Hola GAIA', 'mira mi pantalla', 'apaga mi PC',
    'corrige ComfyUI', 'descarga e instala GPU drivers',
    'elimina la carpeta de mi proyecto',
])
def test_non_diagnostic_text_is_not_executed(text):
    assert not is_local_diagnostic_request(text)


def test_offline_verified_diagnostics_with_persistence(tmp_path):
    root=tmp_path/'work';root.mkdir()
    db=tmp_path/'gaia.sqlite3'
    result=execute_diagnostic('GAIA, diagnostica mi PC',directory=root,db=db)
    assert result['state']=='SUCCEEDED', result
    assert result['read_only'] is True
    assert 'system_status' in result['response']
    assert 'system_processes' in result['response']
    assert result['task_id'][:18] in recent_tasks(directory=root,db=db)
    from gaia_operator import Operator
    doc=Operator(root,db).get(result['task_id'])
    assert doc['approved'] is False
    assert all(s['state']=='SUCCEEDED' for s in doc['steps'])
    assert doc['steps'][0]['result']['facts'].get('ram_total_gb',0)>0
    assert not any('processes' in (s['result'].get('facts') or {}) for s in doc['steps'])


def test_chat_does_not_elevate_permissions(tmp_path):
    with pytest.raises(ValueError):
        execute_diagnostic('GAIA, elimina el disco de mi PC',directory=tmp_path,db=tmp_path/'db.sqlite3')


def test_models_check_matches_exact_tag_and_no_false_substring():
    assert _has_model('qwen2.5vl:7b',['qwen2.5vl:7b','qwen3:4b'])
    assert _has_model('qwen2.5vl',['qwen2.5vl:7b'])
    assert not _has_model('qwen2.5vl:3b',['qwen2.5vl:7b'])


def test_readiness_reports_missing_components_without_side_effects(monkeypatch):
    import gaia_readiness as r
    monkeypatch.setattr(r, '_import_available',lambda _:False)
    monkeypatch.setenv('GAIA_WAKEWORD_MODEL','/absent/gaia.onnx')
    output=run(platform_name='Linux',models_probe=lambda: {'models':[]},
               audio_probe=lambda: [],display_probe=lambda: [])
    assert output['read_only'] and output['physical_validation_required']
    checks={c['id']:c for c in output['checks']}
    assert checks['wake']['status']=='CUSTOM_MODEL_MISSING'
    assert checks['vision_model']['status']=='MISSING'
    assert checks['stt']['status']=='MISSING'
    assert 'ollama pull' in to_text(output)


def test_readiness_ollama_offline(monkeypatch):
    def dead(): raise ConnectionError('not running')
    output=run(platform_name='Linux',models_probe=dead,
               audio_probe=lambda: [],display_probe=lambda: [])
    assert any(c['id']=='ollama' and c['status']=='OFFLINE' for c in output['checks'])


def test_readiness_local_urls_only(monkeypatch):
    monkeypatch.setenv('OLLAMA_URL','https://remote-site.example:11434')
    with pytest.raises(RuntimeError): local_models()


def test_voice_operator_dispatch_not_sent_to_llm(monkeypatch):
    from fastapi import UploadFile
    from routes import api
    monkeypatch.setattr(api,'speech_to_text',lambda _: 'GAIA revisa mi GPU y la RAM')
    async def reject(*args,**kwargs):
        pytest.fail('The Core must not invoke a chat LLM or execute PC actions for local operator voice intents')
    monkeypatch.setattr(api,'_chat_service',reject)
    audio=UploadFile(file=__import__('io').BytesIO(b'fake'),filename='test.wav')
    result=asyncio.run(api.chat_voice(principal=object(),audio=audio,channel='desktop_voice',request_envelope='{}',desktop_snapshot='{}',session_id=''))
    assert result['operator_requested'] is True
    assert result['kind']=='desktop_diagnostic'
    assert result['audio_url'] is None


def test_ui_buttons_and_safety_guards_present():
    panel=(ROOT/'lumen-pc/gaia_panel.py').read_text(encoding='utf-8')
    shell=(ROOT/'lumen-pc/desktop_shell.py').read_text(encoding='utf-8')
    assert 'Diagnosticar PC' in panel and 'Diagnosticar ComfyUI' in panel
    assert 'QScrollArea' in panel
    assert 'readiness_requested.connect(self.run_readiness)' in shell
    assert 'voice_reply=True' in shell


def test_shell_loads_dotenv_before_configuration_defaults():
    src=(ROOT/'lumen-pc/desktop_shell.py').read_text(encoding='utf-8')
    assert src.index('load_dotenv(Path(__file__)') < src.index('class ShellConfig:')


def test_voice_action_contract_is_never_implicitly_executed(monkeypatch, tmp_path):
    from desktop_api import LumenDesktopAPI
    class Response:
        def json(self):
            return {
                'kind':'action', 'session_id':'s1', 'action_id':'action-local-1',
                'confirmation_required':False, 'preview':'Abrir aplicación',
                'action':{'name':'open_vscode','args':{},'risk_level':2},
            }
    api=LumenDesktopAPI()
    monkeypatch.setattr(api,'desktop_context',lambda **kwargs: {'desktop_snapshot':{}})
    monkeypatch.setattr(api,'request_envelope',lambda **kwargs:{})
    monkeypatch.setattr(api,'_request',lambda *a,**k:Response())
    monkeypatch.setattr(api,'confirm_action',lambda *a,**k:pytest.fail('voice may never auto-execute'))
    audio=tmp_path/'test.wav';audio.write_bytes(b'WAV')
    returned=api.send_voice(audio)
    assert returned['kind']=='action'
    assert returned['confirmation_required'] is True
    assert 'Abrir aplicación' in returned['response']


def test_shell_action_proposals_use_visible_approval_gate():
    shell=(ROOT/'lumen-pc/desktop_shell.py').read_text(encoding='utf-8')
    assert 'QMessageBox.question' in shell
    assert 'self.api.confirm_action(contract)' in shell
    assert 'self.api.cancel_action(contract)' in shell
    assert "result.get('kind') in {'action','plan'}" in shell
    assert 'No se ejecutó ninguna acción todavía.' in shell
