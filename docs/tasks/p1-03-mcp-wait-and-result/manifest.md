# p1-03 bounded wait and truthful results — Coding delivery 1

Candidate for independent exact-commit review on [AID-164](/AID/issues/AID-164),
delivered by [AID-163](/AID/issues/AID-163). This is original implementation
delivery round 1, not a correction or a self-certified QA PASS.

Base: **`faad28dc339b8b5d14aceea91d1fcfaad0a79ddd`**. Branch:
`aid-163-bounded-wait`. Worktree:
`/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-163-bounded-wait`.
The final commit contains this manifest, all source/tests/docs and evidence.
Its full SHA is pinned by the external integrity receipt and Coding completion
comment; a commit cannot contain its own SHA. The official source packet,
binary patch and verified Git bundle identify that same fixed candidate.

## Delivered behavior

Exactly one new intent, `wait_for_job(job_id, timeout_seconds=50)`, with risk
`read`; discovery now has 30 tools. All 29 prior literal risk expectations are
unchanged, including ComfyUI admin. Ping stays; health/workers remain staged.
Existing names, synchronous client behavior, envelope/structured-text agreement,
generation/training domains and image/artifact namespaces remain distinct.

The async GET added to `HttpBackendClient` lets one AnyIO cancellation deadline
abort slow connection/header/body reads. A single monotonic budget includes
lookup, polling, enrichment, sleep and response preparation, with explicit checks
after non-yielding work. Generation is tried first; only HTTP 404 permits a
training lookup. Once identified, that domain is polled without fallback.
Read failure never proves absence or job failure.

Generation success returns `data.job_id`, `job_domain: generation`, unchanged
`status: completed`, `artifacts` and separate `images`. Canonical artifacts retain
all real IDs, kinds, order, source-node and revision/provenance fields. Every
entry carries its real `artifact_id`, `kind`, supported host `local_path` and
Backend `artifact_url`. `images` carries actual image IDs with
`artifact_id: null`, image path/URL and host path; legacy image-only completions
keep `artifacts: []`. No result cap, borrowed ID, basename mapping or file write
manufactures a result.

Locator construction uses safe Gallery-relative metadata or an existing Backend
Gallery URL under configured `MCP_GALLERY_DIR`. It preserves nested/Unicode
identity, encodes raw Unicode/spaces, preserves existing URL escapes and binds
relative URLs only to configured Backend authority. Absolute paths require
established host containment; traversal, symlink escape, outside/container-only
paths, conflicting metadata, credential-bearing and arbitrary remote URLs are
rejected. A separately supported host path survives a rejected URL without
manufacturing a replacement URL.

`artifact_locator_unavailable` is an error about result metadata, retaining
completed Backend status, target domain/ID, every known canonical and separate
image identity, available locators and reasons in `unavailable_locators`.
Unsupported locators remain null. The hint calls for inspecting the same job
and existing Gallery configuration before another read, without migration or
resubmission. Stored path fields remain source metadata, not usable-host claims.

Training reuses existing public status/error projection. Safetensors output and
registration fields survive; no Gallery media is invented (`artifacts: []`,
`images: []`). Independent smoke job/image/nullable canonical IDs, safe locators,
status and diagnostics survive. Training completion never awaits or submits smoke.
Failed training is an error even when the status read has `ok: true`.
Cancellation uses `job_cancelled`, preserving terminal status and context.
Timeout uses `error.code: timeout`, last-known status/domain (explicitly unknown
before an identifying status read), budget and same-ID call-again hint. It sends
zero cancellation or submission requests.

## Done when evidence

Test names below are in
[test_wait_for_job.py](../../../mcp-server/tests/test_wait_for_job.py), unless
another path is named. All use registered SDK validation/wrappers, actual
adapters/HTTP client and mocked HTTP transport; timeout tests additionally use
real elapsed time. Nothing patches the wait callable.

| Item | Check | Level | Result / evidence | Layer and proof boundary |
|---|---|---|---|---|
| D1 — truthful complete generation/media | test | P1 | Mixed image/video/order/lineage, 106-artifact no-cap, supported URL/absolute mappings, legacy images, 20 unsafe/missing locator classes, symlink escape, mixed unavailable results, separate legacy failures, identity mismatch, partial available host path; 12 real-route export replays. Final wait log, mutation summary. | Registered MCP → real client → mocked HTTP. Fresh real Backend routes + SQLite produce the replay fixture. IDs/metadata are verified, not live Gallery bytes. |
| D2 — failed/cancelled jobs | test | P1 | `test_terminal_failure_cancellation_and_safe_training_projection` (both domains); read/enrichment failures retain target and safe recovery. Terminal-success fault fails all four cases. | Real registered error envelope retains node/recording/revision context and public training output; transport replaced only. |
| D3 — bounded overall wait/recovery | test + manual | P1 | Five deadline stages, streamed-body close, high clamp, last-known/unknown status, response-preparation/non-yielding checks, queued/running same-ID recovery for both domains. Timing log; removing overall abortion fails the four slow-request stages (the last-known sleep case still passes). | Actual monotonic time, async HTTP transport and cancellation. 70 ms budget observed about 72–73 ms including SDK/setup overhead; 400 ms mocked reads aborted. No Backend job cancellation/submission. Manual source/limit review below. |
| D4 — training and independent smoke | test | P1 | Completed/failed/cancelled/queued/running training; absent/real/legacy/queued/running/failed/cancelled/unavailable smoke, nullable canonical artifact and real image IDs. Fresh route replays assert safe public fields. Borrowing smoke image ID as artifact ID fails. | Existing public projection; real route/SQLite fixture plus registered mocked-HTTP consumer. Training completion performs exactly generation lookup + training status read; no smoke request. No real training. |
| D5 — documentation/current flow | manual + test | P2 | [MCP documentation](../../mcp.md#bounded-wait-and-results), [team current flow](../../team/README.md#mcp-calls), discovery/schema and existing catalog-doc guard. Author compared timeout/error/success/host/URL/legacy namespaces against delivered source and tests. | Offline author review and real SDK discovery, pending independent QA. Runtime, health/workers and remote retrieval are not claimed. |

## Limit source and verification

Actual calling-client enforced tool-call limit: **unverified**. Inspected tracked
MCP wrapper/config/server sources and existing kickoff source-search evidence;
none identifies/configures that client's enforced limit. The approved
**50-second overall fallback is policy, not a measurement**. The existing
Backend client default remains 60 seconds per request for other consumers;
AnyIO's overall scope, rather than that inactivity default, bounds wait reads.
See pre-implementation source pin,
[implementation plan](implementation-plan.md) and actual timing receipts.

Each command has argv, cwd, selected non-secret environment, elapsed seconds,
exit and complete output in delivery-1-evidence.
All pytest commands use isolated roots and `--timeout=60`:

| Check | Exact command suffix after the interpreter | Exit / result |
|---|---|---|
| Baseline MCP, before implementation | `-m pytest -c pytest.ini mcp-server/tests -q --timeout=60` | 0; 459 passed / 3 optional export skips in 1.79s. Fresh lifecycle/multi-LoRA exports were provided; revision export was added for final verification. |
| Fresh full Backend / existing standing guards | `-m pytest -c pytest.ini backend/tests -q --timeout=60 -ra` | 0; **1900 passed, 124 Windows-only skips, 76 warnings in 41.37s** (42.45s process). Fresh revision/multi-LoRA/lifecycle exports retained. |
| Final restored full MCP | `-m pytest -c pytest.ini mcp-server/tests -q --timeout=60 -ra` | 0; **540 passed, 2 unchanged optional smoke-export skips in 2.84s** (3.01s process). All meaningful fresh-export consumers execute. |
| LoRA shared interface parity | `-m pytest -c pytest.ini backend/tests/test_lora_start_contract_parity.py -q --timeout=60` | 0; 5 passed / 1 existing warning in 0.29s. Helper imports resolve this checkout in the separate MCP interpreter. |
| Final targeted wait/timing | `-m pytest -c pytest.ini mcp-server/tests/test_wait_for_job.py -q --timeout=60 -s` | 0; 77 passed in 1.04s. Recorded elapsed times and request counts. |
| Platform-aware fixture paths + registered boundary | `-m pytest -c pytest.ini mcp-server/tests/test_wait_for_job.py mcp-server/tests/test_intent_boundary.py -q --timeout=60` | 0; 221 passed in 1.42s. Native Windows itself not executed. |
| Fresh Backend shape export | `docs/tasks/p1-03-mcp-wait-and-result/delivery-1-evidence/backend-shape-export.py.txt` | 0; 0.56s process, real HTTP routes/in-memory SQLite; queue observations mocked, fixture PNGs only, no lifespan/service/trainer. |
| Seven production faults | Exact mutations and test argv, paired `.patch`/`.json`/`.log` files | All expected exit 1; media omission 1 failure, hidden locator errors 20, ignored terminal failures 4, missing overall abortion 4 (1 passed), borrowed smoke ID 7 (1 passed), false wait risk 2, false existing admin risk 2. Every source restored before final GREEN. |

MCP interpreter is canonical Python 3.10.20 (MCP 1.26.0 / httpx 0.28.1 /
AnyIO 4.12.1); Backend interpreter is canonical Python 3.11.15. Imports are
explicitly bound to this worktree through cwd/pytest.ini/PYTHONPATH, including
cross-layer helpers; import receipts retain
the paths and package versions. No canonical venv was changed. Scratch-only
`pytest-timeout==2.4.0` was installed with `uv pip install --target ... --no-deps`.
No product dependency or lockfile changed; AnyIO already belongs to the MCP stack.

The two unchanged MCP skips require optional `SMOKE_HTTP_FIXTURE_OUT` and
`SMOKE_IMAGE_HTTP_FIXTURE_OUT` exports. New wait smoke-shape cases all execute,
including fresh current Backend route responses. Backend skips all require
Windows. Frontend, native Windows, worker, launcher and bot suites were not run:
their code/inputs are unchanged; no claim is made for those platforms/components.
Full Backend was run once for its nine-standing-guard surface and fresh exports,
not repeated for later MCP-only test/fixture/doc changes.

## Preservation, deviations and earlier failures

Preservation audit compares all
1032 baseline tracked files: only six existing files changed, plus the new
implementation/tests/fixture/engineering evidence. Backend, Frontend, worker,
bot, launcher, authored data and dependencies are unchanged. All inherited
p1-03 task/decision/kickoff/report/evidence bytes and all nine registry guards
are unchanged. Only QA certifies registry changes; Coding made none.

Existing tests necessarily adapted: independent catalog expectations/discovery
now permit 30 tools and wait=read, keeping all 29 prior labels. The generic
registered transport fixture now supports async reads and a completed wait
response; host-path fixture/expectation uses native absolute paths. No feature
test was removed or quarantined. No deviation from cleared D1–D5.

No product/test failure remains. Initial baseline setup failed because the
canonical MCP environment lacks pytest-timeout; a pip attempt also showed it
has no pip. Scratch uv target fixed tooling without environment edits. Two
initial baseline failures were absent explicitly configured exports, resolved
by fresh producers. These were setup failures, not preexisting product bugs.
Preserved RED/GREEN development runs additionally exposed malformed/unsafe URL
handling, safe training HTTP error projection and raw Unicode Backend URLs;
those have covering tests and restored GREEN. One early request-count assertion
was corrected to three generation reads versus four training reads across two
calls. The raw receipts are retained, not relabeled as passing.
Source/docs pass `git diff --cached --check` with the raw evidence directory
excluded; original pytest log whitespace and unified-patch context whitespace
are preserved in that directory as data.

Abandoned: a synchronous sleep/poll loop around the 60-second request timeout
cannot enforce D3; the cancellable async read uses the existing stack. No other
architectural replacement or out-of-scope interface change was needed.

Accounting remains one p1-03 kickoff ambiguity / clarification 1 / kickoff 2
CLEAR, with **no implementation rejection yet**. The separate p1-02 delivery
rejection/correction 1/review 2 PASS and p1-00a history remain intact. K3-1 was
resolved at specification level; this candidate awaits actual independent PASS.

## Proof limits and handoff

- **Offline:** tests, real-route SQLite fixtures, SDK discovery, fault checks,
  source/hash audit and documentation review only.
- **Running service:** none inspected, restarted, redeployed or replaced.
  AID-151 runtime/worktree/private configuration and component environments stay.
- **Real generation/training/download/worker dispatch:** none.
- **Generated-artifact retrieval:** no live Gallery-byte retrieval or remote
  URL consumption. Only synthetic fixture PNG validation in the Backend reader.

Constructed locators prove neither file existence nor consumer access/bytes.
Real wait behavior is deferred to p1-05. Original baseline remains 23 intervention
units/eight incidents; historical proof remains one cached-original/revision
pair with colocated host-path retrieval/lineage. Live timeout/cancel/dedup
recovery, remote consumption, aesthetics, three zero-intervention runs and phase
close remain unaccepted. No main merge/push or p1-04 release is performed.

Coding uploads this official manifest, indexed exact source/evidence packet,
feature patch, verified Git bundle and external final-SHA integrity receipt on
AID-163, then marks Coding done to release its native dependent AID-164. Producer
reads the actual manifest and QA verdict and owns subsequent integration.
