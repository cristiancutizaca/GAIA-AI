"""Cliente PC de GAIA: terminal, voz push-to-talk y polling proactivo."""
from __future__ import annotations

import argparse
import asyncio
import atexit
import json
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path
import httpx
from dotenv import load_dotenv
from action_engine import ActionEngine
from action_coordinator import ActionCoordinator
from action_response import parse_action_response, response_for_display
from context_providers import collect_desktop_context
from request_envelope import build_request_envelope

PROJECT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_DIR / ".env")
load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

CORE_URL = os.getenv("LUMEN_CORE_URL", "http://127.0.0.1:8090").rstrip("/")
ASSISTANT_NAME = os.getenv("LUMEN_ASSISTANT_NAME", "GAIA").strip() or "GAIA"
API_SECRET = os.getenv("LUMEN_SECRET", "lumen-dev-key")
DEVICE = f"pc-{platform.system().lower()}"
POLL_SECONDS = max(5, int(os.getenv("LUMEN_PROACTIVE_POLL_SECONDS", "15")))
LLM_CLIENT_TIMEOUT = max(30.0, float(os.getenv("LUMEN_LLM_TIMEOUT_SECONDS", "600")))
session_id = ""
active_request_id = ""
_temp_audio: list[Path] = []


def headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {API_SECRET}"}


def desktop_context() -> dict:
    try:
        return collect_desktop_context(base_dir=PROJECT_DIR, projects_file=PROJECT_DIR / "projects.json", level="FOREGROUND")
    except Exception:
        return {"active_window": None, "ollama": {"status": "unavailable"}, "project": {"active_project": None, "status": "unavailable"}, "system": {}, "desktop_snapshot": {"desktop_available": False, "context_level": "FOREGROUND"}}


def request_payload(text: str = "", *, channel: str = "terminal") -> dict:
    context = desktop_context()
    snapshot = context.get("desktop_snapshot") if isinstance(context.get("desktop_snapshot"), dict) else context
    return {"message": text, "session_id": session_id, "device": DEVICE, "channel": channel, "pc_context": context, "desktop_snapshot": snapshot, "request_envelope": build_request_envelope(session_id=session_id, channel=channel, requesting_device=DEVICE, message=text, desktop_snapshot=snapshot)}


def cleanup_temp_audio() -> None:
    for path in _temp_audio:
        path.unlink(missing_ok=True)

atexit.register(cleanup_temp_audio)


def clear_screen() -> None:
    if platform.system() == "Windows":
        subprocess.run(["cls"], shell=False, check=False)
    elif os.getenv("TERM"):
        subprocess.run(["clear"], shell=False, check=False)

async def check_connection() -> tuple[bool, dict | None]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{CORE_URL}/api/status", headers=headers())
            response.raise_for_status()
            return True, response.json()
    except httpx.HTTPError:
        return False, None

async def send_message(text: str) -> dict:
    """Compatibilidad con integraciones antiguas que aún usan POST /chat."""
    global session_id
    async with httpx.AsyncClient(timeout=LLM_CLIENT_TIMEOUT) as client:
        response = await client.post(f"{CORE_URL}/api/chat", headers=headers(), json=request_payload(text, channel="terminal"))
        response.raise_for_status()
        data = response.json()
    session_id = data.get("session_id", session_id)
    return data


async def complete_action(action_data: dict, result: dict) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(f"{CORE_URL}/api/actions/complete", headers=headers(), json={
            "action_id": action_data["action_id"], "session_id": action_data["session_id"], "device": DEVICE,
            "success": result["success"], "message": result["message"], "data": result.get("data", {}),
        })
        response.raise_for_status()
        return response.json()


async def execute_action_response(data: dict, engine: ActionEngine, confirm_input=None) -> dict:
    parsed = parse_action_response(data)
    if not parsed:
        return data
    print(f"\n  {ASSISTANT_NAME}: {response_for_display(parsed)}")
    coordinator = ActionCoordinator(engine, policy=os.getenv("GAIA_ACTION_CONFIRM_POLICY", "CONFIRM_EXECUTION"))
    ask = confirm_input or (lambda _preview, _parsed: input("  ¿Confirmas la ejecución? [s/N]: ").strip().lower() in {"s", "si", "sí", "y", "yes"})
    local_result = await asyncio.to_thread(coordinator.execute, data, confirm=ask)
    print(f"  Resultado: {local_result['message']}\n")
    if local_result.get("blocked"):
        return {**data, "response": local_result["message"], "local_result": local_result}
    completed = await complete_action(data, local_result)
    completed.update({"kind": "chat", "response": completed.get("response") or local_result["message"], "session_id": data["session_id"], "local_result": local_result, "plan": parsed.plan})
    return completed


async def send_stream(text: str, engine: ActionEngine, print_tokens: bool = True, profile: str = "") -> dict:
    """Consume el contrato SSE y ejecuta acciones solo después de validarlas."""
    global session_id, active_request_id
    final: dict = {}
    action_data: dict | None = None
    event_name = ""
    async with httpx.AsyncClient(timeout=LLM_CLIENT_TIMEOUT) as client:
        stream_payload = request_payload(text, channel="terminal")
        stream_payload["profile"] = profile
        async with client.stream("POST", f"{CORE_URL}/api/assistant/stream", headers=headers(), json=stream_payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("event: "):
                    event_name = line[7:].strip()
                    continue
                if not line.startswith("data: "):
                    continue
                payload = json.loads(line[6:])
                if event_name == "meta":
                    session_id = payload.get("session_id", session_id)
                    active_request_id = payload.get("request_id", active_request_id)
                elif event_name == "token":
                    if print_tokens:
                        print(payload.get("text", ""), end="", flush=True)
                elif event_name == "action":
                    action_data = payload
                elif event_name == "done":
                    final = payload
                elif event_name == "cancelled":
                    final = {"kind": "cancelled", "response": payload.get("detail", "Generación cancelada."), "session_id": session_id}
                elif event_name == "error":
                    raise RuntimeError(payload.get("detail", "El Core informó un error."))
    if print_tokens and final.get("kind") == "chat":
        print("\n")
    if action_data:
        return await execute_action_response(action_data, engine)
    session_id = final.get("session_id", session_id)
    return final

async def send_voice(audio_path: str) -> dict:
    global session_id
    context = desktop_context()
    snapshot = context.get("desktop_snapshot") if isinstance(context.get("desktop_snapshot"), dict) else context
    envelope = build_request_envelope(session_id=session_id, channel="terminal", requesting_device=DEVICE, desktop_snapshot=snapshot)
    form = {"channel": "terminal", "request_envelope": json.dumps(envelope, ensure_ascii=False), "desktop_snapshot": json.dumps(snapshot, ensure_ascii=False)}
    async with httpx.AsyncClient(timeout=180.0) as client:
        with open(audio_path, "rb") as audio_file:
            response = await client.post(f"{CORE_URL}/api/chat/voice", headers=headers(), params={"session_id": session_id, "device": DEVICE}, data=form, files={"audio": ("audio.wav", audio_file, "audio/wav")})
        response.raise_for_status()
        data = response.json()
    session_id = data.get("session_id", session_id)
    return data

async def download_audio(audio_url: str) -> Path:
    url = audio_url if audio_url.startswith("http") else f"{CORE_URL}{audio_url}"
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(url, headers=headers())
        response.raise_for_status()
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp.write(response.content)
        path = Path(tmp.name)
    _temp_audio.append(path)
    return path

async def request_tts(text: str) -> Path:
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(f"{CORE_URL}/api/voice/tts", headers=headers(), json={"text": text})
        response.raise_for_status()
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp.write(response.content)
        path = Path(tmp.name)
    _temp_audio.append(path)
    return path

async def play_local_audio(path: Path) -> None:
    """Reproduce un archivo que ya existe localmente; no intenta descargarlo otra vez."""
    try:
        system = platform.system()
        if system == "Windows":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif system == "Darwin":
            await asyncio.to_thread(subprocess.run, ["afplay", str(path)], check=False)
        else:
            for player in (["mpv", "--no-video", str(path)], ["ffplay", "-nodisp", "-autoexit", str(path)], ["xdg-open", str(path)]):
                try:
                    await asyncio.to_thread(subprocess.run, player, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                    return
                except FileNotFoundError:
                    continue
            print("  [Instala mpv o ffmpeg para reproducir audio en Linux]")
    except Exception as exc:
        print(f"  [No se pudo reproducir audio: {exc}]")

async def play_remote_audio(audio_url: str) -> None:
    await play_local_audio(await download_audio(audio_url))


def record_audio(duration: int = 5) -> str:
    try:
        import numpy as np
        import sounddevice as sd
        import wave
        print("  🎤 Grabando... habla ahora")
        sample_rate = 16000
        try:
            from desktop_api import get_preferred_microphone
            preferred_device = get_preferred_microphone()
        except Exception:
            preferred_device = None
        audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype="int16", device=preferred_device)
        sd.wait()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp:
            tmp_path = temp.name
        with wave.open(tmp_path, "wb") as wav_file:
            wav_file.setnchannels(1); wav_file.setsampwidth(2); wav_file.setframerate(sample_rate); wav_file.writeframes(audio.tobytes())
        print("  ✓ Grabación completada")
        return tmp_path
    except ImportError:
        print("  ⚠ Instala dependencias del cliente: pip install -r requirements.txt")
    except Exception as exc:
        print(f"  ⚠ Error grabando: {exc}")
    return ""


def print_banner() -> None:
    clear_screen()
    spaced_name = "   ".join(ASSISTANT_NAME.upper())
    print("╔" + "═" * 46 + "╗")
    print("║" + spaced_name.center(46) + "║")
    print("║" + "IA Personal — Cliente PC".center(46) + "║")
    print("╚" + "═" * 46 + "╝")


def print_help() -> None:
    print("""
  Comandos:
    /salir              Cerrar cliente
    /voz                Grabar 5 segundos y enviar audio
    /microfonos         Listar micrófonos disponibles
    /microfono n         Guardar el micrófono de entrada n
    /decir texto        Probar TTS sin usar micrófono
    /estado             Ver estado del Core
    /diagnostico        Ver diagnóstico seguro del sistema
    /memoria            Ver estadísticas de memoria
    /perfil             Ver datos recordados
    /nombre [nombre]    Guardar tu nombre
    /backup             Crear backup SQLite inmediato
    /brain-backup       Crear GAIA Brain Backup portable
    /cancelar           Solicitar cancelación de la generación activa
    /probar-proactivo   Encolar un aviso y recibirlo por polling
    /sesion             Ver sesión actual
    /limpiar            Limpiar pantalla
    /ayuda              Mostrar ayuda
""")

async def handle_command(command: str, argument: str, auto_play: bool, engine: ActionEngine) -> bool:
    if command in {"/salir", "/exit", "/q"}:
        return False
    if command == "/microfonos":
        try:
            from desktop_api import select_microphone
            devices = select_microphone()
            print("\n  Micrófonos de entrada:")
            for item in devices:
                marker = " *preferido*" if item.get("preferred") else ""
                print(f"    [{item['index']}] {item['name']} ({item['max_input_channels']} canales){marker}")
            if not devices:
                print("    No hay dispositivos de entrada detectados.")
            print()
        except Exception as exc:
            print(f"\n  No pude consultar micrófonos: {exc}\n")
    elif command == "/microfono":
        try:
            from desktop_api import set_preferred_microphone
            set_preferred_microphone(int(argument))
            print(f"\n  ✓ Micrófono preferido guardado: {argument}\n")
        except (ValueError, TypeError, OSError) as exc:
            print(f"\n  No pude guardar el micrófono: {exc}\n")
    elif command == "/voz":
        audio_path = record_audio()
        if audio_path:
            try:
                data = await execute_action_response(await send_voice(audio_path), engine)
                print(f"\n  Tú (voz): {data.get('user_text', '?')}\n  {ASSISTANT_NAME}: {data['response']}\n")
                if auto_play and data.get("audio_url"):
                    await play_remote_audio(data["audio_url"])
            finally:
                Path(audio_path).unlink(missing_ok=True)
    elif command == "/decir":
        if not argument:
            print("\n  Uso: /decir texto a pronunciar\n")
        else:
            await play_local_audio(await request_tts(argument))
            print("\n  ✓ TTS generado sin usar micrófono.\n")
    elif command == "/brain-backup":
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(f"{CORE_URL}/api/backup/brain", headers=headers()); response.raise_for_status(); path = response.json()["path"]
        print(f"\n  ✓ GAIA Brain Backup creado: {path}\n")
    elif command == "/cancelar":
        if not active_request_id:
            print("\n  No hay una generación activa registrada.\n")
        else:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(f"{CORE_URL}/api/assistant/cancel", headers=headers(), json={"request_id": active_request_id}); response.raise_for_status()
            print("\n  ✓ Cancelación solicitada.\n")
    elif command == "/sesion":
        print(f"\n  Sesión actual: {session_id or '(nueva)'}\n")
    elif command == "/diagnostico":
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"{CORE_URL}/api/diagnostics", headers=headers()); response.raise_for_status(); diagnostic = response.json()
        print("\n  Diagnóstico GAIA:")
        for section in ("core", "database", "vault", "ollama", "voice", "action_engine", "devices"):
            print(f"    {section}: {json.dumps(diagnostic.get(section, {}), ensure_ascii=False)}")
        print()
    elif command in {"/estado", "/memoria"}:
        ok, data = await check_connection()
        if not ok or not data:
            print(f"\n  ⚠ No se puede conectar con {ASSISTANT_NAME} Core\n")
        elif command == "/estado":
            print(f"\n  Estado: {data['status']} | LLM: {data['llm']['backend']} ({data['llm']['status']}) | Modelo: {data['llm']['model']}\n")
        else:
            mem = data["memory"]
            print(f"\n  Mensajes: {mem['total_messages']} | Hechos: {mem['total_facts']} | Sesiones: {mem['total_sessions']} | Backups: {mem.get('last_backup_time') or 'aún ninguno'}\n")
    elif command == "/perfil":
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{CORE_URL}/api/profile", headers=headers()); response.raise_for_status(); profile = response.json()
        print(f"\n  Lo que {ASSISTANT_NAME} recuerda:" if profile else "\n  Aún no hay datos guardados.")
        for category, facts in profile.items():
            print(f"    [{category}] " + "; ".join(facts))
        print()
    elif command == "/nombre":
        if not argument:
            print("\n  Uso: /nombre TuNombre\n")
        else:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(f"{CORE_URL}/api/memory/preference", headers=headers(), json={"key": "user_name", "value": argument}); response.raise_for_status()
            print(f"\n  ✓ Nombre guardado: {argument}\n")
    elif command == "/backup":
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(f"{CORE_URL}/api/backup", headers=headers()); response.raise_for_status(); path = response.json()["path"]
        print(f"\n  ✓ Backup creado: {path}\n")
    elif command == "/probar-proactivo":
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(f"{CORE_URL}/api/proactive/test", headers=headers(), json={"message": "Prueba proactiva superada. El cliente sí me recibe, milagrosamente."}); response.raise_for_status()
        print(f"\n  ✓ Mensaje encolado. Aparecerá en menos de {POLL_SECONDS} segundos.\n")
    elif command == "/limpiar":
        print_banner()
    elif command == "/ayuda":
        print_help()
    else:
        print(f"\n  Comando desconocido: {command}\n")
    return True

async def proactive_poll(auto_play: bool) -> None:
    while True:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{CORE_URL}/api/proactive/check", headers=headers())
                if response.status_code == 200:
                    data = response.json()
                    if data.get("has_message"):
                        print(f"\n  {ASSISTANT_NAME} [proactiva]: {data['message']}\n  Tú > ", end="", flush=True)
                        if auto_play:
                            await play_local_audio(await request_tts(data["message"]))
        except httpx.HTTPError:
            pass
        await asyncio.sleep(POLL_SECONDS)

async def main() -> None:
    global CORE_URL
    parser = argparse.ArgumentParser(description=f"{ASSISTANT_NAME} — Cliente PC")
    parser.add_argument("--voice", action="store_true", help="Habilitar comando /voz")
    parser.add_argument("--auto", action="store_true", help="Reproducir respuestas con voz")
    parser.add_argument("--wake", action="store_true", help=f"Activar wake word experimental '{ASSISTANT_NAME.title()}'")
    parser.add_argument("--profile", choices=("auto", "fast", "normal", "reasoning", "code"), default=os.getenv("LUMEN_LLM_PROFILE", "auto"), help="Perfil LLM para la conversación")
    parser.add_argument("--url", default=CORE_URL, help="URL del Core")
    args = parser.parse_args()
    CORE_URL = args.url.rstrip("/")
    print_banner()
    ok, data = await check_connection()
    if not ok or not data:
        print(f"\n  ⚠ No se pudo conectar a {CORE_URL}\n  Inicia el Core con: start.bat\n")
        return
    print(f"  ✓ Conectado. LLM: {data['llm']['backend']} ({data['llm']['status']}) | Modelo: {data['llm'].get('selected_model', data['llm'].get('model', '--'))} | Perfil: {args.profile}")
    if args.voice:
        print("  ✓ Voz push-to-talk disponible con /voz")
    engine = ActionEngine(PROJECT_DIR)
    listener = None
    if args.wake:
        from wake_word import WakeWordListener
        def on_wake(audio_path: str) -> None:
            async def process() -> None:
                try:
                    result = await execute_action_response(await send_voice(audio_path), engine)
                    print(f"\n  Tú (voz): {result.get('user_text', '?')}\n  {ASSISTANT_NAME}: {result['response']}\n")
                    if args.auto and result.get("audio_url"):
                        await play_remote_audio(result["audio_url"])
                finally:
                    Path(audio_path).unlink(missing_ok=True)
            asyncio.run(process())
        listener = WakeWordListener(on_wake=on_wake); listener.start(); print("  ✓ Wake word experimental activa")
    print_help()
    task = asyncio.create_task(proactive_poll(args.voice and args.auto))
    try:
        while True:
            user_input = (await asyncio.to_thread(input, "  Tú > ")).strip()
            if not user_input:
                continue
            if user_input.startswith("/"):
                parts = user_input.split(" ", 1)
                try:
                    keep_running = await handle_command(parts[0].lower(), parts[1] if len(parts) > 1 else "", args.voice and args.auto, engine)
                except Exception as exc:
                    print(f"\n  ⚠ El comando no se pudo completar, pero la sesión continúa: {exc}\n")
                    keep_running = True
                if not keep_running:
                    break
            else:
                try:
                    data = await send_stream(user_input, engine, profile=args.profile)
                    if data.get("kind") == "chat" and data.get("response"):
                        print(f"  {ASSISTANT_NAME}: {data['response']}\n")
                    if args.voice and args.auto and data.get("response"):
                        await play_local_audio(await request_tts(data["response"]))
                except Exception as exc:
                    print(f"\n  ⚠ GAIA no pudo completar este turno; puedes continuar: {exc}\n")
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        task.cancel(); await asyncio.gather(task, return_exceptions=True)
        if listener:
            listener.stop()
        print("\n  Cliente cerrado.\n")

if __name__ == "__main__":
    asyncio.run(main())
