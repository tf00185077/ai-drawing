# Git-tracked Prompt Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist Prompt Library edits from Docker directly in the Git-tracked repository directory.

**Architecture:** Keep the existing file-backed Prompt Library provider and change only deployment path injection. Docker Compose will mount the repository's `prompt_library/` at `/workspace/prompt_library`, and launcher-generated configuration will select the same path.

**Tech Stack:** Docker Compose, Python launcher configuration, Pytest contract tests, Markdown documentation

---

### Task 1: Update deployment contract tests

**Files:**
- Modify: `scripts/tests/test_compose_contract.py`
- Modify: `scripts/tests/test_configuration.py`

- [ ] **Step 1: Change the Compose assertions**

Expect `PROMPT_LIBRARY_DIR` to default to `/workspace/prompt_library`, expect the bind source to be `./prompt_library`, and remove `/data/prompt_library` from the persistent-data mount set.

- [ ] **Step 2: Change the launcher environment assertion**

Assert that `render_env()` emits `PROMPT_LIBRARY_DIR=/workspace/prompt_library`.

- [ ] **Step 3: Run the focused tests and verify they fail**

Run: `pytest scripts/tests/test_compose_contract.py scripts/tests/test_configuration.py -q`

Expected: failures showing the old `/data/prompt_library` path.

### Task 2: Route Docker writes to the repository library

**Files:**
- Modify: `docker-compose.yml`
- Modify: `scripts/launcher/configuration.py`

- [ ] **Step 1: Change the Compose environment default**

Set the fallback value of `PROMPT_LIBRARY_DIR` to `/workspace/prompt_library`.

- [ ] **Step 2: Change the Prompt Library bind mount**

Mount `./prompt_library` at `/workspace/prompt_library` with the existing long-form writable bind syntax.

- [ ] **Step 3: Change launcher-generated configuration**

Set the generated `PROMPT_LIBRARY_DIR` value to `/workspace/prompt_library`.

- [ ] **Step 4: Run the focused tests**

Run: `pytest scripts/tests/test_compose_contract.py scripts/tests/test_configuration.py -q`

Expected: all selected tests pass.

### Task 3: Document the persistence change

**Files:**
- Modify: `docs/PROGRESS.md`

- [ ] **Step 1: Add a dated progress entry**

Record that Docker and launcher configurations now use the Git-tracked Prompt Library, that saved combinations land under `prompt_library/combinations/`, and that legacy `data/prompt_library` content is retained but unused by default.

- [ ] **Step 2: Validate the rendered Compose configuration**

Run: `docker compose config --quiet`

Expected: exit code 0.

- [ ] **Step 3: Inspect the final diff**

Run: `git diff -- docker-compose.yml scripts/launcher/configuration.py scripts/tests/test_compose_contract.py scripts/tests/test_configuration.py docs/PROGRESS.md`

Expected: only the approved persistence-path changes and documentation are present.

