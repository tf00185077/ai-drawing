# M2 exact408 SQLite contract — retained unavailable profile

This helper is outside fixed110 and starts at accepted M1 `4ba42857162f1e751673f288701af6caa74430bc`. No product file, initializer, Settings, database module or schema is adopted. The task permits new synthetic SQLite component fixtures; it supplies no actual database values, cold epoch, DB-setting grant or operation grant.

## Callable outcome

Add this directory to `sys.path` and import `contract`. Import uses only standard-library modules and opens no database. Both `read_exact408(connection, window, administrative_time)` and `execute_exact408(connection, window, administrative_time)` return the frozen `Refusal` dataclass:

- `status='unavailable'`, `code='complete_sqlite_profile_unavailable'`, `commit_state='not_attempted'`.
- `database_access_attempted=false`, `full_db_bound=null`, every protection/source/start/retry flag false.
- Six exact missing obligations are in `MISSING`: cold file/epoch/writer/path closure; same-connection native/registered/external binding; supported required limit APIs; complete native write bounds; a complete admitted shared M1 plan; actual schema/preimages/exact settings grant.

These two calls do not inspect any argument, open or query SQLite, attempt BEGIN/UPDATE/COMMIT/ROLLBACK, write a setting, invoke a Window callback, reserve/charge a slot, emit a local receipt, or close a borrowed handle. A poison-object control verifies no argument access, in addition to a real connection's empty SQL trace, unchanged main bytes, shared-plan snapshot and untouched active journal. The return is an in-memory refusal, not a successful local durability receipt. Python/OS failure while constructing/returning any result is not certified away.

There is no supported executable profile, no caller `safe` boolean/cap/profile dictionary, and no hidden DML callback. `UPDATE_SQL` is retained as exact intent for the synthetic harness and future review; the public executor never executes it. Absence of a reachable mutation is deliberate: this component cannot bound and precharge all native effects before BEGIN or a setting write. Constructing an M1 Window itself has custody-directory effects; the M2 API does not create one.

## Exact data and bounded synthetic reader

`exact408.txt` is the unmodified sorted ASCII UUID+LF set from request revision `ec799cc5`: 408 unique IDs, 15096 bytes, final LF, SHA256 `2a87d402ef171ba200b68b6db79c4656cfefb12449141742b891e7a429bec9a4`. `exact_ids(raw)` and both full guards rebind that fixed set. No normalization/subset/expansion is accepted.

`fixture_snapshot(c)` is an **explicitly synthetic evidence API**. Call only from the reviewed pre-isolated harness against its own fresh SQLite connection. Also add accepted `tools/m1_bounded` to `sys.path` for its unchanged owned-finalization primitive. This reader is not an alternative operational entry point and does not produce admission evidence. Its exact schema is the literal `FIXTURE_SCHEMA`, with all 12 columns: job_id, status, stage, cancel_requested_at, completed_at, updated_at, params, recipe, reservation, serial, model, dataset. It is not a production schema inferred from an ORM. Any additional/changed schema, explicit index, trigger, CHECK, generated column, foreign-key DDL or table refuses; only its exact table plus automatic primary-key index is accepted. All record fields, including arbitrary scalar params/recipe values and binary asset-related values, are retained rather than decoded as JSON or reduced to a digest.

Fixed query sequence:

```sql
PRAGMA database_list;
SELECT type,name,tbl_name,rootpage,sql
FROM main.sqlite_master ORDER BY type,name LIMIT 33;
PRAGMA main.table_xinfo(lora_training_jobs);
SELECT "job_id", "status", "stage", "cancel_requested_at", "completed_at",
       "updated_at", "params", "recipe", "reservation", "serial", "model", "dataset"
FROM main.lora_training_jobs ORDER BY job_id COLLATE BINARY LIMIT 413;
```

The fixture permits exactly main in database_list. Unknown attached/TEMP state refuses. Schema is limited to 32 returned objects; columns to 32; records to 412, so the 413th sentinel refuses. Each returned cell is checked after fetch: null; signed 64-bit integer (bool excluded); finite IEEE float represented by `float.hex`; UTF-8 text up to 4096 bytes; bytes up to 4096 represented by hex. Null, empty text, empty blob, integer/real, embedded NUL and binary values remain distinct. Invalid UTF-8 raises the actual binding error and is not coerced. Row width must be exactly 12. `encode_records` validates types and writes JSON pieces only within a 4194304-byte aggregate ceiling. These are refusal ceilings for the fixture representation, never proof a production value fits. Native fetch may allocate/materialize before Python sees a value; this is a separate reason the operational reader remains unavailable.

`fixture_facts(c)` collects only selected same-connection fixture build/schema/limit facts. Source contains the complete literal query catalog: version/sourceid, compile_options, database_list, function_list, collation_list, module_list, main page_size/page_count/max_page_count/journal_mode, temp_store, table index_list/index_xinfo/foreign_key_list and EXPLAIN QUERY PLAN for the fixed reader. Every query has finite row ceilings and the same returned-cell checks; cursors receive one owned close attempt using accepted M1 `finish_owned`. Unsupported/empty PRAGMA results stay null, since an unknown PRAGMA can silently return nothing. Enumeration is not proof of a function's effects, overriding collation semantics, extension/VFS configuration, native external writes or all destinations: `vfs_binding` and `complete_registered_effects` stay null. The selected vendor build's compile options, even OMIT_LOAD_EXTENSION, do not turn unknown native closure into absence.

Snapshots retain actual connection identity (process-local `id(c)`, not a transferable FD/VFS certificate), complete schema/rootpage/columns and every typed value. `guard_preimages` requires full equality, exact408 present and queued/queued, and all outside rows terminal. `guard_postimages` requires the same connection/schema/record set and every value equal except the exact five fields. `T` must be a valid UTC-naive administrative string `YYYY-MM-DD HH:MM:SS[.ffffff]`; the function cannot certify clock provenance or owner approval. No digest of selected columns substitutes for conservation.

The successful synthetic SQL control uses ONE actual connection/BEGIN IMMEDIATE, reads fresh complete preimages, checks all 408 rowcounts, makes exactly 408 separately bound updates, checks full conservation before one COMMIT attempt, and observes autocommit afterwards. Its effects are harness operations authorized on fresh fixtures. **It is not an executable bounded B profile**: the harness does not pretend to precharge/confine SQLite native writes, and its direct transaction does not call the unavailable public executor.

## Main and companion bound derivation

`main_file_derivation(header100, complete_length, page_count, page_size, N)` rejects unsupported format/version, page-size interpretation, invalid header counters/page-count, cap shortfall and any extra tail/partial page. The main-only conditional arithmetic is `page_size * N`; `usable_for_admission=false` and `full_D_B=null` remain explicit. Header checks alone do not establish full B-tree/file validity or a consistent cold epoch. A complete valid main file, no tail, unique writer, exact connection/build, current pages <= effective N and full native path/lifetime proof are still required. WAL format refuses this narrow main-header interpretation. No file truncation makes a counterexample fit. Allocation estimates and file logical length are distinct.

On the actually selected /usr/bin Python 3.9.6 / SQLite 3.51.0 fixture, queried prior max_page_count was 1073741823; setting 4 returned 4 and a separate same-connection query returned 4. Another newly opened connection queried 1073741823. Thus the PRAGMA setter returns an effective value, not sqlite3_limit's prior-value convention; the fixture cap is connection-local here. No reopen durability claim extends to other builds. The selected Python connection exposes neither getlimit nor setlimit. No private CPython struct, ctypes pointer, second library or different connection is used to fabricate that access. sqlite3_limit prior/effective/lifetime behavior is consequently **unavailable in this component**; its official C contract does not fill the missing API.

A 21-page capped 86016-byte fixture produced an observed 53864-byte rollback journal; repeated WAL fixture transactions produced WAL 267832 and SHM 32768 while the main cap remained 21 pages. The actual companion bytes are retained before their normal SQLite lifetime cleanup. These are observations/counterexamples to main-only closure, not journal/WAL peak bounds or a measurement-based quota. The main-only future example 4096*31=126976 differs from current 86016; it does not select production N. Appending four own-fixture tail bytes refuses, even though logical page_count is unchanged.

Complete pre-mutation accounting would need, for **each** category, exact build/schema/connection/epoch, path/owner, full logical demand, finite enforcement or proved absence, lifetime including partial/error/recovery state, and admitted immutable M1 reservation before effects:

| Category | This source's result |
| --- | --- |
| Full later main file/header/tail | Conditional arithmetic only; actual validity/epoch/effective cap not supplied |
| Rollback journal/header/sector padding/spill/recovery | Real fixture observed; complete native bound/enforcement unavailable |
| WAL and SHM, checkpoint/recovery and retained later files | Real fixture observed; full bound/path/lifetime unavailable |
| Superjournal and each attached DB | Unsupported schema/ATTACH refuses; no production absence proof |
| Statement journal | No full operation/build bound; not set to zero from main cap |
| TEMP database, materialization, transient indexes/sort, other query internals | Native allocations/path/spill before Python checks unbounded by this adapter |
| VACUUM/transient DB and arbitrary schema/UDF/collation/virtual-table/extension/native destinations | Not admitted or executed by the public API; arbitrary existing connection closure unknown |
| Settings/header/config effects, rollback/failure partials | No production setting grant; exact native complete effects unknown |
| Output/receipt/metadata/control and complete post-B copies | Must be in the one shared M1 plan before corresponding effects; existing M1 API does not fence SQLite |
| Physical allocation/free space/shared-pool effects | Not proved by logical values, hooks, current size or file fsync |

Therefore no complete D_B is derived. No arbitrary overhead, journal_size_limit, construction limits, observed-size maximum, page difference, reserved copy credit, refund or per-file ledger fills the gap. The full later D_B remains separate from post-start D_S and control M in `2P+D_B+D_S+M<=120GiB`. Shared physical free-space-once/20percent policy is unchanged. No VFS, OS quota, framework or installed dependency is introduced.

## Exact future setting grant fields — no current values/grant

A future separately reviewed grant must bind operation/request revision and exact408 SHA, actual data/setting owner and named operator, epoch/window and approved T format; Python binding/library/sourceid/compile-options/VFS and the single connection lifetime; file identity/complete header/length/validity and all named companion/temp/external destinations; complete schema/all columns/index/trigger/check/generated/FK/UDF/collation/module effects; category/schema, prior integer, proposed integer, mechanism, same-connection effective query integer, lifetime/reopen semantics, persistence/header/config side effects; complete affected paths/logical/native/physical demands and shared M1 reservation slots; error/recovery outcome and post-B protection/reconciliation authority. All actual values are absent here. A synthetic N, task admission or old administrative intent is not a DB-setting grant. No journal_mode/page_size/temp_store/locking/synchronous/checkpoint/VACUUM/schema/Settings change is proposed for production.

This input description is not a new admission form or a requirement to possess a future task's own fresh receipts before task admission. The future authorized task obtains its bounded evidence, then honors the actual execution gates. Merely filling these fields cannot enable this unavailable implementation.

## Transaction/errors and output preservation

`transaction_state` is a conservative diagnostic function taking actual same-connection `in_transaction` observations and explicitly attributed event evidence; its booleans are not an execution permission or closure proof. Successful COMMIT acknowledgement plus autocommit distinguishes known_committed. A lost COMMIT acknowledgement stays commit_unknown even if autocommit is now on: COMMIT and automatic rollback both enable autocommit. Before any COMMIT attempt, an active transaction is known uncommitted; verified rollback/observed automatic rollback without commit can establish known_not_committed. Missing observation or a failed/unverified attempted rollback remains commit_unknown. No SQL or retry is performed by the classifier. `error_record` retains fixed stage/code, sanitized numeric errno/SQLite code if exposed and actual transaction state; it never retains the exception text. This binding does not expose SQLite numeric error codes, so they remain null, not parsed/invented from text.

Controls exercise genuine SQLite constraint failure with an active transaction, real SQLITE_FULL behavior (numeric code unavailable), real progress-handler interruption and automatic transaction rollback, one real commit followed by injected caller acknowledgement loss, and an actual authorizer-denied ROLLBACK with the journal retained at observation. Denied rollback is an explicit fixture fault, not physical IOERR/power-loss evidence. No COMMIT/UPDATE retry occurs. The public API owns no DB handle; each fixture connection receives one normal harness close. Successful close may perform SQLite's normal internal rollback/checkpoint/unlink; this is fixture lifecycle, not a recovery grant or budget refund. Harness copies of observed companion bytes are retained as evidence, not certified restores.

The unchanged accepted M1 Window is used for scoped new output controls, not an old-suite replay. Actual `part`, failed payload/receipt, original errno28/known_committed, full 276 charge plus unused19 reservation, failed local receipt and bounded fallback survive. Genuine KeyboardInterrupt propagates after the M1 owned stream cleanup, with its partial and stop latch. A successful/possible commit with failed post-B output leaves source/start/retry false. A separate reconciled forward-recovery grant is required; no old DB/ledger restore or blind B resend follows.

## Reproduction and limits

```text
/usr/bin/python3 -I -B tools/m2_sqlite/run_tests.py <new-empty-task-owned-parent>
```

Create the parent physically before invocation. Runner sets synthetic cwd/TMPDIR and clears inherited environment before sqlite3/candidate/M1 import, blocks product Settings/app/SQLAlchemy/conftest, networks and subprocesses, and restricts SQLite opens to its scratch parent. It blocks audited writes outside the fixture and excluded R/V/C reads. Python audit hooks do not confine native SQLite/VFS/OS operations. TMPDIR is selected before import, not claimed to prove every possible native temp root. This limitation is reflected in the refused operational profile. No production/private file or service is inspected to fill unknowns.

Retain fresh fixtures/partials/logs; do not rerun in an existing parent or delete prior evidence for credit. The final targeted suite has 15 methods. Earlier missing-interface RED (1 failure, 10 skipped), audit byte-path harness error (8 errors), corrected development 11 PASS, foreign-connection regression RED, 14 PASS and rollback-interface RED remain separately retained. Counts overlap and must not be added. Whole-product/kit/old M1/G09 suites are not rerun.

Primary mechanism sources: [max_page_count PRAGMA](https://www.sqlite.org/pragma.html#pragma_max_page_count) defines the database-page cap; [SQLite temporary files](https://www.sqlite.org/tempfiles.html) describes additional native destinations and version-sensitive behavior; [sqlite3_limit](https://www.sqlite.org/c3ref/limit.html) returns the prior value and queries with negative newVal; [transaction errors](https://www.sqlite.org/lang_transaction.html#response_to_errors_within_a_transaction) may leave or abort the transaction; [autocommit](https://www.sqlite.org/c3ref/get_autocommit.html) distinguishes active state but not lost commit outcome; [Python 3.9 sqlite3](https://docs.python.org/3.9/library/sqlite3.html) documents the supported binding. Actual fixture files/queries establish the observed component values, not documentation or another library.

M1 full endpoint/native/physical closure, M3 launcher/native write set, A1 genuine actor/manual/caller receipts and I1 actual complete logical/physical numbers remain unpassed. AID55's two genuine partials/no-third/no-refill hold is unchanged. Four policy facets, exact408/fixed110/five fields, dual cold copies/isolated restore/post-B barrier and no-resend/forward-recovery gates remain unchanged. There is no source adoption, installation, deployment, service operation, generation/training/resource acquisition or aesthetics acceptance. Author completion returns the frozen package to the existing independent QA/Producer path.
