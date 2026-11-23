"""Direct scratch tests. No product modules, conftest, Settings or engine imports."""
import errno
import hashlib
import importlib.util
import os
from pathlib import Path
import sqlite3
import sys
import unittest
from unittest.mock import patch
import uuid

PARENT = Path(sys.argv.pop(1)).resolve()
spec = importlib.util.spec_from_file_location("guard", Path(__file__).with_name("guard.py"))
g = importlib.util.module_from_spec(spec)
sys.modules["guard"] = g
if spec.loader and Path(spec.origin).exists():
    spec.loader.exec_module(g)

class ContractTests(unittest.TestCase):
    def setUp(self):
        self.area = PARENT / ("case-" + uuid.uuid4().hex)
        self.area.mkdir(mode=0o700)

    def session(self, slots=None, cap=None):
        limits = {"error": 256, "stdout": 0, "stderr": 0}
        limits.update(slots or {})
        return g.ScratchWriter(self.area, "destination", limits,
                               cap=sum(limits.values()) if cap is None else cap)

    def source(self, data=b"abcdef"):
        path = self.area / "source"
        path.write_bytes(data)
        return path, g.identity(path), hashlib.sha256(data).hexdigest()

    def test_aggregate_denied_before_destination_creation(self):
        with self.assertRaises(g.Refused):
            self.session({"first": 6, "second": 6}, cap=266)
        self.assertFalse((self.area / "destination").exists())

    def test_120gib_equality_and_one_byte_overflow(self):
        w = self.session({"large": 128849018624}, cap=128849018880)
        self.assertEqual(w.snapshot()["reserved_remaining"], 128849018880)
        w.close()
        with self.assertRaises(g.Refused):
            g.ScratchWriter(self.area, "overflow", {"error": 256, "large": 128849018625})
        self.assertFalse((self.area / "overflow").exists())

    def test_invalid_or_unavailable_plan_never_creates_destination(self):
        for limits in (None, {}, {"error": 255}, {"error": 256, "x": -1},
                       {"error": 256, "x": True}, {"error": 256, "x": 1.5},
                       {"error": 256, "../escape": 1}):
            with self.assertRaises(g.Refused):
                g.ScratchWriter(self.area, "invalid", limits)
            self.assertFalse((self.area / "invalid").exists())

    def test_full_exact_stream_and_no_reopen_or_refund(self):
        w = self.session({"data": 6})
        result = w.stream("data", [b"abc", b"def"])
        self.assertEqual(result["status"], "payload_verified")
        self.assertEqual((w.root / "data").read_bytes(), b"abcdef")
        self.assertEqual(w.snapshot()["charged"], 6)
        second = w.stream("data", [b"x"])
        self.assertEqual(second["status"], "unverified")
        self.assertEqual((w.root / "data").read_bytes(), b"abcdef")
        self.assertEqual(w.snapshot()["plan_total"], 262)
        self.assertEqual(w.snapshot()["charged"] + w.snapshot()["reserved_remaining"], 262)
        w.close()

    def test_one_byte_overflow_retains_partial_and_future_reservations(self):
        w = self.session({"data": 6, "future": 5})
        result = w.stream("data", [b"abc", b"defg"])
        self.assertEqual(result["code"], "limit")
        self.assertEqual((w.root / "data").read_bytes(), b"abc")
        self.assertEqual(w.snapshot()["slots"]["future"]["remaining"], 5)
        self.assertEqual(w.snapshot()["slots"]["data"]["charged"], 3)
        self.assertEqual(w.snapshot()["charged"] + w.snapshot()["reserved_remaining"], 267)
        self.assertEqual((w.root / "error").stat().st_size, 256)
        self.assertEqual(w.stream("future", [b"a"])["code"], "stopped")
        w.close()

    def test_short_write_is_not_retried_or_refunded(self):
        w = self.session({"data": 6})
        real = os.write
        calls = []
        def short(fd, data):
            if data == b"abcdef":
                calls.append(1)
                return real(fd, data[:2])
            return real(fd, data)
        with patch.object(g.os, "write", side_effect=short):
            result = w.stream("data", [b"abcdef"])
        self.assertEqual((w.root / "data").read_bytes(), b"ab")
        self.assertEqual(result["code"], "short_write")
        self.assertEqual(w.snapshot()["slots"]["data"]["charged"], 6)
        self.assertEqual(len(calls), 1)
        w.close()

    def test_partial_then_ioerror_retains_commit_known_and_blocks_source(self):
        w = self.session({"data": 6})
        real = os.write
        def fail(fd, data):
            if data == b"abcdef":
                real(fd, data[:2])
                raise OSError(errno.ENOSPC, "synthetic injected write failure")
            return real(fd, data)
        with patch.object(g.os, "write", side_effect=fail):
            result = w.stream("data", [b"abcdef"], commit_state="known_committed")
        self.assertEqual((w.root / "data").read_bytes(), b"ab")
        self.assertEqual(result["commit_state"], "known_committed")
        self.assertEqual(result["errno"], errno.ENOSPC)
        self.assertFalse(result["source_start_allowed"])
        self.assertFalse(result["retry_b_allowed"])
        self.assertEqual(w.snapshot()["slots"]["data"]["charged"], 6)
        w.close()

    def test_bounded_stdout_stderr_and_metadata_share_one_plan(self):
        w = self.session({"stdout": 4, "stderr": 3, "metadata": 2})
        self.assertEqual(w.stream("metadata", [b"{}"])["status"], "payload_verified")
        self.assertEqual(w.stream("stdout", [b"1234"])["status"], "payload_verified")
        result = w.stream("stderr", [b"abc", b"d"])
        self.assertEqual(result["code"], "limit")
        self.assertEqual((w.root / "stdout").stat().st_size, 4)
        self.assertEqual((w.root / "stderr").read_bytes(), b"abc")
        self.assertEqual(w.snapshot()["plan_total"], 265)
        w.close()

    def test_error_receipt_cannot_persist_keeps_native_fallback(self):
        w = self.session({"data": 6})
        (w.root / "error").mkdir()
        result = w.stream("data", [b"abc", b"toolong"] ,commit_state="unknown")
        self.assertEqual((w.root / "data").read_bytes(), b"abc")
        self.assertFalse(result["local_error_receipt"])
        self.assertEqual(result["native_fallback"], "stage=copy;commit=unknown;code=limit;local_receipt=failed")
        self.assertFalse(result["source_start_allowed"])
        w.close()

    def test_payload_copy_success_is_not_metadata_restore_acceptance(self):
        source, pin, digest = self.source()
        source.chmod(0o711)
        pin = g.identity(source)
        w = self.session({"copy": 6})
        result = w.copy("source", "copy", pin, digest)
        self.assertEqual((w.root / "copy").read_bytes(), b"abcdef")
        self.assertEqual((w.root / "copy").stat().st_mode & 0o777, 0o600)
        self.assertEqual(source.stat().st_mode & 0o777, 0o711)
        self.assertEqual(result["status"], "payload_verified")
        self.assertFalse(result["protection_verified"])
        self.assertFalse(result["source_start_allowed"])
        w.close()

    def test_missing_invalid_and_symlink_sources_fail_without_data_writes(self):
        source, pin, digest = self.source()
        (self.area / "link").symlink_to(source)
        w = self.session({"copy": 6})
        result = w.copy("link", "copy", pin, digest)
        self.assertEqual(result["status"], "unverified")
        self.assertFalse((w.root / "copy").exists())
        w.close()
        with self.assertRaises((g.Refused, OSError)):
            g.identity(self.area / "missing")
        with self.assertRaises(g.Refused):
            g.identity(self.area)

    def test_known_full_source_must_fit_reserved_slot_before_copy(self):
        source, pin, digest = self.source(b"a" * 131072)
        w = self.session({"copy": 65536})
        result = w.copy("source", "copy", pin, digest)
        self.assertEqual(result["code"], "limit")
        self.assertFalse((w.root / "copy").exists())
        self.assertEqual(w.snapshot()["slots"]["copy"]["charged"], 0)
        w.close()

    def test_bad_hash_retains_full_unverified_payload(self):
        source, pin, digest = self.source()
        w = self.session({"copy": 6})
        result = w.copy("source", "copy", pin, "0" * 64)
        self.assertEqual(result["code"], "hash")
        self.assertEqual((w.root / "copy").read_bytes(), b"abcdef")
        self.assertFalse(result["protection_verified"])
        w.close()

    def test_racing_growth_stops_after_first_real_chunk(self):
        data = b"a" * 131072
        source, pin, digest = self.source(data)
        w = self.session({"copy": len(data)})
        real = os.write
        changed = []
        def mutate(fd, chunk):
            written = real(fd, chunk)
            if chunk == b"a" * 65536 and not changed:
                with source.open("ab") as src:
                    src.write(b"!")
                changed.append(True)
            return written
        with patch.object(g.os, "write", side_effect=mutate):
            result = w.copy("source", "copy", pin, digest)
        self.assertEqual(result["code"], "source_drift")
        self.assertEqual((w.root / "copy").stat().st_size, 65536)
        self.assertEqual(source.stat().st_size, 131073)
        w.close()

    def test_destination_collision_never_overwrites(self):
        w = self.session({"data": 6})
        (w.root / "data").write_bytes(b"preserve")
        result = w.stream("data", [b"abcdef"])
        self.assertEqual(result["status"], "unverified")
        self.assertEqual((w.root / "data").read_bytes(), b"preserve")
        w.close()

    def test_reentrant_writer_cannot_borrow_other_reservations(self):
        w = self.session({"data": 6, "other": 6})
        real = os.write
        attempts = []
        def nested(fd, data):
            if data == b"abcdef":
                with self.assertRaises(g.Refused):
                    w.stream("other", [b"123456"])
                attempts.append(True)
            return real(fd, data)
        with patch.object(g.os, "write", side_effect=nested):
            result = w.stream("data", [b"abcdef"])
        self.assertEqual(result["status"], "payload_verified")
        self.assertEqual(attempts, [True])
        self.assertFalse((w.root / "other").exists())
        w.close()

    def test_existing_root_and_symlink_parent_are_refused(self):
        w = self.session()
        with self.assertRaises((g.Refused, OSError)):
            self.session()
        w.close()
        (self.area / "alias").symlink_to(self.area, target_is_directory=True)
        with self.assertRaises((g.Refused, OSError)):
            g.ScratchWriter(self.area / "alias", "new", {"error": 256})
        self.assertFalse((self.area / "new").exists())

    def test_input_exception_cannot_expand_or_leak_error_receipt(self):
        w = self.session({"data": 1})
        def untrusted():
            yield b"a"
            raise g.Refused("PRIVATE" * 1000)
        result = w.stream("data", untrusted())
        self.assertEqual(result["code"], "input_error")
        self.assertEqual((w.root / "error").stat().st_size, 256)
        self.assertNotIn(b"PRIVATE", (w.root / "error").read_bytes())
        w.close()

    def test_stopped_copy_never_opens_input(self):
        w = self.session({"data": 1})
        w.stream("data", [b"overflow"])
        with patch.object(g.os, "open", side_effect=AssertionError("stopped writer opened input")):
            result = w.copy("missing", "data", (1, 2, 3, 4, 5, 6, 1), "0" * 64)
        self.assertEqual(result["code"], "stopped")
        w.close()

    def test_root_renamed_midwrite_leaves_partial_and_native_fallback(self):
        w = self.session({"data": 6})
        real = os.write
        def rename(fd, chunk):
            result = real(fd, chunk)
            if chunk == b"abc":
                w.root.rename(self.area / "retained-partial")
            return result
        with patch.object(g.os, "write", side_effect=rename):
            result = w.stream("data", [b"abc", b"def"])
        self.assertEqual((self.area / "retained-partial/data").read_bytes(), b"abc")
        self.assertFalse(result["local_error_receipt"])
        self.assertFalse(result["source_start_allowed"])
        w.close()

    def test_same_pool_demands_are_combined_once(self):
        result = g.check_pools([("one", 70), ("one", 50)], {"one": 100})
        self.assertEqual(result, {"one": {"remaining": 120, "threshold": 144, "free": 100, "fits": False}})
        self.assertTrue(g.check_pools([("one", 100)], {"one": 120})["one"]["fits"])
        with self.assertRaises(g.Refused):
            g.check_pools([("unknown", 1)], {"one": 100})

    def test_synthetic_sqlite_full_does_not_restore_or_retry(self):
        dbpath = self.area / "synthetic.db"
        db = sqlite3.connect(str(dbpath), isolation_level=None)
        db.execute("CREATE TABLE fixture(id INTEGER PRIMARY KEY, value BLOB)")
        db.execute("INSERT INTO fixture VALUES(1, 'original')")
        pages = db.execute("PRAGMA page_count").fetchone()[0]
        size = db.execute("PRAGMA page_size").fetchone()[0]
        self.assertEqual(db.execute("PRAGMA max_page_count=" + str(pages)).fetchone()[0], pages)
        db.execute("BEGIN IMMEDIATE")
        with self.assertRaises(sqlite3.DatabaseError):
            db.execute("UPDATE fixture SET value=? WHERE id=1", (b"x" * (size * 10),))
        if db.in_transaction:
            db.execute("ROLLBACK")
        self.assertEqual(db.execute("SELECT value FROM fixture").fetchone()[0], "original")
        db.close()

    def test_lost_commit_ack_and_failed_postcopy_preserve_new_state(self):
        dbpath = self.area / "source"
        db = sqlite3.connect(str(dbpath), isolation_level=None)
        db.execute("CREATE TABLE fixture(id INTEGER PRIMARY KEY, status TEXT)")
        db.execute("INSERT INTO fixture VALUES(1, 'queued')")
        db.execute("BEGIN IMMEDIATE")
        db.execute("UPDATE fixture SET status='cancelled' WHERE id=1 AND status='queued'")
        db.execute("COMMIT")
        # A transport acknowledgement loss cannot undo the actual COMMIT.
        db.close()
        pin = g.identity(dbpath)
        digest = hashlib.sha256(dbpath.read_bytes()).hexdigest()
        w = self.session({"copy": pin[2]})
        real = os.write
        once = []
        def fail(fd, chunk):
            if len(chunk) > 256 and not once:
                once.append(True)
                real(fd, chunk[:19])
                raise OSError(errno.EIO, "synthetic lost postcopy write")
            return real(fd, chunk)
        with patch.object(g.os, "write", side_effect=fail):
            result = w.copy("source", "copy", pin, digest, commit_state="unknown")
        self.assertEqual((w.root / "copy").stat().st_size, 19)
        reader = sqlite3.connect("file:" + str(dbpath) + "?mode=ro", uri=True)
        self.assertEqual(reader.execute("SELECT status FROM fixture").fetchone()[0], "cancelled")
        reader.close()
        self.assertEqual(result["commit_state"], "unknown")
        self.assertEqual(result["errno"], errno.EIO)
        self.assertFalse(result["source_start_allowed"])
        self.assertFalse(result["retry_b_allowed"])
        w.close()

if __name__ == "__main__":
    unittest.main(verbosity=2)
