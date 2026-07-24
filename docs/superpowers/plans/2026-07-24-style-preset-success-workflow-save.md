# Successful Style Preset Workflow Save Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Save an explicitly selected, already-successful generation graph as a keyword-sanitized raw ComfyUI API workflow for a style preset and retest that exact saved graph.

**Architecture:** A backend service resolves short Gallery/job locators, deep-copies recorded `workflow_json`, replaces only sampler-linked positive/negative text encoders, and atomically writes a conventional raw graph file. FastAPI owns save/get/test stateful operations; MCP tools are thin intent clients. A dedicated queue method submits server-owned saved graphs verbatim instead of reusing the prompt-mutating custom workflow route.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, pytest, Python MCP SDK, ComfyUI REST/WebSocket queue.

## Global Constraints

- Invoke save only after successful generation and explicit user request.
- LLM supplies compact positive and negative keywords; backend performs no semantic inference.
- Preserve every graph value except the targeted conditioning text.
- Store raw ComfyUI API JSON only; no hashes, snapshot ids, manifests, or full round prompts.
- Keep Civitai Source Alias, Discord, automatic save, and batch backfill out of scope.
- Keep the implementation generic across all style presets; do not encode Niji, Anima, checkpoint-family, template-name, fixed node-id, or LoRA-count assumptions.
- Follow RED → GREEN → REFACTOR and do not commit, push, or archive; Hermes verifies and closes the branch.

---

### Task 1: Successful-workflow sanitizer service

**Files:**
- Create: `backend/app/schemas/style_preset_workflows.py`
- Create: `backend/app/services/style_preset_workflows.py`
- Create: `backend/tests/test_style_preset_workflow_save.py`

**Interfaces:**
- Consumes: SQLAlchemy `Session`, `GeneratedImage`/`GeneratedArtifact`, `DirStylePresetProvider`.
- Produces: `normalize_keywords(value)`, `resolve_successful_workflow(session, source)`, `sanitize_workflow_prompts(workflow, positive, negative)`, and `save_successful_workflow(...)`.

- [ ] Write failing tests for locator, normalization, polarity traversal, ambiguity, no-mutation, zero-write errors, and at least two structurally different model-family graph fixtures.
- [ ] Run `PYTHONPATH=. pytest backend/tests/test_style_preset_workflow_save.py -q` and confirm failures are caused by missing interfaces.
- [ ] Implement only the service/schema behavior specified in the OpenSpec design.
- [ ] Rerun the focused test and keep it green before refactoring.

### Task 2: Atomic storage and API

**Files:**
- Modify: `backend/app/api/style_presets.py`
- Modify: `backend/app/core/style_presets.py` only if a provider-root accessor is required.
- Test: `backend/tests/test_style_preset_workflow_save.py`

**Interfaces:**
- Produces: `POST /api/style-presets/{preset_id}/workflow/save` and raw `GET /api/style-presets/{preset_id}/workflow?profile=...`.

- [ ] Add failing endpoint tests covering save, raw read, conventional paths, atomic replace, and structured errors.
- [ ] Run the exact endpoint test selectors and confirm RED.
- [ ] Implement temporary-write → parse-back → `os.replace`, plus thin routes.
- [ ] Rerun focused style-preset tests and ensure existing compose/create behavior remains green.

### Task 3: Verbatim retest queue path

**Files:**
- Modify: `backend/app/core/queue.py`
- Modify: `backend/app/api/style_presets.py`
- Create: `backend/tests/test_style_preset_workflow_retest.py`

**Interfaces:**
- Produces: a queue method accepting a server-owned graph plus recording metadata without calling `apply_params`, and `POST /api/style-presets/{preset_id}/workflow/test`.

- [ ] Add a failing spy test asserting the graph handed to ComfyUI is deeply equal to the saved graph and `apply_params` is not called.
- [ ] Add failing route tests for queued success and missing saved graph.
- [ ] Implement the narrow queue/route path while reusing existing status/completion/node-error lifecycle.
- [ ] Rerun queue, generation, recording, Gallery, and style-preset tests.

### Task 4: MCP intent tools and catalog

**Files:**
- Modify: `mcp-server/mcp_server/tools/style_presets.py`
- Modify: `mcp-server/mcp_server/tool_catalog.py`
- Modify: `docs/mcp-setup.md`
- Modify: `mcp-server/tests/test_style_presets.py`
- Modify: `mcp-server/tests/test_tool_catalog.py`

**Interfaces:**
- Produces: `save_successful_workflow_as_style_preset(...)` and `test_saved_style_preset_workflow(...)` returning parseable JSON strings.

- [ ] Add failing request-body/response/error tests and catalog-name assertions.
- [ ] Confirm focused MCP tests fail for missing tools.
- [ ] Implement thin backend calls; do not parse or transfer workflow JSON in MCP.
- [ ] Rerun focused MCP tests and inspect tool docstrings for the explicit-save-only rule.

### Task 5: Verification and handoff

**Files:**
- Modify: `docs/PROGRESS.md`
- Modify: `openspec/changes/save-successful-style-preset-workflow/tasks.md`

- [ ] Run complete backend and MCP suites from their own environments.
- [ ] Run strict target/all OpenSpec validation and `git diff --check`.
- [ ] Update progress and task checkboxes only for evidence actually obtained.
- [ ] If live services are available, use a disposable target for one exact saved-graph retest, clean up, and record the job/artifact result; otherwise leave the live task unchecked with its blocker.
- [ ] Return a concise implementation report with changed files, test totals, live-smoke status, and remaining risks. Do not commit, push, archive, or modify another worktree.
