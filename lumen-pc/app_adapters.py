from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class AppAdapter:
    identity: str
    capabilities: tuple[str, ...]
    process_names: tuple[str, ...]


_ADAPTERS: Mapping[str, AppAdapter] = {
    "safe:vscode": AppAdapter(
        identity="safe:vscode",
        capabilities=("vscode.focus", "vscode.open_project", "vscode.new_window", "vscode.open_file_trusted", "vscode.open_terminal_trusted"),
        process_names=("code.exe", "code", "code - insiders.exe", "code - insiders"),
    ),
}


def get_app_adapter(identity: str) -> AppAdapter | None:
    return _ADAPTERS.get(str(identity or "").strip().casefold())


def list_app_adapters() -> list[dict]:
    return [{"identity": item.identity, "capabilities": list(item.capabilities), "process_names": list(item.process_names), "code_owned": True} for item in _ADAPTERS.values()]
