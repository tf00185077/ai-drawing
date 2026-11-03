# Roadmap

Draft for owner review — 2026-11-03. **OWNER DECISION NEEDED:** the proposed milestone order, exits, Not-now list, selection order and thresholds below are not yet approved. Existing [Goal](../GOAL.md) and exact operation grants remain authoritative. Until adoption, only the owner-requested checkpoint and work already required by existing approvals may proceed.

## Destination and constraints

A user requests an image in the project channel, obtains a retrievable result from their local ComfyUI through MCP, and can request a specified style and a traceable revision. The existing simple UI supports generation and training progress, errors and results. An authorized LoRA request produces a valid, clearly named model in its own run folder, readable effective parameters, supported selection and a retrievable smoke image. Native feature requests reach reviewed, integrated delivery.

Success requires evidence from these actual journeys. Source tests, a listed tool, a healthy listener and an unmerged candidate do not establish running capability. Independent technical QA and CTY's aesthetic acceptance remain separate. See [Goal and milestone assessment](../GOAL.md#milestone-assessment).

Constraints: retain the Backend/FastAPI, React/Vite, MCP and ComfyUI architecture; canonical job/artifact/provenance records; existing data and frozen evidence; role separation and independent QA. Windows installation/reporting remains deferred. No deadline or new compute campaign is approved here. Preserve finite attempts, exact data/source operation grants, caller holds, backup/restore, resource, spending and deployment gates. Do not restart ComfyUI, substitute compute or reopen stopped maintenance from a planning decision.

## Unknowns, ranked by cost of being wrong

| Rank | Unknown and consequence | Cheapest real evidence |
| --- | --- | --- |
| 1 | Can the reviewed application run with the user's existing state and carry a request to a retrievable result? Incorrect source/state adoption affects every journey and risks existing records. | Resolve the specific integration barrier, then one separately authorized real image request and revision through MCP and the existing UI, retaining jobs and artifacts. |
| 2 | Can the supported trainer produce a usable new model with correct naming, isolation and effective parameters? A wrong assumption wastes dataset preparation and GPU work. | One explicitly scoped dataset/base-model training run, followed by selection and one smoke image, with real artifact retrieval. |
| 3 | Can the team repeat the requested style/revision and feature-delivery journey without losing lineage? Technical completion alone may not meet the user's purpose. | CTY reviews the first delivered images; one real feedback revision and one real feature intake are traced through delivery. |

The source and design checkpoint is complete within its stated limits; it does not answer these product questions. [Checkpoint and exact evidence](../checkpoints/2026-11-03-source-design.md).

## Milestones — proposed, not in force

### M1 — Can a user obtain and revise an image through the existing MCP/UI? (proposed active; status: not started)

Evidence path: reuse accepted source and QA → resolve a safe source/state integration path → verify the identified integrated version independently → obtain an exact authorized request, target and caller arrangement → submit one real image request through MCP → retrieve its canonical artifact → inspect status, errors and results in the current UI → deliver one feedback-bound revision.

Exit: the intended ComfyUI target, canonical IDs and artifact lineage are demonstrated; results can be retrieved without a duplicate submission; the existing UI shows useful progress/errors/results; independent QA confirms the integrated journey. Hermes confirms the functional milestone within delegation. CTY separately judges image/style aesthetics; no missing aesthetic decision is inferred as acceptance.

Remaining: source integration, runtime/data readiness and actual execution/artifact/UI evidence. The retained maintenance path remains unavailable; no replacement architecture is selected. Repeating the same refusal or readiness review produces no new evidence. [Integration checkpoint task](http://127.0.0.1:3100/AID/issues/AID-94) may establish Git feasibility, not runtime readiness.

### M2 — Can an authorized training request yield a usable named LoRA and smoke result? (status: not started; proposed next)

Question: can the intended supported base model and versioned dataset reach an attributed valid final model, readable actual parameters, supported selection and a retrievable smoke image through the existing Backend/MCP/UI?

Exit: real training and smoke job/artifact records demonstrate that sequence without overwriting another run; independent QA confirms technical behavior; Hermes confirms the functional milestone, with CTY's model/image-effect judgment recorded separately. Dataset, base model, resource and execution approvals must be specific to that run.

### Later direction — repeatable requested styles, revisions and feature delivery

Use actual channel requests and CTY feedback to establish repeatability and close concrete journey gaps. Define the milestone exit after M1/M2 evidence; do not invent a speculative feature backlog.

## Not now — OWNER DECISION NEEDED

- A new VM/storage/control architecture or relaxed protection policy: revisit only through an exact architecture/policy decision supported by the accepted comparison.
- More generic maintenance hardening or repeated unavailable-operation reviews: revisit only when new evidence identifies a finite mechanism or defect on M1's path.
- Windows installation/reporting: revisit when CTY lifts the current deferral; no alternate compute is implied.
- New generation/training campaigns, model acquisition, supplemental datasets or unrelated UI redesign: revisit with the relevant milestone and actual authority.
- Watchdogs, recurring decision polling or replacement monitoring: the withdrawal remains in force; fresh approval is required.

## Task selection and escalation — OWNER DECISION NEEDED

Proposed priority: (1) an explicit owner request, including this checkpoint; (2) a concrete blocker preventing the active milestone's cheapest real evidence; (3) the next step producing that evidence. A prerequisite qualifies only if that path cannot proceed without it. Keep source-only and real-journey advancement distinct.

Proposed thresholds: ask after **3 consecutive completed tasks without advancing the active milestone's real evidence**, or **2 calendar days blocked**. These are proposed review triggers, not operational retry allowances or new schedules. Counters start from an explicitly recorded adoption baseline; the existing multi-day integration block must be reviewed immediately rather than erased at adoption.

Stop starting work in an affected direction and request an owner/delegated decision when an exit is claimed, a task falls outside the evidence path, milestone order/Not-now changes, a threshold is reached, a constraint changes, or an unresolved roadmap choice blocks selection. Finish authorized in-flight work while waiting. Producer keeps task selection and technical judgment; Hermes handles delegated routine decisions, while CTY-reserved architecture, permission and aesthetic choices remain reserved.

## Review proposal

**A — Recommended:** adopt the image-first order, exits, Not-now/selection rules and 3-task/2-day triggers. Cost: one review and the already-required integration checkpoint; the first real image evidence still depends on resolving the named integration/operation gates. No new compute or service action follows from adoption.

**B:** prioritize training evidence first, then image/MCP/UI. Cost: re-order the evidence path and obtain an exact dataset/base-model/compute scope; real evidence cannot arrive until those prerequisites and safe integration are satisfied. This may expose model feasibility earlier, but requires more preparation than the first image.

**C:** retain the checkpoint and defer product selection until an exact integration/architecture decision is available. Cost: product journey evidence remains blocked for that decision's duration; checkpoint publication and preservation can finish now. Name the next decision owner and action rather than requesting another general readiness cycle.

Review the [native plan and decision path](http://127.0.0.1:3100/AID/issues/AID-93#document-plan). The earlier [source/design milestone question](http://127.0.0.1:3100/AID/issues/AID-4) remains a separate pending record; this proposal does not answer it.

## Review history

- 2026-11-03 — Draft created under [CTY's checkpoint instruction](http://127.0.0.1:3100/AID/issues/AID-93). Destination and preserved constraints come from [Goal](../GOAL.md) and its linked owner decisions. No milestone order, exit, Not-now/selection rule or threshold is approved by this entry; no product milestone is claimed done.

At first approval, record the exact decision/revision here, move the then-existing PROGRESS unchanged to `docs/progress/before-roadmap.md`, and initialize the new linked history. Preserve existing anchor routes to that archive. This draft does not perform the first-adoption migration.
