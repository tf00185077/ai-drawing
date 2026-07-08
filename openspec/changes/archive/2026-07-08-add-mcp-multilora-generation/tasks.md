## 1. Discovery
- [x] Inspect backend generate API schemas and queue/template LoRA injection behavior.
- [x] Inspect MCP tool schemas and HTTP client methods for generate/cancel.
- [x] Identify exact tests covering multi-LoRA forwarding and cancel.

## 2. Implementation
- [x] Add/confirm typed `loras` support in backend request models if needed.
- [x] Expose `loras` on MCP `generate_image` and `generate_image_custom_workflow` tools.
- [x] Ensure MCP forwards `loras` to backend without dropping legacy `lora` fields.
- [x] Fix `cancel_job` HTTP client/delete/cancel path.
- [x] Preserve single-LoRA backwards compatibility.

## 3. Tests
- [x] Add/update backend tests for ordered multi-LoRA preservation.
- [x] Add/update MCP tests for tool schema/forwarding.
- [x] Add/update MCP cancel job test.
- [x] Run targeted backend tests.
- [x] Run targeted MCP tests.
- [x] Run `openspec validate add-mcp-multilora-generation --strict`.
- [x] Run `openspec validate --all`.

## 4. Live verification
- [x] Use local MCP/backend to compose or submit a multi-LoRA generation payload.
- [x] Verify the submitted ComfyUI workflow keeps distinct LoRA names/strengths instead of overwriting all nodes with one LoRA.
- [x] Verify MCP cancel path no longer raises missing `delete` method.
