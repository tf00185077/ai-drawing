# Phase 1 execution plan — 2026-11-24

Status: **execution authorized inside existing boundaries; kickoff pending**.
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
| [AID-147](/AID/issues/AID-147), first | QA kickoff for [p1-00](../p1-00-mcp-friction-run-mac/task.md) | Published fixed planning/spec commit, pinned on its card | CLEAR / ASK OWNER / BLOCK, independent reading and material differences on the QA card |
| [AID-142](/AID/issues/AID-142), 1 | Producer coordinates p1-00; Coding executes; QA reviews evidence | AID-147; read actual verdict and require CLEAR | Mac Backend suite with `--timeout=60`; ordered stdio transcript; original + traceable revision retrieval or explicit blocker; full friction log and baseline count |
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

AID-141 waits natively on AID-142 while the first execution path proceeds. AID-142
waits on QA kickoff, then on the Coding/evidence-review chain. Later coordination
cards depend on their predecessor. This is an event-driven continuation, not
polling or a prose-only promise to resume. If kickoff returns ASK OWNER/BLOCK,
Producer triages the verdict before dispatch; no implicit implementation starts.

## Verification and reporting

This planning heartbeat verifies source/docs, native plans and prerequisite edges,
publication and kickoff release. Read-only Backend/ComfyUI health/resource probes
succeeded. No software was changed; no Backend/MCP/frontend suite was rerun, no
image generated and no new Gallery artifact retrieved. Prior Windows counts stay
prior evidence; Mac Backend verification is p1-00's first execution action.

Report the adopted pair, first work, native task links and actual next actor in
Traditional Chinese in Discord `1562710701280202813`. No owner response is
requested for these ordinary choices. Later delivery reports must distinguish
offline tests, running services, real generation and artifact retrieval.

Knowledge capture: the delegated-choice rule and its reason are recorded in
roadmap/MCP decisions with source provenance. Existing memory already covers
compute targets, model loaders and revision lineage; transient receipts do not
become memory topics.
