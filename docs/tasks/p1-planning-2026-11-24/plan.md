# Phase 1 execution plan — 2026-11-24

Status: **p1-00 evidence accepted at `3081952`; p1-00a delivery round 1 FAIL (D5); bounded inventory correction next; p1-01/02 remain gated**.
Planning/coordinating issue: [AID-141](/AID/issues/AID-141).
[Initial request](../../requests/2026-11-24-fresh-producer-planning.md) ·
[later owner instruction](../../requests/2026-11-24-proceed-within-project-boundaries.md).

## Authority and adopted choices

The authenticated board relayed CTY's later instruction to proceed directly with
executable work and use routine reference options inside the project boundaries.
This supersedes the earlier planning-only framing and ordinary-choice wait. It
does not change the destination, phase order/scope, architecture, Not now list,
operating policy, three-real-run exit or independent review requirements.

Producer adopts `Illustrious-XL-v2.0.safetensors` + `default`, no LoRA and explicit
`execution_target=local` for p1-00 and p1-05. This is a delegated technical choice,
not an individual owner model selection or aesthetic approval. There is no
outstanding CTY question on the current supported path. Escalate a demonstrated
project-boundary change through native interaction plus project-channel delivery.

## Baseline and evidence

Fetched published `main` matched the clean local checkout at
`6be499f62629e6478bdb290951dbd0e6eb23c6a1`. Phase 0 remains done; Phase 1 now
proceeds under the later direction. This planning commit changes docs/specs only.

| Area | Observed source / read-only evidence | Work consequence |
|---|---|---|
| MCP surface | `tool_catalog.py`: 40 tools; 3 plain-text, 19 dict and 18 JSON-string categories; existing tool modules registered by `server.py` | Run the baseline on today's tools; envelope and consolidation still needed |
| Error boundary | Existing `tools/responses.py` helpers; `ContractFastMCP.call_tool` handles LoRA start validation only | Extend existing boundaries; test validation through the MCP call path |
| Generation/revision | Existing template/custom-workflow functions, Backend revision schema and Gallery artifact readers | Reuse them; revisions use a new generate request with `parent_artifact_id`, not `gallery_rerun` |
| Completion | Generation job endpoint returns durable artifacts; MCP has no wait tool | Read existing state; never resubmit on a wait timeout |
| Health/worker | `/api/system/status` and `/api/workers/status` already exist | Reuse these; registry/scheduler remain Phase 3 |
| Mac services | Backend healthy, system status connected; ComfyUI reports `darwin`/`mps` | Reachable now; no generation or deployed Git-revision proof implied |
| Adopted pair | Backend and ComfyUI both list the selected checkpoint; catalog marks `default` valid/SDXL; graph uses `CheckpointLoaderSimple` | No new download dependency; runtime compatibility remains p1-00 evidence |

The default graph saves an older, unlisted checkpoint filename. Pass the adopted
checkpoint explicitly through the existing generation argument; do not edit the
graph or download a replacement as a hidden baseline repair. Backend resource
listing describes Backend model directories, not worker readiness.

Read: README, AGENTS, INDEX, MEMORY and compute/model/revision topics; operating
policy; team guide, Producer role, skill bindings and channel routing; ROADMAP,
CURRENT, PROGRESS; decision files and all existing Phase 1 specs. Run-installed
Producer skills were loaded. The administrative live skill-selection GET returned
403; no configuration was changed or inferred from it. Native roster showed
Coding/QA available and other production specialists paused.

## Ordered native backlog

The existing task folders remain the implementation specifications. New native
cards give Producer coordination ownership and actual prerequisite edges; parent
links only group work. QA is the first released recipient. Coding/delivery-review
cards follow CLEAR kickoff without another routine start confirmation.

| Native card / order | Work and execution owner | Native prerequisite | Observable delivery |
|---|---|---|---|
| [AID-147](/AID/issues/AID-147), completed | QA kickoff for [p1-00](../p1-00-mcp-friction-run-mac/task.md) | Published fixed planning/spec commit `e443f2e` | [CLEAR](../p1-00-mcp-friction-run-mac/kickoff-review.md); independent reading and comparison; no execution acceptance |
| [AID-148](/AID/issues/AID-148), completed | Coding ran p1-00 without repairs | AID-147 CLEAR read by Producer before dispatch | [Evidence](../p1-00-mcp-friction-run-mac/manifest.md) `3081952`: passing Mac suite, completed original, byte retrieval/revision blocked; 23 intervention units/eight incidents |
| [AID-149](/AID/issues/AID-149), completed | QA independently reviewed p1-00 evidence | AID-148 exact delivery | [PASS](../p1-00-mcp-friction-run-mac/review.md) at `3081952` for D1-D4 including the documented-blocker route; report/registry `c377a02` |
| [AID-150](/AID/issues/AID-150), completed | QA independently reviewed [bounded Mac runtime/retrieval repair](../p1-00a-mac-runtime-and-retrieval/task.md) | Published fixed specification `4ac3d56` and accepted baseline evidence | [CLEAR](../p1-00a-mac-runtime-and-retrieval/kickoff-review.md); official report/archive/patch match `9bd0029`; no specification change |
| [AID-151](/AID/issues/AID-151), completed | Coding delivered p1-00a candidate `00ebb4d`, unmerged | AID-150 actual CLEAR read; isolated branch from published `eaf11b8`; fixed task unchanged | Runtime/client-configuration/docs-only repair; fresh pair and decoded bytes/lineage; original raw evidence retained |
| [AID-152](/AID/issues/AID-152), completed | QA independently reviewed exact candidate `00ebb4d` | AID-151 actual delivery | FAIL: D1-D4 PASS, D5 incomplete runtime inventory; report `537d47f`; no loss of old values demonstrated |
| p1-00a correction 1, next | Coding corrects inventory/schema evidence under original D5 | Actual QA finding and [bounded correction](../p1-00a-mac-runtime-and-retrieval/repair-round-1.md); original CLEAR/task unchanged | New exact candidate, complete schema delta/preservation receipts and refreshed uploads; no product change/restart/new generation indicated |
| p1-00a delivery QA round 2, next | QA independently reviews the corrected exact candidate | Native prerequisite on correction Coding | D1-D5 verdict; reuse applicable unchanged-source evidence, focus on D5; one prior rejection carries forward |
| [AID-142](/AID/issues/AID-142), 1 | Producer accepted the baseline and triages the first repair rejection | Correction and round-2 exact-commit QA before acceptance | Accepted complete repair evidence before merge/publication or later release |
| [AID-143](/AID/issues/AID-143), 2 | Producer coordinates [p1-01](../p1-01-mcp-response-envelope/task.md) + [p1-02](../p1-02-mcp-tool-consolidation/task.md); Coding; QA | AID-142 accepted usable baseline, plus newly CLEAR specs informed by its log | Uniform success/failure envelopes; catalog/intent/risk/mode coverage; docs and MCP suite; both changes published together at one reviewed final commit |
| [AID-144](/AID/issues/AID-144), 3 | Producer coordinates [p1-03](../p1-03-mcp-wait-and-result/task.md); Coding; QA | AID-143 accepted/published result; CLEAR kickoff | Complete/failed/timed-out generation/training jobs; truthful artifact/output locators; bounded calls, no timeout resubmission; sourced limit or explicit fallback |
| [AID-145](/AID/issues/AID-145), 4 | Producer coordinates [p1-04](../p1-04-mcp-health-and-workers/task.md); Coding; QA | AID-144 accepted/published result; CLEAR kickoff | Up/down/unconfigured health; empty or one configured worker; read-only risk; existing status endpoints reused |
| [AID-146](/AID/issues/AID-146), 5 | Producer coordinates [p1-05](../p1-05-mcp-e2e-smoke-mac/task.md); Coding; QA; CTY sees demo | AID-145 and all earlier accepted results; same adopted pair; CLEAR kickoff | Stdio smoke script; 3 consecutive original/revision real runs, zero manual fixes; retrieved artifacts and lineage; CTY demo reply and phase-close review request |

Keep the existing serial order. One Coding agent and one combined breaking change
make serial delivery clearer than parallel health/wait work. Phase 2 stays
inactive until Phase 1 exits and CTY reviews the roadmap at phase close.

## Specification reconciliation applied before kickoff

- The map contradicted the existing owner-confirmed LoRA exclusion. Keep
  `lora_train_job_status` and `lora_train_cancel` unchanged in Phase 1; their
  envelopes/risk labels change with the other tools. Renamed generation
  `job_status`/`cancel_job` do not absorb LoRA intents. This preserves scope.
- p1-02/p1-03 previously had six Done when items. Their existing checks are
  regrouped into at most five without dropping coverage; p1-01/02 still integrate
  together. A stale roadmap LoRA phase number is aligned to Phase 5.
- p1-03 reports training output/status honestly. No media artifact means an empty
  media list, not a fabricated image; preserve existing smoke-generation links.
- p1-03 inspects the actual client timeout. If no limit is established, use the
  existing 50-second fallback and label the client limit unverified. Include
  Backend request durations in the overall wait budget; do not certify an
  unknown limit as measured.
- p1-00's adopted resource pair is explicit in its specification and decision
  record. p1-05 reuses it. p1-00 does not fix failures: a non-passing full suite or
  blocked generation needs a bounded repair task and independent review before
  dependent work is released. A documented stop is evidence, not a phase pass.

QA independently reviews these points. A demonstrated spec defect is repaired or
escalated according to its actual effect on boundaries, not automatically sent
back to CTY as a routine technical option.

## Handoff, delivery and continuation

After CLEAR, Producer creates a Coding card and a separate QA delivery-review
card whose native prerequisite is Coding. The coordination card waits on the QA
card. QA reviews the exact delivered commit and posts its verdict on its own
issue, marking the review done even for FAIL or AMBIGUITY. Producer reads the
actual deliverable: completed prerequisites alone are not acceptance. Later code
changes need a new exact-commit review. Engineering uses isolated worktrees.

For p1-01/02, deliver a manifest in each task folder and review their combined
final commit. Merge/push together only after PASS; every later software delivery
also needs PASS. Update CURRENT/PROGRESS and continue without per-item starts.

AID-147 returned CLEAR for `e443f2e`. AID-148 delivered `3081952` without repairs;
AID-149 returned evidence-only PASS, and Producer inspected the actual manifest,
review, full bounded suite receipts, raw transcript and friction accounting. The
official attachments and exact patches match Git. The original evidence and QA
report/registry `c377a02` are integrated without changing their bytes.

The full Mac Backend suite passed twice independently: 1900 passed, 124 existing
Windows-only skips, 77 warnings; Coding 43.84s, QA 44.13s, both exit 0 with
`--timeout=60`. One original completed, with Gallery metadata only. The relative
URL failed locally before an HTTP image request; no bytes or revision were
retrieved. The live Backend omits revision context and its loaded commit is
unknown. This is an accepted baseline record, not a usable end-to-end journey.

Producer sent p1-00a to independent fixed-commit kickoff on AID-150 at `4ac3d56`.
QA returned CLEAR; Producer read the complete comparison and verified the official
report/archive/patch against QA report commit `9bd0029`. Its bounded scope
aligns the existing Backend runtime and resolves the locator/client boundary,
then proves a fresh original/revision pair with actual bytes and persisted
lineage. No envelope/consolidation/wait/health redesign is pulled forward. The
original 23-unit/eight-incident no-repair baseline remains unchanged; repair
interventions are recorded separately. Coding AID-151 delivered `00ebb4d` from
published `eaf11b8`, with unchanged product/test source. QA AID-152 returned FAIL:
D1-D4 pass, but D5 omits eight nullable training columns and a new empty reservation
table from the existing startup footprint. Its read-only audit found old values
preserved. Producer checked the official report/audit and startup source; the
candidate is not merged or accepted.

[Correction 1](../p1-00a-mac-runtime-and-retrieval/repair-round-1.md) fixes the
inventory and schema receipts within original cleared D5. No specification change,
product fix, restart or extra generation is indicated. Separate Coding and
exact-commit review round 2 carry one prior delivery rejection; applicable D1-D4
evidence may be reused with source/environment equivalence. AID-142 stays open
through acceptance; AID-141/AID-143 remain gated. No ordinary owner confirmation
or escalation threshold is pending. A blocked journey still cannot pass D3.

Later coordination cards depend on their predecessor. This is an event-driven
continuation, not polling or a prose-only promise to resume. A completed review
with FAIL or AMBIGUITY is triaged before dependent release. Any later kickoff
returning ASK OWNER/BLOCK is likewise triaged before implementation starts.

## Verification and reporting

The planning and initial dispatch rounds verified source/docs, native handoffs,
read-only health/resources and publication. The acceptance round verified the
actual completed deliveries, official attachments/archives/patches and raw call
accounting. It integrated reviewed task evidence and QA metadata and wrote the
bounded repair specification/status documents. Producer did not rerun software
suites, probe services, generate or retrieve image bytes in this acceptance
round. Accepted Coding/QA results remain attributed to those runs; prior Windows
counts remain prior evidence. The repair-dispatch follow-through verified CLEAR,
official report/archive/patch integrity and native plans/dependencies, then
published the unchanged kickoff mirror and dispatch state. It performed no
software suite, live product probe, generation or image-byte retrieval. Repair
delivery evidence remains pending; no new full MCP/Frontend/Windows result or
phase exit is implied.

Report the adopted pair, first work, native task links and actual next actor in
Traditional Chinese in Discord `1562710701280202813`. No owner response is
requested for these ordinary choices. Later delivery reports must distinguish
offline tests, running services, real generation and artifact retrieval.

The delivery-triage round inspected actual manifest/review/schema evidence and
published the bounded correction/status records only. QA's full Backend/MCP,
runtime, decoded-byte and lineage checks remain attributed to QA. D5 accounting
fails despite the verified journey; no acceptance, merge or dependent release.

Knowledge capture: the delegated-choice rule remains in roadmap/MCP decisions;
the new [runtime source-contract topic](../../memory/runtime-source-contract-verification.md)
explains why a current checkout and healthy process cannot certify loaded
revision behavior. The [startup-schema topic](../../memory/backend-startup-additive-schema.md)
explains whole-schema inventory versus old-column value preservation. Compute/model/lineage topics remain in place. Receipts and
incident accounting stay in task evidence.
