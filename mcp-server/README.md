# AI Drawing MCP Server

AI 自動化出圖系統的 MCP（Model Context Protocol）介面，讓 Cursor / Claude 等 AI 透過自然語言觸發生圖、LoRA 訓練、圖庫查詢。

## Tools

| Tool | 說明 |
|------|------|
| `mcp_ping` | 檢查 Backend 連線狀態 |
| `generate_image` | 觸發圖片生成（prompt 必填） |
| `generate_queue_status` | 取得生圖佇列狀態 |
| `lora_train_start` | 手動觸發 LoRA 訓練 |
| `lora_train_status` | 取得 LoRA 訓練進度 |
| `gallery_list` | 圖庫列表（可篩選） |
| `gallery_detail` | 單張圖片完整參數 |
| `gallery_rerun` | 一鍵重現該圖參數 |

## 安裝

```bash
cd mcp-server
uv sync
# 或 pip install -e .
```

## 執行

```bash
# stdio（供 Cursor 等 MCP 用戶端使用）
uv run ai-drawing-mcp
# 或 python -m mcp_server.server
```

## 環境變數

| 變數 | 說明 | 預設 |
|------|------|------|
| `MCP_BACKEND_API_URL` | ai-drawing 後端 Base URL | `http://127.0.0.1:8000` |

## 依賴

- Python ≥ 3.10
- mcp
- httpx
