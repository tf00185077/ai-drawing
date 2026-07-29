# 移動詞條到其他分類 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在分類詳情頁編輯詞條時，選「所屬分類」，存檔即把詞條（含這次的欄位修改）原子地搬到目標分類。

**Architecture:** 後端新增原子 `move_entry`（單一 store 鎖內：來源移除＋目標寫入、來源樂觀鎖、撞 id 擋下、同 polarity）。前端詞條編輯器加「所屬分類」下拉；詳情頁 `saveEntry` 依所選分類決定走 `putPromptEntry`（原地）或 `moveEntry`（搬移）。

**Tech Stack:** Python 3.11 + Pydantic + FastAPI（後端）；React 18 + TS + Vite + vitest（前端）。

## Global Constraints

- **同 polarity 限定**：正向詞條只能搬到正向分類（路由 `polarity` 同時約束來源與目標）。
- **不覆蓋**：目標分類已有相同 entry id → 回 422 `entry_id_conflict`、不寫檔。
- **原子**：來源移除與目標寫入在同一 `self.store.locked()` 內完成。
- **樂觀鎖**：以**來源**分類的 `expected_revision/expected_etag` 為準。
- **組合皆 literal**，移動不影響組合；不重指 ref。
- **後端測試用 Python 3.11**（`py -3.11`）；前端無 `user-event`，用 `fireEvent`。
- 驗證：後端 `cd backend && PYTHONUTF8=1 py -3.11 -m pytest <file> -q`；前端 `cd frontend && npx vitest run <file>`、`npx tsc --noEmit`、`npm run build`。

---

## File Structure

| 檔案 | 責任 | 動作 |
|---|---|---|
| `backend/app/schemas/prompt_library.py` | `MoveEntryRequest` | Modify（Task 1） |
| `backend/app/core/prompt_library_writes.py` | `move_entry` writer | Modify（Task 1） |
| `backend/app/core/prompt_library.py` | provider `move_entry`（ABC + impl） | Modify（Task 1） |
| `backend/app/api/prompt_library.py` | move 路由 | Modify（Task 1） |
| `backend/tests/test_prompt_library_move.py` | 後端測試 | Create（Task 1） |
| `frontend/src/types/api.ts` | `PromptMoveEntryRequest` | Modify（Task 2） |
| `frontend/src/components/prompt-library/promptLibraryApi.ts` | `moveEntry` | Modify（Task 2） |
| `frontend/src/components/prompt-library/PromptEntryEditor.tsx` | 「所屬分類」下拉 + `categoryId` | Modify（Task 2） |
| `frontend/src/pages/PromptCategoryDetail.tsx` | `saveEntry` 分支 + 傳 props | Modify（Task 2） |
| 對應 `*.test.*` | 測試 | Modify（Task 2） |
| `docs/PROGRESS.md` | 進度 | Modify（Task 3） |

---

## Task 1: 後端 `move_entry`（schema + writer + provider + route）

**Files:**
- Modify: `backend/app/schemas/prompt_library.py`, `backend/app/core/prompt_library_writes.py`, `backend/app/core/prompt_library.py`, `backend/app/api/prompt_library.py`
- Test: `backend/tests/test_prompt_library_move.py`（新建）

**Interfaces:**
- Produces: `MoveEntryRequest(EntryWriteRequest)` 加 `to_category_id: Slug`；`provider.move_entry(polarity, from_category_id, entry_id, request) -> WriteResponse`；`POST /api/prompt-library/categories/{polarity}/{category_id}/entries/{entry_id}/move`。

- [ ] **Step 1: 寫失敗測試**

新建 `backend/tests/test_prompt_library_move.py`：

```python
from __future__ import annotations
import json
from pathlib import Path
import pytest
from app.core.prompt_library import FilePromptLibraryProvider
from app.core.prompt_library_errors import PromptLibraryError
from app.schemas.prompt_library import MoveEntryRequest


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _cat(cid: str, entries: list[dict]) -> dict:
    return {"schema_version": 1, "id": cid, "polarity": "positive", "name_zh": cid,
            "description_zh": "d", "aliases": [], "keywords": [], "order": 10,
            "revision": 1, "archived": False, "entries": entries}


def _entry(eid: str, prompt: str) -> dict:
    return {"id": eid, "name_zh": eid, "description_zh": "d", "prompt": prompt,
            "aliases": [], "keywords": [], "order": 10, "revision": 1, "archived": False}


@pytest.fixture
def provider(tmp_path: Path) -> FilePromptLibraryProvider:
    root = tmp_path / "prompt_library"
    (root / "positive").mkdir(parents=True); (root / "negative").mkdir(); (root / "combinations").mkdir()
    _write(root / "manifest.json", {"schema_version": 2, "library_id": "default", "name": "T",
            "description_zh": "測試", "comma_atomic_version": 1, "comma_atomic_migration_required": False})
    _write(root / "positive" / "src.json", _cat("src", [_entry("dress", "dress"), _entry("skirt", "skirt")]))
    _write(root / "positive" / "dst.json", _cat("dst", [_entry("hat", "hat")]))
    return FilePromptLibraryProvider(root)


def _req(to: str, prompt: str = "dress", name: str = "洋裝", rev: int = 1) -> MoveEntryRequest:
    return MoveEntryRequest(to_category_id=to, name_zh=name, description_zh="d", prompt=prompt,
                            aliases=[], keywords=[], order=10, expected_revision=rev)


def test_move_removes_from_source_adds_to_dest_with_edits(provider):
    resp = provider.move_entry("positive", "src", "dress", _req("dst", name="洋裝(改)"))
    src = provider.get_category("positive", "src")
    dst = provider.get_category("positive", "dst")
    assert [e.id for e in src.category.entries] == ["skirt"]
    assert src.category.revision == 2
    moved = next(e for e in dst.category.entries if e.id == "dress")
    assert moved.name_zh == "洋裝(改)" and dst.category.revision == 2
    assert resp.entry.id == "dress"


def test_move_to_same_category_is_in_place_edit(provider):
    provider.move_entry("positive", "src", "dress", _req("src", name="原地改"))
    src = provider.get_category("positive", "src")
    assert next(e for e in src.category.entries if e.id == "dress").name_zh == "原地改"
    assert [e.id for e in src.category.entries] == ["dress", "skirt"]


def test_move_rejects_id_conflict_without_writing(provider):
    # give dst its own "dress" (dst rev 1->2); src is untouched (rev still 1)
    provider.save_entry("positive", "dst", "dress", _req("dst", prompt="dress", name="dst洋裝"))
    with pytest.raises(PromptLibraryError) as exc:
        provider.move_entry("positive", "src", "dress", _req("dst"))  # src expected_revision=1
    assert exc.value.status_code == 422
    # src still has dress (not written away)
    assert any(e.id == "dress" for e in provider.get_category("positive", "src").category.entries)


def test_move_entry_not_found(provider):
    with pytest.raises(PromptLibraryError) as exc:
        provider.move_entry("positive", "src", "ghost", _req("dst", prompt="ghost", name="無"))
    assert exc.value.status_code == 404


def test_move_target_not_found(provider):
    with pytest.raises(PromptLibraryError) as exc:
        provider.move_entry("positive", "src", "dress", _req("nope"))
    assert exc.value.status_code == 404


def test_move_stale_source_revision_409(provider):
    with pytest.raises(PromptLibraryError) as exc:
        provider.move_entry("positive", "src", "dress", _req("dst", rev=99))
    assert exc.value.status_code == 409
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd backend && PYTHONUTF8=1 py -3.11 -m pytest tests/test_prompt_library_move.py -q`
Expected: FAIL（`MoveEntryRequest` / `move_entry` 不存在）。

- [ ] **Step 3: 實作**

在 `schemas/prompt_library.py` 的 `EntryWriteRequest` 之後新增：
```python
class MoveEntryRequest(EntryWriteRequest):
    to_category_id: Slug
```

在 `prompt_library_writes.py`：頂部 import 加 `MoveEntryRequest`（與 `EntryWriteRequest` 並列）。在 `save_entry` 方法之後新增：
```python
    def move_entry(
        self,
        polarity: Polarity,
        from_category_id: str,
        entry_id: str,
        request: MoveEntryRequest,
    ) -> WriteResponse:
        if request.to_category_id == from_category_id:
            return self.save_entry(polarity, from_category_id, entry_id, request)
        if not request.prompt.strip():
            raise PromptLibraryError.blank_fragment(polarity=polarity, positions=[1])
        if "," in request.prompt:
            raise PromptLibraryError.comma_not_atomic(field="prompt")
        with self.store.locked():
            source = self.store.read_category(polarity, from_category_id)
            assert_precondition(
                exists=True,
                actual_revision=source.model.revision,
                actual_etag=source.etag,
                expected_revision=request.expected_revision,
                expected_etag=request.expected_etag,
            )
            if not any(item.id == entry_id for item in source.model.entries):
                raise PromptLibraryError(
                    code="entry_not_found",
                    message="The entry to move does not exist in the source category.",
                    hint="Reload the category and try again.",
                    status_code=404,
                    details={"category_id": from_category_id, "entry_id": entry_id},
                )
            dest_path = self.store.category_path(polarity, request.to_category_id)
            if not dest_path.exists():
                raise PromptLibraryError(
                    code="target_category_not_found",
                    message="The target category does not exist.",
                    hint="Pick an existing same-polarity category.",
                    status_code=404,
                    details={"to_category_id": request.to_category_id},
                )
            dest = self.store.read_category(polarity, request.to_category_id)
            if any(item.id == entry_id for item in dest.model.entries):
                raise PromptLibraryError(
                    code="entry_id_conflict",
                    message="The target category already has an entry with this id.",
                    hint="Rename the entry id or pick another category.",
                    status_code=422,
                    details={"entry_id": entry_id, "to_category_id": request.to_category_id},
                )
            moved = PromptEntry(
                id=entry_id,
                name_zh=request.name_zh,
                description_zh=request.description_zh,
                prompt=request.prompt,
                aliases=request.aliases,
                keywords=request.keywords,
                order=request.order,
                revision=1,
                archived=False,
            )
            source_entries = [item for item in source.model.entries if item.id != entry_id]
            source_category = source.model.model_copy(
                deep=True,
                update={"entries": source_entries, "revision": source.model.revision + 1},
            )
            self.store.replace_json(source.path, source_category)
            dest_entries = [*dest.model.entries, moved]
            dest_entries.sort(key=lambda item: (item.order, item.id))
            dest_category = dest.model.model_copy(
                deep=True,
                update={"entries": dest_entries, "revision": dest.model.revision + 1},
            )
            dest_etag = self.store.replace_json(dest.path, dest_category)
            affected = self._propagate_entry(polarity, request.to_category_id, moved)
        return WriteResponse(
            category=VersionedCategory(category=dest_category, etag=dest_etag),
            entry=moved,
            entry_revision=moved.revision,
            affected_combinations=affected,
        )
```

在 `prompt_library.py`：import 加 `MoveEntryRequest`。在抽象基底（`def save_entry(...) -> WriteResponse: ...` 附近）加抽象簽章：
```python
    def move_entry(
        self, polarity: Polarity, from_category_id: str, entry_id: str,
        request: MoveEntryRequest,
    ) -> WriteResponse: ...
```
在 `FilePromptLibraryProvider` 的 `save_entry` 實作之後加：
```python
    def move_entry(
        self, polarity: Polarity, from_category_id: str, entry_id: str,
        request: MoveEntryRequest,
    ) -> WriteResponse:
        self._guard()
        return self._writer.move_entry(polarity, from_category_id, entry_id, request)
```

在 `api/prompt_library.py`：import 加 `MoveEntryRequest`。在 `save_entry` 路由之後加：
```python
@router.post(
    "/categories/{polarity}/{category_id}/entries/{entry_id}/move",
    response_model=WriteResponse,
)
def move_entry(
    polarity: Polarity,
    category_id: str,
    entry_id: str,
    body: MoveEntryRequest,
    provider: PromptLibraryProvider = Depends(_provider),
) -> WriteResponse:
    return _call(provider.move_entry, polarity, category_id, entry_id, body)
```

- [ ] **Step 4: 執行測試確認通過**

Run: `cd backend && PYTHONUTF8=1 py -3.11 -m pytest tests/test_prompt_library_move.py -q`
Expected: PASS（6 passed）。

- [ ] **Step 5: 後端回歸**

Run: `cd backend && PYTHONUTF8=1 py -3.11 -m pytest tests/test_prompt_library_writes.py tests/test_prompt_library_api.py -q`
Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/prompt_library.py backend/app/core/prompt_library_writes.py backend/app/core/prompt_library.py backend/app/api/prompt_library.py backend/tests/test_prompt_library_move.py
git commit -m "feat(prompt-library): atomic move_entry endpoint (remove from source, add to dest)"
```

---

## Task 2: 前端 — API + 編輯器分類下拉 + 詳情頁分支

**Files:**
- Modify: `frontend/src/types/api.ts`, `frontend/src/components/prompt-library/promptLibraryApi.ts`, `frontend/src/components/prompt-library/PromptEntryEditor.tsx`, `frontend/src/pages/PromptCategoryDetail.tsx`
- Test: `frontend/src/components/prompt-library/promptLibraryApi.test.ts`, `PromptEntryEditor.test.tsx`, `frontend/src/pages/PromptCategoryDetail.test.tsx`

**Interfaces:**
- Consumes: Task 1 的 move 路由。
- Produces: `moveEntry(polarity, fromCategoryId, entryId, input)`；`EntryEditorValue` 加 `categoryId: string`；`PromptEntryEditor` 加 props `categories`/`currentCategoryId`。

- [ ] **Step 1: 型別 + API 包裝（含測試）**

在 `types/api.ts`（`PromptEntryWriteRequest` 之後）加：
```ts
export interface PromptMoveEntryRequest extends PromptEntryWriteRequest {
  to_category_id: string;
}
```
在 `promptLibraryApi.ts`（`putPromptEntry` 之後）加，並在頂部 import 型別加 `PromptMoveEntryRequest`：
```ts
export function moveEntry(
  polarity: PromptPolarity,
  fromCategoryId: string,
  entryId: string,
  input: PromptMoveEntryRequest,
): Promise<PromptLibraryWriteResponse> {
  const body = { ...categoryWriteBody(input), prompt: input.prompt, to_category_id: input.to_category_id };
  return requestJson<PromptLibraryWriteResponse>(
    `${API_ROOT}/categories/${segment(polarity)}/${segment(fromCategoryId)}/entries/${segment(entryId)}/move`,
    jsonWrite("POST", body),
  );
}
```
在 `promptLibraryApi.test.ts` 追加（沿用該檔 fetch mock 慣例）：
```ts
it("moveEntry POSTs to the move route with to_category_id + entry fields", async () => {
  const calls: { url: string; init?: RequestInit }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, init }); return { ok: true, json: async () => ({}) } as Response;
  }));
  const { moveEntry } = await import("./promptLibraryApi");
  await moveEntry("positive", "src", "dress", {
    to_category_id: "dst", name_zh: "洋裝", description_zh: "d", prompt: "dress",
    aliases: [], keywords: [], order: 10, expected_revision: 1,
  });
  expect(calls[0].url).toBe("/api/prompt-library/categories/positive/src/entries/dress/move");
  const body = JSON.parse(calls[0].init!.body as string);
  expect(body.to_category_id).toBe("dst");
  expect(body.prompt).toBe("dress");
});
```

- [ ] **Step 2: `PromptEntryEditor` 加「所屬分類」下拉**

在 `PromptEntryEditor.tsx`：
1. 頂部 import 加 `import { orderedCategoryRows } from "./categoryTree";`
2. `EntryEditorValue` 介面加 `categoryId: string;`。
3. `Props` 加：
```ts
  categories?: { id: string; name_zh: string; parent_id?: string | null; order: number }[];
  currentCategoryId?: string;
```
並在解構參數加入 `categories`, `currentCategoryId`。
4. state 加：`const [categoryId, setCategoryId] = useState(currentCategoryId ?? "");`
5. `submit()` 的 `onSubmit({...})` 物件加一個欄位：
```ts
      categoryId: mode === "create" ? (currentCategoryId ?? "") : (categoryId || currentCategoryId || ""),
```
6. 在「英文 prompt」欄位之後、僅 `mode === "edit"` 且有 `categories` 時，插入分類下拉：
```tsx
      {mode === "edit" && categories && categories.length > 0 && (
        <label className="block text-xs text-slate-400">所屬分類
          <select aria-label="詞條所屬分類" disabled={submitting} value={categoryId} onChange={(e) => setCategoryId(e.target.value)} className={inputClass}>
            {orderedCategoryRows(categories).map(({ category, depth }) => (
              <option key={category.id} value={category.id}>{`${"　".repeat(depth)}${category.name_zh}`}</option>
            ))}
          </select>
          <span className="mt-1 block text-slate-500">改選其他分類後儲存＝把此詞條搬過去。</span>
        </label>
      )}
```

- [ ] **Step 3: 詳情頁 `saveEntry` 分支 + 傳 props**

在 `PromptCategoryDetail.tsx`：
1. import 的 promptLibraryApi 加 `moveEntry`。
2. `saveEntry` 改為：
```tsx
  function saveEntry(value: EntryEditorValue) {
    const operation =
      value.categoryId && value.categoryId !== currentCategoryId
        ? () => moveEntry(currentPolarity, currentCategoryId, value.id, { to_category_id: value.categoryId, ...value.fields, ...token })
        : () => putPromptEntry(currentPolarity, currentCategoryId, value.id, { ...value.fields, ...token });
    void mutate(operation, { closeEditor: true, showAffectedCombinations: true });
  }
```
3. 兩個 `<PromptEntryEditor .../>`（create 與 edit）都加 props：`categories={samePolarityCategories} currentCategoryId={currentCategoryId}`。（`samePolarityCategories` 已於檔內定義。）

- [ ] **Step 4: 測試（editor + detail）**

Run: `cd frontend && cat src/components/prompt-library/PromptEntryEditor.test.tsx`
Run: `cd frontend && cat src/pages/PromptCategoryDetail.test.tsx`

`PromptEntryEditor.test.tsx`：
- 既有 render 的 onSubmit 斷言若比對整個 value，補上 `categoryId`。
- 新增：edit 模式 + `categories`/`currentCategoryId` → 顯示「所屬分類」下拉、預設 currentCategoryId；改選後 onSubmit 的 `categoryId` 為新值。

`PromptCategoryDetail.test.tsx`：
- 新增：編輯詞條、把「所屬分類」改成別的分類、儲存 → 呼叫 `moveEntry`（帶正確 from `currentCategoryId`、`to_category_id`、entry 欄位）；分類相同時仍呼叫 `putPromptEntry`。
- 既有測試若因 `getPromptCatalog`/新 props 需要，補 mock（詳情頁已載 catalog）。

- [ ] **Step 5: 全前端測試 + typecheck + build**

Run: `cd frontend && npx vitest run && npx tsc --noEmit && npm run build`
Expected: 全 PASS、typecheck 乾淨、build 成功、pristine。**務必跑整套**。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types/api.ts frontend/src/components/prompt-library/promptLibraryApi.ts frontend/src/components/prompt-library/PromptEntryEditor.tsx frontend/src/pages/PromptCategoryDetail.tsx frontend/src/components/prompt-library/promptLibraryApi.test.ts frontend/src/components/prompt-library/PromptEntryEditor.test.tsx frontend/src/pages/PromptCategoryDetail.test.tsx
git commit -m "feat(prompt-library): move entry to another category from the editor"
```

---

## Task 3: 收尾驗證與進度更新

**Files:**
- Modify: `docs/PROGRESS.md`

- [ ] **Step 1: 總驗證**

Run:
```bash
cd backend && PYTHONUTF8=1 py -3.11 -m pytest tests/test_prompt_library_move.py tests/test_prompt_library_writes.py tests/test_prompt_library_api.py -q
cd frontend && npx vitest run && npx tsc --noEmit && npm run build
```
Expected: 後端相關全綠；前端測試全綠、typecheck、build 成功。

- [ ] **Step 2: `git diff --check`**

Run: `git diff --check`
Expected: 無輸出。

- [ ] **Step 3: 更新 `docs/PROGRESS.md`**

於檔案最上方新增：

```markdown
## 2026-07-29 分類管理：編輯時把詞條移到其他分類

- 後端新增原子 `move_entry` 端點（`POST .../entries/{id}/move`）：單一 store 鎖內把詞條從來源分類移除、寫入目標分類，兩邊 bump revision；以來源分類 revision/etag 樂觀鎖；目標撞相同 entry id → 422 不寫檔；同 polarity 限定；`to==from` 時等同原地編輯。
- 前端詞條編輯器加「所屬分類」下拉（同 polarity 分類縮排樹）；詳情頁存檔時若選了不同分類即呼叫 move（連同這次的中/英文修改一起搬過去），相同分類則照舊 `putPromptEntry`。
- 組合皆 literal、不受影響。驗證：後端 pytest、前端 vitest 全綠，`tsc` 與 Vite build 通過。
```

- [ ] **Step 4: Commit**

```bash
git add docs/PROGRESS.md
git commit -m "docs(progress): move entry between categories"
```

---

## Self-Review 對照

- **spec 後端 move_entry（原子、樂觀鎖、撞名 422、to==from 原地、同 polarity）** → Task 1。✅
- **spec 前端編輯器分類下拉 + 詳情頁分支** → Task 2。✅
- **spec 測試（後端各情境、前端 API/editor/detail）** → Task 1 Step 1 + Task 2 Step 1/4。✅
- **不覆蓋/同 polarity/組合不受影響** → Global Constraints + Task 1 邏輯與測試。✅
- **型別一致**：`MoveEntryRequest.to_category_id`、`move_entry(polarity, from_category_id, entry_id, request)`、`moveEntry(...)`、`EntryEditorValue.categoryId`、`PromptEntryEditor` props 在 Task 1/2 一致。✅
- **每 task 後 repo green**：後端（1）→ 前端 editor+detail+api 一起改（2，避免 prop/型別跨 task 破 tsc）→ 收尾（3）。✅
