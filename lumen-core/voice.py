"""GAIA local-first speech stack.

Production defaults: faster-whisper (CPU-safe) + Piper invoked as a separate
local process. Legacy openai-whisper/Edge are optional fallbacks only.
"""
from __future__ import annotations

import asyncio
import importlib.util
import logging
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

from config import TTS_ENABLED, TTS_ENGINE, TTS_VOICE, STT_ENABLED, WHISPER_MODEL, DATA_DIR

logger = logging.getLogger("lumen.voice")
AUDIO_DIR = DATA_DIR / "audio"
MODEL_DIR = DATA_DIR / "models"
PIPER_DIR = MODEL_DIR / "piper"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
PIPER_DIR.mkdir(parents=True, exist_ok=True)
_faster_model = None
_whisper_model = None


def _piper_model() -> str:
    return os.getenv("LUMEN_PIPER_MODEL", TTS_VOICE if "_" in TTS_VOICE and "-" in TTS_VOICE else "es_MX-claude-high").strip()


def _piper_data_dir() -> Path:
    raw = os.getenv("LUMEN_PIPER_DATA_DIR", "").strip()
    path = Path(raw).expanduser() if raw else PIPER_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def piper_voice_ready(model: str | None = None) -> bool:
    voice = model or _piper_model()
    base = _piper_data_dir() / f"{voice}.onnx"
    return importlib.util.find_spec("piper") is not None and base.is_file() and Path(str(base) + ".json").is_file()


async def text_to_speech(text: str, output_path: str | None = None) -> str:
    if not TTS_ENABLED:
        raise RuntimeError("TTS está desactivado en la configuración.")
    if not text.strip():
        raise ValueError("No hay texto para convertir a voz.")
    engine = (TTS_ENGINE or "piper").lower().strip()
    if engine in {"piper", "local"}:
        if importlib.util.find_spec("piper") is None:
            raise RuntimeError("Falta Piper TTS. Instala el perfil Voice/Full (piper-tts).")
        model = _piper_model()
        data_dir = _piper_data_dir()
        if not piper_voice_ready(model):
            raise RuntimeError(
                f"Falta la voz Piper '{model}'. Ejecuta: gaia models install piper --voice {model}"
            )
        target = output_path or str(AUDIO_DIR / f"lumen_tts_{uuid.uuid4().hex}.wav")
        cmd = [
            sys.executable,
            "-m",
            "piper",
            "-m",
            model,
            "--data-dir",
            str(data_dir),
            "-f",
            target,
            "--",
            text[:4000],
        ]
        try:
            await asyncio.to_thread(
                subprocess.run,
                cmd,
                check=True,
                timeout=90,
                capture_output=True,
                text=True,
            )
            return target
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"Piper TTS falló: {(exc.stderr or exc.stdout or '')[-1000:]}") from exc
    if engine == "edge":
        target = output_path or str(AUDIO_DIR / f"lumen_tts_{uuid.uuid4().hex}.mp3")
        try:
            import edge_tts
            await edge_tts.Communicate(text[:4000], TTS_VOICE).save(target)
            return target
        except ImportError as exc:
            raise RuntimeError("Falta edge-tts. Instala requirements-voice-legacy.txt.") from exc
    raise ValueError(f"Motor TTS no soportado: {engine}")


def speech_to_text(audio_path: str) -> str:
    global _faster_model, _whisper_model
    if not STT_ENABLED:
        raise RuntimeError("STT está desactivado en la configuración.")
    engine = os.getenv("LUMEN_STT_ENGINE", "faster-whisper").lower().strip()
    language = os.getenv("LUMEN_STT_LANGUAGE", "es").strip() or None
    if language and language.lower() == "auto":
        language = None
    if engine in {"faster-whisper", "faster_whisper", "auto"}:
        try:
            from faster_whisper import WhisperModel
            if _faster_model is None:
                device = os.getenv("LUMEN_STT_DEVICE", "cpu").strip()
                compute = os.getenv("LUMEN_STT_COMPUTE_TYPE", "int8" if device == "cpu" else "float16").strip()
                logger.info("Cargando faster-whisper '%s' device=%s compute=%s", WHISPER_MODEL, device, compute)
                _faster_model = WhisperModel(WHISPER_MODEL, device=device, compute_type=compute)
            segments, _info = _faster_model.transcribe(audio_path, language=language, vad_filter=True, beam_size=5)
            return " ".join(seg.text.strip() for seg in segments if seg.text.strip()).strip()
        except ImportError:
            if engine != "auto":
                raise RuntimeError("Falta faster-whisper. Instala el perfil Voice/Full.")
        except Exception as exc:
            if engine != "auto":
                raise RuntimeError(f"faster-whisper falló: {exc}") from exc
            logger.warning("faster-whisper falló; intentando Whisper legacy: %s", exc)
    try:
        import whisper
    except ImportError as exc:
        raise RuntimeError("No hay STT disponible. Instala faster-whisper o requirements-voice-legacy.txt.") from exc
    if _whisper_model is None:
        logger.info("Cargando Whisper legacy '%s'", WHISPER_MODEL)
        _whisper_model = whisper.load_model(WHISPER_MODEL)
    result = _whisper_model.transcribe(audio_path, language=language, fp16=False)
    return str(result.get("text", "")).strip()


async def get_available_voices() -> list[dict]:
    engine = (TTS_ENGINE or "piper").lower().strip()
    if engine in {"piper", "local"}:
        voice = _piper_model()
        return [{"Name": voice, "Locale": "es-MX", "Engine": "piper", "Local": True, "Ready": piper_voice_ready(voice)}]
    try:
        import edge_tts
    except ImportError as exc:
        raise RuntimeError("Falta edge-tts legacy.") from exc
    voices = await edge_tts.list_voices()
    return [v for v in voices if str(v.get("Locale", "")).startswith("es-")]


def cleanup_audio(max_age_hours: int = 24) -> None:
    cutoff = time.time() - (max_age_hours * 3600)
    for path in AUDIO_DIR.glob("lumen_tts_*"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
        except OSError:
            pass
