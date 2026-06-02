---
name: mcp-tools-usage
description: 透過 Cursor 呼叫 ai-drawing MCP Tools 執行生圖、LoRA 訓練、圖庫查詢。使用者口語說「產生初音的圖」「查訓練進度」「列出圖庫」等時，Agent 應依此 skill 直接呼叫 call_mcp_tool，無需再搜尋文件。
---

# MCP Tools 使用指南

當使用者以口語描述生圖、訓練、圖庫相關需求時，直接使用 `call_mcp_tool` 呼叫 ai-drawing MCP，無需重新查文件。

## 呼叫格式

```text
call_mcp_tool(
  server="user-ai-drawing",
  toolName="<工具名稱>",
  arguments={ ... }
)
```

**呼叫前**：若需確認參數 schema，讀取 `mcps/user-ai-drawing/tools/<tool_name>.json`。

## 口語 → Tool 對照表

| 使用者說 | 對應 Tool | arguments 範例 |
|----------|-----------|----------------|
| 檢查連線、ping、確認 Backend | `mcp_ping` | `{}` |
| 產生 XX 風格的圖、生圖、產圖 | `generate_image` | `{ "character": "初音", "style": "動漫" }` 或 `{ "prompt": "1girl, kimono" }` |
| 依描述生圖（一句話） | `generate_image_from_description` | `{ "description": "穿和服的初音，動漫風格，1024" }` |
| 預覽描述會用什麼參數 | `suggest_workflow_from_description` | `{ "description": "初音 動漫" }` |
| 用自訂 workflow 生圖 | `generate_image_custom_workflow` | 需先 `list_workflow_templates` → `get_workflow_template` 取得 workflow JSON |
| 有哪些 workflow 模板 | `list_workflow_templates` | `{}` |
| 取得 default 模板 | `get_workflow_template` | `{ "template_name": "default" }` |
| 查生圖佇列 | `generate_queue_status` | `{}` |
| 開始訓練、訓練 LoRA | `lora_train_start` | `{ "folder": "my_char" }` |
| 查訓練進度、LoRA 訓練狀態 | `lora_train_status` | `{}` |
| 列出圖庫、最近圖片 | `gallery_list` | `{ "limit": 10 }` |
| 查 id=3 的圖片參數 | `gallery_detail` | `{ "image_id": 3 }` |
| 用某張圖參數重現、一鍵重現 | `gallery_rerun` | `{ "image_id": 3 }` |
| 有哪些角色和風格可選 | `list_character_styles` | `{}` |
| 預覽 prompt 會變什麼 | `resolve_character_style_prompt` | `{ "character": "初音", "style": "動漫" }` |

## 生圖流程選擇

| 情境 | 作法 |
|------|------|
| 簡單（角色+風格，如「初音動漫」） | `generate_image_from_description("初音 動漫 1024")` |
| 需 ControlNet、img2img 等進階 | `list_workflow_templates` → `get_workflow_template` → 自行修改 workflow → `generate_image_custom_workflow` |

自組 workflow 詳見 `.cursor/rules/mcp-workflow-generation.mdc`、`.cursor/skills/comfyui-workflow/SKILL.md`。

## 常用參數

- **generate_image**：`prompt`（預設 `"1girl, solo"`）、`character`、`style`、`checkpoint`、`lora`、`negative_prompt`、`seed`、`steps`、`cfg`、`batch_size`（1～8）
- **lora_train_start**：`folder`（必填）、`checkpoint`、`epochs`、`class_tokens`、`generate_after`（dict：訓練完成後自動生圖）
- **gallery_list**：`checkpoint`、`lora`、`from_date`、`to_date`、`limit`、`offset`

## 相關文件

- 安裝與設定：`docs/mcp-setup.md`
- 自然語言範例：見 `docs/mcp-setup.md` 第七節
