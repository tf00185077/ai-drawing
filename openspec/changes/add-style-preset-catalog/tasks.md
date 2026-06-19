## 1. Catalog data model and provider

- [x] 1.1 Add a sample-safe runtime catalog file at `backend/style_presets/catalog.json` with an empty or placeholder preset list.
- [x] 1.2 Add typed backend models for style presets, profiles, resource references, default params, validation results, and compose results.
- [x] 1.3 Implement a file-backed style preset provider with `list_presets`, `get_preset`, `validate_presets`, and `compose` operations.
- [x] 1.4 Implement deterministic prompt composition using preset base prompt, profile prompt prefix/suffix, user `content_prompt`, and negative prompt merging.
- [x] 1.5 Add unit tests for catalog loading, unknown preset/profile errors, prompt composition order, and profile param overrides.

## 2. Backend API and generation payload support

- [x] 2.1 Add API schemas for preset list, preset detail, validation, and compose responses.
- [x] 2.2 Add backend endpoints to list presets, get a preset, validate presets, and compose a preset with `content_prompt`.
- [x] 2.3 Extend normal `GenerateRequest` and `trigger_generate` to accept optional `diffusion_model`, `text_encoder`, and `vae` fields and forward them to the queue.
- [x] 2.4 Add API tests for preset list/detail/validation/compose and for forwarding diffusion component fields through the normal generate endpoint.

## 3. MCP tools

- [x] 3.1 Add MCP tools for `list_style_presets`, `get_style_preset`, `validate_style_presets`, and `compose_style_preset`.
- [x] 3.2 Ensure MCP tools return stable agent-friendly JSON with `ok`, `tool`, result payloads, structured errors, and `next` instructions.
- [x] 3.3 Extend the existing `generate_image` MCP tool to accept optional `diffusion_model`, `text_encoder`, and `vae` and include them only when provided.
- [x] 3.4 Add MCP tests for preset tool success/error responses, missing resource diagnostics, and composed payload forwarding guidance.

## 4. Agent guidance and documentation

- [x] 4.1 Update MCP README/tool docs to describe preset mode, manual resource mode, and the compose-then-generate flow.
- [x] 4.2 Update `docs/api-contract.md` with the style preset endpoints and optional diffusion fields on normal generation.
- [x] 4.3 Update the relevant OpenClaw/MCP drawing SOP so the agent uses presets when specified and only asks for a new recipe when no preset exists.
- [x] 4.4 Update `docs/PROGRESS.md` when implementation is complete.

## 5. Verification

- [x] 5.1 Run backend tests covering the new provider/API/generation fields.
- [x] 5.2 Run MCP server tests covering the new tools and `generate_image` signature.
- [x] 5.3 Run an end-to-end dry path: compose a preset into a generation payload, then submit that payload through `generate_image` using mocked or local backend resources.
