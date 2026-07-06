## Context

The current LoRA workflow can discover datasets, inspect image/caption pairs, validate training starts, and assess caption suitability. Those operations infer intent from files and request parameters. For agent-guided work, intent must be durable and local to the dataset so an agent can tell whether the folder is a character, style, object, or other dataset, which trigger token is expected, which tags are protected, and whether captions can be normalized.

## Goals / Non-Goals

**Goals:**

- Introduce `.lora-dataset.json` as the canonical dataset-local metadata profile.
- Provide conservative defaults when the file is absent.
- Make malformed profiles visible as structured validation warnings or errors.
- Keep `auto_train` defaulted to `false` and non-operative for training starts.

**Non-Goals:**

- Do not add automatic LoRA training.
- Do not replace the archived caption suitability assessment.
- Do not implement curation edits, MCP metadata mutation, or training decision preflight in this change.

## Decisions

1. **Use a dataset-local JSON file.**
   - Store `.lora-dataset.json` in the dataset folder under `lora_train_dir`.
   - Alternative considered: database-only metadata. Rejected because agents and humans need portable dataset folders and simple handoff inspection.

2. **Default missing profiles instead of failing discovery.**
   - Missing metadata yields a synthetic profile with `auto_train=false`, unknown dataset type, empty protected/remove tag lists, and no trigger token unless one is detected by existing logic.
   - This keeps current datasets usable while encouraging profile creation.

3. **Separate profile validity from caption suitability.**
   - Profile validation reports schema and policy issues.
   - Caption suitability assessment remains the archived local deterministic metric service.
   - Dataset inspection can show both sets of signals side by side.

4. **Hash metadata separately from image/caption data.**
   - Return `profile_hash` for the metadata file and keep the existing `dataset_hash` for dataset content.
   - Later changes can use both hashes for safe updates and training decisions.

## Risks / Trade-offs

- Malformed JSON could block agent interpretation -> return structured validation errors while preserving raw dataset discovery.
- Humans might assume `auto_train=true` is a trigger -> this change defines `auto_train` as metadata only and defaults it to `false`.
- Profile schema could grow quickly -> start with only fields needed for LoRA dataset identity, caption policy, and agent decisions.

## Migration Plan

- Existing datasets need no migration because missing profiles use defaults.
- New profiles can be added one dataset at a time.
- Rollback removes metadata parsing and the additive response fields without changing caption or training files.

## Open Questions

- None for this scope. Model-family-specific training parameter defaults are handled by the later training decision change.
