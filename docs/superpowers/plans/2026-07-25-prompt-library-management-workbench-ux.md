# Prompt Library Management and Workbench UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move category and entry CRUD into an independent category-detail route, add reversible archive/restore, and make Prompt Workbench loadable, document-safe, and comfortable for free-text editing.

**Architecture:** Backend adds a narrow category/entry restore command using the existing file lock and optimistic concurrency contract. Frontend separates Prompt Library master-data management from Workbench combination documents, centralizes typed API calls, and separates raw text drafts from canonical fragments. MCP exposes the same restore intent, while live Gateway activation remains pending until CTY restarts the Gateway.

**Tech Stack:** FastAPI, Pydantic v2, file-backed JSON with atomic replace, pytest, React 18, TypeScript, React Router 6, Vitest, Testing Library, Tailwind CSS, FastMCP.

## Global Constraints

- `Prompt Workbench` must never create, update, archive, or restore category/entry source data.
- Workbench may create, load, update, and save-as combination documents.
- Category and entry delete means archive; no physical JSON deletion.
- Restore supports only `category` and `entry`, not `combination`.
- Entry writes use the parent category revision and etag as the concurrency token.
- Restoring a category must preserve every entry's existing `archived` state.
- Restoring an entry under an archived category must fail with an actionable error.
- Raw text must remain byte-for-byte editable while typing; normalization occurs only when the user applies or saves the text.
- Loading a combination must use the detail GET response revision and etag, never the catalog summary token.
- Frontend must preserve FastAPI `detail[]` errors and Backend `code + message + hint` errors.
- Source tests and the currently running Gateway schema are separate acceptance layers. CTY performs Gateway restarts.
- Do not modify repository Prompt Library seed JSON during automated tests.
- Do not touch or commit the existing untracked `.hermes/` directory.
- This feature does not submit GPU generation. The existing four-image Discord E2E remains a later task.

---

## File Map

### Backend

- `backend/app/schemas/prompt_library.py`: narrow `RestoreRequest` DTO.
- `backend/app/core/prompt_library_errors.py`: already-active and archived-parent errors.
- `backend/app/core/prompt_library_writes.py`: locked restore implementation.
- `backend/app/core/prompt_library.py`: provider protocol and adapter.
- `backend/app/api/prompt_library.py`: `POST /api/prompt-library/restore`.
- `backend/tests/test_prompt_library_writes.py`: restore domain tests.
- `backend/tests/test_prompt_library_api.py`: HTTP contract and OpenAPI tests.

### MCP

- `mcp-server/mcp_server/tools/prompt_library.py`: `prompt_library_restore` tool.
- `mcp-server/mcp_server/tool_catalog.py`: audited registration.
- `mcp-server/tests/test_prompt_library_tools.py`: payload and error tests.
- `mcp-server/tests/test_tool_catalog.py`: exposed schema assertion.
- `mcp-server/README.md`: active tool catalog.
- `docs/mcp-setup.md`: setup catalog.

### Frontend shared contracts

- `frontend/src/types/api.ts`: complete Prompt Library response types.
- `frontend/src/components/prompt-library/promptLibraryApi.ts`: typed fetch and shared error parser.
- `frontend/src/components/prompt-library/promptLibraryApi.test.ts`: API payload/error tests.

### Category management

- `frontend/src/pages/PromptCategoryManagement.tsx`: category list/create/status filters.
- `frontend/src/pages/PromptCategoryManagement.test.tsx`: list/create/navigation tests.
- `frontend/src/pages/PromptLibrary.tsx`: compatibility re-export only.
- `frontend/src/pages/PromptCategoryDetail.tsx`: category metadata and entry CRUD.
- `frontend/src/pages/PromptCategoryDetail.test.tsx`: detail-route integration tests.
- `frontend/src/components/prompt-library/PromptEntryEditor.tsx`: reused entry form.
- `frontend/src/App.tsx`: detail route.
- `frontend/src/pages/PromptLibraryLayout.tsx`: category navigation remains active on descendants.
- `frontend/src/pages/PromptLibraryLayout.test.tsx`: nested route navigation tests.

### Workbench

- `frontend/src/components/prompt-library/PromptEntryBrowser.tsx`: read-only source browser.
- `frontend/src/components/prompt-library/PromptEntryBrowser.test.tsx`: read-only boundary tests.
- `frontend/src/components/prompt-library/compositionState.ts`: deserialize and raw commit functions.
- `frontend/src/components/prompt-library/compositionState.test.ts`: fragment identity and raw parsing tests.
- `frontend/src/components/prompt-library/PromptComposerPanel.tsx`: fragment/raw modes.
- `frontend/src/components/prompt-library/PromptComposerPanel.test.tsx`: typing and apply/cancel tests.
- `frontend/src/components/prompt-library/PromptOverview.tsx`: updated action contract.
- `frontend/src/components/prompt-library/CombinationToolbar.tsx`: document selector/actions/status.
- `frontend/src/components/prompt-library/CombinationToolbar.test.tsx`: presentational action tests.
- `frontend/src/components/prompt-library/PromptWorkbench.tsx`: document state and API orchestration.
- `frontend/src/components/prompt-library/PromptWorkbench.test.tsx`: load/save/dirty/source-boundary integration.

---

### Task 1: Backend Category and Entry Restore Contract

**Files:**
- Modify: `backend/app/schemas/prompt_library.py`
- Modify: `backend/app/core/prompt_library_errors.py`
- Modify: `backend/app/core/prompt_library_writes.py`
- Modify: `backend/app/core/prompt_library.py`
- Modify: `backend/app/api/prompt_library.py`
- Test: `backend/tests/test_prompt_library_writes.py`
- Test: `backend/tests/test_prompt_library_api.py`

**Interfaces:**
- Consumes: `PromptLibraryStore.locked()`, `assert_precondition()`, `VersionedCategory`, and `WriteResponse`.
- Produces: `RestoreRequest`, `PromptLibraryProvider.restore(request)`, and `POST /api/prompt-library/restore`.

- [ ] **Step 1: Add failing writer tests for category restore**

Add tests that archive a category, restore it with the archive response token, and assert active state, incremented revision, changed etag, and unchanged entry archive flags:

```python
restored = provider.restore(
    RestoreRequest(
        resource_type="category",
        resource_id="clothing",
        polarity="positive",
        expected_revision=archived.category.category.revision,
        expected_etag=archived.category.etag,
    )
)
assert restored.category.category.archived is False
assert restored.category.category.revision == archived.category.category.revision + 1
assert restored.category.etag != archived.category.etag
assert restored.category.category.entries[0].archived is True
```

- [ ] **Step 2: Add failing writer tests for entry restore and rejection paths**

Cover successful entry restore, stale revision, stale etag, already-active category/entry, missing entry, and an archived parent:

```python
with pytest.raises(PromptLibraryError) as caught:
    provider.restore(
        RestoreRequest(
            resource_type="entry",
            resource_id="dress",
            polarity="positive",
            category_id="clothing",
            expected_revision=archived_parent.revision,
            expected_etag=archived_parent_etag,
        )
    )
assert caught.value.code == "parent_category_archived"
```

For each rejected write, read the category again and assert revision, entry revision, archived flags, and etag did not change.

- [ ] **Step 3: Run the writer tests and confirm RED**

Run:

```bash
cd backend && .venv/bin/pytest tests/test_prompt_library_writes.py -q
```

Expected: collection or test failures because `RestoreRequest` and `provider.restore` do not exist.

- [ ] **Step 4: Add the narrow restore schema and domain errors**

Add a category/entry-only DTO:

```python
RestoreResourceType = Literal["category", "entry"]

class RestoreRequest(ConcurrencyToken):
    resource_type: RestoreResourceType
    resource_id: Slug
    polarity: Polarity
    category_id: Slug | None = None

    @model_validator(mode="after")
    def validate_locator(self) -> "RestoreRequest":
        if self.resource_type == "entry" and self.category_id is None:
            raise ValueError("entry restore requires category_id")
        if self.resource_type == "category" and self.category_id is not None:
            raise ValueError("category restore must not include category_id")
        return self
```

Add errors with status 409:

```python
@classmethod
def already_active(cls, resource_type: str, resource_id: str) -> "PromptLibraryError":
    return cls(
        code="resource_already_active",
        message=f"{resource_type} '{resource_id}' is already active",
        hint="Reload the resource and restore only archived data.",
        status_code=409,
        details={"resource_type": resource_type, "resource_id": resource_id},
    )

@classmethod
def archived_parent(cls, polarity: str, category_id: str, entry_id: str) -> "PromptLibraryError":
    return cls(
        code="parent_category_archived",
        message=f"entry '{entry_id}' cannot be restored while category '{category_id}' is archived",
        hint="Restore the parent category first, then retry the entry restore.",
        status_code=409,
        details={"polarity": polarity, "category_id": category_id, "entry_id": entry_id},
    )
```

- [ ] **Step 5: Implement locked restore operations**

Add `PromptLibraryWriter.restore`, `_restore_category`, and `_restore_entry`. Check the concurrency token before active/parent state, mutate only archived/revision fields, and use `replace_json()` under the existing lock:

```python
def restore(self, request: RestoreRequest) -> WriteResponse:
    if request.resource_type == "entry":
        return self._restore_entry(request)
    return self._restore_category(request)
```

Do not call `_propagate_entry()` because restore does not change prompt snapshots.

- [ ] **Step 6: Wire provider and FastAPI route**

Add to the protocol and file provider:

```python
def restore(self, request: RestoreRequest) -> WriteResponse: ...
```

```python
def restore(self, request: RestoreRequest) -> WriteResponse:
    return self._writer.restore(request)
```

Add route:

```python
@router.post("/restore", response_model=WriteResponse)
def restore(
    body: RestoreRequest,
    provider: PromptLibraryProvider = Depends(_provider),
) -> WriteResponse:
    return _call(provider.restore, body)
```

- [ ] **Step 7: Add HTTP and OpenAPI tests**

Add category/entry success tests, a structured 409 assertion, a 422 assertion for `resource_type="combination"`, and `/api/prompt-library/restore` to the OpenAPI route-table assertion.

- [ ] **Step 8: Run focused Backend tests and confirm GREEN**

Run:

```bash
cd backend && .venv/bin/pytest \
  tests/test_prompt_library_writes.py \
  tests/test_prompt_library_api.py -q
```

Expected: all selected tests pass.

- [ ] **Step 9: Commit Backend restore**

```bash
git add backend/app/schemas/prompt_library.py \
  backend/app/core/prompt_library_errors.py \
  backend/app/core/prompt_library_writes.py \
  backend/app/core/prompt_library.py \
  backend/app/api/prompt_library.py \
  backend/tests/test_prompt_library_writes.py \
  backend/tests/test_prompt_library_api.py
git diff --cached --check
git commit -m "feat(prompt-library): restore categories and entries"
```

---

### Task 2: MCP Restore Tool and Audited Catalog

**Files:**
- Modify: `mcp-server/mcp_server/tools/prompt_library.py`
- Modify: `mcp-server/mcp_server/tool_catalog.py`
- Modify: `mcp-server/tests/test_prompt_library_tools.py`
- Modify: `mcp-server/tests/test_tool_catalog.py`
- Modify: `mcp-server/README.md`
- Modify: `docs/mcp-setup.md`

**Interfaces:**
- Consumes: `POST /api/prompt-library/restore` from Task 1.
- Produces: FastMCP tool `prompt_library_restore(resource_type, resource_id, expected_revision, expected_etag, polarity=None, category_id=None)`.

- [ ] **Step 1: Add failing exact-payload and error tests**

Patch `_get_client()` with a mock and assert the entry request exactly matches:

```python
{
    "resource_type": "entry",
    "resource_id": "masterpiece",
    "polarity": "positive",
    "category_id": "quality-ratings",
    "expected_revision": 21,
    "expected_etag": "current-etag",
}
```

Also test category payload omission of `category_id`, local rejection of combination, incomplete locators without a Backend call, and preservation of Backend 409 `code/message/hint/details`.

- [ ] **Step 2: Run MCP focused test and confirm RED**

Run:

```bash
cd mcp-server && .venv/bin/pytest tests/test_prompt_library_tools.py -q
```

Expected: import or assertion failures because `prompt_library_restore` does not exist.

- [ ] **Step 3: Implement the MCP restore tool**

Add a category/entry guard before reusing `_locator`:

```python
@mcp.tool()
def prompt_library_restore(
    resource_type: str,
    resource_id: str,
    expected_revision: int,
    expected_etag: str,
    polarity: str | None = None,
    category_id: str | None = None,
) -> dict[str, Any]:
    tool = "prompt_library_restore"
    if resource_type not in {"category", "entry"}:
        return {
            "ok": False,
            "tool": tool,
            "error": {
                "code": "invalid_resource_locator",
                "message": "restore supports category and entry resources only",
                "hint": "Choose category or entry and provide its required locator fields.",
                "details": {"resource_type": resource_type},
            },
        }
    _, problem = _locator(resource_type, resource_id, polarity, category_id)
    if problem:
        return {"tool": tool, **problem}
    body = {
        "resource_type": resource_type,
        "resource_id": resource_id,
        "expected_revision": expected_revision,
        "expected_etag": expected_etag,
        "polarity": polarity,
    }
    if category_id:
        body["category_id"] = category_id
    try:
        response = _get_client().post("prompt-library/restore", json=body)
        return {"ok": True, "tool": tool, **response, "next": "reload the category and use its new revision and etag"}
    except Exception as exc:
        return _error(tool, exc)
```

- [ ] **Step 4: Register and document the tool**

Add the audited catalog entry:

```python
ToolCatalogEntry(
    "prompt_library_restore",
    "mcp_server.tools.prompt_library",
    "prompt_library_restore",
    "dict",
    ("POST /api/prompt-library/restore",),
),
```

Add the same tool row to `mcp-server/README.md` and `docs/mcp-setup.md`.

- [ ] **Step 5: Add an exposed-schema assertion**

In `test_tool_catalog.py`, inspect FastMCP metadata and assert required fields are `resource_type`, `resource_id`, `expected_revision`, `expected_etag`, while `polarity` and `category_id` remain optional properties.

- [ ] **Step 6: Run focused registration tests and confirm GREEN**

Run:

```bash
cd mcp-server && .venv/bin/pytest \
  tests/test_prompt_library_tools.py \
  tests/test_tool_catalog.py \
  tests/test_server.py -q
```

Expected: all selected tests pass and formal stdio registration equals `INTENDED_TOOLS`.

- [ ] **Step 7: Commit MCP restore**

```bash
git add mcp-server/mcp_server/tools/prompt_library.py \
  mcp-server/mcp_server/tool_catalog.py \
  mcp-server/tests/test_prompt_library_tools.py \
  mcp-server/tests/test_tool_catalog.py \
  mcp-server/README.md docs/mcp-setup.md
git diff --cached --check
git commit -m "feat(mcp): expose prompt library restore"
```

---

### Task 3: Typed Frontend Prompt Library API Client

**Files:**
- Modify: `frontend/src/types/api.ts`
- Create: `frontend/src/components/prompt-library/promptLibraryApi.ts`
- Create: `frontend/src/components/prompt-library/promptLibraryApi.test.ts`

**Interfaces:**
- Consumes: existing Backend Prompt Library schemas.
- Produces: typed `getPromptCatalog`, `getPromptCategory`, `putPromptCategory`, `putPromptEntry`, `archivePromptResource`, `restorePromptResource`, `getPromptCombination`, `composeAndSaveCombination`, and `promptLibraryErrorMessage`.

- [ ] **Step 1: Add failing client tests**

Test exact URL encoding, archive/restore bodies, category/entry PUT tokens, combination GET, and both Backend error shapes:

```ts
expect(promptLibraryErrorMessage({
  detail: { message: "版本衝突", hint: "重新載入" },
}, 409)).toBe("版本衝突（重新載入）");

expect(promptLibraryErrorMessage({
  detail: [{ loc: ["body", "resource_id"], msg: "Field required" }],
}, 422)).toBe("resource_id：Field required");
```

- [ ] **Step 2: Run client test and confirm RED**

Run:

```bash
cd frontend && npm test -- src/components/prompt-library/promptLibraryApi.test.ts
```

Expected: module-not-found failure.

- [ ] **Step 3: Define complete Prompt Library types**

Add exact interfaces for `PromptEntryRef`, `PromptFragment`, `PromptEntry`, `PromptCategory`, `VersionedPromptCategory`, `PromptCombinationSummary`, `PromptCombination`, `VersionedPromptCombination`, `PromptWarning`, `PromptLibraryDiagnostic`, `PromptLibraryCatalogResponse`, `PromptLibraryWriteResponse`, and compose/save responses.

Use the Backend field names unchanged, including `source_revision`, `positive_prompt_snapshot`, `affected_combinations`, and nullable response members.

- [ ] **Step 4: Implement the typed API client**

Use a shared helper:

```ts
async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(promptLibraryErrorMessage(data, response.status));
  return data as T;
}
```

Build every mutation body explicitly so optional `expected_etag` and locator fields are omitted when absent.

- [ ] **Step 5: Run client tests and typecheck**

Run:

```bash
cd frontend && npm test -- src/components/prompt-library/promptLibraryApi.test.ts
cd frontend && npx tsc --noEmit
```

Expected: tests and typecheck pass.

- [ ] **Step 6: Commit the typed client**

```bash
git add frontend/src/types/api.ts \
  frontend/src/components/prompt-library/promptLibraryApi.ts \
  frontend/src/components/prompt-library/promptLibraryApi.test.ts
git diff --cached --check
git commit -m "refactor(frontend): type prompt library API"
```

---

### Task 4: Category List, Archived Filter, and Independent Detail Route

**Files:**
- Modify: `frontend/src/pages/PromptCategoryManagement.tsx`
- Modify: `frontend/src/pages/PromptLibrary.tsx`
- Create: `frontend/src/pages/PromptCategoryManagement.test.tsx`
- Create: `frontend/src/pages/PromptCategoryDetail.tsx`
- Create: `frontend/src/pages/PromptCategoryDetail.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/pages/PromptLibraryLayout.tsx`
- Modify: `frontend/src/pages/PromptLibraryLayout.test.tsx`

**Interfaces:**
- Consumes: catalog/category reads and category writes from Task 3.
- Produces: `/prompt-library/categories/:polarity/:categoryId` and a detail shell that later hosts entry CRUD.

- [ ] **Step 1: Move existing list tests and add failing navigation/filter tests**

Create `PromptCategoryManagement.test.tsx` from the existing page tests. Add assertions that active/archived filters show the correct cards and clicking a card navigates to:

```text
/prompt-library/categories/positive/quality-ratings
```

- [ ] **Step 2: Add failing nested-route tests**

Assert the category NavLink remains active on a detail route and `PromptCategoryDetail` receives valid route params. Include invalid polarity handling that renders an actionable error instead of fetching.

- [ ] **Step 3: Run page tests and confirm RED**

Run:

```bash
cd frontend && npm test -- \
  src/pages/PromptCategoryManagement.test.tsx \
  src/pages/PromptCategoryDetail.test.tsx \
  src/pages/PromptLibraryLayout.test.tsx
```

Expected: missing detail page/route and filter failures.

- [ ] **Step 4: Implement category list responsibility**

Move the list/create implementation into `PromptCategoryManagement.tsx`. Add `status: "active" | "archived"`, filter by polarity and `category.archived`, and render each card as a `Link` with encoded polarity/id.

Keep `PromptLibrary.tsx` as:

```ts
export { default } from "./PromptCategoryManagement";
```

- [ ] **Step 5: Add detail route and read-only shell**

Add:

```tsx
<Route path="categories/:polarity/:categoryId" element={<PromptCategoryDetail />} />
```

The detail page must validate polarity, fetch the complete category, render ID as readonly, and provide a back link. Remove `end` from the category management NavLink so descendants remain active.

- [ ] **Step 6: Run page tests and typecheck**

Run:

```bash
cd frontend && npm test -- \
  src/pages/PromptCategoryManagement.test.tsx \
  src/pages/PromptCategoryDetail.test.tsx \
  src/pages/PromptLibraryLayout.test.tsx
cd frontend && npx tsc --noEmit
```

Expected: selected tests and typecheck pass.

- [ ] **Step 7: Commit the route and list**

```bash
git add frontend/src/pages/PromptCategoryManagement.tsx \
  frontend/src/pages/PromptLibrary.tsx \
  frontend/src/pages/PromptCategoryManagement.test.tsx \
  frontend/src/pages/PromptCategoryDetail.tsx \
  frontend/src/pages/PromptCategoryDetail.test.tsx \
  frontend/src/App.tsx \
  frontend/src/pages/PromptLibraryLayout.tsx \
  frontend/src/pages/PromptLibraryLayout.test.tsx
git diff --cached --check
git commit -m "feat(frontend): add prompt category detail route"
```

---

### Task 5: Category Metadata and Entry CRUD in the Detail Page

**Files:**
- Modify: `frontend/src/pages/PromptCategoryDetail.tsx`
- Modify: `frontend/src/pages/PromptCategoryDetail.test.tsx`
- Modify: `frontend/src/components/prompt-library/PromptEntryEditor.tsx`
- Modify: `frontend/src/components/prompt-library/PromptEntryEditor.test.tsx`

**Interfaces:**
- Consumes: typed update/archive/restore calls from Task 3 and route shell from Task 4.
- Produces: the only UI that writes category and entry master data.

- [ ] **Step 1: Add failing category mutation tests**

Cover metadata update with current revision/etag, archive confirmation, restore, reload after success, duplicate-submit prevention, 409 draft preservation, and archived-category state.

Use a deterministic confirmation abstraction or injected `window.confirm` mock and assert archive does not call the API when declined.

- [ ] **Step 2: Add failing entry mutation tests**

Cover entry create/edit using the parent category token, archive/restore, active/archived filters, archived-parent restore disabled, and `affected_combinations` IDs rendered after an edit.

- [ ] **Step 3: Run detail tests and confirm RED**

Run:

```bash
cd frontend && npm test -- \
  src/pages/PromptCategoryDetail.test.tsx \
  src/components/prompt-library/PromptEntryEditor.test.tsx
```

Expected: mutation controls and restore behavior are missing.

- [ ] **Step 4: Implement category metadata update/archive/restore**

Keep the latest `VersionedPromptCategory` in state. Every successful mutation must call `loadCategory()` and replace the token. A 409 must set a local form error without clearing fields.

- [ ] **Step 5: Implement entry CRUD and status filters**

Reuse `PromptEntryEditor` inside the detail page. Pass the parent category revision/etag for both create and edit. Render separate active/archived filters and disable entry restore while `category.archived` is true with visible text: `請先恢復分類`.

- [ ] **Step 6: Display affected combination results**

After entry update, render:

```tsx
{affected.length > 0 && (
  <p role="status">已同步更新 {affected.length} 個組合：{affected.join("、")}</p>
)}
```

- [ ] **Step 7: Run detail/editor tests and typecheck**

Run:

```bash
cd frontend && npm test -- \
  src/pages/PromptCategoryDetail.test.tsx \
  src/components/prompt-library/PromptEntryEditor.test.tsx
cd frontend && npx tsc --noEmit
```

Expected: all selected tests and typecheck pass.

- [ ] **Step 8: Commit category and entry CRUD**

```bash
git add frontend/src/pages/PromptCategoryDetail.tsx \
  frontend/src/pages/PromptCategoryDetail.test.tsx \
  frontend/src/components/prompt-library/PromptEntryEditor.tsx \
  frontend/src/components/prompt-library/PromptEntryEditor.test.tsx
git diff --cached --check
git commit -m "feat(frontend): manage prompt categories and entries"
```

---

### Task 6: Enforce the Workbench Read-Only Source Boundary

**Files:**
- Modify: `frontend/src/components/prompt-library/PromptEntryBrowser.tsx`
- Modify: `frontend/src/components/prompt-library/PromptEntryBrowser.test.tsx`
- Modify: `frontend/src/components/prompt-library/PromptWorkbench.tsx`
- Modify: `frontend/src/components/prompt-library/PromptWorkbench.test.tsx`

**Interfaces:**
- Consumes: category/entry reads only.
- Produces: a source browser with only `onAddEntry` and `onAddLiteral` write callbacks into the local combination.

- [ ] **Step 1: Replace CRUD tests with failing read-only-boundary tests**

Assert there are no buttons named `新增詞條`, `編輯 …`, `封存 …`, or `恢復 …`. Assert search, polarity/category switching, `onAddEntry`, and `onAddLiteral` still work.

- [ ] **Step 2: Add a Workbench network-boundary test**

Interact with every source-browser control and assert no request uses category/entry PUT, `/archive`, or `/restore`.

- [ ] **Step 3: Run browser/workbench tests and confirm RED**

Run:

```bash
cd frontend && npm test -- \
  src/components/prompt-library/PromptEntryBrowser.test.tsx \
  src/components/prompt-library/PromptWorkbench.test.tsx
```

Expected: existing CRUD buttons violate the new assertions.

- [ ] **Step 4: Remove CRUD state, props, and handlers**

Delete `PromptEntryEditor`, `editingId`, `creating`, `busy`, `onSaveEntry`, and `onArchiveEntry` from `PromptEntryBrowser`. Delete `saveEntry()` and `archiveEntry()` from `PromptWorkbench` and stop passing those props.

- [ ] **Step 5: Run focused tests and typecheck**

Run:

```bash
cd frontend && npm test -- \
  src/components/prompt-library/PromptEntryBrowser.test.tsx \
  src/components/prompt-library/PromptWorkbench.test.tsx
cd frontend && npx tsc --noEmit
```

Expected: selected tests and typecheck pass.

- [ ] **Step 6: Commit the boundary correction**

```bash
git add frontend/src/components/prompt-library/PromptEntryBrowser.tsx \
  frontend/src/components/prompt-library/PromptEntryBrowser.test.tsx \
  frontend/src/components/prompt-library/PromptWorkbench.tsx \
  frontend/src/components/prompt-library/PromptWorkbench.test.tsx
git diff --cached --check
git commit -m "fix(frontend): keep prompt workbench source data read-only"
```

---

### Task 7: Composition Deserialization and Explicit Raw-Text Commit

**Files:**
- Modify: `frontend/src/components/prompt-library/compositionState.ts`
- Modify: `frontend/src/components/prompt-library/compositionState.test.ts`

**Interfaces:**
- Consumes: typed API `PromptFragment[]`.
- Produces: `deserializeFragments`, `commitRawText`, `RawCommitResult`, and display metadata on `WorkbenchFragment`.

- [ ] **Step 1: Add failing deserialization tests**

Test order sorting, source ref/revision preservation, literal source omission, weight restoration, resolved `name_zh`, entry-ID fallback, and non-colliding UI IDs across repeated loads:

```ts
const names = new Map([["positive/quality-ratings/masterpiece", "最高品質"]]);
const state = deserializeFragments(apiFragments, "positive", createFragmentId, names);
expect(state.fragments[0].source).toEqual({
  polarity: "positive",
  categoryId: "quality-ratings",
  entryId: "masterpiece",
  revision: 3,
});
expect(state.fragments[0].displayName).toBe("最高品質");
```

- [ ] **Step 2: Add failing raw commit tests**

Test that the raw string `masterpiece, ` remains outside canonical state until commit, successful commit creates only literals, middle insertion/deletion preserves no old refs, and malformed parentheses or weights return an error with the original state untouched.

Define the result contract:

```ts
export type RawCommitResult =
  | { ok: true; state: CompositionState }
  | { ok: false; state: CompositionState; error: string };
```

- [ ] **Step 3: Run state tests and confirm RED**

Run:

```bash
cd frontend && npm test -- src/components/prompt-library/compositionState.test.ts
```

Expected: missing exports and current positional reconcile behavior fails identity assertions.

- [ ] **Step 4: Implement API deserialization**

Sort by `(order, originalIndex)`, map API fields explicitly, convert weight `1` to an empty editable string, and accept both an ID factory and an `entryNameByRef` map. Resolve names with the stable key `${polarity}/${categoryId}/${entryId}`; when the map lacks a key, use `entryId`, never a hardcoded translation. Entry fragments added from the live browser must set `displayName` directly from that entry's `name_zh`.

- [ ] **Step 5: Implement raw commit parser**

Reuse top-level comma parsing but call it only from `commitRawText`. Validate balanced parentheses and weight range `0 < weight <= 2`. Every parsed item must be:

```ts
{
  id: idFactory(),
  kind: "literal",
  originalSnapshot: part.text,
  text: part.text,
  weight: part.weight,
  displayName: "自訂文字",
}
```

Do not reuse positional entry metadata.

- [ ] **Step 6: Run state tests and typecheck**

Run:

```bash
cd frontend && npm test -- src/components/prompt-library/compositionState.test.ts
cd frontend && npx tsc --noEmit
```

Expected: tests and typecheck pass.

- [ ] **Step 7: Commit composition state changes**

```bash
git add frontend/src/components/prompt-library/compositionState.ts \
  frontend/src/components/prompt-library/compositionState.test.ts
git diff --cached --check
git commit -m "fix(frontend): separate raw prompt drafts from fragments"
```

---

### Task 8: Fragment and Free-Text Editing Modes

**Files:**
- Modify: `frontend/src/components/prompt-library/PromptComposerPanel.tsx`
- Modify: `frontend/src/components/prompt-library/PromptComposerPanel.test.tsx`
- Modify: `frontend/src/components/prompt-library/PromptOverview.tsx`
- Modify: `frontend/src/components/prompt-library/PromptWorkbench.tsx`

**Interfaces:**
- Consumes: `commitRawText` and `RawCommitResult` from Task 7.
- Produces: explicit fragment/raw modes with `onCommitRawText(raw: string)`, `onRawDraftStateChange(open: boolean)`, and `rawResetVersion: number`.

- [ ] **Step 1: Add failing typing/apply/cancel tests**

Enter raw mode, type `masterpiece, `, and assert the textarea retains the exact value while the commit callback has not fired. Then test cancel, successful apply, and failed apply with draft preservation.

- [ ] **Step 2: Add failing label/layout tests**

Assert cards use `displayName`, edited source copies show `自訂副本`, no masterpiece/blurry hardcoding remains, and the grid uses responsive one/two-column classes. Replace the stale page-size assertion that currently expects 5 while production renders 6; the accepted design uses responsive cards rather than that outdated count.

- [ ] **Step 3: Run composer tests and confirm RED**

Run:

```bash
cd frontend && npm test -- \
  src/components/prompt-library/PromptComposerPanel.test.tsx \
  src/components/prompt-library/compositionState.test.ts
```

Expected: exact raw typing and new labels fail.

- [ ] **Step 4: Implement raw mode locally in each panel**

Use local state:

```ts
const [editingRaw, setEditingRaw] = useState(false);
const [rawDraft, setRawDraft] = useState("");
const [rawError, setRawError] = useState("");
```

Initialize from `state.text` when entering raw mode. `onChange` only updates `rawDraft`. Apply calls `onCommitRawText`; cancel discards draft. Call `onRawDraftStateChange(true)` on entry and `false` on apply/cancel. A `useEffect` keyed by `rawResetVersion` closes raw mode and clears draft/error after Workbench confirms a document replacement.

- [ ] **Step 5: Update action contracts and fragment labels**

Replace `onComposedTextChange` with `onCommitRawText`. Mark an entry fragment as a custom copy when `fragment.text !== fragment.originalSnapshot`. Use responsive grid classes such as `grid-cols-1 md:grid-cols-2`.

- [ ] **Step 6: Run focused tests and typecheck**

Run:

```bash
cd frontend && npm test -- \
  src/components/prompt-library/PromptComposerPanel.test.tsx \
  src/components/prompt-library/compositionState.test.ts \
  src/components/prompt-library/PromptWorkbench.test.tsx
cd frontend && npx tsc --noEmit
```

Expected: selected tests and typecheck pass.

- [ ] **Step 7: Commit the editor UX**

```bash
git add frontend/src/components/prompt-library/PromptComposerPanel.tsx \
  frontend/src/components/prompt-library/PromptComposerPanel.test.tsx \
  frontend/src/components/prompt-library/PromptOverview.tsx \
  frontend/src/components/prompt-library/PromptWorkbench.tsx
git diff --cached --check
git commit -m "feat(frontend): add explicit free-text prompt editing"
```

---

### Task 9: Combination Toolbar, Load, Dirty Guard, Update, and Save-As

**Files:**
- Create: `frontend/src/components/prompt-library/CombinationToolbar.tsx`
- Create: `frontend/src/components/prompt-library/CombinationToolbar.test.tsx`
- Modify: `frontend/src/components/prompt-library/PromptWorkbench.tsx`
- Modify: `frontend/src/components/prompt-library/PromptWorkbench.test.tsx`

**Interfaces:**
- Consumes: typed combination APIs from Task 3 and deserializer from Task 7.
- Produces: explicit combination document lifecycle and dirty state.

- [ ] **Step 1: Add failing toolbar presentation tests**

Assert selector options exclude archived combinations, current ID/revision and `尚未儲存` are visible, loading disables actions, and update/save-as dispatch different callbacks.

- [ ] **Step 2: Add failing Workbench load tests**

Mock catalog summary revision 1 and detail GET revision 3. Assert load uses GET data, restores both polarities with weights/order/refs, fetches each distinct referenced category once to resolve `name_zh`, displays `repaired` and warnings, and saves later with revision 3/GET etag. A failed category-name lookup must keep the combination loaded, fall back to entry IDs, and add a non-blocking warning.

- [ ] **Step 3: Add failing dirty-guard tests**

Modify a fragment, request another load or blank document, decline confirmation, and assert the current document remains. Approve and assert replacement occurs.

Raw drafts that have not been applied stay inside their panel. Each panel reports open/closed state through `onRawDraftStateChange`; loading/blank actions treat either open panel like dirty data so typing cannot be lost silently.

- [ ] **Step 4: Add failing create/update/save-as tests**

Assert:

- new document uses expected revision 0;
- update uses detail GET revision/etag;
- save-as uses the new ID and revision 0;
- Backend canonical fragments replace local state;
- success clears dirty;
- any later mutation clears old success text.

- [ ] **Step 5: Run toolbar/workbench tests and confirm RED**

Run:

```bash
cd frontend && npm test -- \
  src/components/prompt-library/CombinationToolbar.test.tsx \
  src/components/prompt-library/PromptWorkbench.test.tsx
```

Expected: toolbar missing and current manual-ID save flow violates assertions.

- [ ] **Step 6: Implement document state and mutation wrapper**

Represent loaded identity separately from compositions and track raw-editor state:

```ts
interface CombinationDocumentMeta {
  id: string | null;
  revision: number | null;
  etag: string | null;
  repaired: boolean;
  warnings: PromptWarning[];
  dirty: boolean;
}

const [rawEditorsOpen, setRawEditorsOpen] = useState<Record<PromptPolarity, boolean>>({
  positive: false,
  negative: false,
});
const [rawResetVersion, setRawResetVersion] = useState(0);
```

Every local mutation must call one wrapper that sets dirty and clears save success. Catalog versions remain display-only.

- [ ] **Step 7: Implement detail load and dirty guard**

Before fetching, use an explicit confirmation dialog whenever `meta.dirty || rawEditorsOpen.positive || rawEditorsOpen.negative`. If confirmed, increment `rawResetVersion`. Then URL-encode the selected ID and GET detail. Collect distinct `(polarity, category_id)` references, GET each category detail once with `Promise.allSettled`, and build the stable entry-name map consumed by `deserializeFragments`. Failed name lookups add a warning but do not discard snapshots or abort loading. Install only the combination detail response revision/etag. Do not autosave.

- [ ] **Step 8: Implement create, update, and save-as**

Keep one canonical save path using `/api/prompt-library/compose` with `save_as`. Normalize the two response states through `saved_combination`. Update local meta and compositions from that response.

- [ ] **Step 9: Run focused Workbench tests and typecheck**

Run:

```bash
cd frontend && npm test -- \
  src/components/prompt-library/CombinationToolbar.test.tsx \
  src/components/prompt-library/PromptWorkbench.test.tsx \
  src/components/prompt-library/compositionState.test.ts \
  src/components/prompt-library/PromptComposerPanel.test.tsx
cd frontend && npx tsc --noEmit
```

Expected: all selected tests and typecheck pass.

- [ ] **Step 10: Commit combination document workflow**

```bash
git add frontend/src/components/prompt-library/CombinationToolbar.tsx \
  frontend/src/components/prompt-library/CombinationToolbar.test.tsx \
  frontend/src/components/prompt-library/PromptWorkbench.tsx \
  frontend/src/components/prompt-library/PromptWorkbench.test.tsx
git diff --cached --check
git commit -m "feat(frontend): load and manage prompt combinations"
```

---

### Task 10: Full Verification and Real Browser Acceptance

**Files:**
- Modify if needed: `docs/PROGRESS.md`
- No Prompt Library seed JSON changes.

**Interfaces:**
- Consumes: all previous tasks.
- Produces: verified local product behavior and an honest Gateway activation status.

- [ ] **Step 1: Run the complete Backend suite**

Run:

```bash
cd backend && .venv/bin/pytest tests -q
```

Expected: complete Backend suite passes.

- [ ] **Step 2: Run the complete MCP suite**

Run:

```bash
cd mcp-server && .venv/bin/pytest tests -q
```

Expected: complete MCP suite passes, including audited catalog and formal stdio server.

- [ ] **Step 3: Run the complete Frontend gate**

Run:

```bash
cd frontend && npm test
cd frontend && npx tsc --noEmit
cd frontend && npm run build
```

Expected: all Frontend tests pass, typecheck exits 0, and production build succeeds.

- [ ] **Step 4: Start or reload only the affected local services**

Before restarting Backend, inspect active generation queues and avoid disrupting active jobs. Start the actual Frontend against the actual Backend. Do not restart Hermes Gateway; CTY owns that action.

- [ ] **Step 5: Perform a reversible browser management smoke**

Use a unique ID such as `ui-restore-smoke-<timestamp>` and complete:

1. create category;
2. navigate through the category card to its independent route;
3. update category metadata;
4. create and edit an entry;
5. archive and restore the entry;
6. archive and restore the category;
7. verify archived filters and parent-archived entry restore blocking.

Read the live API after each write to verify revision, etag, archived state, and unchanged entry flags after category restore.

- [ ] **Step 6: Perform a reversible browser Workbench smoke**

Complete:

1. verify source browser has no CRUD controls;
2. add one entry and one literal to both positive and negative lanes;
3. enter raw mode and type a value ending in `, `;
4. verify typing remains exact until apply;
5. apply and observe canonical fragments;
6. save a uniquely named combination;
7. create a blank document;
8. reload the saved combination;
9. verify both lanes, weights, order, dirty state, and detail revision/etag;
10. modify and update, then save-as under a second unique ID;
11. verify the generation request construction uses the visible prompts without submitting a GPU job.

- [ ] **Step 7: Clean smoke data using supported APIs**

Archive the unique entry/category and test combinations through supported APIs. Confirm catalog shows them archived. Do not delete files directly.

- [ ] **Step 8: Verify source registration and report Gateway status separately**

Confirm a freshly launched MCP stdio process exposes `prompt_library_restore`. Report the active Hermes Gateway as `pending CTY restart` until CTY restarts it. After that restart, enumerate active tools and perform one live archive→restore call with fresh revision/etag.

- [ ] **Step 9: Update progress documentation and commit verification notes**

Record the implemented routes, restore endpoint/tool, focused/full test counts, production build, real browser result, cleanup IDs, and pending/active Gateway state in `docs/PROGRESS.md`.

```bash
git add docs/PROGRESS.md
git diff --cached --check
git commit -m "docs: record prompt library management verification"
```

- [ ] **Step 10: Final repository review**

Run:

```bash
git status --short
git log --oneline -12
git diff --check
git diff HEAD~10..HEAD --stat
```

Expected: only the pre-existing untracked `.hermes/` remains, no product files are unstaged, and every planned commit is present locally. Do not claim remote publication unless an explicit push is performed and verified.
