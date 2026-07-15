"""Persistent SHA-256 digest cache keyed by file identity.

Hashing a multi-GB checkpoint takes tens of seconds; doing it on every
resolution call caused MCP ReadTimeouts. Hash once, remember the file's
(size, mtime_ns, inode) identity, and trust the cached digest while that
identity is unchanged. Any change to the file re-hashes.

The cache is a small JSON sidecar file plus an in-process dict. Corruption
or a missing sidecar silently degrades to an empty cache.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()
_MEMORY: dict[str, dict[str, Any]] = {}
_LOADED_PATH: str | None = None


def _cache_path() -> Path:
    from app.config import get_settings

    return Path(get_settings().file_digest_cache_path)


def _load_locked(cache_file: Path) -> None:
    global _LOADED_PATH
    if _LOADED_PATH == str(cache_file):
        return
    _MEMORY.clear()
    _LOADED_PATH = str(cache_file)
    try:
        payload = json.loads(cache_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if isinstance(payload, dict):
        for key, entry in payload.items():
            if isinstance(entry, dict) and isinstance(entry.get("sha256"), str):
                _MEMORY[key] = entry


def _save_locked(cache_file: Path) -> None:
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = cache_file.with_name(cache_file.name + ".tmp")
        tmp.write_text(json.dumps(_MEMORY, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, cache_file)
    except OSError:
        # A failed save only costs a future re-hash; never fail the caller.
        pass


def _identity(stat: os.stat_result) -> dict[str, int]:
    return {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns, "inode": stat.st_ino}


def _stream_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_for(path: Path | str, *, cache_file: Path | None = None) -> str:
    """Return the file's SHA-256, from cache when its stat identity is unchanged."""
    resolved = Path(path).resolve()
    stat = os.stat(resolved)
    identity = _identity(stat)
    key = str(resolved)
    cache = cache_file or _cache_path()
    with _LOCK:
        _load_locked(cache)
        entry = _MEMORY.get(key)
        if entry is not None and all(entry.get(field) == value for field, value in identity.items()):
            return str(entry["sha256"])
    digest = _stream_sha256(resolved)
    with _LOCK:
        _load_locked(cache)
        _MEMORY[key] = {**identity, "sha256": digest}
        _save_locked(cache)
    return digest


def record_sha256(path: Path | str, sha256: str, *, cache_file: Path | None = None) -> None:
    """Seed the cache with an already-verified digest (e.g. right after a download)."""
    resolved = Path(path).resolve()
    try:
        stat = os.stat(resolved)
    except OSError:
        return
    cache = cache_file or _cache_path()
    with _LOCK:
        _load_locked(cache)
        _MEMORY[str(resolved)] = {**_identity(stat), "sha256": sha256.lower()}
        _save_locked(cache)
