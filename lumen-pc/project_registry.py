from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import platform


class ProjectRegistryError(RuntimeError):
    pass


@dataclass(frozen=True)
class RegisteredProject:
    name: str
    aliases: tuple[str, ...]
    path: Path
    working_directory: Path
    commands: dict[str, tuple[str, ...]]
    allowed_os: tuple[str, ...]
    trusted: bool = False

    def as_dict(self) -> dict:
        return {"name": self.name, "aliases": list(self.aliases), "path": str(self.path), "working_directory": str(self.working_directory), "commands": {key: list(value) for key, value in self.commands.items()}, "allowed_os": list(self.allowed_os), "trusted": self.trusted}


class ProjectRegistry:
    def __init__(self, file_path: Path, base_dir: Path) -> None:
        self.file_path = file_path.expanduser().resolve()
        self.base_dir = base_dir.expanduser().resolve()

    def list_projects(self) -> list[RegisteredProject]:
        projects: list[RegisteredProject] = []
        seen: set[str] = set()
        for project in self._load().values():
            canonical = project.name.casefold()
            if canonical in seen:
                continue
            seen.add(canonical)
            projects.append(project)
        return projects

    def resolve(self, name: str) -> RegisteredProject:
        key = " ".join(str(name or "default").strip().lower().split())
        projects = self._load()
        if key == "default" and projects:
            return next(iter(projects.values()))
        project = projects.get(key)
        if not project:
            raise ProjectRegistryError(f"No hay un proyecto registrado con el nombre o alias {name!r}.")
        return project

    def _load(self) -> dict[str, RegisteredProject]:
        if not self.file_path.exists():
            return {}
        try:
            raw = json.loads(self.file_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ProjectRegistryError(f"No se pudo leer el registro de proyectos: {exc}") from exc
        records = raw.get("projects", []) if isinstance(raw, dict) and isinstance(raw.get("projects"), list) else []
        if not records and isinstance(raw, dict):
            records = [{"name": key, **value} for key, value in raw.items() if isinstance(value, dict)]
        result: dict[str, RegisteredProject] = {}
        for record in records:
            project = self._parse(record)
            result[project.name.lower()] = project
            for alias in project.aliases:
                result[alias.lower()] = project
        return result

    def _parse(self, record: dict) -> RegisteredProject:
        if not isinstance(record, dict):
            raise ProjectRegistryError("Cada proyecto registrado debe ser un objeto JSON.")
        name = _safe_name(record.get("name"))
        raw_path = str(record.get("path", "")).strip()
        if not raw_path:
            raise ProjectRegistryError(f"El proyecto {name!r} no tiene ruta.")
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = self.base_dir / path
        path = path.resolve()
        if not path.exists() or not path.is_dir():
            raise ProjectRegistryError(f"La ruta del proyecto {name!r} no existe o no es carpeta: {path}")
        raw_workdir = str(record.get("working_directory", record.get("cwd", path))).strip()
        working_directory = Path(raw_workdir).expanduser()
        if not working_directory.is_absolute():
            working_directory = path / working_directory
        working_directory = working_directory.resolve()
        if not working_directory.is_dir() or not _within(working_directory, path):
            raise ProjectRegistryError(f"El working directory de {name!r} no es válido dentro del proyecto.")
        allowed_os = tuple(str(item) for item in (record.get("allowed_os") or ["Windows", "Linux", "Darwin"]))
        if platform.system() not in allowed_os:
            raise ProjectRegistryError(f"El proyecto {name!r} no está habilitado para {platform.system()}.")
        commands_raw = record.get("commands", {})
        if not isinstance(commands_raw, dict):
            raise ProjectRegistryError(f"Los comandos de {name!r} deben ser un objeto.")
        commands: dict[str, tuple[str, ...]] = {}
        for label, command in commands_raw.items():
            if not isinstance(label, str) or not isinstance(command, list) or not command or not all(isinstance(part, str) and part.strip() for part in command):
                raise ProjectRegistryError(f"El comando {label!r} de {name!r} debe ser una lista de argumentos no vacía.")
            commands[label] = tuple(command)
        # El formato antiguo command se transforma solo a la acción start_project.
        if not commands_raw and isinstance(record.get("command"), list):
            command = record["command"]
            if command and all(isinstance(part, str) and part.strip() for part in command):
                commands["start"] = tuple(command)
        aliases = tuple(_safe_name(alias) for alias in (record.get("aliases") or []))
        trusted = record.get("trusted", False) is True
        return RegisteredProject(name, aliases, path, working_directory, commands, allowed_os, trusted)


def _safe_name(value: object) -> str:
    name = " ".join(str(value or "").strip().split())
    if not name or len(name) > 80 or any(char in name for char in "\\/:\n\r\t"):
        raise ProjectRegistryError("Nombre de proyecto inválido.")
    return name


def _within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
