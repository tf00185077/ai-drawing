Verdict: AMBIGUITY

Review type: independent kickoff only, 2026-11-24. QA: [AID-155](/AID/issues/AID-155).
Fixed specification/source: `d1ffb8d8d9db12f728ed98704e966e76489faafb`.
Task: `docs/tasks/p1-02-mcp-tool-consolidation/task.md`.
Task SHA-256: `b5b650b882bbe1659fd9cf0d84e3cc33b13d895453c52c8cab6d5dbb2146a7a9`.

One bounded intent/risk clarification is needed before Coding. The separate
[p1-01 kickoff](../p1-01-mcp-response-envelope/kickoff-review.md) is CLEAR; that
does not clear this task or release their combined delivery. This is not a
delivery rejection: p1-01/02 have no implementation delivery yet.

## Independent owner reading and comparison

My reading: reduce overlapping tools to one per intent with one truthful risk
label, preserve the Phase 1 capabilities and canonical Backend state, leave
Civitai and all LoRA names unchanged except the explicitly removed generate-like
tool, remove both video tools only from MCP, and ship the envelope/consolidation
together. Keep temporary ping, then add wait and health/workers in the later
tasks. Routine internal choices are delegated to Producer; no ordinary CTY
confirmation is pending.

This reading was saved after the preserved owner direction, approved decisions
and active milestone were read, before opening the fixed on-disk task files.
The inline assignment already exposed their contents. Sources are the [later
owner instruction](../../requests/2026-11-24-proceed-within-project-boundaries.md),
[approved tool map](../../decisions/mcp.md#tool-map),
[roadmap](../../roadmap/ROADMAP.md) and
[execution plan](../p1-planning-2026-11-24/plan.md).

Difference: the task/map do not settle an existing optional write capability
inside the tool assigned the new read-only prompt-composition intent.

## Finding K2-1 — P1, D1/D2 and associated D3 coverage

The approved map assigns `prompt_library_compose` to `prompt_compose`, risk
`read` (`docs/decisions/mcp.md:60`). Existing source exposes `save_as` in
`mcp-server/mcp_server/tools/prompt_library.py:96`, forwards it at line 99 to
`POST /api/prompt-library/compose`, and the Backend's
`FilePromptLibraryProvider.compose` calls `_writer.save_combination` when it is
present (`backend/app/core/prompt_library.py:148`).
`backend/app/schemas/prompt_library.py:163` includes that save intent in the
request contract. This is persistent writing, not just rendering a prompt:
`backend/tests/test_prompt_library_api.py::test_compose_can_save_and_read_back_safe_unicode_combination_id`
contains a save followed by a successful readback assertion. I inspected these
sources; I did not execute that write or test.

Concrete scenario: Coding can rename the current callable to `prompt_compose`,
retain `save_as`, set its catalog/description risk to `read`, and pass the stated
label/registration checks. An agent selecting this read-labeled tool can then
create or update a stored combination. Conversely, deleting the optional save
path without an explicit disposition can lose a currently exposed capability
while the 40-name table still appears complete.

D1 requires every old tool's intent/risk/mode disposition, D2 requires the single
risk label, and D3 requires merged mode/action coverage. None explicitly resolves
this old mixed-intent optional mode or requires a negative guard against writes
through the new read intent. Name coverage plus label cardinality alone cannot
judge that outcome. The issue is the proposed map applied to the actual source,
not a request to repair an unrelated Backend feature.

Producer action: pin the disposition of compose-with-save and its MCP-path
acceptance check before Coding. Recommended bounded interpretation: retain
`prompt_compose` as pure composition, explicitly remove/reject its `save_as`
write path at MCP, and document saving composed fragments through
`prompt_write(action=save)` with the existing revision/ETag contract. State that
optional-capability migration in the old-to-new mapping and require a registered
MCP test proving the read tool cannot reach the writer, plus coverage of the
replacement write path. Backend compose/save behavior can remain unchanged.

This recommendation follows the existing read/write intent map; Producer owns
the final clarification and a fresh fixed-spec kickoff. QA has not edited the
specification or selected an implementation. No new CTY boundary decision is
demonstrated by this finding. Do not dispatch combined Coding until both fixed
specifications actually have CLEAR.

## All 40 baseline dispositions checked

The following is QA's source-to-map cross-check, not Coding's future manifest.
All old names occur exactly once. There are 15 retained names, eight renames,
14 old entries merged into six destinations, and three removals: 29 provisional
delivered names. Names may still change within the spec's QA-agreement rule.
Risks for retained tools that the map does not explicitly label are source-based
QA proposals for Coding to state in its manifest; no new behavior is approved.
Removed rows show their old intent's risk for accounting, not a delivered label.

| Old tool | Disposition / destination | Intent; mode/action or selector | Risk |
|---|---|---|---|
| `mcp_ping` | keep | Backend connectivity; transitional | read |
| `civitai_source_info` | keep | Civitai preview | read |
| `civitai_generate_like` | remove from MCP | Civitai reproduction; Backend frozen | mutate |
| `civitai_resource_acquire` | keep | Civitai download | mutate |
| `civitai_resource_status` | keep | Acquisition status | read |
| `generate_image` | merge → `generate` | Image generation; `template` | mutate |
| `generate_image_custom_workflow` | merge → `generate` | Image generation; `custom_workflow` | mutate |
| `generate_video_wan_keyframes` | remove from MCP | Wan video; Backend frozen | mutate |
| `generate_video_custom_workflow` | remove from MCP | Custom video; Backend frozen | mutate |
| `get_generation_status` | rename → `job_status` | Generation status; same job ID | read |
| `cancel_job` | keep | Generation-queue cancellation | mutate |
| `list_available_resources` | rename → `list_resources` | Discover resources and generation forms | read |
| `deliver_generation_result_to_discord` | rename → `deliver_to_discord` | Completed-job delivery; allowlisted alias, dedup/force-resend | mutate |
| `gallery_list` | rename → `gallery_search` | Gallery search; filters/pagination | read |
| `get_gallery_image` | merge → `gallery_get` | Retrieval; image-ID branch | read |
| `get_gallery_artifact` | merge → `gallery_get` | Retrieval; canonical artifact-ID branch | read |
| `gallery_rerun` | keep | Replay recorded image parameters; not revision | mutate |
| `free_comfyui_memory` | merge → `comfyui_admin` | Administration; `free_memory` | admin |
| `comfyui_node_provision` | merge → `comfyui_admin` | Administration; `install_node` | admin |
| `comfyui_restart` | merge → `comfyui_admin` | Administration; `restart` | admin |
| `create_style_preset` | merge → `style_preset_save` | Save preset; from fields | mutate |
| `list_style_presets` | merge → `style_preset_get` | Read preset; no ID = list | read |
| `get_style_preset` | merge → `style_preset_get` | Read preset; ID = detail | read |
| `compose_style_preset` | rename → `style_preset_compose` | Compose payload; does not generate | read |
| `save_successful_workflow_as_style_preset` | merge → `style_preset_save` | Save preset; from successful job | mutate |
| `test_saved_style_preset_workflow` | rename → `style_preset_test` | Submit saved server-owned graph | mutate |
| `prompt_library_search` | rename → `prompt_search` | Catalog/category/search | read |
| `prompt_library_save` | merge → `prompt_write` | Write prompts; `save` | mutate |
| `prompt_library_compose` | rename → `prompt_compose`; K2-1 unresolved | Compose; existing optional `save_as` writes | read in map; write capability unresolved |
| `prompt_library_archive` | merge → `prompt_write` | Write prompts; `archive` | mutate |
| `prompt_library_restore` | merge → `prompt_write` | Write prompts; `restore` | mutate |
| `caption_image` | keep | Caption image | mutate |
| `lora_training_decision_preflight` | keep | Non-starting training decision | read |
| `lora_train_start` | keep | Start training | mutate |
| `lora_train_job_status` | keep | Training status; separate from generation | read |
| `lora_train_logs` | keep | Bounded training logs | read |
| `lora_train_cancel` | keep | Training cancellation; separate from generation | mutate |
| `lora_dataset_list` | keep | List datasets | read |
| `lora_dataset_inspect` | keep | Inspect dataset | read |
| `lora_train_smoke_test` | keep | Existing submit-once/return-existing smoke intent | mutate |

Static AST enumeration finds all 40 catalog entries and exactly matching
`@mcp.tool()` registrations. Retained baseline live discovery matches them too.
All nine LoRA/caption names and three retained Civitai names remain distinct.
No training status/cancel is absorbed by the generation tools. Both image
generation modes and all removed video/generate-like entries are explicit.

## Other acceptance gates and preservation checks

| Item | Kickoff assessment |
|---|---|
| D1 — registration and complete old-to-new mapping | Observable through `test_tool_catalog.py`, static catalog/registration equality and manual 40-row comparison. K2-1 prevents complete capability/risk disposition for one row. |
| D2 — exactly one risk in catalog and description | Metadata cardinality is observable. K2-1 must pin the prompt-composition capability so the label is truthful as well. |
| D3 — every merged mode/action through MCP | Observable via `mcp.call_tool`, with mocks below each real wrapper. Minimum branches: two generate modes; image/artifact Gallery selectors; three prompt-write actions; preset list/detail; preset fields/successful-job save; three ComfyUI actions. Preserve existing internal resource-type, concurrency and error checks as well. Add the resolved K2-1 boundary guard. |
| D4 — friction fixed or explained | Complete F1–F8 disposition agrees with accepted evidence, as reconciled below. Only F3 is directly fixed; F5/F8 preservation remains material. |
| D5 — executable/staged docs and MCP suite | Observable. Current flow uses `mcp_ping → list_resources → generate → job_status` polling, then `gallery_get`; health/wait must be labeled staged. Full MCP suite with isolated root and `--timeout=60`; no new failures. |

Preservation requirements are concrete at the source boundary:

- `tools/generate.py` forwards `revision_context` and distinguishes omitted
  `loras` from `[]`. Preserve those meanings in `generate(template)`; Backend
  resolves the canonical parent. Custom-workflow behavior stays its existing
  supported behavior; this task adds no Backend revision contract to it.
- `tools/gallery.py:43` constructs an image `local_path` from configured Gallery
  root while preserving a returned URL; line 86 forwards canonical-artifact
  locators and metadata. Merging must explicitly distinguish image IDs from
  artifact IDs, retain metadata/context and supported locators, and retain
  existing artifact retrieval even though new video submissions leave MCP.
- `gallery_rerun` remains parameter replay. `job_status` and generation cancel
  must retain their status/error semantics. LoRA status/cancel and existing
  uncertain-admission recovery stay separate. Do not add automatic resubmission
  or fallback to local execution after worker failure.
- Preserve prompt revision/ETag guards and restore locators; the saved-preset
  server-owned graph and explicit save semantics; direct local ComfyUI targeting;
  and Discord allowlisted-alias/dedup behavior. Risk labels do not broaden any
  endpoint, destination or security boundary. No new worker control is needed.
- The stated documentation scope includes `docs/mcp.md`, operating policy,
  architecture, style/workflow READMEs, affected memory and team role prompts.
  Rewrite current executable examples and old response-shape guidance; retain
  historical task evidence. `docs/mcp.md` also still describes repair QA as
  pending, which should be reconciled while its current flows are rewritten.
  Backend removal or later wait/health implementation is outside this delivery.

## Friction and prerequisite evidence

I independently agree with all eight rows in the fixed
[kickoff context](../p1-01-mcp-response-envelope/kickoff-context.md) and the
complete per-row reconciliation in the [p1-01
report](../p1-01-mcp-response-envelope/kickoff-review.md#original-friction-and-accepted-repair-reconciliation):
F1=1 setup (p1-05), F2=1 bootstrap (p1-05), F3=1 parsing (direct p1-01/02),
F4=6 runtime diagnostics (bounded launch repaired; general visibility p1-04),
F5=1 revision mismatch (new persistence repaired; preserve here), F6=11 polls
(p1-03), F7=1 visibility (p1-03/04), F8=1 failed relative-URL consumption
(colocated host-path repair accepted; preserve here, later result/smoke proof).
Total remains **23 units/eight incidents**, including the original failed
retrieval/revision outcome. No count is subtracted or attributed to this new task.

I read the actual original manifest/review, corrected repair manifest,
acceptance, final PASS and historical FAIL. Fixed Git comparisons retain all 20
original baseline files unchanged, corrected repair manifest/raw flow at
`b6d58468147e11a21b3d7a26ea25ed4353a28a28`, final review at
`3d5d8902a89a8c3c8994ed89e944fcaee0260577` and historical round-1 review.
Publication `a963386a3141194a6a08853d89224b548d112aa2` accepted one bounded
original/revision pair with canonical lineage and real decoded bytes from both
Gallery tools' unmodified host paths, for a colocated Mac client. The original
used cache. Remote/relative-URL consumption, timeout/cancellation/recovery,
idempotency, aesthetics, demo and three-zero-intervention-run phase exit remain
unproved. The one rejection/correction round 1/review round 2 remain p1-00a's
history, not p1-01/02's.

## Verification, artifacts and handoff

Review used recipient-owned branch `aid-155-fixed-kickoff-review` at
`/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-155-kickoff-review`,
created at the full fixed specification SHA. No p1-01/02 manifest exists there.
Source/contract, Git-object and AST checks were read-only. The static audit
command and complete verification limits are recorded in the p1-01 report;
it exited 0 with all 40 dispositions covered and K2-1 positively identified.
`git diff --check` and outgoing exact-file/package checks are part of this
report handoff. The two committed reports, task digests, audit source/JSON,
independent owner reading and exact patch are uploaded on AID-155. Package
receipt records the full report commit and file hashes.

No offline software suite, product-service probe, restart, generation or live
image-byte retrieval was performed. Historical independent Backend
`1900 passed / 124 Windows-only skips` and MCP `314 passed / 4 exported-fixture
skips` were inspected as accepted prior evidence; they do not test future
consolidation. This kickoff adds no registry certification. Shared main, the
active AID-151 worktree/private configuration, canonical Backend venv, models,
datasets, outputs and Gallery records were left untouched.

Complete this QA card with AMBIGUITY as its delivered verdict. Producer on
[AID-143](/AID/issues/AID-143) owns clarification, a fresh fixed-spec kickoff and
later dispatch. After both tasks actually clear, use separate Coding and QA
delivery cards, with native QA dependency on Coding; inspect one combined exact
final commit and both manifests. Independent PASS precedes combined merge/push.
Any later candidate change requires a new exact-commit review. Completing this
kickoff card does not satisfy that release gate.
