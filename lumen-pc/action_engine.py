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


@dataclass(frozen=True)
class ExecutionResult:
    success: bool
    action: str
    message: str
    data: dict

    def as_dict(self) -> dict:
        return {
            "success": self.success,
            "action": self.action,
            "message": self.message,
            "data": self.data,
        }


class ActionEngineError(RuntimeError):
    pass


class ActionEngine:
    SAFE_ACTIONS = {
        "open_vscode": (1, False),
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
    }

    def __init__(self, project_dir: Path | None = None, projects_file: Path | None = None) -> None:
        self.project_dir = (project_dir or Path.cwd()).expanduser().resolve()
        self.projects_file = projects_file or Path(os.getenv("GAIA_PROJECTS_FILE", str(self.project_dir / "projects.json"))).expanduser().resolve()
        self.default_project = Path(os.getenv("GAIA_DEFAULT_PROJECT", str(self.project_dir))).expanduser().resolve()
        self.max_output_chars = max(1000, int(os.getenv("GAIA_ACTION_MAX_OUTPUT", "6000")))
        self.registry = ProjectRegistry(self.projects_file, self.project_dir)
        self.process_registry_file = self.project_dir / ".gaia_processes.json"

    def execute(self, intent: dict, *, allow_execution: bool = True) -> ExecutionResult:
        started = time.perf_counter()
        name = str(intent.get("name", "")).strip()
        args = intent.get("args") or {}
        if name not in self.SAFE_ACTIONS:
            return ExecutionResult(False, name or "unknown", "Acción no permitida por GAIA.", {"duration_ms": 0.0})
        if not allow_execution:
            return ExecutionResult(True, name, "Simulación: la acción fue validada y no se ejecutó.", {"dry_run": True, "duration_ms": 0.0})
        try:
            handler = getattr(self, f"_{name}")
            result = handler(args)
        except ActionEngineError as exc:
            result = ExecutionResult(False, name, str(exc), {})
        except Exception as exc:
            result = ExecutionResult(False, name, f"La acción falló de forma controlada: {exc}", {})
        data = dict(result.data or {})
        data.setdefault("duration_ms", round((time.perf_counter() - started) * 1000, 2))
        return ExecutionResult(result.success, result.action, result.message, data)

    def _open_vscode(self, _args: dict) -> ExecutionResult:
        running = self._find_running_vscode()
        if running:
            return ExecutionResult(True, "open_vscode", "VS Code ya está abierto; no lancé otra instancia.", {"already_open": True, "pid": running})
        command = shutil.which("code") or shutil.which("code.cmd")
        if not command:
            raise ActionEngineError("No encuentro el comando de VS Code ('code') en PATH.")
        self._spawn([command])
        return ExecutionResult(True, "open_vscode", "VS Code se está abriendo.", {"already_open": False})

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
            projects = [item.as_dict() for item in self.registry.list_projects()]
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
