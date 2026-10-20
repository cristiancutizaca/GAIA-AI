"""Registry code-owned de capabilities PC para GAIA.

El LLM puede proponer una capability conocida y parámetros que pasan este
validador; nunca puede registrar capabilities, executors, comandos o paths.
La ejecución real continúa en ``ActionEngine`` mediante acciones allowlisted.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class CapabilityDefinition:
    name: str
    category: str
    description: str
    risk_level: int
    required_permissions: tuple[str, ...]
    supported_os: tuple[str, ...]
    executor: str
    parameter_schema: tuple[str, ...]
    confirmation_policy: str
    reversible: bool
    timeout: float
    implemented: bool = False

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class CapabilityRequest:
    capability: str
    params: Mapping[str, object]
    device: str = "pc-main"
    resource_scope: str = ""

    def as_dict(self) -> dict:
        return {
            "capability": self.capability,
            "params": dict(self.params),
            "device": self.device,
            "resource_scope": self.resource_scope,
        }


@dataclass(frozen=True)
class VerifiedCapabilityResult:
    capability: str
    success: bool
    message: str
    data: Mapping[str, object]
    execution_verified: bool = True
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
            object.__setattr__(self, "execution_verified", False)
            object.__setattr__(self, "capability_available", False)
            object.__setattr__(self, "effect_verified", False)
            object.__setattr__(self, "side_effect_performed", False)
        else:
            object.__setattr__(self, "capability_available", True if available is None else bool(available))
            if status != "SUCCESS":
                object.__setattr__(self, "execution_verified", False)
                object.__setattr__(self, "effect_verified", False)
                object.__setattr__(self, "side_effect_performed", False)
        if status == "SUCCESS" and not self.observation_completed and data.get("observation_completed"):
            object.__setattr__(self, "observation_completed", True)
        if status == "SUCCESS" and self.success and not self.execution_verified and not self.observation_completed and not data.get("dry_run"):
            object.__setattr__(self, "side_effect_performed", True)
            object.__setattr__(self, "effect_verified", bool(data.get("verified", True)))
            object.__setattr__(self, "execution_verified", bool(self.effect_verified))
        object.__setattr__(self, "status", status)

    def as_dict(self) -> dict:
        return {
            "capability": self.capability,
            "success": bool(self.success),
            "message": self.message,
            "data": dict(self.data),
            "status": self.status,
            "request_validated": bool(self.request_validated),
            "execution_attempted": bool(self.execution_attempted),
            "capability_available": self.capability_available,
            "side_effect_performed": bool(self.side_effect_performed),
            "effect_verified": bool(self.effect_verified),
            "observation_completed": bool(self.observation_completed),
            "execution_verified": bool(self.execution_verified),
        }


class CapabilityValidationError(ValueError):
    """La request no cumple el registry code-owned."""


class CapabilityRegistry:
    """Registry inmutable después de construirlo; no expone register dinámico."""

    def __init__(self, definitions: Mapping[str, CapabilityDefinition]) -> None:
        normalized: dict[str, CapabilityDefinition] = {}
        for key, definition in definitions.items():
            canonical = str(key).strip().casefold()
            if not canonical or definition.name.casefold() != canonical:
                raise CapabilityValidationError("El nombre de capability no es canónico.")
            if definition.risk_level not in range(5):
                raise CapabilityValidationError(f"Risk level inválido para {definition.name}.")
            if definition.timeout <= 0:
                raise CapabilityValidationError(f"Timeout inválido para {definition.name}.")
            normalized[canonical] = definition
        self._definitions = MappingProxyType(normalized)

    def get(self, name: str) -> CapabilityDefinition | None:
        return self._definitions.get(str(name).strip().casefold())

    def all(self) -> tuple[CapabilityDefinition, ...]:
        return tuple(self._definitions.values())

    def request(
        self,
        name: str,
        params: Mapping[str, object] | None = None,
        *,
        device: str = "pc-main",
        resource_scope: str = "",
    ) -> CapabilityRequest:
        definition = self.get(name)
        if definition is None:
            raise CapabilityValidationError("Capability no registrada.")
        if not definition.implemented:
            raise CapabilityValidationError("Capability registrada pero aún no implementada.")
        clean_params = dict(params or {})
        allowed = {field[:-1] if field.endswith("!") else field for field in definition.parameter_schema}
        unknown = sorted(set(clean_params) - allowed)
        if unknown:
            raise CapabilityValidationError("Parámetros no permitidos: " + ", ".join(unknown))
        missing = [field[:-1] for field in definition.parameter_schema if field.endswith("!") and field[:-1] not in clean_params]
        if missing:
            raise CapabilityValidationError("Faltan parámetros requeridos: " + ", ".join(missing))
        if definition.name in {"apps.open", "apps.close", "apps.focus", "apps.minimize", "apps.is_running"} and str(clean_params.get("app", "")).casefold() not in {"calculator", "notepad", "spotify", "vscode"}:
            raise CapabilityValidationError("La aplicación no pertenece al Safe App Registry.")
        if definition.name == "apps.open_discovered":
            app_id = str(clean_params.get("app_id", "")).strip()
            if not app_id.startswith("discovered:") or any(char in app_id for char in "\\\x00;|&"):
                raise CapabilityValidationError("app_id descubierto inválido o no canónico.")
        if definition.name == "windows.move_to_display" and not str(clean_params.get("display_id", "")).strip():
            raise CapabilityValidationError("display_id es obligatorio.")
        if definition.name == "url.open" and not str(clean_params.get("url", "")).lower().startswith(("http://", "https://")):
            raise CapabilityValidationError("La URL debe usar http o https.")
        if definition.name == "audio.set_volume":
            try:
                if not 0 <= int(float(clean_params.get("level", -1))) <= 100:
                    raise CapabilityValidationError("El volumen debe estar entre 0 y 100.")
            except (TypeError, ValueError) as exc:
                raise CapabilityValidationError("El volumen debe ser numérico.") from exc
        if definition.name.startswith("windows.") and not str(clean_params.get("window_id", "")).strip().isdigit():
            raise CapabilityValidationError("window_id debe ser un identificador numérico.")
        if definition.name in {"uia.inspect_window", "uia.list_controls", "uia.get_focused_control", "screen.capture_window"} and str(clean_params.get("window_id", "")).strip() and (not str(clean_params.get("window_id", "")).strip().isdigit() or int(str(clean_params.get("window_id", "0")).strip()) <= 0):
            raise CapabilityValidationError("window_id UIA debe ser numérico y positivo.")
        if definition.name in {"uia.inspect_window", "uia.list_controls", "uia.get_focused_control", "screen.capture_window"} and "expected_target" in clean_params and (not isinstance(clean_params.get("expected_target"), dict) or not clean_params.get("expected_target")):
            raise CapabilityValidationError("expected_target debe ser un snapshot estructurado cuando se proporciona.")
        if definition.name == "screen.capture_display" and not str(clean_params.get("display_id", "")).strip():
            raise CapabilityValidationError("display_id es obligatorio para captura.")
        if definition.name in {"uia.focus_control", "uia.invoke_control", "uia.set_value"}:
            control_id = str(clean_params.get("control_id", "")).strip()
            expected_target = clean_params.get("expected_target")
            if not control_id.startswith("uia:") or len(control_id) > 100:
                raise CapabilityValidationError("control_id UIA no es canónico.")
            if not isinstance(expected_target, dict) or not expected_target:
                raise CapabilityValidationError("expected_target es obligatorio para stale-target protection.")
            if definition.name == "uia.set_value":
                value = str(clean_params.get("value", ""))
                if len(value) > 4000 or "\x00" in value or any(token in value.casefold() for token in ("password", "passwd", "token", "secret", "credential", "contraseña")):
                    raise CapabilityValidationError("El valor UIA no puede contener datos sensibles ni superar el límite.")
        if definition.name.startswith(("uia.",)):
            try:
                max_controls = int(clean_params.get("max_controls", 100))
            except (TypeError, ValueError) as exc:
                raise CapabilityValidationError("max_controls debe ser entero.") from exc
            if not 1 <= max_controls <= 200:
                raise CapabilityValidationError("max_controls debe estar entre 1 y 200.")
        if definition.name == "files.rename" and any(char in str(clean_params.get("name", "")) for char in ("/", "\\", "\x00")):
            raise CapabilityValidationError("El nuevo nombre debe ser local al directorio.")
        return CapabilityRequest(definition.name, MappingProxyType(clean_params), device=device, resource_scope=resource_scope)

    def request_for_action(
        self,
        action_name: str,
        args: Mapping[str, object] | None = None,
        *,
        device: str = "pc-main",
        resource_scope: str = "",
    ) -> CapabilityRequest:
        mapping = ACTION_TO_CAPABILITY.get(str(action_name).strip())
        if not mapping:
            raise CapabilityValidationError("La acción no tiene capability registrada.")
        capability, defaults = mapping
        merged = dict(defaults)
        merged.update(dict(args or {}))
        return self.request(capability, merged, device=device, resource_scope=resource_scope)


# Adaptadores actuales. El nombre legacy de ActionEngine no otorga permisos extra.
ACTION_TO_CAPABILITY: dict[str, tuple[str, dict[str, object]]] = {
    "list_safe_apps": ("apps.list", {}),
    "is_safe_app_running": ("apps.is_running", {"app": ""}),
    "close_app": ("apps.close", {"app": ""}),
    "focus_app": ("apps.focus", {"app": ""}),
    "minimize_app": ("apps.minimize", {"app": ""}),
    "open_calculator": ("apps.open", {"app": "calculator"}),
    "open_notepad": ("apps.open", {"app": "notepad"}),
    "open_spotify": ("apps.open", {"app": "spotify"}),
    "open_vscode": ("apps.open", {"app": "vscode"}),
    "open_vscode_new_window": ("apps.open", {"app": "vscode", "new_window": True}),
    "open_discovered_app": ("apps.open_discovered", {"app_id": ""}),
    "open_browser": ("browser.open", {}),
    "open_url": ("url.open", {"url": ""}),
    "open_folder": ("folders.open", {"path": ""}),
    "open_project": ("projects.open", {"project": ""}),
    "system_status": ("system.status", {}),
    "system_ram": ("system.status", {"metric": "ram"}),
    "system_cpu": ("system.status", {"metric": "cpu"}),
    "system_gpu": ("system.status", {"metric": "gpu"}),
    "system_disk": ("system.status", {"metric": "disk"}),
    "system_processes": ("processes.list", {}),
    "process_info": ("processes.info", {"pid": ""}),
    "process_stop": ("processes.stop", {"pid": "", "creation_time": "", "executable": "", "command": []}),
    "system_network": ("network.status", {}),
    "network_adapters": ("network.adapters", {}),
    "network_ip": ("network.ip", {}),
    "git_status": ("git.status", {"path": ""}),
    "list_projects": ("projects.list", {}),
    "show_project": ("projects.info", {"project": ""}),
    "run_tests": ("projects.tests", {"path": ""}),
    "start_project": ("projects.start", {"project": ""}),
    "run_project_command": ("projects.command", {"project": "", "command": ""}),
    "open_terminal": ("projects.terminal", {"project": "default"}),
    "file_exists": ("files.exists", {"path": ""}),
    "file_list": ("files.list", {"path": ""}),
    "file_info": ("files.info", {"path": ""}),
    "file_open": ("files.open", {"path": ""}),
    "file_delete": ("files.delete", {"path": ""}),
    "file_copy": ("files.copy", {"source": "", "destination": ""}),
    "file_move": ("files.move", {"source": "", "destination": ""}),
    "file_rename": ("files.rename", {"path": "", "name": ""}),
    "folder_create": ("folders.create", {"path": ""}),
    "windows_list": ("windows.list", {}),
    "windows_focus": ("windows.focus", {"window_id": ""}),
    "windows_minimize": ("windows.minimize", {"window_id": ""}),
    "windows_maximize": ("windows.maximize", {"window_id": ""}),
    "windows_restore": ("windows.restore", {"window_id": ""}),
    "windows_close": ("windows.close", {"window_id": ""}),
    "windows_move_to_display": ("windows.move_to_display", {"window_id": "", "display_id": ""}),
    "desktop_context": ("desktop.context", {"force_refresh": False}),
    "uia_inspect_window": ("uia.inspect_window", {"window_id": "", "max_controls": 100, "expected_target": {}}),
    "uia_list_controls": ("uia.list_controls", {"window_id": "", "max_controls": 100, "expected_target": {}}),
    "uia_get_focused_control": ("uia.get_focused_control", {"window_id": "", "max_controls": 200, "expected_target": {}}),
    "uia_focus_control": ("uia.focus_control", {"window_id": "", "control_id": "", "expected_target": {}}),
    "uia_invoke_control": ("uia.invoke_control", {"window_id": "", "control_id": "", "expected_target": {}}),
    "uia_set_value": ("uia.set_value", {"window_id": "", "control_id": "", "value": "", "expected_target": {}}),
    "vscode_focus": ("vscode.focus", {}),
    "vscode_open_project": ("vscode.open_project", {"project": ""}),
    "vscode_new_window": ("vscode.new_window", {}),
    "vscode_open_file_trusted": ("vscode.open_file_trusted", {"path": ""}),
    "vscode_open_terminal_trusted": ("vscode.open_terminal_trusted", {"project": "default"}),
    "media_status": ("media.status", {}),
    "media_play_pause": ("media.play_pause", {}),
    "media_next": ("media.next", {}),
    "media_previous": ("media.previous", {}),
    "media_stop": ("media.stop", {}),
    "screen_capture_display": ("screen.capture_display", {"display_id": ""}),
    "screen_capture_window": ("screen.capture_window", {"window_id": "", "expected_target": {}}),
    "list_audio_devices": ("audio.list_devices", {}),
    "get_volume": ("audio.get_volume", {}),
    "set_volume": ("audio.set_volume", {"level": ""}),
    "mute": ("audio.mute", {}),
    "unmute": ("audio.unmute", {}),
    "clipboard_read": ("clipboard.read", {}),
    "clipboard_write": ("clipboard.write", {"text": ""}),
    "display_list": ("display.list", {}),
    "display_info": ("display.info", {"display_id": ""}),
    "git_branch": ("git.branch", {"path": ""}),
    "git_log": ("git.log", {"path": ""}),
    "git_diff": ("git.diff", {"path": ""}),
    "git_add": ("git.add", {"path": ""}),
    "git_commit": ("git.commit", {"message": ""}),
    "system_lock": ("system.lock", {}),
    "system_sleep": ("system.sleep", {}),
    "system_restart": ("system.restart", {}),
    "system_shutdown": ("system.shutdown", {}),
}


def _definition(name: str, category: str, description: str, risk: int, executor: str, params: tuple[str, ...] = (), *, implemented: bool = False, confirmation: str = "AUTO", reversible: bool = True, timeout: float = 30.0) -> CapabilityDefinition:
    return CapabilityDefinition(
        name=name,
        category=category,
        description=description,
        risk_level=risk,
        required_permissions=("actions_execute",),
        supported_os=("windows", "linux", "darwin"),
        executor=executor,
        parameter_schema=params,
        confirmation_policy=confirmation,
        reversible=reversible,
        timeout=timeout,
        implemented=implemented,
    )


def default_capability_registry() -> CapabilityRegistry:
    definitions = {
        "apps.list": _definition("apps.list", "apps", "Lista aplicaciones conocidas; discovery no autoriza ejecución.", 0, "ActionEngine._list_safe_apps", implemented=True),
        "apps.open": _definition("apps.open", "apps", "Abre una app del Safe App Registry 2.0.", 1, "ActionEngine._open_registered_app", ("app", "new_window"), implemented=True),
        "apps.open_discovered": _definition("apps.open_discovered", "apps", "Abre una aplicación descubierta solo después de trust explícito.", 1, "ActionEngine._open_discovered_app", ("app_id!",), implemented=True, confirmation="ASK_ONCE"),
        "apps.close": _definition("apps.close", "apps", "Cierra una aplicación normal con policy explícita.", 2, "ActionEngine._close_app", ("app!",), implemented=True, confirmation="ASK_ONCE"),
        "apps.focus": _definition("apps.focus", "apps", "Enfoca una aplicación registrada.", 1, "ActionEngine._focus_app", ("app!",), implemented=True),
        "apps.minimize": _definition("apps.minimize", "apps", "Minimiza una aplicación registrada mediante ventanas estructuradas.", 1, "ActionEngine._minimize_app", ("app!",), implemented=True),
        "apps.is_running": _definition("apps.is_running", "apps", "Consulta si una app registrada está ejecutándose.", 0, "ActionEngine._is_safe_app_running", ("app!",), implemented=True),
        "browser.open": _definition("browser.open", "browser", "Abre el navegador predeterminado.", 1, "ActionEngine._open_browser", implemented=True),
        "url.open": _definition("url.open", "browser", "Abre una URL validada con esquema HTTP(S).", 1, "ActionEngine._open_url", ("url!",), implemented=True),
        "folders.open": _definition("folders.open", "folders", "Abre una carpeta validada.", 1, "ActionEngine._open_folder", ("path!",), implemented=True),
        "projects.open": _definition("projects.open", "projects", "Abre un proyecto registrado/validado.", 1, "ActionEngine._open_project", ("project!",), implemented=True),
        "system.status": _definition("system.status", "system", "Obtiene métricas locales sin LLM.", 0, "ActionEngine._system_status", ("metric",), implemented=True),
        "processes.list": _definition("processes.list", "processes", "Lista procesos en modo read-only.", 0, "ActionEngine._system_processes", implemented=True),
        "network.status": _definition("network.status", "network", "Consulta estado básico de red sin cambiar configuración.", 0, "ActionEngine._system_network", implemented=True),
        "git.status": _definition("git.status", "git", "Consulta el estado de un proyecto Git trusted.", 0, "ActionEngine._git_status", ("path",), implemented=True),
        "projects.list": _definition("projects.list", "projects", "Lista proyectos registrados sin duplicados.", 0, "ActionEngine._list_projects", implemented=True),
        "projects.info": _definition("projects.info", "projects", "Obtiene datos de un proyecto registrado.", 0, "ActionEngine._show_project", ("project!",), implemented=True),
        "projects.tests": _definition("projects.tests", "projects", "Ejecuta únicamente tests registrados en un proyecto trusted.", 2, "ActionEngine._run_tests", ("path",), implemented=True, confirmation="ASK_ONCE", timeout=600.0),
        "projects.start": _definition("projects.start", "projects", "Inicia un proyecto trusted con comando registrado.", 2, "ActionEngine._start_project", ("project!",), implemented=True, confirmation="ASK_ONCE", timeout=60.0),
        "projects.command": _definition("projects.command", "projects", "Ejecuta solo un comando registrado de proyecto trusted.", 2, "ActionEngine._run_project_command", ("project!", "command!"), implemented=True, confirmation="ASK_ONCE", timeout=600.0),
        "projects.terminal": _definition("projects.terminal", "projects", "Abre terminal únicamente en un proyecto trusted.", 1, "ActionEngine._open_terminal", ("project",), implemented=True),
        "files.exists": _definition("files.exists", "files", "Comprueba existencia de una ruta validada.", 0, "ActionEngine._file_exists", ("path!",), implemented=True),
        "files.list": _definition("files.list", "files", "Lista una carpeta dentro de un scope permitido.", 0, "ActionEngine._list_files", ("path",), implemented=True),
        "files.info": _definition("files.info", "files", "Obtiene metadata de una ruta validada.", 0, "ActionEngine._file_info", ("path!",), implemented=True),
        "files.open": _definition("files.open", "files", "Abre un archivo mediante asociación segura.", 1, "ActionEngine._open_file", ("path!",), implemented=True),
        "files.delete": _definition("files.delete", "files", "Envía una ruta a papelera con confirmación obligatoria.", 3, "ActionEngine._delete_file", ("path!",), implemented=True, confirmation="ALWAYS_CONFIRM", reversible=True),
        "files.copy": _definition("files.copy", "files", "Copia con scopes de ruta validados.", 2, "ActionEngine._copy_file", ("source!", "destination!"), implemented=True, confirmation="ASK_ONCE"),
        "files.move": _definition("files.move", "files", "Mueve con scopes de ruta validados.", 2, "ActionEngine._move_file", ("source!", "destination!"), implemented=True, confirmation="ASK_ONCE"),
        "files.rename": _definition("files.rename", "files", "Renombra dentro de un directorio validado.", 2, "ActionEngine._rename_file", ("path!", "name!"), implemented=True, confirmation="ASK_ONCE"),
        "folders.create": _definition("folders.create", "folders", "Crea una carpeta dentro de un scope validado.", 2, "ActionEngine._create_folder", ("path!",), implemented=True, confirmation="ASK_ONCE"),
        "windows.list": _definition("windows.list", "windows", "Lista ventanas visibles mediante API estructurada.", 0, "ActionEngine._windows_list", implemented=True),
        "windows.focus": _definition("windows.focus", "windows", "Enfoca una ventana identificada, sin coordenadas.", 1, "ActionEngine._windows_focus", ("window_id!",), implemented=True),
        "windows.minimize": _definition("windows.minimize", "windows", "Minimiza una ventana identificada.", 1, "ActionEngine._windows_minimize", ("window_id!",), implemented=True),
        "windows.maximize": _definition("windows.maximize", "windows", "Maximiza una ventana identificada.", 1, "ActionEngine._windows_maximize", ("window_id!",), implemented=True),
        "windows.restore": _definition("windows.restore", "windows", "Restaura una ventana identificada.", 1, "ActionEngine._windows_restore", ("window_id!",), implemented=True),
        "windows.close": _definition("windows.close", "windows", "Cierra una ventana identificada con policy.", 2, "ActionEngine._windows_close", ("window_id!",), implemented=True, confirmation="ASK_ONCE"),
        "windows.move_to_display": _definition("windows.move_to_display", "windows", "Mueve una ventana a un monitor enumerado mediante SetWindowPos.", 1, "ActionEngine._windows_move_to_display", ("window_id!", "display_id!"), implemented=True),
        "desktop.context": _definition("desktop.context", "desktop", "Consulta el contexto activo estructurado sin screenshots.", 0, "ActionEngine._desktop_context", ("force_refresh",), implemented=True),
        "uia.inspect_window": _definition("uia.inspect_window", "uia", "Inspecciona controles UIA de una ventana seleccionada en read-only.", 0, "ActionEngine._uia_inspect_window", ("window_id!", "max_controls", "expected_target"), implemented=True),
        "uia.list_controls": _definition("uia.list_controls", "uia", "Lista controles UIA normalizados sin exponer valores sensibles.", 0, "ActionEngine._uia_list_controls", ("window_id!", "max_controls", "expected_target"), implemented=True),
        "uia.get_focused_control": _definition("uia.get_focused_control", "uia", "Obtiene el control UIA enfocado de una ventana seleccionada.", 0, "ActionEngine._uia_get_focused_control", ("window_id", "max_controls", "expected_target"), implemented=True),
        "uia.focus_control": _definition("uia.focus_control", "uia", "Enfoca un control UIA único de una app trusted.", 1, "ActionEngine._uia_focus_control", ("window_id!", "control_id!", "expected_target!"), implemented=True, confirmation="ASK_ONCE"),
        "uia.invoke_control": _definition("uia.invoke_control", "uia", "Invoca un control UIA único y no sensible de una app trusted.", 2, "ActionEngine._uia_invoke_control", ("window_id!", "control_id!", "expected_target!"), implemented=True, confirmation="ASK_ONCE"),
        "uia.set_value": _definition("uia.set_value", "uia", "Escribe un valor acotado en un control UIA no sensible.", 2, "ActionEngine._uia_set_value", ("window_id!", "control_id!", "value!", "expected_target!"), implemented=True, confirmation="ASK_ONCE"),
        "vscode.focus": _definition("vscode.focus", "vscode", "Enfoca VS Code mediante el adapter code-owned.", 1, "ActionEngine._vscode_focus", implemented=True),
        "vscode.open_project": _definition("vscode.open_project", "vscode", "Abre un proyecto registrado en VS Code.", 1, "ActionEngine._vscode_open_project", ("project!",), implemented=True, confirmation="ASK_ONCE"),
        "vscode.new_window": _definition("vscode.new_window", "vscode", "Abre una nueva ventana de VS Code.", 1, "ActionEngine._vscode_new_window", implemented=True),
        "vscode.open_file_trusted": _definition("vscode.open_file_trusted", "vscode", "Abre un archivo dentro de un scope trusted en VS Code.", 1, "ActionEngine._vscode_open_file_trusted", ("path!",), implemented=True, confirmation="ASK_ONCE"),
        "vscode.open_terminal_trusted": _definition("vscode.open_terminal_trusted", "vscode", "Abre terminal solo en un proyecto trusted registrado.", 1, "ActionEngine._vscode_open_terminal_trusted", ("project",), implemented=True, confirmation="ASK_ONCE"),
        "media.status": _definition("media.status", "media", "Consulta la sesión multimedia activa mediante SMTC del sistema operativo.", 0, "ActionEngine._media_status", implemented=True),
        "media.play_pause": _definition("media.play_pause", "media", "Alterna reproducción/pausa mediante SMTC, sin credenciales de proveedor.", 1, "ActionEngine._media_play_pause", implemented=True),
        "media.next": _definition("media.next", "media", "Avanza la sesión multimedia mediante SMTC.", 1, "ActionEngine._media_next", implemented=True),
        "media.previous": _definition("media.previous", "media", "Retrocede la sesión multimedia mediante SMTC.", 1, "ActionEngine._media_previous", implemented=True),
        "media.stop": _definition("media.stop", "media", "Detiene la sesión multimedia mediante SMTC.", 1, "ActionEngine._media_stop", implemented=True),
        "screen.capture_display": _definition("screen.capture_display", "screen", "Captura un monitor únicamente bajo demanda y con cleanup.", 1, "ActionEngine._screen_capture_display", ("display_id!",), implemented=True, confirmation="ASK_ONCE"),
        "screen.capture_window": _definition("screen.capture_window", "screen", "Captura una ventana únicamente bajo demanda y con cleanup.", 1, "ActionEngine._screen_capture_window", ("window_id!", "expected_target"), implemented=True, confirmation="ASK_ONCE"),
        "audio.list_devices": _definition("audio.list_devices", "audio", "Enumera endpoints de audio sin cambiar configuración.", 0, "ActionEngine._list_audio_devices", implemented=True),
        "audio.get_volume": _definition("audio.get_volume", "audio", "Consulta el volumen del sistema.", 0, "ActionEngine._get_volume", implemented=True),
        "audio.set_volume": _definition("audio.set_volume", "audio", "Cambia el volumen del sistema.", 1, "ActionEngine._set_volume", ("level!",), implemented=True),
        "audio.mute": _definition("audio.mute", "audio", "Silencia el sistema.", 1, "ActionEngine._mute", implemented=True),
        "audio.unmute": _definition("audio.unmute", "audio", "Restaura el silencio del sistema.", 1, "ActionEngine._unmute", implemented=True),
        "display.list": _definition("display.list", "display", "Lista monitores disponibles.", 0, "ActionEngine._display_list", implemented=True),
        "display.info": _definition("display.info", "display", "Obtiene metadata de un monitor.", 0, "DisplayHost.info", ("display_id!",), implemented=True),
        "clipboard.read": _definition("clipboard.read", "clipboard", "Lee clipboard solo bajo policy local; no loggea contenido.", 1, "ActionEngine._clipboard_read", implemented=True),
        "clipboard.write": _definition("clipboard.write", "clipboard", "Escribe clipboard bajo policy local.", 1, "ActionEngine._clipboard_write", ("text!",), implemented=True),
        "network.adapters": _definition("network.adapters", "network", "Lista adaptadores de red en read-only.", 0, "ActionEngine._network_adapters", implemented=True),
        "network.ip": _definition("network.ip", "network", "Consulta direcciones IP locales en read-only.", 0, "ActionEngine._network_ip", implemented=True),
        "git.branch": _definition("git.branch", "git", "Consulta rama Git de un proyecto trusted.", 0, "ActionEngine._git_branch", ("path",), implemented=True),
        "git.log": _definition("git.log", "git", "Consulta resumen de log Git.", 0, "ActionEngine._git_log", ("path",), implemented=True),
        "git.diff": _definition("git.diff", "git", "Consulta resumen de diff Git.", 0, "ActionEngine._git_diff", ("path",), implemented=True),
        "git.add": _definition("git.add", "git", "Prepara archivos para commit con policy.", 2, "ActionEngine._git_add", ("path!",), implemented=True, confirmation="ASK_ONCE"),
        "git.commit": _definition("git.commit", "git", "Crea un commit con policy configurable.", 2, "ActionEngine._git_commit", ("message!",), implemented=True, confirmation="ASK_ONCE"),
        "system.lock": _definition("system.lock", "power", "Bloquea la sesión de usuario.", 3, "ActionEngine._system_lock", implemented=True, confirmation="ALWAYS_CONFIRM"),
        "system.sleep": _definition("system.sleep", "power", "Suspende el sistema.", 3, "ActionEngine._system_sleep", implemented=True, confirmation="ALWAYS_CONFIRM"),
        "system.restart": _definition("system.restart", "power", "Reinicia el sistema.", 4, "ActionEngine._system_restart", implemented=True, confirmation="ALWAYS_CONFIRM", reversible=False),
        "system.shutdown": _definition("system.shutdown", "power", "Apaga el sistema; requiere confirmación explícita.", 4, "ActionEngine._system_shutdown", implemented=True, confirmation="ALWAYS_CONFIRM", reversible=False),
    }
    return CapabilityRegistry(definitions)


DEFAULT_CAPABILITY_REGISTRY = default_capability_registry()
