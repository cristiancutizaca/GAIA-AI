"""Persistent trusted-folder scopes with explicit rights.

Personal folders are discovery-only until the user grants trust. The registry
never stores commands or executable fragments; every path is canonicalized
before persistence and lookup.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any, Iterable


try:
    _TRUSTED_FOLDERS_TTL_SECONDS = max(1.0, min(300.0, float(os.getenv("GAIA_TRUSTED_FOLDERS_TTL_SECONDS", "30"))))
except (TypeError, ValueError):
    _TRUSTED_FOLDERS_TTL_SECONDS = 30.0
_TRUSTED_FOLDERS_CACHE: tuple[float, list[dict[str, Any]]] | None = None


def _invalidate_cache() -> None:
    global _TRUSTED_FOLDERS_CACHE
    _TRUSTED_FOLDERS_CACHE = None


RIGHTS = frozenset({
    "READ", "OPEN", "CREATE", "WRITE", "COPY_FROM", "COPY_TO",
    "MOVE_FROM", "MOVE_TO", "RENAME", "DELETE",
})
READ_RIGHTS = frozenset({"READ", "OPEN"})
WRITE_RIGHTS = frozenset({"CREATE", "WRITE", "RENAME", "DELETE", "COPY_TO", "MOVE_TO"})
SOURCE_RIGHTS = frozenset({"COPY_FROM", "MOVE_FROM"})
DESTINATION_RIGHTS = frozenset({"COPY_TO", "MOVE_TO"})


def _registry_path() -> Path:
    raw = os.getenv("GAIA_TRUSTED_FOLDERS_FILE", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path(os.getenv("LUMEN_DATA_DIR", str(Path(__file__).resolve().parent / "data"))) / "trusted_folders.json"


def _canonical(path: str | Path, *, must_exist: bool = True) -> Path:
    candidate = Path(str(path or "").strip().strip('"')).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    resolved = candidate.resolve(strict=False)
    if must_exist and not resolved.is_dir():
        raise ValueError("La carpeta trusted no existe o no es un directorio.")
    return resolved


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _load() -> dict[str, dict[str, Any]]:
    try:
        data = json.loads(_registry_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _save(data: dict[str, dict[str, Any]]) -> None:
    path = _registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    try:
        os.chmod(temp, 0o600)
    except OSError:
        pass
    os.replace(temp, path)
    _invalidate_cache()


def _folder_id(path: Path) -> str:
    return "folder:" + hashlib.sha256(str(path).casefold().encode("utf-8")).hexdigest()[:20]


def _normalize_rights(raw: Iterable[object] | None, *, write_allowed: bool | None = None, read_allowed: bool | None = None) -> list[str]:
    if raw is None:
        result = set()
        if read_allowed is not False:
            result.update(READ_RIGHTS)
        if write_allowed:
            result.update({"CREATE", "WRITE", "RENAME", "DELETE"})
        return sorted(result)
    result = {str(item).strip().upper() for item in raw if str(item).strip().upper() in RIGHTS}
    return sorted(result)


def _legacy_flags(rights: set[str]) -> tuple[bool, bool]:
    return bool(rights & READ_RIGHTS), bool(rights & WRITE_RIGHTS)


def _row(path: Path, *, label: str, source: str, trusted: bool, rights: Iterable[object] | None, updated_at: float = 0.0, exists: bool | None = None, state: str | None = None, legacy_write: bool | None = None, legacy_read: bool | None = None, folder_id: str | None = None) -> dict[str, Any]:
    normalized = _normalize_rights(rights, write_allowed=legacy_write, read_allowed=legacy_read)
    right_set = set(normalized)
    read_allowed, write_allowed = _legacy_flags(right_set)
    if not trusted:
        normalized = []
        read_allowed = False
        write_allowed = False
    return {
        "folder_id": folder_id or _folder_id(path),
        "path": str(path),
        "label": str(label or path.name)[:120],
        "source": str(source or "user-granted"),
        "trusted": bool(trusted),
        "state": state or ("TRUSTED" if trusted else "DISCOVERED"),
        "rights": normalized,
        "read_allowed": read_allowed,
        "write_allowed": write_allowed,
        "exists": path.is_dir() if exists is None else bool(exists),
        "updated_at": float(updated_at),
    }


def default_personal_folders() -> list[dict[str, Any]]:
    """Detect personal folders without granting any operation automatically."""
    home = Path.home().resolve()
    rows: list[dict[str, Any]] = []
    for label, name in (
        ("Documentos", "Documents"), ("Descargas", "Downloads"),
        ("Escritorio", "Desktop"), ("Imágenes", "Pictures"),
        ("Música", "Music"), ("Vídeos", "Videos"),
    ):
        path = home / name
        if path.is_dir():
            rows.append(_row(path, label=label, source="personal-default", trusted=False, rights=[], state="DISCOVERED"))
    return rows


def list_trusted_folders() -> list[dict[str, Any]]:
    global _TRUSTED_FOLDERS_CACHE
    now = time.monotonic()
    if _TRUSTED_FOLDERS_CACHE is not None and now - _TRUSTED_FOLDERS_CACHE[0] <= _TRUSTED_FOLDERS_TTL_SECONDS:
        return [dict(row) for row in _TRUSTED_FOLDERS_CACHE[1]]
    merged: dict[str, dict[str, Any]] = {row["folder_id"]: row for row in default_personal_folders()}
    for folder_id, raw in _load().items():
        if not isinstance(raw, dict) or not raw.get("path"):
            continue
        try:
            path = _canonical(raw["path"], must_exist=False)
        except ValueError:
            continue
        raw_rights = raw.get("rights") if isinstance(raw.get("rights"), list) else None
        trusted = bool(raw.get("trusted", True))
        merged[str(folder_id)] = _row(
            path,
            label=str(raw.get("label") or path.name),
            source=str(raw.get("source") or "user-granted"),
            trusted=trusted,
            rights=raw_rights,
            updated_at=float(raw.get("updated_at", 0.0)),
            exists=path.is_dir(),
            state=str(raw.get("state") or ("TRUSTED" if trusted else "DISCOVERED")),
            legacy_write=raw.get("write_allowed") if raw_rights is None else None,
            legacy_read=raw.get("read_allowed") if raw_rights is None else None,
            folder_id=str(folder_id),
        )
    result = sorted(merged.values(), key=lambda item: (str(item.get("label", "")).casefold(), str(item.get("path", "")).casefold()))
    _TRUSTED_FOLDERS_CACHE = (now, [dict(row) for row in result])
    return [dict(row) for row in result]


def grant_trusted_folder(
    path: str,
    *,
    label: str = "",
    rights: Iterable[object] | None = None,
    write_allowed: bool = False,
) -> dict[str, Any]:
    resolved = _canonical(path, must_exist=True)
    home = Path.home().resolve()
    if resolved == home or resolved.parent == resolved:
        raise ValueError("No se puede conceder trust a la raíz del usuario o del sistema.")
    normalized = _normalize_rights(rights, write_allowed=write_allowed, read_allowed=True)
    folder_id = _folder_id(resolved)
    data = _load()
    row = _row(
        resolved,
        label=str(label or resolved.name),
        source="user-granted",
        trusted=True,
        rights=normalized,
        updated_at=time.time(),
        state="TRUSTED",
        folder_id=folder_id,
    )
    data[folder_id] = row
    _save(data)
    return row


def update_trusted_folder(folder_id: str, *, rights: Iterable[object] | None = None, trusted: bool | None = None, label: str | None = None) -> dict[str, Any]:
    data = _load()
    raw = data.get(str(folder_id))
    if not isinstance(raw, dict) or not raw.get("path"):
        raise ValueError("Trusted Folder no encontrada o no editable.")
    path = _canonical(raw["path"], must_exist=False)
    current_trusted = bool(raw.get("trusted", True)) if trusted is None else bool(trusted)
    current_rights = rights if rights is not None else raw.get("rights")
    row = _row(path, label=label if label is not None else str(raw.get("label") or path.name), source=str(raw.get("source") or "user-granted"), trusted=current_trusted, rights=current_rights, updated_at=time.time(), state="TRUSTED" if current_trusted else "DISABLED", folder_id=str(folder_id))
    data[str(folder_id)] = row
    _save(data)
    return row


def revoke_trusted_folder(folder_id: str) -> bool:
    data = _load()
    if str(folder_id) not in data:
        return False
    del data[str(folder_id)]
    _save(data)
    return True


def folder_for_path(path: str | Path, *, write: bool = False, right: str | None = None) -> dict[str, Any] | None:
    try:
        resolved = _canonical(path, must_exist=False)
    except ValueError:
        return None
    required = str(right or ("WRITE" if write else "READ")).strip().upper()
    candidates = []
    for row in list_trusted_folders():
        if not row.get("trusted") or not row.get("exists", True):
            continue
        row_rights = {str(item).upper() for item in row.get("rights", [])}
        if required not in row_rights:
            continue
        root = Path(str(row["path"])).resolve()
        if _within(resolved, root):
            candidates.append((len(root.parts), row))
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


def is_trusted_path(path: str | Path, *, write: bool = False, right: str | None = None) -> bool:
    return folder_for_path(path, write=write, right=right) is not None
