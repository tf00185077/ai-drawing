"""CIV-C safe, resumable, offline-testable Civitai file download boundary."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
import hashlib
import os
from pathlib import Path
import stat
import time
from typing import Any, Callable, Mapping, Protocol

from app.services.civitai_acquisition import redact_secrets
from app.services.civitai_provider import CivitaiProviderError, ProviderOperation


_ALLOWED_SCAN_STATUSES = frozenset({"passed", "success", "clean"})


class DownloadTransport(Protocol):
    def get(self, url: str, *, headers: dict[str, str] | None = None) -> Any:
        ...


@dataclass(frozen=True)
class DownloadResponse:
    status_code: int
    body: bytes | Iterable[bytes]
    headers: Mapping[str, str] = field(default_factory=dict)

    def close(self) -> None:
        close = getattr(self.body, 'close', None)
        if callable(close):
            close()


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
    reason: str, secret_values: tuple[str, ...], error: CivitaiProviderError | None = None,
) -> DownloadResult:
    part = target.with_name(target.name + ".part")
    # Invalid contents are never useful resume material; preserve an old final untouched.
    if part.exists():
        part.unlink()
    return DownloadResult(
        status="failed", final_path=str(target), actual_sha256=None, bytes=bytes_written,
        resume_used=resume_used,
        diagnostics=redact_secrets({**_base_diagnostics(metadata), "reason": reason, **(error.to_dict() if error else {})}, secrets=secret_values),
    )


def safe_download(
    metadata: CivitaiFileMetadata,
    target_path: Path | str,
    *,
    transport: DownloadTransport,
    authorization: str | None = None,
    backoff: Callable[[int, DownloadResponse | None], float | int | None] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    operation: ProviderOperation | None = None,
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
        response = None
        try:
            return_value = _download_attempt(metadata, target, part, transport, headers, initial_offset, attempt, diagnostics, secret_values, operation)
            response, outcome = return_value
            if outcome is not None:
                return outcome
            last_reason = f"HTTP status {response.status_code}"
            retryable = response.status_code == 429 or 500 <= response.status_code <= 599
        except CivitaiProviderError as exc:
            if exc.code != 'civitai_network_error':
                return _failure(target, metadata, resume_used=resume_used, bytes_written=part.stat().st_size if part.exists() else 0,
                                reason=exc.message, secret_values=secret_values, error=exc)
            last_reason, retryable = exc.message, True
        except Exception:
            last_reason = "Civitai network request failed"
            retryable = True
        finally:
            if response is not None:
                response.close()
        if not retryable or attempt == 3:
            bytes_written = part.stat().st_size if part.exists() else 0
            code = 'unauthorized' if response is not None and response.status_code in (401, 403) else ('civitai_api_error' if response is not None else 'civitai_network_error')
            return _failure(target, metadata, resume_used=resume_used, bytes_written=bytes_written,
                            reason=last_reason, secret_values=secret_values,
                            error=CivitaiProviderError(code, last_reason, 'Check provider access/availability and inspect this acquisition ID before retrying.'))
        delay = max(float(backoff(attempt, response) if backoff else 0) or 0, 0)
        try:
            if operation is not None:
                operation.pause(delay, sleep)
            elif delay:
                sleep(delay)
        except CivitaiProviderError as exc:
            return _failure(target, metadata, resume_used=resume_used, bytes_written=part.stat().st_size if part.exists() else 0,
                            reason=exc.message, secret_values=secret_values, error=exc)
    raise AssertionError("unreachable retry loop exit")


def _download_attempt(metadata, target, part, transport, headers, initial_offset, attempt, diagnostics, secret_values, operation):
    if operation is not None:
        operation.remaining()
    response = _response(transport.get(metadata.download_url, headers=headers))
    resume_used = False
    try:
        if 200 <= response.status_code < 300 and (
            isinstance(response.body, bytes) or isinstance(response.body, Iterable)
        ):
            if response.status_code == 206 and initial_offset:
                mode = "ab"
                resume_used = True
            elif response.status_code == 200:
                mode = "wb"
                resume_used = False
            else:
                return response, _failure(target, metadata, resume_used=resume_used, bytes_written=0,
                                reason=f"unexpected successful status {response.status_code}", secret_values=secret_values)
            chunks = (response.body,) if isinstance(response.body, bytes) else iter(response.body)
            try:
                with part.open(mode) as stream:
                    for chunk in chunks:
                        if not isinstance(chunk, bytes):
                            raise TypeError("download stream chunks must be bytes")
                        stream.write(chunk)
            except CivitaiProviderError as exc:
                return response, _failure(target, metadata, resume_used=resume_used,
                                         bytes_written=part.stat().st_size if part.exists() else 0,
                                         reason=exc.message, secret_values=secret_values, error=exc)
            except Exception as exc:
                return response, _failure(
                    target,
                    metadata,
                    resume_used=resume_used,
                    bytes_written=part.stat().st_size if part.exists() else 0,
                    reason=f"streaming download failed: {exc.__class__.__name__}",
                    secret_values=secret_values,
                )
            finally:
                close = getattr(chunks, "close", None)
                if callable(close):
                    close()
            actual_bytes = part.stat().st_size
            actual_sha = _file_digest(part)
            if actual_bytes != metadata.size or actual_sha.lower() != metadata.sha256.lower():
                return response, _failure(target, metadata, resume_used=resume_used, bytes_written=actual_bytes,
                                reason="size or sha256 verification failed", secret_values=secret_values)
            os.replace(part, target)
            from app.services.file_digest_cache import record_sha256

            record_sha256(target, actual_sha)
            return response, DownloadResult(
                status="completed", final_path=str(target), actual_sha256=actual_sha,
                bytes=actual_bytes, resume_used=resume_used,
                diagnostics=redact_secrets({**diagnostics, "attempt": attempt}, secrets=secret_values),
            )
        return response, None
    finally:
        response.close()
