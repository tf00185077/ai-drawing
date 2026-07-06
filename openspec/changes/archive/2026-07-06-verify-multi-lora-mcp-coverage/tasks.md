## 1. Backend Audit and Coverage

- [x] 1.1 Audit `app/core/workflow.py`, generation schemas/API/queue params, and style preset provider/API for the formal multi-LoRA requirements.
- [x] 1.2 Add backend tests for any missing generation or style preset API `loras` preservation paths.
- [x] 1.3 Patch backend implementation only if the new tests expose a real behavior gap.

## 2. MCP Tool Coverage

- [x] 2.1 Add MCP tests proving `generate_image_custom_workflow` forwards ordered `loras` to the backend.
- [x] 2.2 Add MCP tests proving style preset create/detail/list/compose paths preserve or return ordered `loras`.
- [x] 2.3 Add MCP catalog schema tests proving supported generation and style preset tools expose `loras` input fields.
- [x] 2.4 Patch MCP implementation only if the new tests expose a real behavior gap.

## 3. Verification Evidence

- [x] 3.1 Run the focused backend multi-LoRA/style-preset/generate API tests.
- [x] 3.2 Run the full backend test suite.
- [x] 3.3 Run the focused MCP tool/style-preset/catalog tests.
- [x] 3.4 Run the full MCP test suite.
- [x] 3.5 Run OpenSpec validation and `git diff --check`.
