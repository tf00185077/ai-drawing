"""Cross-thread and cross-process serialization for the fixed update request file."""
from __future__ import annotations

import errno
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


REQUEST_FILENAME = "update-request.json"
REQUEST_LOCK_FILENAME = "update-request.lock"
_THREAD_LOCKS: dict[str, threading.Lock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


@contextmanager
def exclusive_request_lock(request_path: Path) -> Iterator[None]:
    """Lock the fixed sibling lock file without depending on replaceable JSON bytes."""
    path = Path(request_path)
    if path.name != REQUEST_FILENAME:
        raise ValueError("update request path is not fixed")
    lock_path = path.with_name(REQUEST_LOCK_FILENAME)
    key = os.path.normcase(str(lock_path.resolve(strict=False)))
    with _THREAD_LOCKS_GUARD:
        thread_lock = _THREAD_LOCKS.setdefault(key, threading.Lock())
    with thread_lock:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a+b") as lock_file:
            if os.fstat(lock_file.fileno()).st_size == 0:
                lock_file.write(b"0")
                lock_file.flush()
            lock_file.seek(0)
            _lock_exclusive(lock_file)
            try:
                yield
            finally:
                lock_file.seek(0)
                _unlock(lock_file)


def _lock_exclusive(lock_file: Any) -> None:
    try:
        import msvcrt
    except ImportError:
        import fcntl

        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
    else:
        while True:
            try:
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                return
            except OSError as error:
                if error.errno != errno.EACCES:
                    raise
                time.sleep(0.05)


def _unlock(lock_file: Any) -> None:
    try:
        import msvcrt
    except ImportError:
        import fcntl

        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    else:
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
