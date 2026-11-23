"""Isolated scratch payload writer, not an installed backup or B executor.

Caller supplies a complete finite logical plan and exclusive cold synthetic
inputs. No crash resume, physical quota, metadata restore or source/start release.
All failed attempts retain their full precharge and every remaining reservation.
"""
import hashlib
import os
from pathlib import Path
import re
import stat
import threading

CAP = 128849018880
CHUNK = 65536
ERROR_BYTES = 256
CODES = {"bounded_bytes_required", "destination_drift", "limit", "short_write",
         "hash", "source_manifest", "source_drift", "invalid_name",
         "unknown_or_used_slot", "reserved_error_slot", "parent_drift",
         "root_drift", "regular_single_link_required", "input_error", "os_error"}
COMMITS = {"not_attempted", "known_not_committed", "known_committed", "unknown"}

class Refused(ValueError):
    pass

def _integer(value):
    if type(value) is not int or value < 0:
        raise Refused("unavailable_or_invalid_integer")
    return value

def _name(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]{0,63}", value):
        raise Refused("invalid_name")
    return value

def _directory(path):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise Refused("absolute_nofollow_parent_required")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise

def _pin(st):
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
        raise Refused("regular_single_link_required")
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns,
            st.st_ctime_ns, stat.S_IMODE(st.st_mode), st.st_nlink)

def identity(path):
    """Non-following identity only; never proof of cold closure or provenance."""
    path = Path(path)
    fd = _directory(path.parent)
    try:
        return _pin(os.stat(_name(path.name), dir_fd=fd, follow_symlinks=False))
    finally:
        os.close(fd)

def check_pools(demands, available):
    """Pure finite-envelope comparison; pool mapping/fresh F are caller inputs."""
    totals = {}
    for pool, amount in demands:
        _name(pool)
        if pool not in available:
            raise Refused("unknown_pool")
        totals[pool] = totals.get(pool, 0) + _integer(amount)
    result = {}
    for pool, amount in totals.items():
        free = _integer(available[pool])
        threshold = (6 * amount + 4) // 5
        result[pool] = dict(remaining=amount, threshold=threshold, free=free, fits=free >= threshold)
    return result

class ScratchWriter:
    """One fresh direct-child root, one immutable plan, one serial writer.

    Source files must be direct children of the supplied test-owned parent.
    Root and file descriptors are anchored and checked before every write.
    This is cooperative control, not OS confinement against other writers.
    """
    def __init__(self, parent, name, limits, cap=CAP):
        _name(name)
        if not isinstance(limits, dict) or not limits:
            raise Refused("complete_plan_required")
        self._limits = {_name(k): _integer(v) for k, v in limits.items()}
        if self._limits.get("error", 0) != ERROR_BYTES:
            raise Refused("fixed_error_reservation_required")
        if _integer(cap) > CAP or sum(self._limits.values()) > cap:
            raise Refused("aggregate_limit")
        self.parent = Path(parent)
        self.root = self.parent / name
        self._name = name
        self._charged = {k: 0 for k in self._limits}
        self._used = set()
        self._lock = threading.Lock()
        self._stopped = False
        self._receipt = None
        self._parent_fd = _directory(self.parent)
        self._root_fd = None
        try:
            os.mkdir(name, mode=0o700, dir_fd=self._parent_fd)
            self._root_fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=self._parent_fd)
            self._root_id = os.fstat(self._root_fd)
            self._parent_id = os.fstat(self._parent_fd)
            if stat.S_IMODE(self._root_id.st_mode) != 0o700:
                raise Refused("private_root_mode")
        except BaseException:
            self.close()
            raise

    def close(self):
        self._stopped = True
        for attr in ("_root_fd", "_parent_fd"):
            fd = getattr(self, attr, None)
            if fd is not None:
                os.close(fd)
                setattr(self, attr, None)

    def snapshot(self):
        total = sum(self._limits.values())
        charged = sum(self._charged.values())
        return dict(plan_total=total, charged=charged, reserved_remaining=total-charged,
                    slots={k: dict(charged=self._charged[k], remaining=v-self._charged[k])
                           for k, v in self._limits.items()})

    def _roots(self):
        check = _directory(self.parent)
        try:
            parent = os.fstat(check)
            root = os.stat(self._name, dir_fd=self._parent_fd, follow_symlinks=False)
            if (parent.st_dev, parent.st_ino) != (self._parent_id.st_dev, self._parent_id.st_ino):
                raise Refused("parent_drift")
            if ((root.st_dev, root.st_ino) != (self._root_id.st_dev, self._root_id.st_ino)
                    or not stat.S_ISDIR(root.st_mode) or stat.S_IMODE(root.st_mode) != 0o700):
                raise Refused("root_drift")
        finally:
            os.close(check)

    def _new(self, name):
        _name(name)
        if name not in self._limits or name in self._used:
            raise Refused("unknown_or_used_slot")
        self._roots()
        self._used.add(name)  # failed creation has no retry credit
        return os.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                       0o600, dir_fd=self._root_fd)

    def _write(self, fd, name, data, position):
        if type(data) is not bytes or len(data) > CHUNK:
            raise Refused("bounded_bytes_required")
        self._roots()
        opened = os.fstat(fd)
        named = os.stat(name, dir_fd=self._root_fd, follow_symlinks=False)
        if (_pin(opened) != _pin(named) or opened.st_size != position
                or stat.S_IMODE(opened.st_mode) != 0o600):
            raise Refused("destination_drift")
        if len(data) > self._limits[name] - self._charged[name]:
            raise Refused("limit")
        # Conservative charge BEFORE the syscall, including a partial/error attempt.
        # No refund, no second attempt after short writes, no reservation borrowing.
        self._charged[name] += len(data)
        if os.write(fd, data) != len(data):
            raise Refused("short_write")
        return position + len(data)

    def _result(self, status, commit, code="", local=None, error_number=None):
        return dict(status=status, commit_state=commit, code=code, errno=error_number,
                    protection_verified=False, source_start_allowed=False,
                    retry_b_allowed=False, local_error_receipt=local,
                    native_fallback=("stage=copy;commit=" + commit + ";code=" + code
                                     + ";local_receipt=failed") if local is False else None)

    def _failure(self, commit, code, error_number=None):
        code = code if code in CODES else "input_error"
        if type(error_number) is not int or not 0 <= error_number <= 65535:
            error_number = None
        self._stopped = True
        if self._receipt is None:
            self._receipt = False  # exactly one attempt, even if persistence fails
            fd = None
            receipt_ready = False
            try:
                data = ("stage=copy;commit=" + commit + ";code=" + code).encode("ascii")
                data = data.ljust(ERROR_BYTES, b" ")
                fd = self._new("error")
                self._write(fd, "error", data, 0)
                os.fsync(fd)
                receipt_ready = True
            except (OSError, Refused):
                pass
            finally:
                if fd is not None:
                    try:
                        os.close(fd)
                    except OSError:
                        # FD state is uncertain: never retry or replace the original error.
                        receipt_ready = False
            self._receipt = receipt_ready
        return self._result("unverified", commit, code, self._receipt, error_number)

    def _run(self, name, chunks, commit, expected_hash=None, prime=False):
        if type(commit) is not str or commit not in COMMITS:
            raise Refused("invalid_commit_state")
        if not self._lock.acquire(blocking=False):
            raise Refused("serial_writer_busy")
        fd = None
        iterator = None
        try:
            if self._stopped:
                return self._result("unverified", commit, "stopped", self._receipt)
            if name == "error":
                raise Refused("reserved_error_slot")
            iterator = iter(chunks)
            if prime:
                first = next(iterator, None)  # source validation under the serial lock
                def prepend(head, tail):
                    if head is not None:
                        yield head
                    yield from tail
                chunks = prepend(first, iterator)
            else:
                chunks = iterator
            fd = self._new(name)
            position = 0
            digest = hashlib.sha256()
            for chunk in chunks:
                position = self._write(fd, name, chunk, position)
                digest.update(chunk)
            os.fsync(fd)
            if expected_hash is not None and digest.hexdigest() != expected_hash:
                raise Refused("hash")
            os.lseek(fd, 0, os.SEEK_SET)
            readback = hashlib.sha256()
            remaining = position
            while remaining:
                chunk = os.read(fd, min(CHUNK, remaining))
                if not chunk:
                    raise Refused("destination_drift")
                readback.update(chunk)
                remaining -= len(chunk)
            if os.read(fd, 1):
                raise Refused("destination_drift")
            self._roots()
            opened = os.fstat(fd)
            named = os.stat(name, dir_fd=self._root_fd, follow_symlinks=False)
            if (_pin(opened) != _pin(named) or opened.st_size != position
                    or stat.S_IMODE(opened.st_mode) != 0o600):
                raise Refused("destination_drift")
            if readback.digest() != digest.digest():
                raise Refused("hash")
            if iterator is not None and hasattr(iterator, "close"):
                iterator.close()
                iterator = None
            os.close(fd)
            fd = None
            return self._result("payload_verified", commit)
        except Refused as error:
            return self._failure(commit, str(error))
        except OSError as error:
            return self._failure(commit, "os_error", error.errno)
        except Exception:
            return self._failure(commit, "input_error")
        except BaseException:
            # Control exceptions propagate, but this object must never write again.
            self._stopped = True
            raise
        finally:
            try:
                try:
                    if iterator is not None and hasattr(iterator, "close"):
                        try:
                            iterator.close()
                        except Exception:
                            pass  # already unverified; never change a failure to success
                finally:
                    if fd is not None:
                        try:
                            os.close(fd)
                        except OSError:
                            pass
            except BaseException:
                # Cleanup can itself be interrupted; latch before releasing the lock.
                self._stopped = True
                raise
            finally:
                self._lock.release()

    def stream(self, name, chunks, commit_state="not_attempted"):
        """File-backed bounded stdout/stderr/metadata/temp/control payloads.

        Caller must not forward a second unbounded copy to console/logs.
        Oversized chunks/iterators fail without serializing exceptions or paths.
        """
        return self._run(name, chunks, commit_state)

    def copy(self, source_name, destination, expected_identity, expected_sha256,
             commit_state="not_attempted"):
        """Copy only synthetic payloads; full metadata/restore remains unverified."""
        def chunks():
            _name(source_name)
            if not isinstance(expected_identity, tuple) or len(expected_identity) != 7:
                raise Refused("source_manifest")
            if destination not in self._limits or destination == "error":
                raise Refused("unknown_or_used_slot")
            if type(expected_identity[2]) is not int or expected_identity[2] < 0:
                raise Refused("source_manifest")
            if expected_identity[2] > self._limits[destination]:
                raise Refused("limit")
            if not isinstance(expected_sha256, str) or not re.fullmatch("[0-9a-f]{64}", expected_sha256):
                raise Refused("source_manifest")
            # Validate before opening destination through the outer generator below.
            named = os.stat(source_name, dir_fd=self._parent_fd, follow_symlinks=False)
            if _pin(named) != expected_identity:
                raise Refused("source_drift")
            source = os.open(source_name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                             dir_fd=self._parent_fd)
            try:
                count = 0
                while True:
                    if _pin(os.fstat(source)) != expected_identity:
                        raise Refused("source_drift")
                    chunk = os.read(source, CHUNK)
                    if _pin(os.fstat(source)) != expected_identity:
                        raise Refused("source_drift")
                    if not chunk:
                        break
                    count += len(chunk)
                    if count > expected_identity[2]:
                        raise Refused("source_drift")
                    yield chunk
                named = os.stat(source_name, dir_fd=self._parent_fd, follow_symlinks=False)
                if count != expected_identity[2] or _pin(named) != expected_identity:
                    raise Refused("source_drift")
            finally:
                os.close(source)
        return self._run(destination, chunks(), commit_state, expected_sha256, prime=True)
