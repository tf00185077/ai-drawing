Verdict: CLEAR
Review round: 2

Review type: independent kickoff only, 2026-11-24. QA: [AID-156](/AID/issues/AID-156).
Fixed specification/source: `496cee2f842dc9386d336afb237075bf952271ce`.
Task: `docs/tasks/p1-02-mcp-tool-consolidation/task.md`.
Task SHA-256: `9b9540278fdf041f66ce3fd80f218e4d7260d34a002814471ff8094e62102028`.
Done when count: **5**. [p1-01 round-2 verdict](../p1-01-mcp-response-envelope/kickoff-review.md): **CLEAR**.

## Independent owner reading and comparison

My reading: reduce overlapping tools to one per intent and one truthful risk,
retain needed Phase 1 capabilities and Backend-owned state, and preserve the
approved Civitai/LoRA exclusions and staged phase order. A read-labeled compose
must never persist; saving must remain available through the existing mutate
intent with fragments, metadata, provenance and optimistic concurrency intact.
Explicitly rejecting legacy save requests avoids returning a misleading unsaved
success. Routine internal choices are delegated to Producer; no CTY boundary
question is demonstrated.

I saved this reading after the [owner direction](../../requests/2026-11-24-proceed-within-project-boundaries.md),
[approved decisions/map](../../decisions/mcp.md) and roadmap, before opening the
on-disk tasks; the inline assignment already exposed their text. Difference:
none at this fixed clarified specification. This is an independent comparison,
not acceptance merely because the prerequisite or first review completed.

## Finding K2-1 — resolved; P1, D1/D2 and associated D3

The historical finding remains intact. I independently
checked clarification 1, the normative
[composition/save contract](../../decisions/mcp.md#prompt-composition-and-saving)
and the actual unchanged source:

- `mcp-server/mcp_server/tools/prompt_library.py:96` advertises `save_as` and
  forwards a truthy value into compose; empty/null is currently ignored by that
  wrapper. The new contract explicitly rejects presence, including those values.
- `backend/app/core/prompt_library.py:148` returns composed arrays without saving
  when `save_as is None`, otherwise calls the same combination writer with the
  composed arrays and save-intent metadata.
- `backend/app/schemas/prompt_library.py:94` defines revision/ETag inputs;
  `CombinationSaveIntent` extends `CombinationWriteRequest` with only `id`.
  Both therefore share positive/negative fragments, metadata and applicable
  `source_combination_id`, `document_context_token`, `literal_conversion_token`
  and `provenance_resolutions`. `ComposeResponse` returns both fragment arrays.
- Existing MCP save uses the combination PUT locator and forwards payload data
  with explicit concurrency arguments. Backend `api/prompt_library.py:181` and
  `core/prompt_library_writes.py:280` use that same write schema and writer.
  `assert_precondition` requires revision 0/no ETag for create, current revision
  and ETag for update; conflicts remain `revision_conflict` or `external_change`
  with their existing hints. These are not generation's `revision_request_conflict`.
- `PromptComposer.compose` resolves and returns fragments; saving re-resolves
  them under existing Backend behavior. Two calls do not promise a snapshot
  transaction or identical rendering if referenced resources change between
  calls. The clarified contract makes no cross-call atomicity claim and changes
  no Backend behavior. Existing API tests demonstrate optional save/readback;
  I inspected them without executing a library write.

The capability migration is now explicit and judgeable:

| Case | Required observable MCP result and boundary |
|---|---|
| Ordinary `prompt_compose` | Schema advertises composition inputs only; real wrapper request contains no `save_as`. |
| Legacy `save_as` with object, empty object/string or null | Presence is rejected before any Backend request; common envelope `ok=false`, `error.code=request_validation_failed`, hint to compose then `prompt_write(action=save)`. Removing a signature field or checking truthiness alone is insufficient. |
| Compose then `prompt_write(action=save, resource_type=combination, resource_id=...)` | Pass returned positive/negative fragment arrays, preserving refs, snapshots, weights/order and applicable context/provenance; use existing save metadata and explicit revision/ETag arguments. Rendered strings do not replace arrays. |
| Save concurrency conflict | Preserve existing Backend code/hint through the common envelope; no automatic overwrite/retry. Create and update keep their existing rules. |

D1 names the optional-capability migration, D2 binds risk to actual capability,
and D3 demands these registered MCP request/error assertions with dependencies
mocked below real wrappers. The read intent has no save route; saving remains a
mutate action. This closes the demonstrated ambiguity without inventing a new
API, tool or persistence system. No remaining blocking specification ambiguity
was demonstrated. Whether implementation meets these gates is still untested.

## Complete tool and acceptance reconciliation

The first 40-tool audit's source inputs are equal. I reused its 39 unaffected
rows and independently resolved the compose row below; this is a QA cross-check,
not Coding's future manifest. Each old name occurs once. Counts remain 15 kept,
eight renamed, 14 merged old entries into six destinations and three removed:
**29 provisional delivered names**, before any QA-agreed naming adjustment.
Each delivered destination below has one consistent risk; removed risks describe
old intent only. Retained-tool labels inferred from source remain proposals for
Coding to state and prove; metadata alone does not certify capability boundaries.

| Old name | Destination/disposition | Intent | Mode/action or capability | Risk |
|---|---|---|---|---|
| `mcp_ping` | `mcp_ping` (kept) | Backend connectivity | transitional | read |
| `civitai_source_info` | `civitai_source_info` (kept) | Civitai preview | unchanged | read |
| `civitai_generate_like` | removed (Backend frozen) | Civitai reproduce | MCP removal only | mutate |
| `civitai_resource_acquire` | `civitai_resource_acquire` (kept) | Civitai download | unchanged | mutate |
| `civitai_resource_status` | `civitai_resource_status` (kept) | Civitai acquisition status | unchanged | read |
| `generate_image` | `generate` (merged) | Generate image | template | mutate |
| `generate_image_custom_workflow` | `generate` (merged) | Generate image | custom_workflow | mutate |
| `generate_video_wan_keyframes` | removed (Backend frozen) | Wan video | MCP removal only | mutate |
| `generate_video_custom_workflow` | removed (Backend frozen) | Custom video | MCP removal only | mutate |
| `get_generation_status` | `job_status` (renamed) | Generation status | unchanged job ID | read |
| `cancel_job` | `cancel_job` (kept) | Generation cancel | generation queue | mutate |
| `list_available_resources` | `list_resources` (renamed) | Resource discovery | resources and forms | read |
| `deliver_generation_result_to_discord` | `deliver_to_discord` (renamed) | Deliver completed job | allowlisted alias; dedup/force_resend | mutate |
| `gallery_list` | `gallery_search` (renamed) | Gallery search | filters/pagination | read |
| `get_gallery_image` | `gallery_get` (merged) | Gallery retrieval | image ID branch | read |
| `get_gallery_artifact` | `gallery_get` (merged) | Gallery retrieval | canonical artifact ID branch | read |
| `gallery_rerun` | `gallery_rerun` (kept) | Replay image parameters | not a revision | mutate |
| `free_comfyui_memory` | `comfyui_admin` (merged) | ComfyUI administration | free_memory | admin |
| `comfyui_node_provision` | `comfyui_admin` (merged) | ComfyUI administration | install_node | admin |
| `comfyui_restart` | `comfyui_admin` (merged) | ComfyUI administration | restart | admin |
| `create_style_preset` | `style_preset_save` (merged) | Save style preset | from fields | mutate |
| `list_style_presets` | `style_preset_get` (merged) | Read style preset | no ID = list | read |
| `get_style_preset` | `style_preset_get` (merged) | Read style preset | ID = detail | read |
| `compose_style_preset` | `style_preset_compose` (renamed) | Compose preset | does not generate | read |
| `save_successful_workflow_as_style_preset` | `style_preset_save` (merged) | Save style preset | from successful job | mutate |
| `test_saved_style_preset_workflow` | `style_preset_test` (renamed) | Test saved graph | server-owned graph | mutate |
| `prompt_library_search` | `prompt_search` (renamed) | Search prompts | catalog/category/search | read |
| `prompt_library_save` | `prompt_write` (merged) | Write prompts | save | mutate |
| `prompt_library_compose` | `prompt_compose` (renamed) | Compose prompts | pure compose; all legacy save_as rejected before Backend; saving arrays/metadata migrates to prompt_write(save) | read |
| `prompt_library_archive` | `prompt_write` (merged) | Write prompts | archive | mutate |
| `prompt_library_restore` | `prompt_write` (merged) | Write prompts | restore | mutate |
| `caption_image` | `caption_image` (kept) | Caption image | unchanged | mutate |
| `lora_training_decision_preflight` | `lora_training_decision_preflight` (kept) | Training preflight | non-starting | read |
| `lora_train_start` | `lora_train_start` (kept) | Start training | unchanged | mutate |
| `lora_train_job_status` | `lora_train_job_status` (kept) | Training status | separate from generation status | read |
| `lora_train_logs` | `lora_train_logs` (kept) | Training logs | bounded lines | read |
| `lora_train_cancel` | `lora_train_cancel` (kept) | Cancel training | separate from generation cancel | mutate |
| `lora_dataset_list` | `lora_dataset_list` (kept) | List datasets | unchanged | read |
| `lora_dataset_inspect` | `lora_dataset_inspect` (kept) | Inspect dataset | unchanged | read |
| `lora_train_smoke_test` | `lora_train_smoke_test` (kept) | Training smoke generation | existing submit-or-return semantics | mutate |

The optional save capability of the single `prompt_library_compose` row migrates
to `prompt_write(save)` (`mutate`), while its pure composition maps to
`prompt_compose` (`read`). This is intentional capability accounting, not a
second old-name row or a 30th delivered tool. The separate actions remain within
the existing prompt-write intent.

| Item | Verdict | Required later delivery evidence |
|---|---|---|
| D1 — catalog/registration and all old capabilities | CLEAR | Catalog test plus exact 40-row manifest map including this optional migration. All nine LoRA/caption and three retained Civitai names remain separate, especially training status/cancel. Three MCP removals leave Backend implementations frozen. |
| D2 — truthful single risk | CLEAR | One catalog risk, stated in description and consistent with exposed capability; metadata and no-save/rejection boundary tests. `caption_image` is mutate, dataset reads read, ComfyUI actions admin, temporary ping read. |
| D3 — every merged mode/action through MCP | CLEAR | Real registered wrappers: generate template/custom_workflow; Gallery image/artifact selectors; prompt save/archive/restore; preset list/detail and save from fields/successful job; ComfyUI restart/free_memory/install_node. Add all clarified compose/no-write/replacement-save/conflict cases above. Retain existing resource-type/locator and validation checks. |
| D4 — all friction fixed/explained | CLEAR | F1-F8 section unchanged; per-row obligations and 23-unit/eight-incident boundary independently reconciled in the p1-01 round-2 report. F3 is the direct fix; F5/F8 require preservation; other later-task obligations are not dropped. |
| D5 — current/staged docs and full MCP suite | CLEAR | Executable current `mcp_ping → list_resources → generate → job_status` polling then `gallery_get`; label `health → list_resources → generate → wait_for_job → gallery_get` as staged. Full MCP suite, isolated root and `--timeout=60`, command/summary in manifest. |

Scope still requires `docs/mcp.md`, operating policy, architecture, style/workflow
READMEs, affected memory and team role prompts to use delivered names and the
common parse shape. Current `docs/mcp.md` still describes mixed shapes and older
repair status; rewriting it is delivery work. Keep historical evidence unchanged.
No new wait, health or worker-list tool is added now: p1-03 adds wait, p1-04
replaces temporary ping with health and adds list_workers.

Preservation remains material: omitted versus empty `loras`, `revision_context`
and canonical parent artifact IDs, Gallery metadata/supported locators and image/
artifact namespaces, existing artifact reads even when video submissions leave
MCP, rerun versus revision semantics, generation and LoRA status/cancel separation,
safe uncertain-admission recovery, prompt concurrency/restore constraints,
server-owned saved-preset replay, direct local ComfyUI targeting and Discord
allowlist/dedup behavior. No automatic timeout resubmission or failed-worker
fallback is introduced. Risk labels do not expand security boundaries.

## History, verification and handoff

Round 1 was [AID-155](/AID/issues/AID-155), source
`d1ffb8d8d9db12f728ed98704e966e76489faafb`, report commit
`b32ac4fcabf8c57e2370aa81bb06f6708863ff22`: p1-01 CLEAR / p1-02 AMBIGUITY
K2-1. Accounting remains one p1-02 kickoff ambiguity, clarification round 1,
this kickoff review round 2; no p1-01/02 implementation delivery, delivery
rejection or delivery review exists. Both `kickoff-review-round-1.md` mirrors
are byte-identical to that exact report commit and are left unchanged.
The separate p1-00a history stays one delivery rejection, correction round 1,
delivery review round 2.

I read the preserved owner requests, approved map, both actual task files,
clarification, revised shared context, original reports, original baseline
manifest/review and corrected repair manifest/acceptance/final and historical
reviews. Neither reviewed task has a `manifest.md`; this is kickoff only.
Guides and skills: AGENTS, project memory/INDEX, team/QA role/bindings,
reviewspec-core, reviewspec-review, paperclip-task-handoff, Paperclip,
Git/worktree and verification-before-completion.

Recipient-owned worktree:
`/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-156-kickoff-review`,
branch `aid-156-fixed-kickoff-round-2`, created at the full fixed SHA above.
Checks used fixed Git objects, AST/schema inspection, `git diff`, `git ls-tree`,
SHA-256 and the uploaded static audit:

```sh
python3 "$PAPERCLIP_RUN_SCRATCH_DIR/kickoff-round2-audit.py"   /Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-156-kickoff-review   "$PAPERCLIP_RUN_SCRATCH_DIR/round2-audit.json"
git diff --check
```

The static audit exited 0: both digests/counts match; 40 catalog/registration/
original-discovery names and dispositions, 29 provisional destinations, 23 units/
eight incidents and unchanged source/evidence inputs reconcile. All 20 original
baseline files remain equal to `3081952e0ba12a339ab7e60b8081ede61a131b7f`;
all 91 repair-folder files equal the first kickoff source, with corrected
manifest/raw flow and final review also equal their named immutable commits.
The changed specification paths are documentation only. Backend/MCP and the
other checked product trees equal the prior source. The only tool-map row
changes concern composition and saving; the F1-F8 section is byte-identical.

I downloaded all four official AID-155 artifacts. Both standalone reports and
the patch equal the exact Git bytes. The archive has 17 members including its
receipt, with all 16 indexed non-self files verified by size/hash; all nine
reference snapshots equal their named first-source Git objects. This identifies
the prior static audit being reused; it is not an old clearance substituted for
this combined-contract review. Fresh report hashes, full report commit, exact
patch, audit source/result and fixed reference snapshots accompany the AID-156
uploads. Outgoing document links, allowed changed paths, whitespace and package
bytes are checked separately before handoff.

Verification boundaries:

- Offline software suites: none run. Static specification review changes no
  software. Historical repair Backend `1900 passed / 124 Windows-only skips`
  and MCP `314 passed / 4 exported-fixture skips` remain historical evidence;
  they do not verify future envelope/consolidation code.
- Running service: no new product probe, restart, private configuration or
  canonical Backend venv access/change. No loaded-source claim is inferred
  from a documentation commit.
- Real generation: none. Accepted evidence remains one original/revision pair,
  with a cached deterministic original and persisted canonical lineage.
- Generated artifact retrieval: no new live image-byte read. Accepted proof is
  decoded bytes from both Gallery tools' unmodified returned host paths for a
  colocated Mac filesystem client only. Remote/relative-URL consumption remains
  unproved. Review-file upload readback is a separate integrity check.
- Errors/cancellation/recovery/duplicate submission/security: static contracts
  only; no new live behavior certification. Existing job IDs must be inspected
  before resubmission after timeout. No worker exposure, data cleanup or changes
  to shared main, active AID-151 runtime/private files or retained data occurred.

Both fixed specifications now have explicit CLEAR. Producer on
[AID-143](/AID/issues/AID-143) owns separate Coding and delivery-QA cards, with QA
natively waiting on Coding. Delivery QA must read both actual manifests at one
combined exact final commit and return independent PASS before combined merge/
push and p1-03 release. New candidate code requires a new exact-commit review.
This kickoff adds no registry coverage, software acceptance, release of p1-03,
aesthetic/demo approval or phase-close authority.
