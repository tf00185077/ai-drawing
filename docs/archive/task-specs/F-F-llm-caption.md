# F-F：LLM 自動產生 Caption

**功能**：agent 可對指定圖片呼叫 LLM 自動產生訓練用的 caption（寫入對應 .txt）。

**完成定義**：呼叫 `caption_image(image_path="character/miku/img1.png")` MCP tool，LLM 產生描述並寫入 `character/miku/img1.txt`，回傳 caption 內容。

---

## 現況確認

- `lora_docs.py` 有 caption 讀取（GET）/ 編輯（PUT）endpoint，但沒有 LLM 生成
- 沒有 MCP tool

---

## Steps

### Step 1：後端 LLM caption API
**檔案**：`backend/app/api/lora_docs.py`

新增：
```python
@router.post("/caption-llm/{image_path:path}")
async def generate_caption_llm(image_path: str):
    """對圖片呼叫 LLM（如 BLIP2 或外部 API）產生 caption，寫入同名 .txt"""
```

實作要點：
- 用 `_resolve_image_and_caption(image_path, base_dir)` 取得路徑
- 呼叫 LLM（優先用 BLIP2；若未部署則呼叫外部 API，見 `app/config.py` 中 LLM 設定）
- 將 caption 寫入 `.txt`
- 回傳 `{"path": caption_rel, "content": caption_text}`

注意：LLM 呼叫方式依部署環境而定，實作前確認 `app/config.py` 中有無 LLM 相關設定。若無，新增 `llm_caption_url: str | None = None` 環境變數。

**Verify**：
```bash
curl -X POST "http://localhost:8000/api/lora-docs/caption-llm/character/miku/img1.png"
# 回傳 {"path": "character/miku/img1.txt", "content": "1girl, blue hair, ..."}
# 確認 img1.txt 檔案已建立或更新
```

### Step 2：MCP tool
**檔案**：`mcp-server/mcp_server/tools/`（新建 `lora_docs.py` 或加入 `lora_train.py`）

新增：
```python
@mcp.tool()
def caption_image(image_path: str) -> str:
    """
    對訓練資料夾內的圖片呼叫 LLM 自動產生 caption，寫入同名 .txt。
    image_path 相對於 lora_train_dir，如 "character/miku/img1.png"。
    回傳產生的 caption 文字。
    """
```
呼叫 `POST /api/lora-docs/caption-llm/{image_path}`。

在 `mcp-server/mcp_server/server.py` 確認新 tool 檔案有被 import。

**Verify**：`uv run pytest tests/ -k caption`

---

## End-to-End Verify

```bash
# 1. caption_image("character/miku/img1.png")
# 2. 回傳 "1girl, blue hair, twintails, school uniform"
# 3. 確認 lora_train_dir/character/miku/img1.txt 內容一致
```
