# 設計：雙語詞庫在 agent 寫入下保持乾淨（軟性偵測 + 操作台 entry 增刪改查）

- 日期：2026-07-24
- 狀態：設計已確認，待寫實作計畫
- 相關程式：`mcp-server/mcp_server/tools/prompt_library.py`、`frontend/src/components/prompt-library/PromptEntryBrowser.tsx`、`frontend/src/components/prompt-library/PromptWorkbench.tsx`

## 背景與問題

Prompt Library 原本是為了「英文不好的使用者」設計：每次找到好用的英文繪圖詞彙就存下來，配上**中文對照**方便日後用中文檢索、回想用途。資料模型 `PromptEntry`（[prompt_library_models.py:27](../../../backend/app/core/prompt_library_models.py)）本來就是雙語結構：

- `prompt`：英文，實際送給繪圖模型的功能性文字
- `name_zh` / `description_zh`：中文對照，給使用者看

新狀況：現在 agent 會透過 MCP tool（`prompt_library_save`）寫入詞庫。agent 不知道使用者需要**有意義的中文對照**，可能把 `name_zh` 填成照抄英文、或機械拼接（現有種子資料的 `name_zh` 例如 `"品質細節：masterpiece"` 也是這種機械標籤，並非真正翻譯）。

### 為什麼不用 i18n

使用者最初想用 i18n 解決。經討論確認 i18n 是錯的工具：

1. i18n 框架解決的是「依語系**切換**顯示語言，一次一種」；使用者要的是**中英同時對照**，概念相反。
2. 另立 i18n store（key → 翻譯）會與詞條 JSON 形成**雙重來源**，遲早不同步。現有設計把翻譯**內嵌在詞條本身**，更乾淨，不該拆開。

結論：目標對，但機制不該是 i18n。真正的缺口是「語義契約 + 讓使用者能兜底修正」。

## 使用者已確認的決定

1. **範圍**：不動 schema、不碰 i18n。維持 `prompt`(英)+`name_zh`(中) 結構。
2. **嚴格度**：MCP 偵測到中文沒填好時**全部軟性**——照存，只回 warning，永不擋。（符合 AGENTS.md §3.5「寬進嚴出、錯誤是修復指南」。）
3. **兜底**：操作台要有讓使用者自己修的地方，因應軟性偵測。範圍為詞條（entry）的**完整增刪改查（全欄位）**。
4. **CRUD 位置**：長在工作台的詞條區，不另開頁面。
5. **刪 = 封存**（archive，可復原），不做實體刪檔——與系統「紀錄層嚴謹、不可逆才硬擋」一致。

## 設計

三個部分，共用一條規則。**backend 端點與 schema 完全不動**（entry 的 `PUT`／`archive` 端點都已存在）。

### Part 0 — 共用「可疑中文」啟發式

定義一次，MCP 端拿來發 warning、前端拿來標 ⚠️。判定「可疑」的條件（任一成立即可疑）：

- `name_zh` 完全不含中日韓統一表意文字（CJK），或
- `name_zh` 經正規化（trim + 大小寫 + 空白收斂）後等於英文 `prompt`（照抄）

實作說明：MCP 是 Python、前端是 TS，同一套邏輯兩份實作，需保持同步。邏輯很小（一個 regex 掃 CJK 範圍 + 一個字串正規化比較），可各自寫單元測試釘住行為。

明確**不做**的偵測（YAGNI，避免誤報惹人厭）：不判斷「翻譯品質好不好」、不判斷 `description_zh` 是否空泛。只抓「幾乎確定沒填」的兩種鐵定失敗。

### Part 1 — MCP 契約 + 軟性 warning

檔案：`mcp-server/mcp_server/tools/prompt_library.py`

1. **契約（指引，非驗證）**：給 `prompt_library_save` 補上 docstring／參數說明，講白規則：
   > 建立 entry／category／combination 時，`name_zh` 必須是英文 `prompt` 的**有意義中文對照**（翻譯或說明），不是照抄英文、也不是機械拼接。這是給中文使用者日後用中文檢索、回想此詞用途的依據。
   這就是「寬鬆綁定」：agent 讀 tool schema 時就看得到，但不強制。

2. **軟性 warning**：`prompt_library_save` 成功呼叫 backend 後，用 Part 0 檢查 agent 送出的 `payload`，把問題塞進回傳 dict 的 `warnings` 陣列（沿用 `code + message + hint` 風格）。**永遠不擋、`ok` 恆為 True、永遠照存。** 依 `resource_type` 走對應欄位：
   - `entry`：檢查該 entry 的 `name_zh` vs `prompt`。
   - `category`：逐一檢查 payload 內每個 `entries[]`，warning 指出是哪個 entry id。
   - `combination`：只檢 `name_zh`（combination 無 per-fragment 中文）。

   warning 範例：
   - 無中文：`{"code": "name_zh_missing_chinese", "message": "name_zh 看起來沒有中文對照", "hint": "建議補上翻譯，方便日後用中文檢索"}`
   - 照抄英文：`{"code": "name_zh_echoes_prompt", "message": "name_zh 只是照抄英文 prompt", "hint": "建議填實際中文意思"}`

### Part 2 — 操作台 entry 增刪改查（純前端補洞）

現況：工作台（`PromptWorkbench.tsx`）目前**沒有** entry CRUD。既有的是分類頁「新增分類」、工作台「自由文字（加入到目前組合，不存成可重用詞條）」、「儲存組合」。後端 entry 端點全部已存在，只是前端沒開口。

在工作台打開某分類後的詞條區（`PromptEntryBrowser`）擴充：

- **查（已有）**：沿用現有詞條列表。每個詞條若被 Part 0 判定可疑，顯示 ⚠️ 標記，使用者一眼看到要修哪個。
- **改**：每條加「編輯」→ 展開內嵌編輯器，可改**全欄位**：`name_zh`、`description_zh`、`prompt`、`aliases`、`keywords`、`order`（`id` 為鍵不可改）→ `PUT /api/prompt-library/categories/{polarity}/{category_id}/entries/{id}`，帶 `expected_revision`（該 entry 目前 revision）＋分類 `expected_etag`（沿用既有樂觀鎖）。存檔後重載分類。
- **增**：詞條區下方「＋ 新增詞條」表單（`id` slug ＋各欄位）→ `PUT .../entries/{新id}`，`expected_revision: 0`。
- **刪**：每條加「封存」鈕 → `POST /api/prompt-library/archive`（`resource_type: "entry"` ＋ polarity ＋ category_id ＋ expected_revision/etag）。封存後從列表消失（`archived` 詞條原本就被過濾掉）。

樂觀鎖衝突（revision/etag 不符）沿用既有處理：把後端回的 `message + hint` 顯示給使用者，請其重載後重試。不繞過既有 concurrency 契約。

## 邊界 / YAGNI

- backend 端點與 schema 完全不動。
- 無 i18n、無 locale 檔、不新增 `name_en`。
- 不碰既有 combination 內容編輯流程；只補 entry 這一層的 CRUD。
- 不做 entry 實體刪檔（刪 = 封存）。
- 軟性偵測不判斷翻譯品質，只抓兩種鐵定失敗。

## 驗證計畫

- **MCP**（`mcp-server/tests/`）：離線單元測試。對 entry／category／combination 三種 payload，各餵「乾淨／無中文／照抄英文」，斷言 `warnings` 內容正確、且 `ok` 恆為 True（軟性不擋）。Part 0 啟發式獨立單元測試。
- **前端**：`PromptEntryBrowser` / `PromptWorkbench` 測試——⚠️ 標記依啟發式渲染、編輯送出正確 PUT、新增、封存、樂觀鎖衝突訊息顯示。`npx tsc --noEmit` 與 Vite production build 通過。Part 0 TS 啟發式獨立單元測試（與 Python 版行為對齊）。

## 完成後

依專案規則，同步更新 [docs/PROGRESS.md](../../PROGRESS.md)。
