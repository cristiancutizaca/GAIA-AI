"""Configuración central del Core de GAIA v0.4.0."""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

VERSION = "0.5.3-pc"
BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
load_dotenv(PROJECT_DIR / ".env")
load_dotenv(BASE_DIR / ".env", override=False)
ASSISTANT_NAME = os.getenv("LUMEN_ASSISTANT_NAME", "GAIA").strip() or "GAIA"


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name, "true" if default else "false").strip().lower()
    return value in {"1", "true", "yes", "si", "sí", "on"}


def _csv(name: str, default: str) -> list[str]:
    value = os.getenv(name)
    return [part.strip() for part in (value if value is not None and value.strip() else default).split(",") if part.strip()]


def _env_value(*names: str, default: str = "") -> str:
    """Return the first non-empty environment value, treating empty as unset."""
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip():
            return value.strip()
    return default


def optional_path(*names: str, default: str | Path) -> Path:
    """Resolve an optional path; blank variables always use the supplied default."""
    value = _env_value(*names, default="")
    return Path(value).expanduser() if value else Path(default).expanduser()

ENVIRONMENT = os.getenv("LUMEN_ENV", "development").strip().lower()
LOG_LEVEL = os.getenv("LUMEN_LOG_LEVEL", "INFO").strip().upper()
HOST = os.getenv("LUMEN_HOST", "127.0.0.1").strip()
PORT = int(os.getenv("LUMEN_PORT", "8090"))
LAN_ENABLED = _bool("GAIA_LAN_ENABLED", False)
CORE_URL = os.getenv("LUMEN_CORE_URL", f"http://localhost:{PORT}").rstrip("/")
API_SECRET = os.getenv("LUMEN_SECRET", "lumen-dev-key").strip()
CORS_ORIGINS = _csv("LUMEN_CORS_ORIGINS", "http://localhost,http://127.0.0.1")

_GAIA_VAULT_REQUESTED = _env_value("GAIA_HOME", "GAIA_VAULT")
GAIA_HOME = Path(_GAIA_VAULT_REQUESTED).expanduser() if _GAIA_VAULT_REQUESTED else None
GAIA_VAULT = GAIA_HOME.resolve() if GAIA_HOME and GAIA_HOME.exists() and GAIA_HOME.is_dir() else None
_LOCAL_DATA_DIR = optional_path("LUMEN_DATA_DIR", default=BASE_DIR / "data")
_DEFAULT_DATA_DIR = GAIA_VAULT / "data" if GAIA_VAULT else _LOCAL_DATA_DIR
DATA_DIR = optional_path("GAIA_DATA_DIR", "LUMEN_DATA_DIR", default=_DEFAULT_DATA_DIR).resolve()
MEMORY_DIR = (GAIA_VAULT / "data" / "memory" if GAIA_VAULT else DATA_DIR).resolve()
SESSIONS_DIR = (GAIA_VAULT / "data" / "sessions" if GAIA_VAULT else DATA_DIR / "sessions").resolve()
STATE_DIR = (GAIA_VAULT / "data" / "state" if GAIA_VAULT else DATA_DIR / "state").resolve()
_DEFAULT_BACKUP_DIR = GAIA_VAULT / "backups" if GAIA_VAULT else DATA_DIR / "backups"
BACKUP_DIR = optional_path("GAIA_BACKUP_DIR", "LUMEN_BACKUP_DIR", default=_DEFAULT_BACKUP_DIR).resolve()
VAULT_CONFIG_DIR = (GAIA_VAULT / "config" if GAIA_VAULT else DATA_DIR / "config").resolve()
VAULT_LOG_DIR = optional_path("GAIA_LOG_DIR", "LUMEN_LOG_DIR", default=(GAIA_VAULT / "logs" if GAIA_VAULT else DATA_DIR / "logs")).resolve()
VAULT_STATUS = "configured" if GAIA_VAULT else ("missing_fallback" if GAIA_HOME else "fallback_local")
for _directory in (DATA_DIR, MEMORY_DIR, SESSIONS_DIR, STATE_DIR, BACKUP_DIR, VAULT_CONFIG_DIR, VAULT_LOG_DIR):
    _directory.mkdir(parents=True, exist_ok=True)
DB_PATH = optional_path("GAIA_MEMORY_DB", "LUMEN_MEMORY_DB", default=MEMORY_DIR / "lumen_memory.db").resolve()
if DB_PATH.exists() and DB_PATH.is_dir():
    raise RuntimeError(f"La ruta SQLite debe ser un archivo, no una carpeta: {DB_PATH}")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

LLM_BACKEND = os.getenv("LUMEN_LLM_BACKEND", "ollama").lower().strip()
LLM_MODEL = os.getenv("LUMEN_LLM_MODEL", "qwen3.5:9b").strip()
LLM_FALLBACK_MODEL = os.getenv("GAIA_MODEL_FALLBACK", os.getenv("LUMEN_MODEL_FALLBACK", "")).strip()
LLM_KEEP_ALIVE = os.getenv("GAIA_OLLAMA_KEEP_ALIVE", os.getenv("LUMEN_OLLAMA_KEEP_ALIVE", "10m")).strip()
LLM_CONTEXT = max(512, int(os.getenv("GAIA_LLM_CONTEXT", os.getenv("LUMEN_LLM_CONTEXT", "4096"))))
LLM_RETRY_COUNT = min(3, max(0, int(os.getenv("GAIA_LLM_RETRY_COUNT", os.getenv("LUMEN_LLM_RETRY_COUNT", "1")))))

# Alias GAIA_* preferido; LUMEN_* se conserva como compatibilidad heredada.
MODEL_BY_PROFILE = {
    "fast": os.getenv("GAIA_MODEL_FAST", os.getenv("LUMEN_MODEL_FAST", "")).strip(),
    "normal": os.getenv("GAIA_MODEL_NORMAL", os.getenv("LUMEN_MODEL_NORMAL", LLM_MODEL)).strip(),
    "reasoning": os.getenv("GAIA_MODEL_REASONING", os.getenv("LUMEN_MODEL_REASONING", LLM_MODEL)).strip(),
    "code": os.getenv("GAIA_MODEL_CODE", os.getenv("LUMEN_MODEL_CODE", LLM_MODEL)).strip(),
}
MODEL_BY_PROFILE = {key: value for key, value in MODEL_BY_PROFILE.items() if value}
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
LLM_TIMEOUT_SECONDS = max(30.0, float(os.getenv("LUMEN_LLM_TIMEOUT_SECONDS", "600")))
LLM_STREAM_ENABLED = _bool("LUMEN_LLM_STREAM_ENABLED", True)
LLM_HIDE_REASONING = _bool("LUMEN_LLM_HIDE_REASONING", True)
LLM_PROFILE = _env_value("LUMEN_LLM_PROFILE", "GAIA_LLM_PROFILE", default="normal").lower()
if LLM_PROFILE not in {"auto", "fast", "normal", "reasoning", "code"}:
    LLM_PROFILE = "normal"

# Action Engine: el Core clasifica; el cliente PC valida y ejecuta localmente.
ACTION_ENGINE_ENABLED = _bool("LUMEN_ACTION_ENGINE_ENABLED", True)
ACTION_MAX_LEVEL = min(2, max(0, int(os.getenv("LUMEN_ACTION_MAX_LEVEL", "2"))))
ACTION_CONFIRM_LEVEL = max(3, int(os.getenv("LUMEN_ACTION_CONFIRM_LEVEL", "3")))

TTS_ENABLED = _bool("LUMEN_TTS_ENABLED", True)
TTS_ENGINE = os.getenv("LUMEN_TTS_ENGINE", "edge").lower().strip()
TTS_VOICE = os.getenv("LUMEN_TTS_VOICE", "es-MX-DaliaNeural").strip()
STT_ENABLED = _bool("LUMEN_STT_ENABLED", True)
WHISPER_MODEL = os.getenv("LUMEN_WHISPER_MODEL", "base").strip()
MAX_AUDIO_UPLOAD_MB = max(1, int(os.getenv("LUMEN_MAX_AUDIO_UPLOAD_MB", "20")))
AUDIO_RETENTION = _bool("GAIA_AUDIO_RETENTION", False)
ACTIVE_SESSION_SECONDS = max(10, int(os.getenv("GAIA_ACTIVE_SESSION_SECONDS", "30")))

AUTO_FACTS_ENABLED = _bool("LUMEN_AUTO_FACTS_ENABLED", False)
BACKUP_ENABLED = _bool("LUMEN_BACKUP_ENABLED", True)
BACKUP_CHECK_MINUTES = max(1, int(os.getenv("LUMEN_BACKUP_CHECK_MINUTES", "60")))
BACKUP_INTERVAL_HOURS = max(1, int(os.getenv("LUMEN_BACKUP_INTERVAL_HOURS", "24")))
MAX_BACKUPS = max(1, int(os.getenv("LUMEN_MAX_BACKUPS", "30")))
SESSION_SUMMARY_EVERY_TURNS = max(4, int(os.getenv("GAIA_SESSION_SUMMARY_EVERY_TURNS", "8")))
MEMORY_CONTEXT_MAX_CHARS = max(1200, int(os.getenv("GAIA_MEMORY_CONTEXT_MAX_CHARS", "8000")))
MEMORY_RELEVANCE_LIMIT = max(3, min(50, int(os.getenv("GAIA_MEMORY_RELEVANCE_LIMIT", "12"))))
AUTO_MEMORY_ENABLED = _bool("GAIA_AUTO_MEMORY_ENABLED", AUTO_FACTS_ENABLED)
BRAIN_BACKUP_ENABLED = _bool("GAIA_BRAIN_BACKUP_ENABLED", False)
BRAIN_BACKUP_INTERVAL_HOURS = max(24, int(os.getenv("GAIA_BRAIN_BACKUP_INTERVAL_HOURS", "168")))
BRAIN_MAX_BACKUPS = max(1, int(os.getenv("GAIA_BRAIN_MAX_BACKUPS", "10")))
ACTION_PLAN_MAX = max(1, min(3, int(os.getenv("GAIA_ACTION_PLAN_MAX", "3"))))
ACTION_CONFIRM_POLICY = _env_value("GAIA_ACTION_CONFIRM_POLICY", default="CONFIRM_EXECUTION").upper()
if ACTION_CONFIRM_POLICY not in {"AUTO_SAFE", "CONFIRM_EXECUTION", "BLOCKED"}:
    ACTION_CONFIRM_POLICY = "CONFIRM_EXECUTION"
DEVICE_TOKENS_ENABLED = _bool("GAIA_DEVICE_TOKENS_ENABLED", True)
DEVICE_TOKEN_TTL_DAYS = max(1, int(os.getenv("GAIA_DEVICE_TOKEN_TTL_DAYS", "365")))
PRIVACY_MODE = _env_value("GAIA_PRIVACY_MODE", default="normal").lower()
if PRIVACY_MODE not in {"normal", "strict", "debug"}:
    PRIVACY_MODE = "normal"
LOG_MAX_BYTES = max(256 * 1024, int(os.getenv("GAIA_LOG_MAX_BYTES", str(5 * 1024 * 1024))))
LOG_BACKUP_COUNT = max(1, int(os.getenv("GAIA_LOG_BACKUP_COUNT", "5")))

# La proactividad automática queda apagada por defecto en v0.4; el test manual sí funciona.
PROACTIVE_ENABLED_DEFAULT = _bool("LUMEN_PROACTIVE_ENABLED", False)
PROACTIVE_POLL_SECONDS = max(5, int(os.getenv("LUMEN_PROACTIVE_POLL_SECONDS", "15")))
PROACTIVE_RULE_CHECK_SECONDS = max(15, int(os.getenv("LUMEN_PROACTIVE_RULE_CHECK_SECONDS", "60")))
PROACTIVE_CPU_THRESHOLD = max(50.0, min(99.0, float(os.getenv("GAIA_PROACTIVE_CPU_THRESHOLD", "90"))))
PROACTIVE_MEMORY_THRESHOLD = max(50.0, min(99.0, float(os.getenv("GAIA_PROACTIVE_MEMORY_THRESHOLD", "90"))))
PROACTIVE_SUSTAINED_SECONDS = max(30, int(os.getenv("GAIA_PROACTIVE_SUSTAINED_SECONDS", "120")))
PROACTIVE_EVENT_COOLDOWN_MINUTES = max(5, int(os.getenv("GAIA_PROACTIVE_EVENT_COOLDOWN_MINUTES", "60")))
PROACTIVE_LONG_SESSION_HOURS = max(1, float(os.getenv("GAIA_PROACTIVE_LONG_SESSION_HOURS", "4")))
PROACTIVE_COOLDOWN_MINUTES = max(5, int(os.getenv("GAIA_PROACTIVE_COOLDOWN_MINUTES", os.getenv("LUMEN_PROACTIVE_COOLDOWN_MINUTES", "30"))))
PROACTIVE_QUIET_START = min(23, max(0, int(os.getenv("GAIA_PROACTIVE_QUIET_START", "23"))))
PROACTIVE_QUIET_END = min(23, max(0, int(os.getenv("GAIA_PROACTIVE_QUIET_END", "8"))))
PROACTIVE_MAX_DAILY = max(1, int(os.getenv("GAIA_PROACTIVE_MAX_DAILY", "3")))
PROACTIVE_MUTED_DEFAULT = _bool("GAIA_PROACTIVE_MUTED", True)


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
    if LLM_TIMEOUT_SECONDS < 30:
        warnings.append("LUMEN_LLM_TIMEOUT_SECONDS es muy bajo para modelos locales; usa al menos 30 segundos.")
    if HOST not in {"127.0.0.1", "localhost", "::1"}:
        if not LAN_ENABLED:
            raise RuntimeError("LUMEN_HOST está fuera de localhost; activa GAIA_LAN_ENABLED=true de forma explícita para habilitar LAN.")
        warnings.append("LAN explícita activa: GAIA no integra TLS; usa una red confiable, proxy TLS o túnel seguro y un token fuerte.")
    if VAULT_STATUS == "missing_fallback":
        warnings.append("GAIA_VAULT fue configurado pero no está montado; se usa fallback local sin borrar la memoria existente.")
    return warnings
