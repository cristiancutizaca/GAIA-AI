#!/usr/bin/env python3
"""Build and verify a clean GAIA-AI release archive.

The source tree is never packaged by a broad glob. Required dotfiles are
included explicitly, private/runtime artifacts fail the build, the archive is
reopened and compared with staging, and only then is SHA-256 written.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TOP_LEVEL_FILES = (
    ".env.example",
    ".gitignore",
    "README.md",
    "CHANGELOG.md",
    "AUDIT.md",
    "TEST_REPORT.md",
    "KNOWN_LIMITATIONS.md",
    "MEMORY_ARCHITECTURE.md",
    "SECURITY_MODEL.md",
    "DEVICES.md",
    "MIGRATION_LUMEN_GAIA.md",
    "MODIFIED_FILES.md",
    "ROLLBACK.md",
    "FINAL_VALIDATION.txt",
    "V051_REQUIREMENTS.md",
    "V052_REQUIREMENTS.md",
    "BASELINE_V052.txt",
    "projects.json.example",
    "start-client.bat",
    "start-client.sh",
    "start-gaia.bat",
    "start-gaia.sh",
    "start-gui.bat",
    "start-gui.sh",
    "start.bat",
    "start.sh",
)
TOP_LEVEL_DIRS = ("lumen-core", "lumen-pc", "lumen-mobile", "tests", "tools")
FORBIDDEN_NAMES = {".env", ".env.local", ".env.production", ".git", ".venv", "venv", "env", "__pycache__", ".pytest_cache", ".dart_tool", "build", ".gaia_processes.json"}
FORBIDDEN_DIR_NAMES = {"data", "logs", "backups", "GAIA_VAULT", "tokens", "secrets", "audio", "exports", "emergency", "tmp"}
FORBIDDEN_SUFFIXES = (".db", ".sqlite", ".sqlite3", ".db-wal", ".db-shm", ".sqlite-journal", ".log", ".pyc", ".pyo", ".wav", ".mp3", ".m4a", ".webm", ".pem", ".key", ".token", ".bak", ".tmp")
FIXED_ZIP_TIME = (2020, 1, 1, 0, 0, 0)


def detect_version() -> tuple[str, str]:
    config = (ROOT / "lumen-core" / "config.py").read_text(encoding="utf-8")
    match = re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', config, re.MULTILINE)
    if not match:
        raise RuntimeError("No se pudo detectar VERSION en lumen-core/config.py")
    version = match.group(1)
    release = version.removesuffix("-pc")
    if not re.fullmatch(r"0\.5\.3", release):
        raise RuntimeError(f"Esta herramienta exige GAIA-AI v0.5.3; detectó {version!r}")
    return version, release


def is_forbidden(path: Path, relative: Path) -> str | None:
    name = path.name
    if name in FORBIDDEN_NAMES:
        return f"nombre prohibido: {relative}"
    if any(part in FORBIDDEN_DIR_NAMES for part in relative.parts[:-1]):
        return f"directorio privado/prohibido: {relative}"
    if name != ".env.example" and (name == ".env" or name.startswith(".env.")):
        return f"archivo de entorno privado: {relative}"
    if name.endswith(FORBIDDEN_SUFFIXES):
        return f"artefacto privado/local: {relative}"
    if name.endswith(".zip"):
        return f"ZIP no permitido dentro de release: {relative}"
    return None


def required_source_files() -> list[Path]:
    missing = [name for name in TOP_LEVEL_FILES if not (ROOT / name).is_file()]
    missing.extend(name for name in TOP_LEVEL_DIRS if not (ROOT / name).is_dir())
    if missing:
        raise RuntimeError("Faltan fuentes obligatorias: " + ", ".join(missing))
    return [ROOT / name for name in TOP_LEVEL_FILES] + [ROOT / name for name in TOP_LEVEL_DIRS]


def copy_allowlist(staging_root: Path) -> list[Path]:
    package_root = staging_root / ROOT.name
    package_root.mkdir(parents=True)
    copied: list[Path] = []
    for item in required_source_files():
        destination = package_root / item.name
        if item.is_file():
            relative = Path(item.name)
            problem = is_forbidden(item, relative)
            if problem:
                raise RuntimeError(f"RELEASE BUILD FAIL: {problem}")
            shutil.copy2(item, destination)
            copied.append(destination)
            continue
        for source in sorted(item.rglob("*")):
            relative = Path(item.name) / source.relative_to(item)
            problem = is_forbidden(source, relative)
            if source.is_dir():
                # Local runtime directories are not release sources; skip them.
                if problem:
                    continue
                (package_root / relative).mkdir(parents=True, exist_ok=True)
            elif source.is_file():
                if problem:
                    raise RuntimeError(f"RELEASE BUILD FAIL: {problem}")
                target = package_root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                copied.append(target)
    return copied


def archive_name(path: Path) -> str:
    return f"{ROOT.name}/{path.relative_to(path.parents[1])}" if False else f"{ROOT.name}/{path.relative_to(path.parents[1])}"


def write_archive(staging_root: Path, files: list[Path], output_zip: Path) -> set[str]:
    package_root = staging_root / ROOT.name
    expected = set()
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for source in sorted(files, key=lambda item: item.relative_to(package_root).as_posix()):
            relative = source.relative_to(package_root).as_posix()
            member = f"{ROOT.name}/{relative}"
            data = source.read_bytes()
            info = zipfile.ZipInfo(member, FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = stat.S_IMODE(source.stat().st_mode)
            info.external_attr = (mode & 0xFFFF) << 16
            bundle.writestr(info, data)
            expected.add(member)
    return expected


def verify_archive(output_zip: Path, expected: set[str]) -> None:
    with zipfile.ZipFile(output_zip) as bundle:
        if bundle.testzip() is not None:
            raise RuntimeError("El ZIP no supera la prueba de integridad.")
        actual = set(bundle.namelist())
        if actual != expected:
            raise RuntimeError(f"Contenido del ZIP no coincide con staging; extras={sorted(actual - expected)}, faltantes={sorted(expected - actual)}")
        for name in actual:
            relative = Path(name)
            if name.startswith("/") or ".." in relative.parts or any(part == "" for part in relative.parts):
                raise RuntimeError(f"Ruta insegura dentro del ZIP: {name}")
            if name.endswith(FORBIDDEN_SUFFIXES) or name.endswith(".zip") or any(part in FORBIDDEN_DIR_NAMES for part in relative.parts):
                raise RuntimeError(f"Archivo prohibido dentro del ZIP: {name}")
            if relative.name in FORBIDDEN_NAMES or (relative.name.startswith(".env.") and relative.name != ".env.example"):
                raise RuntimeError(f"Archivo privado dentro del ZIP: {name}")
        required = {f"{ROOT.name}/{name}" for name in TOP_LEVEL_FILES if name in {".env.example", ".gitignore", "README.md", "CHANGELOG.md", "AUDIT.md", "TEST_REPORT.md", "KNOWN_LIMITATIONS.md", "MEMORY_ARCHITECTURE.md", "SECURITY_MODEL.md", "DEVICES.md", "MIGRATION_LUMEN_GAIA.md", "MODIFIED_FILES.md", "ROLLBACK.md", "FINAL_VALIDATION.txt"}}
        required.update({f"{ROOT.name}/{name}/" for name in ()})
        missing = sorted(required - actual)
        if missing:
            raise RuntimeError("Faltan archivos obligatorios en el ZIP: " + ", ".join(missing))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a clean, verified GAIA-AI v0.5.3 release")
    parser.add_argument("--output-dir", type=Path, default=ROOT.parent)
    args = parser.parse_args()
    version, release = detect_version()
    output_dir = args.output_dir.expanduser().resolve()
    output_zip = output_dir / f"GAIA-AI-v{release}-final.zip"
    checksum_file = output_zip.with_suffix(output_zip.suffix + ".sha256")
    output_zip.unlink(missing_ok=True)
    checksum_file.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix="gaia_release_stage_") as temp:
        staging_root = Path(temp)
        files = copy_allowlist(staging_root)
        expected = write_archive(staging_root, files, output_zip)
        verify_archive(output_zip, expected)
    digest = sha256(output_zip)
    checksum_file.write_text(f"{digest}  {output_zip.name}\n", encoding="utf-8")
    print(f"RELEASE BUILD PASS: {output_zip}")
    print(f"version={version}; files={len(expected)}; sha256={digest}")
    print(f"checksum={checksum_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
