"""Synthetic regressions for interruption latching and receipt cleanup only.

Run with -I -B and a fresh test-owned parent, optionally followed by guard.py.
The original QA15 and defect-asserting minimal script remain separate inputs.
"""
import errno
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import unittest
from unittest.mock import patch

BASE = Path(sys.argv.pop(1)).resolve(strict=True)
CANDIDATE = Path(sys.argv.pop(1)).resolve(strict=True) if len(sys.argv) > 1 else Path(__file__).with_name("guard.py")
os.chdir(BASE)

class BlockProduct(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "app" or fullname.startswith("app."):
            raise AssertionError("product imports prohibited")

sys.meta_path.insert(0, BlockProduct())
spec = importlib.util.spec_from_file_location("failure_guard", CANDIDATE)
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)
OBS = []

def is_receipt(fd):
    st = os.fstat(fd)
    return stat.S_ISREG(st.st_mode) and st.st_size == 256

class FailureContracts(unittest.TestCase):
    def writer(self, label, size=3):
        parent = BASE / label
        parent.mkdir(mode=0o700)
        w = g.ScratchWriter(parent, "dest", {"error": 256, "partial": size, "later": 2})
        self.addCleanup(w.close)
        return w

    def stopped(self, w, charged):
        before = w.snapshot()
        result = w.stream("later", [b"XY"], commit_state="unknown")
        OBS.append(dict(root=w.root.name, result=result, snapshot=w.snapshot(),
                        partial=(w.root / "partial").read_bytes().decode("ascii"),
                        later_exists=(w.root / "later").exists()))
        self.assertEqual(result["code"], "stopped")
        self.assertEqual(result["commit_state"], "unknown")
        self.assertFalse(result["retry_b_allowed"])
        self.assertFalse(result["source_start_allowed"])
        self.assertFalse(result["protection_verified"])
        self.assertFalse((w.root / "later").exists())
        self.assertEqual(w.snapshot(), before)
        self.assertEqual(before["slots"]["partial"]["charged"], charged)
        self.assertEqual(before["slots"]["later"]["remaining"], 2)
        self.assertEqual(before["charged"] + before["reserved_remaining"], charged + 258)

    def test_iterator_control_exceptions_propagate_and_stop(self):
        # Removing the BaseException stop latch permits a real later payload.
        for kind in (KeyboardInterrupt, SystemExit, GeneratorExit):
            with self.subTest(kind=kind.__name__):
                w = self.writer("iterator-" + kind.__name__)
                original = kind("SYNTHETIC_PRIVATE_INTERRUPT")
                def interrupted():
                    yield b"ABC"
                    raise original
                with self.assertRaises(kind) as raised:
                    w.stream("partial", interrupted(), commit_state="unknown")
                self.assertIs(raised.exception, original)
                self.assertEqual((w.root / "partial").read_bytes(), b"ABC")
                self.assertFalse((w.root / "error").exists())
                self.stopped(w, 3)

    def test_success_path_iterator_close_interrupt_stops(self):
        # A control exception from close also occurs inside the guarded boundary.
        w = self.writer("iterator-close")
        payload_fd = []
        realwrite = os.write
        def capture(fd, data):
            if data == b"ABC":
                payload_fd.append(fd)
            return realwrite(fd, data)
        # This iterator completes its data, then interrupts the explicit close.
        class Closing:
            def __init__(self):
                self.items = iter([b"ABC"])
            def __iter__(self):
                return self
            def __next__(self):
                return next(self.items)
            def close(self):
                raise KeyboardInterrupt("SYNTHETIC_PRIVATE_CLEANUP")
        with patch.object(g.os, "write", side_effect=capture):
            with self.assertRaises(KeyboardInterrupt):
                w.stream("partial", Closing(), commit_state="unknown")
        self.assertEqual((w.root / "partial").read_bytes(), b"ABC")
        with self.assertRaises(OSError) as closed:
            os.fstat(payload_fd[0])
        self.assertEqual(closed.exception.errno, errno.EBADF)
        self.stopped(w, 3)

    def test_interrupted_write_keeps_full_precharge(self):
        # A real 3/5 partial write must retain the entire 5-byte charge.
        w = self.writer("write-interrupt", size=5)
        real = os.write
        def interrupted(fd, data):
            if data == b"ABCDE":
                real(fd, data[:3])
                raise KeyboardInterrupt()
            return real(fd, data)
        with patch.object(g.os, "write", side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                w.stream("partial", [b"ABCDE"], commit_state="unknown")
        self.assertEqual((w.root / "partial").read_bytes(), b"ABC")
        self.stopped(w, 5)

    def test_receipt_close_errors_preserve_original_sanitized_failure(self):
        # Let real payload/receipt writes happen; inject only syscall outcomes.
        for label, sync_fails, close_fails, uncertain_fd in (
                ("fsync-only", True, False, False),
                ("close-only", False, True, False),
                ("fsync-close", True, True, False),
                ("uncertain-close", False, True, True)):
            with self.subTest(case=label):
                w = self.writer(label, size=5)
                realwrite, realsync, realclose = os.write, os.fsync, os.close
                receipt_fds = []
                close_calls = []
                def fail_payload(fd, data):
                    if data == b"ABCDE":
                        realwrite(fd, data[:3])
                        raise OSError(errno.ENOSPC, "SYNTHETIC_PRIVATE_PAYLOAD")
                    return realwrite(fd, data)
                def sync(fd):
                    if sync_fails and is_receipt(fd):
                        raise OSError(errno.EIO, "SYNTHETIC_PRIVATE_FSYNC")
                    return realsync(fd)
                def close(fd):
                    receipt = is_receipt(fd)
                    if receipt:
                        receipt_fds.append(fd)
                        close_calls.append(fd)
                    if not (receipt and uncertain_fd):
                        realclose(fd)
                    if receipt and close_fails:
                        raise OSError(errno.EIO, "SYNTHETIC_PRIVATE_CLOSE")
                result = None
                escaped = None
                try:
                    with patch.object(g.os, "write", side_effect=fail_payload), \
                         patch.object(g.os, "fsync", side_effect=sync), \
                         patch.object(g.os, "close", side_effect=close):
                        try:
                            result = w.stream("partial", [b"ABCDE"], commit_state="unknown")
                        except OSError as exc:
                            escaped = dict(errno=exc.errno, marker="PRIVATE" in str(exc))
                finally:
                    # Test-owned recovery only: the helper must never retry close.
                    if uncertain_fd:
                        for fd in receipt_fds:
                            realclose(fd)
                OBS.append(dict(case=label, result=result, escaped=escaped,
                                receipt_bytes=(w.root / "error").stat().st_size,
                                partial=(w.root / "partial").read_bytes().decode(),
                                close_attempts=len(close_calls), snapshot=w.snapshot()))
                self.assertIsNotNone(result, "cleanup lost the sanitized original failure")
                self.assertIsNone(escaped)
                self.assertEqual(len(close_calls), 1)
                self.assertEqual(result["code"], "os_error")
                self.assertEqual(result["errno"], errno.ENOSPC)
                self.assertFalse(result["local_error_receipt"])
                self.assertEqual(result["native_fallback"], "stage=copy;commit=unknown;code=os_error;local_receipt=failed")
                self.assertNotIn("PRIVATE", json.dumps(result))
                self.assertLess(len(json.dumps(result)), 1024)
                self.assertEqual((w.root / "error").stat().st_size, 256)
                self.assertNotIn(b"PRIVATE", (w.root / "error").read_bytes())
                self.assertEqual(w.snapshot()["slots"]["error"]["charged"], 256)
                self.stopped(w, 5)

    def test_true_receipt_interrupt_is_not_swallowed(self):
        # OSError containment must not convert an actual interrupt into a result.
        for location in ("fsync", "close"):
            with self.subTest(location=location):
                w = self.writer("receipt-interrupt-" + location)
                realsync, realclose = os.fsync, os.close
                def sync(fd):
                    if location == "fsync" and is_receipt(fd):
                        raise KeyboardInterrupt()
                    return realsync(fd)
                def close(fd):
                    receipt = is_receipt(fd)
                    realclose(fd)
                    if location == "close" and receipt:
                        raise KeyboardInterrupt()
                with patch.object(g.os, "fsync", side_effect=sync), \
                     patch.object(g.os, "close", side_effect=close):
                    with self.assertRaises(KeyboardInterrupt):
                        w.stream("partial", [b"ABC", b"!"], commit_state="unknown")
                self.assertEqual((w.root / "partial").read_bytes(), b"ABC")
                self.stopped(w, 3)

if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(FailureContracts)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    (BASE / "failure-observations.json").write_text(json.dumps(OBS, indent=2))
    sys.exit(not result.wasSuccessful())
