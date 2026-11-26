# p2-02 independent delivery review

Verdict: FAIL
Review round: 1
Issue: [QA AID-187](/AID/issues/AID-187)
Coding: [AID-186](/AID/issues/AID-186)
Producer: [AID-146](/AID/issues/AID-146)
Date: 2026-11-26

Reviewed final candidate: **9abe3d1c3237791b684e3b9f5a692879df747361**.
Reviewed tree: **412b302f9a92b25d589ff53b2db4d143b326c4e3**.
Implementation base: **a8e57d90e4678565baec8cd4638c350c8dd11deb**.
Coding software freeze: **17e90a65b0b227900956e20b36d6ae8d3a8e4048**.
Unchanged task SHA-256:
`c43339e42ff1a160cfb87cf9742e53606db17c37ffe12439745b115ca6a8beda`.
The actual final candidate was pinned on this card before substantive review
([receipt](qa-evidence/pin-receipt.json)). The review/report/evidence commit and
tree are recorded in the native post-commit delivery to avoid a circular hash.

The ordinary suites pass, but four independent expected-feature assertions fail
on the exact candidate. These are observable gaps in the cleared contract.
Producer owns correction dispatch; QA has made no product or product-test repair.

## Findings

All source line numbers refer to the reviewed candidate. Reproducers are in
[adverse_probes.py](qa-evidence/adverse_probes.py); the complete latest failures
are [adverse-final.log](qa-evidence/adverse-final.log), exit 1, **four failed**.
They use synthetic inputs only. These review-only RED probes are outside the
ordinary product suites and are not certified passing guards or new skips.

### R1 / P1 / D1, D2, D4: supplied snapshots bypass the secrecy boundary

`backend/app/services/civitai_resource_install.py:248–253` accepts a typed
client-supplied snapshot after checking only base-label agreement and absence of
verification. `:342–346` publishes it. `resource_records.py:144` serializes that
snapshot without sanitization, and `:183`, `:215–218` return diagnostics, license,
triggers and recommendations directly. Only source_evidence gets read-time
sanitization. Typing alone does not constrain diagnostic strings to safe codes
and field names or remove signed locators from license values.

Reproduce `test_retained_install_snapshot_cannot_publish_signed_locators`: use
the real registered inspect/select result, add a synthetic signed proof URL to
resource_metadata.license.values and a token-bearing URL to a diagnostic field,
then call registered resource-install and GET resource detail. Install returns
200 and detail includes both `QA_SIGNED_LOCATOR` and `QA_DIAGNOSTIC_SECRET` with
their URL queries intact. Expected: reject or sanitize this input and exclude
these locators from the public record and diagnostics. Observed: both persist
through the new metadata path and are returned. This boundary is newly exposed
by resource_metadata; the old notes redaction does not cover it. No actual owner
credential was read or disclosed. The probe deliberately edits client input;
it does not claim that a live provider sent these fields.

### R2 / P1 / D1, D4: family filtering disagrees with the typed projection

`backend/app/api/resources.py:50–65` checks only JSON syntax and a string
base_model; `:87–90` filters that value. `resource_records.py:174–186` instead
validates the whole metadata schema and returns null family on invalid metadata.

Reproduce `test_invalid_typed_metadata_family_filter_agrees_with_detail`: store
an otherwise valid Pony snapshot with unsupported metadata version 999 on one
real ORM row. Detail returns model_family=null and invalid_metadata, as intended
for an incomplete row. GET /api/resources?model_family=sdxl nevertheless returns
that same null-family item with total=1. Expected: an exact family filter excludes
this row (total=0). This makes selection and pre-pagination totals unreliable
precisely for the malformed/incomplete records the task requires to stay readable.

### R3 / P1 / D1, D2: repeated installation clears a known AIR

`resource_records.py:118–123` correctly treats an incoming null identity as
unknown, but `civitai_resource_install.py:329`, `:332–341` subsequently assigns
that null to the authoritative AIR column. It does not preserve known identity
while filling only missing fields as shared publication does at
`resource_records.py:142–143`.

Reproduce `test_repeated_install_missing_air_preserves_known_identity`: acquire
and complete a synthetic resource with AIR urn:air:sdxl:lora:civitai:10@21.
Have a later provider metadata response omit that optional field; registered
inspect/select/install adopts the identical existing bytes and returns the same
ledger ID with 200, but its AIR is now null. Expected: preserve the known AIR
when the repeated result supplies no replacement evidence. The new authority
and publication contract promises stable known identity; missing is unknown,
not evidence for erasure. The candidate's existing test covers conflicting AIR,
but does not guard this missing-field case.

### R4 / P1 / D2 and preservation: same-ID retry destroys original notes

The new retry branch reuses a preexisting row at
`backend/app/services/civitai_resource_acquire.py:394–428`. Background completion
constructs fresh notes from the new request and assigns them at `:513`, `:532`;
the exception path also replaces them at `:539`. This overwrites the original
legacy evidence on the same authoritative ID.

Reproduce `test_legacy_retry_preserves_original_notes`: create a failed legacy
resource with matching immutable IDs/hash and notes containing historical
evidence PRESERVE_ME. Retry through registered acquire and execute its actual
background target with synthetic HTTP bytes. The same ID becomes installed,
but PRESERVE_ME and the original note body are lost. Expected: preserve the old
notes as immutable evidence, as required by the contract; augment the row without
discarding them. The isolated backfill preserves notes, but does not protect
this newly retained-row writer path. Before this change, acquisition created a
new retry row instead of overwriting the old row. This finding does not request
a new identity registry, lifecycle schema or production migration.

## D1–D5 assessment

| Item | Level | Verdict | Independent result |
|---|---|---|---|
| D1 | P1 | FAIL | Real ORM mapping, all four exact labels, malformed/unsupported/absent inputs, typed finite metadata, ordered triggers, license gaps, measured versus declared facts and identity conflict tests pass. R1 and R3 still violate snapshot secrecy/known identity; R2 exposes competing interpretations on malformed storage. |
| D2 | P1 | FAIL | Both registered writer paths, strict non-first selected version/file, real Settings/file resolver, actual background target, retry/failure/reuse/conflicts/status and ledger execute successfully in fixtures. R1, R3 and R4 demonstrate unguarded publication/reuse failures. |
| D3 | P1 | PASS within isolated migration boundary | Exact base ORM schema comparison and full old-schema/value audit pass. All 16 old tables including sqlite_sequence, eight resource rows, all five populated alias/history tables, original notes, duplicates, malformed/conflicting/unsupported/offline cases and synthetic file bytes survive startup/backfill/repeat. R4 separately blocks preservation through retry. No registry certification is added on this failed delivery. |
| D4 | P1 | FAIL | Registered HTTP/OpenAPI, all filters, ascending pagination, filtered totals, bounds, 422/404/hint and no-write/body/provider guards pass their existing cases. R1 and R2 fail actual HTTP security/filter cases. |
| D5 | P1 | FAIL as acceptance gate | Exact source/artifact restoration, seven effective mutations, restored feature/full suites and all 22 prior contracts are reproduced. Existing guards miss the four actual violations above; the independent RED probes prevent a false PASS. No new registry item is certified. |

## Commands and evidence

Persistent worktree:
`/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-187-qa`;
branch `aid-187-exact-review`, created at the pinned final candidate. All QA
evidence below is in [qa-evidence/](qa-evidence/). The runner records exact argv,
cwd, allowlisted environment, time, exit status, raw/saved log hashes and actual
guard/import receipts. Invocation:

```bash
python3.11 -B docs/tasks/p2-02-resource-record/qa-evidence/run_checks.py LABEL PATHS...
python3.11 -B docs/tasks/p2-02-resource-record/qa-evidence/run_standing.py
python3.11 -B docs/tasks/p2-02-resource-record/qa-evidence/check_faults.py
```

The adverse command is explicitly expected to exit 1:

```bash
python3.11 -B docs/tasks/p2-02-resource-record/qa-evidence/run_checks.py adverse-replay docs/tasks/p2-02-resource-record/qa-evidence/adverse_probes.py
```

The runner's normal zero-exit expectation then raises after saving the four RED
results. The recorded adverse/adverse-final invocations instead call run(...,
expect=1), so orchestration succeeds while preserving pytest exit 1. Do not count
this orchestration success as a passing feature result. Replaying requires a new
PAPERCLIP_RUN_SCRATCH_DIR and the dedicated environment described in
environment.json and the Coding reproduction guide; recorded scratch directories
are ephemeral. Use fresh labels to retain old results.

| Label / scope | Independent result |
|---|---|
| backend-full, before mutations | 2,039 passed / 124 existing skips, 76 warnings, 46.34 s |
| mcp-full, before mutations | 666 passed / four existing optional-export skips, 72.30 s |
| adverse, then adverse-final after exact restoration | Four failures each; R1–R4 above |
| export | 93 passed; current Backend revision/multi-LoRA/lifecycle/health producers |
| cross-layer | 73 passed; separate MCP consumers of fresh outputs |
| registry-mcp | 412 passed; standing MCP/PNG/stdio/smoke/independent content guards |
| fresh-wait | 12 passed; fresh current Backend child export, registered MCP reader |
| retained-provider-guards | 19 positive credential/cookie/header/deadline regressions passed |
| schema-audit, schema-diagnostic | Migration passed; independent raw DDL equality assertion failed only on documented trailing whitespace. The second diagnostic isolates that difference. Both failed attempts are retained. |
| schema-final | Two passed: whole-schema/value migration and independent exact-base schema authority after trailing-whitespace normalization only |
| restored-feature | All 61 new feature cases passed after the seven mutations |
| backend-final, after restoration | **2,039 passed / 124 existing skips**, 76 warnings, 47.14 s |
| mcp-final, after restoration | **666 passed / four existing optional-export skips**, 73.67 s |
| source audit | All **2,710** final tracked blob fingerprints, no ordinary path suppression; **412** protected Backend/MCP/replay source bodies exact after restoration |
| registry rebuild | All **22** prior active rows remain byte-exact; no addition, deletion, supersession or new skip |

All long suites use per-test --timeout=60, unique guarded roots under run-owned
scratch, no pytest cache/bytecode and pinned QA imports. A fresh ignored Python
3.11.15 environment references the three existing dependency sites read-only;
no dependency install or canonical environment change. environment.json records
versions, sys.path, .pth bodies and guard fingerprint. The .pth audit guard denies
private key/.env reads, non-scratch writes/DBs, remote DNS/network and live service
ports. Actual denied probes are in guard-activation.json; those three deliberate
events are distinguished from test receipts. Ordinary test receipts have no
blocked events. The activation probe ran after the first full-suite launches;
those processes still independently record the loaded guard and pinned imports.
Isolated -I/-S children use the repository's own offline_pytest guard, not .pth.
Current exports (20 payloads), nested receipts and whole synthetic schema/value
audit are retained. A stat call is allowed; no model-body read is allowed during
resource reads/startup/backfill.

### Fault sensitivity and exact restoration

QA inspected and reran Coding's seven production faults sequentially using the
QA runner; no test ran against shared main or overlapped a mutant with a registry
or full-suite run. faults.json records unique anchors and original/mutant/
restored hashes. Each failure was at the intended observable feature assertion,
not an import/setup/fingerprint error:

| Fault | Actual failures |
|---|---|
| Map NoobAI to null | One exact-mapping assertion |
| Fabricate verification without evidence | Two declared/legacy honesty assertions |
| Bypass acquire publication | One registered acquire selected-snapshot assertion |
| Bypass install publication | One registered non-first install selected-snapshot assertion |
| Destroy backfill notes | One complete old-value/notes assertion |
| Remove SQL pagination | Two page-size/query-bound assertions |
| UPDATE during list | One actual SQL write-denial assertion |

Every mutated file was restored byte-for-byte in finally; source fingerprints,
61-case GREEN and the final complete suites followed. These nine meaningful
failures demonstrate the guards they exercise, not completeness against R1–R4.

## Boundary review and preservation

Fixture substitutions are explicit: per-test SQLite/in-memory sessions; complete
synthetic previous-schema SQL plus constrained alias/history sentinels; scratch
paths and tiny synthetic model bytes; environment-selected synthetic key files;
HTTPX external wire responses; deferred thread scheduling that calls the actual
background target. Settings, credential file resolver, provider operations,
version resolution, schemas, ORM, publication, mapping and successful results
are real. The adverse cases additionally supply one malformed stored snapshot,
one optional AIR omission, one edited untrusted install snapshot and one failed
legacy row. No injected settings/key/domain transport manufactures production
configuration success. Existing old unit tests retain their documented fixtures.

The frozen legacy normalizer remains an explicit recipe/AIR/Anima adapter;
the Phase 2 mapping table is exact and separate. Static inspection confirms the
two resource constructor sites and alias/ledger callers in legacy-inventory.md
and evidence/legacy-callers.json; these are dependencies, not live use or removal
proof. Workflow graphs/training behavior and 31 MCP names/risks are unchanged.
The one old test edit moves Illustrious into the provider fixture before inspect;
its lock assertions are preserved. No meaningful assertion was removed, relaxed
or newly skipped. Full suites and fresh standing producers/readers cover all
22 prior certified items. The registry builder excludes this FAIL report, so no
new coverage row is added. Registry structural generation itself is not a test.

Whole-schema evidence has 16 tables/14 populated sentinel rows including sequence
state; the only startup delta is nullable downloaded_resources.metadata_json.
Backfill changes that field only, preserves old notes/IDs/counts/aliases/history,
diagnoses incomplete/conflicting/duplicate/offline evidence and is idempotent.
The independent schema check loads exact pre-task models into a new declarative
Base without importing application Settings. Initial raw SQL comparisons exposed
trailing whitespace from Coding's documented fixture normalization; the final
check strips only line-ending whitespace and still compares every statement.
Guessed nonexistent test_support/offline_pytest paths were resolved with the
tracked inventory and actual helper references; those read errors are not tests
or product findings. No other QA product-test failure or harness overlap occurred.

Acquisition failure, duplicate submission, same-ID status/retry and synthetic
installed-file retrieval were exercised. No new cancellation/job API is in this
increment; live cancellation, persistent download accounting and real artifact
retrieval qualification remain later work. Existing PNG/smoke regressions passed.

## Delivery integrity, limits and disposition

QA independently downloaded all four official Coding uploads and verified their
exact bytes/sizes/hashes, the uploaded manifest against Git, **139 indexed
payloads / 140 archive members**, **136 exact changed Git bodies** and all
**2,710** final fingerprints. Actual downloaded bundle and full-index patch each
restore the exact candidate/tree in a new bare store; git fsck --full succeeds.
The delta requires the exact published base and its existing shallow boundary:
seed it with an explicit prerequisite ref and --update-shallow. It is not a
standalone history backup. coding-integrity.json records the independent result;
Coding's failed restoration attempts remain in its official index. QA's own
report/evidence/registry delta and official upload receipts are in native delivery.

**Offline:** current source/ORM/registered HTTP fixtures, synthetic bytes, full
suites, independent adverse observations, mutation/restoration and package checks.
**Running service:** no production probe, startup/restart, deployment or backfill.
**Provider/generation:** no real key read, live provider request, model download,
registration or generation. **Retrieval:** synthetic fixture bytes and official
Paperclip attachments only; no live model/Gallery bytes. Frontend is unchanged
and was not rerun; Windows is untested. Credential-origin/redirect/stateless-cookie/
deadline/closure properties were exercised offline by current retained guards;
the earlier live HEADs remain historical, not fresh evidence here.

Shared main and all 13 concurrent memory bodies are untouched. Private settings,
key/runtime/snapshots/backups, canonical environments, existing worktrees and all
models/datasets/outputs/Gallery records are preserved. QA commits only this report
and QA evidence; REGISTRY.md is regenerated with identical bytes. No product/test
repair, feature merge/push, parent status write, owner interaction or aesthetic/
phase acceptance. p2-02 history is kickoff1 CLEAR, delivery review1 FAIL with four
P1 findings/one rejected delivery. p2-01's original R1 FAIL/correction1/review2 PASS
and First check's one bridged chain/20 interventions/77 overlapping units/five
missing earlier hashes remain unchanged.

QA completes its own card with this actual FAIL. Producer reads the report and
owns correction dispatch and another exact-final-commit review. A changed
candidate requires a new independent review before feature integration.
