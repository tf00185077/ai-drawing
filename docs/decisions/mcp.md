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
- Configured-worker discovery preserves configuration separately from nullable current observations and uses an additive extension of existing Backend status; failed probes retain one configured worker and Backend-read failure is not an empty list · Producer choice under delegated authority after K4-1 · [contract](#configured-worker-health-and-identity)
- Phase 1 is implemented by the Paperclip team from `docs/tasks/p1-*`; the earlier planning-only session restriction is superseded for this round by the [follow-through instruction](../requests/2026-11-24-proceed-within-project-boundaries.md) · owner-confirmed

## Log (newest first)

### 2026-11-24 · Keep configured worker identity distinct from probe observations
- Decision: adopt the [configured-worker contract](#configured-worker-health-and-identity) for p1-04. Extend the existing read-only worker-status response additively; keep its existing flags/nested worker response. Expose configured URL/expected identity independently of nullable current observations and the validated resolved endpoint. Preserve one configured entry after probe failure; report an unavailable/unknown Backend read through the common error envelope.
- Why: the current status route has no URL and drops identity metadata on failed probes. Guessing identity or returning no workers would misstate configuration. Current `last_error` needs no persistent history or heartbeat store.
- Supersedes: the unspecified configured-versus-observed field meaning and endpoint-extension disposition in p1-04 kickoff round 1, not the read-only/single-worker scope.
- Provenance: Producer adopts [QA's K4-1 recommendation](/AID/issues/AID-165#comment-ba500f6f-fe78-44e1-87d4-dc81558560b9) under the [delegated routine-choice instruction](../requests/2026-11-24-proceed-within-project-boundaries.md), after reading the actual report, route evidence and current worker client/settings. This is a technical choice inside Phase 1, not a new owner-boundary decision or implementation acceptance.
- Link: [clarification 1](../tasks/p1-04-mcp-health-and-workers/kickoff-clarification-1.md). Fresh independent fixed-source kickoff must CLEAR the clarified task before Coding.

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

## Wait results and media locators

Target contract for [p1-03](../tasks/p1-03-mcp-wait-and-result/task.md), clarified
by Producer under delegated technical authority after [K3-1](../tasks/p1-03-mcp-wait-and-result/kickoff-clarification-1.md).
Fresh independent kickoff CLEAR remains required; this section does not claim
that `wait_for_job` is delivered or deployed. It stays one `read` intent in the
common envelope. Backend state, identity and provenance remain authoritative.

- A completed generation with supported Gallery locators returns success,
  unchanged job ID/status and every existing canonical image/video artifact's
  real `artifact_id`, kind, host path and Backend Gallery URL. Preserve result
  order/provenance and canonical revision references; no arbitrary result cap
  may omit the required artifact set.
- Resolve safe Gallery-relative locators under `MCP_GALLERY_DIR` for the host
  path and the configured Backend Gallery route for the URL. Preserve file
  identity through nested/Unicode names and URL encoding. An existing relative
  Backend URL is a supported locator; making it absolute may only bind it to
  the configured Backend base without changing its target. A host path is usable
  only by clients with access to that filesystem. Locator construction does not
  verify file existence, bytes or remote consumption.
- Never infer host containment from a basename, remap an outside-root or
  container-only absolute path to a different file, accept traversal/escape or
  arbitrary remote URLs, or create/copy/move a file to fill in missing metadata.
  An absolute path may supply a host locator only when its Gallery relationship
  is established without guessing; unsupported/missing relationships follow
  the error disposition below.
- A legacy image-only completion keeps `artifacts: []` and a separate legacy
  image result carrying the actual image ID, kind=image and supported path/URL.
  Its canonical artifact ID stays null/absent. Never use an image ID as an
  artifact ID or invent an artifact row. The separate namespace must remain
  explicit in docs and tests.
- If any required generation media locator is missing, outside the supported
  Gallery mapping or unsafe, return `ok: false` with
  `error.code: artifact_locator_unavailable`. `error.details` retains the target
  job ID, job domain, unchanged completed Backend status, all known canonical
  artifact identities/kinds and separate legacy image identities, plus which
  locator is unavailable and why. Return supported available locators truthfully;
  unavailable ones remain null/absent, and an unverified outside-root path must
  not be advertised as a usable Gallery host path or exposed through a new URL.
  The hint directs the caller to inspect the same job and existing Gallery
  metadata/configuration before another read; do not imply generation failure,
  cancel, resubmit or automatically migrate data. Preserve the whole known result
  identity set even when only one artifact lacks locators.
- Training completion reports existing public output/registration fields;
  safetensors output is not Gallery image/video media. Keep `artifacts: []` when
  no real canonical media exists. Preserve independently bound smoke job, image
  and nullable artifact IDs, locators, status and safe diagnostics exactly as
  available, including legacy image-only and `artifact_unavailable` states.
  Pending/failed/unavailable smoke is not training failure. Do not wait for,
  start or resubmit that separate job or turn its image ID into an artifact ID.
- Read failures preserve safe Backend reason/code/recovery and target identity;
  training's successful status-read flag does not turn a failed training job
  into wait success. Resolve the two UUID job domains with existing reads;
  a connection error/5xx is not a not-found proof or a reason to probe another
  domain as if the first were absent. Preserve terminal cancellation truthfully.
- All lookup/status/enrichment requests, sleeps and response preparation share
  one monotonic deadline. High requested timeouts clamp to the sourced maximum,
  or the explicit 50-second fallback if the actual client limit is unverified.
  A budget exhausted before complete result preparation returns timeout with
  current/last-known status, or explicitly unknown if no read completed, and
  a call-again hint for the same job. It never cancels/resubmits. A completed
  status observed near the deadline cannot start unbounded enrichment. Existing
  per-request defaults do not override the overall deadline.

Acceptance cases include normal multi-image/mixed image-video completion,
separate image/artifact IDs, nested/Unicode locators, legacy image-only success,
a canonical artifact with no URL, outside-root/container-only paths, missing or
unsafe locator input and mixed available/unavailable results. Also check training
completion without media, real/legacy/absent/pending/failed/unavailable smoke
references, failed/cancelled jobs in both domains, and deadlines consumed by the
first status read, fallback lookup and artifact enrichment. Tests traverse the
registered MCP/HTTP boundary with mocked existing Backend shapes; a short real
elapsed-time mocked-transport check supports the configured bound. No new real
training run, remote retrieval claim or Backend change is required.

## Configured-worker health and identity

Target contract for [p1-04](../tasks/p1-04-mcp-health-and-workers/task.md), adopted
by Producer after K4-1 under delegated technical authority. This is a clarified
specification, not a claim that health or worker discovery is delivered or
deployed. Fresh independent kickoff CLEAR and later exact-commit delivery PASS
remain required.

Reuse `GET /health`, `GET /api/system/status` and `GET /api/workers/status`.
The existing worker-status response may be extended additively to expose the
required configuration and observation fields; preserve its existing
`configured`, `reachable`, `status`, failure `error_type` and successful nested
`worker` behavior for existing consumers. Backend configuration remains the
authority; MCP must not read a private Backend settings file or add a parallel
worker configuration. No second status route, registry, heartbeat, scheduling
or persistent error history is introduced.

For the MCP `list_workers` entry, field meanings are:

| Field | Meaning |
|---|---|
| `url` | Configured `NVIDIA_WORKER_URL`, with the existing worker client's trailing-slash normalization; never silently replaced by a discovered address. |
| `expected_hostname` | Configured expected hostname, or null if none was set. It is an expectation, not an observation. |
| `expected_protocol_version` | Configured expected protocol version, including the existing default. It is not evidence of a successful probe. |
| `hostname` | Hostname actually returned by this accepted current worker-status probe; null if absent or the probe/identity validation failed. Never substitute an expectation or stale observation. |
| `protocol_version` | Protocol actually returned and accepted by the current probe; null on failed probe/validation. |
| `resolved_url` | Actual endpoint used by the accepted current worker-status probe, including an address chosen by existing LAN discovery/cache. Null without an accepted current probe; it does not rewrite `url`. |
| `reachable` | Whether that current worker-status probe succeeded under existing identity validation. This does not certify remote ComfyUI, models or generation readiness. |
| `status` | Existing worker-status disposition (`ready` or `unavailable` for a configured worker). |
| `last_error` | Null on an accepted current probe; otherwise a safe nonempty reason string for the current failed observation, with read/configuration recovery guidance. It is not persisted error history. |

Backend response layout may keep configuration and observations nested; it
must supply these meanings to MCP without private settings access or guesses.
Preserve existing hostname/protocol validation and single-worker LAN discovery
semantics, including its derived runtime URL cache. Failed identity validation
does not produce accepted current observations. URL-only configuration can
successfully report a valid protocol without a hostname; in that case
`hostname` is null and `reachable` can be true.

- A successful authoritative Backend response with `configured: false` yields
  an empty worker list. It is the only basis for the empty/unconfigured result.
- A configured worker yields one entry even after connection, HTTP, protocol or
  hostname validation failure. Keep its configuration, false reachability,
  safe current error and null current observations/resolved URL. Do not show a
  stale success as current or erase configuration because a probe failed.
- Backend connection/HTTP/invalid-status failure makes configuration unknown.
  Return the common error envelope with a stable code and safe same-read/config
  recovery hint, never an inferred empty list or worker observation.
- `health` retains one entry each for Backend, Backend-local ComfyUI and worker
  even on Backend-down or partial status-read failure. A false `reachable`
  observation needs a safe reason that distinguishes a reported failed probe
  from an unavailable/not-observed dependency read. No direct dependency fallback
  probe is introduced. Preserve ComfyUI configuration/state/hints: `no_models`
  and `degraded` can still be reachable. Response layout/error spelling remain
  Coding choices within the existing common envelope.

Both MCP tools are `read` and use the real registered HTTP path. Replace ping
and add health/list_workers, yielding 31 intents while preserving all other 29
names/risks and accepted wait behavior. Independent literal risk expectations
and recorded GET paths must prove this; deriving the expected labels from the
catalog itself is not a guard. No generation/training submission, cancellation,
PowerShell, install or control request is part of discovery.

Acceptance includes unconfigured, configured up/down, failed hostname/protocol
validation, URL-only success without hostname, an accepted existing-discovery
endpoint distinct from configuration, Backend-down/partial-read failure and
reachable ComfyUI without models. Use real Backend routes/client validation
and registered MCP wrappers/client with mocked transports, not live LAN scans.
Document the actual response/error examples and recovery. Backend-local ComfyUI
health is separate from `MCP_COMFYUI_API_URL` used by direct admin. Resource
inventory, reachability and locators do not prove worker model parity, loaded
source, job readiness, artifact bytes or client access.

## Open questions
- None for resource selection: Producer adopted `Illustrious-XL-v2.0.safetensors` + `default`, no LoRA, local target under [delegated routine-choice authority](../requests/2026-11-24-proceed-within-project-boundaries.md); p1-00 verifies runtime compatibility, p1-05 reuses the pair.
- The tool-call timeout of the MCP client the Paperclip agents use — found in [p1-03](../tasks/p1-03-mcp-wait-and-result/task.md).
