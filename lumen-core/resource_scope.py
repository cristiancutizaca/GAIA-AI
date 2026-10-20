"""Core-owned resource scope resolution.

Clients must never infer permission scope from action arguments.  This module is
intentionally deterministic, side-effect free, and independent from the PC
executor so the same authority can build confirmation payloads and permission
lookups for desktop and Android requests.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Mapping

RESOURCE_SCOPE_VERSION = "1"

_READ_ONLY_CAPABILITIES = {
    "desktop.context",
    "uia.inspect_window",
    "uia.list_controls",
    "uia.get_focused_control",
    "screen.capture_display",
    "screen.capture_window",
    "media.status",
    "apps.list",
    "apps.is_running",
    "system.status",
    "processes.list",
    "network.status",
    "display.list",
    "display.info",
    "files.exists",
    "files.list",
    "files.info",
}

_MUTATING_CAPABILITIES = {
    "files.delete",
    "files.rename",
    "uia.invoke_control",
    "uia.set_value",
    "media.play_pause",
    "media.next",
    "media.previous",
    "media.stop",
    "windows.close",
    "system.restart",
    "system.shutdown",
}


def _text(value: object, limit: int = 240) -> str:
    return str(value or "").strip()[:limit]


def _canonical_path(raw: object) -> Path | None:
    value = _text(raw)
    if not value:
        return None
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    try:
        return candidate.resolve(strict=False)
    except OSError:
        return candidate.absolute()


def _folder_token(raw: object, *, destination: bool = False) -> str:
    path = _canonical_path(raw)
    if path is None:
        return "folder:unresolved"
    try:
        if destination or not path.is_dir():
            path = path.parent
    except OSError:
        path = path.parent
    digest = sha256(str(path).casefold().encode("utf-8")).hexdigest()[:20]
    return "folder:" + digest


def _safe_token(value: object, fallback: str = "unresolved") -> str:
    token = _text(value, 180)
    token = re.sub(r"[^A-Za-z0-9_.:@/+\-# ]", "_", token)
    token = re.sub(r"\s+", " ", token).strip()
    return token or fallback


def _json_token(value: object) -> str:
    if isinstance(value, Mapping):
        allowed = {
            str(key): value[key]
            for key in ("window_id", "pid", "process_id", "executable", "app_id", "title_fingerprint")
            if value.get(key) not in (None, "")
        }
        return _safe_token(json.dumps(allowed, sort_keys=True, separators=(",", ":")), "unresolved")
    return _safe_token(value, "unresolved")


def _window_identity(parameters: Mapping[str, object]) -> str:
    expected = parameters.get("expected_target")
    if expected is None:
        expected = parameters.get("target_window")
    if expected is None:
        expected = parameters.get("window_identity")
    app = parameters.get("trusted_app_id") or parameters.get("app_id") or parameters.get("app")
    window = _json_token(expected)
    return f"app={_safe_token(app)}|window={window}"


def _path_description(raw: object, *, fallback: str) -> str:
    path = _canonical_path(raw)
    if path is None:
        return fallback
    return str(path)


def _scope_result(scope: str, description: str, *, persistent: bool, kind: str) -> dict:
    return {
        "resource_scope": _text(scope, 500),
        "human_scope_description": _text(description, 500),
        "persistent_grant_allowed": bool(persistent and scope and "unresolved" not in scope),
        "resource_scope_version": RESOURCE_SCOPE_VERSION,
        "resource_kind": kind,
    }


def resolve_resource_scope(capability: str, parameters: Mapping[str, object] | None = None, execution_context: Mapping[str, object] | None = None) -> dict:
    """Resolve the exact permission scope for one structured capability request.

    The function is the sole scope authority.  It never executes filesystem,
    Windows, UIA, media, network, or process operations; it only canonicalizes
    structured parameters and returns metadata for Core confirmation and grant
    lookup.  Missing identity is represented as ``unresolved`` and disables
    persistent grants rather than widening the scope.
    """
    context = execution_context or {}
    capability = _text(capability, 160).casefold()
    legacy_action = _text(context.get("legacy_action"), 80).casefold()
    params: Mapping[str, object] = parameters or {}

    if capability in {"files.copy", "files.move"}:
        source = _folder_token(params.get("source"))
        destination = _folder_token(params.get("destination"), destination=True)
        scope_prefix = legacy_action if legacy_action in {"file_copy", "file_move"} else capability
        scope = f"{scope_prefix}:from={source}->to={destination}"
        description = f"carpeta de origen {_path_description(params.get('source'), fallback='no resuelta')} → carpeta de destino {_path_description(params.get('destination'), fallback='no resuelta')}"
        return _scope_result(scope, description, persistent=True, kind="compound_file")

    if capability in {"files.delete", "files.rename"}:
        path = _canonical_path(params.get("path") or params.get("target") or params.get("resource"))
        scope = "file:" + str(path) if path else "file:unresolved"
        description = _path_description(path, fallback="recurso de archivo no resuelto")
        return _scope_result(scope, description, persistent=False, kind="file_resource")

    if capability in {"files.exists", "files.list", "files.info", "files.open", "folders.open", "folders.create"}:
        path = _canonical_path(params.get("path") or params.get("project"))
        scope = "path:" + str(path) if path else "path:unresolved"
        return _scope_result(scope, _path_description(path, fallback="ruta no resuelta"), persistent=False, kind="path")

    if capability.startswith("uia."):
        identity = _window_identity(params)
        control = _safe_token(params.get("control_id") or params.get("automation_id") or params.get("name"))
        scope = f"uia:{identity}|control={control}"
        if capability in {"uia.inspect_window", "uia.list_controls", "uia.get_focused_control"}:
            persistent = False
        else:
            persistent = bool(params.get("persistent_safe_control", False)) and capability == "uia.focus_control"
        description = f"aplicación/ventana {identity}; control {control}"
        return _scope_result(scope, description, persistent=persistent, kind="uia_control")

    if capability == "screen.capture_display":
        display = _safe_token(params.get("display_id") or params.get("display"))
        return _scope_result(f"display:{display}", f"monitor {display}", persistent=False, kind="display")

    if capability == "screen.capture_window":
        identity = _window_identity(params)
        return _scope_result(f"screen:{identity}", f"ventana {identity}", persistent=False, kind="window_capture")

    if capability.startswith("media."):
        session = _safe_token(params.get("session_id") or params.get("media_session") or "active_media_session")
        persistent = capability == "media.play_pause" or capability == "media.next" or capability == "media.previous"
        return _scope_result(f"media:{session}", f"sesión multimedia {session}", persistent=persistent, kind="media_session")

    if capability.startswith("vscode."):
        project = _safe_token(params.get("project") or params.get("project_id"))
        file_value = _text(params.get("path") or params.get("file"))
        suffix = f"|file={_safe_token(file_value)}" if file_value else ""
        scope = f"vscode:project={project}{suffix}"
        return _scope_result(scope, f"VS Code proyecto {project}{' archivo ' + file_value if file_value else ''}", persistent=True, kind="vscode")

    if capability in {"apps.open", "apps.close", "apps.focus", "apps.minimize", "apps.open_discovered", "apps.is_running"}:
        app = _safe_token(params.get("app_id") or params.get("app"))
        persistent = capability in {"apps.open", "apps.open_discovered", "apps.focus", "apps.minimize"}
        return _scope_result(app, f"aplicación {app}", persistent=persistent, kind="application")

    if capability.startswith("windows."):
        identity = _window_identity(params)
        display = _safe_token(params.get("display_id")) if capability == "windows.move_to_display" else ""
        scope = f"window:{identity}{'|display=' + display if display else ''}"
        return _scope_result(scope, f"ventana {identity}{' al monitor ' + display if display else ''}", persistent=False, kind="window")

    if capability == "desktop.context":
        return _scope_result("desktop:active_context", "contexto activo efímero del escritorio", persistent=False, kind="observation")

    if capability in _READ_ONLY_CAPABILITIES:
        return _scope_result(f"system:{capability}", f"consulta {capability}", persistent=False, kind="observation")

    if capability in _MUTATING_CAPABILITIES or capability.startswith(("files.", "projects.", "system.")):
        return _scope_result(f"capability:{capability}", f"capability {capability}", persistent=False, kind="mutation")

    return _scope_result(f"capability:{capability or 'unresolved'}", f"capability {capability or 'no resuelta'}", persistent=False, kind="unknown")
