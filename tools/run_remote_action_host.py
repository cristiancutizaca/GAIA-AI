from __future__ import annotations

import ctypes
import os
import platform
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-pc"))

from remote_action_host import RemoteActionHost


_DPAPI_MAGIC = b"GAIA-DPAPI-V1\n"


def _token_file() -> Path:
    return Path(os.getenv("GAIA_REMOTE_HOST_TOKEN_FILE", str(ROOT / ".gaia_remote_host.token"))).expanduser()


def _dpapi_protect(value: bytes) -> bytes:
    if platform.system() != "Windows":
        raise RuntimeError("DPAPI solo está disponible en Windows.")
    try:
        from ctypes import wintypes

        class DataBlob(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

        crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        source = ctypes.create_string_buffer(value)
        input_blob = DataBlob(len(value), ctypes.cast(source, ctypes.POINTER(ctypes.c_char)))
        output_blob = DataBlob()
        if not crypt32.CryptProtectData(ctypes.byref(input_blob), None, None, None, None, 0, ctypes.byref(output_blob)):
            raise RuntimeError("CryptProtectData falló.")
        try:
            return ctypes.string_at(output_blob.pbData, output_blob.cbData)
        finally:
            kernel32.LocalFree(output_blob.pbData)
    except (AttributeError, OSError, TypeError) as exc:
        raise RuntimeError("No se pudo usar DPAPI; no se guardará el token en plaintext.") from exc


def _dpapi_unprotect(value: bytes) -> str:
    if platform.system() != "Windows":
        raise RuntimeError("El token DPAPI solo puede abrirse en Windows.")
    try:
        from ctypes import wintypes

        class DataBlob(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

        crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        source = ctypes.create_string_buffer(value)
        input_blob = DataBlob(len(value), ctypes.cast(source, ctypes.POINTER(ctypes.c_char)))
        output_blob = DataBlob()
        if not crypt32.CryptUnprotectData(ctypes.byref(input_blob), None, None, None, None, 0, ctypes.byref(output_blob)):
            raise RuntimeError("CryptUnprotectData falló.")
        try:
            return ctypes.string_at(output_blob.pbData, output_blob.cbData).decode("utf-8").strip()
        finally:
            kernel32.LocalFree(output_blob.pbData)
    except (AttributeError, OSError, TypeError, UnicodeDecodeError) as exc:
        raise RuntimeError("No se pudo descifrar el token DPAPI.") from exc


def _write_token(token: str) -> None:
    value = str(token or "").strip()
    if not value:
        raise RuntimeError("Core devolvió un token vacío.")
    path = _token_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    if platform.system() == "Windows":
        payload = _DPAPI_MAGIC + _dpapi_protect(value.encode("utf-8"))
    else:
        payload = (value + "\n").encode("utf-8")
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_bytes(payload)
    try:
        temp.chmod(0o600)
    except OSError:
        pass
    os.replace(temp, path)
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _read_token() -> str:
    path = _token_file()
    if not path.is_file():
        return ""
    try:
        raw = path.read_bytes()
    except OSError:
        return ""
    if raw.startswith(_DPAPI_MAGIC):
        return _dpapi_unprotect(raw[len(_DPAPI_MAGIC):])
    # Legacy v0.6.2 file. On Windows migrate it immediately to DPAPI;
    # on Linux retain the explicit chmod-600 file model.
    value = raw.decode("utf-8").strip()
    if value and platform.system() == "Windows":
        _write_token(value)
    return value


def _bootstrap_token(core_url: str, secret: str, device_id: str) -> str:
    headers = {"Authorization": f"Bearer {secret}"}
    with httpx.Client(timeout=10.0) as client:
        client.post(f"{core_url}/api/devices/register", headers=headers, json={"device_id": device_id, "capabilities": ["chat", "actions_request", "actions_execute", "action_host", "device_self"], "permission_level": 2, "name": "GAIA PC Action Host", "device_type": "pc"}).raise_for_status()
        created = client.post(f"{core_url}/api/devices/{device_id}/token", headers=headers, json={"ttl_days": int(os.getenv("GAIA_DEVICE_TOKEN_TTL_DAYS", "365"))}).json()
    token = str(created.get("token") or "").strip()
    if not token:
        raise RuntimeError("Core no devolvió token de pc-main.")
    _write_token(token)
    return token


def load_token(core_url: str, device_id: str) -> str:
    value = os.getenv("GAIA_REMOTE_HOST_TOKEN", "").strip()
    if value:
        return value
    value = _read_token()
    if value:
        return value
    secret = os.getenv("LUMEN_SECRET", "").strip()
    if not secret:
        raise RuntimeError("Configura GAIA_REMOTE_HOST_TOKEN o LUMEN_SECRET para bootstrap seguro del host pc-main.")
    return _bootstrap_token(core_url, secret, device_id)


def main() -> int:
    core_url = os.getenv("LUMEN_CORE_URL", "http://127.0.0.1:8090").rstrip("/")
    device_id = os.getenv("GAIA_PC_DEVICE_ID", "pc-main").strip() or "pc-main"
    if os.getenv("GAIA_REMOTE_HOST_ENABLED", "true").strip().lower() in {"0", "false", "no", "off"}:
        return 0
    for _ in range(30):
        try:
            token = load_token(core_url, device_id)
            host = RemoteActionHost(core_url=core_url, token=token, device_id=device_id, project_dir=ROOT)
            host.run_forever()
            return 0
        except (httpx.HTTPError, OSError, RuntimeError) as exc:
            print(f"GAIA Remote Action Host espera Core: {str(exc)[:180]}", file=sys.stderr)
            time.sleep(2.0)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
