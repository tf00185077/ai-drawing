# 分類管理：編輯詞條時移動到其他分類

> 設計日期：2026-07-29
> 狀態：待實作（brainstorming 已核准）

## 背景與動機

分類詳情頁（`PromptCategoryDetail`）可以在**單一分類內**新增/編輯詞條，但**無法把詞條移到別的分類**。目前後端只有 `save_entry`（寫入單一分類）與 `archive`（軟封存，仍留在原分類），**沒有「移動」也沒有硬刪除**。使用者希望在**編輯詞條時**能選「所屬分類」，存檔即把詞條（連同這次的欄位修改）搬到目標分類。

## 決策（已確認）

1. **操作方式**：編輯表單加「所屬分類」下拉；存檔時分類若不同＝**移動**（含這次的中/英文等欄位修改）。
2. **ID 撞名**：目標分類已有相同 entry id 時，**擋下並提示、不覆蓋**。
3. **同 polarity 限定**：正向詞條只能搬到正向分類（反之亦然）；目標下拉只列同 polarity 的分類樹、排除自己。

## 核心限制與安全

- 詞條身分是 `(polarity, category_id, entry_id)`。移動會改 `category_id`。目前 **5 個組合皆為 literal、不引用任何 entry**，故移動不影響組合。
- 移動需**原子**：在單一 store 鎖內，從來源分類移除並寫入目標分類，兩邊各 bump revision。
- 樂觀鎖以**來源分類**的 `revision/etag` 為準（詳情頁載入來源分類時已有）。

## 後端

### Schema（`backend/app/schemas/prompt_library.py`）

新增 `MoveEntryRequest(EntryWriteRequest)`：繼承 `EntryWriteRequest`（`name_zh/description_zh/prompt/aliases/keywords/order` ＋ `expected_revision/expected_etag`），新增 `to_category_id: Slug`。`expected_revision/etag` 對應**來源**分類。

### Provider / Writer（`prompt_library.py` / `prompt_library_writes.py`）

新增 `move_entry(polarity, from_category_id, entry_id, request: MoveEntryRequest) -> WriteResponse`，於 `self.store.locked()` 內：

1. `to_category_id == from_category_id` → 直接走既有 `save_entry` 語意（等同原地編輯）。
2. 讀來源分類；`assert_precondition`（來源 `revision/etag` vs request）。
3. 找不到 `entry_id` → `PromptLibraryError`（entry_not_found）。
4. 讀目標分類；不存在 → error（target_category_not_found）。
5. 目標分類已存在 `entry_id` → error（`entry_id_conflict`，422）不寫檔。
6. `prompt` 驗證同 `save_entry`（非空、不含逗號）。
7. 建立移動後詞條：套用 request 欄位；`revision=1`（於目標為新項）、`archived=False`。
8. 來源：移除該 entry、`revision+1`、寫檔。
9. 目標：加入該 entry、依 `(order, id)` 排序、`revision+1`、寫檔。
10. 回 `WriteResponse`（含 `entry` 與目標 `VersionedCategory`）。

> 不重指組合 ref（組合皆 literal）；如未來有引用，移動後該 ref 會 fallback 至 snapshot（既有語意）。

### API（`backend/app/api/prompt_library.py`）

新增 `POST /categories/{polarity}/{category_id}/entries/{entry_id}/move`（`category_id` 為來源），body `MoveEntryRequest`，回 `WriteResponse`。錯誤沿用 `code + message + hint`。

## 前端

### API 包裝（`promptLibraryApi.ts`）

`moveEntry(polarity, fromCategoryId, entryId, input)`：`POST` 上述路由，body 帶 `to_category_id` 與 entry 欄位＋concurrency token。型別 `PromptMoveEntryRequest = PromptEntryWriteRequest & { to_category_id: string }`。

### 詞條編輯器（`PromptEntryEditor.tsx`）

- 新增選填 props：`categories: { id: string; name_zh: string; parent_id?: string | null; order: number }[]`（同 polarity）與 `currentCategoryId: string`。
- 表單加「所屬分類」`<select>`：以 `orderedCategoryRows(categories)` 縮排呈現，預設 `currentCategoryId`。
- `EntryEditorValue` 擴充 `categoryId: string`（送出時帶所選目標分類）。
- create 模式維持在目前分類（不顯示或鎖定為目前分類）。

### 詳情頁（`PromptCategoryDetail.tsx`）

- 傳 `categories`（來自已載入的 catalog、篩同 polarity）與 `currentCategoryId` 給編輯器。
- `saveEntry(value)`：若 `value.categoryId === currentCategoryId` → 既有 `putPromptEntry`；否則 → `moveEntry(polarity, currentCategoryId, value.id, { to_category_id: value.categoryId, ...value.fields, ...token })`。
- 成功後重載分類與 catalog（新詞條已不在本分類，本頁清單會少一筆）；顯示成功訊息。撞名/錯誤顯示 `message（hint）`。

## 測試

- **後端**（`backend/tests/test_prompt_library_move.py`）：成功移動（來源少一筆、目標多一筆、兩邊 revision+1、可帶欄位修改）、`to==from` 走原地編輯、entry 不存在、目標不存在、目標撞 ID → 422 不寫檔、來源 revision 過期 → 409。
- **前端**：`PromptEntryEditor` 顯示分類下拉、預設目前分類、送出帶 `categoryId`；`PromptCategoryDetail` 於選不同分類時呼叫 `moveEntry`（帶正確 from/to 與欄位）、相同分類時走 `putPromptEntry`；撞名錯誤顯示。`promptLibraryApi.moveEntry` 送對 URL 與 body。
- 回歸：全前端 vitest、`tsc`、build；後端 prompt-library 既有測試不受影響。

## 明確不做（YAGNI）

- 不做跨 polarity 移動（正↔負）。
- 不在編輯器內新建分類（選現有；建分類仍在分類管理頁）。
- 不重指組合 ref（組合皆 literal；未來需要再議）。
- 不改詞條 id（撞名擋下，由使用者處理）；不提供批次移動。
