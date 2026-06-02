# 代理人 B（圖庫模組）擴展性審核報告

> 依據 `python-extensibility-review` Skill 執行，審核範圍：`recording.py`、`api/gallery.py`、`schemas/gallery.py`

---

## 1. Overall Verdict

**🟡 有風險（Acceptable with Caveats）**

功能符合契約、可正常運作。主要擴展性缺口：**無 Repository 抽象**，未來替換儲存後端或 Phase 5 分析模組擴充查詢時會吃力。其餘為 when-touching 級別。

---

## 2. 須注意項目（依階段）

| 優先 | 項目 | 須注意階段 | 說明 |
|------|------|------------|------|
| 1 | GalleryRepository 抽象 | **before-phase-5** | E2 生成統計分析需更多查詢；避免在 route 中堆疊查詢邏輯 |
| 2 | `_to_image_url` 參數化 | when-touching | 下次改 gallery 時順便注入 settings |
| 3 | Export formatter 抽出 | when-touching | 加新 export 格式（如 Excel）時再重構 |
| 4 | 日期錯誤回傳 400 | when-touching | `from_date`/`to_date` 無效時改為回傳 400，避免靜默忽略 |

---

## 3. Architecture Summary

| 層級 | 現狀 | 契約預期 |
|------|------|----------|
| API 層 | `gallery.py`：路由、篩選、轉換、CSV | ✅ |
| 服務層 | **無**，邏輯在 route 內 | - |
| 持久層 | **無 Repository**，直接 query GeneratedImage | - |
| recording | 純 DB 寫入，簽名符合 internal-interfaces | ✅ |

---

## 4. Positive Findings

- `recording.save()` 簽名清楚，`db` 注入，易 mock
- Schemas 與 API 契約對齊
- `get_db` 透過 Depends 注入，測試可 override
- recording 單元測試充分；test_gallery 涵蓋主要 API

---

## 5. Extensibility Risks

- **無 Repository**：換儲存後端時需改 gallery + recording 多處
- **查詢邏輯在 route 內**：list_images 篩選若擴充，route 會膨脹
- **`_to_image_url` 直接呼叫 get_settings()**：非 DI，單測需 patch

---

## 6. 使用者測試方法與預期結果

| 測試類型 | 指令／步驟 | 預期結果 |
|----------|------------|----------|
| 單元測試（recording） | `cd backend && pytest tests/test_recording.py -v` | 2 passed |
| 單元測試（gallery API） | `cd backend && pytest tests/test_gallery.py -v` | 6 passed |
| API 列表 | GET `/api/gallery/?limit=5` | 200, items + total |
| API rerun | POST `/api/gallery/1/rerun` | 202 + job_id |
| API export | GET `/api/gallery/1/export?format=json` 或 `format=csv` | 200 |
