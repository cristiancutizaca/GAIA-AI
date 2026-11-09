"""Regression evidence for repair paths. Audio hardware is a fixture here."""
import asyncio
import io
import json
import sys
import threading
import wave
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "lumen-pc"), str(ROOT / "lumen-core"), str(ROOT / "tools")]

import desktop_api
import desktop_shell
import gaia_vision
import llm
import memory
import voice
from authz import Principal
from routes import api
from test_gaia_memory_reflex import application, HEADERS, PC, WAV


def test_mic_cancel_uses_selected_input_and_never_dispatches(monkeypatch):
    captured = []
    stopped = []

    class Input:
        def __init__(self, **options):
            self.options = options
            assert options["device"] == 7
            assert options["samplerate"] == 48000

        def start(self):
            self.options["callback"](desktop_shell.np.ones((64, 1), dtype="int16"), 64, None, None)

        def stop(self):
            stopped.append("stop")

        def close(self):
            stopped.append("close")

    def settings(**options):
        if options["samplerate"] == 16000:
            raise RuntimeError("fixture only supports native format")

    backend = SimpleNamespace(InputStream=Input, check_input_settings=settings,
                              query_devices=lambda *_: {"name": "MCHOSE V9 PRO fixture", "default_samplerate": 48000})
    monkeypatch.setattr(desktop_shell, "sd", backend)
    monkeypatch.setattr(desktop_api, "get_preferred_microphone", lambda: 7)
    capture = desktop_shell.AudioCapture(captured.append)
    assert capture.start()["device_name"].startswith("MCHOSE")
    assert capture.start()["status"] == "ALREADY_CAPTURING"
    capture.cancel()
    assert stopped == ["stop", "close"] and captured == []
    assert capture.stop()["status"] == "IDLE"
    capture.start()
    info = capture.stop()
    with wave.open(str(captured[0]), "rb") as audio:
        assert audio.getframerate() == 48000 and audio.getnframes() == 64
    captured[0].unlink()
    assert info["frames"] == 64


def test_hotkey_stops_when_modifier_or_primary_released():
    hotkey = desktop_shell.GlobalHotkey(lambda: None, lambda: None, "Ctrl+Space")
    pressed = {0x11, 0x20}
    win32 = SimpleNamespace(GetAsyncKeyState=lambda key: 0x8000 if key in pressed else 0)
    assert hotkey._keys_down(win32)
    pressed.remove(0x11)
    assert not hotkey._keys_down(win32)
    invalid = desktop_shell.GlobalHotkey(lambda: None, lambda: None, "Ctrl+Nothing")
    assert invalid.register()["status"] == "HOTKEY_INVALID"


def test_mic_off_discards_queued_recording(tmp_path):
    shell = desktop_shell.DesktopShell(api=object())
    queued = tmp_path / "not-uploaded.wav"
    queued.touch()
    shell._microphone_on = False
    shell._handle_wake_audio_gui(queued)
    assert not queued.exists()


def test_playback_cancels_before_next_synthesis(monkeypatch, tmp_path):
    player = desktop_shell.AudioPlayer()
    first = tmp_path / "first.wav"
    first.touch()
    played = []
    done = threading.Event()

    class Resource:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            done.set()

    class Sound(Resource):
        samplerate = 16000
        channels = 1

        def __init__(self, _):
            pass

        def read(self, *_args, **_kwargs):
            return [0.5] * 20

    class Output(Resource):
        def write(self, block):
            played.append(block)

    monkeypatch.setattr(desktop_shell, "sf", SimpleNamespace(SoundFile=Sound))
    monkeypatch.setattr(desktop_shell, "sd", SimpleNamespace(OutputStream=lambda **_: Output()))

    def chunks(cancelled):
        yield first
        if not cancelled.is_set():
            pytest.fail("A second segment was synthesized after interruption")

    player.play_segments(chunks, on_start=player.stop)
    assert done.wait(2)
    player._thread.join(2)
    assert len(played) == 1 and not first.exists()


def test_split_voice_delivers_text_before_tts_and_restricts_private_engine(application, monkeypatch):
    monkeypatch.setattr(api, "TTS_ENABLED", True)
    monkeypatch.setattr(api, "speech_to_text", lambda _: "recuerda que la libélula es azul")

    async def reject(*args, **kwargs):
        pytest.fail("text-only voice response must not wait for TTS")

    monkeypatch.setattr(api, "text_to_speech", reject)
    with TestClient(application) as client:
        response = client.post("/api/chat/voice", params=PC, files=WAV, data={"synthesize_audio": "false"}, headers=HEADERS)
        assert response.is_success and "Guardé" in response.json()["response"]
        assert response.json()["tts_enabled"] is True and response.json()["audio_url"] is None
        monkeypatch.setattr(api, "TTS_ENGINE", "edge")
        response = client.post("/api/voice/tts", json={"text": "Recuerdo local", "local_only": True}, headers=HEADERS)
        assert response.status_code == 409


def test_voice_http_preserves_recognized_text_when_backend_fails(application, monkeypatch):
    from fastapi import HTTPException

    monkeypatch.setattr(api, "speech_to_text", lambda _: "hola, soy yo")

    async def offline(*args, **kwargs):
        raise HTTPException(502, "Ollama no respondió")

    monkeypatch.setattr(api, "_chat_service", offline)
    with TestClient(application) as client:
        response = client.post("/api/chat/voice", params=PC, files=WAV, headers=HEADERS)
        assert response.status_code == 502
        assert response.json()["stage"] == "chat" and response.json()["user_text"] == "hola, soy yo"
        assert response.json()["audio_url"] is None


def test_piper_load_failure_falls_back_to_sapi(monkeypatch, tmp_path):
    monkeypatch.setattr(voice, "TTS_ENABLED", True)
    monkeypatch.setattr(voice, "TTS_ENGINE", "piper")
    monkeypatch.setattr(voice, "piper_voice_ready", lambda _: True)
    monkeypatch.setattr(voice, "_windows_fallback_ready", lambda: True)

    def failing(model, text, target):
        Path(target).write_bytes(b"bad")
        raise RuntimeError("test engine error")

    def sapi(text, target):
        assert not Path(target).exists()
        Path(target).write_bytes(b"fixture")
        return target

    monkeypatch.setattr(voice, "_piper_tts", failing)
    monkeypatch.setattr(voice, "_windows_tts", sapi)
    output = tmp_path / "result.wav"
    assert asyncio.run(voice.text_to_speech("Hola", str(output))) == str(output)
    assert output.read_bytes() == b"fixture"


def test_vision_checks_capability_before_capturing(monkeypatch):
    def respond(request):
        assert request.url.path == "/api/show"
        return httpx.Response(200, json={"capabilities": ["completion"]})

    client = httpx.Client(transport=httpx.MockTransport(respond))
    monkeypatch.setattr(gaia_vision.httpx, "Client", lambda **_: client)
    with pytest.raises(RuntimeError, match="no declara capacidad"):
        gaia_vision.describe_monitor("display-1", capture=lambda _: pytest.fail("invalid model captured screen"))


def test_sse_clears_owner_if_client_disconnects(application):
    async def disconnect():
        stream = api._assistant_stream(api.ChatRequest(message="Hola"), Principal(type="master"))
        meta = json.loads((await anext(stream)).split("data: ", 1)[1])
        key = meta["request_id"]
        assert memory.get_state(f"request_owner:{key}")
        await stream.aclose()
        assert not memory.get_state(f"request_owner:{key}")
        assert not memory.get_state(f"cancel:{key}")

    with TestClient(application):
        asyncio.run(disconnect())


def test_ollama_status_separates_installed_from_loaded(monkeypatch):
    monkeypatch.setattr(llm, "LLM_BACKEND", "ollama")
    monkeypatch.setattr(llm, "selection_for", lambda *_: SimpleNamespace(
        preferred_model="fixture:latest", selected_model="fixture:latest",
        used_fallback=False, as_dict=dict,
    ))
    rows = {"models": []}

    def respond(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "fixture:latest"}]})
        if request.url.path == "/api/ps":
            return httpx.Response(200, json=rows)
        return httpx.Response(200, json={"version": "fixture"})

    client = httpx.AsyncClient
    monkeypatch.setattr(llm.httpx, "AsyncClient", lambda **_: client(transport=httpx.MockTransport(respond)))
    status = asyncio.run(llm.check_backend())
    assert status["model_installed"] and status["model_loaded"] is False
    rows["models"].append({"name": "fixture:latest", "size_vram": 4, "context_length": 4096})
    status = asyncio.run(llm.check_backend())
    assert status["model_loaded"] is True and status["loaded_models"][0]["size_vram"] == 4


def test_tool_call_is_not_executed_or_read_as_final_answer(monkeypatch, tmp_path):
    async def tool_call(*_args, **_kwargs):
        return {"message": {"content": "He escrito el archivo", "tool_calls": [{
            "function": {"name": "invented_write", "arguments": {"path": str(tmp_path / "prueba.txt")}}
        }]}}

    monkeypatch.setattr(llm, "_post_json", tool_call)
    with pytest.raises(llm.LLMError, match="fuera del canal"):
        asyncio.run(llm._ollama_chat("fixture", [], {"temperature": 0, "num_predict": 10}, "qwen-fixture"))
    assert not (tmp_path / "prueba.txt").exists()
    assert "herramienta" not in api._ground_conversation_response("<tool_call>herramienta</tool_call>")


def test_file_round_trip_uses_real_host_and_verified_disk_state(tmp_path):
    from action_host import ActionHost
    from uuid import uuid4

    host = ActionHost(tmp_path)
    source = tmp_path / "fixture.txt"
    target = tmp_path / "prueba.txt"
    source.write_text("primera versión", encoding="utf-8")

    def run(name, args, risk, *, confirmed=True):
        return host.execute({
            "kind": "action", "action_id": uuid4().hex, "session_id": "disk-probe",
            "confirmation_required": True,
            "action": {"name": name, "args": args, "risk_level": risk},
        }, confirmed=confirmed)

    args = {"source": str(source), "destination": str(target)}
    denied = run("file_copy", args, 2, confirmed=False)
    assert not denied.execution_verified and not target.exists()
    created = run("file_copy", args, 2)
    assert created.execution_verified and target.read_text(encoding="utf-8") == "primera versión"
    assert run("file_exists", {"path": str(target)}, 0).observation_completed
    removed = run("file_delete", {"path": str(target)}, 3)
    assert removed.execution_verified and not target.exists()
    source.write_text("segunda versión", encoding="utf-8")
    assert run("file_copy", args, 2).execution_verified
    assert target.read_text(encoding="utf-8") == "segunda versión"
    assert run("file_delete", {"path": str(target)}, 3).execution_verified
    assert not target.exists()


def test_stt_uses_local_weights_and_explains_pyav_regression(monkeypatch):
    observed = {}

    class Whisper:
        def __init__(self, _model, **options):
            observed.update(options)

        def transcribe(self, *_args, **_kwargs):
            raise TypeError("open() got an unexpected keyword argument 'metadata_errors'")

    monkeypatch.setenv("LUMEN_STT_ENGINE", "faster-whisper")
    monkeypatch.delenv("LUMEN_STT_ALLOW_DOWNLOAD", raising=False)
    monkeypatch.setattr(voice, "STT_ENABLED", True)
    monkeypatch.setattr(voice, "_faster_model", None)
    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=Whisper))
    with pytest.raises(RuntimeError, match="incompatible con el PyAV"):
        voice.speech_to_text("fixture.wav")
    assert observed["local_files_only"] is True
    assert "av>=11,<19" in (ROOT / "requirements-voice.txt").read_text(encoding="utf-8")


def test_wake_rejects_another_word_model_even_when_file_exists(monkeypatch, tmp_path):
    from wake_word import WakeWordListener
    path = tmp_path / "hey_jarvis.onnx"
    path.write_bytes(b"fixture")
    monkeypatch.setenv("GAIA_WAKEWORD_MODEL", str(path))
    assert WakeWordListener().health()["status"] == "CUSTOM_MODEL_INVALID"


def test_loopback_ollama_does_not_initialize_environment_proxy(monkeypatch):
    monkeypatch.setattr(llm, "OLLAMA_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("all_proxy", "ftp://invalid.local:9")
    monkeypatch.setenv("ALL_PROXY", "ftp://invalid.local:9")
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)

    async def run():
        client = await llm._http_client(trust_env=llm._ollama_trust_env())
        assert client is await llm._http_client(trust_env=False)
        await client.aclose()
        llm._HTTP_CLIENTS.clear()

    asyncio.run(run())
