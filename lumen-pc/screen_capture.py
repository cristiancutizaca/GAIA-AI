from __future__ import annotations

import atexit
import hashlib
import hmac
import json
from pathlib import Path
import platform
import secrets
import tempfile
import time
from typing import Any
import uuid


class ScreenCaptureError(RuntimeError):
    pass


_CAPTURE_TTL_SECONDS = 120.0
_CAPTURE_DIR = Path(tempfile.gettempdir()) / "gaia-captures"
_CAPTURE_MANIFEST = _CAPTURE_DIR / "manifest.json"
_CAPTURED: set[Path] = set()


def _load_manifest() -> dict[str, dict[str, Any]]:
    try:
        payload = json.loads(_CAPTURE_MANIFEST.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _save_manifest(payload: dict[str, dict[str, Any]]) -> None:
    _CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _CAPTURE_MANIFEST.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    try:
        tmp.chmod(0o600)
    except OSError:
        pass
    tmp.replace(_CAPTURE_MANIFEST)


def _cleanup_expired() -> None:
    now = time.time()
    manifest = _load_manifest()
    changed = False
    for capture_id, entry in list(manifest.items()):
        path = Path(str(entry.get("path") or ""))
        expires_at = float(entry.get("expires_at") or 0.0)
        if expires_at <= now or not path.is_file():
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
            manifest.pop(capture_id, None)
            _CAPTURED.discard(path)
            changed = True
    if changed:
        _save_manifest(manifest)


def cleanup_captures() -> None:
    manifest = _load_manifest()
    for entry in manifest.values():
        try:
            Path(str(entry.get("path") or "")).unlink(missing_ok=True)
        except OSError:
            pass
    for path in list(_CAPTURED):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        _CAPTURED.discard(path)
    try:
        _CAPTURE_MANIFEST.unlink(missing_ok=True)
    except OSError:
        pass


atexit.register(cleanup_captures)


def _save_image(
    image: Any,
    *,
    kind: str,
    identity: str,
    owner_device: str = "pc-main",
    target_host: str = "pc-main",
    request_id: str = "",
) -> dict[str, Any]:
    _cleanup_expired()
    _CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    capture_id = f"cap_{uuid.uuid4().hex}"
    path = _CAPTURE_DIR / f"{capture_id}.png"
    image.save(path, format="PNG")
    _CAPTURED.add(path)
    now = time.time()
    expires_at = now + _CAPTURE_TTL_SECONDS
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    entry = {
        "capture_id": capture_id,
        "path": str(path),
        "kind": str(kind)[:40],
        "identity": str(identity)[:160],
        "owner_device": str(owner_device or "pc-main")[:80],
        "target_host": str(target_host or "pc-main")[:80],
        "request_id": str(request_id or "")[:100],
        "created_at": now,
        "expires_at": expires_at,
        "sha256": digest,
    }
    manifest = _load_manifest()
    manifest[capture_id] = entry
    _save_manifest(manifest)
    return {
        "available": True,
        "capture_id": capture_id,
        "path": str(path),
        "kind": str(kind)[:40],
        "temporary": True,
        "created_at": now,
        "expires_at": expires_at,
        "expires_in_seconds": _CAPTURE_TTL_SECONDS,
        "owner_device": entry["owner_device"],
        "target_host": entry["target_host"],
        "sha256": digest,
        "retrieval_url": f"/api/captures/{capture_id}",
    }


def get_capture_record(capture_id: str, *, owner_device: str = "", is_master: bool = False) -> dict[str, Any] | None:
    _cleanup_expired()
    candidate = str(capture_id or "").strip()
    if not candidate or len(candidate) > 80 or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for char in candidate):
        return None
    entry = _load_manifest().get(candidate)
    if not isinstance(entry, dict):
        return None
    if not is_master and str(entry.get("owner_device") or "") != str(owner_device or ""):
        return None
    path = Path(str(entry.get("path") or "")).resolve()
    try:
        path.relative_to(_CAPTURE_DIR.resolve())
    except ValueError:
        return None
    if not path.is_file() or float(entry.get("expires_at") or 0.0) <= time.time():
        return None
    return dict(entry)


def capture_display(display_id: str, *, owner_device: str = "pc-main", target_host: str = "pc-main", request_id: str = "") -> dict[str, Any]:
    if platform.system() != "Windows":
        return {"available": False, "reason": "La captura estructurada está disponible en Windows; no se tomó screenshot en este host."}
    try:
        from PIL import ImageGrab
        from platform_capabilities import display_info

        display = display_info(str(display_id))
        work = display.get("work_area") or {}
        bbox = (int(work.get("left", display.get("x", 0))), int(work.get("top", display.get("y", 0))), int(work.get("right", 0)), int(work.get("bottom", 0)))
        image = ImageGrab.grab(bbox=bbox, all_screens=True)
        return _save_image(image, kind="display", identity=display_id, owner_device=owner_device, target_host=target_host, request_id=request_id)
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        return {"available": False, "reason": f"No se pudo capturar el display: {exc}"}


def capture_window(window_id: str, *, owner_device: str = "pc-main", target_host: str = "pc-main", request_id: str = "") -> dict[str, Any]:
    if platform.system() != "Windows":
        return {"available": False, "reason": "La captura estructurada está disponible en Windows; no se tomó screenshot en este host."}
    try:
        from PIL import ImageGrab
        from platform_capabilities import _window

        user32, hwnd = _window(str(window_id))
        import ctypes
        from ctypes import wintypes

        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            raise ScreenCaptureError("No se pudo leer el rectángulo de la ventana.")
        bbox = (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))
        image = ImageGrab.grab(bbox=bbox, all_screens=True)
        return _save_image(image, kind="window", identity=window_id, owner_device=owner_device, target_host=target_host, request_id=request_id)
    except (ImportError, OSError, RuntimeError, ValueError, ScreenCaptureError) as exc:
        return {"available": False, "reason": f"No se pudo capturar la ventana: {exc}"}
