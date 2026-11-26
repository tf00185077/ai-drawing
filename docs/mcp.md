# MCP server

The stdio MCP server gives agents 31 tools with one response envelope and one
risk label per intent. It calls the existing Backend APIs; direct ComfyUI admin
operations and Discord delivery use their configured service endpoints.

The accepted [p1-04 delivery](tasks/p1-04-mcp-health-and-workers/acceptance.md)
replaces temporary `mcp_ping` with `health` and adds `list_workers`, after
independent exact-commit PASS. This source publication does not deploy the
running product.
The earlier combined p1-01/02 delivery was a breaking change. Reload client tool discovery and
migrate old calls using the [complete capability map](tasks/p1-02-mcp-tool-consolidation/manifest.md#old-to-new-capability-map).
The catalog in `mcp-server/mcp_server/tool_catalog.py` drives registration.

Accepted [p1-00a evidence](tasks/p1-00a-mac-runtime-and-retrieval/acceptance.md)
proves one original/revision pair and decoded bytes through unmodified host paths
for a colocated Mac client; its deterministic original used cache. The original
baseline remains 23 intervention units/eight incidents. This MCP software
change is verified offline and does not redeploy that runtime, prove remote URL
consumption, meet the three-run exit, or imply aesthetic/phase acceptance.

Accepted [p1-05](tasks/p1-05-mcp-e2e-smoke-mac/acceptance.md) adds canonical
static PNG bytes on `gallery_get` and the [strict Mac smoke driver](#strict-mac-smoke-driver).
Exact independent QA PASS, fresh three-pair MCP-byte/lineage/uncached-sampling
proof and native owner fixed-demo acceptance are recorded. Phase-close roadmap
review remains separate before Phase 2. Historical p1-00a bytes were fetched
outside MCP and never substitute for this qualification. Source integration
performs no runtime/client deployment or new generation.

The [Phase 2 First check](tasks/p2-00-civitai-first-check/acceptance.md) is accepted
as one manually bridged login-required LoRA/download/registration/default_lora
image observation. It used current MCP reads/generation plus counted direct
provider/key/transport/record/default bridges; it does not add tools or automatic
Phase 2 behavior. All 31 intent names/risks remain. [p2-01](tasks/p2-01-civitai-key-file/task.md)
enters fresh kickoff for private key-file/credential-safe request behavior;
provider search, unified records, generic download jobs and automatic defaults
remain later implementation tasks.

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
| `MCP_COMFYUI_API_URL` | `http://127.0.0.1:8188` | Direct admin operations only; independent of Backend-local health |
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
| `health` | read | Backend, Backend-local ComfyUI and worker reachability; retains unknown reads |
| `list_workers` | read | zero/one configured worker; configuration separate from current observations |
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
| `gallery_get` | read | exactly one image_id or artifact_id; optional bounded canonical static PNG content |
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
`health` and `list_workers` use only the existing Backend GET/status routes.
There is no registry, heartbeat, scheduler or worker-control intent in discovery.

## Health and configured worker

Call `health()` before selecting a target. Its common success envelope always
contains `data.backend`, `data.comfyui` and `data.worker`. Each has `reachable`
and a nullable `reason`. False reachability has a safe nonempty reason:

- `reason_code: reported_unreachable` means the Backend reports a failed probe.
- `reason_code: not_configured` means a successful read confirms no configuration.
- `reason_code: not_observed` means the dependency status could not be read
  through the Backend. `configured` is null, and `read_error` gives a stable
  code, safe message and same-read recovery hint. It does not establish a
  failed dependency probe.

Full recorded envelopes and GET requests are in the accepted delivery
[offline samples](tasks/p1-04-mcp-health-and-workers/delivery-1-evidence/recorded-mcp-samples.output.txt).

The tool reads `/health` first. If that read fails or is invalid, Backend is
unreachable with a read error and both dependencies remain not observed; no
further request is sent. Otherwise `/api/system/status` and
`/api/workers/status` are read independently: failure of either leaves the
other observation intact. Read failures are represented in the aggregate's
success data so all three entries survive. They do not turn into job failure.

ComfyUI preserves Backend `mode`, `state`, `configured`, `reachable`, model
counts, `warnings` and `hint`. In particular `no_models` and `degraded` can
remain reachable. This is **Backend-local** ComfyUI configured by Backend
`COMFYUI_MODE`/`COMFYUI_BASE_URL`, not `MCP_COMFYUI_API_URL` for direct admin.
Health sends no direct ComfyUI or worker fallback request. Each Backend read
uses a five-second HTTP timeout; these are sequential observations, without
an atomic snapshot or an overall wait-style deadline.

`list_workers()` reads only `/api/workers/status`. A successful authoritative
unconfigured response returns exactly `{"ok":true,"data":{"workers":[]}}`.
A configured worker returns one entry even when its current probe fails:

```json
{"ok":true,"data":{"workers":[{"url":"http://192.0.2.10:8791","expected_hostname":"EXPECTED-PC","expected_protocol_version":2,"hostname":null,"protocol_version":null,"resolved_url":null,"reachable":false,"status":"unavailable","last_error":"Worker status probe failed; inspect Backend NVIDIA_WORKER_URL, expected hostname/protocol and worker availability, then retry this read."}]}}
```

`url` is Backend `NVIDIA_WORKER_URL` with trailing slashes removed. Expected
hostname (null when unset) and protocol (default 2) are configuration, never
observations. Accepted current probes supply `hostname`, `protocol_version`
and `resolved_url`, with `last_error: null`. A URL-only configuration may be
reachable with `hostname: null` and a valid protocol. With existing discovery,
`url` can remain `http://192.0.2.10:8791` while `resolved_url` is the accepted
`http://192.0.2.11:8791`. A later connection/HTTP/identity failure clears all
three observations even when that address remains cached. `last_error` is a
safe reason for the current failed probe, without persistent error history.

Backend connection/HTTP/invalid or inconsistent worker status makes
configuration unknown and returns the common error envelope, never an empty
list or inferred observation. Example:

```json
{"ok":false,"error":{"code":"invalid_backend_status","message":"Backend status response is missing, invalid or inconsistent.","hint":"Inspect Backend availability and status/configuration, then retry this read; no job submission is needed."}}
```

Health uses that same error object in the affected entry's `read_error` and
labels the dependency not observed. `backend_http_error` retains HTTP status
without arbitrary response text; `backend_unavailable` reports connection or
timeout failure. Inspect Backend availability, deployed status contract and
configuration, then repeat the read. Failed worker probes instead require
checking Backend worker URL/expected identity and worker availability.

One worker only until Phase 3. Reachability does not certify remote ComfyUI,
worker model/node parity, generation readiness, loaded-source identity or
artifact availability/bytes/client access. `list_resources` still inventories
the Backend host. Keep execution target explicit; discovery submits, cancels,
installs and controls nothing, and never silently falls back worker to local.

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
Use host paths only where that filesystem is accessible. Accepted p1-05 verifies
real Mac waits and canonical PNG bytes consumed through MCP. Broader remote URL
consumption remains unverified.

## Common flows

The current image flow is **health → list_resources → generate →
wait_for_job → gallery_get(artifact_id=..., include_content=true)** for canonical
PNG bytes; metadata locators remain available. Example tool arguments:

```json
{"tool": "health", "arguments": {}}
{"tool": "list_workers", "arguments": {}}
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

Use `list_workers` when selecting the configured worker; inspect health reasons
before generation. This accepted flow is executable in source and verified
offline. Deployment, real-run wait and the Phase 1 exit remain unverified here.

**Retrieve:** `gallery_get(image_id=...)` retains image metadata and locators;
`gallery_get(artifact_id=...)` retains full canonical metadata, including existing
video/legacy/non-PNG behavior. Metadata reads open no content. Set
`include_content=true` with exactly one **positive integer canonical artifact ID**
to receive PNG bytes through MCP. Image IDs, booleans/coercible IDs, absent/multiple
selectors and unsupported fields fail validation before Backend/file access.

Content reads use the existing Backend artifact route, verify its identity and
require `artifact_type=image` and declared `image/png`. Only a supported Gallery
mapping under the actual resolved `MCP_GALLERY_DIR` is read. Nested/Unicode paths
retain identity. The regular file actually opened is checked through its OS
handle, including intermediate symlink races; unsupported handle inspection fails
closed. No caller path/URL/root, URL fetch, basename remapping, copying or state
change is accepted. Host Gallery filesystem access is required by the MCP server.

A single bounded read requests at most 2,097,153 bytes, with maximum content
2,097,152 bytes (2 MiB). Content must fully decode as one static PNG frame, with
width/height 1–2048 and at most 4,194,304 pixels. Header dimensions are checked
before full decoding. Pillow is a declared dependency; bytes are never rewritten.
Success retains ordinary `data` metadata and adds exactly:

```json
{"content":{"encoding":"base64","mime_type":"image/png","byte_length":123,"sha256":"<lower-case SHA-256 of returned bytes>","width":512,"height":512,"base64":"<standard unwrapped base64>"}}
```

The client can decode and validate these received bytes without another product
fetch. Length, digest and dimensions describe those exact bytes. Backend lookup
errors retain their prior codes/hints. Other failures return no partial content:
`artifact_content_unavailable` for missing/unreadable/unsafe/unmapped or identity
conflicts, `artifact_content_too_large` for byte/dimension/pixel limits, and
`artifact_content_invalid` for empty/corrupt/non-PNG/animated/unsupported MIME or
media. Details retain the requested ID and safe identity metadata, omitting unsafe
paths and file contents. Inspect the same artifact metadata/configuration or use a
metadata-only read; completed jobs stay completed. Metadata locators alone still
do not prove retrieval.

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
Restart may interrupt work. Health afterwards reports Backend-local dependencies;
if direct admin targets another ComfyUI, its state is not observed by health.
deliver_to_discord accepts job_id, allowlisted destination_alias and optional
force_resend. The bot enforces allowlist and dedup; it cannot send arbitrary
files, messages or channel IDs through this tool.

## Strict Mac smoke driver

Use a separate environment; do not modify canonical Backend/MCP venvs for this
experiment. From the pinned candidate worktree:

```bash
uv venv .venv --python 3.11
uv pip install --python .venv/bin/python -e ./mcp-server
.venv/bin/python scripts/mcp_smoke_mac.py prepare \
  --config /persistent/evidence/invocation.json \
  --backend http://127.0.0.1:8001 --gallery /actual/host/gallery
.venv/bin/python scripts/mcp_smoke_mac.py run \
  --config /persistent/evidence/invocation.json --output /persistent/evidence/run-1
```

`prepare` creates a new file containing six request references and twelve distinct
48-bit seeds from `secrets.randbits`, allocated before qualification. Review and
record runtime/client preparation before `run`. The exact fixed parameters are
Illustrious-XL-v2.0.safetensors/default, explicit local, `loras=[]`, 512×512,
batch 1, four steps, CFG 7, Euler/normal, fixed fresh seeds and red-cup/blue-cup
prompts. Four steps guarantee neither speed nor aesthetics. The script validates
the fixed inputs and source fingerprints; it never downloads or changes models.
Bind the actual Backend/ComfyUI source/process/import/configuration/roots in the
preparation ledger; source fingerprints in `frozen.json` identify the client
worktree, not an uninspected long-running Backend. Preserve active jobs, private
configuration, roots and complete database schema/values before a controlled
replacement. Never infer loaded source from HEAD/cwd/health or restart for docs.

Every attempt is exactly `health → list_resources → generate → wait_for_job →
gallery_get(include_content=true) → generate(parent_artifact_id=original) →
wait_for_job → gallery_get(include_content=true)`. Each image has one submit and
one wait with the unchanged **50-second total tool fallback**. This SDK driver
uses a disclosed 65-second response guard; it does not measure another calling
client's limit or expand the tool wait. No external byte fetch or status salvage
occurs in an attempt. Bytes/digest/length/full decode and persisted canonical
parent/job/request/brief context must validate before accepting a pair.

Timeout/error/nonterminal/failure/cancellation/invalid bytes/lineage/interruption
resets the streak. Recovery is a separate ledger of at most six same-ID read-only
waits per possibly outstanding known job. All preceding submitted jobs must be
terminal before a new declared attempt. Unknown admission without a recovered ID
or unresolved finite recovery stops the invocation, preserving jobs. It never
cancels, resubmits or changes target. Six attempts maximum; stop after three
consecutive successes. A timeout fails qualification without proving job failure.

SIGINT/cancellation records the interrupted call with its arguments, start/end,
duration and interruption rather than inventing a response. SDK traffic records
whether the request was sent. The active attempt ends once, nonqualifying, with
zero streak and explicit admission uncertainty. Known job identities and their
last observed status remain intact. Interruption exits immediately without
recovery, audit or another submit; the exclusive evidence directory cannot be
resumed. Any later same-ID read-only recovery is separate disclosed work. An
unknown admission without a recovered ID prohibits a new attempt or resubmission.

The output directory must be new and is never overwritten. `sdk-messages.jsonl`
contains complete sent/received SDK JSON-RPC messages and actual content payloads;
`calls.jsonl` records phase/attempt, UTC, durations, arguments and complete SDK
results. `events.jsonl`, separate session stderr, `frozen.json`, `summary.json`
and decoded `payloads/*.png` retain failures and successes. A second SDK process
and session corroborates all validated records after attempts. A zero exit code
means **streak complete, independent sampling audit pending**. Exit 2 is honest
non-exit/interruption/audit failure; it is never permission to rerun silently.

After results, independently reconcile all six distinct jobs/artifacts with six
ComfyUI prompts, compiled graphs and actual sampling/cache evidence. Retain every
post-result audit call, including outside-MCP Backend/ComfyUI/file reads, separately.
Audit failure invalidates technical exit evidence. Reconcile preparation, attempts,
recovery and audits against original F1–F8 units 1,1,1,6,1,11,1,1 = 23; never
label the whole round zero interventions merely because a qualifying attempt had
none. A product/input change requires renewed applicable qualification. Independent
QA reviews D1–D3 at the exact final candidate. Producer records the actual owner
demo decision separately; p1-05's fixed native confirmation is accepted in its
[acceptance record](tasks/p1-05-mcp-e2e-smoke-mac/acceptance.md). The roadmap
phase-close gate remains separate.

## Error codes and recovery

| Code | Meaning / hint |
|---|---|
| request_validation_failed | MCP argument/type/mode error, legacy compose save, or Backend validation; correct fields; compose/save hint names prompt_write(action=save). |
| backend_http_error | Unstructured/unknown HTTP error; message keeps HTTP status; inspect before retry. |
| backend_unavailable | HTTP connection/timeout; check service; inspect existing job ID before resubmission. |
| tool_execution_failed | Unexpected wrapper/dependency exception; inspect before retry; writes may have uncertain admission. |
| invalid_backend_status | Health dependency read or worker configuration is unknown: inspect the deployed Backend status contract/configuration, then retry this read. Never infer an empty worker list. |
| invalid_json | Custom workflow must be a valid JSON string. |
| generation_failed | Job failed; inspect node errors; never automatically fall back from worker to local. |
| timeout | Overall wait budget exhausted; last-known status is retained, unknown before a completed read; call wait_for_job again with the same ID. |
| artifact_content_unavailable, artifact_content_too_large, artifact_content_invalid | Inspect the same artifact metadata and MCP_GALLERY_DIR; metadata-only reads remain available. No job-state change. |
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
| Health Backend entry fails | MCP_BACKEND_API_URL and Backend availability; dependencies are not observed |
| Worker list read fails | Backend status endpoint/schema/configuration; repeat the same read |
| Configured worker unavailable | Backend NVIDIA_WORKER_URL, expected hostname/protocol and worker availability |
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
