## 1. Profile Schema

- [x] 1.1 Add backend schema tests for missing, valid, malformed, and unsupported `.lora-dataset.json` profiles.
- [x] 1.2 Implement dataset profile parsing with conservative defaults, supported enum values, `profile_hash`, and structured validation messages.
- [x] 1.3 Ensure `auto_train` defaults to `false` and is treated as descriptive metadata only.

## 2. Dataset Discovery Integration

- [x] 2.1 Add dataset list/inspect tests proving profile summary fields are returned without changing existing image/caption counts or dataset hash behavior.
- [x] 2.2 Wire profile summary and validation output into existing dataset discovery and inspection responses.
- [x] 2.3 Preserve existing caption suitability assessment behavior and do not enqueue training from profile parsing.

## 3. Verification

- [x] 3.1 Run focused backend tests for LoRA dataset profile parsing and discovery integration.
- [x] 3.2 Run `openspec validate add-lora-dataset-metadata-profiles` and `git diff --check`.
