# Prompt Library 分類樹 Phase 1（地基）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 為分類加上選填 `parent_id` 與寫入防環/容錯，並讓組裝排序改用「祖先路徑」比較——地基完成、非破壞、畫面仍扁平。

**Architecture:** 後端 `PromptCategory` 加選填 `parent_id`（身分三元組不變）；寫入時嚴格驗證父分類（存在/同 polarity/非自我/防環），讀取 catalog 時容錯（壞連結降級為 root＋diagnostic）。前端排序 `rankOf` 從單一數字改為「祖先路徑 order 陣列」，`sortFragmentsByRecommendation` 改字典序比較。此階段無 UI 樹、無資料變更。

**Tech Stack:** Python 3.11 + Pydantic（後端）；React 18 + TS + Vite + vitest（前端）。

## Global Constraints

- **身分不變**：詞的定址仍是 `(polarity, category_id, entry_id)`；不動組合、provenance、comma-atomic、composer、生圖、輸出字串。零 migration。
- **後端 API 契約**：只新增選填欄位與診斷，不移除既有欄位。
- **向後相容排序**：扁平分類（全為 root）的排序輸出必須與現況逐字相同。
- **寬進嚴出**：寫入 parent 嚴格擋錯；讀取 catalog 遇壞連結降級 root＋diagnostic，絕不讓 library 無法載入。
- 驗證：後端 `cd backend && python -m pytest <file> -q`（`PYTHONUTF8=1`）；前端 `cd frontend && npx vitest run <file>`、`npx tsc --noEmit`、`npm run build`。

---

## File Structure

| 檔案 | 責任 | 動作 |
|---|---|---|
| `backend/app/core/prompt_library_models.py` | `PromptCategory` 加 `parent_id` | Modify（Task 1） |
| `backend/app/schemas/prompt_library.py` | `CategorySummary` + `CategoryWriteRequest` 加 `parent_id` | Modify（Task 1） |
| `backend/app/core/prompt_library.py` | `_category_summary` 帶出 `parent_id`；`catalog()` 套用樹驗證 | Modify（Task 1、Task 3） |
| `backend/app/core/prompt_library_writes.py` | `save_category` 驗證父分類並持久化 `parent_id` | Modify（Task 2） |
| `backend/app/core/prompt_library_tree.py` | 純函式 `validate_category_tree`（catalog 用） | Create（Task 3） |
| `backend/tests/test_prompt_library_hierarchy.py` | Phase 1 後端測試 | Create（Task 1–3） |
| `frontend/src/types/api.ts` | `PromptCategory` / `PromptCategorySummary` 加 `parent_id` | Modify（Task 4） |
| `frontend/src/components/prompt-library/compositionState.ts` | `sortFragmentsByRecommendation` 改字典序（rankOf 回 `number[]`） | Modify（Task 4） |
| `frontend/src/components/prompt-library/compositionState.test.ts` | 排序測試改陣列 + 深樹案例 | Modify（Task 4） |
| `frontend/src/components/prompt-library/PromptWorkbench.tsx` | 建 `categoryPathOrders`、`rankOf` 回路徑陣列 | Modify（Task 4） |
| `frontend/src/components/prompt-library/PromptWorkbench.test.tsx` | 深樹排序整合測試 | Modify（Task 4） |
| `docs/PROGRESS.md` | 進度 | Modify（Task 5） |

---

## Task 1: 後端 `parent_id` 欄位（模型 + schema + catalog 帶出）

**Files:**
- Modify: `backend/app/core/prompt_library_models.py`
- Modify: `backend/app/schemas/prompt_library.py`
- Modify: `backend/app/core/prompt_library.py`（`_category_summary`）
- Test: `backend/tests/test_prompt_library_hierarchy.py`（新建）

**Interfaces:**
- Consumes: 既有 `Slug`、`PromptCategory`、`CategorySummary`、`CategoryWriteRequest`、`FilePromptLibraryProvider`。
- Produces: `PromptCategory.parent_id: Slug | None = None`；`CategorySummary.parent_id: Slug | None = None`；`CategoryWriteRequest.parent_id: Slug | None = None`；catalog summary 帶出 `parent_id`。此階段**不做**父分類驗證（Task 2/3）。

- [ ] **Step 1: 寫失敗測試**

新建 `backend/tests/test_prompt_library_hierarchy.py`：

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.prompt_library import FilePromptLibraryProvider
from app.core.prompt_library_models import PromptCategory
from app.schemas.prompt_library import CategorySummary, CategoryWriteRequest


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _category(cid: str, order: int, parent_id: str | None = None) -> dict:
    doc = {
        "schema_version": 1,
        "id": cid,
        "polarity": "positive",
        "name_zh": cid,
        "description_zh": f"{cid} desc",
        "aliases": [],
        "keywords": [],
        "order": order,
        "revision": 1,
        "archived": False,
        "entries": [],
    }
    if parent_id is not None:
        doc["parent_id"] = parent_id
    return doc


@pytest.fixture
def provider(tmp_path: Path) -> FilePromptLibraryProvider:
    root = tmp_path / "prompt_library"
    (root / "positive").mkdir(parents=True)
    (root / "negative").mkdir()
    (root / "combinations").mkdir()
    _write_json(root / "manifest.json", {
        "schema_version": 2, "library_id": "default", "name": "Test",
        "description_zh": "測試", "comma_atomic_version": 1,
        "comma_atomic_migration_required": False,
    })
    return FilePromptLibraryProvider(root)


def test_category_parent_id_defaults_none_and_roundtrips():
    assert PromptCategory(id="clothing", polarity="positive", name_zh="服裝",
                          description_zh="d").parent_id is None
    child = PromptCategory(id="clothing-top", polarity="positive", name_zh="上衣",
                           description_zh="d", parent_id="clothing")
    assert child.parent_id == "clothing"


def test_category_summary_carries_parent_id():
    summary = CategorySummary(id="clothing-top", polarity="positive", name_zh="上衣",
                              description_zh="d", order=10, revision=1, archived=False,
                              entry_count=0, etag="x", parent_id="clothing")
    assert summary.parent_id == "clothing"


def test_catalog_surfaces_parent_id(provider: FilePromptLibraryProvider):
    root = provider.store.root
    _write_json(root / "positive" / "clothing.json", _category("clothing", 10))
    _write_json(root / "positive" / "clothing-top.json",
                _category("clothing-top", 10, parent_id="clothing"))
    catalog = provider.catalog()
    by_id = {c.id: c for c in catalog.categories}
    assert by_id["clothing"].parent_id is None
    assert by_id["clothing-top"].parent_id == "clothing"


def test_category_write_request_accepts_parent_id():
    req = CategoryWriteRequest(name_zh="上衣", description_zh="d", order=10,
                               expected_revision=0, parent_id="clothing")
    assert req.parent_id == "clothing"
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd backend && PYTHONUTF8=1 python -m pytest tests/test_prompt_library_hierarchy.py -q`
Expected: FAIL（`parent_id` 非法欄位 / 未帶出）。

- [ ] **Step 3: 實作**

在 `prompt_library_models.py` 的 `PromptCategory`（欄位區，`archived: bool = False` 之後、`entries` 之前）新增：
```python
    parent_id: Slug | None = None
```

在 `schemas/prompt_library.py` 的 `CategorySummary` 末尾欄位加：
```python
    parent_id: Slug | None = None
```
在同檔 `CategoryWriteRequest` 末尾欄位加：
```python
    parent_id: Slug | None = None
```
（註：`EntryWriteRequest`、`CombinationWriteRequest` 繼承此欄位但其 writer 不讀取，無副作用。）

在 `prompt_library.py` 的 `_category_summary` 的 `CategorySummary(...)` 建構加一行：
```python
            parent_id=category.parent_id,
```

- [ ] **Step 4: 執行測試確認通過**

Run: `cd backend && PYTHONUTF8=1 python -m pytest tests/test_prompt_library_hierarchy.py -q`
Expected: PASS（4 passed）。

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/prompt_library_models.py backend/app/schemas/prompt_library.py backend/app/core/prompt_library.py backend/tests/test_prompt_library_hierarchy.py
git commit -m "feat(prompt-library): add optional category parent_id (model, schema, catalog)"
```

---

## Task 2: 後端 `save_category` 父分類驗證 + 持久化

**Files:**
- Modify: `backend/app/core/prompt_library_writes.py`
- Test: `backend/tests/test_prompt_library_hierarchy.py`（追加）

**Interfaces:**
- Consumes: Task 1 的 `parent_id` 欄位；既有 `PromptLibraryStore`、`PromptLibraryError`。
- Produces: `save_category` 在 `request.parent_id` 非空時驗證（父存在且同 polarity、非自我、不成環），失敗回 `PromptLibraryError`（status 422）；成功時把 `parent_id` 寫入 `PromptCategory`。

- [ ] **Step 1: 寫失敗測試**（追加到 `test_prompt_library_hierarchy.py`）

```python
from app.core.prompt_library_errors import PromptLibraryError


def _save(provider, cid, parent_id=None, expected_revision=0):
    return provider.save_category("positive", cid, CategoryWriteRequest(
        name_zh=cid, description_zh="d", order=10,
        expected_revision=expected_revision, parent_id=parent_id))


def test_save_category_persists_valid_parent(provider):
    _save(provider, "clothing")
    _save(provider, "clothing-top", parent_id="clothing")
    stored = provider.get_category("positive", "clothing-top")
    assert stored.category.parent_id == "clothing"


def test_save_category_rejects_missing_parent(provider):
    with pytest.raises(PromptLibraryError) as exc:
        _save(provider, "clothing-top", parent_id="nope")
    assert exc.value.status_code == 422


def test_save_category_rejects_self_parent(provider):
    with pytest.raises(PromptLibraryError):
        _save(provider, "clothing", parent_id="clothing")


def test_save_category_rejects_cross_polarity_parent(provider):
    # negative category as parent of a positive one → rejected
    provider.save_category("negative", "neg-root", CategoryWriteRequest(
        name_zh="n", description_zh="d", order=10, expected_revision=0))
    with pytest.raises(PromptLibraryError):
        _save(provider, "clothing-top", parent_id="neg-root")


def test_save_category_rejects_cycle(provider):
    _save(provider, "a")
    _save(provider, "b", parent_id="a")
    # now try to make a's parent = b → cycle a->b->a
    with pytest.raises(PromptLibraryError):
        provider.save_category("positive", "a", CategoryWriteRequest(
            name_zh="a", description_zh="d", order=10,
            expected_revision=1, parent_id="b"))
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd backend && PYTHONUTF8=1 python -m pytest tests/test_prompt_library_hierarchy.py -q`
Expected: FAIL（驗證未實作；valid parent 也未持久化）。

- [ ] **Step 3: 實作**

在 `prompt_library_writes.py` 新增驗證輔助（放在 `save_category` 方法上方，class 內）：

```python
    def _validate_parent(self, polarity: Polarity, category_id: str, parent_id: str) -> None:
        if parent_id == category_id:
            raise PromptLibraryError(
                code="invalid_parent_self",
                message="A category cannot be its own parent.",
                hint="Choose a different parent category or leave it empty for a root.",
                status_code=422,
                details={"category_id": category_id},
            )
        categories, _ = self.store.scan_categories()
        by_id = {
            doc.model.id: doc.model
            for doc in categories
            if doc.model.polarity == polarity
        }
        if parent_id not in by_id:
            raise PromptLibraryError(
                code="parent_not_found",
                message="The parent category does not exist in this polarity.",
                hint="Create the parent first, or pick an existing same-polarity category.",
                status_code=422,
                details={"category_id": category_id, "parent_id": parent_id},
            )
        # walk up from parent; reaching category_id means a cycle
        seen: set[str] = set()
        cursor: str | None = parent_id
        while cursor is not None:
            if cursor == category_id:
                raise PromptLibraryError(
                    code="parent_cycle",
                    message="Setting this parent would create a category cycle.",
                    hint="Pick a parent that is not a descendant of this category.",
                    status_code=422,
                    details={"category_id": category_id, "parent_id": parent_id},
                )
            if cursor in seen:
                break
            seen.add(cursor)
            cursor = by_id[cursor].parent_id if cursor in by_id else None
```

在 `save_category` 內、`assert_precondition(...)` 之後、`category = PromptCategory(...)` 之前，加：
```python
            if request.parent_id is not None:
                self._validate_parent(polarity, category_id, request.parent_id)
```
並在 `category = PromptCategory(` 建構參數中加一行（於 `entries=...` 附近）：
```python
                parent_id=request.parent_id,
```

- [ ] **Step 4: 執行測試確認通過**

Run: `cd backend && PYTHONUTF8=1 python -m pytest tests/test_prompt_library_hierarchy.py -q`
Expected: PASS（含 Task 1 共 9 passed）。

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/prompt_library_writes.py backend/tests/test_prompt_library_hierarchy.py
git commit -m "feat(prompt-library): validate category parent on write (exists/self/polarity/cycle)"
```

---

## Task 3: 後端 catalog 樹容錯（壞連結降級 root + diagnostic）

**Files:**
- Create: `backend/app/core/prompt_library_tree.py`
- Modify: `backend/app/core/prompt_library.py`（`catalog()`）
- Test: `backend/tests/test_prompt_library_hierarchy.py`（追加）

**Interfaces:**
- Consumes: `CategorySummary`、`PromptLibraryDiagnostic`。
- Produces: `validate_category_tree(summaries: list[CategorySummary]) -> tuple[list[CategorySummary], list[PromptLibraryDiagnostic]]`——回傳「已把壞 parent 降級為 None 的 summaries」與診斷清單。`catalog()` 套用之。

- [ ] **Step 1: 寫失敗測試**（追加）

```python
from app.core.prompt_library_tree import validate_category_tree


def _summary(cid, order=10, parent_id=None, polarity="positive"):
    return CategorySummary(id=cid, polarity=polarity, name_zh=cid, description_zh="d",
                           order=order, revision=1, archived=False, entry_count=0,
                           etag="x", parent_id=parent_id)


def test_validate_tree_keeps_valid_parents():
    adjusted, diags = validate_category_tree([
        _summary("clothing"), _summary("clothing-top", parent_id="clothing"),
    ])
    assert diags == []
    assert {c.id: c.parent_id for c in adjusted} == {"clothing": None, "clothing-top": "clothing"}


def test_validate_tree_demotes_missing_parent():
    adjusted, diags = validate_category_tree([_summary("top", parent_id="ghost")])
    assert {c.id: c.parent_id for c in adjusted} == {"top": None}
    assert len(diags) == 1 and diags[0].details["category_id"] == "top"


def test_validate_tree_demotes_cross_polarity_parent():
    adjusted, diags = validate_category_tree([
        _summary("np", polarity="negative"),
        _summary("pos", parent_id="np", polarity="positive"),
    ])
    assert {c.id: c.parent_id for c in adjusted}["pos"] is None
    assert len(diags) == 1


def test_validate_tree_breaks_cycle():
    adjusted, diags = validate_category_tree([
        _summary("a", parent_id="b"), _summary("b", parent_id="a"),
    ])
    # at least one edge demoted so the result is acyclic; a diagnostic emitted
    parents = {c.id: c.parent_id for c in adjusted}
    assert parents["a"] is None or parents["b"] is None
    assert len(diags) >= 1


def test_catalog_demotes_dangling_parent_and_still_loads(provider):
    root = provider.store.root
    _write_json(root / "positive" / "top.json", _category("top", 10, parent_id="ghost"))
    catalog = provider.catalog()
    by_id = {c.id: c for c in catalog.categories}
    assert by_id["top"].parent_id is None
    assert any(d.details.get("category_id") == "top" for d in catalog.diagnostics)
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd backend && PYTHONUTF8=1 python -m pytest tests/test_prompt_library_hierarchy.py -q`
Expected: FAIL（`prompt_library_tree` 不存在 / catalog 未套用）。

- [ ] **Step 3: 實作純函式**

新建 `backend/app/core/prompt_library_tree.py`：

```python
"""Category tree integrity: demote invalid parent links to root with diagnostics."""

from __future__ import annotations

from app.schemas.prompt_library import CategorySummary, PromptLibraryDiagnostic


def _diagnostic(summary: CategorySummary, reason: str, hint: str) -> PromptLibraryDiagnostic:
    return PromptLibraryDiagnostic(
        code="category_parent_demoted",
        message=f"Category '{summary.id}' parent link was ignored: {reason}.",
        hint=hint,
        path=f"{summary.polarity}/{summary.id}",
        details={
            "category_id": summary.id,
            "polarity": summary.polarity,
            "parent_id": summary.parent_id,
            "reason": reason,
        },
    )


def validate_category_tree(
    summaries: list[CategorySummary],
) -> tuple[list[CategorySummary], list[PromptLibraryDiagnostic]]:
    by_key: dict[tuple[str, str], CategorySummary] = {
        (summary.polarity, summary.id): summary for summary in summaries
    }
    demoted: set[tuple[str, str]] = set()
    diagnostics: list[PromptLibraryDiagnostic] = []

    def parent_of(polarity: str, cid: str) -> str | None:
        summary = by_key.get((polarity, cid))
        if summary is None:
            return None
        if (polarity, cid) in demoted:
            return None
        return summary.parent_id

    for summary in summaries:
        parent_id = summary.parent_id
        if parent_id is None:
            continue
        key = (summary.polarity, summary.id)
        parent_key = (summary.polarity, parent_id)
        if parent_id == summary.id:
            demoted.add(key)
            diagnostics.append(_diagnostic(summary, "points to itself",
                                           "Leave the parent empty or pick another category."))
            continue
        if parent_key not in by_key:
            demoted.add(key)
            diagnostics.append(_diagnostic(summary, "parent not found in this polarity",
                                           "Create the parent, or clear the parent link."))
            continue
        # cycle detection: walk up from parent (respecting already-demoted edges)
        seen: set[tuple[str, str]] = set()
        cursor: str | None = parent_id
        cycles = False
        while cursor is not None:
            cursor_key = (summary.polarity, cursor)
            if cursor == summary.id:
                cycles = True
                break
            if cursor_key in seen:
                break
            seen.add(cursor_key)
            cursor = parent_of(summary.polarity, cursor)
        if cycles:
            demoted.add(key)
            diagnostics.append(_diagnostic(summary, "would form a cycle",
                                           "Pick a parent that is not a descendant of this category."))

    adjusted = [
        summary.model_copy(update={"parent_id": None})
        if (summary.polarity, summary.id) in demoted
        else summary
        for summary in summaries
    ]
    return adjusted, diagnostics
```

在 `prompt_library.py` 匯入並套用。頂部 import 區加：
```python
from app.core.prompt_library_tree import validate_category_tree
```
把 `catalog()` 內建構 `CatalogResponse` 的部分改為先算 summaries、驗證樹、合併 diagnostics：
```python
    def catalog(self) -> CatalogResponse:
        self._guard()
        manifest = self.store.read_manifest()
        categories, category_diagnostics = self.store.scan_categories()
        combinations, combination_diagnostics = self.store.scan_combinations()
        category_summaries = sorted(
            (self._category_summary(document) for document in categories),
            key=lambda item: (item.order, item.id),
        )
        category_summaries, tree_diagnostics = validate_category_tree(category_summaries)
        return CatalogResponse(
            manifest=manifest,
            categories=category_summaries,
            combinations=sorted(
                (self._combination_summary(document) for document in combinations),
                key=lambda item: (item.order, item.id),
            ),
            diagnostics=category_diagnostics + combination_diagnostics + tree_diagnostics,
        )
```

- [ ] **Step 4: 執行測試確認通過**

Run: `cd backend && PYTHONUTF8=1 python -m pytest tests/test_prompt_library_hierarchy.py -q`
Expected: PASS（全部 Phase 1 後端測試綠）。

- [ ] **Step 5: 後端回歸**

Run: `cd backend && PYTHONUTF8=1 python -m pytest tests/test_prompt_library_api.py tests/test_prompt_library_writes.py tests/test_prompt_composer.py tests/test_prompt_library_models.py -q`
Expected: PASS（既有 prompt-library 測試不受影響）。

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/prompt_library_tree.py backend/app/core/prompt_library.py backend/tests/test_prompt_library_hierarchy.py
git commit -m "feat(prompt-library): catalog demotes invalid category parents with diagnostics"
```

---

## Task 4: 前端 — 型別 + 祖先路徑排序

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/components/prompt-library/compositionState.ts`
- Modify: `frontend/src/components/prompt-library/compositionState.test.ts`
- Modify: `frontend/src/components/prompt-library/PromptWorkbench.tsx`
- Modify: `frontend/src/components/prompt-library/PromptWorkbench.test.tsx`

**Interfaces:**
- Consumes: catalog 的 `parent_id`。
- Produces: `sortFragmentsByRecommendation(state, rankOf: (f) => number[])` 改字典序；`PromptWorkbench` 依 catalog `parent_id` 建 `categoryPathOrders: Map<string, number[]>`，`rankOf` 回 `[...path, entryOrder]`（literal/未解析回 `[Infinity]`）。

- [ ] **Step 1: 型別加 `parent_id`**

在 `types/api.ts` 的 `PromptCategory` 介面加 `parent_id?: string | null;`；`PromptCategorySummary` 介面加 `parent_id?: string | null;`。

- [ ] **Step 2: 改排序測試為陣列 rankOf + 深樹案例**

在 `compositionState.test.ts` 的 `describe("sortFragmentsByRecommendation", ...)`：把既有 `rankOf` 從回傳數字改為回傳陣列，並新增深樹案例。用以下整段**取代**現有 `describe("sortFragmentsByRecommendation", ...)` 區塊：

```ts
describe("sortFragmentsByRecommendation", () => {
  const ids = sequentialIds("s");
  const entryFrag = (categoryId: string, entryId: string) => ({
    id: ids(),
    kind: "entry" as const,
    displayName: entryId,
    source: { polarity: "positive" as const, categoryId, entryId, revision: 1 },
    sourceSnapshotRaw: entryId,
    snapshotRaw: entryId,
    weight: "",
  });

  // path-order rank keys: character root(15) deep vs clothing root(70)
  const paths: Record<string, number[]> = {
    "chars-2nd": [15, 10, 20, 30], // 角色→女→LoveLive→二代
    "chars-1st": [15, 10, 20, 10], // 角色→女→LoveLive→一代
    clothing: [70],
    quality: [10],
  };
  const rankOf = (fragment: { kind: string; source?: { categoryId: string } }): number[] => {
    if (fragment.kind !== "entry" || !fragment.source) return [Number.POSITIVE_INFINITY];
    const entryOrder = 10;
    return [...(paths[fragment.source.categoryId] ?? [Number.POSITIVE_INFINITY]), entryOrder];
  };

  it("aggregates by root ancestor and orders sub-branches by path, literals last", () => {
    let state = emptyComposition();
    state = appendFragment(state, entryFrag("clothing", "dress"));
    state = appendLiteralText(state, "solo", ids);
    state = appendFragment(state, entryFrag("chars-2nd", "honoka"));
    state = appendFragment(state, entryFrag("quality", "masterpiece"));
    state = appendFragment(state, entryFrag("chars-1st", "eli"));

    const sorted = sortFragmentsByRecommendation(state, rankOf);
    expect(sorted.fragments.map((f) => f.snapshotRaw)).toEqual([
      "masterpiece", // quality [10,10]
      "eli",         // [15,10,20,10,10]
      "honoka",      // [15,10,20,30,10]
      "dress",       // [70,10]
      "solo",        // literal [Infinity]
    ]);
    expect(sorted.text).toBe("masterpiece,eli,honoka,dress,solo");
  });

  it("keeps original order among equal-rank fragments (stable)", () => {
    let state = emptyComposition();
    state = appendFragment(state, entryFrag("clothing", "first"));
    state = appendFragment(state, entryFrag("clothing", "second"));
    const sorted = sortFragmentsByRecommendation(state, rankOf);
    expect(sorted.fragments.map((f) => f.snapshotRaw)).toEqual(["first", "second"]);
  });
});
```

- [ ] **Step 3: 執行測試確認失敗**

Run: `cd frontend && npx vitest run src/components/prompt-library/compositionState.test.ts`
Expected: FAIL（`rankOf` 現簽名為回傳 `number`，字典序未實作）。

- [ ] **Step 4: 實作字典序排序**

在 `compositionState.ts` 把 `sortFragmentsByRecommendation` 整段換成：

```ts
function compareRankKey(a: number[], b: number[]): number {
  const length = Math.min(a.length, b.length);
  for (let index = 0; index < length; index += 1) {
    if (a[index] < b[index]) return -1;
    if (a[index] > b[index]) return 1;
  }
  return a.length - b.length;
}

export function sortFragmentsByRecommendation(
  state: CompositionState,
  rankOf: (fragment: WorkbenchFragment) => number[],
): CompositionState {
  const ranked = state.fragments.map((fragment, index) => ({
    fragment,
    index,
    rank: rankOf(fragment),
  }));
  ranked.sort(
    (left, right) => compareRankKey(left.rank, right.rank) || left.index - right.index,
  );
  return rebuild(ranked.map((item) => item.fragment));
}
```

- [ ] **Step 5: 執行測試確認通過**

Run: `cd frontend && npx vitest run src/components/prompt-library/compositionState.test.ts`
Expected: PASS。

- [ ] **Step 6: `PromptWorkbench` 建路徑表 + rankOf 回陣列**

在 `PromptWorkbench.tsx`：新增 ref（於 `entryOrderByRef` 附近）：
```tsx
  const categoryPathOrders = useRef<Map<string, number[]>>(new Map());
```
在載入 catalog 的 effect 內、建好 `categoryMeta` 之後，新增建路徑表（`catalog.categories` 每筆含 `order` 與可選 `parent_id`）：
```tsx
        const orderByKey = new Map<string, { order: number; parentId: string | null }>();
        (catalog.categories || []).forEach((item) =>
          orderByKey.set(`${item.polarity}/${item.id}`, {
            order: item.order,
            parentId: item.parent_id ?? null,
          }),
        );
        const pathOrders = new Map<string, number[]>();
        const pathFor = (polarity: string, id: string, guard: Set<string>): number[] => {
          const key = `${polarity}/${id}`;
          const cached = pathOrders.get(key);
          if (cached) return cached;
          const node = orderByKey.get(key);
          if (!node || guard.has(key)) return [];
          guard.add(key);
          const parentPath = node.parentId ? pathFor(polarity, node.parentId, guard) : [];
          const path = [...parentPath, node.order];
          pathOrders.set(key, path);
          return path;
        };
        orderByKey.forEach((_value, key) => {
          const slash = key.indexOf("/");
          pathFor(key.slice(0, slash), key.slice(slash + 1), new Set());
        });
        categoryPathOrders.current = pathOrders;
```
把既有 `rankOf`（`useCallback`）改為回傳路徑陣列：
```tsx
  const rankOf = useCallback(
    (fragment: WorkbenchFragment): number[] => {
      if (fragment.kind !== "entry" || !fragment.source) return [Number.POSITIVE_INFINITY];
      const catKey = `${fragment.source.polarity}/${fragment.source.categoryId}`;
      const path = categoryPathOrders.current.get(catKey);
      if (!path || path.length === 0) return [Number.POSITIVE_INFINITY];
      const entryOrder = entryOrderByRef.current.get(`${catKey}/${fragment.source.entryId}`) ?? 10;
      return [...path, entryOrder];
    },
    [],
  );
```
（`categoryMeta` 與 `categoryInfoOf` 維持不變，供面板顯示分類標籤。）

- [ ] **Step 7: 深樹排序整合測試**

先讀既有 `PromptWorkbench.test.tsx` 的 catalog mock 慣例：
Run: `cd frontend && cat src/components/prompt-library/PromptWorkbench.test.tsx`

在既有整合測試附近新增一個測試：讓 `getPromptCatalog` 回傳含 `parent_id` 的巢狀分類（例如 root `chars`(order 15) 與 child `chars-2nd`(order 30, parent_id `chars`)、以及一個 `quality`(order 10) root），`getPromptCategory` 回其 entries。互動加入「chars-2nd 的一個詞」再加入「quality 的一個詞」，斷言 Positive 最終文字中 **quality 詞在 chars-2nd 詞之前**（依根 order 10 < 15），且 chars-2nd 詞緊接其後（證明路徑排序生效）。骨架：

```tsx
it("auto-sorts nested-category entries by ancestor-path order", async () => {
  // getPromptCatalog → categories:
  //   { polarity:"positive", id:"quality", order:10, parent_id:null, ... }
  //   { polarity:"positive", id:"chars", order:15, parent_id:null, ... }
  //   { polarity:"positive", id:"chars-2nd", order:30, parent_id:"chars", ... }
  // getPromptCategory(positive, chars-2nd) → entry honoka(prompt "honoka")
  // getPromptCategory(positive, quality) → entry masterpiece(prompt "masterpiece")
  render(<PromptWorkbench />);
  await screen.findByText("Prompt Workbench");
  // add honoka (from chars-2nd) first, then masterpiece (from quality)
  // ... existing add-entry helper ...
  const finalText = await screen.findByLabelText("Positive Prompt 最終文字");
  expect((finalText as HTMLTextAreaElement).value).toBe("masterpiece,honoka");
});
```
> 依既有 mock/操作 helper 補齊；關鍵斷言：後加入的 quality 詞（root order 10）排在先加入的深層 chars-2nd 詞（root order 15）之前。

- [ ] **Step 8: 全前端測試 + typecheck + build**

Run: `cd frontend && npx vitest run && npx tsc --noEmit && npm run build`
Expected: 全 PASS、typecheck 乾淨、build 成功。既有扁平排序測試（皆單層 → 路徑長度 2）行為不變。

- [ ] **Step 9: Commit**

```bash
git add frontend/src/types/api.ts frontend/src/components/prompt-library/compositionState.ts frontend/src/components/prompt-library/compositionState.test.ts frontend/src/components/prompt-library/PromptWorkbench.tsx frontend/src/components/prompt-library/PromptWorkbench.test.tsx
git commit -m "feat(prompt-workbench): ancestor-path ordering for hierarchical categories"
```

---

## Task 5: 收尾驗證與進度更新

**Files:**
- Modify: `docs/PROGRESS.md`

- [ ] **Step 1: 後端 + 前端總驗證**

Run:
```bash
cd backend && PYTHONUTF8=1 python -m pytest tests/test_prompt_library_hierarchy.py tests/test_prompt_library_api.py tests/test_prompt_library_writes.py tests/test_prompt_composer.py -q
cd frontend && npx vitest run && npx tsc --noEmit && npm run build
```
Expected: 後端相關測試全綠；前端測試全綠、typecheck、build 成功。

- [ ] **Step 2: `git diff --check`**

Run: `git diff --check`
Expected: 無輸出。

- [ ] **Step 3: 更新 `docs/PROGRESS.md`**

於檔案最上方新增：

```markdown
## 2026-07-27 Prompt Library 分類樹 Phase 1（地基）

- `PromptCategory` 新增選填 `parent_id`（指向同 polarity 分類）；詞的身分 `(polarity, category_id, entry_id)` 不變，組合/provenance/comma-atomic/生圖/輸出全不動、零 migration。
- 寫入分類的 parent 嚴格驗證：父存在且同 polarity、非自我、不成環，違反回結構化 422 不寫檔。
- 讀取 catalog 容錯：懸空/跨 polarity/成環的 parent 一律降級為 root 並附 `category_parent_demoted` diagnostic，library 照常載入（寬進嚴出）。
- 前端組裝排序改「祖先路徑」字典序：`rankOf` 回傳從 root 到該詞每層 order 的陣列＋詞 order，`sortFragmentsByRecommendation` 逐層比較。扁平分類（皆 root）行為與先前逐字相同。
- 畫面此階段仍為扁平（Phase 2 管理 UX、Phase 3 瀏覽器樹狀另行）。驗證：後端 pytest、前端 vitest 全綠，`tsc` 與 Vite build 通過。
```

- [ ] **Step 4: Commit**

```bash
git add docs/PROGRESS.md
git commit -m "docs(progress): prompt library category tree phase 1 (parent_id + path ordering)"
```

---

## Self-Review 對照

- **spec：資料模型 `parent_id`（身分不變）** → Task 1。✅
- **spec：寫入嚴格驗證（存在/同 polarity/自我/防環）** → Task 2。✅
- **spec：讀取容錯降級 + diagnostic** → Task 3。✅
- **spec：依根祖先的路徑排序（rankOf number[]、字典序、扁平向後相容）** → Task 4。✅
- **spec：零 migration / 輸出不變 / 後端契約只增不減** → Global Constraints + 各 task 回歸與最終文字斷言。✅
- **型別一致性**：`parent_id`（後端 `Slug|None`、前端 `string|null`）、`validate_category_tree` 回傳型別、`rankOf: (f)=>number[]`、`categoryPathOrders: Map<string, number[]>` 在 Task 1/3/4 使用一致。✅
- **每 task 後 repo green**：後端欄位（1）→ 寫入驗證（2）→ catalog 容錯（3）→ 前端排序（4，簽名與呼叫端同 task 一起改）→ 收尾（5）。✅
- Phase 2（管理 UX）、Phase 3（瀏覽器樹狀）不在本 plan，依 spec 各自另一輪。
