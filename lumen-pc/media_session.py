from __future__ import annotations

"""Windows System Media Transport Controls adapter.

The adapter talks only to the operating system's Global System Media Transport
Controls session. It deliberately has no provider credentials, web scraping,
window scraping, or application-specific integration.
"""

from dataclasses import dataclass
import asyncio
import platform
from typing import Any


class MediaSessionError(RuntimeError):
    pass


@dataclass
class MockMediaSession:
    title: str = "Tema de prueba"
    artist: str = "Artista de prueba"
    state: str = "paused"

    def status(self) -> dict[str, Any]:
        return {"available": True, "title": self.title, "artist": self.artist, "state": self.state, "source": "mock"}

    def play_pause(self) -> dict[str, Any]:
        self.state = "playing" if self.state != "playing" else "paused"
        return self.status()

    def next(self) -> dict[str, Any]:
        return {**self.status(), "command": "next"}

    def previous(self) -> dict[str, Any]:
        return {**self.status(), "command": "previous"}

    def stop(self) -> dict[str, Any]:
        self.state = "stopped"
        return self.status()


_MOCK_SESSION: MockMediaSession | None = None


def set_mock_session(session: MockMediaSession | None) -> None:
    """Install an in-memory session for deterministic contract tests only."""
    global _MOCK_SESSION
    _MOCK_SESSION = session


def _unavailable(reason: str) -> dict[str, Any]:
    return {"available": False, "title": "", "artist": "", "state": "stopped", "reason": reason, "source": "os.smtc"}


def _run(awaitable: Any) -> Any:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None and loop.is_running():
        raise MediaSessionError("SMTC no puede bloquear un event loop activo.")
    return asyncio.run(awaitable)


async def _current_session_async() -> Any:
    try:
        from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
    except ImportError as exc:
        raise MediaSessionError("El paquete Windows SDK para SMTC no está instalado.") from exc
    manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
    return manager.get_current_session()


def _current_session() -> Any | None:
    if platform.system() != "Windows":
        return None
    try:
        return _run(_current_session_async())
    except MediaSessionError:
        raise
    except Exception as exc:
        raise MediaSessionError(f"SMTC no está disponible: {exc}") from exc


def _state_name(playback_info: Any) -> str:
    raw = getattr(playback_info, "playback_status", None)
    value = str(getattr(raw, "name", raw or "")).casefold()
    if "playing" in value:
        return "playing"
    if "paused" in value:
        return "paused"
    if "stopped" in value or "closed" in value:
        return "stopped"
    return "unknown"


async def _status_async(session: Any) -> dict[str, Any]:
    properties = await session.try_get_media_properties_async()
    playback = session.get_playback_info()
    return {
        "available": True,
        "title": str(getattr(properties, "title", "") or ""),
        "artist": str(getattr(properties, "artist", "") or ""),
        "state": _state_name(playback),
        "source": "os.smtc",
    }


def media_status() -> dict[str, Any]:
    if _MOCK_SESSION is not None:
        return _MOCK_SESSION.status()
    if platform.system() != "Windows":
        return _unavailable("unsupported_os")
    try:
        session = _current_session()
        if session is None:
            return _unavailable("no_active_session")
        return _run(_status_async(session))
    except MediaSessionError as exc:
        return _unavailable(str(exc))
    except Exception as exc:
        return _unavailable(f"SMTC status failed: {exc}")


async def _command_async(session: Any, command: str) -> bool:
    method = {
        "play_pause": "try_toggle_play_pause_async",
        "next": "try_skip_next_async",
        "previous": "try_skip_previous_async",
        "stop": "try_stop_async",
    }.get(command)
    if not method:
        raise MediaSessionError("Comando SMTC no permitido.")
    operation = getattr(session, method, None)
    if operation is None:
        return False
    return bool(await operation())


def _command(command: str) -> dict[str, Any]:
    if _MOCK_SESSION is not None:
        return getattr(_MOCK_SESSION, command)()
    if platform.system() != "Windows":
        return _unavailable("unsupported_os")
    try:
        session = _current_session()
        if session is None:
            return _unavailable("no_active_session")
        accepted = _run(_command_async(session, command))
        status = media_status()
        status["command"] = command
        status["accepted"] = bool(accepted)
        return status
    except MediaSessionError as exc:
        result = _unavailable(str(exc))
        result["command"] = command
        result["accepted"] = False
        return result
    except Exception as exc:
        result = _unavailable(f"SMTC command failed: {exc}")
        result["command"] = command
        result["accepted"] = False
        return result


def media_play_pause() -> dict[str, Any]:
    return _command("play_pause")


def media_next() -> dict[str, Any]:
    return _command("next")


def media_previous() -> dict[str, Any]:
    return _command("previous")


def media_stop() -> dict[str, Any]:
    return _command("stop")
