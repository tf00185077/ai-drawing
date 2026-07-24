# Why

Style presets currently persist only declarative recipes. The concrete ComfyUI API graph is assembled at generation time, so a graph that has already produced a successful image cannot be explicitly promoted into a reusable preset artifact. The owner wants a narrow save path: only after a successful generation and only after an explicit user request, an LLM supplies compact positive and negative style keywords while the backend copies the proven graph, replaces only its conditioning text, and persists a strict ComfyUI API-format JSON file.

# What Changes

- Add a backend service and HTTP API that resolve a successful Gallery image/artifact or completed generation job to its recorded `workflow_json`.
- Accept positive and negative keywords as either strings or string lists; normalize them deterministically without semantic inference.
- Trace KSampler positive and negative conditioning links and replace only the connected text semantics: direct `CLIPTextEncode.inputs.text` strings, or an exclusive identity-like Primitive/String carrier when the text input is linked. Preserve every other graph value and connection.
- Use the source Gallery record's exact nonempty prompt fields as fail-closed evidence and reject before writing if either exact full prompt remains anywhere in the complete sanitized graph.
- Atomically save the raw graph at `style_presets/agent/workflows/<preset-id>/<profile-or-__base__>.api.json` without hashes, snapshot IDs, manifests, or full round prompts.
- Add a backend read endpoint that returns the saved file as a raw ComfyUI API graph.
- Add a verbatim retest path that submits the saved graph without `apply_params`, default prompts, or any other mutation; every submit exception becomes a terminal failed job and releases the queue slot.
- Keep the capability generic across every style preset and supported ComfyUI API graph shape; do not encode Niji, Anima, checkpoint-family, LoRA-count, template-name, or node-id assumptions.
- Add MCP tools `save_successful_workflow_as_style_preset` and `test_saved_style_preset_workflow` with loose locator/keyword inputs and stable JSON responses.
- Update the audited MCP catalog, documentation, progress record, and automated tests.

# Capabilities

## Modified Capabilities

- `style-preset-catalog`: successful generated workflows can be explicitly saved and retrieved as raw ComfyUI API graphs with keyword-only prompt text.
- `mcp-tool-catalog`: exposes the explicit-save and verbatim-retest intent tools with structured responses.
- `custom-workflow-generation`: supports a server-owned verbatim submission path that does not inject the existing custom-workflow default prompt.

# Impact

- Backend: style-preset service/schema/API, Gallery record resolution, and queue submission behavior.
- MCP server: style-preset tools and audited tool catalog.
- Filesystem: new `style_presets/agent/workflows/` artifacts written only on explicit save.
- Tests/docs: focused backend and MCP suites, OpenSpec validation, tool documentation, and `docs/PROGRESS.md`.

# Non-Goals

- Discord command or modal design.
- Civitai Source Alias execution or workflow storage.
- Automatic saving after every generation.
- Batch backfill of existing presets/profiles.
- Snapshot IDs, SHA-256 verification, immutable version chains, or resource-lock manifests.
- LLM inference inside the backend or MCP server.
- Rebuilding a graph from a style-preset recipe during save.
- A Niji-specific or model-family-specific save implementation.
