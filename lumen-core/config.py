"""Configuración central del Core de LUMEN v0.2."""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

VERSION = "0.2.0-pc"
BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
load_dotenv(PROJECT_DIR / ".env")
load_dotenv(BASE_DIR / ".env", override=False)


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name, "true" if default else "false").strip().lower()
    return value in {"1", "true", "yes", "si", "sí", "on"}


def _csv(name: str, default: str) -> list[str]:
    return [part.strip() for part in os.getenv(name, default).split(",") if part.strip()]

ENVIRONMENT = os.getenv("LUMEN_ENV", "development").strip().lower()
LOG_LEVEL = os.getenv("LUMEN_LOG_LEVEL", "INFO").strip().upper()
HOST = os.getenv("LUMEN_HOST", "127.0.0.1").strip()
PORT = int(os.getenv("LUMEN_PORT", "8090"))
CORE_URL = os.getenv("LUMEN_CORE_URL", f"http://localhost:{PORT}").rstrip("/")
API_SECRET = os.getenv("LUMEN_SECRET", "lumen-dev-key").strip()
CORS_ORIGINS = _csv("LUMEN_CORS_ORIGINS", "http://localhost,http://127.0.0.1")

DATA_DIR = Path(os.getenv("LUMEN_DATA_DIR", str(BASE_DIR / "data"))).expanduser().resolve()
BACKUP_DIR = Path(os.getenv("LUMEN_BACKUP_DIR", str(DATA_DIR / "backups"))).expanduser().resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "lumen_memory.db"

LLM_BACKEND = os.getenv("LUMEN_LLM_BACKEND", "ollama").lower().strip()
LLM_MODEL = os.getenv("LUMEN_LLM_MODEL", "llama3.1").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
LLM_TIMEOUT_SECONDS = float(os.getenv("LUMEN_LLM_TIMEOUT_SECONDS", "120"))

TTS_ENABLED = _bool("LUMEN_TTS_ENABLED", True)
TTS_ENGINE = os.getenv("LUMEN_TTS_ENGINE", "edge").lower().strip()
TTS_VOICE = os.getenv("LUMEN_TTS_VOICE", "es-MX-DaliaNeural").strip()
STT_ENABLED = _bool("LUMEN_STT_ENABLED", True)
WHISPER_MODEL = os.getenv("LUMEN_WHISPER_MODEL", "base").strip()
MAX_AUDIO_UPLOAD_MB = max(1, int(os.getenv("LUMEN_MAX_AUDIO_UPLOAD_MB", "20")))

AUTO_FACTS_ENABLED = _bool("LUMEN_AUTO_FACTS_ENABLED", False)
BACKUP_ENABLED = _bool("LUMEN_BACKUP_ENABLED", True)
BACKUP_CHECK_MINUTES = max(1, int(os.getenv("LUMEN_BACKUP_CHECK_MINUTES", "60")))
BACKUP_INTERVAL_HOURS = max(1, int(os.getenv("LUMEN_BACKUP_INTERVAL_HOURS", "24")))
MAX_BACKUPS = max(1, int(os.getenv("LUMEN_MAX_BACKUPS", "30")))

# La proactividad automática queda apagada por defecto en v0.2; el test manual sí funciona.
PROACTIVE_ENABLED_DEFAULT = _bool("LUMEN_PROACTIVE_ENABLED", False)
PROACTIVE_POLL_SECONDS = max(5, int(os.getenv("LUMEN_PROACTIVE_POLL_SECONDS", "15")))
PROACTIVE_RULE_CHECK_SECONDS = max(30, int(os.getenv("LUMEN_PROACTIVE_RULE_CHECK_SECONDS", "300")))


def validate_configuration() -> list[str]:
    """Devuelve advertencias o lanza errores para configuración peligrosa."""
    warnings: list[str] = []
    if API_SECRET == "lumen-dev-key" or len(API_SECRET) < 16:
        message = "LUMEN_SECRET es débil; usa un token largo y privado."
        if ENVIRONMENT == "production":
            raise RuntimeError(message)
        warnings.append(message)
    if ENVIRONMENT == "production" and "*" in CORS_ORIGINS:
        raise RuntimeError("CORS '*' no está permitido en producción.")
    if ENVIRONMENT == "production" and LLM_BACKEND == "mock":
        raise RuntimeError("El backend mock no está permitido en producción.")
    if HOST not in {"127.0.0.1", "localhost", "::1"}:
        warnings.append("El Core escucha fuera de localhost; protege la red y cambia el token.")
    return warnings
