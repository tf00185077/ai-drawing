# Prompt Workbench UI 優化：詞條 chips 分頁 · 已選區 filter+九格分頁 · 加入組合

> 設計日期：2026-07-26
> 狀態：待實作（brainstorming 已核准）
> 前置：本設計修改 `2026-07-26-prompt-workbench-series-and-assembly-ordering-design.md` 交付的 UI（分類分區、自動排序、載入組合），後端仍零改動、輸出不變。

## 背景

前一版交付了系列標註、推薦排序（auto/manual）與「連續分區」已選檢視後，使用者提出三項 UI 優化：

1. 左側「加入 Prompt」的詞條選項目前是**全寬列表**（每個 `<li>` 佔滿一列），要改成**依字串長度的內容寬度 chips**，一頁最多 30 個、超過分頁。
2. 已選片段檢視目前是**常駐分類區塊（連續分區）、無分頁**；要改成**分類 filter + 每頁 3×3（9 張）分頁**，沒選 filter 顯示全部、一樣每頁 9 張。
3. 「載入組合」目前**取代**目前組合並綁定為可更新的 document；要改成**加入（append）**進現有組合，並套用既有自動排序。

## 設計原則（延續前版）

- **後端零程式改動**；送 ComfyUI 的最終逗號字串邏輯不變（append 只是多加片段、排序只動順序）。
- **comma-atomic 不變式**：最終文字 textarea 仍是單一 raw 逗號字串。
- 沿用既有 `CompositionState` / `WorkbenchFragment` / 排序狀態機（auto/manual）。

---

## 範圍一：#1 詞條 chips + 分頁（`PromptEntryBrowser.tsx`）

### 做什麼

把 `visibleEntries` 的全寬 `<ul>`（`space-y-2` 的 `<li>` 卡）改成 **flex-wrap 的內容寬度 chips**：

- 每個 chip 寬度依標籤（`promptEntryLabel(entry)` = `name_zh`）內容決定，`flex-wrap` 排列、有最大寬度上限避免超長字撐滿整列。
- 整顆 chip 可點即加入（呼叫既有 `onAddEntry(entry)`）；原始 `entry.prompt` 放到 chip 的 `title`（tooltip）。
- 保留 ⚠️ 可疑中文標記（`suspectReason`），以小圖示置於 chip 內。
- **分頁**：每頁最多 **30** 個 chip，超過顯示「上一頁／下一頁」與頁碼；`query`（搜尋）或 `selectedCategory` 改變時回第 1 頁。
- 搜尋輸入、正負切換、分類 chip 列、下方「自由文字」加入區都不變。

### 不做什麼

- 不改 `onAddEntry` / `onAddLiteral` 契約；不改詞庫資料。
- chip 不再常駐顯示 prompt 字串（移到 tooltip）——已與使用者確認可接受。

---

## 範圍二：#2 已選區 filter + 3×3 分頁（`PromptComposerPanel.tsx`）

### 做什麼

移除常駐「分類區塊（連續分區）」渲染，改為 **filter + 九格分頁**：

- **filter chip 列**（面板卡片區上方）：`[全部]` 加上目前**有被選到的分類**（依分類 order），literal 片段歸為 `[自訂文字]`。預設「全部」。點某分類 → 只顯示該分類的已選片段；點「全部」→ 顯示全部。
- **卡片網格固定 3 欄**，每頁最多 **9 張**（3×3），提供「上一頁／下一頁」與頁碼。切換 filter 時回第 1 頁。
- 卡片依**目前真實輸出順序**（`state.fragments` 全域順序）排列；套 filter 只是取子集、保序。
- 每張卡新增一個小的**分類標籤**（因為沒有區塊標題了，仍看得出屬哪類；literal 顯示「自訂文字」）。
- 卡片保留：內容編輯、權重、上移/下移、刪除。上移/下移作用於**全域順序**；`第 N 段` 與 disabled 邊界用全域 index（`state.fragments.indexOf`）。在「全部」檢視下所見即所得（無 grouping，視覺順序＝全域順序），前版 Issue 1 的 desync 在此消失；套分類 filter 時移動可能跨過被隱藏的卡（可接受，通常在「全部」檢視排序）。
- 保留 `arrangement` 狀態列、「重新套用推薦排序」按鈕、以及最終文字 textarea（＋selection 保留邏輯）不變。
- filter 與 page 狀態各 polarity 獨立（面板自身 local state 即可）。

### 元件邊界變更

- Panel 需要一份「目前有哪些分類（含顯示名與 order）」來建 filter chip 列，並需 `categoryInfoOf` 給每張卡的分類標籤。沿用前版已傳入的 `categoryInfoOf` prop。
- 移除前版 `groupFragmentsByCategory`（連續分區用）與其測試；新增純函式 `distinctCategoriesOf(fragments, categoryInfoOf)` 回傳依 order 排序、去重的分類清單（含 `{ key, displayName, order }`，literal 以 `__literal__`/「自訂文字」表示，排最後）供 filter chip 列使用。
- Filtering 與分頁在 Panel 內以 local state 完成，不動 `CompositionState`。

---

## 範圍三：#3 加入組合（append）（`CombinationToolbar.tsx` + `PromptWorkbench.tsx`）

### 做什麼

- Toolbar 按鈕「載入組合」改名「**加入組合**」；行為由取代改為 **append**。
- Workbench 新增 append 流程（取代 `loadCombination` 的取代語意）：
  1. 讀取選中組合（`getPromptCombination`），解析 entry 顯示名（沿用 `resolveEntryNames`）。
  2. 反序列化其 positive/negative 片段後，**接到**目前對應 lane 尾端（沿用 append 語意）。
  3. **自動去重**：跳過與目標 lane 內**已存在**的同來源 entry ref（同 `polarity/category_id/entry_id`）重複者，保留既有第一個；literal 一律加入。
  4. 加入後套既有排序狀態機：`auto` lane → `sortFragmentsByRecommendation` 重排；`manual` lane → 維持尾端。
  5. **清掉目前 document 身分**：`document` 重置為 blank（id/revision/etag/metadata/blockingDiagnostics 皆空），並標記 `dirty=true` → 結果是未儲存草稿；只能「另存新組合」。
  6. 顯示載入組合帶回的 warnings（修復／缺件／archived）。
- 因為是「加」不是「取代」，**移除**原本 dirty 時的取代確認（`canReplace`）於此路徑；append 是純附加，不會遺失現有內容。
- 「建立空白組合」保留（要從零開始 = 空白 → 加入）。

### 去重實作

新增純函式 `appendFragmentsDeduped(target: CompositionState, incoming: WorkbenchFragment[], idFactory)`：對每個 incoming 片段，若為 entry 且其 `source` 的 `(polarity, categoryId, entryId)` 已存在於 `target` 或先前已加入者，跳過；literal 一律加入；回傳新的 `CompositionState`（走既有 `rebuild`）。Workbench append 後再依 lane arrangement 決定是否 `sortFragmentsByRecommendation`。

### document 身分處理

append 後 `setDocument(blankDocument())`（但 `dirty: true`），並保留 append 帶回的 warnings 於一個顯示欄位（可用既有 `document.warnings` 承載，於 blank 基礎上填入）。因為身分清空，`更新目前組合` 會因 `document.id` 為 null 而 disabled，符合「未儲存草稿」語意。

---

## 資料流與元件邊界（變更摘要）

```
PromptEntryBrowser
  - local state: query, literal, + NEW page（chips 30/頁）
  - 渲染 flex-wrap chips（label＋⚠️＋tooltip=prompt），click=onAddEntry

PromptComposerPanel
  - props 不變（title, state, arrangement, categoryInfoOf, onReapplySort, 行為回呼）
  - local state: NEW filterKey（"__all__" | categoryId | "__literal__"）, NEW page（9/頁）
  - 用 distinctCategoriesOf 建 filter chip 列；用 categoryInfoOf 給每卡分類標籤
  - 移除 groupFragmentsByCategory 渲染，改 filter+分頁的 flat 3 欄網格
  - 最終文字 textarea + selection 保留邏輯不變

PromptWorkbench
  - 新增 appendCombination（取代 loadCombination 的取代行為）：
    getPromptCombination → resolveEntryNames → deserialize →
    appendFragmentsDeduped 進各 lane → 依 arrangement 排序 →
    setDocument(blank, dirty=true, warnings)
  - actions()/arrangement/rankOf/categoryInfoOf 沿用前版

CombinationToolbar
  - onLoad 按鈕文案改「加入組合」；props 契約不變（onLoad 綁到 appendCombination）

compositionState.ts
  - 移除 groupFragmentsByCategory（+ FragmentGroup 若不再他用則一併移除）與其測試
  - 新增 distinctCategoriesOf、appendFragmentsDeduped（皆走 rebuild）
  - sortFragmentsByRecommendation 不變
```

## 測試

- **compositionState.test.ts**
  - `appendFragmentsDeduped`：跳過已存在同來源 ref、保留 literal、跨 polarity 不誤判、輸出 `text` 為單一逗號串、保序。
  - `distinctCategoriesOf`：依 order 去重排序、literal 歸「自訂文字」排最後、空狀態。
  - 移除舊 `groupFragmentsByCategory` 測試。
- **PromptEntryBrowser.test.tsx**：chips 內容寬度渲染、tooltip=prompt、⚠️、每頁 30 上限與分頁、搜尋/切分類回第 1 頁、click 觸發 `onAddEntry`。
- **PromptComposerPanel.test.tsx**：filter chip 列只列出現有分類、選分類只顯示該類、預設全部、每頁 9 與分頁、每卡分類標籤、最終文字值不因 filter/分頁改變；更新既有 grouping/pagination 相關斷言。
- **PromptWorkbench.test.tsx**：加入組合 append（不清空現有）、去重、加入後 auto lane 重排、document 身分清空且 dirty、更新目前組合 disabled。
- 回歸：`tsc --noEmit`、Vite build、`git diff --check`。

## 明確不做（YAGNI）

- 不動後端 / API / schema / MCP。
- 不保留純取代式「載入」（取代 = 空白 + 加入）。
- 不做跨組合的衝突偵測（去重僅同來源 ref）。
- filter 只做「單選分類」；不做多選或關鍵字 filter。

## 與前版的相容性

- 前版 `groupFragmentsByCategory` 與其測試被本版移除；`sortFragmentsByRecommendation`、`rankOf`、`categoryInfoOf`、arrangement 狀態機沿用不變。
- 前版分類 `order`（研究版）與品質詞 `name_zh` 系列標註不受影響。
