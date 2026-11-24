# p1-02 — one MCP tool per intent

Combined implementation delivery with [p1-01](../p1-01-mcp-response-envelope/manifest.md), 2026-11-24.

## Done when evidence

| Item | Check | Level | Result / evidence | Layer and real boundary |
|---|---|---|---|---|
| D1 — registration/catalog and complete old capabilities | test + manual | P1 | test_tool_catalog.py::test_intended_catalog_matches_fastmcp_registration, test_removed_tools_and_staged_tools_are_not_registered; exact 40-row map below; [parameter migration audit](../p1-01-mcp-response-envelope/evidence/capability-audit.json); [discovery](../p1-01-mcp-response-envelope/evidence/discovery.json) and [static audit](../p1-01-mcp-response-envelope/evidence/source-audit.json) | 40 baseline rows → 29 delivered names with unchanged retained LoRA/Civitai names; Backend implementations unchanged. Manual optional-capability review accompanies metadata tests. |
| D2 — one truthful risk per tool | test | P1 | test_envelope_schema_and_one_truthful_risk_per_tool; compose schema/rejection tests; all 29 HTTP-transport cases | Real SDK discovery includes exactly one risk in each description/catalog entry. Read compose exposes no save field and rejects all legacy presence before any Backend call. |
| D3 — every merged branch; compose/write concurrency | test | P1 | test_merged_modes_forward_exact_requests (14 cases); compose legacy-save cases (empty dict/string, null, populated); test_compose_then_write_preserves_fragments_metadata_provenance_and_conflict; test_generate_preserves_omitted_empty_ordered_loras_and_graph_defaults; test_gallery_keeps_namespaces_locators_metadata_and_lineage; saved replay, prompt locators, Discord and worker-timeout cases | Real registered wrappers, mode/action dispatch, adapters and HTTP client. Tests replace HTTP transport only and assert actual path/body/call counts; Backend fixture consumers also traverse registration. |
| D4 — complete p1-00 friction dispositions | manual | P2 | F1–F8 table below, preserving all 23 units/eight original incidents | Author reconciled shared kickoff context, no-repair baseline and accepted repair. No new live journey or reduced baseline count is claimed. |
| D5 — current/staged flow/docs and full MCP | test + manual | P1 | [Current and staged flows](../../mcp.md#common-flows), tool table/error contract, test_catalog_docs_list_active_tools; [final MCP log/receipt](../p1-01-mcp-response-envelope/evidence/final-mcp-server.json), 458 passed / 2 unchanged optional export skips | Fresh full offline MCP with isolated root/timeout; author document review pending independent exact-commit QA. |

## Old-to-new capability map

Exactly 40 baseline names occur once in the first column. “Retained” means the
same exposed name; removed entries have no delivered MCP risk. No new tool name
needs a deviation from the approved map. Every retained tool now uses the common
envelope; action-specific capabilities remain behind one truthful label.

| Old tool | Delivered intent / name | Risk | Mode/action and optional-capability disposition |
|---|---|---|---|
| `mcp_ping` | Retained | read | Backend connectivity only; temporary until p1-04, no ComfyUI/worker identity claim. |
| `civitai_source_info` | Retained | read | Existing source locator and read-only resource/parameter preview. |
| `civitai_generate_like` | Removed from MCP | none | Backend API/implementation remains frozen and unchanged; no delivered video/generate-like registration or alias. |
| `civitai_resource_acquire` | Retained | mutate | Existing source locator and model/LoRA acquisition; no new download behavior. |
| `civitai_resource_status` | Retained | read | Existing job/resource progress query and optional recent-resource listing. |
| `generate_image` | `generate` | mutate | mode=template; all prompt/character/style, resource, sampling, workflow-default/seed and revision_context controls; omitted versus empty loras retained. |
| `generate_image_custom_workflow` | `generate` | mutate | mode=custom_workflow; JSON-string graph, subject/pose/mask, optional injection fields and execution_target; omitted graph overrides unchanged. |
| `generate_video_wan_keyframes` | Removed from MCP | none | Backend API/implementation remains frozen and unchanged; no delivered video/generate-like registration or alias. |
| `generate_video_custom_workflow` | Removed from MCP | none | Backend API/implementation remains frozen and unchanged; no delivered video/generate-like registration or alias. |
| `get_generation_status` | `job_status` | read | Generation status/artifacts/revision diagnostics; distinct from LoRA status; caller polls existing job ID. |
| `cancel_job` | Retained | mutate | Generation queued-job cancellation only; distinct from LoRA cancellation. |
| `list_available_resources` | `list_resources` | read | Backend-host resource lists plus generation forms/capability metadata; no worker readiness inference. |
| `deliver_generation_result_to_discord` | `deliver_to_discord` | mutate | job_id, allowlisted destination_alias and force_resend retained; bot owns dedup/message IDs; no arbitrary file/text/channel capability. |
| `gallery_list` | `gallery_search` | read | Filters, dates, limit/offset retained; image namespace. |
| `get_gallery_image` | `gallery_get` | read | image_id selector; metadata, precise seed, image_url and configured-host local_path, revision context preserved. |
| `get_gallery_artifact` | `gallery_get` | read | artifact_id selector; canonical namespace, existing image/video artifact reads, URLs/host path, workflow and media metadata retained. |
| `gallery_rerun` | Retained | mutate | Replay recorded parameters with execution_target; does not become a revision. |
| `free_comfyui_memory` | `comfyui_admin` | admin | action=free_memory; unload_models/free_memory flags retained; configured local ComfyUI only. |
| `comfyui_node_provision` | `comfyui_admin` | admin | action=install_node; node_class_names, curated package resolution/install/status and needs_restart retained; never restarts automatically. |
| `comfyui_restart` | `comfyui_admin` | admin | action=restart; configured local ComfyUI Manager reboot; policy authority unchanged. |
| `create_style_preset` | `style_preset_save` | mutate | from_source=fields; id migrates to preset_id; name, all recipe/resources/profiles/defaults, overwrite and validation retained. |
| `list_style_presets` | `style_preset_get` | read | No preset_id lists lightweight summaries. |
| `get_style_preset` | `style_preset_get` | read | preset_id reads full recipe. |
| `compose_style_preset` | `style_preset_compose` | read | content_prompt, profile, overrides; read-only data.generation payload, no job submission. |
| `save_successful_workflow_as_style_preset` | `style_preset_save` | mutate | from_source=successful_job; source, preset_id, prompt_keywords, negative_prompt_keywords and profile; explicit-save intent and Backend-owned graph retained. |
| `test_saved_style_preset_workflow` | `style_preset_test` | mutate | preset_id/profile/execution_target only; saved graph replay unchanged, no prompt/graph overrides. |
| `prompt_library_search` | `prompt_search` | read | Catalog/category/query branches, filters, include_archived, threshold/limit and locator semantics retained. |
| `prompt_library_save` | `prompt_write` | mutate | action=save; entry/category/combination locators; payload metadata/fragments/context/provenance plus explicit revision/ETag; bilingual warnings preserved. |
| `prompt_library_compose` | `prompt_compose` | read | Pure composition → prompt_compose; any legacy save_as presence rejected before HTTP with replacement hint. Optional saving migrates to compose then prompt_write(action=save, resource_type=combination) carrying returned fragment arrays, metadata, revision/ETag and provenance/context. No cross-call transaction; no overwrite/retry on conflicts; direct Backend compose/save unchanged. |
| `prompt_library_archive` | `prompt_write` | mutate | action=archive; exact resource locator and explicit revision/ETag retained. |
| `prompt_library_restore` | `prompt_write` | mutate | action=restore; category/entry only, exact polarity/category locator and explicit revision/ETag; combination restore remains rejected. |
| `caption_image` | Retained | mutate | Existing LLM caption operation; mutate, not dataset read. |
| `lora_training_decision_preflight` | Retained | read | Existing recipe object/string hints, readable output_name, canonical preview and hashes; no start. |
| `lora_train_start` | Retained | mutate | Existing versioned recipe, required dataset/profile hashes and optional output-config hash; safe migration/validation and uncertain-admission job recovery retained. |
| `lora_train_job_status` | Retained | read | Separate training status, safe public projection and smoke reconciliation; never generation status. |
| `lora_train_logs` | Retained | read | Separate bounded training logs. |
| `lora_train_cancel` | Retained | mutate | Separate queued/running training cancellation; not generation cancellation. |
| `lora_dataset_list` | Retained | read | Existing read-only dataset summaries. |
| `lora_dataset_inspect` | Retained | read | Existing read-only folder/agent inspection and hashes. |
| `lora_train_smoke_test` | Retained | mutate | Existing submit-once-or-return behavior and independent execution_target; no failed-worker local fallback. |

The two generate modes, two Gallery selectors, three prompt write actions,
preset list/detail, two preset-save sources and three ComfyUI actions have
explicit registered-path request assertions. Renamed prompt search also has
catalog/category/query coverage. All LoRA status/cancel distinctions and all
retained Civitai names remain. There is no hidden legacy registration or new
wait/health/worker tool.

## Friction disposition

| Item | Original units | Delivery disposition / continuing owner |
|---|---:|---|
| F1 — test environment/timeout | 1 | No packaging change. Explicit component interpreters and scratch timeout plugin used; repeatable setup remains p1-05. |
| F2 — stdio/client bootstrap | 1 | Supported wrapper/interpreter/source/Backend/Gallery binding preserved. Formal stdio tested offline; automatic bootstrap/repeatable smoke driver remains p1-05. |
| F3 — mixed parsing | 1 | Fixed at registered MCP boundary: all 29 successes/failures share one parse contract; catalog and docs agree. |
| F4 — runtime identity | 6 | Existing controlled-launch evidence retained. No runtime attestation/restart here; general health/worker visibility remains p1-04. |
| F5 — missing live revision contract | 1 | New generate/Gallery interfaces preserve revision_context, canonical parent IDs and legacy/null diagnostics; fresh serialized Backend fixtures survive registration. Deployed persistence is rechecked by p1-05. |
| F6 — repeated polling | 11 | job_status/cancel_job retained, distinct from training status/cancel. Current docs poll existing ID; bounded wait remains p1-03. No automatic timeout resubmission. |
| F7 — coarse execution visibility | 1 | Status, artifacts and node/recording errors retained. No progress subsystem; wait/result p1-03, health visibility p1-04. |
| F8 — relative-URL byte retrieval | 1 | gallery_get preserves image/artifact namespaces and supported unmodified locators/media metadata. No new URL normalization or remote retrieval claim; truthful locator/result handling remains p1-03 and real decoding p1-05. |
| Total | 23 | Eight incidents. Resolution changes no original no-repair count or outcome. |

## Current documentation and preservation

Updated docs/mcp.md, docs/OPERATING-POLICY.md, docs/ARCHITECTURE.md,
style_presets/README.md, backend/workflows/README.md and the affected
style-preset memory topic. Role prompts contain no old tool/shape literals;
the shared team guide now binds all roles to the common envelope/current flow.
Historical task/decision/kickoff/baseline/repair documents remain unchanged.
Current executable flow uses temporary mcp_ping and job_status polling; the
later health/list_resources/generate/wait_for_job/gallery_get flow is labeled
staged. Internal next-step guidance names delivered intents and local ComfyUI
restart guidance follows the existing operating policy.

Evidence for both tasks is under [p1-01/evidence](../p1-01-mcp-response-envelope/evidence/).

## Delivery identity and boundaries

- Coding: [AID-157](/AID/issues/AID-157); Producer: [AID-143](/AID/issues/AID-143).
- Branch/worktree: `aid-157-mcp-intents`,
  `/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-157-mcp-intents`.
- Exact handoff base: `cee10138db8e6e944409701cdae6fb9cfe55c74f`.
  Cleared specification source: `496cee2f842dc9386d336afb237075bf952271ce`;
  actual independent round-2 kickoff reports at `9d79d203f65cf3802651a16559da13cbcc4ba14b`.
  Both task digests match the assignment; task/decision/kickoff bytes are unchanged.
- Candidate: **the one feature commit containing both manifests**. Resolve with
  `git rev-parse aid-157-mcp-intents`; the full final SHA is pinned in AID-157's
  completion and the external delivery receipt, since a commit cannot self-hash.
- Local delivery only. No merge/push or product deployment. Producer owns
  independent exact-commit delivery QA, acceptance and publication. Kickoff CLEAR
  and these test results are not implementation acceptance.
- Backend app/tests/APIs, Frontend, worker, Discord bot, graphs, resource data,
  old baseline/repair evidence and private runtime configuration are unchanged.
  Keep AID-151's active worktree and canonical Backend venv. Tests used the
  existing component interpreters without modifying installed dependencies;
  pytest-timeout 2.4.0 was installed only to run scratch.

## Verification

All commands ran from the feature worktree with isolated test roots below the
injected TMPDIR. Full command arrays, exact environment/times and exit codes are
in the linked JSON receipts. Common setup:

```sh
export PYTHONNOUSERSITE=1
export PYTHONPATH="$PAPERCLIP_RUN_SCRATCH_DIR/timeout-plugin"
export MCP_TEST_PYTHON=/Users/tf00185088/Desktop/tim-project/ai-drawing/mcp-server/.venv/bin/python
export REVISION_HTTP_EXPORT="$PAPERCLIP_RUN_SCRATCH_DIR/revision-http.json"
export MULTI_LORA_HTTP_EXPORT="$PAPERCLIP_RUN_SCRATCH_DIR/multi-lora-http.json"
AI_DRAWING_TEST_ROOT="$TMPDIR/aid-157-final-backend" \
 /Users/tf00185088/Desktop/tim-project/ai-drawing/backend/.venv/bin/python \
 -m pytest -c pytest.ini backend/tests -q --timeout=60 -ra
export LORA_LIFECYCLE_HTTP_FIXTURE="$TMPDIR/aid-157-final-backend/http-export.json"
AI_DRAWING_TEST_ROOT="$TMPDIR/aid-157-final-mcp-server" \
 /Users/tf00185088/Desktop/tim-project/ai-drawing/mcp-server/.venv/bin/python \
 -m pytest -c pytest.ini mcp-server/tests -q --timeout=60 -ra
AI_DRAWING_TEST_ROOT="$TMPDIR/aid-157-final-parity" \
 /Users/tf00185088/Desktop/tim-project/ai-drawing/backend/.venv/bin/python \
 -m pytest -c pytest.ini backend/tests/test_lora_start_contract_parity.py -q --timeout=60
```

Results: Backend **1900 passed, 124 skipped, 76 warnings in 42.15s**, exit 0;
final MCP **458 passed, 2 skipped in 1.78s**, exit 0 (exact timing in receipt/log);
final Backend/MCP LoRA schema parity **5 passed, 1 warning in 0.29s**, exit 0.
All Backend skips require Windows. The two unchanged MCP skips require optional
smoke HTTP/image-validation exports whose producing harness is not part of this
checkout. No skip was added or expanded. Revision and uncertain-admission
export consumers did execute, now through the real registered MCP wrappers in
the separate MCP interpreter. No Backend package was imported into MCP tests.
The full Backend and MCP runs also satisfy both standing guards in REGISTRY.md;
Coding does not edit QA's registry or claim new certified coverage.

Raw pytest logs retain their original trailing whitespace; candidate whitespace
checks exclude only those evidence logs. Source/docs whitespace checks pass.

The clean baseline was **314 passed, 4 skipped in 1.03s**. Tests tied to removed
names/shapes were migrated, retaining their feature assertions. Two existing
export skips were resolved by supplying fresh Backend fixtures. No feature test
was deleted. The removed Civitai registration schema check became an absence
check, while its private adapter's existing feature tests remain. Prior repair
suite numbers are historical context only, not evidence for this surface.
The Backend full-suite result precedes later MCP-only validation/guidance/test
edits: its Backend code/test/dependency inputs remain identical, and final
cross-layer parity was rerun. Frontend/worker/launcher/build/Windows suites were
not run because their code/dependencies were unchanged.

Five deliberate production mutations failed their intended registered-path
tests: flat success shape (29 failures), lost Backend code (4), missing legacy
save replacement hint (4), accidental compose save payload (1), wrong custom
mode dispatch (1). Each file was restored byte-for-byte in a finally block.
The initial envelope tests and unknown-LoRA-field check also failed before their
respective fixes. Saved mutation commands/logs identify these checks; no mutant
is delivered. Final full MCP results apply to the restored final source.

Verification layers are distinct:

- **Offline software:** fresh full suites, registered HTTP-transport cases,
  formal stdio success/validation with a test-only HTTP server, Backend-generated
  serialized fixtures, mutation checks and static catalog/spec/scope audit.
- **Running product service:** no intentional product preflight/deployment or
  restart. The preexisting ping unit in baseline/intermediate suites could
  attempt the default Backend /health; it is now mocked and the formal protocol
  test uses its own test server. No runtime identity/readiness claim follows.
- **Real generation:** none. No GPU, training, download or worker dispatch.
- **Generated artifact retrieval:** none from the live Gallery. Synthetic
  offline fixtures check locators/metadata; accepted historical colocated Mac
  PNG decoding remains separate and does not establish remote URL consumption.

Known limits: this is a breaking MCP change, awaiting independent QA. Existing
smoke-export skips and Windows-only skips remain disclosed. No timeout retry,
failed-worker fallback, later wait/health/worker tool, Backend API change,
cross-call prompt transaction, aesthetic verdict or phase-close claim is added.
The original no-repair baseline remains **23 units/eight incidents**; accepted
repair remains one cached-original/revision pair for a colocated Mac client.

## Implementation choices and prior failures

Preexisting failing tests: none in the baseline. Intermediate expected failures
covered old result shapes and discovery names; one real SDK issue surfaced when
an optional workflow string was pre-parsed into a dict. The delivered workflow
field is a string with an empty default, preserving the original JSON-string
transport; custom mode requires a nonempty value. This avoids changing the
Backend or accepting a new graph format. A central catalog registration pass
initially exposed a circular import for tests importing an adapter first;
client construction was moved to client.py, eliminating adapter imports of the
server. Both cases have registered-path coverage in the final suite.

Routine implementation choices: central registration applies one envelope while
reusing private adapters; no large business-logic replacement. Old Python
adapter names remain internally for reuse/tests but are absent from MCP
discovery. Single risk labels and canonical tool names match the approved map.
style_preset_save uses the Python-safe selector `from_source=fields|successful_job`;
new dispatchers reject incompatible mode inputs rather than silently dropping
caller intent. Prompt archive/restore retain Backend concurrency enforcement,
including explicit revision 0; only omission is rejected before access. Legacy
LoRA migration errors retain precedence over generic unknown-field validation.

Intentional test changes are limited to discovered names, common generic error
codes, moved envelope context and updated next-step text; LoRA safe projection,
known revision-parent allowlist/redaction and existing forwarding constraints
remain checked. Unknown unstructured preset HTTP errors now follow the common
backend_http_error contract (including HTTP 409), while structured Backend codes,
hints and details remain preserved. There are no unresolved scope deviations.
A fresh review will be performed on the existing separate QA card; no author
self-review or kickoff verdict is represented as independent delivery PASS.
