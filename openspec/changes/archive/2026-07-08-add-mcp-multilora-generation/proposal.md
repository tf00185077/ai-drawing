# Add multi-LoRA MCP generation support

## Why
Style presets can compose generation payloads with an ordered `loras` array, but the MCP `generate_image` tool schema currently exposes only legacy single-LoRA fields. When agents pass a multi-LoRA workflow template with only `lora/lora_strength`, the backend can overwrite all LoRA loader nodes with the same LoRA, breaking presets such as `niji-moonlit-semi-real-anima`.

The MCP `cancel_job` tool also fails because its backend HTTP client lacks the DELETE/cancel request path it tries to use.

## What Changes
- Expose ordered `loras` payload support through MCP image generation tools.
- Preserve backwards compatibility for single `lora/lora_strength` callers.
- Ensure multi-LoRA template/workflow submission preserves distinct LoRA nodes and strengths.
- Fix MCP cancel job backend client/delete path.
- Add backend and MCP tests plus a live smoke verification path using the local MCP/backend.

## Impact
- Agents can call `compose_style_preset` then pass the returned generation payload to `generate_image` without losing multi-LoRA information.
- Existing single-LoRA/image workflows continue working.
- Pending job cancellation works through MCP.
