# LTJ Prompt Library Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace AI Drawing's test Prompt Library categories with LTJ's selectable Prompt fragments through the local MCP server.

**Architecture:** The LTJ import was a one-time bootstrap operation. The resulting Prompt Library is self-contained; future maintenance uses AI Drawing's existing library UI and MCP tools without reading the LTJ folder.

**Tech Stack:** Python 3.11+, FastAPI backend, FastMCP client/server, Pydantic, pytest.

## Global Constraints

- Delete only `ai-drawing/prompt_library/positive/*.json` and `ai-drawing/prompt_library/negative/*.json`; preserve `manifest.json` and every non-library feature.
- Use existing `prompt_library_save` for category and entry creation; do not write replacement category JSON directly.
- Import static selectable LTJ Prompt fragments only; do not port model-family, composition, conflict, or generation behavior.
- Do not create model-family categories; all imported fragments are organized by semantic category.
- Populate `name_zh` and `description_zh` with Chinese-only user-visible text;
  keep source English only in `prompt`, aliases, and keywords. Do not change
  the MCP tool's permissive warning-only validation policy.

---

### Task 1: Build a deterministic LTJ import manifest

**Files:**
- Create: `scripts/import_ltj_prompt_library.py`
- Create: `backend/tests/test_ltj_prompt_library_import.py`

**Interfaces:**
- Produces: `build_categories(ltj_source: Path) -> list[dict[str, object]]`.
- Produces: `validate_categories(categories: list[dict[str, object]]) -> None`.
- Consumes: static tuple/list/dictionary literals in `LTJ/scenario_gui.py`.

- [ ] **Step 1: Write the failing manifest test**

```python
from pathlib import Path
from scripts.import_ltj_prompt_library import build_categories, validate_categories


def test_build_categories_extracts_bilingual_static_entries() -> None:
    source = Path(__file__).parents[2] / ".." / "LTJ" / "scenario_gui.py"
    categories = build_categories(source.resolve())
    validate_categories(categories)
    assert {item["id"] for item in categories} >= {"body-appearance", "clothing", "environment", "camera-composition", "expressions"}
    assert all(entry["name_zh"] and entry["description_zh"] and entry["prompt"] for item in categories for entry in item["entries"])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest backend/tests/test_ltj_prompt_library_import.py -v`

Expected: FAIL because `scripts.import_ltj_prompt_library` does not exist.

- [ ] **Step 3: Implement literal extraction and semantic mapping**

```python
def build_categories(ltj_source: Path) -> list[dict[str, object]]:
    constants = load_literal_constants(ltj_source)
    return map_ltj_constants_to_categories(constants)


def validate_categories(categories: list[dict[str, object]]) -> None:
    ids = [str(category["id"]) for category in categories]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate category id")
    for category in categories:
        for entry in category["entries"]:
            if not entry["name_zh"] or not entry["description_zh"] or not entry["prompt"]:
                raise ValueError(f"incomplete entry: {entry['id']}")
```

`load_literal_constants` must use `ast.parse` and `ast.literal_eval`, never import or execute `scenario_gui.py`. Map source constants to the approved semantic categories; preserve each selected Prompt string exactly.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest backend/tests/test_ltj_prompt_library_import.py -v`

Expected: PASS.

- [ ] **Step 5: Commit the manifest builder**

```bash
git add scripts/import_ltj_prompt_library.py backend/tests/test_ltj_prompt_library_import.py
git commit -m "feat: add LTJ prompt library manifest builder"
```

### Task 2: Add MCP-backed import and guarded physical clearing

**Files:**
- Modify: `scripts/import_ltj_prompt_library.py`
- Modify: `backend/tests/test_ltj_prompt_library_import.py`

**Interfaces:**
- Produces: `clear_existing_categories(root: Path) -> list[Path]`.
- Produces: `import_categories_via_mcp(categories: list[dict[str, object]], backend_url: str) -> dict[str, int]`.
- Consumes: Task 1 category documents and the running backend endpoint.

- [ ] **Step 1: Write failing safety and HTTP tests**

```python
def test_clear_existing_categories_leaves_manifest_and_other_files(tmp_path: Path) -> None:
    root = tmp_path / "prompt_library"
    (root / "positive").mkdir(parents=True)
    (root / "negative").mkdir()
    (root / "manifest.json").write_text("{}", encoding="utf-8")
    (root / "positive" / "test.json").write_text("{}", encoding="utf-8")
    removed = clear_existing_categories(root)
    assert [path.name for path in removed] == ["test.json"]
    assert (root / "manifest.json").exists()


def test_import_refuses_to_clear_when_mcp_backend_is_unhealthy() -> None:
    with pytest.raises(RuntimeError, match="backend"):
        require_healthy_backend("http://127.0.0.1:1")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest backend/tests/test_ltj_prompt_library_import.py -v`

Expected: FAIL because the guarded clear/import functions do not exist.

- [ ] **Step 3: Implement validation-before-deletion and MCP API writes**

```python
def require_healthy_backend(backend_url: str) -> None:
    response = httpx.get(f"{backend_url.rstrip('/')}/health", timeout=5)
    response.raise_for_status()


def clear_existing_categories(root: Path) -> list[Path]:
    removed: list[Path] = []
    for polarity in ("positive", "negative"):
        directory = (root / polarity).resolve()
        if directory.parent != root.resolve():
            raise ValueError("invalid Prompt Library directory")
        for path in directory.glob("*.json"):
            path.unlink()
            removed.append(path)
    return removed
```

After `require_healthy_backend`, use the existing MCP-compatible category PUT route once per category. A category payload contains its complete `entries` list and `expected_revision: 0`, so the backend writes through the same contract as `prompt_library_save`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest backend/tests/test_ltj_prompt_library_import.py -v`

Expected: PASS.

- [ ] **Step 5: Commit guarded importer behavior**

```bash
git add scripts/import_ltj_prompt_library.py backend/tests/test_ltj_prompt_library_import.py
git commit -m "feat: import LTJ prompts through MCP contract"
```

### Task 3: Start local services, perform import, and verify catalog

**Files:**
- Modify: `docs/PROGRESS.md`

**Interfaces:**
- Consumes: `scripts/import_ltj_prompt_library.py --backend-url http://127.0.0.1:8001 --library-root prompt_library --apply`.
- Produces: a catalog containing only LTJ-derived category documents.

- [ ] **Step 1: Start the backend at the project library root**

Run: `python -m uvicorn app.main:app --host 127.0.0.1 --port 8001` from `backend/`, with `PROMPT_LIBRARY_DIR` set to the repository `prompt_library` path.

Expected: `GET http://127.0.0.1:8001/health` returns HTTP 200.

- [ ] **Step 2: Start and inspect the MCP server**

Run: `uv run ai-drawing-mcp` from `mcp-server/`, with `MCP_BACKEND_API_URL=http://127.0.0.1:8001`.

Expected: the server exposes `prompt_library_search` and `prompt_library_save`.

- [ ] **Step 3: Run the guarded import**

Run: `python scripts/import_ltj_prompt_library.py --backend-url http://127.0.0.1:8001 --library-root prompt_library --apply`

Expected: the script reports the removed test documents and category/entry totals returned by the backend.

- [ ] **Step 4: Verify through MCP and tests**

Run: `python -m pytest backend/tests/test_ltj_prompt_library_import.py backend/tests/test_prompt_library_seed.py mcp-server/tests/test_prompt_library_tools.py -v`

Expected: PASS; MCP search catalog contains the new semantic categories and no old test categories.

- [ ] **Step 5: Record the import and commit**

```bash
git add prompt_library docs/PROGRESS.md scripts/import_ltj_prompt_library.py backend/tests/test_ltj_prompt_library_import.py
git commit -m "feat: replace test prompt library with LTJ prompts"
```
