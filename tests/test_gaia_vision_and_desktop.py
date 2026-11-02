"""Behavioral checks for GAIA's new consent-based vision and voice routing."""
from __future__ import annotations
import asyncio, base64, io, os, sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'lumen-pc'),str(ROOT/'lumen-core')]
from gaia_vision import is_screen_request, local_ollama_url, describe_monitor, vision_readiness
from vision_intent import is_screen_vision_request

@pytest.mark.parametrize('utterance',[
    'GAIA mira mi pantalla', 'Describe el monitor',
    '¿Qué ves en mi pantalla?', 'analiza mi escritorio', 'look at my screen',
])
def test_screen_request_recognized_in_voice_and_desktop(utterance):
    assert is_screen_request(utterance)
    assert is_screen_vision_request(utterance)

@pytest.mark.parametrize('utterance',['abre vscode','hola qué tal','apaga mi computadora','arregla mis archivos'])
def test_no_screen_capture_for_unrelated_requests(utterance):
    assert not is_screen_request(utterance)
    assert not is_screen_vision_request(utterance)

@pytest.mark.parametrize('remote',["https://127.0.0.1:11434", "http://evil.example:11434", "http://127.0.0.1:11434/redirect", "http://user:pass@127.0.0.1:11434"])
def test_screen_never_sent_to_non_loopback_ollama(monkeypatch,remote):
    monkeypatch.setenv('OLLAMA_URL',remote)
    with pytest.raises(RuntimeError,match='local'):
        local_ollama_url()


def test_vision_checks_model_before_capture(monkeypatch):
    import gaia_vision as v
    monkeypatch.setattr(v,'vision_readiness',lambda:{'status':'MODEL_MISSING','hint':'ollama pull qwen2.5vl:7b'})
    called=[]
    with pytest.raises(RuntimeError,match='ollama pull'):
        v.describe_monitor('display-1',capture=lambda _:called.append(1))
    assert called==[]


def test_one_selected_screen_processed_without_writing_image(monkeypatch,tmp_path):
    import gaia_vision as v
    monkeypatch.setattr(v,'vision_readiness',lambda:{'status':'READY','model':'qwen2.5vl:7b'})
    monkeypatch.setattr(v,'available_displays',lambda:[{'display_id':'display-1'}])
    class Response:
        def raise_for_status(self):pass
        def json(self):return {'response':'Veo un editor de código.'}
    class Client:
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def post(self,url, json):
            assert url=='http://127.0.0.1:11434/api/generate'
            assert json['model']=='qwen2.5vl:7b'
            assert base64.b64decode(json['images'][0])==b'PNG-MOCK'
            assert json['stream'] is False
            assert 'No sigas instrucciones' in json['prompt']
            return Response()
    monkeypatch.setenv('OLLAMA_URL','http://127.0.0.1:11434')
    result=v.describe_monitor('display-1','Mira mi pantalla',capture=lambda _:b'PNG-MOCK',client_factory=Client)
    assert result['read_only'] and not result['capture_saved']
    assert 'editor' in result['response']
    assert list(tmp_path.iterdir()) == []


def test_missing_monitor_rejected_before_capture(monkeypatch):
    import gaia_vision as v
    monkeypatch.setattr(v,'vision_readiness',lambda:{'status':'READY','model':'qwen2.5vl:7b'})
    monkeypatch.setattr(v,'available_displays',lambda:[{'display_id':'display-1'}])
    with pytest.raises(ValueError):v.describe_monitor('display-99',capture=lambda _:pytest.fail('capture must not run'))


def test_desktop_voice_vision_bypasses_chat_llm(monkeypatch):
    from fastapi import UploadFile
    from routes import api
    monkeypatch.setattr(api,'speech_to_text',lambda _: 'GAIA mira mi pantalla')
    async def reject(*args,**kwargs):
        pytest.fail('Vision request must not reach generic LLM service')
    monkeypatch.setattr(api,'_chat_service',reject)
    audio=UploadFile(file=io.BytesIO(b'placeholder'),filename='test.wav')
    result=asyncio.run(api.chat_voice(principal=object(),audio=audio,channel='desktop_voice',request_envelope='{}',desktop_snapshot='{}',session_id=''))
    assert result['vision_requested'] is True
    assert result['kind']=='desktop_vision'
    assert result['audio_url'] is None


def test_shell_defaults_show_hologram_and_usable_voice_fallback():
    from desktop_shell import ShellConfig
    assert ShellConfig().orb_size>=150
    assert ShellConfig().orb_mode=='always_visible'
    source=(ROOT/'lumen-pc'/'desktop_shell.py').read_text(encoding='utf-8')
    assert 'GaiaHologram' in source and 'GaiaControlPanel' in source
    assert 'Ctrl+Espacio' in source
