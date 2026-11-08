#!/usr/bin/env python3
"""Build a shareable source snapshot of the ALL MY'ND project.

The archive contains selected source, project documentation, tests, and the
semantic-engine word-vector asset. It deliberately excludes runtime saves,
logs, vessel data, caches, backups, audio, environment files, and other
non-allowlisted content. It does not modify project files or run the mind.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import zipfile
from datetime import datetime, timezone
from typing import Iterable

ROOT_FILES = (
    "README.md",
    "ALLMYND_CHANGELOG.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "STATE_NOTES.md",
    "LICENSE",
    "pyproject.toml",
    "run.py",
    "mind_server.py",
    "quantum_state.py",
    "tools/make_snapshot.py",
)
SOURCE_DIRS = ("allmynd", "semantic_engine", "tests")
REQUIRED_FILES = (
    "run.py",
    "allmynd/mind.py",
    "allmynd/bridge.py",
    "semantic_engine/quantum.py",
)
EXACT_ASSETS = {"semantic_engine/word_vectors.bin.gz"}
ALLOWED_SOURCE_SUFFIXES = {".py"}
EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "vessels",
    "mind_maps",
    "node_modules",
}
EXCLUDED_AUDIO_SUFFIXES = {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".raw"}
SNAPSHOT_PREFIX = "allmynd_source_snapshot_"
MANIFEST_NAME = "SNAPSHOT_MANIFEST.json"


def _is_excluded(rel_path: Path) -> bool:
    parts = rel_path.parts
    name = rel_path.name.lower()
    if any(part.lower() in EXCLUDED_DIRS for part in parts[:-1]):
        return True
    if name == ".env" or name.startswith(".env."):
        return True
    if name in {"allmynd_v1.json", "allmynd_v1.json.emergency", "mind_log.jsonl", "node_id.txt"}:
        return True
    if name.startswith("allmynd_v1.json.") or ".bak" in name:
        return True
    if name.endswith((".pyc", ".pyo", ".log")) or Path(name).suffix in EXCLUDED_AUDIO_SUFFIXES:
        return True
    return False


def _selected_paths(root: Path) -> list[Path]:
    selected: set[Path] = set()

    for rel_text in ROOT_FILES:
        rel = Path(rel_text)
        path = root / rel
        if path.is_file() and not path.is_symlink() and not _is_excluded(rel):
            selected.add(rel)

    for dirname in SOURCE_DIRS:
        base = root / dirname
        if not base.is_dir() or base.is_symlink():
            continue
        for current, dirs, filenames in os.walk(base, followlinks=False):
            current_path = Path(current)
            dirs[:] = sorted(
                d for d in dirs
                if d.lower() not in EXCLUDED_DIRS
                and not (current_path / d).is_symlink()
                and not d.startswith(".")
            )
            for filename in filenames:
                candidate = current_path / filename
                if candidate.is_symlink() or not candidate.is_file():
                    continue
                rel = candidate.relative_to(root)
                if _is_excluded(rel):
                    continue
                if candidate.suffix.lower() in ALLOWED_SOURCE_SUFFIXES or rel.as_posix() in EXACT_ASSETS:
                    selected.add(rel)

    return sorted(selected, key=lambda p: p.as_posix())


def _zip_info(name: str) -> zipfile.ZipInfo:
    """Use fixed metadata so identical inputs produce identical ZIP bytes."""
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def create_snapshot(
    root: str | Path,
    output_dir: str | Path | None = None,
    output_name: str | None = None,
) -> tuple[Path, int]:
    """Create a source ZIP and return its path and number of source files.

    Only explicitly selected project files are included. ``output_name`` must
    be a simple ZIP filename, not a path. If omitted, a UTC timestamp is used.
    Existing destinations are never overwritten.
    """
    project_root = Path(root).expanduser().resolve()
    if not project_root.is_dir():
        raise ValueError(f"project root is not a directory: {project_root}")
    missing = [rel for rel in REQUIRED_FILES if not (project_root / rel).is_file()]
    if missing:
        raise ValueError("not an ALL MY'ND project root; missing: " + ", ".join(missing))

    rel_paths = _selected_paths(project_root)
    selected_names = {p.as_posix() for p in rel_paths}
    missing_after_filter = sorted(set(REQUIRED_FILES) - selected_names)
    if missing_after_filter:
        raise ValueError("required project files were excluded: " + ", ".join(missing_after_filter))

    file_data: list[tuple[str, bytes]] = []
    manifest_items = []
    for rel in rel_paths:
        data = (project_root / rel).read_bytes()
        name = rel.as_posix()
        file_data.append((name, data))
        manifest_items.append({
            "path": name,
            "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        })

    manifest = json.dumps(
        {
            "schema_version": 1,
            "purpose": "shareable ALL MY'ND source snapshot; not a runtime-state backup",
            "files": manifest_items,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    destination_dir = Path(output_dir).expanduser().resolve() if output_dir else project_root
    if output_name is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        output_name = f"{SNAPSHOT_PREFIX}{stamp}.zip"
    if Path(output_name).name != output_name or not output_name.endswith(".zip"):
        raise ValueError("output name must be a plain filename ending in .zip")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", output_name):
        raise ValueError("output name may contain only letters, numbers, dot, underscore, and hyphen")

    destination_dir.mkdir(parents=True, exist_ok=True)
    output_path = destination_dir / output_name
    if output_path.exists():
        raise FileExistsError(f"refusing to overwrite existing snapshot: {output_path}")

    fd: int | None = None
    created = False
    complete = False
    try:
        # O_EXCL prevents overwriting an existing archive, including when two
        # runs happen at once. Use the target directly for compatibility with
        # Android shared storage, which may not support hard links.
        fd = os.open(output_path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o644)
        created = True
        with os.fdopen(fd, "w+b") as stream:
            fd = None
            with zipfile.ZipFile(stream, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
                for name, data in file_data:
                    archive.writestr(_zip_info(name), data)
                archive.writestr(_zip_info(MANIFEST_NAME), manifest)
        complete = True
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if created and not complete and output_path.exists():
            try:
                output_path.unlink()
            except FileNotFoundError:
                pass

    return output_path, len(file_data)


def _default_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=_default_root(), help="ALL MY'ND project root (default: repository containing this tool)")
    parser.add_argument("--output-dir", type=Path, help="where to write the ZIP (default: project root)")
    parser.add_argument("--name", help="optional ZIP filename; existing files are never overwritten")
    args = parser.parse_args(argv)
    try:
        archive_path, count = create_snapshot(args.root, args.output_dir, args.name)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        parser.error(str(exc))
    size_kb = archive_path.stat().st_size / 1024
    print(f"Created {archive_path} ({count} source files, {size_kb:.1f} KiB).")
    print(f"Manifest: {MANIFEST_NAME} (SHA-256 per file)")
    print("Excluded by design: runtime saves, logs, vessels, backups, caches, audio, environment files, and non-allowlisted files.")
    print("Review the archive before sharing; source files may still contain sensitive material.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
