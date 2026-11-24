Verdict: FAIL
Review round: 1

Independent delivery review by QA AID-172, 2026-11-24 UTC. Reviewed full immutable
candidate **873629869dce8935d68daa8236f0aaf8eb1b553a**, tree
**b6ea69080d8d96c7ba7f965949be43b7f0b6eacc**, against fixed base
**e540829376cc397b3dc509192643874fabad3459**. Software freeze:
**6bcb402ff8be2bea59c2dc3dbcd0de01c78ecab9**. This report/evidence commit is named
by the external integrity receipt and completion on [AID-172](/AID/issues/AID-172).
The review used its own persistent `aid-172-exact-review` branch/worktree at
`/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-172-qa`.

D1 and the recorded D2 real evidence pass independent checks. **D3 fails the
required interruption reset and complete attempt accounting. D4 remains
unchecked/pending Producer/CTY owner-demo.** This is a completed adverse technical
review, with no candidate repair, merge, push, acceptance or phase closure.

## Findings

**R5-1 — P1 / D3: an interrupted attempt retains the prior streak and omits its
completed failure/call accounting.** In
[`scripts/mcp_smoke_mac.py`](../../../scripts/mcp_smoke_mac.py), the attempt handler
at lines 268–280 catches `Exception`; an actual SIGINT raises cancellation and
then `KeyboardInterrupt` across `asyncio.run`. The outer `BaseException` handler
at lines 333–338 writes `interruption`, but neither resets `summary.streak` nor
finishes the current attempt. `Run.call` also catches only `Exception`, so the
interrupted call does not receive a `calls.jsonl` record.

Reproduced at the exact unmodified candidate with the actual CLI, SDK stdio and
product MCP subprocess. Only the lower HTTP/storage fixture is synthetic. After
one qualifying pair, an HTTP proxy pauses the second attempt's health response;
QA sends SIGINT to the calling CLI. Result: exit **2**, two previous submits,
no additional submit, `result="interrupted"`, **`streak=1`**, and attempt 2 has
only `attempt`, `declared`, `started`, `qualifying=false`, `images=[]`. It lacks
reason/end/call-count/streak. The second health call exists in sent SDK traffic,
but only the first attempt's eight calls exist in `calls.jsonl`; no attempt-2
`ended` event exists. The final interruption event does not complete that
attempt's ledger or reset its streak.

[Probe and observed result](review-evidence/interruption-probe.json),
[reproducer](review-evidence/probe_interruption.py),
[complete fixture SDK/call/event/frozen/summary evidence](review-evidence/interruption-fixture-run/),
[stderr](review-evidence/interruption-probe-stderr.txt).
Command: `$QA_PYTHON docs/tasks/p1-05-mcp-e2e-smoke-mac/review-evidence/probe_interruption.py`
from the repository root. The probe's zero process status
means the observation was captured; **`compliant_reset=false` is the defect**,
not a passing feature assertion.

Clarification 1 explicitly says every interrupted attempt resets the counter,
and requires complete timestamped failures/reset/call evidence. D3 is assigned
P1 in the manifest; this review retains that level. The CLI does safely stop
with non-exit and does not falsely return success, duplicate a submit or change
target. The defect concerns the mandatory strict reset/accounting contract;
no false claim about generation safety is needed to demonstrate it. Coding must
handle interruption at the actual boundary, retain the attempted call and a
final nonqualifying attempt record, reset to zero, and add an actual CLI signal
regression. Preserve any admitted/uncertain request and same-ID recovery rules;
do not convert interruption into a new submit. QA made no repair.

## Done when assessment

| Item | Independent result | Evidence / limits |
|---|---|---|
| D1 — bounded canonical PNG read / P1 | PASS | Actual registered/client/open/decode boundaries, actual SDK CLI fixture round trips, all compatibility/risk/envelope guards, six additional QA cases and deliberate identity/open/full-decode faults. |
| D2 — three real consecutive pairs / P1 | PASS for this recorded candidate evidence | Actual attempts 2–4 and all six MCP byte payloads independently verified, plus fresh QA SDK retrieval and live canonical/ComfyUI/persistence/source audits. No new real generation was run. |
| D3 — strict no-retry/reset/accounting / P1 | **FAIL R5-1** | Normal/error/recovery/finite-budget paths pass; actual signal interruption violates reset/full ledger requirements. The recorded real invocation itself has no hidden retry or omitted submit. |
| D4 — explicit reviewed-demo reply | **UNCHECKED / pending owner-demo** | Producer must present the reviewed candidate/images/Gallery records and obtain CTY's explicit project-channel reply after the technical gate. QA does not judge aesthetics or supply that reply. |

## Exact delivery and history integrity

The full candidate was pinned with all cleared hashes on this review card before
substantive review. QA downloaded the five official Coding deliverables and six
individual PNG attachments. The actual manifest matches Git. All **133 indexed
payloads / 134 archive members** match lengths, SHA-256, Git blob identities and
candidate bodies. The official binary/full-index patch equals the exact
base-to-candidate diff and reconstructs the candidate tree. The independently
downloaded prerequisite bundle verifies and fetches into a separate bare
repository with the same full SHA/tree; the fixed shallow base was imported as a
connected ref using `--update-shallow`.
[Independent integrity receipt](review-evidence/coding-official-integrity.json).

Cleared unchanged SHA-256 identities:

- Task: `c8bbbe8215f440e8859a5bc0bedf3febf4686f42ea0178fc82da871b041b8698`.
- Clarification: `f172d2098b69308b62a7cff7dc9c9cba7ed6bc71b3161a08b86ed9e9aa20e859`.
- Full MCP decision: `bf94f8b4277e7a264770b4788d2facfa2fbcdd7ec216538c429865b6c693e395`.

All **728 protected prior inputs**, original kickoff/report/evidence, accepted
p1-00/00a and p1-01–04 histories and original 16 registry rows match the fixed
base. Incoming history remains one kickoff ambiguity event/two P1 findings,
clarification 1 and kickoff round-2 CLEAR, with zero preceding implementation
rejections. **This review adds delivery review 1 FAIL / first implementation
delivery rejection / one P1 finding.** It does not alter earlier histories.
No new automated item is certified on this FAIL. Registry derivation is rerun;
all 16 standing items retain their tests. Any generated-date change is metadata
only, with row bodies and count preserved.

## Independent offline verification

QA prepared an isolated run-owned Python 3.11 environment, pinned MCP 1.26.0,
Pillow 12.2.0, Starlette 1.0.1 and recorded all installed package versions/import
origins. The canonical Backend and MCP environments were not installed into or
changed. The Backend suite uses the canonical interpreter with explicit QA
worktree imports and an isolated timeout-plugin directory.
[Environment](review-evidence/task-environment.json),
[reproducible package pins](review-evidence/qa-requirements.txt).
All tests use isolated `AI_DRAWING_TEST_ROOT` below run-owned `TMPDIR`, and long
pytest runs use `--timeout=60`. Exact argv, cwd, selected environment, UTC,
duration, exit status and complete output accompany each result.

| QA command scope | Actual result |
|---|---|
| Full MCP suite at candidate | **663 passed, 4 existing optional export skips**, 51.66s, exit 0. [Receipt](review-evidence/mcp-full.json), [output](review-evidence/mcp-full.txt). |
| Full Backend suite at candidate | **1916 passed, 124 existing platform skips**, 42.77s, exit 0. [Receipt](review-evidence/backend-full.json), [output](review-evidence/backend-full.txt). |
| Six extra registered-boundary QA cases | **6 passed**. CRC-valid but undecodable IDAT pixels require full loading; additional boolean/coercible/null selectors reject before access. [Tests](review-evidence/test_independent_content.py). |
| Final restored full MCP plus six QA cases | **669 passed, 4 existing optional skips**, 48.06s, exit 0. [Receipt](review-evidence/mcp-restored-full.json), [output](review-evidence/mcp-restored-full.txt). |
| Fresh actual Backend revision HTTP/persistence export | **1 passed**, exit 0. [Receipt](review-evidence/fresh-revision-export.json), [fresh output](review-evidence/revision-fresh-export.json). |
| Revision and retained LoRA cross-layer consumers | **7 passed**, exit 0. [Receipt](review-evidence/cross-layer-corrected.json). Fresh QA revision export and unchanged accepted lifecycle fixture; actual current consumers rerun. |
| Seven independent production mutations | All expected **RED**, restored to exact candidate bytes. [Results](review-evidence/mutation-results.json). |
| Actual CLI SIGINT probe | Required reset **fails**; exit 2 and no further submit, R5-1 above. No product mutation or failing test left installed. |

The mutations separately remove canonical identity validation, both actual-open
identity/containment guards, full pixel decoding, client digest validation,
parent/request/brief validation, terminal-status validation and the six-call
recovery limit. Each targeted check fails. A first narrower open mutation stayed
green because the second real guard still rejected the unsafe open; it did not
violate containment and is retained as an insufficient probe. Source was
restored before the effective mutation and the final GREEN suite. See
[retained narrow probe](review-evidence/mutation-opened-redundant-guard.txt).

D1 inspection confirms one bounded read of at most 2,097,153 bytes, the 2 MiB
limit, pre-decode dimensions/pixels and static frame/MIME/PNG verification, full
decode, exact unmodified bytes, safe same-artifact recovery errors and no writes.
Opened-descriptor identity checks preserve actual host-root containment across
intermediate symlink swaps; unsupported handle inspection fails closed. Canonical
identity, nested Unicode, contradictory/outside/container locators, FIFO and
unsafe-file tests cross actual registration/client/storage boundaries. Metadata
video/legacy behavior, 31 literal intent/risk labels, wait semantics and old
capabilities retain their guards. No new intent, URL fetch, endpoint/schema or
worker-control expansion is introduced.

Two optional exports execute subsequently in the seven-case cross-layer check;
the two old smoke-export skips remain disclosed. Backend's existing platform
skips and deprecation warnings are unchanged. No new skip or changed/removed
existing test. No unrelated Frontend build, Windows run or full-workspace build
was needed or claimed.

## Running-service, real-generation and artifact boundaries

[QA independent live audit](review-evidence/independent-real-audit.json),
[read-only audit code](review-evidence/independent_audit.py),
[complete fresh SDK results](review-evidence/qa-sdk-results.jsonl),
[raw live requested rows](review-evidence/live-requested-rows.json).

**Running service:** QA matches Backend PID 99953 and ComfyUI PID 99952 to Coding's
actual recorded creation times, full process commands, executable and cwd.
Frozen source bodies match the reviewed candidate and persistent runtime tree;
live OpenAPI matches the deployed receipt. Equivalent-interpreter imports under
the actual process environment corroborate imports and all effective non-secret
roots/settings. Those probes are not a general in-process attestation endpoint.
The complete SQLite schema and all old values match the private prelaunch
snapshot; only the intended new records are added. Original AID-151 private
snapshots and AID-171 runtime/worktree/config remain preserved. QA neither
restarted services nor generated work. macOS resolves the Backend venv launcher
to Python.app at execution; comparing actual process identity with the recorded
actual process resolves the apparent launcher-path discrepancy.

**Real generation:** QA independently reconciles all 35 captured SDK calls with
the actual sent/received JSON-RPC IDs and full text/structured results. Attempt 1
has four calls and timeout with status **running** at the 50-second fallback;
one separately recorded same-ID recovery establishes completed before attempt
2. Attempts 2–4 each have exactly the eight required calls, two distinct submits,
fixed local/empty-LoRA/512×512/batch-1/four-step/CFG-7/Euler/normal parameters,
declared fresh seeds and changed red/blue prompts. Each call, reset, recovery
and new-session audit matches the ledger. All seven actual jobs are completed.
Complete persisted compiled graphs match exactly seven distinct current ComfyUI
history entries, with matching sampler/latent/checkpoint/prompt inputs, successful
execution and uncached KSampler nodes. Runtime 4/4 progress corroborates actual
sampling. This rechecks recorded generations; it creates no replacement runs.

**Artifact retrieval:** QA decodes and verifies all six original recorded
MCP-returned PNG byte sequences, lengths, digests, 512×512 dimensions, static
frames, full pixel decode and embedded graph. A fresh QA SDK process/session
retrieves those same six actual canonical content records again; exact bytes and
all normal metadata equal the recorded qualifying reads. Canonical artifact
3866→3867, 3868→3869 and 3870→3871 correspond to separate image IDs 4451–4456.
Current image/artifact database rows, qualifying reads and new-session reads
agree on job/request/brief and all canonical parent snapshot fields, without
context errors. All fresh retrievals are disclosed QA post-result audits,
not new qualifying attempts. QA did not fetch image bytes via host paths/HTTP.

**Accounting:** Original baseline remains **23 units/eight incidents** and F1–F8
**1,1,1,6,1,11,1,1**. Coding's retained ledger sums to **53 preparation + 0 attempt
interventions + 1 recovery + 27 audit = 81**. Zero applies only to the qualifying
request-to-result flows. The whole round has nonzero interventions and does not
beat the baseline total. All normal 28 attempt calls, one recovery and six
persistence reads remain visible. The first aborted external audit's eleven
reads, extra diagnostic read and missing intermediate bodies are disclosed;
the later completed independent graph/persistence audit and this QA audit supply
the actual corroboration. That diagnostic assumption did not find bad product
sampling/lineage or require a product/input change. It is not silently removed
or counted as another qualifying invocation.

QA's own post-result operations are separate, retained in the live-audit receipt,
failed-audit-tool receipts and [QA audit ledger](review-evidence/qa-audit-ledger.json).
They never alter Coding's original 81-unit total. QA tooling initially assumed
launcher and actual Python.app paths were identical, then assumed an image row
used the artifact metadata column; both assumptions were corrected from actual
process/schema data. The failed checks are tooling failures, not product faults
or fresh qualifying attempts. An optional cross-layer test first used a wrong
fixture path (one FileNotFoundError); the corrected seven-case run passes.
No failure or product operation is hidden as a clean first try. Raw pytest
tracebacks retain their original trailing whitespace; patch application uses
`--whitespace=nowarn` without rewriting evidence bytes.

## Limits and disposition

No CTY aesthetic judgment, owner-demo reply, whole-task/Phase-1 acceptance, phase
close, Phase 2 activation, Windows generation, worker dispatch, downloads,
training or Discord send is verified. Current calling-application limit remains
unverified; the wait fallback stays 50 seconds and the disclosed SDK response
guard stays 65 seconds. Offline mocks never substitute for the six real images.

Producer AID-146 owns the demonstrated R5-1 follow-up, Coding repair and renewed
exact-final-commit QA; changed software requires renewed applicable qualification
under the cleared rules. Preserve this report, all original evidence and the
failed interruption observation. QA completes AID-172 with **FAIL** and its
immutable official report/packet/patch/bundle/integrity receipt. D4 remains
unchecked and cannot prevent completion of this adverse recipient-owned review.
