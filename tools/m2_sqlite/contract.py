"""Retained M2 refusal contract and bounded synthetic operation derivation.

No SQLite import/open, product integration, setting setter, B executor or OS fence.
The two operational entry points are unavailable BEFORE even inspecting arguments.
fixture_* APIs require the reviewed harness's newly created synthetic connection;
they are evidence tools, never cold-reader admission or a production profile.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import re

class Stop(ValueError):
    """Fixed sanitized refusal code; never embed database/native messages."""

IDS_SHA = '2a87d402ef171ba200b68b6db79c4656cfefb12449141742b891e7a429bec9a4'
COLUMNS = ('job_id', 'status', 'stage', 'cancel_requested_at', 'completed_at',
           'updated_at', 'params', 'recipe', 'reservation', 'serial', 'model', 'dataset')
FIXTURE_SCHEMA = '''CREATE TABLE lora_training_jobs (
job_id TEXT PRIMARY KEY, status TEXT, stage TEXT,
cancel_requested_at TEXT, completed_at TEXT, updated_at TEXT,
params, recipe, reservation, serial, model, dataset)'''
# Exact supported synthetic query. No SELECT * or selected-column digest.
ROW_SQL = ('SELECT ' + ', '.join('"'+c+'"' for c in COLUMNS) +
           ' FROM main.lora_training_jobs ORDER BY job_id COLLATE BINARY LIMIT 413')
SCHEMA_SQL = 'SELECT type,name,tbl_name,rootpage,sql FROM main.sqlite_master ORDER BY type,name LIMIT 33'
UPDATE_SQL = """UPDATE lora_training_jobs
SET status='cancelled', stage='cancelled',
    cancel_requested_at=:T, completed_at=:T, updated_at=:T
WHERE job_id=:approved_job_id AND status='queued' AND stage='queued'"""
MAX_ROWS = 412  # Synthetic subset ceiling, not an assertion about production.
CELL_BYTES = 4096
SERIAL_BYTES = 4194304
MISSING = (
    'cold_file_epoch_writer_and_complete_path_closure',
    'same_connection_VFS_registered_and_external_effect_binding',
    'supported_same_connection_all_required_limit_APIs',
    'complete_native_companion_temp_partial_recovery_write_bounds',
    'reviewed_M1_plan_covering_all_native_effects_and_full_post_B_copies',
    'actual_schema_complete_typed_preimages_and_exact_setting_grant',
)

@dataclass(frozen=True)
class Refusal:
    status: str = 'unavailable'
    code: str = 'complete_sqlite_profile_unavailable'
    commit_state: str = 'not_attempted'
    full_db_bound: object = None
    missing: tuple = MISSING
    database_access_attempted: bool = False
    protection_verified: bool = False
    source_start_allowed: bool = False
    retry_b_allowed: bool = False


def read_exact408(connection, window, administrative_time):
    """Borrowed handles untouched: no cold/effect proof exists in this component."""
    return Refusal()


def execute_exact408(connection, window, administrative_time):
    """No supported complete profile: no BEGIN, settings, charge, receipt or close.

    No caller cap, safe flag, arbitrary callback or profile dictionary is accepted.
    Window.effect is cooperative accounting and cannot confine SQLite's native I/O.
    This deliberately contains NO reachable DML implementation to accidentally admit.
    """
    return Refusal()


def exact_ids(raw):
    if (type(raw) is not bytes or len(raw) != 15096 or
            hashlib.sha256(raw).hexdigest() != IDS_SHA):
        raise Stop('exact408')
    ids = raw.decode('ascii').splitlines()
    if (len(ids) != 408 or ids != sorted(set(ids)) or not raw.endswith(b'\n') or
            any(not re.fullmatch(r'[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}', i) for i in ids)):
        raise Stop('exact408')
    return tuple(ids)


def cell(value):
    """Faithful SQLite scalar storage classes, no JSON recipe decoding/coercion."""
    if value is None: return ['null', None]
    if type(value) is int and -(2**63) <= value < 2**63: return ['integer', value]
    if type(value) is float and math.isfinite(value): return ['real', value.hex()]
    if type(value) is str and len(value) <= CELL_BYTES:
        try: raw = value.encode('utf-8')
        except UnicodeError: raise Stop('typed_value')
        if len(raw) <= CELL_BYTES: return ['text', value]
    if type(value) is bytes and len(value) <= CELL_BYTES: return ['blob', value.hex()]
    raise Stop('typed_value')


def encode_records(rows):
    if type(rows) not in (list, tuple) or len(rows) > MAX_ROWS: raise Stop('row_bound')
    typed = []
    for row in rows:
        if type(row) not in (tuple, list) or len(row) != len(COLUMNS): raise Stop('columns')
        typed.append([cell(v) for v in row])
    out = bytearray()
    for piece in json.JSONEncoder(ensure_ascii=True, separators=(',', ':'), allow_nan=False).iterencode(typed):
        raw = piece.encode('ascii')
        if len(raw) > SERIAL_BYTES-len(out): raise Stop('serialization_bound')
        out.extend(raw)
    return bytes(out)


def _bounded_query(c, sql, maximum):
    # A Python fetch ceiling bounds the returned representation, not SQLite native
    # query memory/temp/writes. Operational reads remain unavailable for this reason.
    from ledger import finish_owned
    cursor = c.execute(sql)
    error = None
    try:
        rows = cursor.fetchmany(maximum+1)
        if len(rows) > maximum: raise Stop('query_bound')
        for row in rows:
            for value in row: cell(value)
        return rows
    except BaseException as e:
        error = e
        raise
    finally:
        finish_owned((cursor.close,), error)  # one owned close; retain original interruption


def fixture_snapshot(c):
    """Synthetic-only complete schema/row representation, not a cold-reader proof.

    All fixture creation and isolation precede this call. A Python value-size check
    cannot bound a native fetch's earlier allocation; no operational use is admitted.
    """
    databases = _bounded_query(c, 'PRAGMA database_list', 3)
    if len(databases) != 1 or databases[0][1] != 'main': raise Stop('attached_or_temp')
    schema = _bounded_query(c, SCHEMA_SQL, 32)
    expected = [('index','sqlite_autoindex_lora_training_jobs_1','lora_training_jobs',None),
                ('table','lora_training_jobs','lora_training_jobs',FIXTURE_SCHEMA)]
    if [(t,n,tbl,sql) for t,n,tbl,root,sql in schema] != expected: raise Stop('schema')
    xinfo = _bounded_query(c, 'PRAGMA main.table_xinfo(lora_training_jobs)', 32)
    if tuple(r[1] for r in xinfo) != COLUMNS or any(r[-1] != 0 for r in xinfo): raise Stop('schema')
    rows = _bounded_query(c, ROW_SQL, MAX_ROWS)
    raw = encode_records(rows)
    return {'connection_id': id(c), 'schema': [list(r) for r in schema], 'columns': list(COLUMNS),
            'records': json.loads(raw), 'serialization_bytes': len(raw)}


def _records(snapshot):
    if snapshot['columns'] != list(COLUMNS) or len(snapshot['records']) > MAX_ROWS: raise Stop('schema')
    result = {}
    for row in snapshot['records']:
        if len(row) != len(COLUMNS) or row[0][0] != 'text': raise Stop('typed_value')
        key = row[0][1]
        if key in result: raise Stop('duplicate')
        result[key] = row
    return result


def _fixed_set(ids):
    if type(ids) not in (list, tuple) or len(ids) != 408 or any(type(i) is not str or len(i) != 36 for i in ids):
        raise Stop('exact408')
    return exact_ids(('\n'.join(ids)+'\n').encode('ascii'))


def guard_preimages(original, fresh, ids):
    ids = _fixed_set(ids)
    # Inputs are complete fixture snapshots; no selected-column hash shortcut.
    if original != fresh: raise Stop('changed_full_preimage')
    records = _records(fresh)
    for i in ids:
        if i not in records or records[i][1:3] != [['text','queued'],['text','queued']]: raise Stop('target_guard')
    for i,row in records.items():
        if i not in ids and row[1] not in (['text','completed'],['text','cancelled'],['text','failed']):
            raise Stop('outside_nonterminal')


def _timestamp(T):
    import datetime
    if type(T) is not str or not re.fullmatch(r'\d{4}-\d\d-\d\d \d\d:\d\d:\d\d(?:\.\d{6})?',T): raise Stop('timestamp')
    try: datetime.datetime.fromisoformat(T)
    except ValueError: raise Stop('timestamp')


def guard_postimages(pre, post, ids, T):
    ids = _fixed_set(ids)
    _timestamp(T)
    if pre['connection_id'] != post['connection_id']: raise Stop('connection')
    if pre['schema'] != post['schema'] or pre['columns'] != post['columns']: raise Stop('schema')
    before, after = _records(pre), _records(post)
    if set(before) != set(after): raise Stop('record_set')
    for i, row in before.items():
        expected = [list(v) for v in row]
        if i in ids:
            expected[1:6] = [['text','cancelled'],['text','cancelled']] + [['text',T]]*3
        if after[i] != expected: raise Stop('conservation')


def fixture_facts(c):
    """Finite selected actual build facts. Unknown introspection remains null."""
    facts = {'connection_id':id(c), 'vfs_binding':None, 'complete_registered_effects':None}
    facts['version_sourceid'] = _bounded_query(c,'SELECT sqlite_version(), sqlite_source_id()',1)
    for name, sql, bound in (
        ('compile_options','PRAGMA compile_options',512),
        ('database_list','PRAGMA database_list',3),
        ('functions','PRAGMA function_list',512),
        ('collations','PRAGMA collation_list',32),
        ('modules','PRAGMA module_list',32),
        ('page_size','PRAGMA main.page_size',1),
        ('page_count','PRAGMA main.page_count',1),
        ('max_page_count','PRAGMA main.max_page_count',1),
        ('journal_mode','PRAGMA main.journal_mode',1),
        ('temp_store','PRAGMA temp_store',1),
        ('indexes','PRAGMA main.index_list(lora_training_jobs)',32),
        ('index_columns','PRAGMA main.index_xinfo(sqlite_autoindex_lora_training_jobs_1)',32),
        ('foreign_key_list','PRAGMA main.foreign_key_list(lora_training_jobs)',32),
        ('query_plan','EXPLAIN QUERY PLAN '+ROW_SQL,32),
    ):
        rows = _bounded_query(c,sql,bound)
        facts[name] = rows if rows else None  # unknown PRAGMA may silently return empty
    facts['python_limit_API'] = {'getlimit':hasattr(c,'getlimit'), 'setlimit':hasattr(c,'setlimit')}
    return facts


def main_file_derivation(header, length, page_count, page_size, N):
    """Conditional main-only arithmetic, never complete D_B/physical admission.

    Header checks are necessary, insufficient for whole-file validity/cold closure.
    Full integrity, unique writer, same connection/build/effective cap, no sidecars,
    no concurrent change and every other required proof remain separate obligations.
    """
    if (type(header) is not bytes or len(header) != 100 or header[:16] != b'SQLite format 3\x00' or
            any(type(v) is not int or v <= 0 for v in (length,page_count,page_size,N))): raise Stop('main_format')
    p = int.from_bytes(header[16:18],'big');p = 65536 if p == 1 else p
    if p != page_size or p not in (512,1024,2048,4096,8192,16384,32768,65536): raise Stop('page_size')
    if header[18:20] != b'\x01\x01': raise Stop('wal_or_unknown_format')
    if header[24:28] != header[92:96] or int.from_bytes(header[28:32],'big') != page_count: raise Stop('header_epoch')
    if length != page_size*page_count or page_count > N or N > 4294967294: raise Stop('tail_or_cap')
    return {'current_complete_main_length':length,'page_size':page_size,'effective_N_required':N,
            'conditional_main_full_later':page_size*N,'full_D_B':None,'usable_for_admission':False,
            'missing':['full_file_validity_cold_epoch_same_connection_cap','all_companions_temp_partials_recovery','physical_allocation_and_shared_plan']}


def transaction_state(began, commit_attempted, commit_acknowledged, rollback_verified, active, *, rollback_attempted=False):
    """Diagnostic only, no execution/release; active is actual same-connection state.

    Lost commit acknowledgement remains unknown even when autocommit is on.
    No SQL/retry/rollback/close is performed here. Callers must keep event provenance.
    """
    if any(type(v) is not bool for v in (began,commit_attempted,commit_acknowledged,rollback_verified,rollback_attempted)) or (active is not None and type(active) is not bool): raise Stop('transaction_evidence')
    if rollback_attempted and not rollback_verified: return 'commit_unknown'
    if not began: return 'not_attempted'
    if commit_acknowledged and commit_attempted and active is False: return 'known_committed'
    if commit_attempted: return 'commit_unknown'
    if rollback_verified and active is False: return 'known_not_committed'
    if active is not None: return 'known_not_committed'
    return 'commit_unknown'


def error_record(stage, error, active):
    if stage not in ('begin','read','limit','update','commit','rollback','output','close'): raise Stop('stage')
    def number(name, high):
        value = getattr(error,name,None)
        return value if type(value) is int and 0 <= value <= high else None
    return {'stage':stage, 'code':'interrupted' if isinstance(error,BaseException) and not isinstance(error,Exception) else 'sqlite_error' if type(error).__module__=='sqlite3' else 'os_error' if isinstance(error,OSError) else 'error',
            'errno':number('errno',65535),'sqlite_errorcode':number('sqlite_errorcode',2**31-1),
            'sqlite_code_available':number('sqlite_errorcode',2**31-1) is not None,
            'transaction_active':active if type(active) is bool else None}
