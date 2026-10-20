from __future__ import annotations

import hashlib
import platform
from typing import Any, Iterable


class UIAutomationError(RuntimeError):
    pass


_SENSITIVE_TOKENS = ("password", "passwd", "contraseña", "token", "secret", "credential", "credencial", "cvv", "pin")
_DESTRUCTIVE_TOKENS = ("delete", "remove", "uninstall", "format", "reset", "eliminar", "borrar", "quitar", "desinstalar", "formatear", "restablecer")
_CRITICAL_TOKENS = ("purchase", "buy", "pay", "payment", "send", "shutdown", "comprar", "pagar", "pago", "enviar", "apagar")


def dynamic_control_risk(control: dict[str, Any] | Any, operation: str) -> dict[str, Any]:
    """Return risk metadata derived from a resolved UIA control, never from free-form commands."""
    if isinstance(control, dict):
        control_type = str(control.get("control_type") or "")
        name = str(control.get("name") or "")
        automation_id = str(control.get("automation_id") or "")
        sensitive = bool(control.get("sensitive"))
    else:
        control_type = _control_type(control)
        name = _safe_name(control)
        automation_id = _automation_id(control)
        sensitive = _sensitive(control_type, name, automation_id)
    haystack = f"{control_type} {name} {automation_id}".casefold()
    operation = str(operation or "invoke").casefold()
    if sensitive:
        return {"risk_level": 4, "requires_explicit_confirmation": True, "sensitive": True, "reason": "sensitive_control"}
    if any(token in haystack for token in _CRITICAL_TOKENS):
        return {"risk_level": 4, "requires_explicit_confirmation": True, "sensitive": False, "reason": "critical_label"}
    if any(token in haystack for token in _DESTRUCTIVE_TOKENS):
        return {"risk_level": 3, "requires_explicit_confirmation": True, "sensitive": False, "reason": "destructive_label"}
    if operation == "focus":
        risk = 1
    elif operation == "set_value":
        risk = 2
    else:
        risk = 2
    return {"risk_level": risk, "requires_explicit_confirmation": risk >= 3, "sensitive": False, "reason": "structured_control"}


def _require_windows() -> None:
    if platform.system() != "Windows":
        raise UIAutomationError("Windows UI Automation no está disponible en este host.")


def _desktop():
    _require_windows()
    try:
        from pywinauto import Desktop

        return Desktop(backend="uia")
    except ImportError as exc:
        raise UIAutomationError("Falta pywinauto para Windows UI Automation; instala requirements-windows.txt.") from exc
    except (OSError, RuntimeError) as exc:
        raise UIAutomationError(f"No se pudo inicializar Windows UI Automation: {exc}") from exc


def _window(window_id: str):
    try:
        hwnd = int(str(window_id).strip())
    except (TypeError, ValueError) as exc:
        raise UIAutomationError("window_id debe ser numérico.") from exc
    if hwnd <= 0:
        raise UIAutomationError("window_id inválido.")
    try:
        wrapper = _desktop().window(handle=hwnd).wrapper_object()
        if not wrapper.exists():
            raise UIAutomationError("La ventana ya no existe.")
        return wrapper
    except UIAutomationError:
        raise
    except (OSError, RuntimeError, AttributeError) as exc:
        raise UIAutomationError(f"No se pudo resolver la ventana UIA: {exc}") from exc


def _safe_name(control: Any) -> str:
    try:
        return str(control.window_text() or "")[:240]
    except (AttributeError, OSError, RuntimeError):
        return ""


def _control_type(control: Any) -> str:
    try:
        return str(control.element_info.control_type or "Unknown")[:80]
    except (AttributeError, OSError, RuntimeError):
        return "Unknown"


def _automation_id(control: Any) -> str:
    try:
        return str(control.element_info.automation_id or "")[:160]
    except (AttributeError, OSError, RuntimeError):
        return ""


def _rectangle(control: Any) -> dict[str, int]:
    try:
        rect = control.rectangle()
        return {"left": int(rect.left), "top": int(rect.top), "right": int(rect.right), "bottom": int(rect.bottom)}
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        return {"left": 0, "top": 0, "right": 0, "bottom": 0}


def _sensitive(control_type: str, name: str, automation_id: str) -> bool:
    text = f"{control_type} {name} {automation_id}".casefold()
    return "password" in text or "passwordbox" in text or any(token in text for token in _SENSITIVE_TOKENS)


def _control_id(window_id: str, control_type: str, name: str, automation_id: str, bounds: dict[str, int]) -> str:
    identity = "|".join([str(window_id), control_type, automation_id, name, ",".join(str(bounds[key]) for key in ("left", "top", "right", "bottom"))])
    return "uia:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


def window_identity(window_id: str) -> dict[str, Any]:
    wrapper = _window(window_id)
    try:
        pid = int(wrapper.process_id())
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
        raise UIAutomationError("No se pudo leer pid de la ventana UIA.") from exc
    process_name = ""
    process_executable = ""
    try:
        import psutil

        process = psutil.Process(pid)
        process_name = str(process.name() or "")[:160]
        process_executable = str(process.exe() or "")[:400]
    except (ImportError, OSError, ValueError):
        pass
    return {"window_id": str(window_id), "pid": pid, "process": process_name, "process_executable": process_executable, "title": _safe_name(wrapper), "bounds": _rectangle(wrapper)}


def verify_window_identity(window_id: str, expected: dict[str, Any]) -> dict[str, Any]:
    current = window_identity(window_id)
    if not isinstance(expected, dict):
        raise UIAutomationError("expected_target debe ser un objeto estructurado.")
    for key in ("window_id", "pid", "process", "process_executable"):
        expected_value = str(expected.get(key) or "").strip()
        if expected_value and str(current.get(key) or "").strip().casefold() != expected_value.casefold():
            raise UIAutomationError("El target UIA cambió desde la creación de la acción; se rechaza por stale-target protection.")
    return current


def _normalise_control(window_id: str, control: Any) -> dict[str, Any]:
    control_type = _control_type(control)
    name = _safe_name(control)
    automation_id = _automation_id(control)
    bounds = _rectangle(control)
    sensitive = _sensitive(control_type, name, automation_id)
    try:
        enabled = bool(control.is_enabled())
    except (AttributeError, OSError, RuntimeError):
        enabled = False
    try:
        focused = bool(control.has_focus())
    except (AttributeError, OSError, RuntimeError):
        focused = False
    invoke_available = control_type.casefold() in {"button", "hyperlink", "menuitem", "tabitem", "listitem", "checkbox", "radiobutton"}
    value_available = not sensitive and control_type.casefold() in {"edit", "document", "combobox", "slider", "text"}
    risk = dynamic_control_risk({"control_type": control_type, "name": name, "automation_id": automation_id, "sensitive": sensitive}, "focus")
    return {
        "control_id": _control_id(window_id, control_type, name, automation_id, bounds),
        "automation_id": automation_id,
        "control_type": control_type,
        "name": name,
        "enabled": enabled,
        "focused": focused,
        "bounds": bounds,
        "value_available": value_available,
        "invoke_available": invoke_available,
        "sensitive": sensitive,
        "value": None,
        "dynamic_risk": risk["risk_level"],
        "requires_explicit_confirmation": risk["requires_explicit_confirmation"],
    }


def _descendants(wrapper: Any, max_controls: int = 200) -> Iterable[Any]:
    try:
        return list(wrapper.descendants(control_type=None, depth=None))[:max_controls]
    except (AttributeError, OSError, RuntimeError) as exc:
        raise UIAutomationError(f"No se pudo leer el árbol UIA seleccionado: {exc}") from exc


def list_controls(window_id: str, *, max_controls: int = 100) -> dict[str, Any]:
    max_controls = max(1, min(200, int(max_controls)))
    wrapper = _window(window_id)
    controls = [_normalise_control(str(window_id), control) for control in _descendants(wrapper, max_controls=max_controls)]
    return {"available": True, "window_id": str(window_id), "controls": controls, "count": len(controls), "truncated": len(controls) >= max_controls}


def inspect_window(window_id: str, *, max_controls: int = 100) -> dict[str, Any]:
    wrapper = _window(window_id)
    controls = list_controls(window_id, max_controls=max_controls)
    try:
        pid = int(wrapper.process_id())
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        pid = 0
    return {
        "available": True,
        "window_id": str(window_id),
        "title": _safe_name(wrapper),
        "pid": pid,
        "process": str(getattr(wrapper.element_info, "class_name", "") or "")[:160],
        "bounds": _rectangle(wrapper),
        "controls": controls["controls"],
        "count": controls["count"],
        "truncated": controls["truncated"],
    }


def get_focused_control(window_id: str, *, max_controls: int = 200) -> dict[str, Any]:
    wrapper = _window(window_id)
    for control in _descendants(wrapper, max_controls=max_controls):
        try:
            if control.has_focus():
                return {"available": True, "window_id": str(window_id), "control": _normalise_control(str(window_id), control)}
        except (AttributeError, OSError, RuntimeError):
            continue
    return {"available": True, "window_id": str(window_id), "control": None}


def resolve_control(window_id: str, control_id: str) -> tuple[Any, dict[str, Any]]:
    wanted = str(control_id or "").strip()
    if not wanted.startswith("uia:"):
        raise UIAutomationError("control_id UIA inválido.")
    matches: list[tuple[Any, dict[str, Any]]] = []
    for control in _descendants(_window(window_id), max_controls=200):
        row = _normalise_control(str(window_id), control)
        if row["control_id"] == wanted:
            matches.append((control, row))
    if len(matches) != 1:
        raise UIAutomationError("El control UIA no existe o no es único; no se ejecuta una interacción ambigua.")
    return matches[0]


def resolve_control_risk(window_id: str, control_id: str, operation: str) -> dict[str, Any]:
    """Resolve one unique control and calculate risk without producing an effect."""
    _control, row = resolve_control(window_id, control_id)
    risk = dynamic_control_risk(row, operation)
    return {"window_id": str(window_id), "control": row, **risk}


def focus_control(window_id: str, control_id: str) -> dict[str, Any]:
    control, row = resolve_control(window_id, control_id)
    if row["sensitive"] or not row["enabled"]:
        raise UIAutomationError("El control no es interactuable por policy.")
    control.set_focus()
    risk = dynamic_control_risk(row, "focus")
    return {"window_id": str(window_id), "control": row, "dynamic_risk": risk["risk_level"], "requires_explicit_confirmation": risk["requires_explicit_confirmation"], "verified": True}


def invoke_control(window_id: str, control_id: str) -> dict[str, Any]:
    control, row = resolve_control(window_id, control_id)
    if row["sensitive"] or not row["enabled"] or not row["invoke_available"]:
        raise UIAutomationError("El control no permite invoke seguro.")
    risk = dynamic_control_risk(row, "invoke")
    if risk["sensitive"]:
        raise UIAutomationError("No se permite invocar un control UIA sensible.")
    try:
        control.invoke()
    except (AttributeError, OSError, RuntimeError) as exc:
        raise UIAutomationError(f"Windows rechazó invoke del control: {exc}") from exc
    return {"window_id": str(window_id), "control": row, "dynamic_risk": risk["risk_level"], "requires_explicit_confirmation": risk["requires_explicit_confirmation"], "risk_reason": risk["reason"], "verified": True}


def set_control_value(window_id: str, control_id: str, value: str) -> dict[str, Any]:
    control, row = resolve_control(window_id, control_id)
    if row["sensitive"] or not row["enabled"] or not row["value_available"]:
        raise UIAutomationError("El control no permite set_value seguro o es sensible.")
    clean = str(value)
    if len(clean) > 4000 or "\x00" in clean:
        raise UIAutomationError("El valor UIA está fuera de límites.")
    risk = dynamic_control_risk(row, "set_value")
    if risk["sensitive"]:
        raise UIAutomationError("No se permite escribir en un control UIA sensible.")
    try:
        control.set_edit_text(clean)
    except (AttributeError, OSError, RuntimeError) as exc:
        raise UIAutomationError(f"Windows rechazó set_value: {exc}") from exc
    return {"window_id": str(window_id), "control": {**row, "value": None}, "dynamic_risk": risk["risk_level"], "requires_explicit_confirmation": risk["requires_explicit_confirmation"], "risk_reason": risk["reason"], "verified": True}
