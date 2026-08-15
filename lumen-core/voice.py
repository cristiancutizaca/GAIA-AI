"""STT local con Whisper y TTS femenino con Edge TTS."""
from __future__ import annotations
import logging
import time
import uuid
from pathlib import Path
from config import TTS_ENABLED, TTS_ENGINE, TTS_VOICE, STT_ENABLED, WHISPER_MODEL, DATA_DIR

logger = logging.getLogger("lumen.voice")
AUDIO_DIR = DATA_DIR / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
_whisper_model = None


async def text_to_speech(text: str, output_path: str | None = None) -> str:
    if not TTS_ENABLED:
        raise RuntimeError("TTS está desactivado en la configuración.")
    if not text.strip():
        raise ValueError("No hay texto para convertir a voz.")
    if TTS_ENGINE != "edge":
        raise ValueError(f"Motor TTS no soportado: {TTS_ENGINE}")
    target = output_path or str(AUDIO_DIR / f"lumen_tts_{uuid.uuid4().hex}.mp3")
    try:
        import edge_tts
        await edge_tts.Communicate(text[:4000], TTS_VOICE).save(target)
        return target
    except ImportError as exc:
        raise RuntimeError("Falta edge-tts. Instala las dependencias del Core.") from exc
    except Exception as exc:
        raise RuntimeError(f"Error generando TTS: {exc}") from exc


def speech_to_text(audio_path: str) -> str:
    global _whisper_model
    if not STT_ENABLED:
        raise RuntimeError("STT está desactivado en la configuración.")
    try:
        import whisper
    except ImportError as exc:
        raise RuntimeError("Falta openai-whisper. Instala dependencias y FFmpeg.") from exc
    if _whisper_model is None:
        logger.info("Cargando modelo Whisper '%s'", WHISPER_MODEL)
        _whisper_model = whisper.load_model(WHISPER_MODEL)
    result = _whisper_model.transcribe(audio_path, language="es", fp16=False)
    return str(result.get("text", "")).strip()


async def get_available_voices() -> list[dict]:
    import edge_tts
    voices = await edge_tts.list_voices()
    return [v for v in voices if str(v.get("Locale", "")).startswith("es-")]


def cleanup_audio(max_age_hours: int = 24) -> None:
    cutoff = time.time() - (max_age_hours * 3600)
    for path in AUDIO_DIR.glob("*.mp3"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
        except OSError:
            pass
