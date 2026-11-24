Verdict: AMBIGUITY
Review round: 1

Review type: independent kickoff only. Date: 2026-11-24 UTC.
QA: [AID-161](/AID/issues/AID-161). Producer: [AID-144](/AID/issues/AID-144).
Fixed published source: **`7a46cb70bde83ba18417620ead3759a78e3c7c14`**.
Task: `docs/tasks/p1-03-mcp-wait-and-result/task.md`.
Task SHA-256: **`b41cc419c0eba393f16a30ae60c844d9654bc8830bf6aa63510c8213bfaf5589`**.
Original Done when count: **5**. No p1-03 manifest exists at this source.

One material locator-contract ambiguity needs Producer clarification before
Coding dispatch. No ASK OWNER or project-boundary change is demonstrated.
The task's purpose, phase order and bounded read-only approach otherwise agree
with the approved direction. This is neither implementation rejection nor
delivery PASS. A clarified fixed specification needs fresh independent CLEAR.

## Independent owner reading and comparison

My reading: Phase 1 needs a bounded read intent that replaces manual polling and
returns existing job state and retrievable result references in one common MCP
envelope. Generation and training remain distinct Backend job domains; training
output and separately bound smoke generation must stay truthful. Timeout keeps
the same job and permits another read, without cancellation or resubmission.
State, artifact identity and provenance remain Backend-owned. Preserve supported
host-path semantics and do not invent media records. Routine technical choices
are delegated to Producer; real-run and phase acceptance remain later gates.

I saved this [reading](kickoff-evidence/owner-reading.md) after reading the
preserved owner direction, roadmap/current state and MCP decisions, before
opening the on-disk task. The inline assignment had already exposed its text.
The [owner request](../../requests/2026-11-24-proceed-within-project-boundaries.md)
supplements the existing Phase 1, including its independent review gates; it
removes routine start/resource confirmation waits. It does not authorize a new
storage migration, phase, stack or worker control boundary.

Difference: Scope/D1 promise complete media locators without defining the
existing cases where no canonical artifact ID or Gallery URL exists. K3-1 below
is a contract disposition, not a request to broaden Backend scope.

## Fixed identity and accepted inputs

The isolated worktree is `ai-drawing-worktrees/aid-161-kickoff-review`, branch
`aid-161-p1-03-kickoff`, based exactly on the full source above. The source/task
identity was pinned before substantive review in
[source-identity.json](kickoff-evidence/source-identity.json) and recorded on
[AID-161](/AID/issues/AID-161#comment-ab94c056-469a-452c-b968-5cfbb3af8383).
Shared main stayed on main. No product source/test/dependency/configuration was changed.

All **12 assignment reference digests match** the named Git objects and checked
out bytes: [immutable input audit](kickoff-evidence/immutable-input-audit.json).
I read the actual p1-01 and p1-02 manifests, both later QA reports and published
acceptance, rather than treating completed prerequisite cards as acceptance.
The manifests equal accepted feature `616f67ff68fc27070e85861e94d70de1baf5082a`;
the reports equal QA `28cd4512b8ec7d6594ec972ab81161b8c2d09d03`. Their immutable
“awaiting review” author text is consistent with the later PASS/acceptance.
Integration `7ba2059f7e46920eaf860e19e61aa84bae8bf02c` preserves those inputs.

Accepted software supplies 29 intents and one envelope/risk per tool, with
separate `job_status` and `lora_train_job_status`, image/artifact selectors,
safe LoRA projection and canonical revision identity. Adding the approved read
intent is in Phase 1. It does not rename/merge LoRA tools or restore removed
video submission tools; existing recorded video reads are still in scope.

## K3-1 — incomplete or non-Gallery media locator disposition

**P1; Scope/D1, with related D4 smoke/legacy references.** This is an AMBIGUITY
for Producer, not a claim of a newly introduced product bug or an observed
production data incident.

The task requires every real media artifact to have `artifact_id`, image/video
kind, a host path under `MCP_GALLERY_DIR` and a Backend URL. It excludes Backend
changes beyond reading state. Existing authoritative source admits these shapes:

1. `backend/app/api/generate.py:598` reads both `GeneratedArtifact` and
   `GeneratedImage`; at `:647` an image row alone is sufficient for completed
   status. It returns `image_id`, `image_path` and `artifacts: []` when no
   canonical artifact row exists. Reusing that image ID as artifact ID is false.
   Normal current `recording.save` writes both records; the legacy read remains
   supported and must not be inferred from that normal writer's invariant.
2. `backend/app/api/gallery.py:43` returns no Gallery URL for an absolute stored
   path outside the resolved Backend Gallery root; `:55` returns an absolute artifact path unchanged. `ArtifactDetail`
   explicitly permits null `artifact_url`/`local_path`. Thus a real recorded file
   outside the Gallery root has neither a truthful path under the configured
   root nor a Backend static URL. Re-rooting its basename would name another file.
3. `backend/app/services/lora_smoke.py:63` explicitly accepts a valid legacy
   image-only reference with `smoke_test_artifact_id=None`, retaining its image
   ID, relative locator and generation job ID. D4 correctly forbids inventing a
   Gallery artifact, so a clarification must preserve this case too.

I reproduced the first two through **actual HTTP routes and in-memory SQLite**,
with a real 1×1 fixture PNG outside the isolated Gallery directory. No product
DB or media was touched. The completed image-only job returned image ID 901
and no artifacts. Recorded artifact 43 returned its unchanged outside-root path
and `artifact_url: null`. See [compact results](kickoff-evidence/shape-summary.json),
[full responses](kickoff-evidence/backend-shape-probe.log) and the
[reproducer](kickoff-evidence/backend-shape-probe.py.txt).

Two incompatible implementations could otherwise claim D1: fabricate root/URL
locators and claim complete success, or preserve truthful null/missing values
and fail the literal “every artifact” promise. Exact delivery QA needs a stated
exception/disposition. Supporting the normal relative-path case alone must not
silently discard real legacy results.

**Smallest recommended correction for Producer to adopt:** qualify Scope and
D1, retaining all five Done when items, along these lines:

> Return every existing canonical media artifact with its real ID/kind and
> available locators. For safe Gallery-relative paths, return a host path under
> MCP_GALLERY_DIR and the Backend Gallery URL. Preserve legacy image-only
> results using their separate image ID/path/URL, without creating or borrowing
> an artifact ID. If an artifact cannot supply the promised Gallery locators,
> retain the job ID/completed Backend status and canonical identity in a common
> error result with an actionable locator-unavailable diagnostic; do not invent,
> remap, copy or expose a new file. Training output stays separate, and real
> smoke links retain nullable canonical artifact IDs and separate image IDs.

The fail-closed error disposition is a recommendation, **not an approved new
contract in this review**. Producer may instead explicitly choose a truthful
nullable-locator success shape, provided its incomplete-retrieval state and
legacy-ID rules are documented/testable. No existing artifact needs deletion,
backfill, file movement or Backend change. This correction stays inside delegated
technical authority; no ordinary CTY confirmation is required. Preserve the
original task and this round when recording the clarification.

## Original D1–D5 assessment

| Item | Kickoff assessment | Concrete later evidence |
|---|---|---|
| D1 — completed job, all media locators | **AMBIGUITY K3-1** for legacy/missing/non-Gallery locators. Normal recorded image/video rows are directly testable. | Real registered call with transport mocked below the HTTP client; multiple artifacts including mixed image/video, different image/artifact IDs, Unicode/nested paths, complete locator list, legacy image-only and unavailable-locator dispositions. Keep canonical revision context. No fabricated ID or host path. |
| D2 — failed job returns error | **Testable.** Generation uses `status=failed`, `error`, node/recording diagnostics. Training exposes `status=failed`, `error_code/message/details`, including registration failure with a surviving output. | Test both domains and safe Backend failure reason/code in the common error envelope, with job ID/status preserved. A successful training status HTTP read has `ok:true` even when the job failed: wait must inspect status rather than copy that read-level flag. Preserve existing safe LoRA diagnostics; do not bypass public projection to recover raw private text. |
| D3 — timeout, clamping, total budget | **Testable; client limit unverified, approved fallback is 50 seconds.** Timeout is an observation outcome, not job failure. | Deterministic deadline tests for queued/running generation and training, high timeout clamp, slow status requests, lookup/fallback and artifact enrichment costs, and a short real elapsed-time mocked-transport check. Assert response within the overall configured bound, same job/current or last-known status and call-again hint, zero submission/cancel requests. Document no observed status truthfully if the first read exhausts the budget. |
| D4 — training output and real smoke references | **Testable on normal shapes; K3-1 must settle legacy locators.** Existing training output is a run-relative safetensors locator, not Gallery image/video. | Completed training with output/registration fields and `artifacts:[]` when no media; failed/cancelled/pending training, independent smoke state, and real smoke job/image/artifact IDs with relative URL. Preserve null IDs when absent and errors such as artifact_unavailable. No start/train/smoke-submit call. Do not wait for a separate smoke job merely because training completed. |
| D5 — MCP docs, limits, result shape | **Testable after contract clarification.** | Compare docs/mcp.md against actual discovery, registered structured/text responses, timeout/error shapes, host-path/URL semantics and the sourced limit or explicit unknown/fallback. Add only this read intent; ping remains until p1-04, and health/workers remain staged. |

These are coverage obligations derived from the task/existing contracts, not
claims that p1-03 tests already exist or pass. Coding chooses field spellings
and error codes within the accepted envelope, documenting them for exact QA.

## Timing, read risk and recovery boundaries

No actual client's enforced tool-call limit is established by the reviewed
repository/configuration. `docs/decisions/mcp.md` explicitly still lists it as
unknown. The launcher wrappers contain no client deadline. The **50-second
fallback is authorized policy, not a measured client limit**. Coding must first
record its client/configuration search, source any real bound it finds, or label
that bound unverified and use the fallback without a new owner decision.

`mcp-server/mcp_server/client.py:40` defaults HTTP calls to **60 seconds**.
Its blocking per-request timeout cannot be copied unchanged into a 50-second
overall wait; a loop with a 50-second sleep/poll count can already exceed budget
on its first request. Bound lookup, polling, all enrichment requests, sleep and
response work by one monotonic deadline. A request-level inactivity timeout
alone does not prove an overall deadline: tests need a slow first read and
repeated/slow body reads, not just instantaneous fake status changes. Terminal
completion observed near the deadline must not trigger unbounded artifact reads.
Returning compact per-artifact locators instead of full graphs/logs helps keep
the response bounded without truncating the required artifact set. No new fixed
response-count limit is inferred from this review.

Both job domains use UUIDs, so the string format is no discriminator. Resolve
using existing read endpoints and preserve which domain answered; a connection
error/5xx is not evidence that an ID belongs to the other domain or that the job
failed. A not-found result must retain recovery guidance. No extra submission
or Backend job-index redesign is needed for the ordinary lookup choice.

The approved risk is **read**, matching existing status/Gallery calls. Training
GET may reconcile already-bound smoke metadata in the Backend; that accepted
behavior never submits generation/training and needs no new MCP mutation intent.
Do not invoke cancellation, generation, smoke-submit, delivery, model downloads,
worker control or filesystem migration. Repeated waits are repeatable reads,
not deduplication of a new submission. Preserve both `cancelled` terminal states:
copying the old generation wrapper would incorrectly turn cancelled into
job_not_found. The exact cancellation envelope is a routine documented delivery
choice, but it must retain terminal identity/state and never resubmit.

Host paths are usable only by clients with that host filesystem. Relative
`/gallery/...` URLs are existing Backend locators; if made absolute, bind them
to the configured Backend base and encode them without changing file identity.
No remote retrieval proof follows from assembling a URL. Gallery-root validation
must not accept traversal, arbitrary remote locators or a different host's
container path as a verified client file. Training private paths/errors remain
under existing public redaction; model outputs never become Gallery media by
changing a suffix or borrowing an ID.

## Commands, results and limits

[Evidence index](kickoff-evidence/README.md) retains exact commands, environments,
exits, source origin and raw output. Fresh checks in this review:

- Fixed-source SHA/task pin, all 12 reference hashes, accepted manifest/report
  equality: pass. The original p1-03 task remains unchanged.
- Offline real-route/in-memory-SQLite shape probe: exit 0, 0.631 seconds. It
  exercised legacy/mixed/absolute media, safe training completion/failure/cancel,
  real fixture smoke links and generation cancellation. Queue state was mocked;
  no app lifespan, trainer, ComfyUI or product service was started.
- Three selected existing Backend tests: **3 passed, 1 existing warning in
  0.09s**, exit 0. Completed-video status, ordinary image status and video detail.
- Selected existing MCP tests: **19 passed in 0.23s**, exit 0. Real HTTP client
  under mocked transport, safe smoke projection/diagnostics and registered
  Gallery namespace/locator behavior.
- One initial Backend selection exited 4 before execution because QA named a
  nonexistent test node. Source inspection identified the correct existing
  node; only the invocation changed. The failed attempt is retained separately,
  excluded from software results. No test was edited or removed.

The short checks each used a 60-second outer process bound, dedicated roots
below run scratch and canonical component interpreters. No dependency was
installed or changed. No full suite/standing-guard rerun is required for this
source-only kickoff; the registry is untouched and no new item is certified.
Prior QA Backend 1900/124 Windows skips, MCP 460/two optional skips, parity five
and extra boundaries 15 remain **prior evidence**, not this review's results.

- **Offline/source:** the inspection, hashes, fixture routes and selected tests
  above only. No wait implementation or live deadline behavior is verified.
- **Running product service:** no probe, deployment, restart or loaded-source claim.
- **Real generation/training/download/worker dispatch:** none.
- **Artifact retrieval:** only scratch fixture bytes were created/decoded by the
  smoke reader. No live Gallery image/video retrieval or remote URL consumption.

Keep the active AID-151 runtime/worktree/private configuration, canonical venvs
and all models/datasets/outputs/Gallery records. The 23-unit/eight-incident
baseline, one cached-original/revision pair, canonical lineage and colocated
host-path proof retain their historical limits. The prior p1-02 delivery
rejection/correction 1/review 2 PASS, kickoff ambiguity/clarification history,
p1-00a history and all nine standing registry items are preserved. Live
cancel/timeout/dedup recovery, remote consumption, aesthetics, three consecutive
zero-intervention runs and phase close remain unaccepted.

## Handoff

The exact report commit, official standalone report, indexed source/reference
packet, binary report patch and verified Git bundle are pinned in AID-161's
completion receipt/comment. They are the handoff; no moving branch tip is the
review input. This report commit cannot contain its own SHA.

QA closes its recipient-owned card even with AMBIGUITY. Producer reads this
report, adopts/documents the narrow locator disposition and obtains a fresh
independent CLEAR before creating Coding and separate exact-commit delivery-QA
cards. No parent ownership, implementation, main merge/push, p1-04 release or
phase acceptance belongs to this review.
