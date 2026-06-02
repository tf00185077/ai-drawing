# 生圖 API 與 Slack Help 參數一致性整理

> 整理 Backend 發送生圖 API 時使用的參數，與 Slack `!給我可用指令` 顯示的方法與參數，兩者來源、格式是否一致。
>
> **Slack 指令規格唯一來源**：`backend/app/services/slack_commands.py` 的 `COMMAND_SPECS`。

---

## 1. 資料流概覽

```
使用者輸入
    │
    ├─ [Slack] !給我可用指令 ──────────────────────► build_help_message() ─► 顯示 COMMAND_SPECS
    │
    └─ [Slack] !生圖片 {"prompt":"..."}  ─────────► parse_command / validate_params
                │                                          │
                │   (S3.2 實作後)                            │
                └──────────────────────────────────────────┼──► httpx.post /api/generate/
                                                           │         │
                                                           │         ▼
                                                           │    GenerateRequest (Pydantic)
                                                           │         │
                                                           │         ▼
                                                           │    trigger_generate() 組 params
                                                           │         │
                                                           │         ▼
                                                           └──► queue.submit(params) ─► GenerateParams
                                                                        │
                                                                        ▼
                                                              apply_params() → ComfyUI
```

---

## 2. 參數來源對照

| 來源 | 檔案 | 用途 |
|------|------|------|
| **api-contract** | `docs/api-contract.md` | 契約文件，規格唯一來源 |
| **GenerateRequest** | `backend/app/schemas/generate.py` | POST /api/generate/ 的 Pydantic 模型 |
| **GenerateCustomRequest** | `backend/app/schemas/generate.py` | POST /api/generate/custom 的 Pydantic 模型 |
| **GenerateParams** | `backend/app/core/queue.py` | queue.submit() 實際接收的 TypedDict |
| **COMMAND_SPECS** | `backend/app/services/slack_commands.py` | Slack help 顯示的指令與參數 |

---

## 3. !生圖片 → POST /api/generate/

### 3.1 參數對照表

| 參數 | api-contract §1 | GenerateRequest | queue.GenerateParams | slack_commands (generate) | 一致性 |
|------|-----------------|-----------------|----------------------|---------------------------|--------|
| prompt | 必填 | 必填 (Field min_length=1) | ✓ | required | ✅ |
| checkpoint | 否 | str \| None | ✓ | optional | ✅ |
| lora | 否 | str \| None | ✓ | optional | ✅ |
| negative_prompt | 否 | str \| None | ✓ | optional | ✅ |
| seed | 否 | int \| None | ✓ | optional | ✅ |
| steps | 否, 預設 20 | int=20, 1–150 | ✓ | optional | ✅ |
| cfg | 否, 預設 7.0 | float=7.0, 1–30 | ✓ | optional | ✅ |
| width | 否, 256–2048 | int \| None, 256–2048 | ✓ | optional | ✅ |
| height | 否, 256–2048 | int \| None, 256–2048 | ✓ | optional | ✅ |
| batch_size | 否 | int \| None, 1–8 | ✓ | optional | ✅ |
| sampler_name | 否 | str \| None | ✓ | optional | ✅ |
| scheduler | 否 | str \| None | ✓ | optional | ✅ |

**結論**：完全一致。Slack help 顯示的參數與 API 規格、Pydantic schema、queue 結構一致。

### 3.2 格式說明

| 項目 | API | Slack help |
|------|-----|------------|
| 來源 | `GenerateRequest` (Pydantic) | `COMMAND_SPECS["generate"]` |
| 使用者輸入格式 | JSON `{"prompt":"1girl", "steps":25}` | 同上，範例與說明一致 |
| 驗證 | FastAPI 自動驗證型別、範圍 | `validate_params(cmd_key, data)` 只驗證必填 |

---

## 4. !用指定動作生圖片 → POST /api/generate/custom

### 4.1 參數對照表

| 參數 | GenerateCustomRequest | queue.GenerateParams | slack_commands (generate_pose) | 一致性 |
|------|------------------------|----------------------|--------------------------------|--------|
| prompt | 必填 | ✓ | required | ✅ |
| image_pose | 必填（此指令專用） | ✓ | required | ✅ |
| workflow | 必填（由 Backend 取得） | ✓ | —（Backend 自動處理） | ⚠️ |
| checkpoint | 否 | ✓ | optional | ✅ |
| lora | 否 | ✓ | optional | ✅ |
| negative_prompt | 否 | ✓ | optional | ✅ |
| seed | 否 | ✓ | optional | ✅ |
| steps | 否 | ✓ | optional | ✅ |
| cfg | 否 | ✓ | optional | ✅ |
| width | 否 | ✓ | optional | ✅ |
| height | 否 | ✓ | optional | ✅ |
| batch_size | 否 | ✓ | optional | ✅ |
| sampler_name | 否 | ✓ | optional | ✅ |
| scheduler | 否 | ✓ | optional | ⚠️ |

### 4.2 差異說明

| 項目 | 說明 |
|------|------|
| **workflow** | `GenerateCustomRequest` 必填，但 `!用指定動作生圖片` 不要求使用者傳。Backend 會先 `GET /api/generate/workflow-templates/controlnet_pose` 取得模板，再組成 body 呼叫 `POST /api/generate/custom`。Slack help  correctly 不列出 workflow。 |
| **sampler_name / scheduler** | `GenerateCustomRequest` 有，但 `slack_commands` 的 `generate_pose` optional 未列入。 |

**建議**：若 `generate` 已列出 `sampler_name`、`scheduler`，`generate_pose` 應一併列出以保持一致。

---

## 5. api-contract 與 COMMAND_SPECS 對照

| 項目 | api-contract §1 | COMMAND_SPECS |
|------|-----------------|---------------|
| 用文字生圖片參數 | 完整 11 欄位 | `generate` 的 required + optional |
| 用指定動作參數 | 無獨立章節 | `generate_pose` 的 required + optional |

**Slack help 來源**：`build_help_message()` 從 `COMMAND_SPECS` 動態產生。指令格式、help 文案皆以 `COMMAND_SPECS` 為準，不在 `slack-command-scheme.md` 重複定義。

---

## 6. 總結

| 對照項 | 結果 |
|--------|------|
| **!生圖片 參數 vs POST /api/generate/** | ✅ 一致 |
| **!用指定動作生圖片 vs POST /api/generate/custom** | ⚠️ 小差異：generate_pose 的 optional 可補上 sampler_name、scheduler |
| **Slack help 來源** | `slack_commands.COMMAND_SPECS` 為唯一來源 |
| **API 參數來源** | `GenerateRequest` / `GenerateCustomRequest` (schemas) |
| **Queue 參數** | `GenerateParams`，與上述 schema 對齊 |

### 建議

1. **generate_pose** 的 `optional` 補上 `sampler_name`、`scheduler`，與 `generate` 及 API schema 一致（直接修改 `COMMAND_SPECS`）。
2. 長期可考慮由 `GenerateRequest` / `GenerateCustomRequest` 自動產生 COMMAND_SPECS 的 `required`、`optional`，避免手動不同步。
