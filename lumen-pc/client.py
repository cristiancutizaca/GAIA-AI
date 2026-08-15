"""Cliente PC de LUMEN: terminal, voz push-to-talk y polling proactivo."""
from __future__ import annotations

import argparse
import asyncio
import atexit
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path
import httpx
from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_DIR / ".env")
load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

CORE_URL = os.getenv("LUMEN_CORE_URL", "http://localhost:8090").rstrip("/")
API_SECRET = os.getenv("LUMEN_SECRET", "lumen-dev-key")
DEVICE = f"pc-{platform.system().lower()}"
POLL_SECONDS = max(5, int(os.getenv("LUMEN_PROACTIVE_POLL_SECONDS", "15")))
session_id = ""
_temp_audio: list[Path] = []


def headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {API_SECRET}"}


def cleanup_temp_audio() -> None:
    for path in _temp_audio:
        path.unlink(missing_ok=True)

atexit.register(cleanup_temp_audio)


def clear_screen() -> None:
    if platform.system() == "Windows":
        os.system("cls")
    elif os.getenv("TERM"):
        os.system("clear")

async def check_connection() -> tuple[bool, dict | None]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{CORE_URL}/api/status", headers=headers())
            response.raise_for_status()
            return True, response.json()
    except httpx.HTTPError:
        return False, None

async def send_message(text: str) -> dict:
    global session_id
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(f"{CORE_URL}/api/chat", headers=headers(), json={"message": text, "session_id": session_id, "device": DEVICE})
        response.raise_for_status()
        data = response.json()
    session_id = data.get("session_id", session_id)
    return data

async def send_voice(audio_path: str) -> dict:
    global session_id
    async with httpx.AsyncClient(timeout=180.0) as client:
        with open(audio_path, "rb") as audio_file:
            response = await client.post(f"{CORE_URL}/api/chat/voice", headers=headers(), params={"session_id": session_id, "device": DEVICE}, files={"audio": ("audio.wav", audio_file, "audio/wav")})
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
        audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype="int16")
        sd.wait()
        tmp_path = tempfile.mktemp(suffix=".wav")
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
    print("""
╔══════════════════════════════════════════════╗
║              L   U   M   E   N               ║
║         IA Personal — Cliente PC             ║
╚══════════════════════════════════════════════╝""")


def print_help() -> None:
    print("""
  Comandos:
    /salir              Cerrar cliente
    /voz                Grabar 5 segundos y enviar audio
    /estado             Ver estado del Core
    /memoria            Ver estadísticas de memoria
    /perfil             Ver datos recordados
    /nombre [nombre]    Guardar tu nombre
    /backup             Crear backup inmediato
    /probar-proactivo   Encolar un aviso y recibirlo por polling
    /sesion             Ver sesión actual
    /limpiar            Limpiar pantalla
    /ayuda              Mostrar ayuda
""")

async def handle_command(command: str, argument: str, auto_play: bool) -> bool:
    if command in {"/salir", "/exit", "/q"}:
        return False
    if command == "/voz":
        audio_path = record_audio()
        if audio_path:
            try:
                data = await send_voice(audio_path)
                print(f"\n  Tú (voz): {data.get('user_text', '?')}\n  LUMEN: {data['response']}\n")
                if auto_play and data.get("audio_url"):
                    await play_remote_audio(data["audio_url"])
            finally:
                Path(audio_path).unlink(missing_ok=True)
    elif command == "/sesion":
        print(f"\n  Sesión actual: {session_id or '(nueva)'}\n")
    elif command in {"/estado", "/memoria"}:
        ok, data = await check_connection()
        if not ok or not data:
            print("\n  ⚠ No se puede conectar con LUMEN Core\n")
        elif command == "/estado":
            print(f"\n  Estado: {data['status']} | LLM: {data['llm']['backend']} ({data['llm']['status']}) | Modelo: {data['llm']['model']}\n")
        else:
            mem = data["memory"]
            print(f"\n  Mensajes: {mem['total_messages']} | Hechos: {mem['total_facts']} | Sesiones: {mem['total_sessions']} | Backups: {mem.get('last_backup_time') or 'aún ninguno'}\n")
    elif command == "/perfil":
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{CORE_URL}/api/profile", headers=headers()); response.raise_for_status(); profile = response.json()
        print("\n  Lo que LUMEN recuerda:" if profile else "\n  Aún no hay datos guardados.")
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
                        print(f"\n  LUMEN [proactiva]: {data['message']}\n  Tú > ", end="", flush=True)
                        if auto_play:
                            await play_local_audio(await request_tts(data["message"]))
        except httpx.HTTPError:
            pass
        await asyncio.sleep(POLL_SECONDS)

async def main() -> None:
    global CORE_URL
    parser = argparse.ArgumentParser(description="LUMEN — Cliente PC")
    parser.add_argument("--voice", action="store_true", help="Habilitar comando /voz")
    parser.add_argument("--auto", action="store_true", help="Reproducir respuestas con voz")
    parser.add_argument("--wake", action="store_true", help="Activar wake word experimental 'Lumen'")
    parser.add_argument("--url", default=CORE_URL, help="URL del Core")
    args = parser.parse_args()
    CORE_URL = args.url.rstrip("/")
    print_banner()
    ok, data = await check_connection()
    if not ok or not data:
        print(f"\n  ⚠ No se pudo conectar a {CORE_URL}\n  Inicia el Core con: start.bat\n")
        return
    print(f"  ✓ Conectado. LLM: {data['llm']['backend']} ({data['llm']['status']})")
    if args.voice:
        print("  ✓ Voz push-to-talk disponible con /voz")
    listener = None
    if args.wake:
        from wake_word import WakeWordListener
        def on_wake(audio_path: str) -> None:
            async def process() -> None:
                try:
                    result = await send_voice(audio_path)
                    print(f"\n  Tú (voz): {result.get('user_text', '?')}\n  LUMEN: {result['response']}\n")
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
                if not await handle_command(parts[0].lower(), parts[1] if len(parts) > 1 else "", args.voice and args.auto):
                    break
            else:
                data = await send_message(user_input)
                print(f"\n  LUMEN: {data['response']}\n")
                if args.voice and args.auto:
                    await play_local_audio(await request_tts(data["response"]))
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        task.cancel(); await asyncio.gather(task, return_exceptions=True)
        if listener:
            listener.stop()
        print("\n  Cliente cerrado.\n")

if __name__ == "__main__":
    asyncio.run(main())
