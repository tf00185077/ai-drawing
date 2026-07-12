"""CIV-C safe, resumable, offline-testable Civitai file download boundary."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import os
from pathlib import Path
import stat
import time
from typing import Any, Callable, Mapping, Protocol

from app.services.civitai_acquisition import redact_secrets


_ALLOWED_SCAN_STATUSES = frozenset({"passed", "success", "clean"})


class DownloadTransport(Protocol):
    def get(self, url: str, *, headers: dict[str, str] | None = None) -> Any:
        ...


@dataclass(frozen=True)
class DownloadResponse:
    status_code: int
    body: bytes
    headers: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CivitaiFileMetadata:
    download_url: str
    sha256: str
    size: int
    availability: bool = True
    scan_status: str | None = None
    license: Any = None
    usage: Any = None


@dataclass
class DownloadResult:
    status: str
    final_path: str
    actual_sha256: str | None
    bytes: int
    resume_used: bool
    diagnostics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return redact_secrets(asdict(self))


def _response(value: Any) -> DownloadResponse:
    if isinstance(value, DownloadResponse):
        return value
    if isinstance(value, tuple) and len(value) in {2, 3}:
        status, body, *headers = value
        return DownloadResponse(int(status), body, headers[0] if headers else {})
    status = getattr(value, "status_code", getattr(value, "status", None))
    if status is not None:
        body = getattr(value, "body", getattr(value, "content", None))
        return DownloadResponse(int(status), body, getattr(value, "headers", {}) or {})
    raise TypeError("download transport must return a response-like value")


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _base_diagnostics(metadata: CivitaiFileMetadata) -> dict[str, Any]:
    return redact_secrets({
        "availability": metadata.availability,
        "scan_status": metadata.scan_status,
        "license": metadata.license,
        "usage": metadata.usage,
    })


def _failure(
    target: Path, metadata: CivitaiFileMetadata, *, resume_used: bool, bytes_written: int,
    reason: str, secret_values: tuple[str, ...],
) -> DownloadResult:
    part = target.with_name(target.name + ".part")
    # Invalid contents are never useful resume material; preserve an old final untouched.
    if part.exists():
        part.unlink()
    return DownloadResult(
        status="failed", final_path=str(target), actual_sha256=None, bytes=bytes_written,
        resume_used=resume_used,
        diagnostics=redact_secrets({**_base_diagnostics(metadata), "reason": reason}, secrets=secret_values),
    )


def safe_download(
    metadata: CivitaiFileMetadata,
    target_path: Path | str,
    *,
    transport: DownloadTransport,
    authorization: str | None = None,
    backoff: Callable[[int, DownloadResponse | None], float | int | None] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> DownloadResult:
    """Download with a same-directory .part file and verified atomic publication."""
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    secret_values = tuple(value for value in (authorization, *(authorization or "").split()) if value)
    diagnostics = _base_diagnostics(metadata)
    normalized_scan = (metadata.scan_status or "").strip().lower()
    if not metadata.availability or normalized_scan not in _ALLOWED_SCAN_STATUSES:
        return DownloadResult(
            status="blocked", final_path=str(target), actual_sha256=None, bytes=0, resume_used=False,
            diagnostics=redact_secrets(diagnostics, secrets=secret_values),
        )

    part = target.with_name(target.name + ".part")
    if part.is_symlink():
        return _failure(target, metadata, resume_used=False, bytes_written=0,
                        reason="unsafe symbolic-link part file", secret_values=secret_values)
    if part.exists():
        part_stat = os.lstat(part)
        if not stat.S_ISREG(part_stat.st_mode) or part_stat.st_nlink != 1:
            return _failure(target, metadata, resume_used=False, bytes_written=0,
                            reason="unsafe non-regular part file", secret_values=secret_values)
    initial_offset = part.stat().st_size if part.exists() else 0
    headers = {"Authorization": authorization} if authorization else {}
    if initial_offset:
        headers["Range"] = f"bytes={initial_offset}-"
    last_reason = "download failed"
    resume_used = False
    for attempt in range(1, 4):
        try:
            response = _response(transport.get(metadata.download_url, headers=headers))
        except Exception as exc:
            last_reason = str(exc)
            response = None
        if response is not None:
            if 200 <= response.status_code < 300 and isinstance(response.body, bytes):
                if response.status_code == 206 and initial_offset:
                    mode = "ab"
                    resume_used = True
                elif response.status_code == 200:
                    mode = "wb"
                    resume_used = False
                else:
                    return _failure(target, metadata, resume_used=resume_used, bytes_written=0,
                                    reason=f"unexpected successful status {response.status_code}", secret_values=secret_values)
                with part.open(mode) as stream:
                    stream.write(response.body)
                actual_bytes = part.stat().st_size
                actual_sha = _file_digest(part)
                if actual_bytes != metadata.size or actual_sha.lower() != metadata.sha256.lower():
                    return _failure(target, metadata, resume_used=resume_used, bytes_written=actual_bytes,
                                    reason="size or sha256 verification failed", secret_values=secret_values)
                os.replace(part, target)
                return DownloadResult(
                    status="completed", final_path=str(target), actual_sha256=actual_sha,
                    bytes=actual_bytes, resume_used=resume_used,
                    diagnostics=redact_secrets({**diagnostics, "attempt": attempt}, secrets=secret_values),
                )
            last_reason = f"HTTP status {response.status_code}"
            retryable = response.status_code == 429 or 500 <= response.status_code <= 599
        else:
            retryable = True
        if not retryable or attempt == 3:
            bytes_written = part.stat().st_size if part.exists() else 0
            return _failure(target, metadata, resume_used=resume_used, bytes_written=bytes_written,
                            reason=last_reason, secret_values=secret_values)
        delay = max(float(backoff(attempt, response) if backoff else 0) or 0, 0)
        if delay:
            sleep(delay)
    raise AssertionError("unreachable retry loop exit")
