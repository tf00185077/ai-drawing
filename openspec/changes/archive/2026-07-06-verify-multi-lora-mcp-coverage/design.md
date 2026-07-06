## Context

The archived `add-multi-lora-support` change already added formal requirements to `custom-workflow-generation` and `style-preset-catalog`. The current task is a cross-module audit of the implementation and tests, with special attention to MCP server behavior. The work must preserve single-LoRA compatibility and must not commit, push, archive, or touch Hermes/Louise sentinel files.

## Goals / Non-Goals

**Goals:**

- Prove backend `apply_params` maps ordered `loras` entries to existing LoRA loader nodes positionally.
- Prove generation schemas/API/queue params preserve `loras` while keeping single `lora` behavior.
- Prove style preset list/detail/create/compose paths preserve and emit ordered `loras`.
- Prove MCP `generate_image`, `generate_image_custom_workflow`, `create_style_preset`, and `compose_style_preset` forward or return `loras`.
- Prove MCP tool input schemas expose `loras` on the relevant generation and style preset tools.

**Non-Goals:**

- No new user-facing multi-LoRA requirements beyond the archived formal specs.
- No graph synthesis, automatic insertion of LoRA loader nodes, database migration, commit, push, or archive.

## Decisions

- Treat this as a verification change, not a requirements change. The authoritative behavioral requirements remain in the main specs. Any delta specs in this change exist only to make the spec-driven workflow apply-ready and should be skipped during archive unless Hermes chooses otherwise.
- Prefer tests over implementation churn. If the audit finds behavior already implemented, add regression tests and leave production code unchanged. If a test exposes a real gap, patch only the smallest affected module.
- Keep tests behavior-oriented. MCP tests should inspect the actual backend payload submitted by mocked clients and the registered FastMCP schemas, not only function signatures.

## Risks / Trade-offs

- Verification-only delta specs could pollute formal specs if archived normally -> Hermes should archive with `--skip-specs` if no product requirement changed.
- FastMCP schema details may differ across library versions -> tests should assert stable field presence, not exact full schemas.
- Existing tests may already cover part of the behavior -> new tests should target uncovered MCP/API edges to avoid redundant broad assertions.
