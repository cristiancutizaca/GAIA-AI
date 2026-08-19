"""Validate that an extracted GAIA release is complete and hygienic."""
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = (
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
    "start-gaia.bat",
    "start-gaia.sh",
    "tools/gaia_doctor.py",
)
REQUIRED_DIRS = ("lumen-core", "lumen-pc", "lumen-mobile", "tools", "tests")
FORBIDDEN_NAMES = {".env", ".env.local", ".env.production", ".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".gaia_processes.json"}
FORBIDDEN_DIRS = {"data", "logs", "backups", "GAIA_VAULT", "tokens", "secrets", "audio"}
FORBIDDEN_SUFFIXES = (".db", ".sqlite", ".sqlite3", ".db-wal", ".db-shm", ".sqlite-journal", ".log", ".pyc", ".pyo", ".wav", ".mp3", ".m4a", ".webm", ".pem", ".key", ".token")


def assert_structure() -> None:
    missing_files = [name for name in REQUIRED_FILES if not (ROOT / name).is_file()]
    missing_dirs = [name for name in REQUIRED_DIRS if not (ROOT / name).is_dir()]
    assert not missing_files, f"missing required files: {missing_files}"
    assert not missing_dirs, f"missing required directories: {missing_dirs}"


def assert_hygiene() -> None:
    bad: list[str] = []
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if path.name in FORBIDDEN_NAMES or any(part in FORBIDDEN_DIRS for part in relative.parts[:-1]):
            bad.append(str(relative))
        if path.is_file() and path.name != ".env.example":
            if path.name.startswith(".env.") or path.name.endswith(FORBIDDEN_SUFFIXES):
                bad.append(str(relative))
    assert not bad, f"private/local artifacts in release: {sorted(set(bad))}"
    assert not (ROOT / ".env").exists(), ".env must not be shipped"
    assert not (ROOT / ".git").exists(), ".git must not be shipped"


def assert_git_safety() -> None:
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for pattern in (".env", "*.db", "logs", "backups", "tokens", "__pycache__"):
        assert pattern in text, f".gitignore lacks protection for {pattern}"


def assert_documentation_references() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for name in (".env.example", "start-gaia.bat", "start-gaia.sh", "tools/gaia_doctor.py"):
        assert name in readme, f"README references missing required installation file: {name}"


def assert_no_obvious_secrets() -> None:
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.name in {".env.example", ".gitignore"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert not re.search(r"LUMEN_SECRET\s*=\s*(?!cambia-este-token|test-|plan-|touch-|master-|scheduler-)[A-Za-z0-9_./+:-]{16,}", text), f"possible real LUMEN_SECRET in {path}"
        assert not re.search(r"(?:sk|pk)-[A-Za-z0-9]{20,}", text), f"possible API key in {path}"
        assert not re.search(r"Bearer\s+(?!(?:test|plan|touch|master|scheduler|owner|voice|permission|action|backup|fresh|device|request|terminal)-)[A-Za-z0-9._-]{24,}", text), f"possible bearer token in {path}"


assert_structure()
assert_hygiene()
assert_git_safety()
assert_documentation_references()
assert_no_obvious_secrets()
print("RELEASE PACKAGE TEST OK: structure, dotfiles, hygiene, docs and git safety.")
