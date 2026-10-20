from __future__ import annotations

"""Safe local execution for GAIA v0.4.

There is intentionally no public ``run(command)`` method. Every operation is
selected by name, validates its parameters, and uses argument lists rather
than arbitrary shell invocation. The engine is usable on Windows and Linux and degrades cleanly
when an optional utility (Git, pytest, nvidia-smi, a terminal, or an editor) is absent.
"""

from dataclasses import dataclass
import json
import os
import platform
from pathlib import Path
import shutil
import subprocess
import time
import webbrowser
from urllib.parse import urlparse
from project_registry import ProjectRegistry, ProjectRegistryError
from safe_apps import consume_discovered_app_once, discover_installed_apps, get_safe_app, is_trusted_executable, list_safe_apps, resolve_discovered_app, resolve_unix_command, resolve_windows_executable
from trusted_folders import is_trusted_path
from desktop_context import get_desktop_context
from screen_capture import capture_display, capture_window
from uia import UIAutomationError, dynamic_control_risk, focus_control, get_focused_control, inspect_window, invoke_control, list_controls, resolve_control_risk, set_control_value, verify_window_identity, window_identity
from capabilities import ACTION_TO_CAPABILITY, CapabilityRequest, CapabilityValidationError, VerifiedCapabilityResult, default_capability_registry
from platform_capabilities import PlatformCapabilityError, audio_devices, audio_get, audio_mute, audio_set, clipboard_read, clipboard_write, display_info, display_list, move_window_to_display, network_adapters, network_ip, power_action, list_windows, window_action
from app_adapters import get_app_adapter
from media_session import media_status, media_play_pause, media_next, media_previous, media_stop


@dataclass(frozen=True)
class ExecutionResult:
    success: bool
    action: str
    message: str
    data: dict
    status: str = ""
    request_validated: bool = True
    execution_attempted: bool = True
    capability_available: bool | None = None
    side_effect_performed: bool = False
    effect_verified: bool = False
    observation_completed: bool = False

    def __post_init__(self) -> None:
        data = dict(self.data or {})
        available = self.capability_available
        if available is None and "available" in data:
            available = bool(data.get("available"))
        status = str(self.status or "").upper()
        if not status:
            status = "UNAVAILABLE" if available is False else ("SUCCESS" if self.success else "FAILED")
        if status == "UNAVAILABLE":
            object.__setattr__(self, "success", False)
            object.__setattr__(self, "capability_available", False)
            object.__setattr__(self, "effect_verified", False)
            object.__setattr__(self, "side_effect_performed", False)
        else:
            object.__setattr__(self, "capability_available", True if available is None else bool(available))
            if status != "SUCCESS":
                object.__setattr__(self, "effect_verified", False)
                object.__setattr__(self, "side_effect_performed", False)
        if status == "SUCCESS" and not self.observation_completed and self.action in {"desktop_context", "windows_list", "uia_inspect_window", "uia_list_controls", "uia_get_focused_control", "screen_capture_display", "screen_capture_window", "list_audio_devices", "media_status", "list_safe_apps", "is_safe_app_running", "system_status", "system_ram", "system_cpu", "system_gpu", "system_disk", "system_processes", "system_network", "git_status", "git_branch", "git_log", "git_diff", "list_projects", "show_project", "file_exists", "file_list", "file_info", "audio_get", "get_volume", "display_list", "display_info", "network_adapters", "network_ip", "process_info", "clipboard_read"}:
            object.__setattr__(self, "observation_completed", bool(self.success))
        if status == "SUCCESS" and self.success and not self.observation_completed and not self.effect_verified and not data.get("dry_run"):
            object.__setattr__(self, "side_effect_performed", True)
            object.__setattr__(self, "effect_verified", bool(data.get("verified", True)))
        object.__setattr__(self, "status", status)

    @property
    def execution_verified(self) -> bool:
        return bool(self.success and (self.effect_verified or self.observation_completed))

    def as_dict(self) -> dict:
        return {
            "success": bool(self.success),
            "action": self.action,
            "message": self.message,
            "data": dict(self.data or {}),
            "status": self.status,
            "request_validated": bool(self.request_validated),
            "execution_attempted": bool(self.execution_attempted),
            "capability_available": self.capability_available,
            "side_effect_performed": bool(self.side_effect_performed),
            "effect_verified": bool(self.effect_verified),
            "observation_completed": bool(self.observation_completed),
            "execution_verified": self.execution_verified,
        }


class ActionEngineError(RuntimeError):
    pass


class ActionEngine:
    SAFE_ACTIONS = {
        "list_safe_apps": (0, False),
        "is_safe_app_running": (0, False),
        "open_vscode": (1, False),
        "open_vscode_new_window": (1, False),
        "open_calculator": (1, False),
        "open_notepad": (1, False),
        "open_spotify": (1, False),
        "open_discovered_app": (2, False),
        "open_browser": (1, False),
        "open_url": (1, False),
        "open_folder": (1, False),
        "open_project": (1, False),
        "system_status": (1, False),
        "system_ram": (1, False),
        "system_cpu": (1, False),
        "system_gpu": (1, False),
        "system_disk": (1, False),
        "git_status": (2, False),
        "run_tests": (2, False),
        "start_project": (2, False),
        "run_project_command": (2, False),
        "system_processes": (1, False),
        "system_network": (1, False),
        "open_terminal": (1, False),
        "stop_gaia_process": (2, False),
        "list_projects": (1, False),
        "show_project": (1, False),
        "close_app": (2, False),
        "focus_app": (1, False),
        "minimize_app": (1, False),
        "file_exists": (0, False),
        "file_list": (0, False),
        "file_info": (0, False),
        "file_open": (1, False),
        "file_delete": (3, False),
        "file_copy": (2, False),
        "file_move": (2, False),
        "file_rename": (2, False),
        "folder_create": (2, False),
        "windows_list": (0, False),
        "windows_focus": (1, False),
        "windows_minimize": (1, False),
        "windows_maximize": (1, False),
        "windows_restore": (1, False),
        "windows_close": (2, False),
        "windows_move_to_display": (1, False),
        "desktop_context": (0, False),
        "uia_inspect_window": (0, False),
        "uia_list_controls": (0, False),
        "uia_get_focused_control": (0, False),
        "uia_focus_control": (1, False),
        "uia_invoke_control": (2, False),
        "uia_set_value": (2, False),
        "vscode_focus": (1, False),
        "vscode_open_project": (1, False),
        "vscode_new_window": (1, False),
        "vscode_open_file_trusted": (1, False),
        "vscode_open_terminal_trusted": (1, False),
        "media_status": (0, False),
        "media_play_pause": (1, False),
        "media_next": (1, False),
        "media_previous": (1, False),
        "media_stop": (1, False),
        "screen_capture_display": (1, False),
        "screen_capture_window": (1, False),
        "list_audio_devices": (0, False),
        "get_volume": (0, False),
        "set_volume": (1, False),
        "mute": (1, False),
        "unmute": (1, False),
        "clipboard_read": (1, False),
        "clipboard_write": (1, False),
        "display_list": (0, False),
        "display_info": (0, False),
        "network_adapters": (0, False),
        "network_ip": (0, False),
        "process_info": (0, False),
        "process_stop": (3, False),
        "git_branch": (0, False),
        "git_log": (0, False),
        "git_diff": (0, False),
        "git_add": (2, False),
        "git_commit": (2, False),
        "system_lock": (3, False),
        "system_sleep": (3, False),
        "system_restart": (4, False),
        "system_shutdown": (4, False),
    }

    def __init__(self, project_dir: Path | None = None, projects_file: Path | None = None) -> None:
        self.project_dir = (project_dir or Path.cwd()).expanduser().resolve()
        self.projects_file = projects_file or Path(os.getenv("GAIA_PROJECTS_FILE", str(self.project_dir / "projects.json"))).expanduser().resolve()
        self.default_project = Path(os.getenv("GAIA_DEFAULT_PROJECT", str(self.project_dir))).expanduser().resolve()
        self.max_output_chars = max(1000, int(os.getenv("GAIA_ACTION_MAX_OUTPUT", "6000")))
        self.registry = ProjectRegistry(self.projects_file, self.project_dir)
        self.process_registry_file = self.project_dir / ".gaia_processes.json"
        self.capability_registry = default_capability_registry()

    def capability_definitions(self) -> list[dict]:
        """Return metadata only; no executor or command is accepted from callers."""
        return [definition.as_dict() for definition in self.capability_registry.all()]

    def execute_capability(self, request: CapabilityRequest, *, allow_execution: bool = True) -> VerifiedCapabilityResult:
        """Execute a validated registry request through an existing safe action."""
        try:
            validated = self.capability_registry.request(
                request.capability,
                request.params,
                device=request.device,
                resource_scope=request.resource_scope,
            )
            action_name = self._legacy_action_for_capability(validated)
            if action_name is None or action_name not in self.SAFE_ACTIONS:
                return VerifiedCapabilityResult(validated.capability, False, "La capability no tiene un adaptador local implementado.", {"implemented": False, "available": False}, execution_verified=False, status="UNAVAILABLE", capability_available=False, execution_attempted=False)
            result = self.execute({"name": action_name, "args": dict(validated.params)}, allow_execution=allow_execution)
            result_data = {**result.data, "legacy_action": action_name, "resource_scope": validated.resource_scope, "dry_run": not allow_execution}
            return VerifiedCapabilityResult(
                validated.capability,
                result.success,
                result.message,
                result_data,
                execution_verified=result.execution_verified,
                status=result.status,
                request_validated=result.request_validated,
                execution_attempted=bool(allow_execution and result.execution_attempted),
                capability_available=result.capability_available,
                side_effect_performed=bool(allow_execution and result.side_effect_performed),
                effect_verified=bool(allow_execution and result.effect_verified),
                observation_completed=bool(allow_execution and result.observation_completed),
            )
        except CapabilityValidationError as exc:
            return VerifiedCapabilityResult(request.capability, False, str(exc), {"validated": False, "available": True}, execution_verified=False, status="DENIED", request_validated=False, execution_attempted=False, capability_available=True)

    @staticmethod
    def _legacy_action_for_capability(request: CapabilityRequest) -> str | None:
        params = dict(request.params)
        if request.capability == "apps.open":
            app = str(params.get("app", "")).casefold()
            if app == "vscode" and bool(params.get("new_window")):
                return "open_vscode_new_window"
            return {"calculator": "open_calculator", "notepad": "open_notepad", "spotify": "open_spotify", "vscode": "open_vscode"}.get(app)
        direct = {
            "apps.list": "list_safe_apps", "apps.open_discovered": "open_discovered_app",
            "apps.is_running": "is_safe_app_running",
            "browser.open": "open_browser",
            "url.open": "open_url",
            "folders.open": "open_folder",
            "projects.open": "open_project",
            "processes.list": "system_processes",
            "network.status": "system_network",
            "git.status": "git_status",
            "projects.list": "list_projects",
            "projects.info": "show_project",
            "projects.tests": "run_tests",
            "projects.start": "start_project",
            "projects.command": "run_project_command",
            "projects.terminal": "open_terminal",
            "apps.close": "close_app", "apps.focus": "focus_app", "apps.minimize": "minimize_app",
            "files.exists": "file_exists", "files.list": "file_list", "files.info": "file_info", "files.open": "file_open", "files.delete": "file_delete", "files.copy": "file_copy", "files.move": "file_move", "files.rename": "file_rename", "folders.create": "folder_create",
            "windows.list": "windows_list", "windows.focus": "windows_focus", "windows.minimize": "windows_minimize", "windows.maximize": "windows_maximize", "windows.restore": "windows_restore", "windows.close": "windows_close", "windows.move_to_display": "windows_move_to_display",
            "desktop.context": "desktop_context", "uia.inspect_window": "uia_inspect_window", "uia.list_controls": "uia_list_controls", "uia.get_focused_control": "uia_get_focused_control", "uia.focus_control": "uia_focus_control", "uia.invoke_control": "uia_invoke_control", "uia.set_value": "uia_set_value", "vscode.focus": "vscode_focus", "vscode.open_project": "vscode_open_project", "vscode.new_window": "vscode_new_window", "vscode.open_file_trusted": "vscode_open_file_trusted", "vscode.open_terminal_trusted": "vscode_open_terminal_trusted", "media.status": "media_status", "media.play_pause": "media_play_pause", "media.next": "media_next", "media.previous": "media_previous", "media.stop": "media_stop", "screen.capture_display": "screen_capture_display", "screen.capture_window": "screen_capture_window",
            "audio.list_devices": "list_audio_devices", "audio.get_volume": "get_volume", "audio.set_volume": "set_volume", "audio.mute": "mute", "audio.unmute": "unmute",
            "clipboard.read": "clipboard_read", "clipboard.write": "clipboard_write", "display.list": "display_list", "display.info": "display_info",
            "network.adapters": "network_adapters", "network.ip": "network_ip", "processes.info": "process_info", "processes.stop": "process_stop",
            "git.branch": "git_branch", "git.log": "git_log", "git.diff": "git_diff", "git.add": "git_add", "git.commit": "git_commit",
            "system.lock": "system_lock", "system.sleep": "system_sleep", "system.restart": "system_restart", "system.shutdown": "system_shutdown",
        }
        if request.capability in direct:
            return direct[request.capability]
        if request.capability == "system.status":
            metric = str(params.get("metric", "")).casefold()
            return {"": "system_status", "ram": "system_ram", "cpu": "system_cpu", "gpu": "system_gpu", "disk": "system_disk"}.get(metric)
        return None

    def execute(self, intent: dict, *, allow_execution: bool = True) -> ExecutionResult:
        started = time.perf_counter()
        name = str(intent.get("name", "")).strip()
        args = dict(intent.get("args") or {})
        if name in {"uia_focus_control", "uia_invoke_control", "uia_set_value"}:
            args.setdefault("_declared_risk", int(intent.get("risk_level", self.SAFE_ACTIONS[name][0])))
        if name not in self.SAFE_ACTIONS:
            return ExecutionResult(False, name or "unknown", "Acción no permitida por GAIA.", {"duration_ms": 0.0})
        if not allow_execution:
            return ExecutionResult(True, name, "Simulación: la acción fue validada y no se ejecutó.", {"dry_run": True, "duration_ms": 0.0}, status="SUCCESS", execution_attempted=False, capability_available=True, side_effect_performed=False, effect_verified=False, observation_completed=False)
        try:
            handler = getattr(self, f"_{name}")
            result = handler(args)
        except ActionEngineError as exc:
            result = ExecutionResult(False, name, str(exc), {})
        except Exception as exc:
            result = ExecutionResult(False, name, f"La acción falló de forma controlada: {exc}", {})
        data = dict(result.data or {})
        data.setdefault("duration_ms", round((time.perf_counter() - started) * 1000, 2))
        return ExecutionResult(result.success, result.action, result.message, data, status=result.status, request_validated=result.request_validated, execution_attempted=result.execution_attempted, capability_available=result.capability_available, side_effect_performed=result.side_effect_performed, effect_verified=result.effect_verified, observation_completed=result.observation_completed)

    def _list_safe_apps(self, _args: dict) -> ExecutionResult:
        apps = discover_installed_apps()
        return ExecutionResult(True, "list_safe_apps", f"Apps conocidas: {', '.join(item['canonical_name'] for item in apps) or 'ninguna'}.", {"apps": apps, "registry": list_safe_apps()})

    def _is_safe_app_running(self, args: dict) -> ExecutionResult:
        app = get_safe_app(str(args.get("app", "")).casefold())
        if not app:
            raise ActionEngineError("La app no pertenece al Safe App Registry.")
        running = False
        observed = False
        try:
            import psutil
            observed = True
            names = {name.casefold() for name in app.process_names}
            for process in psutil.process_iter(["name", "exe"]):
                name = str(process.info.get("name") or "").casefold()
                executable = str(process.info.get("exe") or "").casefold()
                if name in names or any(executable.endswith("/" + candidate) or executable.endswith("\\\\" + candidate) for candidate in names):
                    running = True
                    break
        except (ImportError, OSError):
            observed = False
        return ExecutionResult(True, "is_safe_app_running", f"{app.canonical_name.capitalize()} {'está' if running else 'no está'} en ejecución.", {"app": app.canonical_name, "running": running, "observed": observed})

    @staticmethod
    def _vscode_adapter():
        adapter = get_app_adapter("safe:vscode")
        if adapter is None:
            raise ActionEngineError("El adapter code-owned de VS Code no está disponible.")
        return adapter

    def _vscode_focus(self, _args: dict) -> ExecutionResult:
        adapter = self._vscode_adapter()
        result = self._focus_app({"app": "vscode"})
        return ExecutionResult(result.success, "vscode_focus", result.message, {**result.data, "adapter": adapter.identity})

    def _vscode_new_window(self, _args: dict) -> ExecutionResult:
        adapter = self._vscode_adapter()
        result = self._open_vscode_new_window({})
        return ExecutionResult(result.success, "vscode_new_window", result.message, {**result.data, "adapter": adapter.identity})

    def _vscode_open_project(self, args: dict) -> ExecutionResult:
        adapter = self._vscode_adapter()
        project_name = str(args.get("project", "default"))
        if self.projects_file.exists():
            try:
                registered = self.registry.resolve(project_name)
            except ProjectRegistryError as exc:
                raise ActionEngineError(str(exc)) from exc
            if not registered.trusted:
                raise ActionEngineError("El proyecto debe estar trusted para abrirlo con el adapter VS Code.")
            path = registered.path.resolve()
        else:
            path = self._resolve_project(project_name)
        command = shutil.which("code") or shutil.which("code.cmd")
        if not command:
            raise ActionEngineError("No encuentro VS Code mediante el adapter code-owned.")
        self._spawn([command, "--reuse-window", str(path)])
        return ExecutionResult(True, "vscode_open_project", f"Abrí el proyecto trusted {path.name} en VS Code.", {"adapter": adapter.identity, "project": str(path), "verified": True})

    def _vscode_open_file_trusted(self, args: dict) -> ExecutionResult:
        adapter = self._vscode_adapter()
        path = self._safe_file(args.get("path", ""), must_exist=True, write=False)
        if not path.is_file():
            raise ActionEngineError("vscode.open_file_trusted requiere un archivo.")
        command = shutil.which("code") or shutil.which("code.cmd")
        if not command:
            raise ActionEngineError("No encuentro VS Code mediante el adapter code-owned.")
        self._spawn([command, "--reuse-window", str(path)])
        return ExecutionResult(True, "vscode_open_file_trusted", f"Abrí {path.name} en VS Code desde un scope trusted.", {"adapter": adapter.identity, "path": str(path), "verified": True})

    def _vscode_open_terminal_trusted(self, args: dict) -> ExecutionResult:
        adapter = self._vscode_adapter()
        result = self._open_terminal({"project": args.get("project", "default")})
        return ExecutionResult(result.success, "vscode_open_terminal_trusted", result.message, {**result.data, "adapter": adapter.identity})

    @staticmethod
    def _media_result(action: str, payload: dict) -> ExecutionResult:
        available = bool(payload.get("available"))
        if available:
            state = str(payload.get("state", "unknown"))
            title = str(payload.get("title", "") or "")
            artist = str(payload.get("artist", "") or "")
            message = f"Media {state}: {title} — {artist}" if title or artist else f"Media {state}."
            return ExecutionResult(True, action, message, payload)
        return ExecutionResult(False, action, "No hay una sesión multimedia SMTC disponible en este equipo.", payload)

    def _media_status(self, _args: dict) -> ExecutionResult:
        return self._media_result("media_status", media_status())

    def _media_play_pause(self, _args: dict) -> ExecutionResult:
        return self._media_result("media_play_pause", media_play_pause())

    def _media_next(self, _args: dict) -> ExecutionResult:
        return self._media_result("media_next", media_next())

    def _media_previous(self, _args: dict) -> ExecutionResult:
        return self._media_result("media_previous", media_previous())

    def _media_stop(self, _args: dict) -> ExecutionResult:
        return self._media_result("media_stop", media_stop())

    def _open_vscode(self, _args: dict) -> ExecutionResult:
        running = self._find_running_vscode()
        if running:
            return ExecutionResult(True, "open_vscode", "VS Code ya está abierto; no lancé otra instancia.", {"already_open": True, "pid": running})
        command = shutil.which("code") or shutil.which("code.cmd")
        if not command:
            raise ActionEngineError("No encuentro el comando de VS Code ('code') en PATH.")
        self._spawn([command])
        return ExecutionResult(True, "open_vscode", "VS Code se está abriendo.", {"already_open": False})

    def _open_vscode_new_window(self, _args: dict) -> ExecutionResult:
        app = get_safe_app("vscode")
        if not app:
            raise ActionEngineError("La app VS Code no está registrada en el catálogo seguro.")
        command = self._registered_app_command(app)
        if not command:
            raise ActionEngineError("No encuentro VS Code mediante el registro seguro de aplicaciones.")
        self._spawn([*command, "--new-window"])
        return ExecutionResult(True, "open_vscode_new_window", "Se aceptó el lanzamiento de una nueva ventana de VS Code.", {"app": "vscode", "new_window": True, "command": [*command, "--new-window"]})

    def _open_calculator(self, _args: dict) -> ExecutionResult:
        return self._open_registered_app("calculator", "open_calculator")

    def _open_notepad(self, _args: dict) -> ExecutionResult:
        return self._open_registered_app("notepad", "open_notepad")

    def _open_spotify(self, _args: dict) -> ExecutionResult:
        return self._open_registered_app("spotify", "open_spotify")

    def _open_discovered_app(self, args: dict) -> ExecutionResult:
        app_id = str(args.get("app_id", "")).strip()
        item = resolve_discovered_app(app_id, require_trusted=True)
        if not item:
            raise ActionEngineError("La aplicación está descubierta pero no trusted; autorízala desde el panel de Apps.")
        definition = item.get("launch_definition") if isinstance(item.get("launch_definition"), dict) else {}
        if definition.get("kind") != "executable":
            raise ActionEngineError("La launch definition de la app no es ejecutable de forma segura.")
        path = Path(str(definition.get("path", ""))).expanduser()
        try:
            resolved = path.resolve(strict=True)
        except OSError as exc:
            raise ActionEngineError("El ejecutable trusted ya no existe; vuelve a descubrir la app.") from exc
        if not resolved.is_file() or resolved.suffix.casefold() != ".exe":
            raise ActionEngineError("El ejecutable trusted no es un .exe válido.")
        self._spawn([str(resolved)])
        consumed_once = consume_discovered_app_once(app_id)
        return ExecutionResult(True, "open_discovered_app", f"Se aceptó el lanzamiento de {item.get('display_name', app_id)} con una definición trusted.", {"app_id": app_id, "path": str(resolved), "trusted": True, "trust_consumed": consumed_once})

    def _open_registered_app(self, canonical_name: str, action_name: str) -> ExecutionResult:
        app = get_safe_app(canonical_name)
        if not app:
            raise ActionEngineError(f"La aplicación {canonical_name!r} no está registrada.")
        command = self._registered_app_command(app)
        if not command:
            message = f"{canonical_name.capitalize()} no está disponible en este equipo."
            return ExecutionResult(False, action_name, message, {"app": canonical_name, "installed": False})
        self._spawn(command)
        return ExecutionResult(True, action_name, f"Se aceptó el lanzamiento de {canonical_name}; el sistema confirmó el proceso inicial.", {"app": canonical_name, "installed": True, "command": command})

    @staticmethod
    def _registered_app_command(app) -> list[str] | None:
        system = platform.system()
        if system == "Windows":
            executable = resolve_windows_executable(app)
            return [executable] if executable else None
        if system == "Darwin":
            opener = shutil.which("open")
            return [opener, "-a", app.mac_app_name] if opener and app.mac_app_name else None
        return resolve_unix_command(app)

    def _find_running_vscode(self) -> int | None:
        try:
            import psutil
            for process in psutil.process_iter(["pid", "name", "exe"]):
                name = str(process.info.get("name") or "").casefold()
                executable = str(process.info.get("exe") or "").casefold()
                if name in {"code", "code.exe", "code - insiders", "code - insiders.exe"} or executable.endswith(("/code", "\\code.exe", "/code-insiders", "\\code-insiders.exe")):
                    return int(process.info["pid"])
        except (ImportError, OSError):
            return None
        except Exception:
            return None
        return None

    def _open_browser(self, _args: dict) -> ExecutionResult:
        if not webbrowser.open("about:blank"):
            raise ActionEngineError("El sistema no pudo abrir el navegador predeterminado.")
        return ExecutionResult(True, "open_browser", "El navegador se está abriendo.", {})

    def _open_url(self, args: dict) -> ExecutionResult:
        url = self._url(args.get("url", ""))
        if not webbrowser.open(url):
            raise ActionEngineError("El sistema no pudo abrir la URL.")
        return ExecutionResult(True, "open_url", f"Abrí {url}.", {"url": url})

    def _open_folder(self, args: dict) -> ExecutionResult:
        path = self._safe_path(args.get("path", ""), must_exist=True)
        self._open_path(path)
        return ExecutionResult(True, "open_folder", f"Abrí la carpeta {path}.", {"path": str(path)})

    def _open_project(self, args: dict) -> ExecutionResult:
        path = self._resolve_project(args.get("project", "default"))
        self._open_path(path)
        return ExecutionResult(True, "open_project", f"Abrí el proyecto {path.name}.", {"path": str(path)})

    def _system_status(self, _args: dict) -> ExecutionResult:
        data = {**self._system_ram({}).data, **self._system_cpu({}).data, **self._system_disk({}).data}
        gpu = self._system_gpu({})
        data.update(gpu.data)
        return ExecutionResult(True, "system_status", self._format_status(data), data)

    def _system_ram(self, _args: dict) -> ExecutionResult:
        data = self._memory_stats()
        return ExecutionResult(True, "system_ram", f"RAM: {data['ram_used_percent']:.1f}% usada ({data['ram_used_gb']:.1f}/{data['ram_total_gb']:.1f} GB).", data)

    def _system_cpu(self, _args: dict) -> ExecutionResult:
        data = self._cpu_stats()
        return ExecutionResult(True, "system_cpu", f"CPU: {data['cpu_percent']:.1f}% de uso.", data)

    def _system_gpu(self, _args: dict) -> ExecutionResult:
        command = shutil.which("nvidia-smi")
        if command:
            result = self._run([command, "--query-gpu=name,utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"], timeout=15)
            if result.returncode == 0 and result.stdout.strip():
                row = [part.strip() for part in result.stdout.splitlines()[0].split(",")]
                if len(row) >= 4:
                    data = {"gpu_name": row[0], "gpu_percent": self._number(row[1]), "gpu_memory_used_mb": self._number(row[2]), "gpu_memory_total_mb": self._number(row[3])}
                    return ExecutionResult(True, "system_gpu", f"GPU: {row[0]}, uso {row[1]}%, memoria {row[2]}/{row[3]} MB.", data)
        return ExecutionResult(True, "system_gpu", "No pude obtener métricas de GPU (nvidia-smi no está disponible).", {"gpu_available": False})

    def _system_disk(self, _args: dict) -> ExecutionResult:
        usage = shutil.disk_usage(self.project_dir)
        data = {"disk_total_gb": usage.total / 1e9, "disk_used_gb": (usage.total - usage.free) / 1e9, "disk_free_gb": usage.free / 1e9, "disk_used_percent": (usage.total - usage.free) / usage.total * 100}
        return ExecutionResult(True, "system_disk", f"Disco: {data['disk_used_percent']:.1f}% usado; quedan {data['disk_free_gb']:.1f} GB libres.", data)

    def _git_status(self, args: dict) -> ExecutionResult:
        path = self._safe_path(args.get("path") or str(self.project_dir), must_exist=True)
        if not (path / ".git").exists() and not (path / ".git").is_file():
            raise ActionEngineError(f"{path} no parece ser un repositorio Git.")
        result = self._run(["git", "-C", str(path), "status", "--short", "--branch"], timeout=30)
        if result.returncode != 0:
            raise ActionEngineError(self._output(result) or "Git status falló.")
        output = self._output(result) or "árbol limpio"
        return ExecutionResult(True, "git_status", f"Estado de Git en {path}:\n{output}", {"path": str(path), "output": output})

    def _run_tests(self, args: dict) -> ExecutionResult:
        raw_path = args.get("path") or str(self.project_dir)
        path = self._safe_path(raw_path, must_exist=True)
        project = self._registered_project_for_path(path)
        if not project or not project.trusted:
            raise ActionEngineError("Los tests ejecutables solo están permitidos en proyectos registrados como trusted.")
        command_name = str(args.get("command", "tests"))
        commands = project.commands.get(command_name)
        if not commands:
            raise ActionEngineError("No encuentro un comando de tests registrado para ese proyecto trusted.")
        result = self._run(list(commands), cwd=project.working_directory, timeout=600)
        output = self._output(result)
        if result.returncode != 0:
            return ExecutionResult(False, "run_tests", f"Los tests terminaron con código {result.returncode}.\n{output}", {"returncode": result.returncode, "output": output})
        return ExecutionResult(True, "run_tests", f"Tests completados correctamente.\n{output}", {"returncode": 0, "output": output})

    def _start_project(self, args: dict) -> ExecutionResult:
        try:
            project = self.registry.resolve(args.get("project", "default"))
        except ProjectRegistryError as exc:
            raise ActionEngineError(str(exc)) from exc
        if not project.trusted:
            raise ActionEngineError(f"El proyecto {project.name!r} no está marcado como trusted; iniciar procesos requiere confianza explícita.")
        command_name = str(args.get("command", "start"))
        command = project.commands.get(command_name) or project.commands.get("backend") or project.commands.get("frontend") or project.commands.get("start")
        if not command:
            raise ActionEngineError(f"El proyecto {project.name!r} no tiene un comando registrado para iniciar.")
        process = self._spawn(list(command), cwd=project.working_directory)
        self._remember_process(process, project.name, command)
        return ExecutionResult(True, "start_project", f"Inicié el proyecto {project.name} con un comando registrado.", {"project": project.name, "path": str(project.path), "command": list(command), "pid": process.pid})

    def _run_project_command(self, args: dict) -> ExecutionResult:
        try:
            project = self.registry.resolve(args.get("project", "default"))
        except ProjectRegistryError as exc:
            raise ActionEngineError(str(exc)) from exc
        if not project.trusted:
            raise ActionEngineError(f"El proyecto {project.name!r} no está marcado como trusted; los comandos requieren confianza explícita.")
        command_name = str(args.get("command", "tests"))
        command = project.commands.get(command_name)
        if not command:
            raise ActionEngineError(f"El proyecto {project.name!r} no tiene el comando registrado {command_name!r}.")
        result = self._run(list(command), cwd=project.working_directory, timeout=600)
        output = self._output(result)
        return ExecutionResult(result.returncode == 0, "run_project_command", f"Comando {command_name} en {project.name}: código {result.returncode}.\n{output}", {"project": project.name, "command": list(command), "returncode": result.returncode, "output": output})

    def _list_projects(self, _args: dict) -> ExecutionResult:
        try:
            projects = []
            seen: set[str] = set()
            for item in self.registry.list_projects():
                canonical = str(item.name).strip().casefold()
                if not canonical or canonical in seen:
                    continue
                seen.add(canonical)
                projects.append(item.as_dict())
        except ProjectRegistryError as exc:
            raise ActionEngineError(str(exc)) from exc
        return ExecutionResult(True, "list_projects", f"Proyectos registrados: {', '.join(item['name'] for item in projects) or 'ninguno'}.", {"projects": projects})

    def _show_project(self, args: dict) -> ExecutionResult:
        try:
            project = self.registry.resolve(args.get("project", "default"))
        except ProjectRegistryError as exc:
            raise ActionEngineError(str(exc)) from exc
        return ExecutionResult(True, "show_project", f"Proyecto {project.name}: {project.path}.", {"project": project.as_dict()})

    def _system_processes(self, _args: dict) -> ExecutionResult:
        rows: list[dict] = []
        try:
            import psutil
            for proc in sorted(psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_percent"]), key=lambda p: p.info.get("memory_percent") or 0, reverse=True)[:20]:
                rows.append({key: proc.info.get(key) for key in ("pid", "name", "username", "cpu_percent", "memory_percent")})
        except (ImportError, Exception):
            command = ["tasklist", "/FO", "CSV", "/NH"] if platform.system() == "Windows" else ["ps", "-eo", "pid,comm,%cpu,%mem", "--sort=-%cpu"]
            result = self._run(command, timeout=15)
            rows = [{"raw": line[:240]} for line in result.stdout.splitlines()[:20]]
        return ExecutionResult(True, "system_processes", f"He consultado una lista limitada de {len(rows)} procesos.", {"processes": rows})

    def _system_network(self, _args: dict) -> ExecutionResult:
        import socket
        hostname = socket.gethostname()
        addresses = sorted({item[4][0] for item in socket.getaddrinfo(hostname, None) if item[4] and item[4][0]})
        return ExecutionResult(True, "system_network", f"Equipo {hostname}; direcciones detectadas: {', '.join(addresses) or 'ninguna'}.", {"hostname": hostname, "addresses": addresses})

    def _open_terminal(self, args: dict) -> ExecutionResult:
        project_name = args.get("project", "default")
        if self.projects_file.exists():
            try:
                project = self.registry.resolve(project_name)
            except ProjectRegistryError as exc:
                raise ActionEngineError(str(exc)) from exc
            if not project.trusted:
                raise ActionEngineError("Abrir terminal con contexto de proyecto requiere un proyecto trusted.")
        path = self._resolve_project(project_name)
        system = platform.system()
        if system == "Windows":
            command = ["powershell.exe", "-NoExit", "-Command", f"Set-Location -LiteralPath '{str(path).replace(chr(39), chr(39) + chr(39))}'"]
        else:
            terminal = shutil.which("x-terminal-emulator") or shutil.which("gnome-terminal") or shutil.which("konsole")
            if not terminal:
                raise ActionEngineError("No encuentro un emulador de terminal compatible.")
            command = [terminal, "--working-directory", str(path)] if Path(terminal).name != "x-terminal-emulator" else [terminal, "--working-directory", str(path)]
        self._spawn(command)
        return ExecutionResult(True, "open_terminal", f"Abrí una terminal en {path}.", {"path": str(path)})

    def _stop_gaia_process(self, args: dict) -> ExecutionResult:
        pid = int(str(args.get("pid", "0"))) if str(args.get("pid", "0")).isdigit() else 0
        records = self._load_processes()
        record = next((item for item in records if int(item.get("pid", 0)) == pid), None)
        if not record:
            raise ActionEngineError("Solo puedo detener procesos que GAIA haya iniciado y registrado.")
        try:
            requested_creation = float(str(args.get("creation_time", "")))
        except ValueError as exc:
            raise ActionEngineError("Para detener un proceso se requiere creation_time validado por GAIA.") from exc
        if abs(float(record.get("creation_time", -1)) - requested_creation) > 0.01:
            raise ActionEngineError("Identidad de proceso no coincide; no se ejecutará terminate.")
        try:
            import psutil
            proc = psutil.Process(pid)
            current_creation = float(proc.create_time())
            if abs(current_creation - requested_creation) > 0.01:
                raise ActionEngineError("El PID fue reutilizado o cambió su creation_time; no se ejecutará terminate.")
            current_executable = ""
            try:
                current_executable = proc.exe()
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass
            if record.get("executable") and current_executable and Path(current_executable).resolve() != Path(str(record["executable"])).resolve():
                raise ActionEngineError("El ejecutable actual no coincide con el proceso registrado; no se ejecutará terminate.")
            current_command = []
            try:
                current_command = proc.cmdline()
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass
            if record.get("command") and current_command and list(record["command"]) != current_command:
                raise ActionEngineError("La identidad command del proceso no coincide; no se ejecutará terminate.")
            proc.terminate()
        except ImportError as exc:
            raise ActionEngineError("psutil es necesario para detener procesos con protección contra PID reuse.") from exc
        except ActionEngineError:
            raise
        except Exception as exc:
            raise ActionEngineError(f"No se pudo detener el proceso registrado: {exc}") from exc
        self._save_processes([item for item in records if int(item.get("pid", 0)) != pid])
        return ExecutionResult(True, "stop_gaia_process", f"Detuve el proceso registrado {pid}.", {"pid": pid, "project": record.get("project")})

    def _close_app(self, args: dict) -> ExecutionResult:
        app = get_safe_app(str(args.get("app", "")).casefold())
        if not app:
            raise ActionEngineError("La app no pertenece al Safe App Registry.")
        try:
            import psutil
            matches = []
            for proc in psutil.process_iter(["pid", "name", "exe"]):
                name = str(proc.info.get("name") or "").casefold()
                exe = str(proc.info.get("exe") or "").casefold()
                if name in {item.casefold() for item in app.process_names} or any(exe.endswith("\\" + item.casefold()) or exe.endswith("/" + item.casefold()) for item in app.process_names):
                    matches.append(proc)
            if not matches:
                return ExecutionResult(False, "close_app", f"{app.canonical_name.capitalize()} no está en ejecución.", {"app": app.canonical_name, "closed": False})
            for proc in matches:
                proc.terminate()
            return ExecutionResult(True, "close_app", f"Solicité el cierre de {app.canonical_name}.", {"app": app.canonical_name, "closed": len(matches), "verified": True})
        except ImportError as exc:
            raise ActionEngineError("psutil es necesario para cerrar apps con identidad de proceso.") from exc
        except Exception as exc:
            raise ActionEngineError(f"No se pudo cerrar la aplicación de forma controlada: {exc}") from exc

    def _focus_app(self, args: dict) -> ExecutionResult:
        app = get_safe_app(str(args.get("app", "")).casefold())
        if not app:
            raise ActionEngineError("La app no pertenece al Safe App Registry.")
        if platform.system() != "Windows":
            return ExecutionResult(False, "focus_app", "El enfoque estructurado de ventanas solo está implementado para Windows.", {"app": app.canonical_name, "implemented": True, "available": False})
        try:
            import psutil
            pid = next((int(proc.info["pid"]) for proc in psutil.process_iter(["pid", "name"]) if str(proc.info.get("name") or "").casefold() in {item.casefold() for item in app.process_names}), 0)
            if not pid:
                return ExecutionResult(False, "focus_app", f"{app.canonical_name.capitalize()} no está en ejecución.", {"app": app.canonical_name})
            from platform_capabilities import focus_process_windows
            result = focus_process_windows(pid)
            return ExecutionResult(True, "focus_app", f"Enfoqué {app.canonical_name}.", {"app": app.canonical_name, **result})
        except (ImportError, PlatformCapabilityError) as exc:
            raise ActionEngineError(str(exc)) from exc

    def _minimize_app(self, args: dict) -> ExecutionResult:
        app = get_safe_app(str(args.get("app", "")).casefold())
        if not app:
            raise ActionEngineError("La app no pertenece al Safe App Registry.")
        if platform.system() != "Windows":
            return ExecutionResult(False, "minimize_app", "La minimización estructurada solo está implementada para Windows.", {"app": app.canonical_name, "available": False})
        try:
            import psutil
            pid = next((int(proc.info["pid"]) for proc in psutil.process_iter(["pid", "name"]) if str(proc.info.get("name") or "").casefold() in {item.casefold() for item in app.process_names}), 0)
            if not pid:
                return ExecutionResult(False, "minimize_app", f"{app.canonical_name.capitalize()} no está en ejecución.", {"app": app.canonical_name})
            from platform_capabilities import minimize_process_windows
            result = minimize_process_windows(pid)
            return ExecutionResult(True, "minimize_app", f"Minimicé {app.canonical_name}.", {"app": app.canonical_name, **result})
        except (ImportError, PlatformCapabilityError) as exc:
            raise ActionEngineError(str(exc)) from exc

    def _file_exists(self, args: dict) -> ExecutionResult:
        path = self._safe_file(args.get("path", ""), must_exist=False, write=False)
        return ExecutionResult(True, "file_exists", f"La ruta {'existe' if path.exists() else 'no existe'}.", {"path": str(path), "exists": path.exists()})

    def _list_files(self, args: dict) -> ExecutionResult:
        raw = args.get("path") or str(self.project_dir)
        path = self._safe_file(raw, must_exist=True, write=False)
        if not path.is_dir():
            raise ActionEngineError("files.list requiere una carpeta.")
        rows = [{"name": item.name, "is_dir": item.is_dir(), "size": item.stat().st_size if item.is_file() else None} for item in sorted(path.iterdir(), key=lambda item: item.name.casefold())[:200]]
        return ExecutionResult(True, "file_list", f"Listé {len(rows)} elementos sin leer su contenido.", {"path": str(path), "entries": rows})

    def _file_info(self, args: dict) -> ExecutionResult:
        path = self._safe_file(args.get("path", ""), must_exist=True, write=False)
        stat = path.stat()
        return ExecutionResult(True, "file_info", f"Metadata disponible para {path.name}.", {"path": str(path), "name": path.name, "is_file": path.is_file(), "is_dir": path.is_dir(), "size": stat.st_size, "modified": stat.st_mtime})

    def _open_file(self, args: dict) -> ExecutionResult:
        path = self._safe_file(args.get("path", ""), must_exist=True, write=False)
        if not path.is_file():
            raise ActionEngineError("files.open requiere un archivo.")
        self._open_path(path)
        return ExecutionResult(True, "file_open", f"Abrí {path.name} mediante la asociación del sistema.", {"path": str(path), "verified": True})

    def _file_delete(self, args: dict) -> ExecutionResult:
        path = self._safe_file(args.get("path", ""), must_exist=True, right="DELETE")
        if path == self.project_dir or path == Path.home():
            raise ActionEngineError("No se permite eliminar la raíz del proyecto ni el home.")
        trash = self.project_dir / ".gaia-trash"
        trash.mkdir(parents=True, exist_ok=True)
        destination = trash / f"{int(time.time() * 1000)}-{path.name}"
        shutil.move(str(path), str(destination))
        return ExecutionResult(True, "file_delete", f"Moví {path.name} a la papelera reversible de GAIA.", {"path": str(path), "trash_path": str(destination), "reversible": True, "verified": True})

    def _file_copy(self, args: dict) -> ExecutionResult:
        source = self._safe_file(args.get("source", ""), must_exist=True, right="COPY_FROM")
        destination = self._safe_file(args.get("destination", ""), must_exist=False, right="COPY_TO")
        self._ensure_allowed_parent(destination, right="COPY_TO")
        if destination.exists():
            raise ActionEngineError("El destino ya existe; no sobrescribiré sin una capability explícita.")
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)
        return ExecutionResult(True, "file_copy", f"Copié {source.name}.", {"source": str(source), "destination": str(destination), "verified": destination.exists()})

    def _file_move(self, args: dict) -> ExecutionResult:
        source = self._safe_file(args.get("source", ""), must_exist=True, right="MOVE_FROM")
        destination = self._safe_file(args.get("destination", ""), must_exist=False, right="MOVE_TO")
        self._ensure_allowed_parent(destination, right="MOVE_TO")
        if destination.exists():
            raise ActionEngineError("El destino ya existe; no sobrescribiré sin una capability explícita.")
        shutil.move(str(source), str(destination))
        return ExecutionResult(True, "file_move", f"Moví {source.name}.", {"source": str(source), "destination": str(destination), "verified": destination.exists()})

    def _file_rename(self, args: dict) -> ExecutionResult:
        source = self._safe_file(args.get("path", ""), must_exist=True, right="RENAME")
        name = str(args.get("name", "")).strip()
        if not name or name in {".", ".."} or any(char in name for char in ("/", "\\", "\x00")):
            raise ActionEngineError("El nombre no es seguro.")
        destination = source.with_name(name)
        self._ensure_allowed_parent(destination, right="RENAME")
        if destination.exists():
            raise ActionEngineError("El nombre destino ya existe.")
        source.rename(destination)
        return ExecutionResult(True, "file_rename", f"Renombré {source.name} a {destination.name}.", {"source": str(source), "destination": str(destination), "verified": destination.exists()})

    def _create_folder(self, args: dict) -> ExecutionResult:
        path = self._safe_file(args.get("path", ""), must_exist=False, right="CREATE")
        self._ensure_allowed_parent(path, right="CREATE")
        path.mkdir(parents=True, exist_ok=False)
        return ExecutionResult(True, "folder_create", f"Creé la carpeta {path.name}.", {"path": str(path), "verified": path.is_dir()})

    def _windows_list(self, _args: dict) -> ExecutionResult:
        try:
            rows = list_windows()
            return ExecutionResult(True, "windows_list", f"Encontré {len(rows)} ventanas visibles.", {"windows": rows, "os": platform.system(), "available": True, "observation_completed": True})
        except PlatformCapabilityError as exc:
            return ExecutionResult(False, "windows_list", str(exc), {"windows": [], "available": False, "os": platform.system(), "observation_completed": False}, status="UNAVAILABLE")

    def _verify_expected_window_target(self, args: dict) -> None:
        expected = args.get("expected_target")
        if not expected:
            return
        if not isinstance(expected, dict):
            raise ActionEngineError("expected_target de ventana debe ser un objeto estructurado.")
        try:
            verify_window_identity(str(args.get("window_id", "")), expected)
        except UIAutomationError as exc:
            raise ActionEngineError(str(exc)) from exc

    def _windows_window_action(self, args: dict, operation: str, action: str) -> ExecutionResult:
        try:
            self._verify_expected_window_target(args)
            data = window_action(str(args.get("window_id", "")), operation)
            return ExecutionResult(True, action, f"Operación de ventana verificada: {operation}.", data)
        except PlatformCapabilityError as exc:
            raise ActionEngineError(str(exc)) from exc

    def _windows_focus(self, args: dict) -> ExecutionResult:
        return self._windows_window_action(args, "focus", "windows_focus")

    def _windows_minimize(self, args: dict) -> ExecutionResult:
        return self._windows_window_action(args, "minimize", "windows_minimize")

    def _windows_maximize(self, args: dict) -> ExecutionResult:
        return self._windows_window_action(args, "maximize", "windows_maximize")

    def _windows_restore(self, args: dict) -> ExecutionResult:
        return self._windows_window_action(args, "restore", "windows_restore")

    def _windows_close(self, args: dict) -> ExecutionResult:
        return self._windows_window_action(args, "close", "windows_close")

    def _windows_move_to_display(self, args: dict) -> ExecutionResult:
        try:
            self._verify_expected_window_target(args)
            data = move_window_to_display(str(args.get("window_id", "")), str(args.get("display_id", "")))
            return ExecutionResult(True, "windows_move_to_display", "Moví la ventana al monitor solicitado y verifiqué su rectángulo.", data)
        except PlatformCapabilityError as exc:
            raise ActionEngineError(str(exc)) from exc

    def _desktop_context(self, args: dict) -> ExecutionResult:
        data = get_desktop_context(force_refresh=bool(args.get("force_refresh", False)))
        return ExecutionResult(True, "desktop_context", "Consulté el contexto activo estructurado sin capturar pantalla.", data)

    @staticmethod
    def _context_window_id(args: dict, *, required: bool = True) -> str:
        value = str(args.get("window_id") or "").strip()
        if value:
            if not value.isdigit() or int(value) <= 0:
                raise ActionEngineError("window_id debe ser numérico y positivo.")
            return value
        context = get_desktop_context(force_refresh=True)
        active = context.get("active_window") if isinstance(context, dict) else None
        value = str(active.get("window_id") or "").strip() if isinstance(active, dict) else ""
        if required and not value:
            raise ActionEngineError("No hay una ventana activa estructurada para resolver este target.")
        return value

    def _uia_inspect_window(self, args: dict) -> ExecutionResult:
        window_id = self._context_window_id(args)
        try:
            target = self._optional_expected_window_target(args)
            data = inspect_window(window_id, max_controls=int(args.get("max_controls", 100)))
            if target:
                data["target"] = target
            return ExecutionResult(True, "uia_inspect_window", "Inspeccioné la ventana seleccionada mediante UI Automation read-only.", data)
        except UIAutomationError as exc:
            return ExecutionResult(False, "uia_inspect_window", str(exc), {"available": False, "window_id": window_id, "observation_completed": False}, status="UNAVAILABLE")

    def _uia_list_controls(self, args: dict) -> ExecutionResult:
        window_id = self._context_window_id(args)
        try:
            target = self._optional_expected_window_target(args)
            data = list_controls(window_id, max_controls=int(args.get("max_controls", 100)))
            if target:
                data["target"] = target
            return ExecutionResult(True, "uia_list_controls", "Listé controles estructurados sin exponer valores sensibles.", data)
        except UIAutomationError as exc:
            return ExecutionResult(False, "uia_list_controls", str(exc), {"available": False, "window_id": window_id, "controls": [], "observation_completed": False}, status="UNAVAILABLE")

    def _uia_get_focused_control(self, args: dict) -> ExecutionResult:
        window_id = self._context_window_id(args)
        try:
            target = self._optional_expected_window_target(args)
            data = get_focused_control(window_id, max_controls=int(args.get("max_controls", 200)))
            if target:
                data["target"] = target
            return ExecutionResult(True, "uia_get_focused_control", "Consulté el control enfocado mediante UI Automation read-only.", data)
        except UIAutomationError as exc:
            return ExecutionResult(False, "uia_get_focused_control", str(exc), {"available": False, "window_id": window_id, "control": None, "observation_completed": False}, status="UNAVAILABLE")

    def _optional_expected_window_target(self, args: dict) -> dict | None:
        expected = args.get("expected_target")
        if expected in (None, {}):
            return None
        if not isinstance(expected, dict) or not expected:
            raise ActionEngineError("expected_target debe ser un snapshot estructurado.")
        try:
            return verify_window_identity(self._context_window_id(args), expected)
        except UIAutomationError as exc:
            raise ActionEngineError(str(exc)) from exc

    def _uia_interaction_target(self, args: dict) -> tuple[str, dict]:
        window_id = self._context_window_id(args)
        expected = args.get("expected_target")
        if not isinstance(expected, dict) or not expected:
            raise ActionEngineError("La interacción UIA requiere expected_target estructurado.")
        try:
            identity = verify_window_identity(window_id, expected)
        except UIAutomationError as exc:
            raise ActionEngineError(str(exc)) from exc
        executable = str(identity.get("process_executable") or "")
        if not is_trusted_executable(executable):
            raise ActionEngineError("La interacción UIA solo está permitida en una aplicación trusted por identidad ejecutable.")
        return window_id, identity

    def _uia_focus_control(self, args: dict) -> ExecutionResult:
        window_id, identity = self._uia_interaction_target(args)
        try:
            risk = resolve_control_risk(window_id, str(args.get("control_id", "")), "focus")
            data = focus_control(window_id, str(args.get("control_id", "")))
            data.update({"target": identity, "dynamic_risk": risk["risk_level"], "requires_explicit_confirmation": risk["requires_explicit_confirmation"]})
            return ExecutionResult(True, "uia_focus_control", "Enfoqué el control UIA trusted y verifiqué el target.", data)
        except UIAutomationError as exc:
            raise ActionEngineError(str(exc)) from exc

    def _uia_invoke_control(self, args: dict) -> ExecutionResult:
        window_id, identity = self._uia_interaction_target(args)
        control_id = str(args.get("control_id", ""))
        try:
            risk = resolve_control_risk(window_id, control_id, "invoke")
            declared = int(args.get("_declared_risk", self.SAFE_ACTIONS["uia_invoke_control"][0]))
            if risk["risk_level"] > declared or risk["sensitive"]:
                return ExecutionResult(False, "uia_invoke_control", "La policy UIA rechazó el control por riesgo dinámico; no se invocó ningún efecto.", {"target": identity, "dynamic_risk": risk["risk_level"], "declared_risk": declared, "risk_reason": risk["reason"], "requires_explicit_confirmation": True, "effect_performed": False}, status="DENIED", capability_available=True, execution_attempted=False)
            data = invoke_control(window_id, control_id)
            data["target"] = identity
            return ExecutionResult(True, "uia_invoke_control", "Invocación UIA trusted verificada sin coordenadas.", data)
        except UIAutomationError as exc:
            raise ActionEngineError(str(exc)) from exc

    def _uia_set_value(self, args: dict) -> ExecutionResult:
        window_id, identity = self._uia_interaction_target(args)
        control_id = str(args.get("control_id", ""))
        try:
            risk = resolve_control_risk(window_id, control_id, "set_value")
            declared = int(args.get("_declared_risk", self.SAFE_ACTIONS["uia_set_value"][0]))
            if risk["risk_level"] > declared or risk["sensitive"]:
                return ExecutionResult(False, "uia_set_value", "La policy UIA rechazó el control por riesgo dinámico; no se escribió ningún valor.", {"target": identity, "dynamic_risk": risk["risk_level"], "declared_risk": declared, "risk_reason": risk["reason"], "requires_explicit_confirmation": True, "effect_performed": False}, status="DENIED", capability_available=True, execution_attempted=False)
            data = set_control_value(window_id, control_id, str(args.get("value", "")))
            data["target"] = identity
            return ExecutionResult(True, "uia_set_value", "Valor UIA trusted actualizado y verificado sin exponerlo en el resultado.", data)
        except UIAutomationError as exc:
            raise ActionEngineError(str(exc)) from exc

    def _screen_capture_display(self, args: dict) -> ExecutionResult:
        data = capture_display(str(args.get("display_id", "")), owner_device=str(args.get("_owner_device") or "pc-main"), target_host=str(args.get("_target_host") or "pc-main"), request_id=str(args.get("_request_id") or ""))
        available = bool(data.get("available"))
        data.setdefault("observation_completed", available)
        return ExecutionResult(available, "screen_capture_display", "La captura fue solicitada bajo demanda y quedó en almacenamiento temporal." if available else str(data.get("reason", "Captura no disponible.")), data, status="SUCCESS" if available else "UNAVAILABLE", capability_available=available, observation_completed=available)

    def _screen_capture_window(self, args: dict) -> ExecutionResult:
        window_id = self._context_window_id(args)
        try:
            target = self._optional_expected_window_target(args)
            data = capture_window(window_id, owner_device=str(args.get("_owner_device") or "pc-main"), target_host=str(args.get("_target_host") or "pc-main"), request_id=str(args.get("_request_id") or ""))
            if target:
                data["source_identity"] = target
        except ActionEngineError as exc:
            return ExecutionResult(False, "screen_capture_window", str(exc), {"available": False, "window_id": window_id, "observation_completed": False}, status="DENIED", capability_available=True, execution_attempted=False)
        available = bool(data.get("available"))
        data.setdefault("observation_completed", available)
        return ExecutionResult(available, "screen_capture_window", "La captura fue solicitada bajo demanda y quedó en almacenamiento temporal." if available else str(data.get("reason", "Captura no disponible.")), data, status="SUCCESS" if available else "UNAVAILABLE", capability_available=available, observation_completed=available)

    def _list_audio_devices(self, _args: dict) -> ExecutionResult:
        try:
            rows = audio_devices()
            available = bool(rows)
            return ExecutionResult(available, "list_audio_devices", f"Detecté {len(rows)} endpoint(s) de audio." if available else "No hay un backend de audio disponible.", {"devices": rows, "available": available, "os": platform.system(), "observation_completed": available}, status="SUCCESS" if available else "UNAVAILABLE", capability_available=available, observation_completed=available)
        except PlatformCapabilityError as exc:
            return ExecutionResult(False, "list_audio_devices", str(exc), {"devices": [], "available": False, "os": platform.system(), "observation_completed": False}, status="UNAVAILABLE")

    def _get_volume(self, _args: dict) -> ExecutionResult:
        try:
            data = audio_get()
            return ExecutionResult(True, "get_volume", f"Volumen actual: {data.get('level', 0)}%.", data)
        except PlatformCapabilityError as exc:
            raise ActionEngineError(str(exc)) from exc

    def _set_volume(self, args: dict) -> ExecutionResult:
        try:
            data = audio_set(int(float(args.get("level", 0))))
            verified = audio_get()
            data.update({"observed_level": verified.get("level"), "verified": abs(float(verified.get("level", -1)) - int(float(args.get("level", 0)))) <= 2})
            return ExecutionResult(bool(data["verified"]), "set_volume", f"Volumen ajustado al {int(float(args.get('level', 0)))}%.", data)
        except PlatformCapabilityError as exc:
            raise ActionEngineError(str(exc)) from exc

    def _mute(self, _args: dict) -> ExecutionResult:
        try:
            data = audio_mute(True)
            return ExecutionResult(True, "mute", "Silencié el sistema y confirmé la operación.", data)
        except PlatformCapabilityError as exc:
            raise ActionEngineError(str(exc)) from exc

    def _unmute(self, _args: dict) -> ExecutionResult:
        try:
            data = audio_mute(False)
            return ExecutionResult(True, "unmute", "Quité el silencio del sistema.", data)
        except PlatformCapabilityError as exc:
            raise ActionEngineError(str(exc)) from exc

    def _clipboard_read(self, _args: dict) -> ExecutionResult:
        try:
            data = clipboard_read()
            return ExecutionResult(True, "clipboard_read", "Leí el clipboard sin registrar su contenido.", data)
        except PlatformCapabilityError as exc:
            raise ActionEngineError(str(exc)) from exc

    def _clipboard_write(self, args: dict) -> ExecutionResult:
        try:
            data = clipboard_write(str(args.get("text", "")))
            return ExecutionResult(True, "clipboard_write", "Escribí el clipboard sin registrar su contenido.", data)
        except PlatformCapabilityError as exc:
            raise ActionEngineError(str(exc)) from exc

    def _display_list(self, _args: dict) -> ExecutionResult:
        try:
            rows = display_list()
            return ExecutionResult(True, "display_list", f"Detecté {len(rows)} display(s).", {"displays": rows})
        except PlatformCapabilityError as exc:
            raise ActionEngineError(str(exc)) from exc

    def _display_info(self, args: dict) -> ExecutionResult:
        try:
            data = display_info(str(args.get("display_id", "")))
            return ExecutionResult(True, "display_info", "Metadata de display verificada.", data)
        except PlatformCapabilityError as exc:
            raise ActionEngineError(str(exc)) from exc

    def _network_adapters(self, _args: dict) -> ExecutionResult:
        return ExecutionResult(True, "network_adapters", "Consulté adaptadores en modo read-only.", {"adapters": network_adapters()})

    def _network_ip(self, _args: dict) -> ExecutionResult:
        return ExecutionResult(True, "network_ip", "Consulté las IP locales en modo read-only.", network_ip())

    def _process_info(self, args: dict) -> ExecutionResult:
        try:
            import psutil
            pid = int(str(args.get("pid", "0")))
            proc = psutil.Process(pid)
            info = proc.as_dict(attrs=["pid", "name", "exe", "username", "status", "create_time", "cpu_percent", "memory_percent"])
            return ExecutionResult(True, "process_info", "Información de proceso verificada.", info)
        except (ImportError, ValueError, Exception) as exc:
            raise ActionEngineError(f"No se pudo consultar el proceso: {exc}") from exc

    def _process_stop(self, args: dict) -> ExecutionResult:
        try:
            import psutil
            pid = int(str(args.get("pid", "0")))
            proc = psutil.Process(pid)
            name = str(proc.name()).casefold()
            protected = {"system", "system idle process", "smss.exe", "csrss.exe", "wininit.exe", "services.exe", "lsass.exe", "gaia", "python", "python3"}
            if any(item in name for item in protected):
                raise ActionEngineError("El proceso está protegido por seguridad.")
            requested = float(str(args.get("creation_time", "")))
            if abs(float(proc.create_time()) - requested) > 0.01:
                raise ActionEngineError("La identidad del proceso no coincide.")
            proc.terminate()
            return ExecutionResult(True, "process_stop", f"Detuve el proceso {pid} de forma controlada.", {"pid": pid, "name": name, "verified": True})
        except ActionEngineError:
            raise
        except (ImportError, ValueError, Exception) as exc:
            raise ActionEngineError(f"No se pudo detener el proceso: {exc}") from exc

    def _trusted_repo(self, raw_path: str | None) -> Path:
        path = self._safe_file(raw_path or str(self.project_dir), must_exist=True)
        candidate = path if path.is_dir() else path.parent
        project = self._registered_project_for_path(candidate)
        if not project or not project.trusted:
            raise ActionEngineError("La operación Git requiere un proyecto registrado como trusted.")
        return candidate if (candidate / ".git").exists() else project.path

    def _git_read(self, args: dict, operation: str, action: str, command: list[str]) -> ExecutionResult:
        path = self._trusted_repo(args.get("path"))
        result = self._run(["git", "-C", str(path), *command], timeout=30)
        output = self._output(result)
        if result.returncode != 0:
            raise ActionEngineError(output or "Git rechazó la operación.")
        return ExecutionResult(True, action, output or f"Git {operation} verificado.", {"path": str(path), "output": output, "operation": operation})

    def _git_branch(self, args: dict) -> ExecutionResult:
        return self._git_read(args, "branch", "git_branch", ["branch", "--show-current"])

    def _git_log(self, args: dict) -> ExecutionResult:
        return self._git_read(args, "log", "git_log", ["log", "-5", "--oneline", "--no-decorate"])

    def _git_diff(self, args: dict) -> ExecutionResult:
        return self._git_read(args, "diff", "git_diff", ["diff", "--stat"])

    def _git_add(self, args: dict) -> ExecutionResult:
        path = self._trusted_repo(args.get("path"))
        target = str(args.get("path") or ".")
        result = self._run(["git", "-C", str(path), "add", "--", target], timeout=30)
        if result.returncode != 0:
            raise ActionEngineError(self._output(result) or "Git add falló.")
        return ExecutionResult(True, "git_add", "Preparé el cambio para commit en el proyecto trusted.", {"path": str(path), "target": target, "verified": True})

    def _git_commit(self, args: dict) -> ExecutionResult:
        path = self._trusted_repo(args.get("path"))
        message = str(args.get("message", "")).strip()
        if not message or len(message) > 240:
            raise ActionEngineError("El mensaje de commit es obligatorio y debe ser corto.")
        result = self._run(["git", "-C", str(path), "commit", "-m", message], timeout=60)
        if result.returncode != 0:
            raise ActionEngineError(self._output(result) or "Git commit falló.")
        return ExecutionResult(True, "git_commit", "Creé el commit en el proyecto trusted.", {"path": str(path), "verified": True})

    def _power(self, operation: str, action: str) -> ExecutionResult:
        try:
            data = power_action(operation)
            return ExecutionResult(True, action, f"Operación de energía solicitada: {operation}.", data)
        except PlatformCapabilityError as exc:
            raise ActionEngineError(str(exc)) from exc

    def _system_lock(self, _args: dict) -> ExecutionResult:
        return self._power("lock", "system_lock")

    def _system_sleep(self, _args: dict) -> ExecutionResult:
        return self._power("sleep", "system_sleep")

    def _system_restart(self, _args: dict) -> ExecutionResult:
        return self._power("restart", "system_restart")

    def _system_shutdown(self, _args: dict) -> ExecutionResult:
        return self._power("shutdown", "system_shutdown")

    def _safe_file(self, raw: str, *, must_exist: bool, write: bool = False, right: str | None = None) -> Path:
        candidate = Path(str(raw or "").strip().strip('"'))
        if not candidate.is_absolute():
            candidate = self.project_dir / candidate
        path = candidate.expanduser().resolve()
        if must_exist and not path.exists():
            raise ActionEngineError(f"La ruta no existe: {path}")
        required_right = str(right or ("WRITE" if write else "READ")).strip().upper()
        if not _within(path, self.project_dir):
            allowed = False
            try:
                for project in self.registry.list_projects():
                    if project.trusted and (_within(path, project.path) or _within(path.parent, project.path)):
                        allowed = True
                        break
            except ProjectRegistryError:
                allowed = False
            if not allowed and is_trusted_path(path, write=write, right=required_right):
                allowed = True
            if not allowed:
                raise ActionEngineError(f"La ruta está fuera del scope permitido; concede el derecho {required_right} a la carpeta o proyecto.")
        return path

    def _ensure_allowed_parent(self, path: Path, *, right: str = "WRITE") -> None:
        required_right = str(right or "WRITE").strip().upper()
        if _within(path.parent, self.project_dir) or is_trusted_path(path.parent, write=required_right in {"WRITE", "CREATE", "RENAME", "DELETE", "COPY_TO", "MOVE_TO"}, right=required_right):
            return
        raise ActionEngineError(f"El destino está fuera del scope permitido; concede el derecho {required_right} a la carpeta.")

    def _resolve_project(self, project: str) -> Path:
        requested = _clean(project) or "default"
        if requested == "default" and not self.projects_file.exists():
            return self._safe_path(str(self.default_project), must_exist=True)
        try:
            return self.registry.resolve(requested).path
        except ProjectRegistryError as exc:
            raise ActionEngineError(str(exc)) from exc

    def _load_projects(self) -> dict:
        if not self.projects_file.exists():
            return {}
        try:
            data = json.loads(self.projects_file.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError) as exc:
            raise ActionEngineError(f"No se pudo leer projects.json: {exc}") from exc

    def _safe_path(self, raw: str, *, must_exist: bool) -> Path:
        candidate = Path(str(raw).strip().strip('"'))
        if not candidate.is_absolute():
            candidate = self.project_dir / candidate
        path = candidate.expanduser().resolve()
        if must_exist and not path.exists():
            raise ActionEngineError(f"La ruta no existe: {path}")
        if path.is_file() and not path.name.endswith(".git"):
            raise ActionEngineError(f"La ruta no es una carpeta: {path}")
        return path

    @staticmethod
    def _url(raw: str) -> str:
        value = str(raw).strip()
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ActionEngineError("Solo se permiten URLs http y https válidas.")
        return value

    @staticmethod
    def _open_path(path: Path) -> None:
        system = platform.system()
        if system == "Windows":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif system == "Darwin":
            subprocess.Popen(["open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            opener = shutil.which("xdg-open")
            if not opener:
                raise ActionEngineError("No encuentro xdg-open para abrir la carpeta en Linux.")
            subprocess.Popen([opener, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @staticmethod
    def _spawn(command: list[str], cwd: Path | None = None) -> subprocess.Popen:
        try:
            return subprocess.Popen(command, cwd=str(cwd) if cwd else None, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=False)
        except FileNotFoundError as exc:
            raise ActionEngineError(f"No encuentro el programa requerido: {command[0]}") from exc

    @staticmethod
    def _run(command: list[str], cwd: Path | None = None, timeout: int = 30) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(command, cwd=str(cwd) if cwd else None, capture_output=True, text=True, timeout=timeout, shell=False, check=False)
        except FileNotFoundError as exc:
            raise ActionEngineError(f"No encuentro el programa requerido: {command[0]}") from exc
        except subprocess.TimeoutExpired as exc:
            raise ActionEngineError(f"La acción superó el límite de {timeout} segundos.") from exc

    def _test_command(self, path: Path) -> list[str] | None:
        if (path / "tests" / "smoke_test.py").exists():
            return [os.environ.get("PYTHON", "python"), "-m", "compileall", "-q", "lumen-core", "lumen-pc", "tests"]
        if (path / "pytest.ini").exists() or (path / "pyproject.toml").exists() or (path / "tests").is_dir():
            return [os.environ.get("PYTHON", "python"), "-m", "pytest", "-q"]
        if (path / "package.json").exists():
            return ["npm", "test", "--", "--runInBand"]
        return None

    @staticmethod
    def _memory_stats() -> dict:
        try:
            import psutil  # optional dependency installed with the PC client
            vm = psutil.virtual_memory()
            return {"ram_total_gb": vm.total / 1e9, "ram_used_gb": vm.used / 1e9, "ram_used_percent": float(vm.percent)}
        except ImportError:
            if platform.system() == "Windows":
                return {"ram_total_gb": 0.0, "ram_used_gb": 0.0, "ram_used_percent": 0.0, "ram_available": False}
            meminfo = Path("/proc/meminfo")
            if meminfo.exists():
                values = {}
                for line in meminfo.read_text(errors="ignore").splitlines():
                    key, _, value = line.partition(":")
                    if value.strip().endswith("kB"):
                        values[key] = int(value.strip().split()[0]) * 1024
                total = values.get("MemTotal", 0)
                available = values.get("MemAvailable", values.get("MemFree", 0))
                used = max(0, total - available)
                return {"ram_total_gb": total / 1e9, "ram_used_gb": used / 1e9, "ram_used_percent": used / total * 100 if total else 0.0, "ram_available": bool(total)}
            return {"ram_total_gb": 0.0, "ram_used_gb": 0.0, "ram_used_percent": 0.0, "ram_available": False}

    @staticmethod
    def _cpu_stats() -> dict:
        try:
            import psutil
            return {"cpu_percent": float(psutil.cpu_percent(interval=0.25))}
        except ImportError:
            load = os.getloadavg()[0] if hasattr(os, "getloadavg") else 0.0
            count = os.cpu_count() or 1
            return {"cpu_percent": min(100.0, load / count * 100.0), "cpu_available": hasattr(os, "getloadavg")}

    @staticmethod
    def _number(value: str) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _format_status(self, data: dict) -> str:
        gpu = data.get("gpu_name") or "GPU no disponible"
        return f"RAM {data.get('ram_used_percent', 0):.1f}% | CPU {data.get('cpu_percent', 0):.1f}% | Disco {data.get('disk_used_percent', 0):.1f}% | {gpu}."

    def _remember_process(self, process: subprocess.Popen, project: str, command: list[str]) -> None:
        records = self._load_processes()
        records = [item for item in records if int(item.get("pid", 0)) != process.pid]
        creation_time = 0.0
        executable = str(command[0]) if command else ""
        try:
            import psutil
            tracked = psutil.Process(process.pid)
            creation_time = float(tracked.create_time())
            executable = tracked.exe() or executable
        except ImportError:
            pass
        except Exception:
            pass
        records.append({"pid": process.pid, "creation_time": creation_time, "executable": executable, "command": command, "project": project, "started_at": time.time()})
        self._save_processes(records)

    def _load_processes(self) -> list[dict]:
        try:
            data = json.loads(self.process_registry_file.read_text(encoding="utf-8")) if self.process_registry_file.exists() else []
            return data if isinstance(data, list) else []
        except (OSError, ValueError):
            return []

    def _save_processes(self, records: list[dict]) -> None:
        self.process_registry_file.write_text(json.dumps(records[-50:], ensure_ascii=False, indent=2), encoding="utf-8")

    def _registered_project_for_path(self, path: Path):
        try:
            for project in self.registry.list_projects():
                if path == project.path or _within(path, project.path):
                    return project
        except ProjectRegistryError as exc:
            raise ActionEngineError(str(exc)) from exc
        return None

    def _output(self, result: subprocess.CompletedProcess[str]) -> str:
        output = ((result.stdout or "") + ("\n" + result.stderr if result.stderr else "")).strip()
        return output[-self.max_output_chars:] if output else "(sin salida)"


def _within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _clean(value: str) -> str:
    return " ".join(str(value).strip().split())
