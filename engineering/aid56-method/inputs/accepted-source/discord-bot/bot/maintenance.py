"""Process-local, linearizable admission. This cannot certify a legacy process."""
from __future__ import annotations

import asyncio
from collections import Counter
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import inspect
import threading
import time


class MaintenanceClosed(Exception):
    """No response is sent on rejection: replies are external effects too."""


_permits: ContextVar[tuple] = ContextVar('maintenance_permits', default=())


class Admission:
    def __init__(self, *, owner: str, epoch: str, version: str, closed: bool = False):
        self.owner, self.epoch, self.version = owner, epoch, version
        self._closed = closed
        self._active = Counter()
        self._uncertain = Counter()
        self._lock = threading.RLock()
        self._tokens = set()

    @contextmanager
    def enter(self, kind: str):
        with self._lock:
            # A copied context alone is not a permit once its original scope exits.
            nested = any(g is self and t in self._tokens for g, t in _permits.get())
            if self._closed and not nested:
                raise MaintenanceClosed('maintenance admission is closed')
            token = object()
            self._tokens.add(token)
            self._active[kind] += 1
        context = _permits.set((*_permits.get(), (self, token)))
        try:
            yield
        except MaintenanceClosed:
            raise
        except BaseException:
            self.hold(kind)
            raise
        finally:
            _permits.reset(context)
            with self._lock:
                self._tokens.remove(token)
                self._active[kind] -= 1
                if not self._active[kind]: del self._active[kind]

    def hold(self, kind: str):
        with self._lock:
            self._closed = True
            self._uncertain[kind] += 1

    def set_hold(self, kind: str, count: int):
        with self._lock:
            self._closed = True
            self._uncertain[kind] = max(self._uncertain[kind], count)

    def close(self):
        with self._lock:
            self._closed = True
        return self.status()

    def status(self):
        with self._lock:
            state = ('uncertain_closed' if self._uncertain else
                     'draining' if self._closed and self._active else
                     'closed' if self._closed else 'open')
            return {'schema_version': 1, 'owner': self.owner, 'epoch': self.epoch,
                    'version': self.version, 'state': state,
                    'active': dict(self._active), 'uncertain': dict(self._uncertain),
                    'legacy_process_certified': False}

    async def drain(self, timeout: float):
        self.close()
        deadline = time.monotonic() + max(0, timeout)
        while self.status()['active'] and time.monotonic() < deadline:
            await asyncio.sleep(min(0.01, max(0, deadline-time.monotonic())))
        return self.status()


def guarded(kind, *, resolve=None, reject=False):
    """Register the complete callback before its first await, including replies."""
    def decorate(fn):
        @wraps(fn)
        async def wrapped(*args, **kwargs):
            admission = resolve(*args, **kwargs) if resolve else getattr(args[0], 'admission', None)
            if not isinstance(admission, Admission):
                return await fn(*args, **kwargs)
            try:
                with admission.enter(kind):
                    return await fn(*args, **kwargs)
            except MaintenanceClosed:
                if reject:raise
                return None
        wrapped.__signature__ = inspect.signature(fn,eval_str=True)
        return wrapped
    return decorate
