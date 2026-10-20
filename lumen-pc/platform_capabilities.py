from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import platform
import shutil
import socket
import subprocess
from pathlib import Path


class PlatformCapabilityError(RuntimeError):
    pass


def _windows_user32():
    if platform.system() != "Windows":
        raise PlatformCapabilityError("Esta capability requiere Windows.")
    return ctypes.windll.user32


def list_windows() -> list[dict]:
    if platform.system() != "Windows":
        return []
    user32 = _windows_user32()
    rows: list[dict] = []
    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def callback(hwnd, _lparam):
        hwnd_int = int(hwnd)
        if not user32.IsWindowVisible(hwnd):
            return True
        title_buffer = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, title_buffer, len(title_buffer))
        title = title_buffer.value.strip()
        if not title:
            return True
        pid = ctypes.c_ulong(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        rows.append({"window_id": str(hwnd_int), "title": title[:240], "pid": int(pid.value), "rect": {"left": rect.left, "top": rect.top, "right": rect.right, "bottom": rect.bottom}})
        return True
    user32.EnumWindows(enum_proc(callback), 0)
    return rows


def _window(hwnd_text: str):
    try:
        hwnd = int(str(hwnd_text))
    except (TypeError, ValueError) as exc:
        raise PlatformCapabilityError("window_id inválido.") from exc
    if hwnd <= 0:
        raise PlatformCapabilityError("window_id inválido.")
    user32 = _windows_user32()
    if not user32.IsWindow(hwnd):
        raise PlatformCapabilityError("La ventana ya no existe.")
    return user32, ctypes.c_void_p(hwnd)


def window_action(window_id: str, operation: str) -> dict:
    user32, hwnd = _window(window_id)
    constants = {"minimize": 6, "maximize": 3, "restore": 9}
    if operation in constants:
        ok = bool(user32.ShowWindow(hwnd, constants[operation]))
    elif operation == "focus":
        ok = bool(user32.SetForegroundWindow(hwnd))
    elif operation == "close":
        ok = bool(user32.PostMessageW(hwnd, 0x0010, 0, 0))
    else:
        raise PlatformCapabilityError("Operación de ventana no permitida.")
    if not ok:
        raise PlatformCapabilityError("Windows rechazó la operación de ventana.")
    return {"window_id": str(window_id), "operation": operation, "verified": True}


def _run_fixed(command: list[str], timeout: float = 10.0) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=timeout, shell=False, check=False)
    except FileNotFoundError as exc:
        raise PlatformCapabilityError(f"No está disponible la utilidad local requerida: {command[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise PlatformCapabilityError("La utilidad local superó su límite de tiempo.") from exc


def audio_devices() -> list[dict]:
    backend = _audio_backend()
    if backend == "pycaw":
        try:
            from pycaw.pycaw import AudioUtilities
            default = AudioUtilities.GetSpeakers()
            default_name = str(getattr(default, "FriendlyName", "") or getattr(default, "name", "") or "Default Windows audio endpoint")
            rows = [{"id": "default-speakers", "name": default_name, "kind": "output", "default": True, "backend": backend, "available": True}]
            getter = getattr(AudioUtilities, "GetAllDevices", None)
            if callable(getter):
                rows = []
                for index, device in enumerate(getter() or []):
                    name = str(getattr(device, "FriendlyName", "") or getattr(device, "name", "") or f"Windows audio endpoint {index + 1}")
                    rows.append({"id": f"endpoint-{index + 1}", "name": name[:200], "kind": "output", "default": name == default_name, "backend": backend, "available": True})
            return rows
        except (ImportError, OSError, AttributeError, TypeError) as exc:
            raise PlatformCapabilityError(f"No se pudieron enumerar endpoints de audio Windows: {exc}") from exc
    if backend in {"wpctl", "pactl"}:
        return [{"id": "default-speakers", "name": "Default Linux audio sink", "kind": "output", "default": True, "backend": backend, "available": True}]
    return [{"id": "default-master", "name": "Default ALSA Master", "kind": "output", "default": True, "backend": backend, "available": True}]


def _audio_backend() -> str:
    for name in ("wpctl", "pactl", "amixer"):
        if shutil.which(name):
            return name
    if platform.system() == "Windows":
        try:
            import pycaw  # noqa: F401
            return "pycaw"
        except ImportError:
            pass
    raise PlatformCapabilityError("No hay un backend de audio seguro disponible.")


def audio_get() -> dict:
    backend = _audio_backend()
    if backend == "pycaw":
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        device = AudioUtilities.GetSpeakers()
        interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        return {"level": round(float(volume.GetMasterVolumeLevelScalar()) * 100, 1), "muted": bool(volume.GetMute()), "backend": backend}
    if backend == "wpctl":
        result = _run_fixed([backend, "get-volume", "@DEFAULT_AUDIO_SINK@"])
        if result.returncode != 0:
            raise PlatformCapabilityError(result.stderr.strip() or "wpctl no pudo consultar el volumen.")
        text = result.stdout.strip()
        muted = "MUTED" in text.upper()
        percent = 0.0
        for token in text.replace("%", " ").split():
            try:
                percent = float(token) * 100 if float(token) <= 1 else float(token)
                break
            except ValueError:
                continue
        return {"level": round(percent, 1), "muted": muted, "backend": backend}
    if backend == "pactl":
        result = _run_fixed([backend, "get-sink-volume", "@DEFAULT_SINK@"]) 
        text = result.stdout.strip()
        percent = 0.0
        for token in text.replace("%", " ").split():
            try:
                percent = float(token)
                break
            except ValueError:
                continue
        muted = "yes" in _run_fixed([backend, "get-sink-mute", "@DEFAULT_SINK@"]).stdout.casefold()
        return {"level": percent, "muted": muted, "backend": backend}
    result = _run_fixed([backend, "-M", "-c", "0", "sget", "Master"])
    text = result.stdout
    muted = "[off]" in text
    percent = 0.0
    for token in text.replace("%", " ").split():
        try:
            percent = float(token)
            break
        except ValueError:
            continue
    return {"level": percent, "muted": muted, "backend": backend}


def audio_set(level: int) -> dict:
    level = max(0, min(100, int(level)))
    backend = _audio_backend()
    if backend == "pycaw":
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        device = AudioUtilities.GetSpeakers()
        interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMasterVolumeLevelScalar(level / 100.0, None)
    elif backend == "wpctl":
        result = _run_fixed([backend, "set-volume", "@DEFAULT_AUDIO_SINK@", f"{level}%"])
        if result.returncode != 0:
            raise PlatformCapabilityError(result.stderr.strip() or "wpctl no pudo cambiar el volumen.")
    elif backend == "pactl":
        result = _run_fixed([backend, "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"])
        if result.returncode != 0:
            raise PlatformCapabilityError(result.stderr.strip() or "pactl no pudo cambiar el volumen.")
    else:
        result = _run_fixed([backend, "-M", "-c", "0", "sset", "Master", f"{level}%"])
        if result.returncode != 0:
            raise PlatformCapabilityError(result.stderr.strip() or "amixer no pudo cambiar el volumen.")
    return {"level": level, "backend": backend, "verified": True}


def audio_mute(muted: bool) -> dict:
    backend = _audio_backend()
    if backend == "pycaw":
        current = audio_get()
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        device = AudioUtilities.GetSpeakers()
        interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMute(bool(muted), None)
    elif backend == "wpctl":
        result = _run_fixed([backend, "set-mute", "@DEFAULT_AUDIO_SINK@", "1" if muted else "0"])
        if result.returncode != 0:
            raise PlatformCapabilityError(result.stderr.strip() or "wpctl no pudo cambiar mute.")
    elif backend == "pactl":
        result = _run_fixed([backend, "set-sink-mute", "@DEFAULT_SINK@", "1" if muted else "0"])
        if result.returncode != 0:
            raise PlatformCapabilityError(result.stderr.strip() or "pactl no pudo cambiar mute.")
    else:
        result = _run_fixed([backend, "-M", "-c", "0", "sset", "Master", "mute" if muted else "unmute"])
        if result.returncode != 0:
            raise PlatformCapabilityError(result.stderr.strip() or "amixer no pudo cambiar mute.")
    return {"muted": bool(muted), "verified": True}


def clipboard_read() -> dict:
    if platform.system() == "Windows":
        user32 = _windows_user32()
        if not user32.OpenClipboard(None):
            raise PlatformCapabilityError("No se pudo abrir el clipboard.")
        try:
            handle = user32.GetClipboardData(13)
            if not handle:
                return {"text": "", "available": True}
            kernel32 = ctypes.windll.kernel32
            pointer = kernel32.GlobalLock(handle)
            text = ctypes.wstring_at(pointer) if pointer else ""
            if pointer:
                kernel32.GlobalUnlock(handle)
            return {"text": text, "available": True}
        finally:
            user32.CloseClipboard()
    raise PlatformCapabilityError("Clipboard nativo no disponible en este entorno.")


def clipboard_write(text: str) -> dict:
    if platform.system() == "Windows":
        user32 = _windows_user32()
        kernel32 = ctypes.windll.kernel32
        if not user32.OpenClipboard(None):
            raise PlatformCapabilityError("No se pudo abrir el clipboard.")
        try:
            data = str(text)
            user32.EmptyClipboard()
            size = (len(data) + 1) * ctypes.sizeof(ctypes.c_wchar)
            handle = kernel32.GlobalAlloc(0x0002, size)
            if not handle:
                raise PlatformCapabilityError("No se pudo reservar clipboard.")
            pointer = kernel32.GlobalLock(handle)
            ctypes.memmove(pointer, ctypes.create_unicode_buffer(data), size)
            kernel32.GlobalUnlock(handle)
            if not user32.SetClipboardData(13, handle):
                kernel32.GlobalFree(handle)
                raise PlatformCapabilityError("Windows rechazó el clipboard.")
            return {"length": len(data), "verified": True}
        finally:
            user32.CloseClipboard()
    raise PlatformCapabilityError("Clipboard nativo no disponible en este entorno.")


class _MonitorInfoEx(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD), ("szDevice", wintypes.WCHAR * 32)]


class _DisplayDevice(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("DeviceName", wintypes.WCHAR * 32), ("DeviceString", wintypes.WCHAR * 128), ("StateFlags", wintypes.DWORD), ("DeviceID", wintypes.WCHAR * 128), ("DeviceKey", wintypes.WCHAR * 128)]


def _normalize_display_rows(raw_rows: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for index, raw in enumerate(raw_rows, 1):
        rect = dict(raw.get("rect") or {})
        work = dict(raw.get("work_area") or rect)
        left = int(rect.get("left", 0))
        top = int(rect.get("top", 0))
        right = int(rect.get("right", left))
        bottom = int(rect.get("bottom", top))
        work_left = int(work.get("left", left))
        work_top = int(work.get("top", top))
        work_right = int(work.get("right", right))
        work_bottom = int(work.get("bottom", bottom))
        rows.append({
            "display_id": str(raw.get("display_id") or f"display-{index}"),
            "name": str(raw.get("name") or f"Monitor {index}"),
            "primary": bool(raw.get("primary", index == 1)),
            "x": left,
            "y": top,
            "width": max(0, right - left),
            "height": max(0, bottom - top),
            "work_area": {"left": work_left, "top": work_top, "right": work_right, "bottom": work_bottom},
        })
    return rows


def display_list() -> list[dict]:
    if platform.system() == "Windows":
        user32 = _windows_user32()
        raw_rows: list[dict] = []
        enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def callback(hmonitor, _lparam):
            monitor_info = _MonitorInfoEx()
            monitor_info.cbSize = ctypes.sizeof(_MonitorInfoEx)
            if not user32.GetMonitorInfoW(hmonitor, ctypes.byref(monitor_info)):
                return True
            rect = monitor_info.rcMonitor
            work = monitor_info.rcWork
            friendly_name = str(monitor_info.szDevice or "").strip()
            try:
                display_device = _DisplayDevice()
                display_device.cb = ctypes.sizeof(_DisplayDevice)
                if friendly_name and user32.EnumDisplayDevicesW(friendly_name, 0, ctypes.byref(display_device), 0):
                    friendly_name = str(display_device.DeviceString or friendly_name).strip()
            except (AttributeError, OSError):
                pass
            raw_rows.append({
                "display_id": f"display-{len(raw_rows) + 1}",
                "name": friendly_name[:160] or f"Monitor {len(raw_rows) + 1}",
                "primary": bool(monitor_info.dwFlags & 1),
                "rect": {"left": rect.left, "top": rect.top, "right": rect.right, "bottom": rect.bottom},
                "work_area": {"left": work.left, "top": work.top, "right": work.right, "bottom": work.bottom},
            })
            return True

        user32.EnumDisplayMonitors(None, None, enum_proc(callback), 0)
        rows = _normalize_display_rows(raw_rows)
        if rows:
            return rows
        width = int(user32.GetSystemMetrics(0))
        height = int(user32.GetSystemMetrics(1))
        return _normalize_display_rows([{"display_id": "display-1", "name": "Primary", "primary": True, "rect": {"left": 0, "top": 0, "right": width, "bottom": height}}])
    return [{"display_id": "primary", "name": "Primary", "width": 0, "height": 0, "x": 0, "y": 0, "work_area": {"left": 0, "top": 0, "right": 0, "bottom": 0}, "primary": True, "available": False}]


def display_info(display_id: str) -> dict:
    rows = display_list()
    for row in rows:
        if row["display_id"] == str(display_id):
            return row
    raise PlatformCapabilityError("display_id no encontrado.")


def move_window_to_display(window_id: str, display_id: str) -> dict:
    user32, hwnd = _window(window_id)
    display = display_info(display_id)
    work = display.get("work_area") or {}
    current = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(current)):
        raise PlatformCapabilityError("No se pudo leer el rectángulo de la ventana.")
    width = max(1, int(current.right - current.left))
    height = max(1, int(current.bottom - current.top))
    left = int(work.get("left", display.get("x", 0)))
    top = int(work.get("top", display.get("y", 0)))
    if not user32.SetWindowPos(hwnd, None, left, top, width, height, 0x0014):
        raise PlatformCapabilityError("Windows rechazó el movimiento al monitor solicitado.")
    verified = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(verified))
    return {"window_id": str(window_id), "display_id": str(display_id), "rect": {"left": verified.left, "top": verified.top, "right": verified.right, "bottom": verified.bottom}, "verified": True}


def network_adapters() -> list[dict]:
    try:
        import psutil
        return [{"name": name, "addresses": [{"family": str(addr.family), "address": addr.address} for addr in addresses]} for name, addresses in psutil.net_if_addrs().items()]
    except ImportError:
        return [{"name": "default", "addresses": [{"family": "hostname", "address": socket.gethostname()}]}]


def network_ip() -> dict:
    addresses = sorted({item[4][0] for item in socket.getaddrinfo(socket.gethostname(), None) if item[4] and item[4][0]})
    return {"hostname": socket.gethostname(), "addresses": addresses}


def power_action(operation: str) -> dict:
    system = platform.system()
    if operation == "lock":
        command = ["rundll32.exe", "user32.dll,LockWorkStation"] if system == "Windows" else ["loginctl", "lock-session"]
    elif operation == "sleep":
        command = ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"] if system == "Windows" else ["systemctl", "suspend"]
    elif operation == "restart":
        command = ["shutdown.exe", "/r", "/t", "0"] if system == "Windows" else ["systemctl", "reboot"]
    elif operation == "shutdown":
        command = ["shutdown.exe", "/s", "/t", "0"] if system == "Windows" else ["systemctl", "poweroff"]
    else:
        raise PlatformCapabilityError("Operación de energía no permitida.")
    result = _run_fixed(command, timeout=5.0)
    if result.returncode != 0:
        raise PlatformCapabilityError(result.stderr.strip() or "El sistema rechazó la operación de energía.")
    return {"operation": operation, "verified": True}


def focus_process_windows(pid: int) -> dict:
    if platform.system() != "Windows":
        raise PlatformCapabilityError("Esta capability requiere Windows.")
    user32 = _windows_user32()
    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    found = {"hwnd": 0}
    def callback(hwnd, _lparam):
        candidate_pid = ctypes.c_ulong(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(candidate_pid))
        if int(candidate_pid.value) == int(pid) and user32.IsWindowVisible(hwnd):
            found["hwnd"] = int(hwnd)
            return False
        return True
    user32.EnumWindows(enum_proc(callback), 0)
    if not found["hwnd"]:
        raise PlatformCapabilityError("No encontré una ventana visible para el proceso.")
    if not user32.SetForegroundWindow(ctypes.c_void_p(found["hwnd"])):
        raise PlatformCapabilityError("Windows rechazó el enfoque de la ventana.")
    return {"pid": int(pid), "window_id": str(found["hwnd"]), "verified": True}


def minimize_process_windows(pid: int) -> dict:
    if platform.system() != "Windows":
        raise PlatformCapabilityError("Esta capability requiere Windows.")
    user32 = _windows_user32()
    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    found = {"hwnd": 0}
    def callback(hwnd, _lparam):
        candidate_pid = ctypes.c_ulong(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(candidate_pid))
        if int(candidate_pid.value) == int(pid) and user32.IsWindowVisible(hwnd):
            found["hwnd"] = int(hwnd)
            return False
        return True
    user32.EnumWindows(enum_proc(callback), 0)
    if not found["hwnd"]:
        raise PlatformCapabilityError("No encontré una ventana visible para el proceso.")
    if not user32.ShowWindow(ctypes.c_void_p(found["hwnd"]), 6):
        raise PlatformCapabilityError("Windows rechazó la minimización.")
    return {"pid": int(pid), "window_id": str(found["hwnd"]), "verified": True}
