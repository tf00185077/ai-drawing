## Context

Existing MCP tools let an agent list datasets, inspect file pairs, run caption assessment, validate datasets, and start or monitor training. After metadata profiles exist, agents need a smaller number of reliable inspection calls that include profile state and explicit profile update paths. This prevents hidden local edits and gives Hermes a repeatable pre-training review workflow.

## Goals / Non-Goals

**Goals:**

- Provide backend operations for profile get, update, and validate.
- Expose profile operations through structured MCP results.
- Provide an agent inspection summary that composes existing dataset inspection, profile validation, and caption suitability signals.
- Use hashes to prevent stale metadata updates.

**Non-Goals:**

- Do not implement caption curation edits.
- Do not implement training decision verdicts.
- Do not start training from inspection or metadata updates.

## Decisions

1. **Keep profile update explicit.**
   - Add dedicated metadata get/update/validate operations instead of hiding writes inside dataset inspect.
   - Alternative considered: auto-create metadata during inspect. Rejected because inspection must be side-effect free.

2. **Use optimistic profile-hash checks for writes.**
   - Metadata update accepts an optional expected `profile_hash`.
   - If the file changed, return a conflict with the current hash so the agent can re-read before writing.

3. **Compose inspection instead of replacing existing tools.**
   - Existing `lora_dataset_list`, `lora_dataset_inspect`, and `lora_dataset_caption_assess` remain valid.
   - New agent inspection output bundles their important signals for pre-training review.

4. **Return structured MCP payloads only.**
   - All MCP tools follow the archived `ok`, `tool`, payload/error shape.
   - `needs_review` or invalid profile states are payload outcomes, not transport failures unless the backend request itself fails.

## Risks / Trade-offs

- Composite inspection can become large -> include summaries by default and allow file-level detail through existing inspect.
- Metadata writes can race with manual edits -> require expected profile hashes for updates that overwrite an existing profile.
- Agents may treat warnings as approval -> include severity and suggested next action fields.

## Migration Plan

- Additive API and MCP tools only.
- Existing dataset tools remain compatible.
- Rollback removes new metadata endpoints/tools and the composite inspection tool.

## Open Questions

- None. Curation and training decisions are intentionally deferred to later changes.
