# MCP server

The stdio MCP server gives agents 30 tools with one response envelope and one
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
| `wait_for_job` | read | bounded generation/training wait plus existing media locators |
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
There is no MCP `health` or `list_workers` in this delivery.

## Bounded wait and results

Call `wait_for_job(job_id, timeout_seconds=50)` after generation or training.
Positive finite timeouts above **50 seconds** clamp to 50. The actual calling
client's enforced tool-call limit is **unverified**: tracked wrappers/settings
do not configure it. Fifty seconds is the approved fallback policy, not a
measured client limit. One monotonic deadline covers job-domain lookup, every
HTTP request and body chunk, Gallery enrichment, polling sleeps and response
preparation. HTTP's existing 60-second per-request default does not extend it.
An unfinished read is aborted at the wait deadline; the Backend job continues.

Both domains use UUIDs. Wait reads generation first and tries training only
after an actual HTTP 404. Connection/5xx failures preserve their safe error
code/reason/recovery, rather than proving absence or job failure. Once found,
the same domain is polled. No submission, smoke submission or cancellation
request is sent. `job_status` and `lora_train_job_status` remain separate reads.

Completed generation returns the common success envelope, for example:

```json
{"ok": true, "data": {"job_id": "...", "job_domain": "generation", "status": "completed", "artifacts": [{"id": 12, "artifact_id": 12, "artifact_type": "image", "kind": "image", "gallery_path": "run/cup.png", "local_path": "/host/gallery/run/cup.png", "artifact_url": "http://127.0.0.1:8001/gallery/run/cup.png"}], "images": []}}
```

`artifacts` keeps **every** canonical media result in Backend order, with its
real `artifact_id`, `kind` (image/video), source-node/provenance fields and
revision context. `images` is a separate image-ID namespace: when Backend
returns an `image_id`, its entry carries `image_id`, `artifact_id: null`,
`kind: image`, stored `image_path`, host `local_path` and `image_url`. A legacy
image-only completion therefore has `artifacts: []` and its real image reference
in `images`; an image ID is never substituted for a canonical artifact ID.

Safe Gallery-relative paths map under `MCP_GALLERY_DIR`; nested/Unicode names
keep their identity and constructed URLs are encoded. An existing relative
Backend `/gallery/...` URL can establish the mapping and is bound only to the
configured Backend authority, preserving its target. A stored absolute path
is usable only when containment under the configured host Gallery root can be
established. Outside-root/container-only paths are never remapped by basename.
Traversal, symlink escape, credential-bearing/arbitrary remote URLs and
conflicting locators are rejected. No file is created, copied or migrated.

If required generation locators are unavailable/unsafe, wait returns
`ok: false`, `error.code: artifact_locator_unavailable`. `error.details` keeps
the **unchanged completed Backend status**, target job/domain, full known
`artifacts` and separate `images`, supported locators on available results, and
`unavailable_locators` with the affected identity and reason. Unusable host
paths/URLs remain null. Stored `gallery_path`/`image_path` are source metadata,
not a promise they are usable locators. Inspect the same job and existing
Gallery metadata/configuration before another read; this is not generation
failure and does not authorize automatic resubmission or data migration.

Completed training returns `job_domain: training`, public output/registration
fields and `artifacts: []`, `images: []`. Its safetensors output is not Gallery
media. Existing independent `smoke_test_job_id`, nullable
`smoke_test_artifact_id`, separate `smoke_test_image_id`, safe locators/status
and diagnostics retain the existing public LoRA projection. Completed training
does not wait for smoke: queued/running/failed/cancelled/`artifact_unavailable`
smoke remains independent of successful training. It submits no smoke job.

Failed jobs return `ok: false` with the Backend failure reason/code and
job/domain/status in `error.details`; generation node/recording/revision
diagnostics and safe public training output/registration state survive.
Cancelled jobs use `job_cancelled` and keep `status: cancelled`.

When the overall budget expires first (including completion observed before
unfinished enrichment), the result is:

```json
{"ok": false, "error": {"code": "timeout", "message": "Wait budget exhausted; Backend job status is unchanged.", "hint": "Call wait_for_job again with the same job_id ...", "details": {"job_id": "...", "job_domain": "generation", "status": "running", "artifacts": [], "images": [], "timeout_seconds": 50.0}}}
```

Status is current/last-known (`completed` can coexist with timeout during
enrichment); before any status read completes it is explicitly `unknown`.
Domain is `unknown` until a read identifies it. Call again with the same ID;
timeout never means job failure, cancellation or resubmission. Locator
construction verifies neither file availability nor bytes/remote retrieval.
Use host paths only where that filesystem is accessible. Real-run wait and
remote consumption remain later verification, including p1-05.

## Common flows

The executable current flow is **mcp_ping → list_resources → generate →
wait_for_job → consume the returned locator**. Example tool arguments:

```json
{"tool": "mcp_ping", "arguments": {}}
{"tool": "list_resources", "arguments": {}}
{"tool": "generate", "arguments": {"mode": "template", "prompt": "a red ceramic cup", "checkpoint": "Illustrious-XL-v2.0.safetensors", "template": "default", "execution_target": "local", "loras": []}}
{"tool": "wait_for_job", "arguments": {"job_id": "<data.job_id from generate>", "timeout_seconds": 50}}
{"tool": "job_status", "arguments": {"job_id": "<data.job_id from generate>"}}
{"tool": "gallery_get", "arguments": {"image_id": 4448}}
{"tool": "gallery_get", "arguments": {"artifact_id": 3863}}
```

Use the IDs returned by your job; the final two numbers illustrate the different
namespaces. `job_status` polling and `gallery_get` remain available for explicit
status/full metadata reads. Repeat wait on timeout with the same ID. A failed job is an
error envelope with status/node/recording/revision details. A timeout does not
prove failure: inspect the existing job ID before any resubmission. No automatic
resubmission or failed-worker local fallback occurs. cancel_job remains for
queued generation; LoRA status and cancel use their own named tools.

The staged final Phase 1 flow is **health → list_resources → generate →
wait_for_job → consume locator (gallery_get for full metadata)**. p1-04 replaces temporary
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
| timeout | Overall wait budget exhausted; last-known status is retained, unknown before a completed read; call wait_for_job again with the same ID. |
| artifact_locator_unavailable | Generation completed; inspect existing Gallery metadata/configuration. Full known result identities survive; never invent locators or automatically migrate/resubmit. |
| job_cancelled | Backend terminal cancellation is retained in error.details; inspect the same job before deciding on a new request. |
| training_failed | Training failed without a more specific safe code; public output/registration state survives. |
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
