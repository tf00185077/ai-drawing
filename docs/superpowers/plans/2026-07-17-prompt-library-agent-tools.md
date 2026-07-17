# Prompt Library Agent Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give agents the same Prompt Library search, authoring, composition, saved-combination, archive, and workflow-default generation capabilities as the human UI through four intent-level MCP tools plus the existing `generate_image` tool.

**Architecture:** Keep MCP stateless and thin: each tool accepts short locators or ordered fragment payloads, calls the shared FastAPI service, preserves its actionable errors and warnings, and returns stable structured dictionaries. Search, save, compose, and archive remain one tool per user intent; actual prompt formatting, revisions, file writes, snapshot repair, workflow execution, and recording stay in the backend.

**Tech Stack:** Python 3.11, FastMCP, httpx, existing `BackendApiClient`, pytest, backend Prompt Library and generation APIs from plans 1 and 2.

---

## Plan-set position and prerequisites

This is plan 3 of 3. Complete both earlier plans first:

1. `2026-07-17-prompt-library-service.md`
2. `2026-07-17-prompt-workbench-generation.md`

The tool catalog moves from exactly 27 to exactly 31 external tools.

## Locked file structure

### Create

- `mcp-server/mcp_server/tools/prompt_library.py` — four agent-facing intent tools and backend error preservation.
- `mcp-server/tests/test_prompt_library.py` — search/save/compose/archive and agent-flow tests.

### Modify

- `mcp-server/mcp_server/server.py:46-54` — register the new tool module.
- `mcp-server/mcp_server/tool_catalog.py:32-67` — add the four audited entries.
- `mcp-server/mcp_server/tools/generate.py:21-114` — expose and forward workflow-default and seed controls.
- `mcp-server/tests/test_client.py` — cover the already-implemented PUT client path.
- `mcp-server/tests/test_tool_catalog.py` — assert the four public schemas and generation parity fields.
- `mcp-server/tests/test_server.py:26-40` — importability smoke test.
- `mcp-server/tests/test_tools.py` — workflow-default `generate_image` request behavior.
- `mcp-server/README.md` — update the marked catalog and daily agent flow.
- `docs/mcp-setup.md` — update the marked catalog, count, and examples.
- `docs/PROGRESS.md` — record final plan-set completion and regression evidence.

## Locked public tool signatures

```python
Polarity = Literal["positive", "negative"]
ResourceType = Literal["category", "entry", "combination"]


def prompt_library_search(
    query: str = "",
    polarity: Polarity | None = None,
    resource_types: list[ResourceType] | None = None,
    category_id: str | None = None,
    threshold: int = 45,
    limit: int = 50,
    include_archived: bool = False,
) -> dict[str, Any]


def prompt_library_save(
    resource_type: ResourceType,
    resource_id: str,
    payload: dict[str, Any],
    expected_revision: int = 0,
    expected_etag: str | None = None,
    polarity: Polarity | None = None,
    category_id: str | None = None,
) -> dict[str, Any]


def prompt_library_compose(
    combination_id: str | None = None,
    positive: list[dict[str, Any]] | None = None,
    negative: list[dict[str, Any]] | None = None,
    save_as: dict[str, Any] | None = None,
) -> dict[str, Any]


def prompt_library_archive(
    resource_type: ResourceType,
    resource_id: str,
    expected_revision: int,
    expected_etag: str,
    polarity: Polarity | None = None,
    category_id: str | None = None,
) -> dict[str, Any]
```

All four return dictionaries. Successful composition includes:

```python
"generation": {
    "prompt": response["positive_prompt"],
    "negative_prompt": response["negative_prompt"],
}
```

No tool permanently deletes data, moves catalog JSON through the agent context, binds a saved combination to workflow parameters, or duplicates backend prompt formatting.

---

### Task 1: Structured backend-error preservation and dual-mode search

**Files:**

- Create: `mcp-server/mcp_server/tools/prompt_library.py`
- Create: `mcp-server/tests/test_prompt_library.py`

- [ ] **Step 1: Write failing search and error tests**

```python
def test_empty_search_returns_catalog_and_diagnostics() -> None:
    client = MagicMock()
    client.get.return_value = {
        "manifest": {"library_id": "default"},
        "categories": [{"id": "clothing", "polarity": "positive"}],
        "combinations": [],
        "diagnostics": [{"code": "invalid_json", "path": "negative/bad.json"}],
    }
    with patch("mcp_server.tools.prompt_library._get_client", return_value=client):
        result = prompt_library_search()
    assert result["ok"] is True
    assert result["categories"][0]["id"] == "clothing"
    assert result["diagnostics"][0]["code"] == "invalid_json"
    client.get.assert_called_once_with("prompt-library/catalog")


def test_empty_search_with_category_locator_returns_full_category() -> None:
    client = MagicMock()
    client.get.return_value = {"category": {"id": "clothing", "entries": [{"id": "dress"}]}, "etag": "v1"}
    with patch("mcp_server.tools.prompt_library._get_client", return_value=client):
        result = prompt_library_search(polarity="positive", category_id="clothing")
    assert result["category"]["entries"][0]["id"] == "dress"
    client.get.assert_called_once_with("prompt-library/categories/positive/clothing")


def test_fuzzy_search_forwards_filters_and_preserves_match_metadata() -> None:
    client = MagicMock()
    client.get.return_value = {
        "results": [{"id": "dress", "score": 100, "matched_fields": ["prompt"]}],
        "total": 1,
        "diagnostics": [],
    }
    with patch("mcp_server.tools.prompt_library._get_client", return_value=client):
        result = prompt_library_search(
            "dress",
            polarity="positive",
            resource_types=["entry"],
            category_id="clothing",
            threshold=50,
            limit=10,
        )
    assert result["results"][0]["matched_fields"] == ["prompt"]
    client.get.assert_called_once_with(
        "prompt-library/search",
        params={
            "q": "dress",
            "polarity": "positive",
            "resource_types": ["entry"],
            "category_id": "clothing",
            "threshold": 50,
            "limit": 10,
            "include_archived": False,
        },
    )


def test_backend_problem_keeps_code_message_hint_and_details() -> None:
    client = MagicMock()
    client.get.side_effect = status_error(
        409,
        {"detail": {"code": "external_change", "message": "bytes changed", "hint": "reload", "details": {"path": "x.json"}}},
    )
    with patch("mcp_server.tools.prompt_library._get_client", return_value=client):
        result = prompt_library_search("dress")
    assert result == {
        "ok": False,
        "tool": "prompt_library_search",
        "error": {
            "code": "external_change",
            "message": "bytes changed",
            "hint": "reload",
            "details": {"path": "x.json"},
        },
        "status_code": 409,
    }
```

- [ ] **Step 2: Run the test file and confirm failure**

```powershell
& .\mcp-server\.venv\Scripts\python.exe -m pytest mcp-server/tests/test_prompt_library.py -q
```

Expected: collection fails because the new tool module does not exist.

- [ ] **Step 3: Implement stable success and error payloads**

Use this module-local HTTP error conversion so backend problems are not collapsed into `HTTPStatusError`:

```python
def _backend_error(tool: str, exc: Exception) -> dict[str, Any]:
    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
        try:
            body = exc.response.json()
        except ValueError:
            body = {}
        detail = body.get("detail", body)
        if not isinstance(detail, dict):
            detail = {"message": str(detail)}
        return {
            "ok": False,
            "tool": tool,
            "error": {
                "code": str(detail.get("code", "backend_http_error")),
                "message": str(detail.get("message", str(exc))),
                "hint": str(detail.get("hint", "Inspect the backend response, correct the request, and retry.")),
                "details": detail.get("details", {}),
            },
            "status_code": exc.response.status_code,
        }
    return {
        "ok": False,
        "tool": tool,
        "error": {
            "code": exc.__class__.__name__,
            "message": str(exc),
            "hint": "Confirm the backend is running, then retry.",
            "details": {"where": "backend"},
        },
    }
```

Successful tools return `{"ok": True, "tool": tool, **response, "next": instruction}`.

- [ ] **Step 4: Implement empty-catalog and fuzzy-result search modes**

Decorate `prompt_library_search` with `@mcp.tool()`. Strip the query. With an empty query plus `polarity` and `category_id`, call the quoted category-detail route so the agent can browse every entry. With no query and no category locator, call `prompt-library/catalog`. With a non-empty query, call `prompt-library/search`. Reject an empty-query category id without polarity. Omit optional search filters whose value is `None`, validate threshold `0..100` and limit `1..200` locally, preserve every backend field, and set `next` to compose selected refs or inspect diagnostics.

- [ ] **Step 5: Run tests and commit**

```powershell
& .\mcp-server\.venv\Scripts\python.exe -m pytest mcp-server/tests/test_prompt_library.py -q
```

Expected: search and error tests pass.

Commit:

```powershell
git add mcp-server/mcp_server/tools/prompt_library.py mcp-server/tests/test_prompt_library.py
git commit -m "feat: search prompt library from MCP"
```

### Task 2: One save intent for category, entry, and combination writes

**Files:**

- Modify: `mcp-server/mcp_server/tools/prompt_library.py`
- Modify: `mcp-server/tests/test_prompt_library.py`
- Modify: `mcp-server/tests/test_client.py`

- [ ] **Step 1: Add failing route, token, and locator tests**

```python
@pytest.mark.parametrize(
    ("resource_type", "resource_id", "polarity", "category_id", "expected_path"),
    [
        ("category", "clothing", "positive", None, "prompt-library/categories/positive/clothing"),
        ("entry", "dress", "positive", "clothing", "prompt-library/categories/positive/clothing/entries/dress"),
        ("combination", "portrait-dress", None, None, "prompt-library/combinations/portrait-dress"),
    ],
)
def test_save_routes_by_resource_type(resource_type, resource_id, polarity, category_id, expected_path) -> None:
    client = MagicMock()
    client.put.return_value = {"revision": 1, "etag": "new"}
    with patch("mcp_server.tools.prompt_library._get_client", return_value=client):
        result = prompt_library_save(
            resource_type,
            resource_id,
            {"name_zh": "名稱", "description_zh": "說明", "aliases": [], "keywords": [], "order": 10},
            expected_revision=0,
            polarity=polarity,
            category_id=category_id,
        )
    assert result["ok"] is True
    client.put.assert_called_once()
    assert client.put.call_args.args[0] == expected_path
    body = client.put.call_args.kwargs["json"]
    assert body["expected_revision"] == 0
    assert "expected_etag" not in body


def test_update_overwrites_payload_concurrency_fields() -> None:
    client = MagicMock()
    client.put.return_value = {"revision": 4, "etag": "new"}
    payload = {"name_zh": "名稱", "expected_revision": 999, "expected_etag": "forged"}
    with patch("mcp_server.tools.prompt_library._get_client", return_value=client):
        prompt_library_save("combination", "my-set", payload, expected_revision=3, expected_etag="trusted")
    body = client.put.call_args.kwargs["json"]
    assert body["expected_revision"] == 3
    assert body["expected_etag"] == "trusted"


def test_entry_save_requires_parent_category_locator() -> None:
    result = prompt_library_save("entry", "dress", {}, polarity="positive")
    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_resource_locator"
```

Add a `test_put_forwards_json` in `mcp-server/tests/test_client.py` using the existing httpx mock pattern.

- [ ] **Step 2: Run focused tests and confirm failure**

```powershell
& .\mcp-server\.venv\Scripts\python.exe -m pytest mcp-server/tests/test_prompt_library.py mcp-server/tests/test_client.py -q
```

Expected: save tests fail because the function is absent; the new client test documents the existing PUT behavior.

- [ ] **Step 3: Implement safe locator routing**

Quote every URL segment with `quote(value, safe="")`. Require polarity for category; require polarity and category id for entry; reject polarity/category id on combination only when they would make the locator ambiguous. Return local `invalid_resource_locator` with a concrete hint and do not call the backend.

Map routes exactly:

```python
if resource_type == "category":
    path = f"prompt-library/categories/{quote(polarity, safe='')}/{quote(resource_id, safe='')}"
elif resource_type == "entry":
    path = f"prompt-library/categories/{quote(polarity, safe='')}/{quote(category_id, safe='')}/entries/{quote(resource_id, safe='')}"
else:
    path = f"prompt-library/combinations/{quote(resource_id, safe='')}"
```

- [ ] **Step 4: Implement concurrency-safe request construction**

Copy the payload, remove any caller-supplied concurrency keys, then set the function arguments. Include etag only when provided. Return the backend revision/etag/affected combinations unchanged. On 409 and 422, use `_backend_error` so `revision_conflict`, `external_change`, messages, and hints survive.

- [ ] **Step 5: Run tests and commit**

```powershell
& .\mcp-server\.venv\Scripts\python.exe -m pytest mcp-server/tests/test_prompt_library.py mcp-server/tests/test_client.py -q
```

Expected: all selected tests pass.

Commit:

```powershell
git add mcp-server/mcp_server/tools/prompt_library.py mcp-server/tests/test_prompt_library.py mcp-server/tests/test_client.py
git commit -m "feat: save prompt resources from MCP"
```

### Task 3: Composition, optional save, archive, and repaired-reference flow

**Files:**

- Modify: `mcp-server/mcp_server/tools/prompt_library.py`
- Modify: `mcp-server/tests/test_prompt_library.py`

- [ ] **Step 1: Add failing compose and archive tests**

```python
def test_compose_forwards_order_weight_literal_and_save_intent() -> None:
    client = MagicMock()
    client.post.return_value = {
        "positive_prompt": "1girl, (dress:1.2)",
        "negative_prompt": "low quality",
        "positive": [{"kind": "literal", "snapshot": "1girl", "weight": 1.0, "order": 10}],
        "negative": [],
        "warnings": [],
        "snapshot_repaired": False,
        "saved_combination": {"combination": {"id": "my-dress"}, "etag": "new"},
    }
    positive = [literal("1girl", order=10), entry_ref("positive", "clothing", "dress", order=20, weight=1.2)]
    save_as = {"id": "my-dress", "name_zh": "我的洋裝", "description_zh": "常用", "expected_revision": 0}
    with patch("mcp_server.tools.prompt_library._get_client", return_value=client):
        result = prompt_library_compose(
            combination_id="portrait-base",
            positive=positive,
            negative=[literal("low quality")],
            save_as=save_as,
        )
    client.post.assert_called_once_with(
        "prompt-library/compose",
        json={
            "combination_id": "portrait-base",
            "positive": positive,
            "negative": [literal("low quality")],
            "save_as": save_as,
        },
    )
    assert result["generation"] == {
        "prompt": "1girl, (dress:1.2)",
        "negative_prompt": "low quality",
    }
    assert "generate_image" in result["next"]


def test_missing_reference_warning_is_successful() -> None:
    client = MagicMock()
    client.post.return_value = {
        "positive_prompt": "blue coat",
        "negative_prompt": "",
        "positive": [],
        "negative": [],
        "warnings": [{"code": "missing_reference", "message": "snapshot used"}],
        "snapshot_repaired": False,
    }
    with patch("mcp_server.tools.prompt_library._get_client", return_value=client):
        result = prompt_library_compose(positive=[entry_ref("positive", "clothing", "missing", snapshot="blue coat")])
    assert result["ok"] is True
    assert result["warnings"][0]["code"] == "missing_reference"


def test_archive_forwards_parent_token_and_never_deletes() -> None:
    client = MagicMock()
    client.post.return_value = {"resource_type": "entry", "archived": True, "revision": 4, "etag": "new"}
    with patch("mcp_server.tools.prompt_library._get_client", return_value=client):
        result = prompt_library_archive(
            "entry", "dress", expected_revision=3, expected_etag="old", polarity="positive", category_id="clothing"
        )
    assert result["archived"] is True
    client.post.assert_called_once_with(
        "prompt-library/archive",
        json={
            "resource_type": "entry",
            "resource_id": "dress",
            "polarity": "positive",
            "category_id": "clothing",
            "expected_revision": 3,
            "expected_etag": "old",
        },
    )
    client.delete.assert_not_called()
```

- [ ] **Step 2: Add a sequential agent-flow test**

Use one stateful fake client to execute: save category, save entry, search, compose with free text and weight, save combination, update entry, fetch repaired combination via empty-query catalog/detail as applicable, and compose again. Assert all short locators and concurrency tokens advance, and the second output uses corrected English prompt without the agent rewriting snapshots.

- [ ] **Step 3: Run tests and confirm failure**

```powershell
& .\mcp-server\.venv\Scripts\python.exe -m pytest mcp-server/tests/test_prompt_library.py -q
```

Expected: compose, archive, and agent-flow tests fail because functions are absent.

- [ ] **Step 4: Implement compose and archive**

Composition sends an optional validated `combination_id` plus ordered lists unchanged, defaulting missing lists to `[]`; include `save_as` only when provided. The backend imports and lazily repairs the saved combination before appending supplied fragments. Preserve repaired fragments, warnings, snapshot flags, and saved-combination details. Add the `generation` object and a next instruction to call `generate_image` with it.

Archive validates locators with the same helper as save, requires revision at least 1 and a non-empty etag, posts only to `prompt-library/archive`, and preserves backend conflicts. Do not expose a delete tool or `force` flag.

- [ ] **Step 5: Run tests and commit**

```powershell
& .\mcp-server\.venv\Scripts\python.exe -m pytest mcp-server/tests/test_prompt_library.py -q
```

Expected: all Prompt Library MCP tests pass.

Commit:

```powershell
git add mcp-server/mcp_server/tools/prompt_library.py mcp-server/tests/test_prompt_library.py
git commit -m "feat: compose and archive prompts from MCP"
```

### Task 4: Registration, audited catalog, and generation parity

**Files:**

- Modify: `mcp-server/mcp_server/server.py:46-54`
- Modify: `mcp-server/mcp_server/tool_catalog.py:32-67`
- Modify: `mcp-server/mcp_server/tools/generate.py:21-114`
- Modify: `mcp-server/tests/test_tool_catalog.py`
- Modify: `mcp-server/tests/test_server.py:26-40`
- Modify: `mcp-server/tests/test_tools.py`

- [ ] **Step 1: Add failing registration and schema assertions**

```python
@pytest.mark.asyncio
async def test_prompt_library_tools_expose_intent_level_schemas() -> None:
    registered = {tool.name: tool for tool in await mcp.list_tools()}
    assert set(registered) >= {
        "prompt_library_search",
        "prompt_library_save",
        "prompt_library_compose",
        "prompt_library_archive",
    }
    assert {"query", "polarity", "resource_types"} <= set(registered["prompt_library_search"].inputSchema["properties"])
    assert {"resource_type", "resource_id", "payload", "expected_revision", "expected_etag"} <= set(
        registered["prompt_library_save"].inputSchema["properties"]
    )
    assert {"combination_id", "positive", "negative", "save_as"} <= set(
        registered["prompt_library_compose"].inputSchema["properties"]
    )


@pytest.mark.asyncio
async def test_generate_image_exposes_workflow_default_controls() -> None:
    registered = {tool.name: tool for tool in await mcp.list_tools()}
    properties = registered["generate_image"].inputSchema["properties"]
    assert "use_workflow_defaults" in properties
    enum_schema = next(item for item in properties["seed_mode"]["anyOf"] if "enum" in item)
    assert set(enum_schema["enum"]) == {"workflow_default", "random", "fixed"}
```

In `test_tools.py`, assert `generate_image(use_workflow_defaults=True, seed_mode="random")` forwards both fields and does not inject `batch_size=1`; assert legacy calls still inject batch size 1.

Also assert `list_available_resources()` calls both `generate/available-resources` and `workflow-catalog/generation-forms`, then returns the descriptor list as `generation_forms`. This gives the agent the same eligible workflow list, supported overrides, defaults, and options shown in the UI.

- [ ] **Step 2: Run catalog/server/tool tests and confirm failure**

```powershell
& .\mcp-server\.venv\Scripts\python.exe -m pytest mcp-server/tests/test_tool_catalog.py mcp-server/tests/test_server.py mcp-server/tests/test_tools.py -q
```

Expected: four tools are missing from registration/catalog and generation fields are absent.

- [ ] **Step 3: Register the module and add four audited entries**

Import `prompt_library` in the tools tuple in `server.py`. Add exactly these catalog entries after style presets:

```python
ToolCatalogEntry("prompt_library_search", "mcp_server.tools.prompt_library", "prompt_library_search", "dict", ("GET /api/prompt-library/catalog", "GET /api/prompt-library/categories/{polarity}/{category_id}", "GET /api/prompt-library/search")),
ToolCatalogEntry("prompt_library_save", "mcp_server.tools.prompt_library", "prompt_library_save", "dict", ("PUT /api/prompt-library/categories/{polarity}/{category_id}", "PUT /api/prompt-library/categories/{polarity}/{category_id}/entries/{entry_id}", "PUT /api/prompt-library/combinations/{combination_id}")),
ToolCatalogEntry("prompt_library_compose", "mcp_server.tools.prompt_library", "prompt_library_compose", "dict", ("POST /api/prompt-library/compose",)),
ToolCatalogEntry("prompt_library_archive", "mcp_server.tools.prompt_library", "prompt_library_archive", "dict", ("POST /api/prompt-library/archive",)),
```

Update the minimum import smoke test to import and assert all four callables.

- [ ] **Step 4: Expose generation defaults and seed mode through `generate_image`**

Add:

```python
use_workflow_defaults: bool | None = None,
seed_mode: Literal["workflow_default", "random", "fixed"] | None = None,
```

Forward each when not `None`. When `use_workflow_defaults is True`, omit the old implicit `batch_size=1`; when false or omitted, retain it for compatibility. Update the docstring to state the three seed modes and that blank overrides preserve workflow values only when workflow defaults are enabled.

In the existing `list_available_resources`, keep its current resource response and make one additional `client.get("workflow-catalog/generation-forms")` call. Attach that response's `items` as `generation_forms` and its `capability_source` as `workflow_capability_source`. Update the existing `list_available_resources` catalog entry so its endpoint tuple also contains `GET /api/workflow-catalog/generation-forms`.

- [ ] **Step 5: Run tests and commit**

```powershell
& .\mcp-server\.venv\Scripts\python.exe -m pytest mcp-server/tests/test_tool_catalog.py mcp-server/tests/test_server.py mcp-server/tests/test_tools.py -q
```

Expected: selected tests pass and the registered catalog contains exactly 31 tools.

Commit:

```powershell
git add mcp-server/mcp_server/server.py mcp-server/mcp_server/tool_catalog.py mcp-server/mcp_server/tools/generate.py mcp-server/tests/test_tool_catalog.py mcp-server/tests/test_server.py mcp-server/tests/test_tools.py
git commit -m "feat: register prompt library agent tools"
```

### Task 5: MCP documentation, full regression, and final feature checkpoint

**Files:**

- Modify: `mcp-server/README.md`
- Modify: `docs/mcp-setup.md`
- Modify: `docs/PROGRESS.md`

- [ ] **Step 1: Update both audited catalog blocks**

Inside each `<!-- MCP-CATALOG:START -->` / `<!-- MCP-CATALOG:END -->` block, list all four new names with their intent and backend endpoints. Replace stale tool-count prose with `31 個意圖級工具`. Keep the catalog source-of-truth statement pointing to `mcp-server/mcp_server/tool_catalog.py`.

- [ ] **Step 2: Document the daily agent flow and concurrency recovery**

Add this flow to both relevant usage sections:

```text
prompt_library_search
  → prompt_library_compose
  → generate_image
  → get_generation_status
```

Document category/entry/combination creation through `prompt_library_save`, revision 0 creation, revision+etag updates, archive instead of deletion, and recovery from `revision_conflict`/`external_change` by reloading before retry. State that a saved combination contains prompts only and never workflow settings.

- [ ] **Step 3: Run the complete MCP suite**

```powershell
& .\mcp-server\.venv\Scripts\python.exe -m pytest mcp-server/tests -q
```

Expected: the full MCP suite exits 0; catalog registration and documentation marker tests pass.

- [ ] **Step 4: Run the cross-project regression command**

```powershell
python -m pytest backend/tests/ mcp-server/tests/ -x -q
Set-Location frontend
npm run typecheck
npm test
npm run build
Set-Location ..
```

Expected: backend, MCP, typecheck, frontend tests, and frontend build all exit 0.

- [ ] **Step 5: Update progress and commit the completed plan set**

Add a dated `Prompt Library agent parity` entry to `docs/PROGRESS.md` with: four intent tools, exact tool count 31, workflow-default/random/fixed generation parity, structured error recovery, documentation updates, and exact regression results. Mark the complete Prompt Library/Workbench feature delivered while leaving unrelated future enhancements unchanged.

```powershell
git add mcp-server/README.md docs/mcp-setup.md docs/PROGRESS.md
git commit -m "docs: complete prompt library agent workflow"
git status --short
```

Expected: the commit succeeds and `git status --short` prints no uncommitted files.
