# Python 擴展性審核 - 詳細維度

本檔補充 SKILL.md 的詳細審核維度與模式，供深入分析使用。

---

## 1. 職責分離（詳）

檢查是否清楚區分：
- API 層：只處理 HTTP
- 應用/服務層：編排、流程
- 領域/業務規則：純邏輯
- 持久層：存取 DB
- 外部整合：呼叫第三方
- 背景任務編排：佇列、排程

---

## 2. 依賴設計（詳）

**偏好**：
- dependency injection
- repository 或 gateway 抽象
- adapter 包第三方 API
- 設定驅動行為

**Flag**：
- service 到處 import 具體 infrastructure
- 業務邏輯直接依賴 SDK client
- 換實作需動很多檔案
- 隱藏全域狀態控制行為

---

## 3. 擴展性（詳）

問：
- 新 payment provider 好加嗎？
- 新 storage backend 好加嗎？
- 新 async workflow 能重用既有邏輯嗎？
- 新 endpoint 能重用既有 service 嗎？
- 驗證規則演進時，無須改不相關程式碼嗎？

**Flag**：
- 邏輯跨模組重複
- 每個新功能都加 if/elif
- 行為靠多個 hardcoded type check
- 新功能要改 god class
- 靠 copy-paste 處理變化

---

## 4. 介面品質（詳）

檢查 public 介面是否：
- 小
- 清楚
- 穩定
- 表達意圖

**偏好**：
- 明確輸入/輸出
- 型別化 DTO / schema / command
- 狹窄 service 合約

**Flag**：
- 方法簽名過胖
- 到處接受模糊 dict
- 回傳不一致
- 一個介面負擔太多職責

---

## 5. 資料存取設計（詳）

**偏好**：
- repository 層或清楚的 query 層
- DB 邏輯與業務邏輯隔離
- 交易邊界明確

**Flag**：
- ORM model 在各層洩漏
- 查詢邏輯重複
- 業務邏輯依賴 DB 特有行為
- 交易管理分散、隱晦

---

## 6. 設定與環境邊界（詳）

**偏好**：
- 環境變數
- 集中設定
- 必要時 feature flag
- 不在程式碼硬編碼 env 相關值

**Flag**：
- URL、secret、timeout、路徑、上限硬編碼
- 行為由藏在程式碼的 magic constant 決定
- 設定散落各模組

---

## 7. 錯誤處理與可觀測性（詳）

**偏好**：
- 領域專屬 exception（需要時）
- 清楚錯誤邊界
- 結構化 logging
- 一致的錯誤對應

**Flag**：
- 吞掉 exception
- 到處用 generic `Exception`
- 關鍵整合點缺 log
- 各模組錯誤回傳不一致

---

## 8. 可測性（詳）

**偏好**：
- 盡量純業務邏輯
- 對 DB/網路/時間做 DI
- 不依賴真實基礎設施即可測
- 行為具決定性

**Flag**：
- 只能透過完整整合環境測
- time、UUID、env、DB、network 硬編碼
- 耦合過高導致 mock 困難

---

## 9. Async / 背景任務設計（詳）

對佇列、worker、排程或異步 job 檢查：
- 冪等性
- 重試安全性
- 編排與業務邏輯分離
- 可重用的 job handler
- 狀態轉換清晰

**Flag**：
- 重試造成重複副作用
- job 邏輯緊綁單一傳輸機制
- worker 直接混雜 IO、業務規則、持久化

---

## 10. 框架過度耦合（詳）

對 FastAPI / Flask / Django 專案，檢查框架是否僅扮演交付層。

**偏好**：
- 薄 controller / route 層
- 與框架無關的核心邏輯

**Flag**：
- request/response 物件深入 service
- decorator、framework 物件主導 domain 層
- 核心邏輯必須在 HTTP request 情境下才能執行

---

## 建議重構 Pattern

視情況採用：
- service 層抽離
- repository pattern
- adapter pattern
- strategy pattern
- domain service 抽離
- command/query 分離
- dependency injection
- 設定物件抽離
- 共用 workflow 編排層

**只在能降低耦合或改善擴展點時建議 pattern。**

---

## 11. 使用者測試與驗證（詳）

審核或重構完成後，應提供使用者可執行的測試方法與預期結果：

- **單元測試**：`pytest` 指令、預期為全 PASSED
- **API 測試**：需起後端，驗證 DI／路由；預期 501（stub）或 200（實作完成），非 500
- **設定測試**：`.env` 覆寫後驗證 config 讀取
- **整合測試**：需外部服務時，列出前置與預期

詳見 SKILL.md「使用者測試方法與預期結果」一節。

---

## 反模式清單（強烈 Flag）

- fat controller
- god service
- copy-paste feature branching
- 業務邏輯散落的 DB 查詢
- 硬編碼第三方整合邏輯
- 隱藏共享可變狀態
- utility 模組堆疊無關職責
- 框架物件洩漏進 domain
- 「再加一個 if/elif」的擴展模式
