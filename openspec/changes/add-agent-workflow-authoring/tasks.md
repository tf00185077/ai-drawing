## 1. ComfyUI node-schema grounding (capability: comfyui-node-schema)

- [x] 1.1 Add a backend ComfyUI client method to fetch `/object_info` with caching keyed to the instance, invalidated on ComfyUI restart / custom-node change
- [x] 1.2 Add backend endpoint(s) for node search (filter `/object_info` keys by query) and single-node schema (return one node's input names/types and output types)
- [x] 1.3 Add MCP tools `search_nodes(query)` and `get_node_schema(node_type)` in `mcp-server/mcp_server/tools/comfyui.py`, returning agent-friendly JSON; empty search → empty list, unknown node → structured not-found
- [x] 1.4 Tests: search returns matching names without full schemas; live custom node appears / absent node does not; unknown node type returns not-found; cache refresh after instance change

## 2. Template capability manifest + index (capability: workflow-template-catalog)

- [x] 2.1 Define the controlled vocabulary (modality enum, conditioning set, io set, model_family) and a registry of allowed tags; decide storage shape — **sidecar `workflows/<name>.meta.json`** (co-located with graph; index globs only the small sidecars)
- [x] 2.2 Author capability manifests for the existing templates in `backend/workflows/` (default, default_lora, anima, inpaint, controlnet_pose, txt2img_lora_pose, img2img_lora_pose)
- [x] 2.3 Add backend manifest loader + validation that rejects/flags tags outside the controlled vocabulary
- [x] 2.4 Add a lightweight capability-index read API (id + tags + description, no full workflow JSON) and an MCP tool to query it
- [x] 2.5 Tests: manifest exposes tags with description as metadata-only; out-of-vocabulary tag is rejected; index entries omit full graph JSON

## 3. Binary reuse matching (capability: workflow-template-catalog)

- [x] 3.1 Implement deterministic superset match (`template_tags ⊇ required_tags`) returning matched template id(s) or an explicit miss
- [x] 3.2 Expose matching via MCP so the agent gets match→template-name or miss→self-author guidance; ensure `modality` is a required member of the test
- [x] 3.3 Tests: covering template matches; missing required capability → miss; differing modality → miss despite other overlap

## 4. Custom-workflow validation-error forwarding (capability: custom-workflow-generation)

- [x] 4.1 Capture ComfyUI `/prompt` validation `node_errors` in the custom submission path (`backend/app/core/queue.py` / comfyui client) instead of swallowing them — failures now recorded (no head-of-queue retry), fixing the documented head-blocking bug
- [x] 4.2 Map errors to a structured `{node_id, class_type, reason}` payload and return it through `/api/generate/job/{id}` (failed status)
- [x] 4.3 Update `generate_image_custom_workflow` (JSON result + next) and `get_generation_status` to surface `ok=false` + structured node errors for agent self-correction; valid workflows unchanged
- [x] 4.4 Tests: rejected node input → structured node_errors; class_type fallback from workflow; valid workflow → no error payload; verified live against ComfyUI (bad sampler_name → node_errors)

## 5. Template backfill / self-extending catalog (capability: workflow-template-catalog)

- [ ] 5.1 Define the verified-success gate (ComfyUI produced an image AND recording succeeded) as the only promotion trigger
- [ ] 5.2 Implement shape extraction that strips one-off values (content prompt, fixed seed) leaving a parameterizable template
- [ ] 5.3 Implement capability-key dedup: existing key → no duplicate; new key → create entry tagged + filed under modality family
- [ ] 5.4 Implement version-on-change: superseding a broken same-key template creates a new version and marks the prior deprecated; never mutate a shared template in place; never auto-merge graphs
- [ ] 5.5 Decide and implement the backfill trigger surface (worker post-record vs explicit MCP tool — see design Open Questions)
- [ ] 5.6 Tests: failed/unrecorded generation not promoted; verified new key creates family-filed entry; existing key not duplicated; broken same-key superseded by new version with prior deprecated and unmodified; scaffold template not mutated; backfilled template does not hardcode content prompt or seed

## 6. Agent guidance + consolidation

- [ ] 6.1 Update MCP tool docstrings/guidance so the agent default flow is "query capability index → binary match → apply template-name on hit, else self-author (optionally scaffolding from a similar template) via custom"
- [ ] 6.2 Add an optional consolidation routine to retire deprecated entries (manual/periodic; cadence per design Open Questions)
- [ ] 6.3 Update `docs/PROGRESS.md` and run `openspec validate add-agent-workflow-authoring`; verify full match→build→backfill loop end to end against a live ComfyUI
