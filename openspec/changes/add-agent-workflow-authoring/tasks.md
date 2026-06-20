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

- [x] 5.1 Define the verified-success gate (ComfyUI produced an image AND recording succeeded) as the only promotion trigger — backend gates on a DB `GeneratedImage` row for the `job_id` with a non-null `workflow_json` (cross-process/restart safe; relies on persist-full-workflow-for-rerun + harden-queue-completion)
- [x] 5.2 Implement shape extraction that strips one-off values (content prompt, fixed seed) leaving a parameterizable template — `strip_workflow_to_shape` reuses `apply_params(seed=0, prompt="", negative_prompt="")`
- [x] 5.3 Implement capability-key dedup: existing key → no duplicate (reused); new key → create entry tagged + filed under modality family (id `gen_<modality>_<family>[_<cond>][_<io>]`)
- [x] 5.4 Implement version-on-change: broken same-key template → new version + prior marked `deprecated` (meta-only, graph untouched); deprecated excluded from reuse matching; never mutate a shared graph; never auto-merge
- [x] 5.5 Backfill trigger = explicit MCP tool `save_workflow_template` (+ `POST /api/workflow-catalog/backfill`), not the worker — agent supplies accurate tags, backend enforces the DB success gate
- [x] 5.6 Tests: unknown/legacy job not promoted (404/409); verified new key creates family-filed entry; existing key not duplicated; broken same-key superseded by new version with prior deprecated and unmodified; deprecated not matched; shape strips prompt/seed

## 6. Agent guidance + consolidation

- [x] 6.1 Update MCP tool docstrings/guidance + mcp-server/README.md so the agent default flow is "capability index/match → apply template-name on hit, else self-author (search_nodes/get_node_schema, scaffold from a similar template) via custom → save_workflow_template on success"; custom success `next` now points to backfill
- [x] 6.2 Add a consolidation routine to retire deprecated entries — `consolidate_templates` core + `POST /api/workflow-catalog/consolidate` + MCP `consolidate_workflow_templates` (manual/on-demand)
- [x] 6.3 Update `docs/PROGRESS.md` and run `openspec validate`; live-smoked catalog index / backfill gate (404) / consolidate endpoints. NOTE: the full generate→backfill leg could not be observed live on this machine (ComfyUI backlog/errors); covered by unit tests incl. the DB gate
