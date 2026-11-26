# p2-03 Coding delivery

Coding [AID-208](/AID/issues/AID-208) delivers the unchanged D1–D5 implementation
for independent exact-candidate [QA AID-209](/AID/issues/AID-209).
[Producer AID-146](/AID/issues/AID-146) owns findings and acceptance. This is a
Coding delivery, not an independent PASS, merge, runtime deployment or Phase 2 exit.

## Identity and freeze

| Input | Exact identity |
|---|---|
| Fixed published handoff | `aefb8318bcdd7942b5c2be14b1c9fc42b33d7556` |
| Handoff tree | `47cb08f3068f0730edb56f3be56d6bff3c4667ab` |
| Unchanged task SHA-256 | `285af6d1419f70e9c5e3b4a7d86f64f5913e6dfebb24e0897d3a67fb21ca32f0` |
| Actual kickoff1 CLEAR | QA `9dfdf9f175a1ea130bdb66c2aa561caebf8d4c42` |
| Final software/tests/feature-helper/topic freeze | `b5af8b691a677a98786f3f371bda1366cb7418a2` |
| Freeze tree | `fe43c5633f3efe5bbcde1c4dcc2ee2cd6bcbc4d3` |
| Persistent branch | `aid-208-p2-03-bounded-download` |
| Persistent worktree | `/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-208-bounded-download` |

**Actual delivery FINAL full SHA/tree** are bound to this exact Git manifest body
by the official post-commit `delivery-index.json` and Coding's final native comment
on [AID-208](/AID/issues/AID-208). Those are the review pin, not the freeze ancestor.
Embedding a commit's own hash inside its tree would be circular; the receipt records
FINAL, tree, manifest bytes/SHA-256 and the complete final inventory together.
Only reporting/evidence descendants follow the freeze. A generated Python cache
accidentally staged with evidence is excluded from delivery; no Python source,
feature test/helper or topic changes after this freeze.

## Result and effective policy

Both retained callers use the stock helper with positive effective Settings,
exact selected size/SHA/type gates, destination observations, associated resume,
verified no-overwrite publication and truthful existing-ID failure. No new schema,
queue, scheduler, MCP tool, dependency, worker or UI behavior is introduced.

`CIVITAI_DOWNLOAD_MAX_BYTES=8589934592` and
`CIVITAI_DOWNLOAD_FREE_SPACE_FLOOR_BYTES=21474836480` are the configurable 8 GiB/
20 GiB defaults. Environment decimal integers are accepted; direct boolean/float/
null, missing, malformed, zero and negative policy values fail rather than becoming
unlimited or larger. Tests use explicit positive small values and real environment
loading as well as direct invalid fixtures. `size` is exact provider bytes when
non-null; otherwise `sizeKB × 1024` must yield an exact positive integer using the
numeric decimal spelling. Inspect, acquisition and typed snapshots share the same
interpretation. Fractional bytes are never rounded or truncated.

Ordinary checkpoint/LoRA selection requires `.safetensors`, case-insensitively,
and selects it ahead of a pickle primary. Malformed primary refusal is preserved.
All selected Anima package components pass admission before any row mutation;
their existing format eligibility and diffusion/text-encoder/VAE routing remain.
Known acquisition rows retain their recorded storage path if configured roots
change. Existing exact reuse/adoption is explicit verification, not replacement.

The [download topic](../../civitai-downloads.md) specifies effective policy, selected
size, admission, resume association, stable errors, ownership and practical limits.
The [caller/dependency inventory](implementation-evidence/caller-inventory.md)
includes registered MCP/HTTP, generate-like, both writers and all public readers.
The [compatibility inventory](implementation-evidence/compatibility.md) lists every
changed old assertion/fixture and its replacement. No feature test is deleted or
new skip added. The sole family map, recipe/alias/variant behavior, accepted
credential boundary, raw internal locators and all 31 MCP names/risks are retained.

## D1–D5 matrix

All items are P1. These are Coding evidence, with independent D5 review pending on
the separate native QA card. Test fixtures substitute external HTTP I/O, deterministic
background scheduling and controlled free-space observations; Settings, configured
synthetic files, ProviderOperation/transport, schemas, registered routes/tools,
ORM commits/reloads and temporary filesystem operations are real.

| Item | Check | Feature evidence, layer and real boundary |
|---|---|---|
| D1 | test | `backend/tests/test_civitai_provider.py::test_p203_production_admission_gates_have_no_body_partial_or_row`: 12 registered MCP/HTTP cases with actual file resolver/Settings and body/row/part counters. `test_civitai_download_bounds.py` covers metadata/policy/type/default/environment matrices and shared exact size. `test_civitai_easy.py::test_anima_package_checks_every_component_before_any_admission` covers last-component cap/space refusal and retained other-kind formats. Full writer/old-storage/adoption/identity guards remain. |
| D2 | test | `test_civitai_download_bounds.py` exercises actual incremental files, cap before violating write, decreasing/unknown/failed space, complete Content-Range/Content-Length/body coverage, safe prefix/full-file hashes, owned 200, valid 206 and foreign/linked/changed/legacy preservation. `test_civitai_download_callers.py::test_real_row_resume_association_survives_interruption_and_retries_same_id` proves both callers record and reuse actual ORM association after interruption, including unknown existing identity augmentation and bad-range refusal. |
| D3 | test | `test_civitai_download_callers.py` covers both registered admitted outcomes, old-note bytes/known identity, same-ID current status, exact measured success, racing target, identical-byte target appearing after admission, compensation with and without replacement, and storage-root changes. Helper tests cover part replacement, linked data and atomic no-overwrite. Open-writer unlink denial is emulated; no native Windows result is inferred. |
| D4 | test | Current `test_civitai_provider.py` plus immutable p2-01 independent guards retain real configured-file precedence, final prepared headers, allowed origins/redirects, deadline/backoff and closure. New callers check byte/space/hash/range/collision/body/403 exits and closure through the real ProviderOperation path. Helper deadline covers disk/hash/publication. Complete current p2-01/p2-02 regressions run in full suites. |
| D5 | test + delivery | [Five actual faults](implementation-evidence/final-fault-audit.json) fail meaningful assertions for byte, space, range, no-overwrite and size/hash, with exact finally restoration then GREEN. Current affected/full Backend/MCP, fresh exports/readers, standing consumers, 72 unchanged registry rows, hashes/modes, raw attempts and official replay artifacts are supplied. Independent exact-FINAL fault reproduction/verdict belongs to AID-209; Coding does not self-certify that gate. |

## Execution and ownership traces

[33 parsed observations](implementation-evidence/outcome-traces.json) retain the
actual stdout source-log hash. They cover bytes accepted before a refused chunk,
decreasing space, range/closure/refusal, existing-ID/old-note outcomes, compensation,
actual association fingerprints and successful 2 MiB 200/206 round trips. The full
raw [456-case affected log](implementation-evidence/final-affected.log) remains.

Resume proofs live only under the existing row's reserved acquisition evidence:
provider/version/file/resource identity, selected hash/size, device/inode/size/
mtime/ctime and full prefix hash. A path/length or legacy part alone is insufficient.
Both callers source proof from the raw Backend row; outgoing normalized paths are
never fed back as executable authority. Unknown legacy/foreign/changed parts are
retained/refused. New parts use exclusive creation and no-follow opening; held
file/path ownership is checked around writes, hashing, publication and cleanup.

The helper rejects chunks before exceeding declared/cap totals, admits remaining
bytes plus floor on the destination filesystem and checks floor before every
write. Unknown observations fail. These are checks, not cross-process reservations.
206 coverage must exactly match prefix and selected total; owned 200 re-admits the
full remaining write before truncation. Exact final size/hash precede same-directory
atomic hard-link creation of the final name. A racing file/symlink survives; there
is no replacement fallback. The writer closes before verified part-name removal.
Cleanup verifies a newly created part's current ownership and prefix digest;
preexisting/foreign/changed data are retained. Retained compensation verifies the
publication identity before deletion. A deadline preventing verification leaves data
rather than extending the deadline for cleanup.

Both callers commit admission on the existing resource authority and record current
failed/error state on that same ID after failure. Retained errors include the ID.
Old notes stay byte-exact; valid known identities and genuine historical measured
facts are not rebound. Verification attaches only to an unchanged verified
publication/adoption. A permanently unavailable DB may prevent failure persistence;
the caller returns failure/ID rather than successful installation. Current policy,
range, ownership and verification errors are fixed sanitized codes/messages with
recovery guidance, documented in the topic. No deterministic refusal is a hidden
network retry or second download submission.

## Current qualification

All following rows apply to final frozen source, with pinned worktree imports,
read-only dependency sites, explicit isolated roots, `--timeout=60` per test and
600-second outer bounds. Raw command/environment/import/hash/closure receipts are
beside each log; [verification index](implementation-evidence/verification.json)
binds them. The 124 Backend and four MCP skips are the existing platform/optional
fixtures. Existing warnings remain; no new unexplained skip or test deletion.

| Check | Actual result |
|---|---|
| Full Backend | 7138 passed, 124 existing skips, 112 warnings; 191.92 s |
| Full MCP | 666 passed, four existing skips; 88.11 s |
| Affected production/compatibility tests | 456 passed; 14.31 s |
| Final five faults | Byte 1, space 1, range 7, no-overwrite 1, size/hash 2 assertion failures; 12 total, all expected exit 1 |
| Exact restored feature run | 155 passed; all five finally-restored SHA-256 values match |
| Fresh Backend producers / separate MCP readers | 93 / 73 passed; 19 indexed fresh exports |
| Standing registered MCP/PNG/stdio/content/smoke | 412 passed; 86.56 s |
| Retained independent provider / fresh wait | 19 / 12 passed |
| Registry/history/shared preservation | 72 rows, 7394 prior task bodies/modes, 14 shared memory bodies unchanged |
| Complete freeze inventory | 8244 exact Git-body fingerprints/modes, including reporting/history already present at freeze |

The first qualification at `ba4d9e5a48ac9d0bdd2c14e51680782ed9a0d42a` also passed
Backend 7135/124 and MCP 666/four. It is retained as intermediate history, not reused
as final qualification. Three subsequent guards reproduced open-writer unlink
refusal and two recorded-storage cases. The final freeze fixes those cases, adds
observable traces and repeats all five faults, affected/full suites and fresh
exports/consumers. Final product/test/helper/topic bodies stay exact thereafter.

## Attempts, deviations and practical limits

[Attempt ledger](implementation-evidence/attempt-ledger.json) retains every raw run.
Initial TDD: 33 helper and seven caller failures; later guards expose late adoption,
racing-part retry, metadata-proof mismatch, failed space observation, missing
existing identity, open-writer cleanup and storage reuse. All are fixed and current
guards pass. Affected runs recorded nine then ten obsolete-fixture/compatibility
failures before their explicit replacements and malformed-primary correction.

Setup mistakes are distinct: one affected command named nonexistent
`test_resource_records_api.py` (exit 4); new caller fixture attempts initially
stacked two HTTPX transport adapters, then omitted required seeded `source_url`.
Both fixtures were corrected without weakening behavior assertions. First-stage
TDD records identify a dirty working tree via HEAD/imports and preserve raw results;
they do not claim a complete loaded-body inventory. Final qualification records
include every ordinary code-body hash plus the complete frozen tree inventory.
Generated Python caches accidentally included with evidence are removed from the
final Git payload; original commits/raw records are retained, no history rewrite.

No specification/scope deviation. The explicit compatibility changes are those
required by the cleared task. The helper's former write/replace flow is replaced
with one ownership/response/descriptor cleanup boundary; policy/size logic is a
small shared module. Existing callers, stack, ORM and request machinery are reused.
Filename/length-only resume, `os.replace` publication and retaining only success
state in install were rejected because they violate D1–D4. There is no new runtime
architecture, reservation or persistent attempt implementation.

Offline tests and synthetic bytes only. Running service: not started, restarted,
backfilled or qualified. Real provider/model download and generation: none. Artifact
retrieval: synthetic installed bytes and official Coding attachments only; no live
model/Gallery bytes. Frontend and native Windows were not run; the writer-deletion
case is an offline OS-behavior emulation. No private owner key/configuration,
canonical dependency environment, production database/job/runtime, model, dataset,
output or Gallery record is changed. Shared-main's dirty memory edits are retained.
Technical delivery supplies neither Phase 2 exit nor CTY's artistic verdict.

## Reproduction and handoff

Use the official incremental bundle from the declared handoff prerequisite and its
actual advertised `HEAD`; do not guess a branch name. The full-index binary patch
independently reconstructs the final tree. The official archive/index retain exact
changed Git bodies, complete final ordinary fingerprints and raw evidence. Upload
readback hashes and independent restore/fsck results are in the official receipt.
The final native comment supplies actual FINAL/tree, manifest hash and attachment
IDs. QA pins that actual FINAL before substantive review, then owns its separate
verdict/card; Producer owns acceptance and any subsequent integration.

[Replay commands](implementation-evidence/replay.md) use only an owned ignored
environment, read-only installed dependency sites and a fresh run scratch root.
No live provider, configured owner key, runtime or model action is required.
