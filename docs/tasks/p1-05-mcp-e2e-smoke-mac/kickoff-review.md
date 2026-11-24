Verdict: AMBIGUITY
Review round: 1 (fresh p1-05 kickoff)

Reviewed source: **`d95f1a3607709285d45ac25f6d87a3be53a7ba41`**.
Task SHA-256: **`5ff74c8794101ed1dc1c1346096444d184ca0b6f999271e820ae6829fcc8ea8b`**.
Date: 2026-11-24 UTC. Independent QA: [AID-169](/AID/issues/AID-169).
Producer: [AID-146](/AID/issues/AID-146).

**Do not dispatch implementation under this unchanged specification.** K5-1 and
K5-2 below are P1 contract ambiguities. Producer owns the smallest clarification
or prerequisite task and a fresh independent kickoff. This completed adverse
review is the deliverable of AID-169; it is not a delivery rejection, an owner
question, or evidence of unimplemented p1-05 behavior.

## Independent owner reading and comparison

My reading: the delegated Illustrious/default, explicit-local, no-LoRA Mac flow
must produce a real original and traceable revision, retrieve their image bytes
through MCP, and succeed three consecutive times with zero manual fixes. Printed
IDs/paths, metadata, mock output and the earlier cached original do not establish
that result. All attempts and interventions remain visible. CTY explicitly
replies to the demo and alone judges aesthetics; CTY reviews the roadmap before
Phase 2 activation. Routine technical choices need no new owner confirmation.

[Owner reading](kickoff-evidence/owner-reading.json) was recorded from the owner
request, roadmap and plan before opening the repository task. The wake had
already supplied the task verbatim; no blind-reading claim is made. The task
matches the intended outcome, adopted resources and Mac-first boundary, but its
allowed script-only implementation cannot currently retrieve bytes through MCP,
and its no-retry/count wording does not reconcile bounded-wait recovery or the
baseline's preparation accounting.

No p1-05 `manifest.md` exists at the pinned source. This is a kickoff review,
not an exact-final-feature delivery review. I used my own run-scratch worktree
on `aid-169-p1-05-kickoff`, not the shared checkout or Coding's runtime tree.
The [source audit](kickoff-evidence/source-audit.json) pins input hashes and
accepted evidence identities. During this review Producer advanced shared main
to `401587aeefa1d15ede3addec4099639bf972f859` with dispatch/status documentation;
I did not update or review against that moving checkout. The report/evidence commit and report byte hash
are pinned by the external receipt and completion on this recipient issue;
a commit cannot embed its own SHA.

## Blocking contract findings

### K5-1 — actual retrieval is missing from the permitted MCP contract (P1, D1/D3)

Evidence: task lines 4, 10 and 13 require retrieval through the listed MCP flow,
but D1 line 19 only asks for printed IDs/paths. `tools/intents.py:73` exposes
`gallery_get(image_id, artifact_id)` and dispatches metadata reads; `tools/gallery.py`
projects locators/metadata, not image content. `docs/mcp.md:312` explicitly says
host-byte consumption is a separate file operation. `wait_for_job` constructs
locators without reading bytes. Server registration has no resource reader that
fills this gap.

The independent [registered probe](kickoff-evidence/source-contract-probe.log)
finds 31 tools, zero MCP resources/templates, text-only Gallery metadata and one
mocked metadata GET. A proposed `include_bytes` argument is rejected before any
second HTTP request. This proves the current contract's boundary; it is not an
implemented byte-read feature or a live artifact test. p1-00a's accepted manifest,
PASS and acceptance explicitly disclose `Path(...).read_bytes()`/decode outside
MCP for its colocated Mac client.

Concrete failure: Coding prints two paths and calls that retrieval, or adds a
client filesystem/HTTP read and calls it zero interventions. The first fails
the owner's retrieved-image gate; the second fails unchanged D3/phase rules.
An automatic external read is still outside MCP. Neither is an allowed exemption.

Smallest recommended resolution: Producer explicitly scope a bounded byte-read
extension of the existing read intent, or a prerequisite providing it, before
the smoke driver. Keep one Gallery intent/risk and the metadata default. For
example, an explicit canonical-artifact content option could return bounded PNG
bytes encoded in the common envelope, with MIME, byte length and digest. Set the
exact selector, payload, byte/decode limits and failure/recovery semantics in the
clarified contract. Resolve only the Backend-owned canonical artifact under the
configured Gallery authority/root; reject arbitrary paths/URLs, traversal and
symlink escapes. Preserve canonical IDs, video/legacy metadata behavior and
unchanged job status. No silent copying, remapping, upload or resubmission.
This is a proposal, not an approved schema or implementation instruction.

Later proof must include both images' actual payloads received through the SDK
stdio channel, lengths/digests and successful decoding, with IDs/paths/lineage.
Decoding those received bytes is client-side validation of an MCP result, not a
second host-file or HTTP fetch. Meaningful byte-identity/missing/oversize/unsafe
cases and a stdio round trip must guard the chosen extension. Producer may adopt
an in-scope technical solution under delegated authority; weakening MCP-only or
accepting paths as bytes would change the owner gate.

### K5-2 — wait recovery and preparation need explicit qualification/accounting (P1, D1/D3)

Evidence: unchanged D3 says no retry; `docs/roadmap/ROADMAP.md:18` counts retries,
workarounds and outside-MCP calls. Accepted wait defaults/clamps to a 50-second
overall budget and tells the caller to repeat with the same ID on timeout
(`docs/mcp.md:208`, `:273`; `tools/wait_for_job.py:63`). Its internal GET polling
is within the MCP tool. A second client tool call is a separate visible action.
The baseline counted 11 repeated status calls, plus environment setup and
pre/post-run diagnostics, for 23 units across F1–F8. The raw transcript audit
reconciles 90 events, 17 tool calls and 12 same-job status reads. A run can time
out while the Backend job remains running or even completed during enrichment.

Concrete failure: a driver loops on timeout until success, hides extra waits
inside a helper and reports zero retries; or setup/relaunch and outside-MCP
checks move outside a newly chosen clock and disappear from the F1–F8 comparison.
A job taking longer than one bounded wait makes these interpretations observable.
The historical original required roughly two minutes of polling; that is not a
measurement of current performance and does not prove every future run will time
out. Increasing the requested wait above 50 does not remove the clamp.

Smallest recommended resolution, retaining the literal zero-retry gate:

- Declare qualification start/end and a finite attempt/recovery budget before
  execution. Each qualifying attempt uses one submit and one bounded wait per
  image. Internal tool polling is not another client call. Every client call,
  failure, interruption and sequence reset is timestamped and retained.
- A timeout, uncertain submit, extra retry, external workaround or manual change
  makes that attempt nonqualifying and resets the consecutive-success counter.
  Timeout does **not** label the job failed. Persist the known job ID; recover
  by read-only same-ID status/wait outside the qualifying attempt, retaining all
  recovery calls and their intervention accounting. Never blindly submit again,
  silently cancel, or fall back to another target. With uncertain admission and
  no recovered ID, stop explicitly rather than create a potential duplicate.
- Subsequent attempts are explicitly new requests, not hidden reruns of the
  uncertain request. Establish the old job's state before new work, preserve its
  outputs/records, and count a success only after both bytes and lineage validate.
  Retain every failed attempt before/between the final three; no log truncation.
- Publish a preparation ledger separately from the request-to-result count and
  reconcile it against every original baseline row/counting rule. One-time
  dependency/client/runtime binding is disclosed as preparation, not silently
  called eliminated friction. If such intervention is needed during an attempt,
  it disqualifies it. Keep the original 23-unit/eight-incident baseline immutable.

This strict policy is implementable without waiving the owner rule; it may expose
that the real workload cannot qualify within one accepted wait. That must remain
an honest non-exit result requiring a separately reviewed solution. If Producer
instead wants repeated bounded waits to count as zero retries, it must reconcile
the existing owner rule explicitly through the proper decision path; QA cannot
create that exemption. No question is being sent to CTY in this review.

## Original Done when classification and future evidence

No levels were supplied by Coding because there is no manifest. These proposed
P1 levels reflect false phase-exit/lineage/owner-acceptance scenarios. There are
no demonstrated P0 issues. Manual evidence remains manual; passing offline tests
does not replace a real run. Owner-demo remains unchecked by technical QA.

| Item | Check / proposed level | Kickoff assessment | Evidence later required |
|---|---|---|---|
| D1 — three consecutive real Mac runs, IDs/paths, reset | manual / P1 | AMBIGUITY K5-1/K5-2 | Frozen driver/source and SDK command/configuration; complete timestamped attempts/calls/results and reset counter; three qualified original/revision pairs (six distinct new jobs and canonical artifacts), adopted checkpoint/template/local/explicit `loras=[]`; decoded MCP bytes, IDs and supported paths; actual ComfyUI execution/cache evidence. No deterministic replay counted as fresh diffusion execution. |
| D2 — each revision's persisted Gallery parent | manual / P1 | Implementable in current source; no independent ambiguity | New generate with shared per-pair request_ref, changed brief_revision, canonical `parent_artifact_id`; fresh `gallery_get(artifact_id=...)` records for both artifacts in every run, including Backend-derived parent job/request/brief. Re-read persisted records in a new session, with those verification calls disclosed. An image ID or `gallery_rerun` is insufficient. |
| D3 — zero fixes/retries/outside calls, all friction rows | manual / P1 | AMBIGUITY K5-1/K5-2 | Reviewable script/guide, full SDK stdio evidence, complete call/intervention/preparation/recovery ledger, F1–F8 comparison with original unit rules. No client host-byte fetch, hidden loop, resubmission, envelope fallback, omitted failure or setup exemption. Focused meaningful driver/contract tests supporting the real manual proof. |
| D4 — CTY sees demo/both images and replies | owner-demo / P1 | Clear owner authority; UNCHECKED, later gate | Producer presents reviewed images/revision/Gallery records and technical evidence through the existing project-channel path; preserve CTY's explicit reply with message/source identity. A bot send receipt, Coding statement or QA technical PASS cannot stand for the reply/aesthetic judgment. |

## Required execution and handoff details (no additional demonstrated blocker)

**Runtime/client binding.** Before qualification, identify the Backend, MCP and
ComfyUI processes/interpreters/source/import paths and effective non-secret
DB/Gallery/output/model/authored-data roots. The accepted active Backend launch
is `eaf11b8f75fb573db3d0a4e858973d59385b5087`, not newly published `d95f1a3`.
Record pre-run preparation and verify loaded generation/revision/health/worker
contracts, SDK tool schemas and common structured/text envelopes. Health/current
HEAD/cwd alone prove no loaded revision. Canonical venvs and AID-151's private
configuration/worktree stay intact until a controlled, separately evidenced
replacement. If replacement is needed, first check active generation, trainer,
ComfyUI work and preserve it; pin all effective paths and configuration, preserve
private snapshots, audit complete additive schema and old-value preservation.
Use the existing setup/memory procedure; never restart merely to change a docs SHA.
Persistence during the actual pairs is the final contract proof.

**Real execution versus cache.** Predeclare fresh seeds/prompts using existing
controls, retaining the same adopted checkpoint/template and no LoRA. Retain
compiled graphs, actual Backend/ComfyUI job/prompt correlation and evidence of
sampling execution/cache disposition for all six outputs. Pre-enabled logs or
post-result audit can corroborate execution without an extra client operation
inside the counted flow; disclose those audit operations in the baseline
reconciliation. Do not flush caches or change models as an unreported fix.
The p1-00a deterministic cached original is historical evidence, never one of
these three runs. Distinct artifact IDs alone do not prove fresh computation.

**Client and driver.** Use the real MCP SDK `stdio_client`/`ClientSession` and
an explicitly source-bound MCP subprocess with interpreter/cwd/URL/Gallery
configuration. `list_resources` is this project's tool, distinct from MCP's
resource discovery. Refresh tools; use `data` once, canonical artifact selector,
explicit local target and `loras=[]`. Preserve stderr, request/result IDs, UTC
and durations, settings relevant to any client call timeout, and all failures.
The calling-client limit remains unverified; 50 seconds is fallback policy.
Do not replace SDK transport with imports, mock Backend for qualifying runs,
or accept mocked validation as real generation. Keep evidence redacted.

Minimal driver tests should reject metadata-only/undecodable bytes, mismatched
parent IDs, failed/cancelled/nonterminal/timeout results and uncertain admission;
assert no duplicate submit/fallback, correct counter reset, retained failed
attempts and exact envelopes/selectors. Test the actual driver boundary, rather
than a second implementation of its state machine. If Gallery content behavior
changes, add the meaningful security/byte tests in K5-1. Later delivery QA runs
all affected suites and standing guards. This kickoff needs no full-workspace
build and does not certify new registry rows.

**Owner/demo ordering.** The existing reviewspec owner-demo convention supplies
a workable route: Coding hands off the exact final technical candidate/evidence;
independent delivery QA reviews it, reports D1–D3 and leaves D4 unchecked. Any
technical PASS must explicitly remain pending the owner-demo item. Producer
then presents that reviewed candidate/evidence, obtains CTY's actual reply and
records D4 in acceptance. Do not close the whole milestone by self-certification
or strand Coding/QA waiting on a reply only Producer owns. Subsequent software
changes require a new exact-final-commit review. The phase-close roadmap review
is separate from a demo reply and precedes any Phase 2 activation. Neither gate
is met by this kickoff. Producer should write this ordering into the handoff.

## Accepted prerequisites and preserved accounting

I read the actual published manifests, reports and acceptances, not just their
native done statuses. The indexed source packet includes these fixed inputs.

| Input | Accepted result and limit |
|---|---|
| p1-00 | Original 23 intervention units/eight incidents; one real original, metadata only, relative-URL fetch failed locally, revision not submitted and live revision context null. Original raw transcript/counts remain unchanged. |
| p1-00a | Corrected `b6d58468147e11a21b3d7a26ea25ed4353a28a28`, independent PASS `3d5d8902a89a8c3c8994ed89e944fcaee0260577`. Identified launch, persisted pair and decoded unmodified host paths for colocated client; original cached and bytes outside MCP. One prior rejection/correction 1/review 2 stays separate. |
| p1-01/02 | Combined corrected `616f67ff68fc27070e85861e94d70de1baf5082a`, independent round-2 PASS `28cd4512b8ec7d6594ec972ab81161b8c2d09d03`. Common envelopes, literal risks/intent/mode/namespace preservation. One p1-02 delivery rejection/correction 1/review 2 and its separate kickoff clarification history remain intact. |
| p1-03 | `77e3e3c1520b01cd6422e8ca2b0c0f4adb66e6ce`, PASS `d088c3258ab782623631d60daaaccc8ce6fcb6dc`. Bounded wait, honest terminal/timeout states and supported locators; no byte/client-access proof. Client limit unverified, 50-second overall fallback. Same-ID reads, never timeout cancellation/submission. |
| p1-04 | `72f483418524a613fb104b92ab483e39f7432bfc`, PASS `3422ccda7a66514fe7dadf7d3c8785a5718ba472`; published `d95f1a3`. Exactly 31 intents; configured/observed worker identity distinct, unknown reads not empty. Sequential five-second reads, no total/atomic health deadline; no live worker required for this local task, registry/heartbeat/scheduling stay Phase 3. |

F1 setup and F2 client binding need disclosed repeatable preparation; F3 uses the
accepted uniform envelope; F4 source identity and F5 persisted revision require
actual runtime binding; F6 requires honest bounded-wait/retry accounting; F7
health/status visibility does not attest sampling execution; F8 requires actual
MCP bytes. Explaining a remaining incident does not waive zero fixes. Preserve
all eight rows and their original units (1,1,1,6,1,11,1,1), not a replacement
baseline. All 16 standing registry entries and their history remain unchanged.

## Checks actually run and limits

Exact argv, allowlisted environment, cwd, UTC times, exits and full outputs are
in [kickoff-evidence](kickoff-evidence/README.md). Unchanged canonical component
interpreters load this pinned worktree. `pytest-timeout==2.4.0` was installed
**offline from cache into run scratch only**; no venv/dependency file changed.
Pytest used isolated roots below run-owned TMPDIR and `--timeout=60`.

| Check | Actual outcome |
|---|---|
| `python kickoff-evidence/run-checks.py.txt` → source-contract-probe.py.txt | Exit 0; pinned task hash, actual registration/schema/resource absence, metadata-only Gallery and rejected content option, baseline transcript/count reconciliation. HTTP transport mocked only. |
| MCP catalog + formal SDK stdio tests + Gallery namespace test + bounded timeout/same-ID/clamp cases (exact nodes in receipt) | **32 passed in 2.10s**, exit 0. Stdio connects only to its ephemeral test Backend; other HTTP is mocked. |
| Backend `test_revision_context.py::test_root_feedback_child_survives_real_recording_restart_and_http` | **1 passed, 1 existing warning in 0.50s**, exit 0. Real FastAPI/SQLite/recording/persisted re-read, synthetic execution and PNGs; no live service or generation. |
| Fixed-input/source audit and report package integrity | Receipts pin immutable inputs, report/evidence SHA, exact binary/full-index patch and verified prerequisite Git bundle; final package checks are in the external integrity receipt. |

These are implementability checks only. I did not rerun full Backend/MCP or any
Frontend/build/Windows suite; the assignment explicitly scopes kickoff to small
source checks. Prior accepted full results (Backend 1916/124 skips/76 warnings,
MCP 606/two optional skips, 51-call/107-GET health probe, 28 fresh wait cases,
ten restored faults) remain attributed to prior QA, not to this run. No source
mutation experiment is appropriate for an unimplemented script or docs-only
kickoff. No registry builder/certification was run or changed. One source-audit helper
initially assumed a registry status column; reading the actual generated table
resolved that parser error without changing candidate files. The final audit
passes all 12 accepted-file equivalence checks and preserves 16 active rows.

**Running service:** none probed, restarted, deployed or reconfigured.
**Real generation/training/download/worker dispatch:** none.
**Generated-artifact retrieval:** none; only offline metadata/fixture checks.
No cancellation, live recovery, duplicate prevention/idempotency, remote bytes,
worker readiness, aesthetics, owner demo or phase exit is certified. No model,
dataset, output or Gallery record was removed. Shared main remains untouched;
this commit adds only the independent report and its supporting evidence. No
merge/push or cross-agent issue write is required or performed.

Producer reads this actual adverse verdict, resolves the bounded contracts and
obtains fresh CLEAR before dispatch. The eventual feature still needs independent
exact-final-commit delivery review, CTY's explicit demo reply and phase-close
roadmap review. No Phase 2 expansion is authorized.
