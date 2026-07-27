# Prompt Library 任意深度分類樹（parent_id）設計

> 設計日期：2026-07-27
> 狀態：待實作（brainstorming 已核准）。實作分三階段；本 spec 涵蓋全貌，plan/實作先做 Phase 1。

## 背景與動機

目前 Prompt Library 的分類是**單層扁平**：一個分類直接裝 entries，沒有父子。使用者希望能自行決定分類的層次深度，而且**每條分支深度可以不同**：

- 角色：`角色與作品 → 女 → 系列作品(LoveLive!) → 第幾代`（深 3~4 層）
- 服裝：`服裝 → 上衣 / 下身 / 內衣 / 內褲`（淺 1~2 層）

需求同時包含「使用者新增分類、新增詞彙」的管理 UX，以及工作台左側瀏覽的 UX。

## 核心設計原則：身分不變，只加「父連結」

詞的身分是 `(polarity, category_id, entry_id)` 這組三元組，被寫死在**每個已存組合（combination）的片段 ref、comma-atomic provenance、composer 解析、API 路由、MCP 工具、前端定址**。因此本設計**刻意不改這組身分**：

- 分類只多一個**選填 `parent_id`**（指向另一個同 polarity 分類）。`parent_id` 是「分類 → 父分類」的**導覽/呈現連結**，不是詞的身分。
- 結果：**組合、provenance、comma-atomic、composer、生圖、輸出字串——全部不動、零 migration**。現有分類 `parent_id` 預設空、自動成為 root，完全向後相容。
- 一個分類**可同時擁有自己的詞彙與子分類**（深度由使用者自行決定，想在哪層停就在哪層放詞）。

明確**不採用**「三層/巢狀 ref」方案（`category → sub-category → entry` 的四元組身分），因為它會重新動到剛穩定的持久化身分並強制全面 migration，成本與風險最大。

## 資料模型

`backend/app/core/prompt_library_models.py`：

- `PromptCategory` 新增欄位 `parent_id: Slug | None = None`。
- `PromptCategorySummary`（catalog wire DTO，`backend/app/schemas/prompt_library.py` 與前端 `types/api.ts`）新增 `parent_id: str | None`。
- 分類寫入請求（`PromptCategoryWriteRequest`）新增選填 `parent_id`。

單一 `PromptCategory` 檔驗證不變（無法看見其他分類）；**樹的完整性在「掃描全部分類 / 組 catalog」時檢查**。

## 樹的建立與韌性（寬進嚴出）

- **讀取（catalog 組樹）寬容**：以全部分類的 `parent_id` 建森林。若某分類的 `parent_id` 懸空（父不存在）、指向不同 polarity、或造成環，將該分類**降級為 root** 並在 catalog 回應附一則結構化 `warning`（`code + message + hint + details{category_id}`）。**絕不因單一壞連結讓整個 library 無法載入**。
- **寫入 parent 嚴格**：`PUT` 分類帶 `parent_id` 時，後端驗證：
  - 父分類存在且同 polarity；
  - 不可指向自己；
  - 從擬定父分類往上走不可回到本分類（**防環**）。
  違反則回結構化 4xx（不寫檔）。
- Archived 父分類：允許設定與載入（樹照建），但 archived 的傳遞語意沿用既有 entry/category archived 警告，不在本 spec 擴充。

## 組裝排序：依根祖先為主的路徑排序

- 每個分類的 `order` 解讀為「**同層兄弟之間**的排序」（root 之間、或同一父之下的子分類之間）。
- 一個詞的**組裝排序鍵** = 從 root 到該詞所在分類、逐層的 `order` 串成陣列，末端接該詞自己的 `order`：
  ```
  rankKey(entry) = [order(root), order(level2), …, order(leafCategory), order(entry)]
  ```
  以**字典序**比較（逐元素比大小；較短者在相同前綴下視為較前）。
- 效果：**同一大類的詞不管多深都聚在一起**（例如所有角色詞都在最前段），支線內再依各層 order 細排。
- **向後相容**：扁平分類都是 root，路徑長度為 1，`rankKey = [order(category), order(entry)]`，等價於現行 `order(category)*100000 + order(entry)` 的相對順序，行為不變。

前端變更：
- `PromptWorkbench.rankOf(fragment)` 從回傳 `number` 改為回傳 `number[]`（該詞分類的祖先路徑 order 陣列 + 詞的 order）。literal / 無法解析分類者回傳一個「極大」哨兵（例如 `[Number.POSITIVE_INFINITY]`），排最後。
- `compositionState.sortFragmentsByRecommendation` 從 `left.rank - right.rank` 改為**陣列字典序比較器**，維持原本以原始 index 為 tie-break 的穩定排序，並仍走 `rebuild`（輸出仍是單一逗號字串、只動順序）。
- 前端需要「分類 → 祖先路徑 order」的查表：由 catalog 的 `parent_id + order` 於載入時建樹一次，快取為 `categoryPathOrders: Map<categoryKey, number[]>`。

## UX（分三階段，各自可獨立上線）

### Phase 1 — 地基（後端 + 排序），非破壞

- 後端：`parent_id` 欄位、寫入防環/存在/同 polarity 驗證、catalog 讀取容錯建樹 + 降級 warning、catalog 回傳 `parent_id`。
- 前端：`types/api.ts` 加 `parent_id`；載入時建樹並算 `categoryPathOrders`；`rankOf` 改路徑陣列；`sortFragmentsByRecommendation` 改字典序比較。
- 畫面**暫時維持扁平**（尚無 UI 樹）；但排序已支援階層。所有現有分類＝root → 行為不變。**可獨立上線。**

### Phase 2 — 管理 UX（`PromptCategoryManagement` / `PromptCategoryDetail`）

- **新增分類表單**：加**選填「父分類」選擇器**（同 polarity 的分類樹；可選「（無，作為頂層）」）。送出時帶 `parent_id`。
- **分類管理清單**：由扁平卡片改為**縮排樹**呈現（依 parent 巢狀、每層依 order），保留既有 polarity / active-archived 切換與詞條數。
- **分類詳情頁**：顯示**麵包屑路徑**（root › … › 本分類）；新增可編輯的**父分類**欄位（搬移分類，寫入時同樣防環）。
- **詞條增刪改幾乎不變**：`PromptEntryEditor` 與 entry CRUD 沿用；可在任一層分類（含同時有子分類的中間層）新增詞。

### Phase 3 — 工作台瀏覽器樹狀（`PromptEntryBrowser`）

- 左側「加入 Prompt」由扁平分類 chip 列改為**鑽入式 + 麵包屑**：
  - 進入一個分類即顯示它的**子分類（資料夾 chip，可再鑽入）** 與**它自己的詞（chips，30/頁沿用）**。
  - 麵包屑可回上層 / 回頂層。
- **搜尋跨整棵樹**：輸入關鍵字時攤平該 polarity 全樹，列出命中詞條並標示其分類路徑，點擊即加入。
- 正負切換沿用。

## 明確不做（YAGNI）

- 已選區的 3×3 filter **維持依詞的實際分類 filter**，不做「選父節點＝含所有子孫」的上捲（日後需要再議）。
- 不改詞的身分/定址（不走三層 ref）。
- 不做分類的拖放排序（沿用 `order` 數字欄位）。
- 不對 archived 傳遞語意做額外擴充。

## 測試策略（各階段對應）

- **Phase 1**
  - 後端：`parent_id` 寫入驗證（父不存在／跨 polarity／自我／成環 → 結構化錯誤且不寫檔）；catalog 容錯（懸空/成環 parent → 降級 root + warning，library 仍載入）；catalog 回傳含 `parent_id`。
  - 前端純函式：`sortFragmentsByRecommendation` 字典序（深樹聚合、支線細排、扁平向後相容、literal 殿後、穩定 tie-break）；「分類 → 路徑 order」建表。
  - 回歸：既有扁平排序輸出不變；`tsc`、Vite build。
- **Phase 2**：新增分類帶 parent、清單樹呈現、詳情搬移防環的元件/整合測試。
- **Phase 3**：瀏覽器鑽入/麵包屑/跨樹搜尋的元件測試。

## 相依與階段順序

Phase 1（地基）→ Phase 2（管理）→ Phase 3（瀏覽器）。每階段結束皆為可運作、可獨立驗證的軟體。本 spec 為三階段的單一設計來源；每階段各自有自己的 implementation plan 與執行循環。
