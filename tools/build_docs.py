"""Build the RC6 documentation ZIP as an exact projection of the project ZIP."""
from __future__ import annotations

import argparse
import hashlib
import posixpath
from pathlib import Path
import unicodedata
import zipfile

DOCS_PACKAGE = "GAIA-AI-v1.0-RC6-docs"
PROJECT_PACKAGE = "GAIA-AI-v1.0-RC6"
FIXED_ZIP_TIME = (2020, 1, 1, 0, 0, 0)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized(name: str) -> str:
    return unicodedata.normalize("NFC", posixpath.normpath(name)).casefold()


def project_documents(project_zip: Path) -> list[tuple[str, bytes, int]]:
    with zipfile.ZipFile(project_zip) as bundle:
        names = bundle.namelist()
        if bundle.testzip() is not None:
            raise RuntimeError("El ZIP de proyecto no supera la prueba de integridad.")
        roots = sorted({name.split("/", 1)[0] for name in names if "/" in name})
        if roots != [PROJECT_PACKAGE]:
            raise RuntimeError(f"Raíz de proyecto inesperada: {roots}")
        unsafe = [name for name in names if name.startswith("/") or ".." in Path(name).parts or "" in Path(name).parts]
        if unsafe:
            raise RuntimeError(f"Rutas inseguras en el proyecto: {unsafe}")
        selected: list[tuple[str, bytes, int]] = []
        for info in bundle.infolist():
            relative = info.filename.split("/", 1)[1] if "/" in info.filename else ""
            if relative.casefold().endswith((".md", ".txt")):
                if relative.endswith("/"):
                    raise RuntimeError(f"Documento directorio inesperado: {relative}")
                mode = (info.external_attr >> 16) & 0o777 or 0o644
                selected.append((relative, bundle.read(info), mode))
        if len({name for name, _, _ in selected}) != len(selected):
            raise RuntimeError("Documentos duplicados en el ZIP de proyecto.")
        keys = [normalized(name) for name, _, _ in selected]
        if len(set(keys)) != len(keys):
            raise RuntimeError("Documentos duplicados tras Unicode normalization/case-fold.")
        return sorted(selected, key=lambda row: row[0])


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the exact RC6 documentation projection")
    parser.add_argument("--project-zip", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    project_zip = args.project_zip.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_zip = output_dir / f"{DOCS_PACKAGE}.zip"
    sidecar = output_zip.with_suffix(output_zip.suffix + ".sha256")
    documents = project_documents(project_zip)
    members = [f"{DOCS_PACKAGE}/{name}" for name, _, _ in documents]
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for (relative, data, mode), member in zip(documents, members):
            info = zipfile.ZipInfo(member, FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = ((0o755 if mode & 0o111 else 0o644) & 0xFFFF) << 16
            bundle.writestr(info, data)
    with zipfile.ZipFile(output_zip) as bundle:
        names = bundle.namelist()
        if names != members:
            raise RuntimeError("Orden o miembros documentalmente no deterministas.")
        if bundle.testzip() is not None:
            raise RuntimeError("El ZIP documental no supera la prueba de integridad.")
        normalized_names = [normalized(name) for name in names]
        if len(normalized_names) != len(set(normalized_names)):
            raise RuntimeError("Duplicado documental normalizado.")
        if any(name.startswith("/") or ".." in Path(name).parts or "" in Path(name).parts for name in names):
            raise RuntimeError("Zip Slip en ZIP documental.")
        if any(name.casefold().endswith((".db", ".sqlite", ".log", ".pyc", ".pyo", ".zip")) for name in names):
            raise RuntimeError("Artefacto prohibido en ZIP documental.")
    digest = sha256(output_zip)
    sidecar.write_text(f"{digest}  {output_zip.name}\n", encoding="utf-8")
    print(f"project_docs_count={len(documents)}")
    print("missing=0")
    print("extra=0")
    print("content_mismatch=0")
    print("status=PASS")
    print(f"zip={output_zip}")
    print(f"sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
