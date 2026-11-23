# MCP server

The MCP server (`mcp-server/`) gives agents intent-level tools for generation, the Gallery, prompts, style presets, Civitai, LoRA training and ComfyUI maintenance. It runs over stdio and calls the Backend.

## Status

**Built:** tools for generation (image, custom workflow, video), job status and cancel, resource listing, Gallery, Civitai, style presets, Prompt Library, LoRA training, Discord delivery, ComfyUI restart/node install/memory. Image generation accepts a revision context (`request_ref`, `parent_artifact_id`, feedback), so revisions are traceable. The tool list is in `mcp-server/mcp_server/tool_catalog.py`.

**Verified in a real run:** retrieval of an existing Gallery image through MCP. A full request → generate → retrieve → revise journey has not been run.

**Gaps:**
- Responses mix plain text, JSON strings and objects.
- No tool that waits for a job to finish.
- No way to list workers or their capabilities.

Overall project state: [CURRENT.md](CURRENT.md).

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

## Tools

The authoritative list is `mcp_server/tool_catalog.py`, kept in sync with registration by `tests/test_tool_catalog.py`. Live client schemas define arguments.

<!-- MCP-CATALOG:START -->
| Group | Tools |
|---|---|
| Health | `mcp_ping` (Backend `/health` only) |
| Generation | `generate_image`, `generate_image_custom_workflow`, `generate_video_wan_keyframes`, `generate_video_custom_workflow`, `get_generation_status`, `cancel_job`, `list_available_resources` |
| Gallery | `gallery_list`, `get_gallery_image`, `get_gallery_artifact`, `gallery_rerun` |
| Prompt Library | `prompt_library_search`, `prompt_library_compose`, `prompt_library_save`, `prompt_library_archive`, `prompt_library_restore` |
| Style presets | `list_style_presets`, `get_style_preset`, `compose_style_preset`, `create_style_preset`, `save_successful_workflow_as_style_preset`, `test_saved_style_preset_workflow` |
| Civitai | `civitai_source_info`, `civitai_generate_like`, `civitai_resource_acquire`, `civitai_resource_status` |
| LoRA training | `lora_dataset_list`, `lora_dataset_inspect`, `caption_image`, `lora_training_decision_preflight`, `lora_train_start`, `lora_train_job_status`, `lora_train_logs`, `lora_train_cancel`, `lora_train_smoke_test` |
| ComfyUI (direct) | `free_comfyui_memory`, `comfyui_node_provision`, `comfyui_restart` |
| Delivery | `deliver_generation_result_to_discord` |
<!-- MCP-CATALOG:END -->

Responses are one of: a JSON object, a JSON-encoded string, or plain text (see the catalog's response column). Parse accordingly.

Direct ComfyUI tools use `MCP_COMFYUI_API_URL`, not the Backend, and always target local ComfyUI. `comfyui_node_provision` installs from ComfyUI-Manager's registry and needs the Manager API; it does not restart ComfyUI.

## Common flows

**Generate and retrieve**
1. `list_available_resources` → pick a form, model and LoRAs.
2. `generate_image` → job ID.
3. Poll `get_generation_status` until done.
4. `get_gallery_image` (images) or `get_gallery_artifact` (video).

**Revise a result** — call `generate_image` again with a revision context (`request_ref`, `brief_revision`, `parent_artifact_id`, feedback). `gallery_rerun` only replays recorded parameters.

**Use prompts** — `prompt_library_search`, then `prompt_library_compose` to get positive/negative text for `generate_image`.

**Use a style preset** — `list_style_presets` → `compose_style_preset` (returns a payload, does not submit) → `generate_image`. `test_saved_style_preset_workflow` runs a preset's saved graph as-is.

**Reproduce a Civitai image** — `civitai_source_info` → `civitai_resource_acquire` if resources are missing (poll `civitai_resource_status`) → `civitai_generate_like`.

**Custom workflows** — pass a full ComfyUI API graph, starting from `backend/workflows/*.json` or a recorded successful graph.

**Remote execution** — where a tool accepts `execution_target`, use `local` or `worker`. A failed worker job is not retried locally.

## Troubleshooting

| Problem | Check |
|---|---|
| Server does not start | Client MCP logs, wrapper path, `uv` on `PATH`, dependencies |
| `mcp_ping` fails | `MCP_BACKEND_API_URL` and that the Backend is up; container-internal URLs are not reachable from the host |
| Tools missing or stale | Reload the client; compare with `tool_catalog.py` |
| Discord delivery fails | `MCP_GALLERY_DIR` must be the real host path |
| Direct ComfyUI tool fails | `MCP_COMFYUI_API_URL`; ComfyUI-Manager installed for node/restart tools |

## Development

```bash
AI_DRAWING_TEST_ROOT="$TMPDIR/ai-drawing-mcp-tests" python -m pytest -c pytest.ini mcp-server/tests -q
```

When adding a tool: register it in `server.py`, add it to `tool_catalog.py`, and add tests.
