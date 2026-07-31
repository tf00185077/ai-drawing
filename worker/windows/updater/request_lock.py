"""Cross-thread and cross-process serialization for the fixed update request file."""
from __future__ import annotations

import errno
import math
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator


REQUEST_FILENAME = "update-request.json"
REQUEST_LOCK_FILENAME = "update-request.lock"
DEFAULT_REQUEST_LOCK_TIMEOUT = 15.0
LOCK_RETRY_INTERVAL = 0.05
_THREAD_LOCKS: dict[str, threading.Lock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


class RequestLockError(RuntimeError):
    """The fixed request lock could not be safely used."""


class RequestLockTimeout(RequestLockError, TimeoutError):
    """The fixed request lock remained contended until its deadline."""

    def __init__(self) -> None:
        super().__init__("update request lock timed out")


@contextmanager
def exclusive_request_lock(
    request_path: Path,
    *,
    timeout: float = DEFAULT_REQUEST_LOCK_TIMEOUT,
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> Iterator[None]:
    """Lock the fixed sibling lock file without depending on replaceable JSON bytes."""
    path = Path(request_path)
    if path.name != REQUEST_FILENAME:
        raise ValueError("update request path is not fixed")
    if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("update request lock timeout is invalid")
    deadline = clock() + float(timeout)
    lock_path = path.with_name(REQUEST_LOCK_FILENAME)
    key = os.path.normcase(str(lock_path.resolve(strict=False)))
    with _THREAD_LOCKS_GUARD:
        thread_lock = _THREAD_LOCKS.setdefault(key, threading.Lock())
    while not thread_lock.acquire(blocking=False):
        _wait_for_retry(deadline, clock, sleeper)
    try:
        lock_file = None
        os_locked = False
        body_error: BaseException | None = None
        try:
            try:
                _require_before_deadline(deadline, clock)
                lock_path.parent.mkdir(parents=True, exist_ok=True)
                lock_file = lock_path.open("a+b")
                if os.fstat(lock_file.fileno()).st_size == 0:
                    lock_file.write(b"0")
                    lock_file.flush()
                lock_file.seek(0)
                _lock_exclusive(lock_file, deadline, clock, sleeper)
                os_locked = True
                _require_before_deadline(deadline, clock)
            except RequestLockError:
                raise
            except OSError:
                raise RequestLockError("update request lock is unavailable") from None
            try:
                yield
            except BaseException as error:
                body_error = error
                raise
        finally:
            if lock_file is not None:
                release_error: RequestLockError | None = None
                try:
                    if os_locked:
                        try:
                            lock_file.seek(0)
                            _unlock(lock_file)
                        except OSError:
                            release_error = RequestLockError(
                                "update request lock is unavailable"
                            )
                finally:
                    try:
                        lock_file.close()
                    except OSError:
                        if release_error is None:
                            release_error = RequestLockError(
                                "update request lock is unavailable"
                            )
                if release_error is not None:
                    if body_error is None:
                        raise release_error from None
                    body_error.add_note("update request lock release failed")
    finally:
        thread_lock.release()


def _require_before_deadline(
    deadline: float, clock: Callable[[], float]
) -> None:
    if deadline - clock() <= 0:
        raise RequestLockTimeout() from None


def _wait_for_retry(
    deadline: float,
    clock: Callable[[], float],
    sleeper: Callable[[float], None],
) -> None:
    remaining = deadline - clock()
    if remaining <= 0:
        raise RequestLockTimeout() from None
    sleeper(min(LOCK_RETRY_INTERVAL, remaining))


def _lock_exclusive(
    lock_file: Any,
    deadline: float,
    clock: Callable[[], float],
    sleeper: Callable[[float], None],
) -> None:
    try:
        import msvcrt
    except ImportError:
        import fcntl

        while True:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            except OSError as error:
                if error.errno not in {errno.EACCES, errno.EAGAIN}:
                    raise
                _wait_for_retry(deadline, clock, sleeper)
    else:
        while True:
            try:
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                return
            except OSError as error:
                if error.errno != errno.EACCES:
                    raise
                _wait_for_retry(deadline, clock, sleeper)


def _unlock(lock_file: Any) -> None:
    try:
        import msvcrt
    except ImportError:
        import fcntl

        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    else:
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
