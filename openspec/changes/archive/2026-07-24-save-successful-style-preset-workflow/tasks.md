## 1. Backend save service

- [x] 1.1 Add RED tests for source locator parsing, successful Gallery image/artifact/job resolution, unsuccessful or graph-less source rejection, and zero-write failures.
- [x] 1.2 Add RED tests for string/list keyword normalization, positive-required behavior, optional empty negative keywords, and no full-prompt leakage.
- [x] 1.3 Add RED tests that trace sampler conditioning links, replace only reachable `CLIPTextEncode.inputs.text`, preserve every other value, reject shared-polarity ambiguity, and do not mutate the source object.
- [x] 1.3a Add RED genericity fixtures for at least one traditional checkpoint graph and one diffusion-family or multi-loader graph with different node ids/order; prohibit preset-id, Niji/Anima, template-name, and fixed loader-count branches.
- [x] 1.4 Implement the minimal backend schema/service needed to pass the save-service tests.
- [x] 1.5 Add RED privacy tests for orphan text encoders, linked primitive/string prompt carriers, metadata or other exact prompt copies, and prove the persisted raw graph contains neither the source record's full positive prompt nor its full negative prompt; implement fail-closed rejection when complete prompt removal cannot be proven without changing non-conditioning graph semantics.

## 2. Filesystem and HTTP contract

- [x] 2.1 Add RED tests for known preset/profile validation, conventional `__base__`/profile paths, parse-back checks, atomic replacement, and no caller-controlled path.
- [x] 2.2 Implement atomic raw `.api.json` persistence under `style_presets/agent/workflows/` without metadata envelopes, hashes, or snapshot ids.
- [x] 2.3 Add RED API tests for `POST .../workflow/save` and raw `GET .../workflow`, including structured repairable errors.
- [x] 2.4 Implement the backend routes and response schemas while leaving declarative preset recipe prompts unchanged.

## 3. Verbatim retest

- [x] 3.1 Add RED queue tests proving the exact saved graph is submitted without `apply_params`, default prompt, seed, sampler, dimensions, or resource mutation.
- [x] 3.2 Implement the narrow server-owned verbatim queue method using the existing job/completion/error lifecycle.
- [x] 3.3 Add RED API tests for `POST .../workflow/test`, missing saved graph behavior, and queued job response.
- [x] 3.4 Implement the retest route without changing `generate_image_custom_workflow` behavior.
- [x] 3.5 Add RED queue tests for non-JSON HTTP errors, missing `prompt_id`, and unexpected submit exceptions; ensure every submit failure releases `_running`, records a terminal failed job, and allows the next pending job to proceed.

## 4. MCP surface

- [x] 4.1 Add RED MCP tests for loose source/keyword forwarding and stable success/error JSON for `save_successful_workflow_as_style_preset`.
- [x] 4.2 Implement the save MCP tool as a thin backend client with an explicit-user-request-only docstring.
- [x] 4.3 Add RED MCP tests for `test_saved_style_preset_workflow`, queued job response, and polling instruction; implement the thin client.
- [x] 4.4 Register both tools in the audited catalog and update MCP documentation/catalog tests.

## 5. Verification and product evidence

- [x] 5.1 Run focused backend tests for style presets, Gallery resolution, queue verbatim submission, and API routes.
- [x] 5.2 Run focused MCP style-preset and tool-catalog tests.
- [x] 5.3 Run the complete backend and MCP test suites from their correct environments.
- [x] 5.4 Run `openspec validate save-successful-style-preset-workflow --strict`, `openspec validate --all --strict`, and `git diff --check`.
- [x] 5.5 Update `docs/PROGRESS.md` with the implemented capability and exact deterministic test evidence.
- [x] 5.6 Using a reversible/disposable target, save one already-successful real image workflow with compact positive/negative keywords, retrieve the raw graph, submit it through the verbatim retest route, and confirm successful completion without visually inspecting, ranking, or regenerating the result. Clean up disposable artifacts and record exact evidence. If the live backend/ComfyUI is unavailable, leave this task unchecked with the precise environment blocker.
