# MCP server

The stdio MCP server gives agents 29 tools with one response envelope and one
risk label per intent. It calls the existing Backend APIs; direct ComfyUI admin
operations and Discord delivery use their configured service endpoints.

This is the combined p1-01/02 breaking change. Reload client tool discovery and
migrate old calls using the [complete capability map](tasks/p1-02-mcp-tool-consolidation/manifest.md#old-to-new-capability-map).
The catalog in `mcp-server/mcp_server/tool_catalog.py` drives registration.

Accepted [p1-00a evidence](tasks/p1-00a-mac-runtime-and-retrieval/acceptance.md)
proves one original/revision pair and decoded bytes through unmodified host paths
for a colocated Mac client; its deterministic original used cache. The original
baseline remains 23 intervention units/eight incidents. This MCP software
change is verified offline and does not redeploy that runtime, prove remote URL
consumption, meet the three-run exit, or imply aesthetic/phase acceptance.

## Install

Python 3.10+.

```bash
cd mcp-server
uv sync                      # or: python -m pip install -e .
```

The launcher does not install or start MCP.

## Connect a client

Use the wrapper scripts; they `cd` into `mcp-server` and run `uv run ai-drawing-mcp`. `uv` must be on the client process's `PATH`.

```json
{
  "mcpServers": {
    "ai-drawing": {
      "command": "/absolute/path/to/ai-drawing/scripts/run-mcp-server.sh",
      "env": {
        "MCP_BACKEND_API_URL": "http://127.0.0.1:8001",
        "MCP_COMFYUI_API_URL": "http://127.0.0.1:8188",
        "MCP_GALLERY_DIR": "/absolute/path/to/ai-drawing/data/gallery"
      }
    }
  }
}
```

On Windows use `scripts\\run-mcp-server.bat`. Reload the client after changes.

## Configuration

Read from the process environment only (not `.env`), in `mcp_server/config.py`.

| Variable | Default | Purpose |
|---|---|---|
| `MCP_BACKEND_API_URL` | `http://127.0.0.1:8001` | Backend (use `8000` when running it without Docker) |
| `MCP_COMFYUI_API_URL` | `http://127.0.0.1:8188` | Direct ComfyUI operations |
| `MCP_GALLERY_DIR` | developer-specific; always set it | Host path of the Gallery |
| `MCP_DISCORD_OPERATOR_URL` | `http://127.0.0.1:8765` | Discord bot operator endpoint |
| `MCP_DISCORD_OPERATOR_TOKEN` | unset | Shared secret for the bot endpoint |

## Response envelope

Every registered call returns a JSON object in MCP `structuredContent` and the
same JSON in a text content block. Read it once; no inner `result` string or
per-tool parsing is required:

```json
{"ok": true, "data": {"job_id": "...", "status": "queued"}}
```

```json
{"ok": false, "error": {"code": "request_validation_failed", "message": "MCP tool argument validation failed", "hint": "Correct the listed arguments and retry.", "details": {"validation_errors": []}}}
```

Success fields, submitted parameters and next-step guidance are under `data`.
Failures have `error.code`, `message`, `hint` and optional `details`. Prior
failure context (job ID, status, node/recording/revision errors, classification
and phase) is preserved in `error.details`. Specialized safe LoRA projection and
uncertain-admission recovery remain in force; its canonical job ID is also kept
at `error.job_id`. MCP validation errors redact input values and run before
any tool body. Unsupported fields fail validation rather than being ignored.

## Tools

Each description starts with exactly one `Risk: read`, `Risk: mutate` or
`Risk: admin`. Risk describes capability; authority comes from the
[operating policy](OPERATING-POLICY.md). Client schemas define all arguments.

<!-- MCP-CATALOG:START -->
| Tool | Risk | Intent / selectors |
|---|---|---|
| `mcp_ping` | read | Backend /health only; temporary until p1-04 |
| `civitai_source_info` | read | inspect source image metadata |
| `civitai_resource_acquire` | mutate | acquire model/LoRA |
| `civitai_resource_status` | read | read acquisition status |
| `generate` | mutate | mode=template or custom_workflow; image submission |
| `job_status` | read | generation job status; no wait |
| `cancel_job` | mutate | cancel a queued generation, distinct from LoRA cancel |
| `list_resources` | read | Backend-host models/workflows and generation forms |
| `deliver_to_discord` | mutate | completed job, destination alias, optional force_resend; bot allowlist/dedup |
| `gallery_search` | read | filter/paginate images |
| `gallery_get` | read | exactly one image_id or artifact_id; includes existing video artifacts |
| `gallery_rerun` | mutate | replay recorded image parameters; no revision lineage |
| `comfyui_admin` | admin | action=restart, free_memory or install_node; configured local ComfyUI |
| `style_preset_save` | mutate | from_source=fields or successful_job |
| `style_preset_get` | read | no preset_id lists; preset_id reads full recipe |
| `style_preset_compose` | read | compose generation fields without submission |
| `style_preset_test` | mutate | submit saved Backend-owned graph verbatim |
| `prompt_search` | read | catalog, category or query |
| `prompt_write` | mutate | action=save, archive or restore |
| `prompt_compose` | read | pure composition; rejects every legacy save_as |
| `caption_image` | mutate | caption via configured LLM |
| `lora_training_decision_preflight` | read | inspect training readiness; does not start training |
| `lora_train_start` | mutate | start with canonical recipe and approval hashes |
| `lora_train_job_status` | read | read training status; separate generation namespace |
| `lora_train_logs` | read | bounded training logs |
| `lora_train_cancel` | mutate | cancel training; separate generation namespace |
| `lora_dataset_list` | read | list datasets |
| `lora_dataset_inspect` | read | inspect a dataset |
| `lora_train_smoke_test` | mutate | submit once or return existing smoke generation/result |
<!-- MCP-CATALOG:END -->

The two old video submission tools and Civitai generate-like are absent from
MCP. Their Backend APIs remain unchanged and frozen. Civitai's three retained
names and all nine LoRA/caption names remain separate until their later phases.
There is no MCP `health`, `list_workers` or `wait_for_job` in this delivery.

## Common flows

The executable current flow is **mcp_ping → list_resources → generate →
job_status (poll the same ID) → gallery_get**. Example tool arguments:

```json
{"tool": "mcp_ping", "arguments": {}}
{"tool": "list_resources", "arguments": {}}
{"tool": "generate", "arguments": {"mode": "template", "prompt": "a red ceramic cup", "checkpoint": "Illustrious-XL-v2.0.safetensors", "template": "default", "execution_target": "local", "loras": []}}
{"tool": "job_status", "arguments": {"job_id": "<data.job_id from generate>"}}
{"tool": "gallery_get", "arguments": {"image_id": 4448}}
{"tool": "gallery_get", "arguments": {"artifact_id": 3863}}
```

Use the IDs returned by your job; the final two numbers illustrate the different
namespaces. Repeat job_status on queued/running results. A failed job is an
error envelope with status/node/recording/revision details. A timeout does not
prove failure: inspect the existing job ID before any resubmission. No automatic
resubmission or failed-worker local fallback occurs. cancel_job remains for
queued generation; LoRA status and cancel use their own named tools.

The staged final Phase 1 flow is **health → list_resources → generate →
wait_for_job → gallery_get**. p1-03 adds bounded wait; p1-04 replaces temporary
ping and adds worker discovery. Ping currently checks only Backend connectivity,
not ComfyUI, workers or loaded source identity.

**Retrieve:** gallery_get(image_id=...) constructs local_path from
MCP_GALLERY_DIR and returns full image metadata, including exact integer seeds
and revision context. gallery_get(artifact_id=...) preserves Backend local_path,
URLs, workflow metadata and video artifact reads. Consume an unmodified absolute
local_path only where the client can access that host filesystem, then decode
bytes to verify retrieval. This file operation is separate from MCP metadata.
URLs may be relative /gallery routes. No remote/relative-URL consumption proof
is claimed. Set MCP_GALLERY_DIR to the Backend's actual host Gallery root.

**Revise:** submit generate(mode=template) with revision_context containing the
same request_ref, a new brief_revision, and canonical parent_artifact_id (never
an image ID), plus feedback_ref/feedback_summary if needed. Feedback annotates;
it does not rewrite prompts or authorize execution. gallery_rerun replays old
parameters and creates no revision lineage. Legacy/null context stays truthful.

**Generate modes:** template retains workflow-default/seed controls and ordinary
revision_context. custom_workflow requires a ComfyUI API graph JSON **string**,
starting from backend/workflows/*.json or a recorded successful graph. It keeps
image/image_pose/mask inputs relative to Gallery and all prior injection fields.
Omitted overrides leave graph defaults unchanged. Omitted loras preserves the
loaders; an explicit ordered list, including [], replaces the active set. Never
truncate a list. Mode-specific unsupported fields fail before Backend access.
Where accepted, execution_target=local or worker is forwarded unchanged.

**Prompt compose then save:** prompt_search → prompt_compose →
generate(mode=template) with data.generation. prompt_compose advertises only
combination_id, positive and negative; it sends no save intent. Any save_as
presence, including null/empty, fails with request_validation_failed before
Backend access and a hint to use prompt_write(action=save). To save a composed
combination, pass **data.positive and data.negative fragment arrays** in payload,
resource_type=combination, resource_id and the existing metadata plus applicable
source_combination_id, document_context_token, literal_conversion_token and
provenance_resolutions. Preserve references, snapshots, weights and order;
rendered strings are not substitutes. Supply expected_revision=0 for creation,
or current revision and expected_etag for update. Conflicts retain Backend
codes/hints without overwrite or retry. These are two calls, without a cross-call
transaction or snapshot guarantee. Backend direct compose-with-save is unchanged.
Archive/restore require explicit revision and ETag. Restore supports category
and entry with their required polarity/category locator; combinations cannot
be restored.

**Style presets:** style_preset_get() → style_preset_get(preset_id=...) →
style_preset_compose → generate. Composition builds from recipe/template and
submits nothing. style_preset_save(from_source=fields) retains recipe creation,
optional profiles/resources/defaults and explicit overwrite. To capture a
successful graph on an explicit save request, use from_source=successful_job,
preset_id, source, prompt_keywords, optional negative_prompt_keywords/profile.
Backend owns the graph. style_preset_test sends only preset/profile and execution
target, replaying that saved graph verbatim, without prompt/graph overrides.
An omitted profile selects __base__.api.json, not a profile named default.

**Resources/admin/delivery:** Civitai source info and acquisition/status remain;
submit image parameters through generate. list_resources describes Backend-host
files, never worker readiness. comfyui_admin always uses MCP_COMFYUI_API_URL;
install_node resolves curated Manager packages and never restarts automatically.
Restart may interrupt work; ping afterwards still proves only Backend availability.
deliver_to_discord accepts job_id, allowlisted destination_alias and optional
force_resend. The bot enforces allowlist and dedup; it cannot send arbitrary
files, messages or channel IDs through this tool.

## Error codes and recovery

| Code | Meaning / hint |
|---|---|
| request_validation_failed | MCP argument/type/mode error, legacy compose save, or Backend validation; correct fields; compose/save hint names prompt_write(action=save). |
| backend_http_error | Unstructured/unknown HTTP error; message keeps HTTP status; inspect before retry. |
| backend_unavailable | HTTP connection/timeout; check service; inspect existing job ID before resubmission. |
| tool_execution_failed | Unexpected wrapper/dependency exception; inspect before retry; writes may have uncertain admission. |
| invalid_json | Custom workflow must be a valid JSON string. |
| generation_failed | Job failed; inspect node errors; never automatically fall back from worker to local. |
| job_not_found | Check the existing job ID/status before submitting another job. |
| revision_parent_not_found | Choose an existing canonical artifact ID. |
| revision_parent_not_image | Choose an image artifact as parent. |
| revision_request_conflict | Use the parent's request_ref or choose a parent from this request. |
| revision_parent_context_invalid | Recover the parent's stored context before using this anchor. |
| invalid_resource_locator | Correct prompt resource type/polarity/category; restore supports category/entry only. |
| revision_conflict, external_change | Reload prompt revision/ETag and reconcile; no automatic overwrite/retry. |
| legacy_training_fields_removed | Run decision preflight and submit its exact versioned recipe start_payload. |
| admission_uncertain | A training request may already exist; check canonical job_id first; do not resubmit automatically. |
| backend_failed, empty_caption | LoRA Backend failure or empty caption; inspect and repair before retry. |
| operator_not_configured, operator_unavailable | Configure server-side Discord token or restore bot endpoint. |
| invalid_operator_response, operator_request_failed | Inspect bot response/logs and correct job/destination; HTTP status is retained when available. |

Structured Backend codes/messages/hints/details (including prompt fail-closed
migration, preset replay/source errors and resource-acquisition failures) pass
through the common envelope. LoRA operations continue their existing allowlisted
safe code/diagnostic projection from mcp_server/lora_public.py; unknown LoRA HTTP
errors use backend_http_error with status. Revision-parent legacy error bodies
use their existing canonical allowlisted recovery copy, without echoing arbitrary
Backend hint text. Known domain failures are not collapsed into a connection error.

## Troubleshooting

| Problem | Check |
|---|---|
| Server does not start | Client MCP logs, wrapper path, uv on PATH, dependencies |
| Ping fails | MCP_BACKEND_API_URL and Backend availability |
| Tools missing or stale | Reload client discovery; compare tool_catalog.py |
| Discord delivery fails | Bot endpoint/token, allowlisted alias and completed job |
| Direct ComfyUI action fails | MCP_COMFYUI_API_URL and ComfyUI-Manager for node/restart actions |
| Host artifact read fails | Actual Backend Gallery root, filesystem access and returned locator |

## Development

```bash
AI_DRAWING_TEST_ROOT="$TMPDIR/ai-drawing-mcp-tests" python -m pytest -c pytest.ini mcp-server/tests -q --timeout=60
```

Add the intent/risk and implementation pointer to tool_catalog.py; server.py
registers it with the shared envelope boundary. Tests must call real registered
wrappers, mocking transport or service dependencies below them.
