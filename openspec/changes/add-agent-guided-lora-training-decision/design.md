## Context

The archived workflow can validate datasets and start training explicitly. Metadata, inspection, and curation changes add the missing inputs for agent judgment. This change adds a deterministic decision layer that tells Hermes whether the dataset is ready to train, needs human review, or must not be trained yet. The layer is intentionally non-executing.

## Goals / Non-Goals

**Goals:**

- Produce a deterministic decision from local metadata, caption assessment, validation, and curation status.
- Explain reasons and next actions in agent-readable form.
- Suggest safe initial training parameters based on dataset type, image count, model family, and caption profile.
- Expose the preflight through MCP.

**Non-Goals:**

- Do not start training automatically.
- Do not replace backend validation that still blocks unsafe start requests.
- Do not tune Kohya parameters with an external LLM.
- Do not implement training monitoring or final handoff reporting in this change.

## Decisions

1. **Use three explicit decisions.**
   - `train` means no blocking issues were found and suggested parameters are available.
   - `needs_review` means an agent or user must resolve warnings, inspect outliers, or approve curation/manual-caption choices.
   - `do_not_train` means blocking issues exist, such as missing captions, invalid metadata, stale hashes, or insufficient dataset size.

2. **Keep decision preflight side-effect free.**
   - The preflight reads metadata, assessment, validation, and curation status only.
   - Alternative considered: optionally enqueue training when decision is `train`. Rejected because CTY requires explicit user-requested training only.

3. **Separate suggested params from submitted params.**
   - Preflight returns suggested parameters and rationale.
   - A later explicit `lora_train_start` request must still provide or accept those parameters and expected hashes.

4. **Make next actions actionable.**
   - Results include recommended calls such as inspect metadata, run curation dry-run, apply reviewed curation, add captions, or ask user for approval.

## Risks / Trade-offs

- Conservative decisions can delay training -> expose reasons and suggested override context for Hermes to discuss with the user.
- Suggested parameters can be too generic -> scope them to safe defaults and known model family/profile fields.
- Dataset state can change after decision -> return dataset/profile hashes and require training start to validate hashes again.

## Migration Plan

- Additive API and MCP preflight only.
- Existing validation and explicit training start remain authoritative.
- Rollback removes the preflight endpoint/tool without changing training execution.

## Open Questions

- None. Handoff reporting and monitoring are handled in the next change.
