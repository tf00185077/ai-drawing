# Decisions · mcp

## Settled
- Mac baseline/smoke pair: `Illustrious-XL-v2.0.safetensors` + `default`, no LoRA, explicit local target · why: listed by Backend and Mac ComfyUI, matching checkpoint-loader family and no new resource dependency · Producer-selected under the owner's delegated routine-choice instruction; runtime compatibility still checked by p1-00 · [request](../requests/2026-11-24-proceed-within-project-boundaries.md)
- Every MCP tool returns one envelope: `{ok, data}` on success, `{ok: false, error: {code, message, hint}}` on failure · why: agents learn one shape · owner-confirmed
- Tools are consolidated to one tool per intent, each with exactly one risk label · why: a smaller surface is easier for agents to choose from · owner-confirmed · [tool map](#tool-map)
- Civitai and LoRA tools are not renamed or merged in Phase 1 (envelope only); Phase 2 and Phase 5 redesign them · why: avoid doing the work twice · owner-confirmed
- `generate` has only the `template` and `custom_workflow` modes; Wan keyframe video, custom video and Civitai generate-like are removed from MCP (Backend code frozen) · why: fewer, clearer parameters; video returns as the Phase 4 image-to-video tool · owner-confirmed
- `wait_for_job` caps its timeout below the MCP client's tool-call limit and returns `timeout` for the agent to call again · why: the tool must answer before the client gives up · owner-confirmed
- Phase 1 starts with a friction run on today's tools ([p1-00](../tasks/p1-00-mcp-friction-run-mac/task.md)); its count of manual fixes is the baseline p1-05 must bring to zero · why: generation already works; the problem is the manual fixes around it · owner-confirmed
- p1-01 and p1-02 merge to `main` together · why: one breaking change for clients instead of two · owner-confirmed
- End-to-end MCP verification runs on the Mac ComfyUI first, then extends to the Windows worker · owner-confirmed
- Phase 1 is implemented by the Paperclip team from `docs/tasks/p1-*`; the earlier planning-only session restriction is superseded for this round by the [follow-through instruction](../requests/2026-11-24-proceed-within-project-boundaries.md) · owner-confirmed

## Log (newest first)

### 2026-11-24 · Keep prompt composition read-only; save through the write intent
- Decision: `prompt_compose` accepts composition inputs only and rejects the legacy MCP `save_as` argument with the common validation-error envelope and a hint to use `prompt_write(action=save)`. Saving composed positive/negative fragment arrays, metadata and existing concurrency/provenance fields goes through that `mutate` intent. Backend APIs remain unchanged.
- Why: the existing MCP compose wrapper forwards `save_as` to a persistent writer. Carrying that option into a tool labeled `read` would contradict the approved read/write intent map; silently ignoring it would conceal an unsaved request.
- Supersedes: the unresolved optional-capability disposition in the original p1-02 map, not its approved risk labels. The single compose-and-save MCP convenience becomes an explicit compose then save sequence, with no cross-call atomicity guarantee.
- Provenance: Producer adopts [QA's bounded recommendation](/AID/issues/AID-155#comment-7ef7f3c8-631a-4a9b-b532-fcb12ef6b8ec) under the [delegated routine-choice authority](../requests/2026-11-24-proceed-within-project-boundaries.md), after checking the wrapper, provider, schemas and existing API tests. No new phase, Backend behavior or owner-boundary decision is introduced.
- Link: [contract](#prompt-composition-and-saving), [clarification 1](../tasks/p1-02-mcp-tool-consolidation/kickoff-clarification-1.md). Fresh independent kickoff must clear the clarified specification before Coding.

### 2026-11-24 · Apply delegated choices and reconcile Phase 1 specifications
- Decision: use the installed Illustrious/default pair for p1-00 and p1-05; preserve all LoRA names, including job status/cancel, as the existing exclusion says; regroup p1-02/p1-03 checks to at most five without dropping requirements; state training outputs and unknown timeout limits honestly.
- Why: these are technical consistency and baseline choices inside the existing Phase 1, with no change to project boundaries. The tool map had contradicted its own LoRA exclusion.
- Supersedes: the open checkpoint/template question and the map's two LoRA rename entries. Existing owner-confirmed exclusion and phase order remain in force.
- Provenance: Producer choice under [owner-confirmed delegated authority](../requests/2026-11-24-proceed-within-project-boundaries.md); resource listings and graph metadata artifact-verified during planning. This is not individual owner model selection or aesthetic approval.
- Link: [plan](../tasks/p1-planning-2026-11-24/plan.md), [p1-00](../tasks/p1-00-mcp-friction-run-mac/task.md), [p1-02](../tasks/p1-02-mcp-tool-consolidation/task.md), [p1-03](../tasks/p1-03-mcp-wait-and-result/task.md)

### 2026-11-24 · Phase 1 re-scoped after review
- Decision: add p1-00 friction run (Mac suite moves there from p1-05); leave Civitai and LoRA tools unmerged; `generate` keeps two modes; video and Civitai generate-like leave MCP; one risk label per tool (`caption_image` stays its own `mutate` tool); `wait_for_job` timeout capped below the client limit; p1-01 and p1-02 ship together.
- Why: generation through MCP already works; the problem is the manual fixes a run needs, and Phase 2 and Phase 5 will redesign Civitai and LoRA tools anyway.
- Supersedes: the 2026-11-23 tool map (about 20 tools including Civitai and LoRA merges and six `generate` modes).
- Provenance: owner-confirmed@"你提到的都改" · @"我確信現在工具是可以跑出圖片的…當時跑過要一直東修西修步驟"
- Link: [ROADMAP Phase 1](../roadmap/ROADMAP.md#phase-1--mcp-that-agents-use-smoothly-next)

### 2026-11-23 · Phase 1 MCP direction
- Decision: uniform envelope for all tools; consolidate to ~20 intent tools; Mac-first end-to-end smoke; team implements.
- Why: Phase 1 exit needs an agent to go from nothing to a retrieved, revised image without help.
- Supersedes: the mixed `plain_text` / `json_string` / `dict` response categories.
- Provenance: owner-confirmed@"全部統一" · "精簡合併" · "mac優先，之後才擴充到worker的windows" · "這個session都只定義文件"
- Link: [ROADMAP Phase 1](../roadmap/ROADMAP.md#phase-1--mcp-that-agents-use-smoothly-next)

## Tool map

Status: target for [p1-02](../tasks/p1-02-mcp-tool-consolidation/task.md); the coding agent may adjust names with QA agreement, but each intent keeps one tool and one risk label.

Delivery is staged in the existing order: p1-01/02 retain `mcp_ping` temporarily
(common envelope, `read`), p1-03 adds `wait_for_job`, and p1-04 replaces the ping
with `health` and adds `list_workers`. Documentation must distinguish the
executable tool list at each delivery from the final Phase 1 flow.

| New tool | Replaces | Risk |
|---|---|---|
| `health` | `mcp_ping` (adds ComfyUI and worker reachability, p1-04) | read |
| `list_workers` | new (p1-04) | read |
| `list_resources` | `list_available_resources` | read |
| `generate` (`mode`: `template`, `custom_workflow`) | `generate_image`, `generate_image_custom_workflow` | mutate |
| `job_status` | `get_generation_status` | read |
| `wait_for_job` | new (p1-03) | read |
| `cancel_job` | `cancel_job` (generation) | mutate |
| `gallery_search` | `gallery_list` | read |
| `gallery_get` | `get_gallery_image`, `get_gallery_artifact` | read |
| `gallery_rerun` | `gallery_rerun` | mutate |
| `prompt_search` | `prompt_library_search` | read |
| `prompt_compose` | Pure composition from `prompt_library_compose`; legacy `save_as` rejected (see below) | read |
| `prompt_write` (`action`: `save`, `archive`, `restore`) | `prompt_library_save`, `prompt_library_archive`, `prompt_library_restore`; saving composed fragments also uses `save` | mutate |
| `style_preset_get` (no id = list) | `list_style_presets`, `get_style_preset` | read |
| `style_preset_compose` | `compose_style_preset` | read |
| `style_preset_save` (`from`: fields or successful job) | `create_style_preset`, `save_successful_workflow_as_style_preset` | mutate |
| `style_preset_test` | `test_saved_style_preset_workflow` | mutate |
| `comfyui_admin` (`action`: `restart`, `free_memory`, `install_node`) | `comfyui_restart`, `free_comfyui_memory`, `comfyui_node_provision` | admin |
| `deliver_to_discord` | `deliver_generation_result_to_discord` | mutate |

**Kept as they are in Phase 1** (envelope only; redesigned later): Civitai — `civitai_source_info`, `civitai_resource_acquire`, `civitai_resource_status` (Phase 2); LoRA — `lora_dataset_list`, `lora_dataset_inspect`, `caption_image`, `lora_training_decision_preflight`, `lora_train_start`, `lora_train_job_status`, `lora_train_logs`, `lora_train_cancel`, `lora_train_smoke_test` (Phase 5). Their risk labels follow the one-label rule (`caption_image` is `mutate`, the dataset reads are `read`).

**Removed from MCP** (Backend code frozen): `generate_video_wan_keyframes`, `generate_video_custom_workflow`, `civitai_generate_like`.

## Prompt composition and saving

`prompt_compose` is a read intent. It takes the existing `combination_id`,
`positive` and `negative` composition inputs and sends no `save_as` to the
Backend. The legacy argument is absent from the advertised MCP schema. An MCP
call containing `save_as`, including an empty or null value, must fail before
any Backend request with `error.code=request_validation_failed` in the common
envelope and a hint to compose then use `prompt_write(action=save)`. Do not
silently ignore that argument or route it to a writer.

To save, pass the composed response's **positive and negative fragment arrays**
to `prompt_write(action=save, resource_type=combination, resource_id=...)`, with
the existing save metadata and revision/ETag fields. Preserve references,
snapshots, weights, order and any applicable source/provenance/context fields;
rendered prompt strings are not substitutes for the arrays. The write intent
uses the existing combination-save API. Creation and update retain the existing
concurrency rules and error codes; a conflict must not trigger an automatic
overwrite or retry. This is two MCP calls, with no atomic transaction across
them. The Backend's direct compose-with-save API remains available unchanged.

The p1-02 mapping must name this optional-capability migration as well as all
40 old tool names. Registered MCP tests must prove ordinary composition sends
no save intent, a legacy `save_as` call is rejected before Backend access, and
the replacement save path carries returned fragments plus concurrency fields
and preserves the existing conflict result. A correct label alone is not this
proof.

## Open questions
- None for resource selection: Producer adopted `Illustrious-XL-v2.0.safetensors` + `default`, no LoRA, local target under [delegated routine-choice authority](../requests/2026-11-24-proceed-within-project-boundaries.md); p1-00 verifies runtime compatibility, p1-05 reuses the pair.
- The tool-call timeout of the MCP client the Paperclip agents use — found in [p1-03](../tasks/p1-03-mcp-wait-and-result/task.md).
