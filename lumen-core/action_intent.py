from __future__ import annotations

"""Deterministic, allowlisted intent recognition for GAIA's first Action Engine.

The LLM is deliberately not allowed to emit shell commands. This module only
maps a small set of Spanish phrases to named actions and validated parameters.
The PC client performs the actual local execution after receiving the intent.
"""

from dataclasses import asdict, dataclass
import json
import re
from urllib.parse import urlparse
from typing import Any


@dataclass(frozen=True)
class ActionIntent:
    name: str
    args: dict[str, str]
    risk_level: int
    confirmation_required: bool = False
    confidence: float = 0.96
    source: str = "deterministic"

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ActionPlan:
    actions: tuple[ActionIntent, ...]
    confirmation_required: bool = False
    confidence: float = 0.96
    source: str = "structured"

    @property
    def risk_level(self) -> int:
        return max((item.risk_level for item in self.actions), default=0)

    def as_dict(self) -> dict:
        return {"type": "plan", "actions": [item.as_dict() for item in self.actions], "risk_level": self.risk_level, "confirmation_required": self.confirmation_required, "confidence": self.confidence, "source": self.source}


_OPEN_VERBS = r"(?:abre|abrir|inicia|iniciar|lanza|lanzar|ejecuta|ejecutar)"
_SHOW_VERBS = r"(?:dime|muestra|muéstrame|consulta|revisa|revisar|ver|mira)"


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip(" \t\n.,;:!?\"'"))


def _valid_url(value: str) -> str | None:
    candidate = _clean(value)
    parsed = urlparse(candidate)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return candidate
    return None


def _normalize_request_frame(text: str) -> str:
    normalized = _clean(text).lower()
    normalized = re.sub(r"^(?:gaia|g\.a\.i\.a)[,;:\s]+", "", normalized).strip()
    normalized = re.sub(r"^(?:¿?puedes|¿?podrías|¿?podrias|can you|could you|would you)\s+", "", normalized).strip()
    normalized = re.sub(r"^(?:quiero|necesito)\s+que\s+", "", normalized).strip()
    normalized = re.sub(r"^(?:te\s+encargo\s+(?:que\s+)?|cuando\s+puedas,?\s+|si\s+tienes\s+un\s+momento,?\s+|en\s+cuanto\s+puedas,?\s+|no\s+te\s+olvides\s+de\s+)", "", normalized).strip()
    normalized = re.sub(r"^(?:quiero|necesito)\s+(.+?)\s+abiert[oa]$", r"abrir \1", normalized).strip()
    verb_map = {"abres": "abrir", "abras": "abrir", "inicias": "iniciar", "inicies": "iniciar", "iniciarías": "iniciar", "iniciarias": "iniciar", "cierras": "cerrar", "cierres": "cerrar", "ejecutas": "ejecutar", "ejecutes": "ejecutar", "eliminas": "eliminar", "elimines": "eliminar", "mueves": "mover", "muevas": "mover", "copias": "copiar", "copies": "copiar", "guardas": "guardar", "guardes": "guardar", "descargas": "descargar", "descargues": "descargar", "envías": "enviar", "envias": "enviar", "envíes": "enviar", "envies": "enviar", "modificas": "modificar", "modifiques": "modificar", "instalas": "instalar", "instales": "instalar", "reinicias": "reiniciar", "reinicies": "reiniciar", "apagas": "apagar", "apagues": "apagar"}
    verb_match = re.match(r"^(?:me\s+)?(" + "|".join(map(re.escape, verb_map)) + r")\s+", normalized)
    if verb_match:
        normalized = verb_map[verb_match.group(1)] + " " + normalized[verb_match.end():]
    normalized = re.sub(r"^(?:por favor,?|hazme el favor de|serías tan amable de|serias tan amable de)\s+", "", normalized).strip()
    normalized = re.sub(r"^(?:me puedes|me podrías|me podrias)\s+", "", normalized).strip()
    normalized = normalized.strip("¿?!.,;: ")
    return normalized


def detect_action(text: str) -> ActionIntent | None:
    """Return an allowlisted action only when the phrase is unambiguous."""
    normalized = _normalize_request_frame(text)
    if not normalized:
        return None

    if re.search(rf"(?:{_OPEN_VERBS})\s+(?:una\s+)?(?:nueva\s+ventana\s+de\s+)?(?:visual studio code|vs\s*code|vscode|code)\s+(?:en\s+)?(?:otra\s+ventana|nueva\s+ventana)$", normalized) or re.search(r"(?:nueva\s+ventana\s+de\s+vs\s*code|abre\s+otro\s+vs\s*code|abre\s+una\s+ventana\s+nueva\s+del\s+editor)", normalized):
        return ActionIntent("open_vscode_new_window", {"app": "vscode"}, 1)
    if re.search(rf"(?:{_OPEN_VERBS})\s+(?:visual studio code|vs\s*code|vscode|code)", normalized):
        return ActionIntent("open_vscode", {"app": "vscode"}, 1)

    if re.search(rf"(?:{_OPEN_VERBS})\s+(?:la\s+)?(?:calculadora|calculator)$", normalized):
        return ActionIntent("open_calculator", {"app": "calculator"}, 1)
    if re.search(rf"(?:{_OPEN_VERBS})\s+(?:el\s+)?(?:bloc\s+de\s+notas|notepad)$", normalized):
        return ActionIntent("open_notepad", {"app": "notepad"}, 1)
    if re.search(rf"(?:{_OPEN_VERBS})\s+spotify$", normalized):
        return ActionIntent("open_spotify", {"app": "spotify"}, 1)
    if re.search(r"(?:quiero|vamos a|necesito)\s+programar", normalized) and re.search(r"(?:visual studio code|vs\s*code|vscode|code)", normalized):
        return ActionIntent("open_vscode", {"app": "vscode", "context": "programming"}, 1, False, 0.98)

    if re.search(rf"(?:{_OPEN_VERBS})\s+(?:el navegador|navegador)$", normalized):
        return ActionIntent("open_browser", {"app": "browser"}, 1)

    volume_match = re.search(r"^(?:baja|sube|pon|ajusta|establece|configura)\s+(?:el\s+)?volumen(?:\s+(?:al|en|a))?\s+(\d{1,3})\s*%?$", normalized)
    if volume_match:
        level = int(volume_match.group(1))
        if 0 <= level <= 100:
            return ActionIntent("set_volume", {"level": level}, 1)
    if re.search(r"^(?:silencia|silenciar|mutea|quita\s+el\s+sonido)(?:\s+(?:la|mi))?\s*(?:pc|equipo|computadora|sistema)?$", normalized):
        return ActionIntent("mute", {}, 1)
    if re.search(r"^(?:activa|activar|quita|quitar)\s+el\s+silencio$", normalized):
        return ActionIntent("unmute", {}, 1)
    if re.search(r"^(?:pausa|pausar|reproduce|reproducir|play|pause|play/pause|pon\s+pausa|pon\s+en\s+pausa)$", normalized):
        return ActionIntent("media_play_pause", {}, 1)
    if re.search(r"^(?:siguiente|saltar siguiente|siguiente\s+canción|siguiente\s+cancion|pasa\s+a\s+la\s+siguiente|next)$", normalized):
        return ActionIntent("media_next", {}, 1)
    if re.search(r"^(?:anterior|pista anterior|canción anterior|cancion anterior|previous)$", normalized):
        return ActionIntent("media_previous", {}, 1)
    if re.search(r"^(?:detén la música|detener la música|detén el audio|stop)$", normalized):
        return ActionIntent("media_stop", {}, 1)
    if re.search(r"^(?:qué|que)\s+(?:suena|está sonando|reproduce)\b|^(?:estado|status)\s+(?:de\s+)?(?:la\s+)?música$", normalized):
        return ActionIntent("media_status", {}, 0)
    close_match = re.search(r"^(?:cierra|cerrar)\s+(?:la\s+)?(.+)$", normalized)
    if close_match:
        raw_app = close_match.group(1).strip()
        app = {"spotify": "spotify", "calculadora": "calculator", "calculator": "calculator", "bloc de notas": "notepad", "notepad": "notepad", "vs code": "vscode", "vscode": "vscode", "visual studio code": "vscode"}.get(raw_app)
        if app:
            return ActionIntent("close_app", {"app": app}, 2)
    focus_match = re.search(r"^(?:enfoca|enfocar|trae al frente)\s+(?:a|el|la)?\s*(.+)$", normalized)
    if focus_match:
        raw_app = focus_match.group(1).strip()
        app = {"spotify": "spotify", "calculadora": "calculator", "calculator": "calculator", "bloc de notas": "notepad", "notepad": "notepad", "vs code": "vscode", "vscode": "vscode", "visual studio code": "vscode"}.get(raw_app)
        if app:
            return ActionIntent("focus_app", {"app": app}, 1)
    if re.search(r"^(?:minimiza|minimizar)\s+(?:a\s+|el\s+|la\s+)?(?:spotify)$", normalized):
        return ActionIntent("minimize_app", {"app": "spotify"}, 1)

    if re.search(r"^(?:lista|listar|muestra)\s+(?:mis\s+)?(?:aplicaciones|apps)(?:\s+instaladas)?$", normalized):
        return ActionIntent("list_safe_apps", {}, 0)
    running_match = re.search(r"^(?:está|esta|se encuentra)\s+(?:abiert[oa]|en ejecución|ejecutándose|corriendo)\s+(?:spotify|la calculadora|el bloc de notas|vs code|vscode)$", normalized)
    if running_match:
        raw_app = normalized.rsplit(" ", 1)[-1]
        app = {"spotify": "spotify", "calculadora": "calculator", "notas": "notepad", "code": "vscode", "vscode": "vscode"}.get(raw_app, raw_app)
        return ActionIntent("is_safe_app_running", {"app": app}, 0)

    url_match = re.search(rf"^{_OPEN_VERBS}|^visita|^navega\s+a", normalized)
    if url_match:
        candidate = normalized[url_match.end():].strip()
        url = _valid_url(candidate)
        if url:
            return ActionIntent("open_url", {"url": url}, 1)

    folder_match = re.match(rf"^{_OPEN_VERBS}\s+(?:la\s+)?(?:carpeta|directorio)\s+(.+)$", normalized)
    if folder_match:
        return ActionIntent("open_folder", {"path": _clean(folder_match.group(1))}, 1)

    project_match = re.match(rf"^{_OPEN_VERBS}\s+(?:el\s+)?proyecto(?:\s+de)?\s+(.+)$", normalized)
    if project_match:
        return ActionIntent("open_project", {"project": _clean(project_match.group(1))}, 1)
    if re.search(rf"(?:{_OPEN_VERBS})\s+(?:el\s+)?proyecto$", normalized) or re.search(r"(?:abre|abrir)\s+(?:el\s+)?proyecto\s+(?:actual|de trabajo|en el que estoy)", normalized):
        return ActionIntent("open_project", {"project": "default"}, 1)

    if re.search(r"(?:cómo|como)\s+está\s+(?:mi\s+)?pc$|estado\s+del\s+sistema$|estado\s+de\s+mi\s+pc$", normalized):
        return ActionIntent("system_status", {}, 1)
    if re.search(r"(?:cuánta|cuanta|cuánta)\s+ram|uso\s+de\s+ram|memoria\s+ram", normalized):
        return ActionIntent("system_ram", {}, 1)
    if re.search(r"(?:uso|carga)\s+(?:de\s+)?cpu|procesador", normalized):
        return ActionIntent("system_cpu", {}, 1)
    if re.search(r"(?:uso|memoria)\s+(?:de\s+)?(?:la\s+)?gpu|tarjeta\s+gráfica|tarjeta\s+grafica", normalized):
        return ActionIntent("system_gpu", {}, 1)
    if re.search(r"espacio\s+(?:del|en el)\s+disco|disco\s+duro|almacenamiento", normalized):
        return ActionIntent("system_disk", {}, 1)
    if re.search(r"(?:qué|que)\s+procesos|procesos\s+abiertos|aplicaciones\s+abiertas", normalized):
        return ActionIntent("system_processes", {}, 1)
    if re.search(r"(?:red|conexión|conexion)\s+(?:básica|basica)?|dirección ip|direccion ip", normalized):
        return ActionIntent("system_network", {}, 1)

    if re.search(rf"^{_SHOW_VERBS}\s+(?:el\s+)?estado\s+de\s+git(?:\s+en\s+(.+))?$", normalized):
        match = re.search(r"\s+en\s+(.+)$", normalized)
        return ActionIntent("git_status", {"path": _clean(match.group(1)) if match else ""}, 2)

    if re.search(r"^(?:ejecuta|ejecutar|corre|correr|lanza|lanzar)\s+(?:los\s+)?tests?(?:\s+en\s+(.+))?$", normalized):
        match = re.search(r"\s+en\s+(.+)$", normalized)
        return ActionIntent("run_tests", {"path": _clean(match.group(1)) if match else ""}, 2)

    terminal_match = re.search(r"(?:abre|abrir)\s+(?:una\s+)?terminal(?:\s+en\s+(?:el\s+)?proyecto\s+(.+))?", normalized)
    if terminal_match:
        return ActionIntent("open_terminal", {"project": _clean(terminal_match.group(1)) if terminal_match.group(1) else "default"}, 1)
    project_command = re.search(r"(?:ejecuta|corre)\s+(?:los\s+)?(tests?|backend|frontend)\s+(?:del\s+)?proyecto\s+(.+)$", normalized)
    if project_command:
        return ActionIntent("run_project_command", {"command": project_command.group(1).rstrip("s"), "project": _clean(project_command.group(2))}, 2)
    if re.search(r"(?:lista|listar|muestra)\s+(?:mis\s+)?proyectos(?:\s+registrados)?", normalized):
        return ActionIntent("list_projects", {}, 1)
    project_info = re.search(r"(?:qué sabes|información|informacion|datos)\s+(?:del|de)\s+proyecto\s+(.+)$", normalized)
    if project_info:
        return ActionIntent("show_project", {"project": _clean(project_info.group(1))}, 1)

    start_match = re.match(rf"^{_OPEN_VERBS}\s+(?:el\s+)?(?:backend|servidor|proyecto registrado)\s+(.+)$", normalized)
    if start_match:
        return ActionIntent("start_project", {"project": _clean(start_match.group(1))}, 2)
    if re.search(rf"^{_OPEN_VERBS}\s+(?:el\s+)?(?:backend|servidor|proyecto registrado)$", normalized):
        return ActionIntent("start_project", {"project": "default"}, 2)

    return None


def _context_window_snapshot(context: dict[str, Any] | None) -> tuple[str, dict[str, Any]] | None:
    if not isinstance(context, dict) or not isinstance(context.get("active_window"), dict):
        return None
    window = context["active_window"]
    window_id = str(window.get("window_id") or "").strip()
    if not window_id.isdigit() or int(window_id) <= 0:
        return None
    target = {key: window[key] for key in ("window_id", "pid", "process", "process_executable", "title") if window.get(key) not in (None, "")}
    return window_id, target


def _context_display_id(context: dict[str, Any] | None, number: str) -> str | None:
    if not isinstance(context, dict):
        return None
    wanted = int(number)
    displays = context.get("displays")
    if isinstance(displays, list):
        for index, display in enumerate(displays, 1):
            if isinstance(display, dict) and (str(display.get("display_id") or "") == f"display-{wanted}" or index == wanted):
                value = str(display.get("display_id") or "").strip()
                return value or None
    if wanted == 1:
        display = context.get("display")
        if isinstance(display, dict):
            value = str(display.get("display_id") or "").strip()
            if value:
                return value
        primary = str(context.get("primary_display_id") or "").strip()
        if primary:
            return primary
    return None


def _context_controls(context: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(context, dict):
        return []
    candidates: list[Any] = []
    for key in ("focused_control", "focus_control"):
        if isinstance(context.get(key), dict):
            candidates.append(context[key])
    if isinstance(context.get("controls"), list):
        candidates.extend(context["controls"])
    window = context.get("active_window")
    if isinstance(window, dict) and isinstance(window.get("focused_control"), dict):
        candidates.append(window["focused_control"])
    return [item for item in candidates if isinstance(item, dict) and str(item.get("control_id") or "").startswith("uia:")]


def detect_contextual_action(text: str, context: dict[str, Any] | None = None) -> ActionIntent | None:
    """Resolve natural desktop phrases only from a request-time structured snapshot."""
    normalized = _normalize_request_frame(text)
    window_info = _context_window_snapshot(context)
    if re.search(r"^(?:captura|toma una captura de|haz una captura de)\s+(?:esta\s+)?ventana$", normalized):
        if not window_info:
            return None
        window_id, target = window_info
        return ActionIntent("screen_capture_window", {"window_id": window_id, "expected_target": target}, 1, source="deterministic:desktop_context")
    display_match = re.search(r"^(?:captura|toma una captura de|haz una captura de)\s+(?:el\s+)?monitor\s+(\d+)$", normalized)
    if display_match:
        display_id = _context_display_id(context, display_match.group(1))
        if display_id:
            return ActionIntent("screen_capture_display", {"display_id": display_id}, 1, source="deterministic:desktop_context")
        return None
    if re.search(r"^(?:qué|que)\s+(?:hay|se ve)\s+en\s+(?:esta\s+)?ventana$", normalized):
        if not window_info:
            return None
        window_id, target = window_info
        return ActionIntent("uia_inspect_window", {"window_id": window_id, "expected_target": target, "max_controls": 100}, 0, source="deterministic:desktop_context")
    invoke_match = re.search(r"^(?:pulsa|presiona|oprime|haz clic en)\s+(?:el\s+botón\s+|el\s+boton\s+|la\s+|el\s+)?(.+)$", normalized)
    if invoke_match and window_info:
        query = invoke_match.group(1).strip()
        window_id, target = window_info
        query_folded = query.casefold()
        for control in _context_controls(context):
            label = f"{control.get('name', '')} {control.get('automation_id', '')}".casefold()
            if query_folded in label or label.strip() == query_folded:
                return ActionIntent("uia_invoke_control", {"window_id": window_id, "control_id": control["control_id"], "expected_target": target}, 2, source="deterministic:desktop_context")
    value_match = re.search(r"^escribe\s+(.+?)\s+en\s+(?:el\s+campo\s+|la\s+casilla\s+)?(.+)$", normalized)
    if value_match and window_info:
        value, query = value_match.group(1).strip(), value_match.group(2).strip().casefold()
        window_id, target = window_info
        for control in _context_controls(context):
            label = f"{control.get('name', '')} {control.get('automation_id', '')}".casefold()
            if query in label or label.strip() == query:
                return ActionIntent("uia_set_value", {"window_id": window_id, "control_id": control["control_id"], "value": value, "expected_target": target}, 2, source="deterministic:desktop_context")
    return None


def parse_action_plan(payload: dict | str, *, max_actions: int = 3, max_risk: int = 2, source: str | None = None) -> ActionPlan | None:
    """Parse a bounded plan; every member must pass the normal action validator."""
    try:
        raw = payload.strip() if isinstance(payload, str) else payload
        if isinstance(raw, str) and raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE | re.DOTALL).strip()
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("type") != "plan" or not isinstance(data.get("actions"), list):
        return None
    actions_raw = data["actions"]
    if not 1 <= len(actions_raw) <= max(1, min(5, int(max_actions))):
        return None
    actions: list[ActionIntent] = []
    plan_confidence = data.get("confidence", 0.0)
    for item in actions_raw:
        if not isinstance(item, dict):
            return None
        normalized_item = dict(item)
        normalized_item.setdefault("type", "action")
        normalized_item.setdefault("confidence", plan_confidence)
        normalized_item.setdefault("source", source or "structured")
        action = parse_structured_intent(normalized_item, source=source or "structured")
        if not action or action.risk_level > int(max_risk):
            return None
        actions.append(action)
    try:
        confidence = min(1.0, max(0.0, float(data.get("confidence", min(item.confidence for item in actions)))))
    except (TypeError, ValueError):
        return None
    if confidence < 0.85:
        return None
    return ActionPlan(tuple(actions), False, confidence, source or "structured")


def parse_structured_intent(payload: dict | str, *, source: str | None = None) -> ActionIntent | None:
    """Validate a JSON-like intent; unknown or executable arguments are rejected."""
    try:
        raw = payload.strip() if isinstance(payload, str) else payload
        if isinstance(raw, str) and raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE | re.DOTALL).strip()
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("type") not in {"action", "tool_call"}:
        return None
    name = str(data.get("action", "")).strip()
    args = data.get("args") if isinstance(data.get("args"), dict) else {}
    allowed_args = {
        "list_safe_apps": set(), "is_safe_app_running": {"app"}, "open_vscode": {"app", "context"}, "open_vscode_new_window": {"app"}, "open_calculator": {"app"}, "open_notepad": {"app"}, "open_spotify": {"app"}, "open_browser": set(), "open_url": {"url"}, "open_folder": {"path"},
                "open_project": {"project"}, "open_discovered_app": {"app_id"}, "system_status": set(),
 "system_ram": set(), "system_cpu": set(), "system_gpu": set(),
        "system_disk": set(), "git_status": {"path"}, "run_tests": {"path"}, "start_project": {"project", "command"},
        "run_project_command": {"project", "command"}, "system_processes": set(), "system_network": set(),
        "open_terminal": {"project"}, "stop_gaia_process": {"pid", "creation_time", "executable", "command"},
        "list_projects": set(), "show_project": {"project"},
        "close_app": {"app"}, "focus_app": {"app"}, "minimize_app": {"app"}, "set_volume": {"level"}, "mute": set(), "unmute": set(),
        "media_status": set(), "media_play_pause": set(), "media_next": set(), "media_previous": set(), "media_stop": set(),
        "vscode_focus": set(), "vscode_open_project": {"project"}, "vscode_new_window": set(), "vscode_open_file_trusted": {"path"}, "vscode_open_terminal_trusted": {"project"},
        "windows_list": set(), "windows_focus": {"window_id"}, "windows_minimize": {"window_id"}, "windows_maximize": {"window_id"}, "windows_restore": {"window_id"}, "windows_close": {"window_id"}, "windows_move_to_display": {"window_id", "display_id"},
        "file_exists": {"path"}, "file_list": {"path"}, "file_info": {"path"}, "file_open": {"path"}, "file_delete": {"path"}, "file_copy": {"source", "destination"}, "file_move": {"source", "destination"}, "file_rename": {"path", "name"}, "folder_create": {"path"},
        "get_volume": set(), "clipboard_read": set(), "clipboard_write": {"text"}, "display_list": set(), "display_info": {"display_id"}, "network_adapters": set(), "network_ip": set(), "process_info": {"pid"}, "process_stop": {"pid", "creation_time", "executable", "command"},
        "git_branch": {"path"}, "git_log": {"path"}, "git_diff": {"path"}, "git_add": {"path"}, "git_commit": {"message"}, "system_lock": set(), "system_sleep": set(), "system_restart": set(), "system_shutdown": set(),
    }
    if name not in allowed_args or not set(args).issubset(allowed_args[name]):
        return None
    if name in {"start_project", "run_project_command"} and str(args.get("command", "")) not in {"tests", "test", "backend", "frontend", "start"}:
        return None
    if name == "stop_gaia_process" and not {"pid", "creation_time"}.issubset(args) or (name == "stop_gaia_process" and not ({"executable", "command"} & set(args))):
        return None
    if any(key in args for key in ("shell", "executable", "admin", "powershell", "cmd", "sudo", "upload")) and name != "stop_gaia_process":
        return None
    safe_args: dict[str, str] = {}
    for key, value in args.items():
        if not isinstance(key, str) or not isinstance(value, (str, int, float, bool)):
            return None
        text_value = str(value).strip()
        if len(text_value) > 300 or "\x00" in text_value:
            return None
        if key == "pid" and (not text_value.isdigit() or int(text_value) <= 0):
            return None
        safe_args[key] = text_value
    try:
        confidence = min(1.0, max(0.0, float(data.get("confidence", 0.0))))
    except (TypeError, ValueError):
        confidence = 0.0
    if confidence < 0.85:
        return None
    risk = 0 if name in {"list_safe_apps", "is_safe_app_running", "system_status", "system_ram", "system_cpu", "system_gpu", "system_disk", "system_processes", "system_network", "list_projects", "show_project", "get_volume", "windows_list", "display_list", "display_info", "network_adapters", "network_ip", "process_info", "file_exists", "file_list", "file_info", "git_branch", "git_log", "git_diff", "media_status"} else 1
    if name in {"git_status", "run_tests", "start_project", "run_project_command", "open_terminal", "stop_gaia_process", "close_app", "windows_close", "file_copy", "file_move", "file_rename", "folder_create", "git_add", "git_commit", "open_discovered_app"}:
        risk = 2
    if name in {"file_delete", "process_stop", "system_lock", "system_sleep"}:
        risk = 3
    if name in {"system_restart", "system_shutdown"}:
        risk = 4
    if name in {"open_vscode_new_window", "open_calculator", "open_notepad", "open_spotify", "close_app", "focus_app", "minimize_app"} and str(safe_args.get("app", "")) not in {"vscode", "calculator", "notepad", "spotify"}:
        return None
    if name == "open_discovered_app" and (not str(safe_args.get("app_id", "")).startswith("discovered:") or any(char in str(safe_args.get("app_id", "")) for char in "\\\x00;|&")):
        return None
    if name == "set_volume":
        try:
            if not 0 <= int(float(safe_args.get("level", -1))) <= 100:
                return None
        except (TypeError, ValueError):
            return None
    if name == "is_safe_app_running" and str(safe_args.get("app", "")) not in {"vscode", "calculator", "notepad", "spotify"}:
        return None
    clean_source = source or str(data.get("source", "structured"))
    if clean_source not in {"structured", "llm", "deterministic"}:
        clean_source = "structured"
    return ActionIntent(name, safe_args, risk, False, confidence, clean_source)


def describe_action(intent: ActionIntent | ActionPlan) -> str:
    if isinstance(intent, ActionPlan):
        steps = "\n".join(f"{index}. {describe_action(item)}" for index, item in enumerate(intent.actions, 1))
        return f"GAIA quiere ejecutar este plan de {len(intent.actions)} pasos:\n{steps}\n\n¿Permitir este plan?"
    descriptions = {
        "open_vscode": "Voy a abrir Visual Studio Code sin duplicar una instancia existente.",
        "open_vscode_new_window": "Voy a abrir una nueva ventana de Visual Studio Code.",
        "open_calculator": "Voy a abrir la Calculadora mediante el lanzador seguro del sistema.",
        "open_notepad": "Voy a abrir el Bloc de notas mediante el lanzador seguro del sistema.",
        "open_spotify": "Voy a intentar abrir Spotify y reportaré el resultado real.",
        "open_browser": "Voy a abrir el navegador.",
        "open_url": f"Voy a abrir {intent.args.get('url', '')}.",
        "open_folder": f"Voy a abrir la carpeta «{intent.args.get('path', '')}».",
        "open_project": f"Voy a abrir el proyecto «{intent.args.get('project', '')}».",
        "open_discovered_app": f"Voy a abrir la aplicación descubierta «{intent.args.get('app_id', '')}» solo si está confiada.",
        "system_status": "Voy a consultar el estado del equipo.",
        "system_ram": "Voy a consultar el uso de RAM.",
        "system_cpu": "Voy a consultar el uso de CPU.",
        "system_gpu": "Voy a consultar el estado de la GPU.",
        "system_disk": "Voy a consultar el espacio del disco.",
        "git_status": "Voy a consultar el estado de Git.",
        "run_tests": "Voy a ejecutar únicamente los tests predefinidos.",
        "start_project": f"Voy a iniciar el proyecto registrado «{intent.args.get('project', '')}».",
        "run_project_command": f"Voy a ejecutar el comando registrado «{intent.args.get('command', '')}» en «{intent.args.get('project', '')}».",
        "system_processes": "Voy a consultar una lista limitada de procesos.",
        "system_network": "Voy a consultar datos básicos de red.",
        "open_terminal": f"Voy a abrir una terminal en «{intent.args.get('project', 'default')}».",
        "stop_gaia_process": f"Voy a detener el proceso de GAIA con PID {intent.args.get('pid', '')}.",
        "list_projects": "Voy a listar los proyectos registrados.",
        "show_project": f"Voy a consultar el proyecto «{intent.args.get('project', '')}».",
        "close_app": f"Voy a cerrar {intent.args.get('app', '')} con confirmación de riesgo moderado.",
        "focus_app": f"Voy a enfocar {intent.args.get('app', '')}.",
        "minimize_app": f"Voy a minimizar {intent.args.get('app', '')}.",
        "vscode_focus": "Voy a enfocar VS Code mediante el adapter code-owned.",
        "vscode_open_project": f"Voy a abrir el proyecto trusted «{intent.args.get('project', 'default')}» en VS Code.",
        "vscode_new_window": "Voy a abrir una nueva ventana de VS Code mediante el adapter code-owned.",
        "vscode_open_file_trusted": f"Voy a abrir «{intent.args.get('path', '')}» en VS Code dentro de un scope trusted.",
        "vscode_open_terminal_trusted": f"Voy a abrir una terminal trusted en «{intent.args.get('project', 'default')}».",
        "media_status": "Voy a consultar la sesión multimedia del sistema.",
        "media_play_pause": "Voy a alternar reproducción/pausa mediante los controles multimedia del sistema.",
        "media_next": "Voy a pasar al siguiente elemento multimedia mediante el sistema.",
        "media_previous": "Voy a volver al elemento multimedia anterior mediante el sistema.",
        "media_stop": "Voy a detener la sesión multimedia mediante el sistema.",
        "windows_move_to_display": f"Voy a mover la ventana {intent.args.get('window_id', '')} al display {intent.args.get('display_id', '')}.",
        "set_volume": f"Voy a ajustar el volumen al {intent.args.get('level', '')}%.",
        "mute": "Voy a silenciar el sistema.",
        "unmute": "Voy a quitar el silencio del sistema.",
        "windows_list": "Voy a listar las ventanas visibles.",
        "windows_focus": f"Voy a enfocar la ventana {intent.args.get('window_id', '')}.",
        "windows_minimize": f"Voy a minimizar la ventana {intent.args.get('window_id', '')}.",
        "windows_maximize": f"Voy a maximizar la ventana {intent.args.get('window_id', '')}.",
        "windows_restore": f"Voy a restaurar la ventana {intent.args.get('window_id', '')}.",
        "windows_close": f"Voy a cerrar la ventana {intent.args.get('window_id', '')}.",
        "file_exists": f"Voy a comprobar la ruta «{intent.args.get('path', '')}».",
        "file_list": f"Voy a listar «{intent.args.get('path', '') or 'el proyecto'}» sin leer contenido.",
        "file_info": f"Voy a consultar metadata de «{intent.args.get('path', '')}».",
        "file_open": f"Voy a abrir el archivo «{intent.args.get('path', '')}».",
        "file_delete": f"Voy a enviar «{intent.args.get('path', '')}» a la papelera reversible.",
        "file_copy": f"Voy a copiar «{intent.args.get('source', '')}» a «{intent.args.get('destination', '')}».",
        "file_move": f"Voy a mover «{intent.args.get('source', '')}» a «{intent.args.get('destination', '')}».",
        "file_rename": f"Voy a renombrar «{intent.args.get('path', '')}».",
        "folder_create": f"Voy a crear la carpeta «{intent.args.get('path', '')}».",
        "get_volume": "Voy a consultar el volumen actual.",
        "clipboard_read": "Voy a leer el clipboard local sin registrarlo.",
        "clipboard_write": "Voy a escribir el clipboard local sin registrar su contenido.",
        "display_list": "Voy a consultar los displays.",
        "display_info": f"Voy a consultar el display «{intent.args.get('display_id', '')}».",
        "network_adapters": "Voy a consultar los adaptadores de red en modo read-only.",
        "network_ip": "Voy a consultar las IP locales en modo read-only.",
        "process_info": f"Voy a consultar el proceso {intent.args.get('pid', '')}.",
        "process_stop": f"Voy a detener el proceso {intent.args.get('pid', '')} con protección de identidad.",
        "git_branch": "Voy a consultar la rama Git del proyecto trusted.",
        "git_log": "Voy a consultar el log reciente del proyecto trusted.",
        "git_diff": "Voy a consultar el diff resumido del proyecto trusted.",
        "git_add": "Voy a preparar cambios para commit en el proyecto trusted.",
        "git_commit": f"Voy a crear un commit con el mensaje «{intent.args.get('message', '')}».",
        "system_lock": "Voy a bloquear la sesión; esta operación siempre requiere confirmación.",
        "system_sleep": "Voy a suspender el equipo; esta operación siempre requiere confirmación.",
        "system_restart": "Voy a reiniciar el equipo; esta operación siempre requiere confirmación.",
        "system_shutdown": "Voy a apagar el equipo; esta operación siempre requiere confirmación.",
    }
    return descriptions.get(intent.name, "Voy a ejecutar una acción segura.")
