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


def detect_action(text: str) -> ActionIntent | None:
    """Return an allowlisted action only when the phrase is unambiguous."""
    normalized = _clean(text).lower()
    normalized = re.sub(r"^(?:gaia|g\\.a\\.i\\.a)[,;:\\s]+", "", normalized).strip()
    if not normalized:
        return None

    if re.search(rf"(?:{_OPEN_VERBS})\s+(?:visual studio code|vs\s*code|vscode|code)", normalized):
        return ActionIntent("open_vscode", {"app": "vscode"}, 1)
    if re.search(r"(?:quiero|vamos a|necesito)\s+programar", normalized) and re.search(r"(?:visual studio code|vs\s*code|vscode|code)", normalized):
        return ActionIntent("open_vscode", {"app": "vscode", "context": "programming"}, 1, False, 0.98)

    if re.search(rf"(?:{_OPEN_VERBS})\s+(?:google\s+chrome|chrome|el navegador|navegador)", normalized):
        return ActionIntent("open_browser", {"app": "browser"}, 1)

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
    if not 1 <= len(actions_raw) <= max(1, min(3, int(max_actions))):
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
        "open_vscode": {"app", "context"}, "open_browser": set(), "open_url": {"url"}, "open_folder": {"path"},
        "open_project": {"project"}, "system_status": set(), "system_ram": set(), "system_cpu": set(), "system_gpu": set(),
        "system_disk": set(), "git_status": {"path"}, "run_tests": {"path"}, "start_project": {"project", "command"},
        "run_project_command": {"project", "command"}, "system_processes": set(), "system_network": set(),
        "open_terminal": {"project"}, "stop_gaia_process": {"pid", "creation_time", "executable", "command"},
        "list_projects": set(), "show_project": {"project"},
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
    risk = 2 if name in {"git_status", "run_tests", "start_project", "run_project_command", "open_terminal", "stop_gaia_process"} else 1
    clean_source = source or str(data.get("source", "structured"))
    if clean_source not in {"structured", "llm", "deterministic"}:
        clean_source = "structured"
    return ActionIntent(name, safe_args, risk, False, confidence, clean_source)


def describe_action(intent: ActionIntent | ActionPlan) -> str:
    if isinstance(intent, ActionPlan):
        steps = "\n".join(f"{index}. {describe_action(item)}" for index, item in enumerate(intent.actions, 1))
        return f"GAIA quiere ejecutar este plan de {len(intent.actions)} pasos:\n{steps}\n\n¿Permitir este plan?"
    descriptions = {
        "open_vscode": "Voy a abrir Visual Studio Code.",
        "open_browser": "Voy a abrir el navegador.",
        "open_url": f"Voy a abrir {intent.args.get('url', '')}.",
        "open_folder": f"Voy a abrir la carpeta «{intent.args.get('path', '')}».",
        "open_project": f"Voy a abrir el proyecto «{intent.args.get('project', '')}».",
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
        "show_project": f"Voy a consultar el proyecto «{intent.args.get('project', '')}»."
    }
    return descriptions.get(intent.name, "Voy a ejecutar una acción segura.")
