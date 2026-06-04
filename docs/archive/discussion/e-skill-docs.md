# E. MCP Skill 文件

## 決策

Skill 文件在功能補齊後才寫，避免文件和實作脫節。
openclaw 的 skill 格式待確認（需知道 openclaw 是哪個工具/框架）。

## 確定的 Skill 清單（2 個）

### Skill 1：`ai-drawing-generate`

| 功能 | 說明 |
|------|------|
| 探索資源 | 知道現在有哪些 checkpoint、LoRA、workflow 可以選 |
| 構建 prompt | 把口語描述轉成 SD prompt（角色、場景、動作、人數、風格等） |
| 選擇 workflow | 根據需求選對 workflow（txt2img / LoRA / pose 等） |
| 提交生圖 | 帶完整參數送出生圖請求 |
| 批次生圖 | 一次提交多張不同 prompt 的請求 |
| 追蹤完成 | 知道圖什麼時候生好 |
| 取得結果 | 拿到生成圖片的路徑或可查閱資訊 |
| 調整重生 | 使用者說「太暗了」「人數改兩個」，調整參數再生 |
| 查歷史圖庫 | 搜尋過去生成的圖片（依角色、日期、LoRA 等） |
| 重現舊圖 | 找到某張圖後用同樣參數重新生成 |
| 取消任務 | 撤銷排隊中的任務 |

**依賴 MCP tools**：`get_available_resources`, `generate_image`, `get_job_result`, `cancel_job`

### Skill 2：`ai-drawing-train`

| 功能 | 說明 |
|------|------|
| 探索可訓練資料夾 | 知道哪些資料夾有素材可以訓練 |
| 設定訓練參數 | 指定 checkpoint、epochs、trigger word 等常用參數 |
| 設定訓練後生圖 | 訓練完成後用新 LoRA 自動生驗證圖（prompt、張數） |
| 提交訓練 | 送出訓練請求 |
| 查訓練進度 | 知道目前第幾 epoch、是否完成、有沒有失敗 |
| 取得訓練結果 | 知道 LoRA 檔案位置、驗證圖結果 |
| 取消訓練 | 撤銷排隊中的訓練任務 |

**依賴 MCP tools**：`lora_train_start`, `lora_train_status`, `llm_caption`

### Skill 銜接點

```
ai-drawing-train 結尾
    訓練完成 → generate_after 自動提交生圖
        ↓
ai-drawing-generate 流程
    生圖佇列 → 完成 → 回傳結果
```

## 從使用情境推導（原始分析）

核心情境：**使用者口語描述 → agent 生圖 / 訓練 / 查詢**

| Skill 名稱 | Agent 需要能做的事 | 依賴的 MCP tools |
|-----------|-------------------|-----------------|
| `generate-image` | 口語→prompt，選 workflow，提交，等待完成，取得結果圖 | get_available_resources, generate_image, get_job_result |
| `train-lora` | 指定資料夾訓練、設定參數、完成後自動生圖 | lora_train_start, lora_train_status |
| `query-gallery` | 查歷史圖片、重現某張圖的參數 | gallery_list, gallery_detail, gallery_rerun |
| `manage-resources` | 知道現在有哪些 checkpoint/lora/workflow | get_available_resources |

→ query-gallery / manage-resources 屬於 generate-image skill 的子步驟，合併為 2 個 skill 更符合使用情境。

## 新增功能方向

### 素材標注雙入口

目前：watchdog 監聽資料夾 → WD Tagger 自動產生 .txt caption（單一模式）

新增第二個入口：**交給 LLM 判斷訓練內容**
- 入口一（保留）：WD Tagger 自動標注，規則式過濾 blacklist
- 入口二（新增）：LLM 分析圖片，生成更語意化的 caption，或依訓練目標（人物/風格/服裝）決定 caption 策略

此功能屬於訓練前置，歸屬 `ai-drawing-train` skill 範圍，但實作上需新增 API 端點與 MCP tool。

### Slack 移除

Slack Socket Mode 整合從專案完全移除。

需清理的項目：
- `backend/app/services/slack_handler.py`
- `backend/app/services/slack_notifier.py`
- `backend/app/services/slack_commands.py`
- `backend/app/main.py` 的 Slack Socket Mode 啟動邏輯
- `backend/app/config.py` 的 slack_app_token / slack_bot_token
- `backend/app/schemas/generate.py` 的 slack_channel_id / slack_thread_ts 欄位
- `README.md` 的遠端觸發生圖章節
- `AGENTS.md` 的 Phase 7 追蹤項目

---

→ 相關實作項目：[checklist.md](checklist.md) #20–29
