# p1-02 — one MCP tool per intent

Corrected combined delivery with [p1-01](../p1-01-mcp-response-envelope/manifest.md), 2026-11-24.

Correction round 1 addresses F2-1 under the unchanged cleared p1-02 D2.
Production labels/behavior and original task contracts are unchanged. The first
candidate was p1-01 PASS / p1-02 FAIL; this candidate awaits independent review 2.

## Done when evidence

| Item | Check | Level | Result / evidence | Layer and real boundary |
|---|---|---|---|---|
| D1 — registration/catalog and complete old capabilities | test + manual | P1 | test_tool_catalog.py::test_intended_catalog_matches_fastmcp_registration, test_removed_tools_and_staged_tools_are_not_registered; exact 40-row map below; [parameter migration audit](../p1-01-mcp-response-envelope/evidence/capability-audit.json); [discovery](../p1-01-mcp-response-envelope/evidence/discovery.json) and [static audit](../p1-01-mcp-response-envelope/evidence/source-audit.json) | 40 baseline rows → 29 delivered names with unchanged retained LoRA/Civitai names; Backend implementations unchanged. Manual optional-capability review accompanies metadata tests. |
| D2 — one truthful risk per tool | test | P1 | test_catalog_risks_match_approved_intent_policy; test_discovered_risks_match_approved_intent_policy; existing envelope/compose schema/rejection and all 29 HTTP-transport cases | Independent approved 29-intent risk map checks exact catalog and real SDK discovery, including exactly one label. Exact false-admin-read fault fails both guards/full suite. Read compose exposes no save field and rejects all legacy presence before any Backend call. |
| D3 — every merged branch; compose/write concurrency | test | P1 | test_merged_modes_forward_exact_requests (14 cases); compose legacy-save cases (empty dict/string, null, populated); test_compose_then_write_preserves_fragments_metadata_provenance_and_conflict; test_generate_preserves_omitted_empty_ordered_loras_and_graph_defaults; test_gallery_keeps_namespaces_locators_metadata_and_lineage; saved replay, prompt locators, Discord and worker-timeout cases | Real registered wrappers, mode/action dispatch, adapters and HTTP client. Tests replace HTTP transport only and assert actual path/body/call counts; Backend fixture consumers also traverse registration. |
| D4 — complete p1-00 friction dispositions | manual | P2 | F1–F8 table below, preserving all 23 units/eight original incidents | Author reconciled shared kickoff context, no-repair baseline and accepted repair. No new live journey or reduced baseline count is claimed. |
| D5 — current/staged flow/docs and full MCP | test + manual | P1 | [Current and staged flows](../../mcp.md#common-flows), tool table/error contract, test_catalog_docs_list_active_tools; [corrected MCP receipt](correction-1-evidence/final-mcp.json), 460 passed / 2 unchanged optional export skips | Fresh full offline MCP with isolated root/timeout; author document review pending independent exact-commit QA. |

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

Original implementation evidence remains under [p1-01/evidence](../p1-01-mcp-response-envelope/evidence/). Fresh correction evidence is linked below.

## Correction delivery identity and review gate

- Coding correction: [AID-159](/AID/issues/AID-159); Producer: [AID-143](/AID/issues/AID-143).
  Branch `aid-159-risk-guard`, worktree
  `/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-159-risk-guard`.
- Exact repair base: rejected combined feature
  `b1082a855a66eedba6a4f11fbd4fcec0e9e867ab`. Original feature handoff base:
  `cee10138db8e6e944409701cdae6fb9cfe55c74f`.
  Only the published correction document was imported from
  `1d4fb0df9c6c78e38c217aefed6afb91b0576c9a`; main's old product was not imported.
- Cleared task/decision/clarification bytes remain exactly
  `496cee2f842dc9386d336afb237075bf952271ce`. Both independent kickoff reports
  remain at `9d79d203f65cf3802651a16559da13cbcc4ba14b`.
- **Combined candidate is the final commit containing both refreshed manifests
  on `aid-159-risk-guard`.** Resolve with `git rev-parse aid-159-risk-guard`.
  The external delivery receipt and AID-159 completion pin its one full final
  SHA for both tasks, plus the exact combined patch, repair delta, verified
  bundle and indexed source/evidence package. A commit cannot contain its own hash.
- [Independent QA AID-160](/AID/issues/AID-160) owns delivery review round 2,
  natively after this Coding card. It must pin that full SHA, reassess both
  original contracts and F2-1, preserve round-1 reports/evidence and own registry
  updates. Coding supplies evidence, not independent PASS. Producer alone
  accepts/publishes after actual PASS for both; new code requires new review.
- No merge/push, main integration, runtime replacement or later-task release.
  Active AID-151 runtime/private configuration, canonical component environments
  and all retained data were preserved. Test roots and timeout installation
  were confined to this run's scratch directory.

## Correction and verification

F2-1 is the automated guard's circular oracle, not an incorrect delivered label.
Two new tests in `mcp-server/tests/test_tool_catalog.py` use an explicit literal
`APPROVED_INTENT_RISKS` for all 29 intents, hand-stated from the cleared
[policy](../../decisions/mcp.md#tool-map), retained capabilities and staged ping:

- `test_catalog_risks_match_approved_intent_policy` checks exact names/labels,
  cardinality and exposed entries, without deriving expected risks from catalog.
- `test_discovered_risks_match_approved_intent_policy` calls real
  `mcp.list_tools()` and checks the exact 29 names and exactly one approved
  description label per tool against that independent expectation.

The existing envelope/risk consistency test and every existing test body remain
unchanged. Existing compose no-write/legacy-presence rejection, replacement-save
fragment/concurrency/conflict tests and all merged request/capability cases run
in the full suite. No wrapper, registration, description, label, Backend API,
product dependency or other behavior changed. No new task-spec deviation.

Fresh evidence is in
[correction-1-evidence](../p1-02-mcp-tool-consolidation/correction-1-evidence/README.md),
separate from immutable original AID-157 `evidence/` and AID-158 `qa-evidence/`.
Full argument arrays, allowlisted environments, UTC times, exits and logs are
retained for each command. The helpers are saved as `.py.txt`; all HTTP is
mocked below real registration/dispatch/adapters, including the restart probe.

| Check | Fresh outcome | Evidence under correction-1-evidence |
|---|---|---|
| Original catalog baseline | 12 passed, exit 0 | baseline-catalog.log/json |
| Before-fix admin-to-read fault | old catalog tests still 12 passed; registered restart advertises read and emits one mocked POST /manager/reboot | before-fix-mutant-catalog.log/json; before-fix-admin-to-read.patch; before-fix-restart-probe.json |
| Corrected guards, same one-field fault | **2 failed, exit 1**, specifically comfyui_admin read versus admin | mutant-policy-guards.log/json |
| Corrected full MCP, same fault | **2 failed, 458 passed, 2 skipped, exit 1** | mutant-full-mcp.log/json |
| Byte-for-byte restore | original/restored SHA-256 both `d57d6a93e3529ca31746e172a37c24574bf068e9d87e433a7e80a204383c9e70` | after-fix-mutation.json; restored-discovery-restart.json |
| Restored full MCP | **460 passed, 2 skipped in 1.95s**, exit 0 | final-mcp.log/json |
| Full Backend | **1900 passed, 124 skipped, 76 warnings in 41.58s**, exit 0 | fresh-backend.log/json |
| Cross-layer LoRA parity | **5 passed, 1 warning in 0.32s**, exit 0 | final-parity.log/json |
| Source/contracts/preservation | production and existing test bodies unchanged; prior official artifacts hash-verified | source-scope-audit.json; prior-official-artifacts.json |

The mutation changes only the production catalog's `comfyui_admin` risk from
admin to read; its dispatch/request implementation is untouched. Both trials
restore the original source in `finally` and record matching SHA-256. The same
registered restart still requests exactly one POST to `comfy.invalid/manager/reboot`
under mocked transport. The restored probe exposes admin. No live restart occurs.
Final full MCP is after restoration and uses fresh serialized Backend exports.

Reproduce from this worktree (exact resolved paths are in receipts):

```sh
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export TMPDIR="$PAPERCLIP_RUN_SCRATCH_DIR"
export PYTHONPATH="$PAPERCLIP_RUN_SCRATCH_DIR/timeout-plugin"
export MCP_TEST_PYTHON=/Users/tf00185088/Desktop/tim-project/ai-drawing/mcp-server/.venv/bin/python
export REVISION_HTTP_EXPORT="$PAPERCLIP_RUN_SCRATCH_DIR/revision-http.json"
export MULTI_LORA_HTTP_EXPORT="$PAPERCLIP_RUN_SCRATCH_DIR/multi-lora-http.json"
export LORA_LIFECYCLE_HTTP_FIXTURE="$PAPERCLIP_RUN_SCRATCH_DIR/backend/http-export.json"
AI_DRAWING_TEST_ROOT="$PAPERCLIP_RUN_SCRATCH_DIR/backend" \
 /Users/tf00185088/Desktop/tim-project/ai-drawing/backend/.venv/bin/python \
 -B -m pytest -c pytest.ini backend/tests -q --timeout=60 -ra
AI_DRAWING_TEST_ROOT="$PAPERCLIP_RUN_SCRATCH_DIR/final-mcp" \
 "$MCP_TEST_PYTHON" -B -m pytest -c pytest.ini mcp-server/tests -q --timeout=60 -ra
AI_DRAWING_TEST_ROOT="$PAPERCLIP_RUN_SCRATCH_DIR/backend" \
 /Users/tf00185088/Desktop/tim-project/ai-drawing/backend/.venv/bin/python \
 -B -m pytest -c pytest.ini backend/tests/test_lora_start_contract_parity.py -q --timeout=60 -ra
```

pytest-timeout 2.4.0 was installed with system Python `pip --no-deps --target`
in run scratch only; the MCP environment has no pip. Component dependencies
were not modified. All suites used isolated roots and per-test timeout 60.
Both baseline/repair standing registry guards and the three p1-01 guards in
QA's five-item registry at `1001586788d89d2c346619a5c1b0ffe1390897f8` are covered
by these fresh full suites. Coding did not edit the registry or certify new items.
No previous Backend test result was reused. Fresh revision, multi-LoRA and
uncertain-admission HTTP exports were consumed through real MCP registration.

All 124 Backend skips require Windows. The two unchanged MCP smoke-export
skips require optional HTTP/image-validation fixtures not produced here; they
are not the revision/uncertain-admission consumers, which executed. Existing
Pydantic/other Backend warnings remain, with the same 76-warning count as QA.
Frontend/build/native Windows checks were not run: those inputs are unchanged,
and this is macOS. Raw logs retain their original whitespace; source/docs
whitespace validation excludes only raw `.log` evidence.

## Preserved history and limits

Read actual [Coding AID-157](/AID/issues/AID-157) manifests and
[QA AID-158](/AID/issues/AID-158) reports, source and mutation evidence before
repair. Prior delivery `b1082a855a66eedba6a4f11fbd4fcec0e9e867ab` remains immutable;
its official manifests/archive/receipt and QA's corresponding reports/archive/
receipt were downloaded and hash-verified. Original reports/evidence/registry
remain QA-owned at `1001586788d89d2c346619a5c1b0ffe1390897f8`; none is overwritten
or merged here. Original Coding evidence remains byte-identical in this tree.

Accounting remains **one p1-02 delivery rejection / correction round 1 /
next delivery review round 2**, following p1-01 PASS and p1-02 FAIL F2-1 (P1,D2)
at the first candidate. No new PASS for either task is claimed by Coding.
One kickoff ambiguity K2-1 / clarification round 1 / kickoff round 2 CLEAR
for both and p1-00a's separate history retain their counts. Original baseline
is 23 intervention units/eight incidents; accepted live evidence remains one
cached-original/revision pair with decoded host paths for a colocated Mac client.

- **Offline tests:** fresh full Backend/MCP, parity, real registered mocked-HTTP
  request/discovery proof, mutation RED/restore/GREEN and scope/artifact audits.
- **Running product services:** no probe, deployment, restart or identity claim.
- **Real generation:** none; no training/download/worker dispatch.
- **Generated artifact retrieval:** no live Gallery bytes; fixture locators and
  downloaded review materials do not establish new generated-image retrieval.

Breaking client migration, later wait/health/worker tools, remote URL consumption,
live timeout/cancel/dedup recovery, aesthetics, three zero-intervention runs and
phase closure remain outside this correction. The existing implementation
choices and original red/green evidence remain inspectable at the prior delivery;
the only new implementation is the bounded test guard above. There are no
unresolved feature failures, widened scope or abandoned product approaches.
