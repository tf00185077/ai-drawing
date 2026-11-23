"""Optional available-component probe: explicit synthetic paths before imports."""
import sys
from pathlib import Path
import json
import hashlib
import importlib.abc
import importlib.metadata
import os
import sqlite3
import asyncio

scratch = Path(sys.argv[1]).resolve()
backend = Path(sys.argv[2]).resolve()
scratch.mkdir(mode=0o700)  # new fixture only, refuses reuse
os.chdir(scratch)
# Only this explicit synthetic process environment is supplied by the launcher.
os.environ["AI_DRAWING_MAINTENANCE"] = "closed"
os.environ["AI_DRAWING_MAINTENANCE_OWNER"] = "synthetic-g09"
os.environ["AI_DRAWING_MAINTENANCE_EPOCH"] = "synthetic-epoch"
blocked = ("app.config", "app.db", "app.api", "app.core", "app.services")
class NoProductState(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == name or fullname.startswith(name + ".") for name in blocked):
            raise AssertionError("stateful product import blocked: " + fullname)
sys.meta_path.insert(0, NoProductState())
writes = []
connections = []
def audit(event, args):
    if event in ("socket.connect", "socket.bind", "subprocess.Popen", "os.system"):
        raise AssertionError("no network/process operation in fixture")
    if event == "sqlite3.connect":
        target = Path(args[0]).resolve()
        if scratch not in target.parents:
            raise AssertionError("DB outside synthetic root")
        connections.append(str(target.relative_to(scratch)))
    if event == "open":
        path, mode, flags = args
        writing = bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
        if writing:
            if not isinstance(path, (str, bytes, os.PathLike)):
                raise AssertionError("unknown write target")
            target = Path(path).resolve()
            if target != scratch and scratch not in target.parents:
                raise AssertionError("write outside synthetic root")
            writes.append(str(target.relative_to(scratch)))
sys.addaudithook(audit)

# Fixture DB/schema only: no product imports, engine or Settings.
dbpath = scratch / "fixture.db"
db = sqlite3.connect(str(dbpath), isolation_level=None)
db.execute("CREATE TABLE fixture(id INTEGER PRIMARY KEY, status TEXT, stage TEXT, cancel_requested_at TEXT, completed_at TEXT, updated_at TEXT, untouched BLOB)")
rows = [(i, "queued", "queued", None, None, None, ("keep-" + str(i)).encode()) for i in range(408)]
db.executemany("INSERT INTO fixture VALUES(?,?,?,?,?,?,?)", rows)
old_max = db.execute("PRAGMA main.max_page_count").fetchone()[0]
pages = db.execute("PRAGMA main.page_count").fetchone()[0]
page_size = db.execute("PRAGMA main.page_size").fetchone()[0]
mode = db.execute("PRAGMA main.journal_mode").fetchone()[0]
before = dbpath.read_bytes()
set_return = db.execute("PRAGMA main.max_page_count=" + str(pages)).fetchone()[0]
readback = db.execute("PRAGMA main.max_page_count").fetchone()[0]
after_setting = dbpath.read_bytes()
second = sqlite3.connect(str(dbpath), isolation_level=None)
second_limit = second.execute("PRAGMA main.max_page_count").fetchone()[0]
second.close()
db.execute("BEGIN IMMEDIATE")
error = None
try:
    db.execute("UPDATE fixture SET untouched=? WHERE id=0", (b"x" * (page_size * (pages + 10)),))
except sqlite3.DatabaseError as exc:
    error = str(exc)
transaction_after_full = db.in_transaction
if db.in_transaction:
    db.execute("ROLLBACK")
assert error == "database or disk is full"
assert db.execute("SELECT untouched FROM fixture WHERE id=0").fetchone()[0] == b"keep-0"
# Exact five-field shape with 408 synthetic integers, not original UUIDs or real B.
db.execute("BEGIN IMMEDIATE")
five_field_error = None
completed_statements = 0
try:
    for i in range(408):
        cur = db.execute("UPDATE fixture SET status='cancelled', stage='cancelled', cancel_requested_at=?, completed_at=?, updated_at=? WHERE id=? AND status='queued' AND stage='queued'", ("synthetic-T",) * 3 + (i,))
        assert cur.rowcount == 1
        completed_statements += 1
    db.execute("COMMIT")
except sqlite3.DatabaseError as exc:
    five_field_error = str(exc)
    if db.in_transaction:
        db.execute("ROLLBACK")
assert five_field_error == "database or disk is full"
assert db.execute("SELECT count(*) FROM fixture WHERE status='queued' AND stage='queued'").fetchone()[0] == 408
untouched = db.execute("SELECT id,untouched FROM fixture ORDER BY id").fetchall()
assert untouched == [(i, ("keep-" + str(i)).encode()) for i in range(408)]
main_after = dbpath.stat().st_size
full_later_sha = hashlib.sha256(dbpath.read_bytes()).hexdigest()
db.close()
reopened = sqlite3.connect(str(dbpath), isolation_level=None)
reopen_limit = reopened.execute("PRAGMA main.max_page_count").fetchone()[0]
reopened.close()
sqlite_result = dict(version=sqlite3.sqlite_version, pages=pages, page_size=page_size,
                     journal_mode_read_only=mode, old_max=old_max, set_value=pages,
                     set_return=set_return, readback=readback,
                     setting_changed_file_bytes=(before != after_setting),
                     second_connection_limit=second_limit, reopen_limit=reopen_limit,
                     full_error=error, in_transaction_after_full=transaction_after_full,
                     synthetic_five_field_rows=408, completed_statements_before_full=completed_statements,
                     five_field_error=five_field_error, queued_after_rollback=408,
                     main_after=main_after,
                     full_later_sha256=full_later_sha)

# Actual fixed closed app, actual prepared FastAPI, in-process ASGI only.
sys.path.insert(0, str(backend))
before_closed = len(writes)
from app.main import app
assert not any(any(n == x or n.startswith(x + ".") for x in blocked) for n in sys.modules)
async def request(path):
    sent = []
    first = True
    wait = asyncio.Event()
    async def receive():
        nonlocal first
        if first:
            first = False
            return {"type": "http.request", "body": b"", "more_body": False}
        await wait.wait()
        return {"type": "http.disconnect"}
    async def send(message):
        sent.append(message)
    scope = dict(type="http", asgi={"version": "3.0"}, http_version="1.1",
                 method="GET", scheme="http", path=path, raw_path=path.encode(),
                 query_string=b"", root_path="", headers=[],
                 client=("fixture", 1), server=("fixture", 1))
    await app(scope, receive, send)
    status = next(x["status"] for x in sent if x["type"] == "http.response.start")
    body = b"".join(x.get("body", b"") for x in sent if x["type"] == "http.response.body")
    assert len(body) <= 4096
    return status, json.loads(body)
status, body = asyncio.run(request("/maintenance/status"))
assert status == 200 and body["state"] == "closed"
assert body["owner"] == "synthetic-g09" and body["epoch"] == "synthetic-epoch"
assert body["legacy_process_certified"] is False
normal, rejected = asyncio.run(request("/health"))
assert normal == 503
assert rejected == {"detail": {"code": "maintenance_closed"}}
print(json.dumps(dict(python=sys.version, sqlite=sqlite_result,
                     closed=dict(status=status, normal_status=normal, source_version=body["version"],
                                 product_state_imports=[], fastapi=importlib.metadata.version("fastapi"),
                                 starlette=importlib.metadata.version("starlette")),
                     python_write_open_events=writes, sqlite_connect_paths=connections,
                     closed_phase_python_write_open_events=writes[before_closed:]), indent=2))
