"""GAIA resident supervisor for Windows/Linux user sessions.

Owns only processes it started. Does not elevate privileges, disable Windows
security, or expose the local API on the network.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=False)
CORE = ROOT / "lumen-core"
SHELL = ROOT / "lumen-pc" / "desktop_shell.py"
HOST = ROOT / "tools" / "run_remote_action_host.py"
URL = os.getenv("LUMEN_CORE_URL", f"http://127.0.0.1:{os.getenv('LUMEN_PORT', '8090')}").rstrip("/")
LOCK = Path(os.getenv("GAIA_LAUNCHER_LOCK", str(Path.home() / ".gaia" / "launcher.lock"))).expanduser()
LOG_DIR = Path(os.getenv("GAIA_RESIDENT_LOG_DIR", str(Path.home() / ".gaia" / "logs"))).expanduser()
RESTART_EXIT_CODE = 75


class SingleInstance:
    def __enter__(self):
        LOCK.parent.mkdir(parents=True, exist_ok=True)
        self.handle = LOCK.open("a+")
        try:
            if os.name == "nt":
                import msvcrt
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, BlockingIOError):
            self.handle.close()
            raise SystemExit("GAIA launcher already running")
        self.handle.seek(0)
        self.handle.truncate()
        self.handle.write(str(os.getpid()))
        self.handle.flush()
        return self

    def __exit__(self, *_):
        try:
            if os.name == "nt":
                import msvcrt
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close()
            # Do not unlink a potentially re-acquired lock file on Windows.
            if os.name != "nt":
                LOCK.unlink(missing_ok=True)


def healthy() -> bool:
    try:
        response = httpx.get(URL + "/api/health", timeout=2.0)
        return response.status_code == 200 and response.json().get("status") in {"online", "ok", "healthy"}
    except (httpx.HTTPError, ValueError):
        return False


def _env() -> dict[str, str]:
    return {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}


def _spawn(name: str, args: list[str], *, cwd: Path = ROOT, env: dict | None = None):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = (LOG_DIR / f"{name}.log").open("a", encoding="utf-8", buffering=1)
    try:
        process = subprocess.Popen(
            args, cwd=cwd, env=env or _env(),
            stdout=log, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            close_fds=(os.name != "nt"),
        )
    finally:
        log.close()
    return process


def _stop(process) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=7)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def _core_process():
    return _spawn("core", [
        sys.executable, "-m", "uvicorn", "main:app",
        "--host", os.getenv("LUMEN_HOST", "127.0.0.1"),
        "--port", os.getenv("LUMEN_PORT", "8090"),
    ], cwd=CORE)


def _wait_for_core(timeout: int) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if healthy():
            return True
        time.sleep(0.5)
    return healthy()


def launch(*, shell: bool = True, host: bool = True, wait: int = 45, once: bool = False) -> int:
    with SingleInstance():
        core_proc = None
        shell_proc = None
        host_proc = None
        host_enabled = host and os.getenv("GAIA_REMOTE_HOST_ENABLED", "true").lower() in {"1", "true", "yes"}
        try:
            if not healthy():
                core_proc = _core_process()
            if not _wait_for_core(wait):
                raise RuntimeError("GAIA Core failed readiness; check ~/.gaia/logs/core.log")
            if once:
                return 0
            if host_enabled:
                host_proc = _spawn("action-host", [sys.executable, str(HOST)])
            if not shell:
                # A headless session keeps the Core and Action Host alive until Ctrl+C.
                while True:
                    if host_enabled and host_proc is not None and host_proc.poll() is not None:
                        host_proc = _spawn("action-host", [sys.executable, str(HOST)])
                    if core_proc is not None and core_proc.poll() is not None:
                        core_proc = _core_process()
                        if not _wait_for_core(wait):
                            raise RuntimeError("GAIA Core failed to restart")
                    time.sleep(2)
            failures = []
            shell_proc = _spawn("desktop", [sys.executable, str(SHELL)],
                                env={**_env(), "GAIA_LAUNCHER_ACTIVE": "1"})
            last_health = 0.0
            while True:
                exit_code = shell_proc.poll()
                if exit_code is not None:
                    if exit_code == 0:
                        return 0  # User chose Exit GAIA.
                    now = time.monotonic()
                    failures = [t for t in failures if now - t < 60]
                    failures.append(now)
                    if len(failures) > 3:
                        raise RuntimeError("GAIA Desktop repeatedly crashed; see ~/.gaia/logs/desktop.log")
                    time.sleep(0.5 if exit_code == RESTART_EXIT_CODE else 2.0)
                    shell_proc = _spawn("desktop", [sys.executable, str(SHELL)],
                                        env={**_env(), "GAIA_LAUNCHER_ACTIVE": "1"})
                if host_enabled and host_proc is not None and host_proc.poll() is not None:
                    # The host's own 30 retries may be exhausted after a Core outage.
                    time.sleep(2)
                    host_proc = _spawn("action-host", [sys.executable, str(HOST)])
                now = time.monotonic()
                if now - last_health >= 8:
                    last_health = now
                    if not healthy():
                        if core_proc is not None and core_proc.poll() is not None:
                            core_proc = _core_process()
                        # If an external Core is offline, do not kill or replace it blindly.
                        if not _wait_for_core(wait):
                            raise RuntimeError("GAIA Core is unavailable; see ~/.gaia/logs/core.log")
                time.sleep(0.5)
        except KeyboardInterrupt:
            return 0
        finally:
            _stop(shell_proc)
            _stop(host_proc)
            _stop(core_proc)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Start/verify Core and exit.")
    parser.add_argument("--no-shell", action="store_true")
    parser.add_argument("--no-host", action="store_true")
    parser.add_argument("--wait", type=int, default=45)
    args = parser.parse_args()
    return launch(shell=not args.no_shell, host=not args.no_host,
                  wait=args.wait, once=args.once)


if __name__ == "__main__":
    raise SystemExit(main())
