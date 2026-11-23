# MCP setup and tool usage

MCP provides generation, Gallery, resource, Prompt Library and style-preset tools. Most call the Backend; direct ComfyUI operations and Discord delivery use separate endpoints. Registration does not establish runtime readiness or acceptance.

## Install and connect

Configure the application using [Setup guide](setup-guide.md), then install MCP separately with Python `>=3.10` and server dependencies. The launcher does not install/configure/start MCP.

From the repository root:

```bash
cd mcp-server
uv sync
```

Alternatively, in an appropriate Python environment:

```bash
cd mcp-server
python -m pip install -e .
```

The repository wrappers change into `mcp-server` and run `uv run ai-drawing-mcp`. Make `uv` available to the MCP client's process, not only an interactive shell.

For Cursor, add an entry to project `.cursor/mcp.json` or personal `~/.cursor/mcp.json`. Other stdio MCP clients use the same command/environment pattern. Replace the absolute paths with your own:

```json
{
  "mcpServers": {
    "ai-drawing": {
      "command": "/absolute/path/to/ai-drawing/scripts/run-mcp-server.sh",
      "args": [],
      "env": {
        "MCP_BACKEND_API_URL": "http://127.0.0.1:8001",
        "MCP_COMFYUI_API_URL": "http://127.0.0.1:8188",
        "MCP_GALLERY_DIR": "/absolute/path/to/ai-drawing/data/gallery"
      }
    }
  }
}
```

On Windows, use the absolute `scripts/run-mcp-server.bat` path in the client's command format; escape JSON backslashes. Clients supporting `cwd` can run `uv run ai-drawing-mcp` from the absolute `mcp-server` directory. Wrappers avoid this client-dependent setting. [Windows Worker](windows-worker.md) configuration is separate.

Reload after configuration changes. In Cursor, check **Tools & MCP** and MCP logs. `mcp_ping` checks Backend `/health`, not ComfyUI, models, delivery paths, Worker or training.

## Environment and address boundaries

`mcp_server/config.py` reads process `MCP_` variables, not `.env`. Export them or set them in client configuration.

| Variable | Meaning and current default |
|---|---|
| `MCP_BACKEND_API_URL` | Backend base URL; `http://127.0.0.1:8001` |
| `MCP_COMFYUI_API_URL` | Direct ComfyUI operations; `http://127.0.0.1:8188` |
| `MCP_GALLERY_DIR` | Gallery root readable by the MCP host; the source default is a developer-specific path, so set this explicitly |
| `MCP_DISCORD_OPERATOR_URL` | Bot-local operator endpoint; `http://127.0.0.1:8765` |
| `MCP_DISCORD_OPERATOR_TOKEN` | Optional server-side shared secret; unset by default |

Default host Gallery: `<repository>/data/gallery`, not container `/data/gallery`. Use host-visible custom paths. Match Backend ports: manual development defaults to `8000`, Compose host to `8001`.

Keep Discord tokens in private environment/secrets configuration. Delivery sends completed generation results only to allowlisted destination aliases, not arbitrary files/messages.

### Backend versus direct ComfyUI

- Generation, Gallery, Civitai, Prompt Library, and style-preset requests use `MCP_BACKEND_API_URL`. The Backend owns queueing, recording, and execution routing.
- `free_comfyui_memory`, `comfyui_node_provision`, and `comfyui_restart` call `MCP_COMFYUI_API_URL` directly, not the Backend. They do not select a worker through `execution_target`.
- Node provisioning installs a package from ComfyUI-Manager's curated registry and requires a working Manager API. It does not restart ComfyUI. Restart requires explicit user approval because it can interrupt other jobs.
- Discord delivery calls the bot operator endpoint separately.

See [Windows worker](windows-worker.md) for routing and failure behavior. Local ComfyUI checks do not establish Worker readiness.

## Current tool catalog

Authority: [source catalog](../mcp-server/mcp_server/tool_catalog.py), checked against registration by `mcp-server/tests/test_tool_catalog.py`. Live client schemas define accepted arguments. The table records registration, not acceptance.

`dict` means a JSON-compatible object, `json_string` a JSON-encoded string, and `plain_text` a human-readable response. Parse the actual response category rather than assuming every result is an object.

<!-- MCP-CATALOG:START -->
| Tool | Response | Service/API |
|---|---|---|
| `mcp_ping` | `plain_text` | Backend: GET /health |
| `civitai_source_info` | `dict` | Backend: GET /api/civitai/source-info |
| `civitai_generate_like` | `dict` | Backend: POST /api/civitai/generate-like |
| `civitai_resource_acquire` | `dict` | Backend: POST /api/civitai/resources/acquire |
| `civitai_resource_status` | `dict` | Backend: GET /api/civitai/resources/status |
| `generate_image` | `json_string` | Backend: POST /api/generate/ |
| `generate_image_custom_workflow` | `json_string` | Backend: POST /api/generate/custom |
| `generate_video_wan_keyframes` | `json_string` | Backend: POST /api/generate/video/wan-keyframes |
| `generate_video_custom_workflow` | `json_string` | Backend: POST /api/generate/video/custom |
| `get_generation_status` | `json_string` | Backend: GET /api/generate/job/{job_id} |
| `cancel_job` | `json_string` | Backend: DELETE /api/generate/queue/{job_id} |
| `list_available_resources` | `json_string` | Backend: GET /api/generate/available-resources; GET /api/workflow-catalog/generation-forms |
| `deliver_generation_result_to_discord` | `dict` | DiscordBot: POST /operator/v1/deliver-result |
| `gallery_list` | `plain_text` | Backend: GET /api/gallery/ |
| `get_gallery_image` | `json_string` | Backend: GET /api/gallery/{image_id} |
| `get_gallery_artifact` | `json_string` | Backend: GET /api/gallery/artifacts/{artifact_id} |
| `gallery_rerun` | `plain_text` | Backend: POST /api/gallery/{image_id}/rerun |
| `free_comfyui_memory` | `json_string` | Direct ComfyUI: POST /free |
| `comfyui_node_provision` | `json_string` | Direct ComfyUI: GET /customnode/getmappings; POST /manager/queue/install; POST /manager/queue/start; GET /manager/queue/status |
| `comfyui_restart` | `json_string` | Direct ComfyUI: POST /manager/reboot |
| `create_style_preset` | `json_string` | Backend: POST /api/style-presets/ |
| `list_style_presets` | `json_string` | Backend: GET /api/style-presets/ |
| `get_style_preset` | `json_string` | Backend: GET /api/style-presets/{preset_id} |
| `compose_style_preset` | `json_string` | Backend: POST /api/style-presets/{preset_id}/compose |
| `save_successful_workflow_as_style_preset` | `json_string` | Backend: POST /api/style-presets/{preset_id}/workflow/save |
| `test_saved_style_preset_workflow` | `json_string` | Backend: POST /api/style-presets/{preset_id}/workflow/test |
| `prompt_library_search` | `dict` | Backend: GET /api/prompt-library/catalog; GET /api/prompt-library/categories/{polarity}/{category_id}; GET /api/prompt-library/search |
| `prompt_library_save` | `dict` | Backend: PUT /api/prompt-library/categories/{polarity}/{category_id}; PUT /api/prompt-library/categories/{polarity}/{category_id}/entries/{entry_id}; PUT /api/prompt-library/combinations/{combination_id} |
| `prompt_library_compose` | `dict` | Backend: POST /api/prompt-library/compose |
| `prompt_library_archive` | `dict` | Backend: POST /api/prompt-library/archive |
| `prompt_library_restore` | `dict` | Backend: POST /api/prompt-library/restore |
| `caption_image` | `dict` | Backend: POST /api/lora-docs/caption-llm/{image_path} |
| `lora_training_decision_preflight` | `dict` | Backend: POST /api/lora-train/datasets/training-decision-preflight |
| `lora_train_start` | `dict` | Backend: POST /api/lora-train/start |
| `lora_train_job_status` | `dict` | Backend: GET /api/lora-train/jobs/{job_id} |
| `lora_train_logs` | `dict` | Backend: GET /api/lora-train/jobs/{job_id}/logs |
| `lora_train_cancel` | `dict` | Backend: POST /api/lora-train/jobs/{job_id}/cancel |
| `lora_dataset_list` | `dict` | Backend: GET /api/lora-train/datasets |
| `lora_dataset_inspect` | `dict` | Backend: GET /api/lora-train/datasets/{folder}/agent-inspect |
| `lora_train_smoke_test` | `dict` | Backend: POST /api/lora-train/jobs/{job_id}/smoke-test |
<!-- MCP-CATALOG:END -->

LoRA training has **not completed end-to-end acceptance**. See [Training status](training-status.md) for evidence and gaps; listed tools do not authorize automated training.

## Everyday usage

- Inspect local resources with `list_available_resources`, then call `generate_image` with compatible resources and the desired prompt.
- For a Civitai image recipe, inspect `civitai_source_info` before `civitai_generate_like`. Resource acquisition can download files; use it only when authorized. Poll `civitai_resource_status` for acquisition progress and `get_generation_status` for the generation job.
- Use `gallery_list` and `get_gallery_image` to inspect recorded output; `gallery_rerun` queues another generation from recorded parameters.
- `compose_style_preset` composes a generation payload; it does not itself submit a job. Submit the returned payload through `generate_image`.
- Call `save_successful_workflow_as_style_preset` only after the user explicitly asks to save an already successful result. Send the compact source locator and keywords, not a reconstructed graph. `test_saved_style_preset_workflow` queues the Backend-owned saved graph verbatim.
- Prompt Library tools search, save, compose, archive, and restore library resources. Archiving/restoring/editing are mutations, not lookup operations.

For custom generation, use a known-good `backend/workflows/*.json` template or successful recorded graph. `generate_video_custom_workflow` requires a supplied graph, not prose-to-graph synthesis. `generate_video_wan_keyframes` uses a Backend-owned graph with required nodes/resources. Poll `get_generation_status`; retrieve video `artifacts[]` with `get_gallery_artifact` rather than assuming image-only output.

Where exposed, `execution_target` accepts `local`/`worker`; check live schemas and [Worker requirements](windows-worker.md). Selection does not prove readiness or resources. Do not retry failed Worker requests locally without authorization.

## Troubleshooting and current API contract

- **Server fails to start:** inspect MCP client logs, the wrapper path, Python environment dependencies, and `uv` availability. Do not assume installing the package proves all imports work.
- **Ping fails:** check the actual Backend URL and service readiness. A container loopback URL is not necessarily reachable from the MCP host.
- **Missing/stale tools:** reload the client/server and compare its advertised schemas with the source catalog. Removed low-level workflow/alias helpers are not MCP tools merely because a Backend route exists.
- **Delivery path fails:** compare `MCP_GALLERY_DIR` with the real host mount; never substitute a container-only path.
- **Direct ComfyUI operation fails:** check its separately configured URL and, for Manager operations, the Manager API. Backend health is not a test of this connection.

REST schemas: running Backend `/docs` or `/openapi.json` (Compose default: <http://127.0.0.1:8001/openapi.json>). Offline: `backend/app/api/`, request/response schemas and `backend/app/main.py` router registration. Use source/live contracts, not historical API notes.
