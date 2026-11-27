Verdict: CLEAR
Review round: 2

Review type: independent kickoff only. Date: 2026-11-24.
QA: [AID-162](/AID/issues/AID-162). Producer: [AID-144](/AID/issues/AID-144).
Fixed published source: **`522c2f10b550d90f7b88ab1a3c9d1f6352439c8e`**.
Task: `docs/tasks/p1-03-mcp-wait-and-result/task.md`.
Task SHA-256: **`0d25f752ed4f17b28a01109c10c163e57532ae4b7e11832b8361f63a67af6688`**.
Done when count: **5**. No p1-03 implementation manifest exists at this source.

**K3-1 is resolved at specification level.** The clarified task and normative
decision form an implementable, testable contract for all five items. No
remaining AMBIGUITY, ASK OWNER or BLOCK is demonstrated. This CLEAR permits
Producer's Coding handoff; it does not accept implementation, deployment or a
Phase 1 exit.

## Independent owner reading and difference

My reading: the owner expects Phase 1 to remove agent-side polling and separate
result discovery through one bounded read. Backend state, identities, artifacts
and provenance stay authoritative. Generation returns truthful existing media
references; training returns existing public output and independently bound
smoke references. Timeout preserves the same job for repeatable reads without
cancellation or resubmission. Common envelopes, one risk per intent, phase order
and CTY's aesthetic/phase-close authority remain. Unsupported historic locators
must be explained without inventing data, changing storage or exposing new files.

I recorded this reading before
opening the worktree task; the inline assignment had already exposed its text.
I read the preserved owner request, roadmap/current plan and later independently
fetched the exact [board comment](/AID/issues/AID-141#comment-afe71bd8-7e9e-434b-af00-813f94c8d131).
Its authenticated author is `local-board`, explicitly relaying CTY through
Hermes; it is not a direct CTY-authored API comment. Its words match the preserved
[request](../../requests/2026-11-24-proceed-within-project-boundaries.md).
Routine technical choices are delegated; the independent review gates remain.

Difference: **none requiring correction**. Producer's locator-error disposition
is a narrow read-result contract inside the approved phase, not a storage,
architecture, training or exposure change. I assessed it independently of
Producer's assertion that K3-1 was settled.

## Fixed inputs and preserved history

The isolated worktree is `ai-drawing-worktrees/aid-162-kickoff-review`, branch
`aid-162-p1-03-kickoff-round-2`, based exactly on the full source above.
Pre-review pin records the source and
task digest. All **17 supplied immutable reference hashes match** checked-out
and Git bytes. See the identity audit
and source index.

I read both accepted p1-01/02 author manifests, later QA reports and acceptance.
The manifests equal corrected feature `616f67ff68fc27070e85861e94d70de1baf5082a`;
the reports equal QA `28cd4512b8ec7d6594ec972ab81161b8c2d09d03`. Their author-time
pending-review text is followed by actual PASS/acceptance. The 29-intent envelope
and risk surface, separate generation/training status and image/artifact
namespaces remain the starting contract. Adding this one approved `read` intent
does not rename LoRA tools, restore removed video submissions or advance health.

The delta from first reviewed `7a46cb70bde83ba18417620ead3759a78e3c7c14` is entirely
documentation/evidence: no product, test, dependency or registry change. The
original task mirror equals that source's task; the historical round-1 report
and all 15 original evidence files equal QA `b3276dc0c138fea8f99fed4a19b76e3a20043781`.
The nine-item registry is byte-identical and untouched. No new guard or coverage
row is certified by this kickoff.

## K3-1 resolution against actual readers

The original adverse report identified two real
source shapes. Both are still supported; the clarification now states what
wait must return instead of requiring nonexistent metadata:

- `generate.py:get_job_status` reads a completed legacy `GeneratedImage` without
  a canonical artifact row. The fresh fixture returns image ID **901**, its
  relative path and `artifacts: []`. Revised D1 preserves a separate legacy
  image namespace with no invented artifact ID. Mixed image/video canonical
  records retain their actual IDs, kinds, order and revision/provenance fields.
- `gallery.py:_to_image_url` supplies no Gallery URL for a stored absolute path
  outside the Backend Gallery root; `_artifact_local_path` retains that absolute
  path. `ArtifactDetail` permits null locators. The fresh artifact **43** has
  `artifact_url: null`. The decision now requires `artifact_locator_unavailable`,
  completed Backend status/job/domain and the full known identity set. Available
  safe locators survive; unavailable locators remain null/absent. No basename
  remapping, container-path guessing, file copying or new file exposure is needed.
- `lora_smoke.reference` explicitly supports image-only legacy smoke. The added
  fresh route fixture returns completed training, smoke job `legacy-smoke-gen`,
  image ID **903**, null artifact ID and the existing Gallery URL. Other fixtures
  preserve completed training with queued, failed, cancelled or
  `artifact_unavailable` smoke, retaining safe code/hint. Training completion
  therefore need not fabricate media or await/resubmit its separate smoke job.

Full responses,
compact shapes and the
reproducer substantiate
these source cases. They use real HTTP routes and SQLite in memory, mocked queue
observations and scratch fixture bytes, with no app lifespan or product service.
Historical first-round results were inspected and preserved, not relabeled
as this review's execution or as a production incident.

## D1–D5 assessment and delivery obligations

| Item | Round-2 assessment | Required later verification |
|---|---|---|
| D1 — complete generation and truthful locators | **CLEAR.** Normal canonical media, separate legacy images and unavailable/unsafe locator errors now have distinct outcomes. Error details retain completed state and every known canonical/legacy identity even for mixed available/unavailable results. | Registered MCP through real adapters/HTTP client with transport mocked: multiple/mixed image-video results; distinct image/artifact IDs; nested/Unicode and encoded URLs; relative Backend URL binding; legacy success; missing URL/path, outside-root/container paths, traversal/escape/arbitrary remote URL and mixed failures. Assert no omitted required artifacts, fabricated ID/path/URL or file writes; preserve revision references. |
| D2 — failed jobs and diagnostics | **CLEAR.** Existing Backend failure reason/code can be projected safely in the common error envelope. A successful training status read is not successful training. Terminal cancellation is explicitly retained. | Failed and cancelled jobs in both domains, job ID/domain/status, generation node/recording diagnostics and public training error/code/hint; preserve surviving training output on registration failure without exposing private raw errors. Neither cancellation nor failure triggers a submission. |
| D3 — total deadline and repeatable recovery | **CLEAR.** Unknown client limit has an explicit authorized 50-second fallback; the budget includes lookup, polling, enrichment, sleep and response preparation. Timeout retains current/last-known status, explicitly unknown before any completed read. | Clamp high requests; consume budget in first read, domain fallback lookup and enrichment; completion near deadline must not launch unbounded enrichment. Include incremental/slow body behavior and a short real elapsed-time mocked-transport check, beyond instantaneous fake clocks. Repeated same-ID calls recover by reads only, with zero cancellation/resubmission. Record sourced client limit or explicit unknown/fallback. |
| D4 — training and independent smoke | **CLEAR.** Public model output/registration remains separate from Gallery media; no real media means `artifacts: []`. Nullable canonical artifact IDs and separate image IDs are supported. Smoke failure does not fail completed training. | Mock existing public Backend shapes for complete/failed/cancelled/pending training, no media and real/legacy/absent/pending/failed/cancelled/unavailable smoke. Preserve safe diagnostics and independently bound IDs/locators; never wait for or submit smoke/training. No real training run is required. |
| D5 — MCP documentation | **CLEAR.** Documentation can describe the above actual shapes and scope without promising retrieval or an unmeasured client limit. | Read delivered docs against discovery, registered structured/text envelopes, actual timeout/error/legacy namespaces and supported host/URL semantics. Keep ping until p1-04; health/workers remain staged. |

These are implementable acceptance requirements, **not passing p1-03 tests**.
Exact envelope field spellings for cancellation/timeout are ordinary Coding
choices to document and test; they cannot discard the required identity/state.
Delivery still needs an exact final commit, manifest and independent PASS.

## Deadline, lookup and security assessment

The reviewed tracked client/server/configuration/wrappers do not establish the
actual calling client's enforced limit. The normative decision still lists it
as unknown. Search evidence
records the **unverified client limit / 50-second overall fallback**; 50 is
approved policy, not a measured client timeout. Coding must first record any
additional client-limit source it finds, or retain this explicit unknown.

`HttpBackendClient` currently defaults to **60 seconds per HTTP request**. A
50-second polling loop around that unchanged blocking call would violate D3.
An inactivity timeout alone also cannot prove the total bound. The clarified
single monotonic deadline makes the necessary MCP-side transport/control change
testable without Backend redesign. Slow lookup/enrichment and response work
share that budget; status observed completed near the deadline can truthfully
return timeout if complete result preparation has not finished.

Both job domains use UUIDs; their formats cannot select a domain. Existing read
endpoints suffice. Only an actual not-found outcome permits the corresponding
fallback lookup; a connection failure or 5xx must preserve safe read failure and
target identity instead of pretending absence. A repeated call observes the same
job. This creates no submission deduplication mechanism and needs none for a read.
The existing generation wrapper's cancelled-to-not-found behavior must not be
copied into the new wait result.

Gallery-relative paths and Backend Gallery URLs can establish supported mapping
without a new file copy. Absolute paths require an established Gallery
relationship, including safe containment; an unrelated host/container absolute
path is not proof. Preserve nested/Unicode file identity and URL encoding;
reject escape/traversal and arbitrary remote targets. Host paths require access
to that filesystem. Constructed locators establish neither file existence nor
remote consumption. Training output uses existing public projection/redaction;
a safetensors path is not an image/video artifact.

Backend training status may reconcile already-bound smoke metadata as an
existing read behavior. It submits no job; preserving it is consistent with the
approved `read` risk. No new Backend migration, file route, push notification,
worker exposure, automatic retry or phase-boundary decision is required.

## Checks, results and limits

Exact command arrays, isolated root environments, elapsed times, exits and raw
output are in the evidence index.
Fresh checks, all exit 0:

- Source/task pin; 17 supplied reference hashes; accepted manifest/report
  equality; docs-only delta; historical task/report/evidence and registry
  preservation: pass.
- Extended offline real-route/in-memory-SQLite probe: **0.707 seconds**, all
  assertions passed, including legacy nullable smoke and independent smoke states.
- Three selected existing Backend tests: **3 passed, 1 existing warning in
  0.10s**. Completed video, legacy image status and video detail.
- Selected MCP cases: **19 passed in 0.26s**. Existing safe smoke projection and
  diagnostics through actual HTTP client under mocked transport, plus registered
  Gallery identity/locator/lineage behavior.

The short processes each had a 60-second outer bound and dedicated scratch roots.
Canonical Backend/MCP interpreters were used unchanged; current package/platform
metadata is retained. No package was installed. Prior source is equivalent for
these checks, but prior unrecorded package versions are not asserted equivalent:
the selected checks and expanded probe were executed afresh. Historical full
Backend 1900/124 Windows skips, MCP 460/two optional skips, parity five and extra
boundaries 15 remain attributed to AID-160. Full suites/standing guards were not
rerun or recertified for this source-only kickoff, as assigned.

- **Offline/source:** only the inspections, hashes, route fixtures and selected
  tests above. No wait implementation or delivered deadline is verified.
- **Running product service:** no probe, restart, deployment or loaded-source claim.
- **Real generation/training/download/worker dispatch:** none.
- **Generated-artifact retrieval:** only isolated fixture PNG verification in
  the smoke reader; no live Gallery-byte read or remote URL consumption.

Keep AID-151's active runtime/worktree/private configuration, canonical venvs and
all models/datasets/outputs/Gallery records. The historical 23-unit/eight-incident
baseline and one cached-original/revision colocated-path proof keep their limits.
Live timeout/cancel/dedup recovery, remote consumption, aesthetics, three
zero-intervention runs and phase close remain unaccepted.

Accounting remains one p1-03 kickoff ambiguity / clarification round 1 / kickoff
round 2 **CLEAR**, with no p1-03 implementation delivery rejection. Preserve the
separate p1-02 kickoff ambiguity/round-2 CLEAR and one delivery rejection /
correction 1 / delivery review 2 PASS; p1-00a's one rejection/correction 1/review 2
PASS remains separate. All nine standing registry items remain unchanged.

## Handoff

The official report, indexed immutable source/evidence packet, exact binary patch
and verified Git bundle are published on QA's own [AID-162](/AID/issues/AID-162).
The completion receipt/comment pins the full report commit SHA; a commit cannot
contain its own hash. No moving branch tip is the reviewed source.

Producer reads this actual CLEAR, then creates Coding and separate exact-commit
delivery QA with native Coding → Review → Producer prerequisites. QA closes its
recipient card after publishing this verdict. This review performs no main
merge/push, parent takeover, p1-04 release or implementation acceptance.
