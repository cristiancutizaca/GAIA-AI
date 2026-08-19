from __future__ import annotations

"""Read-only context provider; it never executes commands supplied by an LLM."""

import os
from pathlib import Path
import platform
import socket
import subprocess


def collect_context(project_path: Path | None = None, process_limit: int = 12) -> dict:
    context: dict = {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "hostname": socket.gethostname(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count() or 1,
    }
    if project_path:
        context["project_path"] = str(project_path.expanduser().resolve())
        context["git"] = _git_context(project_path)
    context["network"] = _network_context()
    context["processes"] = _process_context(process_limit)
    return context


def _network_context() -> dict:
    try:
        addresses = sorted({item[4][0] for item in socket.getaddrinfo(socket.gethostname(), None) if item[4] and item[4][0]})
    except socket.gaierror:
        addresses = []
    return {"addresses": addresses}


def _process_context(limit: int) -> list[dict]:
    limit = min(30, max(1, int(limit)))
    try:
        import psutil
        rows = []
        for proc in sorted(psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]), key=lambda p: p.info.get("cpu_percent") or 0, reverse=True)[:limit]:
            rows.append(dict(proc.info))
        return rows
    except (ImportError, OSError):
        return []


def _git_context(path: Path) -> dict:
    root = path.expanduser().resolve()
    if not (root / ".git").exists():
        return {"is_repo": False}
    try:
        result = subprocess.run(["git", "-C", str(root), "status", "--short", "--branch"], capture_output=True, text=True, timeout=15, shell=False, check=False)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {"is_repo": True, "available": False}
    return {"is_repo": True, "available": result.returncode == 0, "status": result.stdout[-3000:] if result.returncode == 0 else ""}
