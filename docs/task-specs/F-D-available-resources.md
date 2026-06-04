# F-D：查詢可用資源

**功能**：agent 可查詢目前系統中可用的 checkpoints、LoRA 模型、workflow 模板清單，再決定生圖或訓練要用哪個。

**完成定義**：呼叫 `get_available_resources()` MCP tool，回傳 checkpoints / loras / workflows 清單。

---

## 現況確認

- `GET /api/generate/available-resources` 已存在，回傳 `{checkpoints, loras, workflows}`
- 沒有 MCP tool

---

## Steps

### Step 1：MCP tool
**檔案**：`mcp-server/mcp_server/tools/generate.py`

新增：
```python
@mcp.tool()
def get_available_resources() -> str:
    """列出可用的 checkpoints、LoRA 模型、workflow 模板。生圖或訓練前先呼叫確認可用清單。"""
    try:
        client = _get_client()
        resp = client.get("generate/available-resources")
        checkpoints = resp.get("checkpoints", [])
        loras = resp.get("loras", [])
        workflows = resp.get("workflows", [])
        lines = [
            f"Checkpoints ({len(checkpoints)}): {', '.join(checkpoints) or '(無)'}",
            f"LoRAs ({len(loras)}): {', '.join(loras) or '(無)'}",
            f"Workflows ({len(workflows)}): {', '.join(workflows) or '(無)'}",
        ]
        return "\n".join(lines)
    except Exception as e:
        return f"error: {e}"
```

**Verify**：
```bash
cd mcp-server && uv run pytest tests/ -k available_resources
```

---

## End-to-End Verify

```bash
# 呼叫 get_available_resources()
# 回傳類似：
# Checkpoints (2): v1-5-pruned.safetensors, animagine-xl.safetensors
# LoRAs (1): my_character.safetensors
# Workflows (3): default, default_lora, img2img_lora_pose
```
