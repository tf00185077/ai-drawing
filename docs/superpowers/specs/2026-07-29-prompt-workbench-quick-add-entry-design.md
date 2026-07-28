# Prompt Workbench 快速新增自訂詞條設計

> 設計日期：2026-07-29
> 狀態：待實作（brainstorming 已核准）

## 背景與動機

目前要新增一個 Prompt Library 詞條，只能到「分類詳情頁」對**已進入的那個分類**用 `PromptEntryEditor` 新增。使用者希望在**工作台組裝 prompt 的地方**就有一個便捷入口：**選擇該詞條屬於哪一層分類（樹的任一層）＋輸入中文名＋輸入英文 prompt**，即可把自訂詞條存進詞庫。

## 設計原則

- **純前端**：沿用既有 `PUT /api/prompt-library/categories/{polarity}/{category_id}/entries/{entry_id}`（`putPromptEntry`），不改後端/API/schema。
- **低摩擦**：只讓使用者填「分類＋中文＋英文」，其餘欄位自動。
- **不覆蓋既有資料**：自動產生的 slug 若與同分類既有詞條撞名，加後綴避免 `PUT` 覆蓋。
- **comma-atomic**：一個詞條的英文 prompt 必須是單一、不含逗號的原子。

## 使用者流程

1. 工作台左側「加入 Prompt」面板內出現「新增詞條」小表單。
2. 使用者選分類（目前 polarity 的分類縮排樹）、輸入中文名稱、輸入英文 prompt，按「新增到詞庫」。
3. 系統把詞條存入該分類；成功後該詞條立即可在瀏覽器被瀏覽/搜尋/手動加入。**不自動加入目前組合**。

## 表單（`PromptEntryBrowser`）

- **分類選擇器**：`<select>`，選項為**目前 `activePolarity`** 的未封存分類，以 `orderedCategoryRows` 縮排呈現（任一層皆可選）。預設空（未選）。
- **中文名稱** 輸入（對應 `name_zh`）。
- **英文 prompt** 輸入（對應 `prompt`）。
- 「新增到詞庫」按鈕；本地顯示 submitting / 錯誤 / 成功訊息。
- **前端驗證**：分類已選、中文與英文皆非空、英文不含逗號、slug 化後非空；否則顯示對應提示。
- 對外新增一個 prop：`onCreateEntry(category: BrowserCategory, input: { name_zh: string; prompt: string }): Promise<void>`——成功 resolve、失敗 reject（Error message 供表單顯示）。表單 `await` 之並管理本地狀態。

## 送出與自動欄位（`PromptWorkbench.onCreateEntry`）

1. **取當前分類狀態**：先 `getPromptCategory(polarity, categoryId)` 取該分類目前的 `revision`、`etag` 與**既有詞條 id 清單**（用於去重與樂觀鎖，避免 stale catalog 造成撞名覆蓋或 409）。
2. **產生 slug**：`slugifyEntryId(prompt, existingIds)`（純函式）——英文小寫、非 `a-z0-9` 轉 `-`、收斂連續與首尾 `-`；若與 existingIds 撞名則附 `-2`、`-3`…；slug 化為空則丟出可讀錯誤。
3. **自動欄位**：`description_zh = name_zh`；`order = 10`；`aliases = []`；`keywords = []`。
4. **寫入**：`putPromptEntry(polarity, categoryId, slug, { name_zh, description_zh, prompt, aliases, keywords, order, expected_revision: category.revision, expected_etag: etag })`。
5. **comma 檢查**：英文含逗號在表單即擋（不進到 `onCreateEntry`）；`onCreateEntry` 亦防禦性再查一次。
6. **成功後刷新**（讓新詞條可見/可搜尋，但不加入組合）：
   - 把新詞條併入工作台的 `allEntries`（跨樹搜尋資料）。
   - 若使用者目前正停在該分類（`category` state 為它），重新 `openCategory` 以刷新該分類詞條清單。
   - 顯示成功訊息。
7. **失敗**：`getPromptCategory`/`putPromptEntry` 的錯誤（含 409 concurrency、後端驗證）以 `message（hint）` reject，表單顯示。

## 純函式

`slugifyEntryId(prompt: string, existingIds: readonly string[]): string`
- `base = prompt.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "")`
- 若 `base === ""` → 丟出 `Error("無法從英文產生 ID，請確認英文內容")`（或回傳空字串由呼叫端擋；實作採丟錯較明確）。
- 若 `base` 不在 existingIds → 回 `base`；否則找最小的 `${base}-${n}`（n≥2）不在 existingIds 者回傳。

## 元件邊界與資料流

```
PromptEntryBrowser
  - 新增 local state: newCategoryId, newNameZh, newPrompt, creating, createError, createSuccess
  - 分類 <select>：orderedCategoryRows(polarityCategories)
  - 提交 → 驗證 → await onCreateEntry(selectedCategory, { name_zh, prompt })
           成功清空欄位 + 成功訊息；失敗顯示錯誤
  - 既有 props/行為（drill-down、search、加入既有詞條）不變

PromptWorkbench
  - onCreateEntry(category, input):
      getPromptCategory → slugifyEntryId(input.prompt, existingIds)
      → putPromptEntry(...)
      → 併入 allEntries；若 category 為目前開啟者則 openCategory 重載
  - 既有 addEntry/browser wiring 不變

promptLibraryApi
  - 沿用 getPromptCategory、putPromptEntry（無新增 API）
```

## 測試策略

- **純函式 `slugifyEntryId`**（vitest）：基本 slug 化、非 ascii/符號、撞名加後綴、連續撞名、slug 為空丟錯。
- **`PromptEntryBrowser`**（vitest）：表單驗證（未選分類、空欄、含逗號英文各自擋並提示）、成功時呼叫 `onCreateEntry` 帶正確 `(category, {name_zh, prompt})` 並於 resolve 後清空、reject 時顯示錯誤訊息；不影響既有 drill-down/search 測試。
- **`PromptWorkbench`**（vitest）：`onCreateEntry` 呼叫 `getPromptCategory` 後以去重後 slug 呼叫 `putPromptEntry`（含 expected_revision/etag、description_zh=name_zh、order 預設）；成功後新詞條進入 allEntries（可被搜尋）且**未**加入組合；後端錯誤被 reject。
- 回歸：`tsc --noEmit`、Vite build、全前端 vitest。

## 明確不做（YAGNI）

- 不在此表單建立新分類（選現有層；建分類仍在分類管理頁）。
- 不自動把新詞條加入目前組合（依決策：只存入詞庫）。
- 不提供別名/關鍵字/自訂 order/自訂 ID（詳情頁 `PromptEntryEditor` 已可補齊）。
- 不改後端、API、schema、MCP。
