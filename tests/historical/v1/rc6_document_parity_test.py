from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unicodedata
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools" / "build_release.py"
DOC_BUILDER = ROOT / "tools" / "build_docs.py"

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def norm(name: str) -> str:
    return unicodedata.normalize("NFC", name).casefold()

def docs_from(path: Path, root_name: str) -> tuple[dict[str, bytes], dict[str, tuple[int, int, int, int, int, int, int]]]:
    with zipfile.ZipFile(path) as bundle:
        assert bundle.testzip() is None
        names = bundle.namelist()
        assert len(names) == len(set(names))
        assert len({norm(name) for name in names}) == len(names)
        docs: dict[str, bytes] = {}
        metadata = {}
        roots = sorted({name.split("/", 1)[0] for name in names if "/" in name})
        assert roots == [root_name], roots
        for info in bundle.infolist():
            assert not info.filename.startswith("/") and ".." not in Path(info.filename).parts
            if info.filename.casefold().endswith((".md", ".txt")):
                relative = info.filename.split("/", 1)[1]
                assert relative not in docs
                docs[relative] = bundle.read(info)
                metadata[relative] = (info.date_time[0], info.date_time[1], info.date_time[2], info.date_time[3], info.date_time[4], info.date_time[5], (info.external_attr >> 16) & 0o777)
        return docs, metadata

with tempfile.TemporaryDirectory(prefix="gaia_rc6_doc_parity_") as temp:
    out = Path(temp)
    project_out = out / "project"
    docs_out = out / "docs"
    project_out.mkdir()
    docs_out.mkdir()
    subprocess.run([sys.executable, str(BUILDER), "--output-dir", str(project_out)], cwd=ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    project_zip = project_out / "GAIA-AI-v1.0-RC6-final.zip"
    subprocess.run([sys.executable, str(DOC_BUILDER), "--project-zip", str(project_zip), "--output-dir", str(docs_out)], cwd=ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    docs_zip = docs_out / "GAIA-AI-v1.0-RC6-docs.zip"
    project_docs, project_meta = docs_from(project_zip, "GAIA-AI-v1.0-RC6")
    docs_docs, docs_meta = docs_from(docs_zip, "GAIA-AI-v1.0-RC6-docs")
    missing = sorted(set(project_docs) - set(docs_docs))
    extra = sorted(set(docs_docs) - set(project_docs))
    mismatch = sorted(name for name in set(project_docs) & set(docs_docs) if digest(project_docs[name]) != digest(docs_docs[name]))
    project_keys = sorted(norm(name) for name in project_docs)
    docs_keys = sorted(norm(name) for name in docs_docs)
    assert not missing, missing
    assert not extra, extra
    assert not mismatch, mismatch
    assert project_keys == docs_keys
    assert all(meta[:6] == (2020, 1, 1, 0, 0, 0) for meta in project_meta.values())
    assert all(meta[:6] == (2020, 1, 1, 0, 0, 0) for meta in docs_meta.values())
    assert all(meta[6] in {0o644, 0o755} for meta in project_meta.values())
    assert all(meta[6] in {0o644, 0o755} for meta in docs_meta.values())
    print(f"project_docs_count={len(project_docs)}")
    print(f"docs_zip_count={len(docs_docs)}")
    print(f"missing={len(missing)}")
    print(f"extra={len(extra)}")
    print(f"content_mismatch={len(mismatch)}")
    print("status=PASS")
