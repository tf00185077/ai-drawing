"""CIV-C safe, resumable, offline-testable Civitai file download boundary."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
import hashlib
import os
from pathlib import Path
import stat
import re
import shutil
import time
from typing import Any, Callable, Mapping, Protocol

from app.services.civitai_acquisition import redact_secrets
from app.services.civitai_provider import CivitaiProviderError, ProviderOperation
from app.services.civitai_download_policy import DownloadPolicy, download_error


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

    publication: dict[str, int] | None = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("publication", None)  # internal ownership, never a public executable lock
        return redact_secrets(value)


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


def _remaining(operation):
    if operation is not None:
        operation.remaining()


def file_identity(info) -> dict[str, int]:
    return {name: getattr(info, 'st_' + name) for name in ('dev', 'ino', 'size', 'mtime_ns', 'ctime_ns')}


def _regular(info):
    return stat.S_ISREG(info.st_mode) and info.st_nlink == 1


def _matches(path, identity, *, single_link=True):
    try:
        info = os.lstat(path)
        return stat.S_ISREG(info.st_mode) and (not single_link or info.st_nlink == 1) and file_identity(info) == identity
    except OSError:
        return False


def remove_owned_publication(path, identity):
    """Compensate only a final whose complete observed identity is still ours."""
    if identity is not None and _matches(path, identity):
        Path(path).unlink()
        return True
    return False


def _space(target, write_bytes, policy, operation):
    _remaining(operation)
    ancestor = target.parent
    while not ancestor.exists() and ancestor != ancestor.parent:
        ancestor = ancestor.parent
    try:
        free = shutil.disk_usage(ancestor).free
        if type(free) is not int or free < 0:
            raise ValueError()
    except Exception:
        raise download_error('civitai_space_unavailable', 'Destination free space could not be observed') from None
    _remaining(operation)
    if free - write_bytes < policy.free_space_floor_bytes:
        raise download_error('civitai_insufficient_space', 'Destination free space would fall below the configured floor')


def _digest(stream, operation):
    digest = hashlib.sha256()
    stream.seek(0)
    while True:
        _remaining(operation)
        chunk = stream.read(1024 * 1024)
        _remaining(operation)
        if not chunk:
            break
        digest.update(chunk)
    return digest


def verified_existing(target, metadata, operation=None):
    """Explicit adoption/reuse, distinct from download publication or a collision."""
    _remaining(operation)
    before = os.lstat(target)
    if not _regular(before):
        raise download_error('civitai_target_exists', 'Destination is not an adoptable regular file')
    fd = os.open(target, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb', buffering=0) as stream:
        identity = file_identity(before)
        if file_identity(os.fstat(stream.fileno())) != identity:
            raise download_error('civitai_file_changed', 'Destination changed during verification')
        actual_sha = _digest(stream, operation).hexdigest()
        if not _matches(target, identity) or file_identity(os.fstat(stream.fileno())) != identity:
            raise download_error('civitai_file_changed', 'Destination changed during verification')
        if before.st_size != metadata.size or actual_sha.lower() != metadata.sha256.lower():
            raise download_error('civitai_target_exists', 'Existing destination does not match the selected file')
        _remaining(operation)
        return before.st_size, actual_sha, identity


def preflight_download(metadata, target, policy, *, association=None, resume=None, operation=None):
    """Read-only admission. A partial proof belongs in the existing resource row.

    Association covers provider/model/version/file/resource + declared SHA/size;
    a full prefix hash and complete stat fingerprint also bind its actual bytes.
    Legacy paths/lengths alone never confer authority.
    """
    target = Path(target)
    policy.validate(metadata.size, metadata.sha256)
    _remaining(operation)
    if os.path.lexists(target):
        raise download_error('civitai_target_exists', 'Destination already exists')
    part = target.with_name(target.name + '.part')
    offset, identity = 0, None
    if os.path.lexists(part):
        info = os.lstat(part)
        if not _regular(info) or info.st_size > min(metadata.size, policy.max_bytes):
            raise download_error('civitai_unsafe_partial', 'Existing partial is linked, nonregular or oversized')
        identity = file_identity(info)
        if (not association or association.get('provider') != 'civitai'
                or any(not str(association.get(key, '')).isdecimal() or int(association[key]) <= 0
                       for key in ('resource_id', 'version_id', 'file_id'))
                or association.get('size') != metadata.size
                or association.get('sha256') != metadata.sha256.lower()
                or not isinstance(resume, dict) or resume.get('association') != association
                or resume.get('identity') != identity):
            raise download_error('civitai_unassociated_partial', 'Existing partial has no matching resource and selected-file association')
        fd = os.open(part, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
        with os.fdopen(fd, 'rb', buffering=0) as source:
            if file_identity(os.fstat(source.fileno())) != identity:
                raise download_error('civitai_file_changed', 'Partial changed before verification')
            digest = _digest(source, operation).hexdigest()
            if (not _matches(part, identity) or file_identity(os.fstat(source.fileno())) != identity
                    or digest != resume.get('prefix_sha256')):
                raise download_error('civitai_file_changed', 'Partial bytes or ownership changed')
        offset = info.st_size
    _space(target, metadata.size - offset, policy, operation)
    return offset, identity


def _base_diagnostics(metadata):
    return redact_secrets({'availability': metadata.availability, 'scan_status': metadata.scan_status,
                           'license': metadata.license, 'usage': metadata.usage})


def safe_download(metadata, target_path, *, transport, authorization=None, backoff=None,
                  sleep=time.sleep, operation=None, policy=None, association=None, resume=None,
                  record_partial=None):
    """Bound writes and publish with atomic link-if-absent on the same filesystem.

    Only the descriptor opened with exclusive creation (or verified row proof)
    is writable. Deterministic disk/policy/range/verification failures never retry.
    """
    target = Path(target_path)
    part = target.with_name(target.name + '.part')
    secrets = tuple(v for v in (authorization, *(authorization or '').split()) if v)
    total, used, stream, identity, created = 0, False, None, None, False
    owned_digest = hashlib.sha256(b"").hexdigest()
    diagnostics = _base_diagnostics(metadata)

    def failed(error):
        nonlocal identity
        # Preexisting/foreign/changed partials survive. Only this exclusive
        # creation is eligible for cleanup, after closing and rechecking it.
        cleanup = created and identity is not None and _matches(part, identity)
        if cleanup and stream is not None and not stream.closed:
            try:
                cleanup = _digest(stream, operation).hexdigest() == owned_digest and _matches(part, identity)
            except (OSError, CivitaiProviderError):
                cleanup = False
        if stream is not None:
            stream.close()
        if cleanup and _matches(part, identity):
            part.unlink()
        return DownloadResult('failed', str(target), None, total, used,
                              redact_secrets({**diagnostics, 'reason': error.message, **error.to_dict()}, secrets=secrets))

    def check_owned():
        _remaining(operation)
        info = os.fstat(stream.fileno())
        if not _regular(info) or file_identity(info) != identity or not _matches(part, identity):
            raise download_error('civitai_file_changed', 'Partial ownership or contents changed')

    def _write_response(response, metadata, target, part, offset, initial_identity, attempt):
        nonlocal total, used, stream, identity, created, owned_digest
        used = response.status_code == 206 and offset > 0
        start = offset if response.status_code == 206 else 0
        headers = {str(k).lower(): str(v) for k, v in response.headers.items()}
        if response.status_code == 206:
            match = re.fullmatch(r"bytes ([0-9]+)-([0-9]+)/([0-9]+)", headers.get('content-range', ''))
            if (match is None or tuple(map(int, match.groups())) != (offset, metadata.size - 1, metadata.size)
                    or offset >= metadata.size):
                raise download_error('civitai_invalid_range', 'Response Content-Range does not cover the selected remaining bytes')
        length = headers.get('content-length')
        if length is not None and (not re.fullmatch(r'[0-9]+', length) or int(length) != metadata.size - start):
            raise download_error('civitai_invalid_range', 'Response Content-Length contradicts selected coverage')
        chunks = (response.body,) if isinstance(response.body, bytes) else iter(response.body)
        try:
            _remaining(operation)
            if initial_identity is None:
                fd = os.open(part, os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
                created = True
            else:
                if not _matches(part, initial_identity):
                    raise download_error('civitai_file_changed', 'Associated partial changed before open')
                fd = os.open(part, os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
            stream = os.fdopen(fd, 'r+b', buffering=0)
            opened = file_identity(os.fstat(stream.fileno()))
            if initial_identity is not None and opened != initial_identity:
                raise download_error('civitai_file_changed', 'Associated partial changed during open')
            identity = opened
            check_owned()
            if response.status_code == 200 and offset:
                # The old prefix is still owned; admit a full restart before truncate.
                _space(target, metadata.size, policy, operation)
                check_owned()
                stream.truncate(0)
                identity = file_identity(os.fstat(stream.fileno()))
                total = 0
            digest = _digest(stream, operation)
            owned_digest = digest.hexdigest()
            check_owned()
            stream.seek(0, os.SEEK_END)

            def record():
                if record_partial is not None and association:
                    check_owned()
                    record_partial({'association': association, 'identity': identity, 'prefix_sha256': digest.hexdigest()})
                    _remaining(operation)

            record()
            for chunk in chunks:
                check_owned()
                if not isinstance(chunk, bytes):
                    raise download_error('civitai_invalid_body', 'Download chunks must be bytes')
                if total + len(chunk) > min(metadata.size, policy.max_bytes):
                    raise download_error('civitai_byte_limit_exceeded', 'Stream exceeds selected size or per-file cap')
                _space(target, len(chunk), policy, operation)
                check_owned()
                if stream.write(chunk) != len(chunk):
                    raise download_error('civitai_download_failed', 'Partial write did not complete')
                total += len(chunk)
                digest.update(chunk)
                owned_digest = digest.hexdigest()
                now = os.fstat(stream.fileno())
                if not _regular(now) or now.st_size != total:
                    raise download_error('civitai_file_changed', 'Partial changed during write')
                identity = file_identity(now)
                check_owned()
                record()
            check_owned()
            os.fsync(stream.fileno())
            _remaining(operation)
            actual_sha = _digest(stream, operation).hexdigest()
            check_owned()
            if total != metadata.size or actual_sha.lower() != metadata.sha256.lower():
                raise download_error('civitai_verification_failed', 'size or sha256 verification failed')
            _remaining(operation)
            try:
                # Same-filesystem hard-link creation is atomic and NEVER replaces.
                os.link(part, target, follow_symlinks=False)
            except FileExistsError:
                raise download_error('civitai_target_exists', 'Destination appeared before publication') from None
            published = os.lstat(target)
            current = os.fstat(stream.fileno())
            if ((published.st_dev, published.st_ino) != (current.st_dev, current.st_ino)
                    or not stat.S_ISREG(published.st_mode) or current.st_size != total
                    or file_identity(published) != file_identity(current)):
                raise download_error('civitai_file_changed', 'Publication ownership changed')
            # Linking changes ctime/nlink. Rebind only after proving both names.
            identity = file_identity(current)
            if not _matches(part, identity, single_link=False):
                raise download_error('civitai_file_changed', 'Partial changed during publication')
            _remaining(operation)
            # Some filesystems refuse deleting a name with an open writer.
            # Carry the verified identity across close and recheck both names.
            stream.close()
            if not _matches(part, identity, single_link=False) or not _matches(target, identity, single_link=False):
                raise download_error('civitai_file_changed', 'Publication changed while closing the writer')
            part.unlink()
            identity = None
            published = os.lstat(target)
            if (published.st_dev, published.st_ino, published.st_size, published.st_mtime_ns) != (
                    current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns):
                raise download_error('civitai_file_changed', 'Final changed while removing the owned partial')
            publication = file_identity(published)
            if not _matches(target, publication):
                raise download_error('civitai_file_changed', 'Final changed after publication')
            try:
                _remaining(operation)
            except CivitaiProviderError:
                remove_owned_publication(target, publication)
                raise
            from app.services.file_digest_cache import record_sha256
            record_sha256(target, actual_sha)
            return DownloadResult('completed', str(target), actual_sha, total, used,
                                  redact_secrets({**diagnostics, 'attempt': attempt}, secrets=secrets), publication)
        except OSError:
            raise download_error('civitai_download_failed', 'Download filesystem operation failed; existing data is retained') from None
        finally:
            close = getattr(chunks, 'close', None)
            if callable(close):
                close()

    try:
        policy = policy if policy is not None else DownloadPolicy.from_settings()
        policy.validate(metadata.size, metadata.sha256)
        if not metadata.availability or (metadata.scan_status or '').strip().lower() not in _ALLOWED_SCAN_STATUSES:
            return DownloadResult('blocked', str(target), None, 0, False, redact_secrets(diagnostics, secrets=secrets))
        offset, identity = preflight_download(metadata, target, policy, association=association, resume=resume, operation=operation)
        total = offset
        # No directory/partial/body side effect precedes all admission gates.
        _remaining(operation)
        target.parent.mkdir(parents=True, exist_ok=True)
        headers = {'Authorization': authorization} if authorization else {}
        if offset:
            headers['Range'] = f'bytes={offset}-'
        for attempt in range(1, 4):
            response = None
            retryable = False
            try:
                _remaining(operation)
                response = _response(transport.get(metadata.download_url, headers=headers))
                _remaining(operation)
                if response.status_code not in {200, 206}:
                    retryable = response.status_code == 429 or 500 <= response.status_code <= 599
                    error = download_error('unauthorized' if response.status_code in {401, 403} else 'civitai_api_error', f'HTTP status {response.status_code}')
                else:
                    return _write_response(response, metadata, target, part, offset, identity, attempt)
            except CivitaiProviderError as exc:
                error = exc
                retryable = exc.code == 'civitai_network_error' and stream is None
            except OSError:
                error = download_error('civitai_network_error', 'Civitai network request failed')
                retryable = stream is None
            finally:
                if response is not None:
                    response.close()
            if not retryable or attempt == 3:
                return failed(error)
            delay = max(float(backoff(attempt, response) if backoff else 0) or 0, 0)
            if operation is not None:
                operation.pause(delay, sleep)
            elif delay:
                sleep(delay)
    except CivitaiProviderError as exc:
        return failed(exc)
    except (OSError, ValueError, TypeError):
        return failed(download_error('civitai_download_failed', 'Civitai download filesystem or stream failed'))
    finally:
        if stream is not None:
            stream.close()
