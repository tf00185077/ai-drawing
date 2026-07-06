# Design: MCP tool catalog exposure audit

## Current Findings

The MCP server implementation currently has tool functions in these modules:

- `character_style_tools.py`
- `comfyui.py`
- `gallery.py`
- `generate.py`
- `lora_train.py`
- `style_presets.py`
- `workflow_catalog.py`

Runtime inspection shows a mixture of return contracts:

- New LoRA workflow tools return `dict[str, Any]`.
- Many older tools return `str`, usually JSON text or human-readable text.
- Some tools exist in code but are not visible in the Hermes MCP tool surface available in this session, notably `generate_video_custom_workflow`.

The backend routes include capabilities that are partially exposed through MCP and partially omitted. Some omissions may be intentional, but the project lacks a canonical catalog that says which backend operations are intended for agents.

## Approach

### 1. Establish an intended MCP catalog

Create a test fixture or source-of-truth list for intended tools. It should include each tool's:

- name
- module/function
- expected return shape category (`dict`, JSON string transitional, or plain text transitional)
- backend endpoint(s), if any
- whether it is required to be visible to external MCP clients
- documentation location

### 2. Registration and visibility tests

Add tests that import the MCP server in the same way clients do and verify intended tools are registered. Add lower-level tests that every exported tool function has coverage and a documented contract.

For the Hermes-visible mismatch, first determine whether the issue is mcp-server registration, generated schema, Hermes tool catalog refresh, or current session toolset filtering. The fix should target the actual layer and document any session-refresh requirement.

### 3. LoRA resource exposure

Audit all payloads that mention LoRA resources:

- `list_available_resources` response `loras`
- style preset detail and composition payloads
- `generate_image` and custom workflow payloads
- multi-LoRA support change interactions
- video workflows that depend on Wan LoRAs
- LoRA training registration output

The result should consistently expose LoRA filenames and ordered multi-LoRA entries where supported. If a caller supplies `loras`, it should not be silently ignored or downgraded to a single `lora` unless explicitly documented and tested.

### 4. Response shape policy

Prefer structured JSON dictionaries for agent-facing tools. Where existing tools still return strings for compatibility, tests must assert that the string is parseable JSON for machine-facing tools, or docs must mark it as legacy human-readable output.

New tools should not return opaque human-readable strings.

### 5. Runtime smoke

After tests pass, run low-load live checks:

- `mcp_ping`
- `list_available_resources` includes non-empty or explicitly empty `loras` with correct type
- `generate_video_custom_workflow` is visible and callable through the real MCP surface or its registration test proves why the current session needs refresh
- one representative LoRA/resource tool path
- one representative gallery/artifact tool path

Heavy generation/training jobs should not be started without explicit approval.

## Risks

- Changing return types can break existing callers. Use transitional compatibility or versioned behavior if needed.
- Hermes may cache tool schemas per session; a server-side fix may require a new session/reload to appear in Hermes's tool list.
- Multi-LoRA support is an active separate OpenSpec change; this change should coordinate rather than duplicate it.
