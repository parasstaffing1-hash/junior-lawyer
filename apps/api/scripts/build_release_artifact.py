#!/usr/bin/env python3
"""Build a reproducible Junior Lawyer source release ZIP and SHA-256 manifest.

The builder excludes runtime data, local databases, caches, VCS metadata, node_modules and .env
files so release artifacts do not accidentally package client data or secrets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "apps" / "api") not in sys.path:
    sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.services.release.engine import build_release_manifest, safe_release_filename

EXCLUDED_DIRS = {".git", ".pytest_cache", "__pycache__", "node_modules", ".next", "data", "validation-output", ".venv", "venv"}
EXCLUDED_NAMES = {".env", "junior_lawyer.db", "rc-local-gate.json", "release-source-gate.json", "security-baseline-report.json", "playwright-report.json"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".db", ".sqlite", ".sqlite3"}
FIXED_ZIP_TIME = (2020, 1, 1, 0, 0, 0)


def eligible(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if any(part in EXCLUDED_DIRS for part in relative.parts):
        return False
    if path.name in EXCLUDED_NAMES or path.suffix.casefold() in EXCLUDED_SUFFIXES:
        return False
    if path.name.startswith(".env.") and not path.name.endswith(".example"):
        return False
    return True


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="0.29.0-rc.1")
    parser.add_argument("--build-ref")
    parser.add_argument("--database-revision", default="20260808_0028")
    parser.add_argument("--output-dir", default=str(ROOT.parent))
    args = parser.parse_args()

    output = Path(args.output_dir).resolve(); output.mkdir(parents=True, exist_ok=True)
    basename = safe_release_filename(f"ai-junior-lawyer-{args.version}-source")
    zip_path = output / f"{basename}.zip"
    files = sorted(path for path in ROOT.rglob("*") if path.is_file() and eligible(path))
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            relative = path.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(f"ai-junior-lawyer/{relative}", FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    digest = sha256(zip_path)
    checksum_path = zip_path.with_suffix(zip_path.suffix + ".sha256")
    checksum_path.write_text(f"{digest}  {zip_path.name}\n", encoding="utf-8")
    manifest = build_release_manifest(
        app_version=args.version,
        build_ref=args.build_ref,
        database_revision=args.database_revision,
        artifact_hashes=[{"kind": "source_zip", "filename": zip_path.name, "sha256": digest}],
        gates={"artifact_integrity": True, "production_load_verified": False},
    )
    manifest_path = output / f"{basename}.manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"zip": str(zip_path), "sha256": digest, "files": len(files), "manifest": str(manifest_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
