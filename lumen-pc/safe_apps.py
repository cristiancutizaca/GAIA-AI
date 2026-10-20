"""Code-owned safe apps plus read-only installed-app discovery.

Discovery is observational only. A discovered executable remains blocked until the
user trusts its canonical app_id; trust stores only the fixed launch definition and
never accepts raw commands or LLM-generated paths.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import time
from typing import Any


@dataclass(frozen=True)
class SafeApp:
    canonical_name: str
    aliases: tuple[str, ...]
    windows_commands: tuple[tuple[str, ...], ...] = ()
    unix_commands: tuple[tuple[str, ...], ...] = ()
    mac_app_name: str = ""
    detect_windows_paths: tuple[str, ...] = ()
    requires_install_detection: bool = False
    launch_strategy: str = "registered_command"
    process_names: tuple[str, ...] = ()
    supported_os: tuple[str, ...] = ("windows", "linux", "darwin")
    default_risk: int = 1


@dataclass(frozen=True)
class DiscoveredApp:
    app_id: str
    display_name: str
    source: str
    launch_definition: dict[str, str]
    process_names: tuple[str, ...]
    installed: bool = True
    trusted: bool = False
    blocked: bool = False
    trusted_executable: str = ""
    app_user_model_id: str = ""
    install_location: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "app_id": self.app_id,
            "display_name": self.display_name,
            "source": self.source,
            "launch_definition": dict(self.launch_definition),
            "process_names": list(self.process_names),
            "installed": self.installed,
            "trusted": self.trusted,
            "blocked": self.blocked,
            "trusted_executable": self.trusted_executable,
            "app_user_model_id": self.app_user_model_id,
            "install_location": self.install_location,
        }


WINDOWS_SAFE_APPS: dict[str, SafeApp] = {
    "calculator": SafeApp("calculator", ("calculadora", "calculator"), windows_commands=(("calc.exe",),), unix_commands=(("gnome-calculator",), ("kcalc",), ("xcalc",)), detect_windows_paths=(r"%WINDIR%\\System32\\calc.exe",), mac_app_name="Calculator", process_names=("calculatorapp.exe", "calc.exe")),
    "notepad": SafeApp("notepad", ("bloc de notas", "notepad"), windows_commands=(("notepad.exe",),), unix_commands=(("gedit",), ("mousepad",), ("xed",)), detect_windows_paths=(r"%WINDIR%\\System32\\notepad.exe",), mac_app_name="TextEdit", process_names=("notepad.exe",)),
    "spotify": SafeApp("spotify", ("spotify",), windows_commands=(("spotify.exe",),), unix_commands=(("spotify",),), mac_app_name="Spotify", detect_windows_paths=(r"%APPDATA%\Spotify\Spotify.exe", r"%LOCALAPPDATA%\Spotify\Spotify.exe", r"%PROGRAMFILES%\Spotify\Spotify.exe", r"%PROGRAMFILES(X86)%\Spotify\Spotify.exe"), requires_install_detection=True, process_names=("spotify.exe", "spotify")),
    "vscode": SafeApp("vscode", ("visual studio code", "vs code", "vscode", "code"), windows_commands=(("code.cmd",), ("code.exe",)), unix_commands=(("code",),), process_names=("code.exe", "code")),
}

_DISCOVERY_CACHE: tuple[float, list[dict[str, Any]]] = (0.0, [])


def _trust_path() -> Path:
    raw = os.getenv("GAIA_TRUSTED_APPS_FILE", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path(os.getenv("LUMEN_DATA_DIR", str(Path(__file__).resolve().parent / "data"))) / "trusted_apps.json"


def _load_trust() -> dict[str, dict[str, Any]]:
    path = _trust_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _canonical_executable_path(path: str | Path) -> str:
    raw = str(path or "").strip()
    if not raw:
        return ""
    try:
        return str(Path(raw).expanduser().resolve(strict=False))
    except OSError:
        return raw


def _executable_identity(path: str | Path) -> dict[str, Any] | None:
    resolved = _canonical_executable_path(path)
    if not resolved:
        return None
    canonical = resolved.casefold()
    candidate = Path(resolved)
    try:
        stat = candidate.stat()
        if not candidate.is_file():
            return None
        digest = hashlib.sha256()
        with candidate.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return {"canonical_path": canonical, "size": int(stat.st_size), "mtime_ns": int(stat.st_mtime_ns), "sha256": digest.hexdigest()}
    except (OSError, ValueError):
        return None


def _save_trust(data: dict[str, dict[str, Any]]) -> None:
    path = _trust_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    try:
        os.chmod(temp, 0o600)
    except OSError:
        pass
    os.replace(temp, path)


def get_app_trust(app_id: str) -> dict[str, Any]:
    item = _load_trust().get(str(app_id).strip())
    return dict(item) if isinstance(item, dict) else {}


def is_trusted_executable(executable: str) -> bool:
    canonical = _canonical_executable_path(executable)
    if not canonical:
        return False
    current_identity = _executable_identity(canonical)
    if not current_identity:
        return False
    for item in _load_trust().values():
        if not isinstance(item, dict) or not bool(item.get("trusted")) or bool(item.get("blocked")):
            continue
        mode = str(item.get("trust_mode") or "ALWAYS").upper()
        if mode == "ONCE" and int(item.get("uses_remaining", 0) or 0) <= 0:
            continue
        definition = item.get("launch_definition") if isinstance(item.get("launch_definition"), dict) else {}
        path = str(definition.get("path") or "").strip()
        trusted_path = _canonical_executable_path(path)
        saved_identity = definition.get("executable_identity") if isinstance(definition.get("executable_identity"), dict) else {}
        if trusted_path and trusted_path.casefold() == canonical.casefold() and saved_identity and saved_identity == current_identity:
            return True
    return False


def revoke_app_trust(app_id: str) -> bool:
    canonical = str(app_id or "").strip()
    data = _load_trust()
    if canonical not in data:
        return False
    del data[canonical]
    _save_trust(data)
    global _DISCOVERY_CACHE
    _DISCOVERY_CACHE = (0.0, [])
    return True


def set_app_trust(app_id: str, *, trusted: bool, blocked: bool = False, launch_definition: dict[str, Any] | None = None, display_name: str = "", source: str = "", process_names: tuple[str, ...] = (), trust_mode: str | None = None, uses_remaining: int = 0) -> dict[str, Any]:
    canonical = str(app_id or "").strip()
    if not canonical or len(canonical) > 160 or any(char in canonical for char in "\\\x00;|&"):
        raise ValueError("app_id inválido.")
    data = _load_trust()
    current = dict(data.get(canonical) or {})
    mode = str("ALWAYS" if trust_mode is None else trust_mode).strip().upper()
    if mode not in {"ONCE", "ALWAYS"}:
        raise ValueError("trust_mode inválido.")
    remaining = max(0, int(uses_remaining if uses_remaining is not None else current.get("uses_remaining", 0)))
    if mode == "ONCE":
        remaining = 1 if trusted and remaining <= 0 else remaining
    definition = dict(launch_definition or current.get("launch_definition") or {})
    if str(definition.get("kind") or "") == "executable":
        path = _canonical_executable_path(definition.get("path", ""))
        identity = _executable_identity(path)
        if trusted and not identity:
            raise ValueError("No se puede confiar un ejecutable ausente o no legible.")
        definition["path"] = path
        if identity:
            definition["executable_identity"] = identity
        elif trusted:
            raise ValueError("Falta la identidad estable del ejecutable.")
    current.update({"app_id": canonical, "trusted": bool(trusted), "blocked": bool(blocked), "trust_mode": mode, "uses_remaining": remaining, "display_name": str(display_name)[:160], "source": str(source)[:80], "launch_definition": definition, "process_names": list(process_names or current.get("process_names") or []), "updated_at": time.time()})
    data[canonical] = current
    _save_trust(data)
    return current


def get_safe_app(canonical_name: str) -> SafeApp | None:
    return WINDOWS_SAFE_APPS.get(str(canonical_name).strip().casefold())


def resolve_windows_executable(app: SafeApp) -> str | None:
    """Resolve only a registry-owned executable, never an input path."""
    for command in app.windows_commands:
        command_name = command[0]
        found = shutil.which(command_name)
        if found:
            return found
    for raw in app.detect_windows_paths:
        expanded = os.path.expandvars(raw)
        candidate = Path(expanded).expanduser()
        if candidate.is_file():
            return str(candidate)
    return None


def resolve_unix_command(app: SafeApp) -> list[str] | None:
    for command in app.unix_commands:
        if command and shutil.which(command[0]):
            return list(command)
    return None


def list_safe_apps() -> list[dict]:
    return [{"canonical_name": app.canonical_name, "aliases": list(app.aliases), "launch_strategy": app.launch_strategy, "process_names": list(app.process_names), "supported_os": list(app.supported_os), "default_risk": app.default_risk} for app in WINDOWS_SAFE_APPS.values()]


def _canonical_executable(value: str) -> Path | None:
    raw = str(value or "").strip().strip('"')
    if not raw:
        return None
    raw = raw.split(",", 1)[0].strip().strip('"')
    candidate = Path(os.path.expandvars(raw)).expanduser()
    try:
        resolved = candidate.resolve(strict=True)
    except OSError:
        return None
    if resolved.is_file() and resolved.suffix.casefold() == ".exe":
        return resolved
    return None


def _resolve_shortcut(path: Path) -> Path | None:
    """Resolve a .lnk target through Windows COM without launching it."""
    try:
        import win32com.client  # type: ignore
        shell = win32com.client.Dispatch("WScript.Shell")
        target = str(shell.CreateShortcut(str(path)).Targetpath or "")
        return _canonical_executable(target)
    except (ImportError, OSError, TypeError, ValueError):
        return None


def _registry_executable(icon: object, install_location: object) -> Path | None:
    path = _canonical_executable(str(icon or ""))
    if path:
        return path
    location = Path(os.path.expandvars(str(install_location or ""))).expanduser()
    if location.is_dir():
        try:
            executables = sorted((item for item in location.glob("*.exe") if item.is_file()), key=lambda item: item.name.casefold())
            if len(executables) == 1:
                return _canonical_executable(str(executables[0]))
        except OSError:
            pass
    return None


def _discovery_candidates_windows() -> list[tuple[Path, str, str, str]]:
    candidates: list[tuple[Path, str, str, str]] = []
    roots = [
        (Path(os.getenv("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs", "start-menu-user"),
        (Path(os.getenv("PROGRAMDATA", "")) / "Microsoft/Windows/Start Menu/Programs", "start-menu-system"),
    ]
    for root, source in roots:
        if not root.is_dir():
            continue
        try:
            for path in root.rglob("*.lnk"):
                if path.is_file():
                    target = _resolve_shortcut(path)
                    if target:
                        candidates.append((target, source + "-shortcut", path.stem, ""))
            for path in root.rglob("*.exe"):
                if path.is_file():
                    candidates.append((path, source, path.stem, ""))
        except OSError:
            continue
    try:
        import winreg
        roots_registry = ((winreg.HKEY_CURRENT_USER, r"Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall"), (winreg.HKEY_LOCAL_MACHINE, r"Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall"))
        for root, subkey in roots_registry:
            try:
                with winreg.OpenKey(root, subkey) as uninstall:
                    for index in range(min(winreg.QueryInfoKey(uninstall)[0], 2000)):
                        try:
                            name = winreg.EnumKey(uninstall, index)
                            with winreg.OpenKey(uninstall, name) as entry:
                                display_name = ""
                                try:
                                    display_name, _ = winreg.QueryValueEx(entry, "DisplayName")
                                except OSError:
                                    pass
                                try:
                                    icon, _ = winreg.QueryValueEx(entry, "DisplayIcon")
                                except OSError:
                                    icon = ""
                                try:
                                    install_location, _ = winreg.QueryValueEx(entry, "InstallLocation")
                                except OSError:
                                    install_location = ""
                                path = _registry_executable(icon, install_location)
                                if path:
                                    candidates.append((path, "windows-uninstall-read-only", str(display_name or path.stem), ""))
                        except OSError:
                            continue
            except OSError:
                continue
    except ImportError:
        pass
    unique: dict[str, tuple[Path, str, str, str]] = {}
    for path, source, display_name, app_user_model_id in candidates:
        try:
            unique[str(path).casefold()] = (path.resolve(), source, display_name, app_user_model_id)
        except OSError:
            continue
    return list(unique.values())[:1000]


def _discovered_from_path(path: Path, source: str, trust: dict[str, dict[str, Any]], display_name: str = "", app_user_model_id: str = "") -> dict[str, Any]:
    canonical = str(path.resolve())
    executable_identity = _executable_identity(canonical)
    identity = f"exe|{canonical}|{app_user_model_id}".casefold()
    app_id = "discovered:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
    saved = trust.get(app_id) if isinstance(trust.get(app_id), dict) else {}
    trust_mode = str(saved.get("trust_mode") or "ALWAYS").upper()
    uses_remaining = max(0, int(saved.get("uses_remaining", 0) or 0))
    saved_definition = saved.get("launch_definition") if isinstance(saved.get("launch_definition"), dict) else {}
    saved_identity = saved_definition.get("executable_identity") if isinstance(saved_definition.get("executable_identity"), dict) else {}
    identity_matches = bool(executable_identity) and bool(saved_identity) and saved_identity == executable_identity
    effective_trusted = bool(saved.get("trusted")) and identity_matches and (trust_mode != "ONCE" or uses_remaining > 0)
    row = DiscoveredApp(
        app_id,
        display_name or path.stem,
        source,
        {"kind": "executable", "path": canonical, "app_user_model_id": app_user_model_id, "executable_identity": executable_identity or {}},
        (path.name.casefold(),),
        True,
        effective_trusted,
        bool(saved.get("blocked")),
        canonical,
        app_user_model_id,
        str(saved.get("install_location") or path.parent),
    )
    data = row.as_dict()
    if saved:
        data["display_name"] = str(saved.get("display_name") or data["display_name"])
        data["trust_mode"] = trust_mode
        data["uses_remaining"] = uses_remaining
    return data


def consume_discovered_app_once(app_id: str) -> bool:
    canonical = str(app_id or "").strip()
    data = _load_trust()
    current = data.get(canonical)
    if not isinstance(current, dict) or str(current.get("trust_mode", "ALWAYS")).upper() != "ONCE":
        return False
    remaining = max(0, int(current.get("uses_remaining", 0) or 0))
    if not bool(current.get("trusted")) or remaining <= 0:
        return False
    remaining -= 1
    current["uses_remaining"] = remaining
    if remaining == 0:
        current["trusted"] = False
    current["updated_at"] = time.time()
    data[canonical] = current
    _save_trust(data)
    global _DISCOVERY_CACHE
    _DISCOVERY_CACHE = (0.0, [])
    return True


def discover_installed_apps(*, force_refresh: bool = False) -> list[dict]:
    """Return code-owned and discovered apps; never grants trust or launches anything."""
    global _DISCOVERY_CACHE
    ttl = max(30.0, float(os.getenv("GAIA_APP_DISCOVERY_TTL_SECONDS", "300")))
    now = time.monotonic()
    if not force_refresh and now - _DISCOVERY_CACHE[0] < ttl:
        return [dict(item) for item in _DISCOVERY_CACHE[1]]
    trust = _load_trust()
    discovered: list[dict[str, Any]] = []
    system = platform.system()
    for app in WINDOWS_SAFE_APPS.values():
        available = bool(resolve_windows_executable(app) if system == "Windows" else resolve_unix_command(app))
        discovered.append({"app_id": f"safe:{app.canonical_name}", "canonical_name": app.canonical_name, "display_name": app.canonical_name.capitalize(), "available": available, "installed": available, "source": "code-owned-registry", "launch_definition": {"kind": "safe_registry", "canonical_name": app.canonical_name}, "process_names": list(app.process_names), "trusted": available, "blocked": False, "trusted_open": available})
    if system == "Windows":
        for path, source, display_name, app_user_model_id in _discovery_candidates_windows():
            discovered.append(_discovered_from_path(path, source, trust, display_name, app_user_model_id))
    _DISCOVERY_CACHE = (now, discovered)
    return [dict(item) for item in discovered]


def resolve_discovered_app(app_id: str, *, require_trusted: bool = True) -> dict[str, Any] | None:
    for item in discover_installed_apps():
        if str(item.get("app_id")) != str(app_id):
            continue
        if require_trusted and (not bool(item.get("trusted")) or bool(item.get("blocked"))):
            return None
        return item
    return None


def find_discovered_app(query: str) -> dict[str, Any] | None:
    wanted = str(query or "").strip().casefold()
    if not wanted:
        return None
    exact: list[dict[str, Any]] = []
    for item in discover_installed_apps():
        names = {str(item.get("display_name") or "").casefold(), str(item.get("canonical_name") or "").casefold()}
        if wanted in names or any(wanted == Path(name).stem.casefold() for name in item.get("process_names", [])):
            exact.append(item)
    return exact[0] if len(exact) == 1 else None
