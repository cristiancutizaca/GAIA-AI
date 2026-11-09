"""Local, read-only diagnostics for the resident Windows assistant.

Avoids misleading PASS flags: an importable module or HTTP 200 alone does not
prove real microphone input, TTS output or a working visual model. No secrets,
screen contents or audio are read by the diagnostics.
"""
from __future__ import annotations

from importlib.util import find_spec
import os
from pathlib import Path
import platform
import sys

import httpx

ROOT = Path(__file__).resolve().parents[1]


def _check(name: str, status: str, detail: str, remedy: str = "") -> dict[str, str]:
    return {"id": name, "status": status, "detail": detail[:350], "remedy": remedy[:350]}


def _import_available(module: str) -> bool:
    try:
        return find_spec(module) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def local_models(*, http_client=None) -> dict:
    """Query only Ollama loopback. Never follow redirects or proxy settings."""
    from gaia_vision import local_ollama_url
    url = local_ollama_url()
    make_client = http_client or (lambda: httpx.Client(timeout=3.5, follow_redirects=False, trust_env=False))
    with make_client() as client:
        resp = client.get(url + "/api/tags")
        resp.raise_for_status()
        payload = resp.json()
    models = payload.get("models", [])
    if not isinstance(models, list):
        raise ValueError("Respuesta de modelos inválida")
    return {"models": [str(item.get("name", ""))[:120] for item in models if isinstance(item, dict)][:60]}


def _has_model(target: str, names: list[str]) -> bool:
    target = target.strip()
    return bool(target and (target in names or (":" not in target and any(s.split(":", 1)[0] == target for s in names))))


def run(*, models_probe=None, platform_name=None, audio_probe=None, display_probe=None) -> dict:
    """All checks have actionable remediation and make no changes to the PC."""
    system = platform_name or platform.system()
    checks = []
    checks.append(_check("python", "READY" if sys.version_info[:2] == (3, 11) else "WARNING",
                         f"Python {sys.version.split()[0]}", "GAIA completo está diseñado para Python 3.11."))
    if system != "Windows":
        checks.append(_check("windows", "NOT_APPLICABLE", f"Sistema detectado: {system}",
                             "Para probar hotkeys y control de ventanas se necesita Windows."))
    else:
        checks.append(_check("windows", "READY", "Windows detectado; control de ventanas aún sin validar físicamente."))
    checks.append(_check("desktop", "READY" if _import_available("PySide6") else "MISSING",
                         "PySide6 presente" if _import_available("PySide6") else "No está instalado PySide6.",
                         "Instala el perfil desktop/full-computer de GAIA."))
    stt_package = _import_available("faster_whisper")
    checks.append(_check("stt", "PACKAGE_PRESENT" if stt_package else "MISSING",
                         "Paquete faster-whisper presente. Verifica pesos y transcripción."
                         if stt_package else "Falta faster-whisper.",
                         "Usa gaia_models.py install stt para preparar los pesos y probar el decodificador WAV."))
    piper = _import_available("piper")
    if piper:
        try:
            sys.path.insert(0, str(ROOT / "lumen-core"))
            from voice import piper_voice_ready, _piper_model
            model = _piper_model()
            model_ready = piper_voice_ready(model)
        except Exception:
            model_ready = False
    else:
        model_ready = False
    if model_ready:
        checks.append(_check("tts", "READY", "Piper y modelo disponibles; salida de audio pendiente de prueba."))
    elif system == "Windows" and os.getenv("GAIA_WINDOWS_TTS_FALLBACK", "true").lower() not in {"0", "false", "no"}:
        checks.append(_check("tts", "FALLBACK", "Piper no preparado; Windows SAPI puede hablar si hay una voz instalada.",
                             "Configura el modelo Piper para una voz local mejor."))
    else:
        checks.append(_check("tts", "MISSING", "Piper sin paquete o modelo instalado.",
                             "Instala requirements-voice.txt y un modelo compatible de Piper."))
    try:
        if audio_probe:
            audio = audio_probe()
        else:
            import sounddevice as sd
            audio = sd.query_devices()
        devices = list(audio or [])
        microphones = sum(1 for dev in devices if int(dev.get("max_input_channels", 0)) > 0)
        speakers = sum(1 for dev in devices if int(dev.get("max_output_channels", 0)) > 0)
        checks.append(_check("audio", "READY" if microphones and speakers else "WARNING",
                             f"Micrófonos detectados: {microphones}; salidas de audio: {speakers}. No se grabó audio.",
                             "Revisa permisos de micrófono de Windows y dispositivo de audio predeterminado."))
    except Exception as exc:
        checks.append(_check("audio", "MISSING", f"No se pudo enumerar audio: {type(exc).__name__}",
                             "Instala sounddevice y conecta un micrófono; valida permisos de Windows."))
    wake = os.getenv("GAIA_WAKEWORD_MODEL", "").strip()
    wake_path = Path(wake).expanduser() if wake else ROOT / "assets" / "wakeword" / "gaia.onnx"
    wake_status = "CUSTOM_MODEL_MISSING"
    if wake_path.is_file():
        wake_status = "MODEL_PRESENT" if wake_path.name.casefold() == "gaia.onnx" else "CUSTOM_MODEL_INVALID"
    checks.append(_check("wake", wake_status,
                         "Archivo gaia.onnx presente. La palabra se verifica con una prueba física." if wake_status == "MODEL_PRESENT"
                         else "Se requiere un modelo auténtico de GAIA con el nombre gaia.onnx.",
                         "Usa Ctrl+Espacio para hablar; el wake word requiere entrenar/instalar gaia.onnx."))
    try:
        displays = list((display_probe or _default_displays)())
        checks.append(_check("displays", "READY" if displays else "WARNING",
                             f"Monitores detectados: {len(displays)}. La visión requiere autorizar cada captura.",
                             "Revisa pantalla principal y secundaria desde Centro de Control."))
    except Exception as exc:
        checks.append(_check("displays", "WARNING", f"No se pudieron consultar monitores: {type(exc).__name__}"))
    chat_model = os.getenv("LUMEN_LLM_MODEL", "qwen3.5:4b").strip()
    vision_model = os.getenv("GAIA_VISION_MODEL", "qwen2.5vl:7b").strip()
    try:
        names = (models_probe or local_models)()["models"]
    except (httpx.HTTPError, OSError, RuntimeError, ValueError, TypeError) as exc:
        checks.extend([_check("ollama", "OFFLINE", f"Ollama local no responde: {type(exc).__name__}", "Abre Ollama en Windows."),
                       _check("chat_model", "UNVERIFIED", f"Modelo solicitado: {chat_model}"),
                       _check("vision_model", "UNVERIFIED", f"Modelo visual solicitado: {vision_model}")])
    else:
        checks.append(_check("ollama", "READY", f"Ollama local responde; {len(names)} modelos instalados."))
        for key, target in (("chat_model", chat_model), ("vision_model", vision_model)):
            exists = _has_model(target, names)
            checks.append(_check(key, "INSTALLED" if exists else "MISSING", f"Modelo {target}: {'instalado' if exists else 'no instalado'}; inferencia aún sin validar.",
                                 "" if exists else f"ollama pull {target}"))
    return {"read_only": True, "platform": system,
            "checks": checks, "ready": sum(c["status"] == "READY" for c in checks),
            "total": len(checks), "physical_validation_required": True}


def _default_displays():
    from gaia_vision import available_displays
    return available_displays()


def to_text(result: dict) -> str:
    icon = {"READY": "✓", "INSTALLED": "~", "MODEL_PRESENT": "~", "CUSTOM_MODEL_MISSING": "×", "WARNING": "!", "FALLBACK": "~", "OFFLINE": "×", "MISSING": "×", "NOT_APPLICABLE": "-"}
    lines = [f"GAIA · Diagnóstico local ({result['ready']}/{result['total']} controles READY)"]
    for item in result["checks"]:
        lines.append(f"{icon.get(item['status'], '?')} {item['id']}: {item['detail']}")
        if item.get("remedy") and item["status"] != "READY":
            lines.append("    Solución: " + item["remedy"])
    lines.append("Este diagnóstico NO verifica voz/visión/hotkeys de extremo a extremo; esas pruebas requieren tu PC.")
    return "\n".join(lines)
