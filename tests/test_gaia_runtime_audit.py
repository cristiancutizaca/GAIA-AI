"""Regressions reproduced while auditing the GAIA production paths."""
import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / name) for name in ('lumen-core', 'lumen-pc')]

import llm
import memory
from routes import api
from test_gaia_memory_reflex import HEADERS, PC, WAV, application, chat


def test_voice_rejects_invalid_metadata_before_decoding(application, monkeypatch):
    monkeypatch.setattr(api, 'speech_to_text', lambda _: pytest.fail('invalid request reached the decoder'))
    with TestClient(application) as client:
        response = client.post('/api/chat/voice', headers=HEADERS, params=PC, files=WAV,
                               data={'request_envelope': json.dumps({'session_id': '../session'})})
    assert response.status_code == 422
    assert '../session' not in response.text


def test_voice_preserves_authoritative_action_contract(application, monkeypatch):
    monkeypatch.setattr(api, 'speech_to_text', lambda _: 'GAIA, abre el Bloc de notas')
    with TestClient(application) as client:
        result = client.post('/api/chat/voice', headers=HEADERS, params=PC, files=WAV).json()
    assert result['kind'] == 'action' and result['confirmation_required']
    assert result['target_host'] == 'pc-main' and result['requesting_device'] == 'pc-main'
    assert result['permission_entries'][0]['capability'] == 'apps.open'
    assert result['resource_scope_version']


def test_action_can_only_be_claimed_once(application):
    with TestClient(application) as client:
        action = chat(client, 'GAIA, abre el Bloc de notas')
        payload = {key: action[key] for key in ('session_id', 'action_id')}
        assert client.post('/api/actions/approve', headers=HEADERS, json=payload).status_code == 200
        assert client.post('/api/actions/claim', headers=HEADERS, json=payload).status_code == 200
        assert client.get('/api/actions/pending', headers=HEADERS).json()['actions'] == []
        assert client.post('/api/actions/claim', headers=HEADERS, json=payload).status_code == 409
        assert client.post('/api/actions/reject', headers=HEADERS, json=payload).status_code == 409


@pytest.mark.parametrize('stream', [False, True])
def test_kill_switch_blocks_structured_action_even_in_chat_text(application, stream):
    with TestClient(application) as client:
        assert client.post('/api/actions/kill-switch', headers=HEADERS).status_code == 200
        result = client.post('/api/chat/stream' if stream else '/api/chat', headers=HEADERS,
                             json={**PC, 'message': 'Hola', 'intent': {'type': 'action', 'action': 'open_notepad', 'args': {'app': 'notepad'}, 'confidence': 0.99}})
    assert result.status_code == 200 and api._ACTIONS_DISABLED_FALLBACK in result.text
    assert memory.list_states('pending_action:') == []


def test_ollama_handles_invalid_nonstream_message(monkeypatch):
    async def post(*_args, **_kwargs):
        return {'message': ['broken']}
    monkeypatch.setattr(llm, '_post_json', post)
    with pytest.raises(llm.LLMError, match='inválida'):
        asyncio.run(llm._ollama_chat('', [], {'temperature': 0, 'num_predict': 10}, 'fixture'))


def test_ollama_stream_requires_done_and_preserves_visible_content(monkeypatch):
    frames = [{'message': {'thinking': 'privado', 'content': 'Visible'}, 'done': False}]
    def respond(_):
        return httpx.Response(200, content='\n'.join(json.dumps(frame) for frame in frames))

    async def collect():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            async def get_client(**_):
                return client
            monkeypatch.setattr(llm, '_http_client', get_client)
            return [chunk async for chunk in llm._ollama_chat_stream('', [], {'temperature': 0, 'num_predict': 10}, 'fixture')]

    with pytest.raises(llm.LLMError, match='finaliz'):
        asyncio.run(collect())
    frames.append({'done': True})
    assert ''.join(asyncio.run(collect())) == 'Visible'


def test_monitor_capture_rejects_reassigned_display_id(monkeypatch):
    import gaia_vision
    import platform
    import platform_capabilities
    from PIL import ImageGrab

    display = {'display_id': 'display-1', 'name': 'Mismo modelo', 'x': 0, 'y': 0, 'width': 100, 'height': 100}
    monkeypatch.setattr(platform, 'system', lambda: 'Windows')
    monkeypatch.setattr(gaia_vision, 'available_displays', lambda: [dict(display, device_name='MONITOR-A')])
    monkeypatch.setattr(gaia_vision, 'vision_readiness', lambda: {'status': 'READY', 'model': 'fixture'})
    monkeypatch.setattr(platform_capabilities, 'display_info', lambda _: dict(display, device_name='MONITOR-B'))
    monkeypatch.setattr(ImageGrab, 'grab', lambda **_: pytest.fail('a different monitor was captured'))
    with pytest.raises(RuntimeError, match='configuración de monitores cambió'):
        gaia_vision.describe_monitor('display-1', expected_display=dict(display, device_name='MONITOR-A'))


def test_master_can_continue_an_existing_device_session(application, monkeypatch):
    async def response(*_args, **_kwargs):
        return 'Conversación disponible.'
    monkeypatch.setattr(llm, 'chat_completion', response)
    with TestClient(application) as client:
        memory.register_device('android-fixture', ['chat'])
        device_headers = {'Authorization': 'Bearer ' + memory.create_device_token('android-fixture')['token']}
        device_chat = chat(client, 'Hola', headers=device_headers)
        assert chat(client, 'Continúa', session_id=device_chat['session_id'])['response'] == 'Conversación disponible.'
        assert memory.get_session_owner(device_chat['session_id'])['owner_device_id'] == 'android-fixture'


def test_local_claim_checks_core_before_desktop_execution(application, monkeypatch):
    import desktop_api

    with TestClient(application) as client:
        desktop = desktop_api.LumenDesktopAPI()
        def request(method, path, **kwargs):
            kwargs.pop('timeout', None)
            response = client.request(method, path, headers=HEADERS, **kwargs)
            if response.is_error:
                raise desktop_api.LumenAPIError(response.json()['detail'])
            return response

        monkeypatch.setattr(desktop, '_request', request)
        action = chat(client, 'GAIA, abre el Bloc de notas', device=desktop_api.DEVICE)
        payload = {key: action[key] for key in ('action_id', 'session_id')}
        local_payload = {**payload, 'local_host': desktop_api.DEVICE}
        assert client.post('/api/actions/claim', headers=HEADERS, json=payload).status_code == 409
        assert client.post('/api/actions/claim', headers=HEADERS, json={**payload, 'local_host': 'otro'}).status_code == 403
        assert client.post('/api/actions/claim', headers=HEADERS, json=local_payload).status_code == 200
        assert client.post('/api/actions/claim', headers=HEADERS, json=local_payload).status_code == 409

        stale = chat(client, 'GAIA, abre el Bloc de notas', device=desktop_api.DEVICE)
        assert client.post('/api/actions/kill-switch', headers=HEADERS).status_code == 200
        monkeypatch.setattr(desktop_api.ActionHost, 'execute', lambda *_a, **_k: pytest.fail('stale preview executed'))
        with pytest.raises(desktop_api.LumenAPIError, match='detenidas'):
            desktop.confirm_action(stale)


def test_permission_denial_does_not_make_action_claimable(application):
    with TestClient(application) as client:
        action = chat(client, 'GAIA, abre el Bloc de notas')
        payload = {key: action[key] for key in ('session_id', 'action_id')}
        result = client.post('/api/actions/approve', headers=HEADERS, json={**payload, 'decision': 'ALWAYS_DENY'})
        assert result.status_code == 200 and result.json()['status'] == 'rejected'
        assert client.get('/api/actions/pending', headers=HEADERS).json()['actions'] == []
        assert client.post('/api/actions/claim', headers=HEADERS, json=payload).status_code == 404
        assert chat(client, 'GAIA, abre el Bloc de notas')['kind'] == 'chat'


def test_desktop_voice_can_require_confirmation_under_auto_safe(application, monkeypatch):
    monkeypatch.setattr(api, 'ACTION_CONFIRM_POLICY', 'AUTO_SAFE')
    monkeypatch.setattr(api, 'speech_to_text', lambda _: 'Abre la calculadora')
    with TestClient(application) as client:
        text = chat(client, 'Abre la calculadora', require_confirmation=True)
        voice = client.post('/api/chat/voice', headers=HEADERS, params=PC, files=WAV).json()
        for action in (text, voice):
            assert action['kind'] == 'action' and action['confirmation_required']
            assert not action['approved']
        assert client.get('/api/actions/pending', headers=HEADERS).json()['actions'] == []


def test_sse_cancel_interrupts_model_before_first_token(application, monkeypatch):
    async def scenario():
        from authz import Principal
        from contextlib import aclosing

        started = asyncio.Event()
        closed = asyncio.Event()

        async def stalled_model(*_args, **_kwargs):
            try:
                started.set()
                await asyncio.sleep(60)
                yield 'should not be sent'
            finally:
                closed.set()

        monkeypatch.setattr(llm, 'chat_completion_stream', stalled_model)
        principal = Principal('master')
        async with application.router.lifespan_context(application):
            async with aclosing(api._assistant_stream(api.ChatRequest(message='Hola'), principal)) as stream:
                meta = json.loads((await anext(stream)).split('data: ', 1)[1])
                next_event = asyncio.create_task(anext(stream))
                await asyncio.wait_for(started.wait(), 1)
                result = await api.cancel_assistant(api.CancelRequest(request_id=meta['request_id']), principal)
                assert result['status'] == 'cancel_requested'
                assert (await asyncio.wait_for(next_event, 1)).startswith('event: cancelled')
                assert closed.is_set()
            assert not api._ACTIVE_STREAMS and not memory.list_states('request_owner:')
    asyncio.run(scenario())


def test_window_restore_verifies_state_regardless_of_previous_visibility(monkeypatch):
    import platform_capabilities as pc
    win = SimpleNamespace(ShowWindow=lambda *_: 0, IsIconic=lambda _: 0,
                          IsZoomed=lambda _: 0, IsWindowVisible=lambda _: 1)
    monkeypatch.setattr(pc, '_window', lambda _: (win, 42))
    assert pc.window_action('42', 'restore')['verified']
    win.IsIconic = lambda _: 1
    with pytest.raises(pc.PlatformCapabilityError):
        pc.window_action('42', 'restore')


def test_audio_queued_before_mic_toggle_is_discarded(tmp_path):
    from desktop_shell import DesktopShell
    shell = DesktopShell(api=object())
    queued = tmp_path / 'stale.wav'
    queued.touch()
    epoch = shell._voice_epoch
    shell.toggle_mic()
    shell.toggle_mic()
    shell._handle_wake_audio_gui(queued, epoch)
    assert not queued.exists()


def test_tool_markup_after_preface_is_not_presented_as_reply():
    assert api._ground_conversation_response('Ahora sí. <tool_call>{"name":"invented"}</tool_call>') == api._UNAVAILABLE_ACTION_FALLBACK


def test_malformed_bearer_header_returns_401(application):
    with TestClient(application) as client:
        response = client.get('/api/visualizer/events', headers=[(b'authorization', b'Bearer \xff')])
    assert response.status_code == 401


def test_audio_native_library_failure_does_not_prevent_desktop_import():
    import subprocess

    code = """
import builtins
import sys
sys.path[:0] = ['lumen-pc', 'lumen-core']
load = builtins.__import__
def import_with_missing_audio(name, *args, **kwargs):
    if name in {'sounddevice', 'soundfile'}:
        raise OSError('Missing native audio library')
    return load(name, *args, **kwargs)
builtins.__import__ = import_with_missing_audio
import desktop_shell
assert desktop_shell.sd is None and desktop_shell.sf is None
assert desktop_shell.DesktopShell(api=object()).health()['authority'] == 'GAIA Core'
"""
    subprocess.run([sys.executable, '-c', code], cwd=Path(__file__).resolve().parents[1], check=True)


def test_vision_resolves_legacy_ollama_url_without_allowing_remote(monkeypatch):
    from gaia_vision import local_ollama_url

    monkeypatch.setenv('OLLAMA_URL', ' ')
    monkeypatch.delenv('GAIA_OLLAMA_URL', raising=False)
    monkeypatch.setenv('LUMEN_OLLAMA_URL', 'http://127.0.0.1:11435/')
    assert local_ollama_url() == 'http://127.0.0.1:11435'
    monkeypatch.setenv('LUMEN_OLLAMA_URL', 'http://127.0.0.1:11435?unexpected=true')
    with pytest.raises(RuntimeError):
        local_ollama_url()


def test_remote_host_ignores_incompatible_env_proxy(monkeypatch):
    from remote_action_host import RemoteActionHost

    monkeypatch.setenv('ALL_PROXY', 'socks5h://127.0.0.1:9')
    monkeypatch.delenv('LUMEN_CORE_URL', raising=False)
    monkeypatch.setenv('LUMEN_PORT', '8098')
    host = RemoteActionHost(token='fixture')
    try:
        assert host.core_url == 'http://127.0.0.1:8098'
    finally:
        host.close()


def test_kill_switch_keeps_claimed_result_auditable(application):
    with TestClient(application) as client:
        action = chat(client, 'GAIA, ¿cuánta RAM estoy usando?')
        payload = {key: action[key] for key in ('action_id', 'session_id')}
        assert client.post('/api/actions/claim', headers=HEADERS, json={**payload, 'local_host': 'pc-main'}).status_code == 200
        waiting = chat(client, 'GAIA, abre el Bloc de notas')
        assert client.post('/api/actions/kill-switch', headers=HEADERS).json()['pending_cancelled'] == 1
        assert not memory.get_state('pending_action:' + waiting['action_id'])
        result = client.post('/api/actions/complete', headers=HEADERS,
                             json={**payload, 'device': 'pc-main', 'success': True,
                                   'message': 'RAM consultada.', 'observation_completed': True})
        assert result.status_code == 200 and result.json()['success']


def test_sentence_playback_keeps_wav_until_reader_finishes(monkeypatch, tmp_path):
    import desktop_api

    clip = tmp_path / 'sentence.wav'
    clip.touch()
    monkeypatch.setattr(desktop_api.platform, 'system', lambda: 'Linux')
    read = []

    class Process:
        def wait(self):
            assert clip.exists()
            read.append(clip)

    monkeypatch.setattr(desktop_api.subprocess, 'Popen', lambda *_a, **_kw: Process())
    def synthesize(_text, *, local_only):
        assert local_only
        return clip

    buffer = desktop_api.SentenceTTSBuffer(SimpleNamespace(request_tts=synthesize), local_only=True)
    try:
        buffer._synthesize_and_play('Recuerdo de prueba.')
        assert read == [clip] and not clip.exists() and not buffer.processes
    finally:
        buffer.stop()
