# MCP 整合文件與 Cursor 配置

> AI 自動化出圖系統的 MCP（Model Context Protocol）介面，讓 Cursor / Claude 等 AI 透過自然語言觸發生圖、LoRA 訓練、圖庫查詢。

---

## 一、前置需求

| 項目 | 說明 |
|------|------|
| **ai-drawing Backend** | 必須先啟動，MCP Server 會呼叫其 API |
| **Python ≥ 3.10** | MCP Server 執行環境 |
| **uv** | 建議使用（或 `pip install -e mcp-server`） |
| **Cursor IDE** | v0.40 以上 |

**啟動順序**：先啟動 Backend → 再讓 Cursor 連線 MCP Server

---

## 二、安裝 MCP Server

```bash
cd mcp-server
uv sync
```

或使用 pip：

```bash
cd mcp-server
pip install -e .
```

---

## 三、Cursor 配置

### 方式 A：專案級配置（建議，可 commit 給團隊）

在專案根目錄建立 `.cursor/mcp.json`。

**Windows**（將 `D:\AI\ai-drawing` 改為你的專案路徑）：

```json
{
  "mcpServers": {
    "ai-drawing": {
      "command": "D:\\AI\\ai-drawing\\scripts\\run-mcp-server.bat",
      "args": []
    }
  }
}
```

**macOS / Linux**：

```json
{
  "mcpServers": {
    "ai-drawing": {
      "command": "/path/to/ai-drawing/scripts/run-mcp-server.sh",
      "args": []
    }
  }
}
```

> 路徑需為**絕對路徑**，或確保 Cursor 的 working directory 為專案根目錄時使用 `scripts/run-mcp-server.bat`（Windows）／`scripts/run-mcp-server.sh`（Unix）。

### 方式 B：使用 uv 直接執行（需指定工作目錄）

若你的 Cursor 支援 `cwd` 或類似設定：

```json
{
  "mcpServers": {
    "ai-drawing": {
      "command": "uv",
      "args": ["run", "ai-drawing-mcp"],
      "cwd": "D:\\AI\\ai-drawing\\mcp-server"
    }
  }
}
```

> **注意**：部分版本可能不支援 `cwd`，建議優先使用方式 A 的啟動腳本。

### 方式 C：全域配置（個人用）

編輯 `~/.cursor/mcp.json`（Windows：`%USERPROFILE%\.cursor\mcp.json`），加入同上結構。

---

## 四、環境變數

| 變數 | 說明 | 預設 |
|------|------|------|
| `MCP_BACKEND_API_URL` | ai-drawing 後端 Base URL | `http://127.0.0.1:8000` |

若 Backend 不在本機或使用不同埠，在 `mcp.json` 的 `env` 中設定：

```json
{
  "mcpServers": {
    "ai-drawing": {
      "command": "D:\\AI\\ai-drawing\\scripts\\run-mcp-server.bat",
      "args": [],
      "env": {
        "MCP_BACKEND_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

---

## 五、驗證

### 1. 重啟 Cursor

修改 `mcp.json` 後需**完整重啟** Cursor。

### 2. 確認 MCP Server 已載入

- 開啟 **Settings**（Ctrl+Shift+J / Cmd+Shift+J）→ **Tools & MCP**
- 檢查 `ai-drawing` 是否出現且為開啟狀態

### 3. 在 Composer（Agent 模式）中測試

對 AI 說：

> 請呼叫 mcp_ping 檢查 ai-drawing 連線

預期回傳：`ok: Backend 連線正常`（若 Backend 已啟動）

### 4. 若失敗

- 查看 **Output** 面板（Ctrl+Shift+U）→ 選擇 **MCP Logs**
- 確認 Backend 是否已啟動：`uvicorn app.main:app --reload`（在 `backend/` 目錄）
- 確認 `MCP_BACKEND_API_URL` 與 Backend 位址一致

---

## 六、可用 Tools

| Tool | 說明 | 範例指令 |
|------|------|----------|
| `mcp_ping` | 檢查 Backend 連線 | 檢查 ai-drawing 連線 |
| `generate_image` | 觸發生圖 | 產生初音、動漫風格的圖 |
| `generate_image_from_description` | **依描述自動選 workflow 生圖** | 穿和服的初音，動漫風格，1024 |
| `suggest_workflow_from_description` | 預覽描述解析結果 | 穿和服初音會用什麼參數 |
| `generate_image_custom_workflow` | 自訂 workflow 生圖 | 用 default 模板產生穿和服的初音 |
| `list_workflow_templates` | 列出 workflow 模板 | 有哪些 workflow 可選 |
| `get_workflow_template` | 取得模板 JSON | 取得 default 模板 |
| `generate_queue_status` | 生圖佇列狀態 | 查生圖佇列 |
| `lora_train_start` | 手動觸發 LoRA 訓練 | 開始訓練 my_lora 資料夾 |
| `lora_train_status` | 訓練進度 | 查 LoRA 訓練進度 |
| `gallery_list` | 圖庫列表 | 列出最近的圖 |
| `gallery_detail` | 單張圖片參數 | 查 id=1 的圖片參數 |
| `gallery_rerun` | 一鍵重現 | 用 id=1 的參數再產一張 |
| `list_character_styles` | 可用角色／風格 | 有哪些角色和風格可選 |
| `resolve_character_style_prompt` | 預覽 prompt | 初音+動漫會變成什麼 prompt |

---

## 七、自然語言範例

在 Composer 中可直接說：

- **「產生初音、動漫風格的圖」** → 呼叫 `generate_image(character="初音", style="動漫")`
- **「用 default 模板產生穿和服的初音」** → 呼叫 `list_workflow_templates` → `get_workflow_template("default")` → `generate_image_custom_workflow(workflow=..., character="初音", prompt="1girl, kimono")`
- **「開始訓練 my_char 資料夾的 LoRA」** → 呼叫 `lora_train_start(folder="my_char")`
- **「列出最近 5 張圖」** → 呼叫 `gallery_list(limit=5)`
- **「用第 3 張的參數再產一張」** → 呼叫 `gallery_rerun(image_id=3)`

---

## 八、範例配置檔

專案內含 `.cursor/mcp.json.example`，複製後重新命名為 `mcp.json` 並修改路徑：

```bash
cp .cursor/mcp.json.example .cursor/mcp.json
# 編輯 .cursor/mcp.json，將 command 路徑改為你的專案絕對路徑
```

---

## 九、相關文件

- [setup-guide.md](./setup-guide.md) - Backend 完整運行設定
- [mcp-server/README.md](../mcp-server/README.md) - MCP Server 技術說明
- [api-contract.md](./api-contract.md) - REST API 契約
