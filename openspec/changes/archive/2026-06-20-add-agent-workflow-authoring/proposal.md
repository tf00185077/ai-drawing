## Why

Today the agent can only assemble a workflow freely through `generate_image_custom_workflow`, but it has no reliable grounding for doing so: it must guess the ComfyUI graph shape from training memory or fetch whole template JSON, and there is no way to know which nodes the live ComfyUI actually has. The default path therefore leans on human-authored fixed templates — every new variant requires a person to hand-craft a template first, making the human the bottleneck and wasting the agent's ability. We want to shift from "supplying templates" to "supplying the agent capability + guardrails" so the agent can author workflows on demand, and so the template library grows itself from verified successes instead of from manual authoring.

## What Changes

- Add a **machine-readable capability manifest** to each workflow template: a controlled-vocabulary set of binary/discrete capability tags (`modality`, `conditioning`, `io`, `model_family`). A lightweight index lets the agent judge a template without expanding its full JSON. Free-text descriptions are human-only and never drive the decision.
- Add a **deterministic binary reuse match**: "can an existing template solve this need?" = the set test *template-capabilities ⊇ required-capabilities*. Match → apply via the existing template-name path; miss → self-author. Matching is intentionally strict (a false miss costs only a rebuild; a false match risks a wrong image).
- Add **single-point ComfyUI node-schema query** tools (`search_nodes` + `get_node_schema`) backed by ComfyUI `/object_info`, so the agent learns the live instance's actual nodes and their input/output schema instead of dumping the whole catalog.
- Add **ComfyUI validation-error forwarding** to the custom-workflow path: submit to ComfyUI and relay its `node_errors` as a structured, agent-readable error for self-correction and retry (no self-built validator).
- Add **template backfill (self-extending library)**: only after ComfyUI actually produces an image and recording succeeds, the verified workflow shape is written back. Backfill uses the capability tag-set as a dedup key — existing key → no new entry (broken originals are superseded with a new version, never edited in place); no match → add a new entry tagged and filed under its `modality` family. Shared templates are never mutated in place; changes are versioned (deprecate old). Two graphs are never auto-merged. A "similar" template may only be used as a build-time scaffold; its result is still saved as its own entry.
- Add a **controlled-vocabulary registry** governing how new capability tags are introduced, plus an optional periodic consolidation step to retire deprecated entries.

Preserved (non-goals): `generate_image` (template-name fast path) and the `style-preset-catalog` mechanism are unchanged. The workflow-template library (graph *shapes*) and the style-preset library (resource + prompt *recipes*) remain two independent libraries; backfill touches only templates. The disabled `generate_image_from_description` / `suggest_workflow_from_description` tools are out of scope.

## Capabilities

### New Capabilities
- `comfyui-node-schema`: Single-point query of the live ComfyUI node catalog (`/object_info`) via `search_nodes` and `get_node_schema`, returning per-node input/output specs so the agent can construct valid workflows grounded in the actual instance.
- `workflow-template-catalog`: Capability manifests on templates (controlled-vocabulary binary tags), a lightweight index query, deterministic binary reuse matching (superset test), and self-extending backfill (verified-success promotion gate, capability-key dedup, modality-family filing, version-on-change without in-place mutation, optional consolidation).

### Modified Capabilities
- `custom-workflow-generation`: Add a requirement that the custom-workflow path forwards ComfyUI `/prompt` validation `node_errors` to the caller as a structured, agent-parseable error suitable for self-correction, rather than failing opaquely.

## Impact

- **MCP server** (`mcp-server/mcp_server/tools/`): new `comfyui` node-schema tools (`search_nodes`, `get_node_schema`); new template-catalog tools (index query / capability match / backfill); `generate_image_custom_workflow` result shape gains structured validation errors. Tool docstrings/guidance updated so the agent's default is "match-then-build", with self-authoring as the primary path for variants.
- **Backend** (`backend/app/api/`, `backend/app/core/`): new endpoints proxying ComfyUI `/object_info`; template manifest/index storage and read/validate/backfill logic; custom-workflow submission surfaces ComfyUI `node_errors` instead of swallowing them.
- **Template storage** (`backend/workflows/`): each template gains an associated capability manifest (sidecar or index entry); new versioned/family layout for backfilled templates.
- **ComfyUI dependency**: relies on `/object_info` and `/prompt` validation responses; node-schema responses may be cached and invalidated on ComfyUI restart / custom-node changes.
- **Out of scope / unchanged**: `generate_image` template-name path, `style-preset-catalog`, gallery rerun, LoRA training.
