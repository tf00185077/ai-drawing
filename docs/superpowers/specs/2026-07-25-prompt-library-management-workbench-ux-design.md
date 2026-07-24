# Prompt Library 管理邊界、組合載入與工作檯編輯 UX 設計

- 日期：2026-07-25
- 狀態：使用者已於 2026-07-25 核准，進入實作計畫
- 相關路徑：`/prompt-library/workbench`、`/prompt-library/categories`、`/prompt-library/categories/:polarity/:categoryId`

## 1. 背景

目前 Prompt Library 前端把兩種責任混在 Prompt Workbench：使用者既能選取詞條建立 Prompt，也能新增、編輯及封存來源詞條。分類管理頁則只有分類清單與新增分類，無法進入既有分類管理內容。

工作檯的「最終文字」還把輸入草稿與結構化 fragments 存在同一份 state。每次鍵盤輸入都會拆分、裁切並重建文字。使用者輸入尾端逗號或空白時，字元會立即消失；在中間插入或刪除文字時，程式也可能按陣列位置把既有 Library reference 配到錯誤內容。

Backend 已支援列出及讀取組合，但工作檯只有儲存入口，沒有載入既有組合的 UI。使用者手動輸入既有組合 ID 時不會載入內容，卻可能把目前畫布覆寫到該 ID。

## 2. 本設計覆蓋的舊決策

本文件更新下列既有設計：

- `2026-07-17-prompt-library-workbench-design.md` 中「可在工作檯把自由文字存成來源詞條」的安排。
- `2026-07-24-prompt-library-bilingual-crud-design.md` 中「詞條 CRUD 長在工作檯」的安排。

中文品質提示與完整詞條欄位仍保留。只有 CRUD 入口移至分類管理。Prompt Workbench 不再寫入分類或詞條主資料。

## 3. 資料所有權

### 3.1 分類與詞條

分類 JSON 與分類內 entries 是 Prompt Library 主資料。只有分類管理頁可建立、更新、封存及恢復這些資源。

Prompt Workbench 對分類與詞條只有讀取權。將詞條加入組合後，工作檯操作的是組合內的副本：

- 未修改的來源詞條保持 `kind=entry` 與原始 reference。
- 使用者修改副本文字後，該片段成為 `kind=literal`。
- 修改副本不得更新來源分類 JSON。
- UI 應把已脫離來源的片段標示為「自訂副本」。

### 3.2 組合

組合是工作檯自己的文件。Prompt Workbench 可以：

- 建立新組合；
- 載入既有組合；
- 更新目前組合；
- 另存新組合。

組合寫入仍使用 Backend API、revision 與 etag，不由 React 直接修改 JSON。

## 4. Routes 與頁面責任

### 4.1 Prompt Workbench

Route：`/prompt-library/workbench`

保留：

- 唯讀瀏覽正向與負向分類；
- 唯讀搜尋及查看詞條；
- 將詞條加入目前組合；
- 加入自由文字；
- 修改工作副本、權重及順序；
- 載入、儲存、更新及另存組合；
- 使用目前 Prompt 生圖。

移除：

- 新增來源詞條；
- 編輯來源詞條；
- 封存來源詞條；
- 任何分類主資料寫入。

### 4.2 分類清單

Route：`/prompt-library/categories`

包含：

- 正向／負向篩選；
- 使用中／已封存篩選；
- 分類清單；
- 新增分類表單；
- 可點擊的分類卡片。

新增分類成功後，頁面重新讀取 catalog。新分類立即出現在清單中，使用者可點入詳情頁。

### 4.3 分類詳情

Route：`/prompt-library/categories/:polarity/:categoryId`

包含：

- 返回分類清單；
- 分類 ID、名稱、說明、aliases、keywords、order 與 revision；
- 編輯分類 metadata；
- 封存或恢復分類；
- 詞條搜尋；
- 使用中／已封存詞條篩選；
- 新增、編輯、封存及恢復詞條。

分類 ID 是 JSON 定位鍵，建立後不可修改。

## 5. 分類與詞條管理流程

### 5.1 建立分類

分類清單頁沿用現有 `PUT /api/prompt-library/categories/{polarity}/{categoryId}`，建立時傳 `expected_revision=0`。建立成功後清空表單並刷新清單。

### 5.2 更新分類

分類詳情頁先讀取完整 category 與 etag。更新時帶目前 category revision 與 etag。409 衝突保留使用者輸入，不關閉表單，並提供重新載入入口。

### 5.3 建立及更新詞條

詞條 CRUD 全部位於分類詳情頁。建立新詞條使用父分類目前 revision 與 etag。更新既有詞條同樣使用父分類 concurrency token；成功後重讀分類，以取得新的 category revision、entry revision 與 etag。

Backend 若回傳 `affected_combinations`，頁面顯示實際受影響的組合數量與 ID，讓使用者知道來源詞條修改已同步到哪些組合。

### 5.4 封存

Delete 的產品語意是軟刪除。分類與詞條使用既有 `POST /api/prompt-library/archive`，不刪除 JSON 檔案或 entry 內容。

封存前顯示確認視窗。成功後資源移至「已封存」清單：

- 已封存分類不出現在工作檯；
- 已封存詞條不出現在工作檯；
- 舊組合保留 snapshot；
- 載入含封存 reference 的組合時顯示 Backend warning。

### 5.5 恢復

新增：

```http
POST /api/prompt-library/restore
```

Restore request 沿用 archive 的 locator 與 concurrency token：

```json
{
  "resource_type": "entry",
  "resource_id": "masterpiece",
  "polarity": "positive",
  "category_id": "quality-ratings",
  "expected_revision": 21,
  "expected_etag": "current-etag"
}
```

規則：

- 恢復分類時設定 `archived=false`，並遞增 category revision。
- 恢復詞條時設定 entry `archived=false`，遞增 entry revision 與父分類 revision。
- revision 或 etag 不符時回傳 409。
- 資源已是使用中狀態時拒絕重複恢復，回傳可操作的 message 與 hint。
- 父分類仍封存時，不允許單獨恢復詞條；錯誤提示使用者先恢復分類。
- 恢復分類不改變各 entry 的 archived 狀態。先前個別封存的詞條仍保持封存。

Provider protocol、FastAPI route 與 MCP `prompt_library_restore` 工具需同步加入 restore，避免 Backend 有功能但 agent runtime 無法使用。這次 restore contract 只處理分類與詞條；組合封存／恢復管理不在本設計範圍。Gateway runtime schema 需在 CTY 執行重啟後另行驗證；程式碼測試通過不等於目前 Gateway 已載入新工具。

## 6. 組合載入與文件狀態

### 6.1 組合工具列

工作檯頂部新增「目前組合」工具列：

- 未封存組合選擇器；
- 載入；
- 建立空白組合；
- 更新組合；
- 另存新組合；
- 目前 ID、revision 與 dirty 狀態。

Catalog summary 用於清單顯示。實際載入必須呼叫：

```http
GET /api/prompt-library/combinations/{combinationId}
```

UI 使用 GET 回傳的 combination、revision 及 etag。不得使用 catalog summary 的版本資訊提交更新。

### 6.2 Lazy repair

現有 `get_combination` 會呼叫 `repair_combination`。若來源詞條已改變，讀取動作可能修復組合 snapshot 並增加組合 revision。UI 必須：

- 顯示修復 warning 或狀態；
- 使用修復後 fragments；
- 保存修復後 revision 與 etag；
- 不把載入前的 catalog revision 當成目前版本。

組合屬於工作檯文件，因此這項 lazy repair 不違反分類／詞條唯讀邊界。

### 6.3 反序列化

Frontend 新增明確的 API fragment → `CompositionState` 轉換函式：

- 保留 polarity、category ID、entry ID 與 source revision；
- 還原文字、權重與順序；
- 產生不碰撞的 UI fragment ID；
- literal 不建立虛假 source；
- entry reference 缺失或封存時保留 snapshot，並顯示 Backend warning。

### 6.4 Dirty 保護

任何片段增刪、文字修改、權重修改、順序調整、自由文字套用，都將目前文件標示為 dirty。

Dirty 狀態下執行「載入其他組合」或「建立空白組合」時，UI 顯示確認視窗：

- 繼續編輯；
- 放棄修改並執行動作。

UI 不自動儲存。新文件可能尚無 ID，自動儲存也可能覆寫錯誤組合。

### 6.5 更新與另存

- 新文件使用「儲存新組合」，expected revision 為 0。
- 載入的文件使用「更新組合」，帶目前 revision 與 etag。
- 「另存新組合」要求新 ID，expected revision 為 0。
- 儲存成功後，UI 使用 Backend 回傳的 canonical fragments、revision 及 etag 更新 state，並清除 dirty。
- 任一後續修改都清除舊的成功提示。

## 7. 自由文字編輯

### 7.1 問題根因

目前 `reconcileComposedText` 在每次 `onChange` 時執行以下工作：

1. 依頂層逗號拆分；
2. 對每個片段 `trim()`；
3. 丟棄空片段；
4. 固定使用 `", "` 重建文字。

因此尾端逗號與空白在輸入後立即消失。位置式 metadata 對應還可能在中間插入或刪除文字後配錯 reference。

### 7.2 編輯模式

每個 Positive／Negative panel 提供兩種狀態：

- 片段模式：使用 cards 編輯工作副本、權重與順序，顯示 canonical 最終文字。
- 自由文字模式：使用獨立 raw draft，提供「取消」與「套用變更」。

自由文字 `onChange` 只更新 raw draft。它不解析、不 trim、不重建，也不改變 fragments。使用者可輸入尾端逗號、空白與暫時未閉合括號。

### 7.3 套用自由文字

使用者按「套用變更」時才：

1. 檢查括號與權重語法；
2. 解析頂層逗號；
3. 正規化 fragments；
4. 將該 polarity 轉為 literal fragments；
5. 標記文件 dirty；
6. 顯示「自由文字已轉為自訂片段」。

自由文字修改不按位置保留舊 reference。這避免把已改寫的內容誤認為 Library entry。使用者若只想調整某個來源片段的權重或內容，可在片段模式操作該 card。

儲存時 Backend 可依既有規則裁切首尾空白與逗號，並用 `", "` 產生 canonical snapshot。輸入期間不做這項正規化。

## 8. 元件邊界

建議元件分工：

- `PromptWorkbench`：組合文件 state、載入、儲存、dirty guard 與生圖資料流。
- `PromptEntryBrowser`：唯讀分類／詞條瀏覽與加入工作副本。
- `PromptComposerPanel`：片段 cards、自由文字草稿與套用／取消。
- `PromptCategoryManagement`：分類清單、狀態篩選及新增分類。
- `PromptCategoryDetail`：分類 metadata 與詞條 CRUD。
- `PromptEntryEditor`：分類詳情頁中的 create/edit 表單。
- `compositionState`：片段操作、API 反序列化、自由文字 commit 與序列化。

`PromptEntryBrowser` 不再接收 `onSaveEntry` 或 `onArchiveEntry`。來源資料寫入函式不得留在 `PromptWorkbench`。

## 9. UI 細節

- Prompt cards 從固定三欄改為響應式一欄或兩欄。
- Fragment 保存並顯示真正的 `name_zh`，移除只辨識 `masterpiece` 與 `blurry` 的硬編碼名稱。
- 已修改的 entry copy 顯示「自訂副本」。
- 錯誤與成功訊息放在觸發操作附近。
- 409 衝突不得清空表單或工作檯。
- Loading 中停用重複提交。
- 分類詳情的已封存資源使用明確狀態標籤。
- 父分類封存時停用 entry restore，並顯示原因。

## 10. 錯誤處理

所有新流程沿用 Backend `code + message + hint`。Frontend 同時支援 FastAPI validation `detail[]`，不得退化成只有 `HTTP 422`。

關鍵錯誤：

- catalog、category 或 combination 載入失敗：保留目前可用 state，提供重試。
- revision／etag 衝突：保留草稿，提示重新載入。
- restore parent archived：提示先恢復分類。
- 自由文字語法錯誤：保留 raw draft，不修改 fragments。
- combination reference warning：保留 snapshot，顯示 warning，不靜默丟棄片段。

## 11. 測試與驗收

### 11.1 Backend

新增 restore 測試：

- 恢復分類；
- 恢復詞條；
- revision 與 etag 遞增；
- stale token 回 409；
- active resource 重複恢復失敗；
- archived parent 阻止 entry restore；
- 恢復分類不改變 entry archived 狀態。

執行 Prompt Library focused tests 與完整 Backend suite。

### 11.2 MCP

- restore payload 與 Backend request 完全一致；
- structured errors 保留 message 與 hint；
- focused MCP tests 與完整 MCP suite 通過；
- CTY 重啟 Gateway 後，另驗證 active tool schema 與一次 live restore call。

### 11.3 Frontend 單元與整合測試

Workbench：

- 不渲染新增、編輯或封存來源詞條入口；
- 載入組合還原 positive／negative fragments、權重、順序與 references；
- lazy repair 後使用最新 revision／etag；
- dirty guard 阻止未確認的組合切換；
- 更新與另存送出正確 concurrency token；
- 修改副本不呼叫 category／entry write API；
- 輸入 `masterpiece, ` 時 raw draft 逐字保留；
- 套用後才正規化；
- 插入或刪除自由文字不會錯配舊 reference。

分類管理：

- 新增分類並刷新清單；
- 分類卡片導向獨立詳情 route；
- 更新與封存分類；
- 顯示及恢復已封存分類；
- 新增、編輯、封存及恢復詞條；
- archived parent 停用 entry restore；
- 409 衝突保留表單；
- 顯示 `affected_combinations`。

執行完整 frontend tests、TypeScript typecheck 與 production build。

### 11.4 真實瀏覽器驗收

啟動實際 Frontend 與 Backend，完成：

1. 建立測試分類；
2. 從清單進入分類詳情；
3. 建立、更新、封存及恢復測試詞條；
4. 確認工作檯只有唯讀來源瀏覽；
5. 建立含 entry 與 literal 的正負組合；
6. 儲存、清空、重新載入並核對內容；
7. 在自由文字模式輸入尾端逗號與空白；
8. 套用後儲存並重新載入 canonical 結果；
9. 驗證生圖 request 使用畫面目前的 positive／negative Prompt。

測試資料需使用唯一 ID。驗收後透過支援的 archive API 封存，不直接刪檔。這一輪不需提交 GPU 生圖；只驗證 generation request construction，真實四張 Discord E2E 仍屬既有 `live-e2e` 任務。

## 12. 完成條件

功能只有在以下條件全部成立時完成：

- Backend restore contract 可用；
- 分類清單與獨立詳情 route 可操作；
- 分類與詞條 archive／restore 完整；
- Workbench 不再寫入分類或詞條；
- 組合可以載入、更新及另存；
- 自由文字輸入不再吞掉尾端逗號或空白；
- focused、完整測試、typecheck 與 production build 通過；
- 真實瀏覽器流程通過；
- MCP source 與 live Gateway runtime 狀態分開回報；
- 測試資源已封存清理。
