#!/usr/bin/env python3
"""GAIA Doctor: diagnóstico read-only de entorno e instalación.

No instala paquetes, no descarga modelos, no crea carpetas y no modifica .env,
SQLite, Vault ni projects.json. Los comandos sugeridos son texto únicamente.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import shutil
import sqlite3
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Check:
    name: str
    status: str
    detail: str
    suggestion: str = ""


def _env_file() -> dict[str, str]:
    values: dict[str, str] = {}
    path = ROOT / ".env"
    if not path.is_file():
        return values
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")
    except OSError:
        return {}
    return values


_FILE_ENV = _env_file()


def env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip():
            return value.strip()
        value = _FILE_ENV.get(name, "")
        if value.strip():
            return value.strip()
    return default


def path_env(*names: str, default: Path) -> Path:
    return Path(env(*names, default=str(default))).expanduser()


def add(checks: list[Check], name: str, status: str, detail: str, suggestion: str = "") -> None:
    checks.append(Check(name, status, detail, suggestion))


def _db_path() -> Path:
    vault_raw = env("GAIA_HOME", "GAIA_VAULT")
    vault = Path(vault_raw).expanduser() if vault_raw else None
    if env("GAIA_MEMORY_DB", "LUMEN_MEMORY_DB"):
        return path_env("GAIA_MEMORY_DB", "LUMEN_MEMORY_DB", default=ROOT / "lumen-core" / "data" / "lumen_memory.db")
    if vault and vault.is_dir():
        return path_env("GAIA_DATA_DIR", "LUMEN_DATA_DIR", default=vault / "data") / "memory" / "lumen_memory.db"
    return path_env("GAIA_DATA_DIR", "LUMEN_DATA_DIR", default=ROOT / "lumen-core" / "data") / "lumen_memory.db"


def _check_db(checks: list[Check], db_path: Path) -> None:
    if not db_path.exists():
        add(checks, "database", "WARN", f"No existe todavía: {db_path}", "Inicia GAIA una vez para crear la DB; no se crea desde Doctor.")
        return
    try:
        with sqlite3.connect(str(db_path), timeout=3) as conn:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            row = conn.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()
            schema = row[0] if row else "desconocido"
        if integrity == "ok":
            add(checks, "database_integrity", "PASS", f"SQLite íntegra; schema {schema}.")
        else:
            add(checks, "database_integrity", "FAIL", f"SQLite integrity_check: {integrity}", "Detén GAIA y usa un Brain Backup/migración validada.")
    except (OSError, sqlite3.DatabaseError) as exc:
        add(checks, "database_integrity", "FAIL", f"No se pudo leer SQLite: {exc}", "Revisa la ruta y permisos; Doctor no repara la DB.")


def _check_ollama(checks: list[Check]) -> None:
    base = env("OLLAMA_URL", default="http://127.0.0.1:11434").rstrip("/")
    try:
        with urllib.request.urlopen(f"{base}/api/tags", timeout=2.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
        names = [str(item.get("name", "")) for item in payload.get("models", []) if isinstance(item, dict)]
        if any(name == "qwen3.5:9b" or name.startswith("qwen3.5:9b") for name in names):
            add(checks, "ollama", "PASS", f"Responde en {base}; qwen3.5:9b está listado.")
        else:
            add(checks, "ollama", "WARN", f"Responde en {base}, pero qwen3.5:9b no aparece.", "Si corresponde, ejecuta manualmente: ollama pull qwen3.5:9b")
    except (OSError, ValueError, urllib.error.URLError) as exc:
        add(checks, "ollama", "FAIL", f"No responde en {base}: {exc}", "Inicia Ollama manualmente y verifica OLLAMA_URL.")


def run_checks() -> list[Check]:
    checks: list[Check] = []
    version = sys.version_info
    if version >= (3, 11):
        add(checks, "python", "PASS", f"Python {version.major}.{version.minor}.{version.micro} en {sys.executable}")
    else:
        add(checks, "python", "FAIL", f"Python {version.major}.{version.minor} es inferior a 3.11", "Usa Python 3.11 o superior.")

    venv = os.getenv("VIRTUAL_ENV") or (ROOT / ".venv")
    add(checks, "venv", "PASS" if Path(venv).exists() else "WARN", f"Entorno: {venv}", "Activa .venv antes de instalar dependencias." if not Path(venv).exists() else "")

    required_modules = {"fastapi": "Core FastAPI", "httpx": "HTTP/LLM", "dotenv": "python-dotenv"}
    missing = [label for module, label in required_modules.items() if importlib.util.find_spec(module) is None]
    add(checks, "dependencies", "PASS" if not missing else "FAIL", "Dependencias principales disponibles." if not missing else "Faltan: " + ", ".join(missing), "Instala los requirements manualmente; Doctor no ejecuta pip." if missing else "")

    env_path = ROOT / ".env"
    add(checks, "env_file", "PASS" if env_path.is_file() else "WARN", str(env_path) if env_path.is_file() else ".env no encontrado; se usarán defaults del proceso.", "Copia .env.example y edítalo manualmente." if not env_path.is_file() else "")
    secret = env("LUMEN_SECRET", default="lumen-dev-key")
    if secret == "lumen-dev-key" or len(secret) < 24:
        add(checks, "master_secret", "WARN", "LUMEN_SECRET está ausente, es default o es corto; no se muestra su valor.", "Configura un secreto largo y privado en .env.")
    else:
        add(checks, "master_secret", "PASS", "LUMEN_SECRET parece no-default y de longitud razonable; el valor no se imprime.")

    db_path = _db_path()
    add(checks, "db_path", "PASS" if db_path.parent.exists() else "WARN", str(db_path), "Revisa GAIA_DATA_DIR/GAIA_MEMORY_DB si la ruta no es la esperada.")
    _check_db(checks, db_path)

    vault_raw = env("GAIA_HOME", "GAIA_VAULT")
    if not vault_raw:
        add(checks, "gaia_vault", "WARN", "GAIA_VAULT no configurado; se espera fallback local.")
    elif Path(vault_raw).expanduser().is_dir():
        add(checks, "gaia_vault", "PASS", "GAIA_VAULT configurado y montado.")
    else:
        add(checks, "gaia_vault", "WARN", "GAIA_VAULT configurado pero no está montado.", "Corrige la ruta o acepta explícitamente el fallback local.")

    backup_dir = path_env("GAIA_BACKUP_DIR", "LUMEN_BACKUP_DIR", default=ROOT / "lumen-core" / "data" / "backups")
    add(checks, "backup_dir", "PASS" if backup_dir.is_dir() else "WARN", str(backup_dir), "La carpeta se creará cuando GAIA cree un backup; Doctor no la crea.")
    _check_ollama(checks)

    ffmpeg = shutil.which("ffmpeg")
    add(checks, "ffmpeg", "PASS" if ffmpeg else "WARN", ffmpeg or "FFmpeg no encontrado.", "Instala FFmpeg manualmente si vas a usar Whisper/voz." if not ffmpeg else "")
    try:
        if importlib.util.find_spec("sounddevice") is None:
            raise RuntimeError("sounddevice no instalado")
        import sounddevice as sd
        devices = sd.query_devices()
        inputs = sum(1 for item in devices if int(item.get("max_input_channels", 0)) > 0)
        add(checks, "audio_devices", "PASS" if inputs else "WARN", f"{inputs} dispositivo(s) de entrada detectado(s).", "Conecta y selecciona un micrófono para voz." if not inputs else "")
    except Exception as exc:
        add(checks, "audio_devices", "WARN", f"No se pudo consultar audio: {exc}", "La voz requiere hardware y dependencias del sistema.")

    code = shutil.which("code") or shutil.which("code.cmd")
    add(checks, "vscode", "PASS" if code else "WARN", code or "VS Code no está en PATH.", "Instala VS Code o ajusta PATH si quieres usar open_vscode." if not code else "")
    git = shutil.which("git")
    add(checks, "git", "PASS" if git else "WARN", git or "Git no está en PATH.", "Instala Git para usar git_status y comandos registrados." if not git else "")

    projects = path_env("GAIA_PROJECTS_FILE", default=ROOT / "projects.json")
    if not projects.is_file():
        add(checks, "projects", "WARN", f"No existe {projects}; solo se puede usar projects.json.example.", "Copia y revisa el registro manualmente; no se crea desde Doctor.")
    else:
        try:
            payload = json.loads(projects.read_text(encoding="utf-8"))
            add(checks, "projects", "PASS", f"projects.json válido con tipo {type(payload).__name__}.")
        except (OSError, ValueError) as exc:
            add(checks, "projects", "FAIL", f"projects.json inválido: {exc}", "Corrige el JSON manualmente.")

    action_enabled = env("LUMEN_ACTION_ENGINE_ENABLED", default="true")
    confirm = env("GAIA_ACTION_CONFIRM_POLICY", default="CONFIRM_EXECUTION")
    add(checks, "action_engine", "PASS" if action_enabled.lower() in {"1", "true", "yes", "si"} and confirm in {"AUTO_SAFE", "CONFIRM_EXECUTION", "BLOCKED"} else "WARN", f"enabled={action_enabled}, policy={confirm}", "Usa CONFIRM_EXECUTION mientras validas el equipo físico.")
    flutter = shutil.which("flutter")
    add(checks, "flutter", "PASS" if flutter else "WARN", flutter or "Flutter no encontrado; Android queda pendiente.", "Instala Flutter manualmente solo para compilar Android." if not flutter else "")
    add(checks, "platform", "PASS", f"{platform.system()} {platform.release()} ({platform.machine()})")
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnóstico read-only de GAIA")
    parser.add_argument("--json", action="store_true", help="Imprime JSON sin secretos")
    parser.add_argument("--strict", action="store_true", help="Devuelve código 1 si existe FAIL")
    args = parser.parse_args()
    checks = run_checks()
    if args.json:
        print(json.dumps({"doctor": "0.5.3", "read_only": True, "checks": [asdict(item) for item in checks]}, ensure_ascii=False, indent=2))
    else:
        print("GAIA Doctor v0.5.3")
        for item in checks:
            print(f"[{item.status}] {item.name}: {item.detail}")
            if item.suggestion:
                print(f"       Sugerencia: {item.suggestion}")
    return 1 if args.strict and any(item.status == "FAIL" for item in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
