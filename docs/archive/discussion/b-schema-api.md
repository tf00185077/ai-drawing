# B. Schema / API 驗證強化

## 決策清單

| 問題 | 決策 | 細節 |
|------|------|------|
| 1. sampler_name / scheduler 無枚舉 | 加 Literal 枚舉 | OpenAPI 自動文件化，agent 直接從 schema 知道合法值 |
| 2. 缺少 lora_strength / denoise | 兩個都加 | lora_strength: 0.0–2.0；denoise: 0.0–1.0；全鏈補齊（schema → api → apply_params） |
| 3. width/height 上限 | 上限改 4096 | 預設維持 None（ComfyUI workflow 預設值），範圍 ge=256, le=4096 |
| 4. GenerateCustomRequest 重複欄位 | 重構為繼承 | `GenerateCustomRequest(GenerateRequest)` 只加 workflow / image / image_pose |
| 5. checkpoint/lora 存在性驗證 | API 層不驗證 | 讓 agent 先呼叫 available-resources 確認合法名稱（與 A 缺口 1 合併） |

## 合法枚舉值（實作參考）

**sampler_name（Literal）**
```
euler, euler_ancestral, heun, dpm_2, dpm_2_ancestral,
dpmpp_2s_ancestral, dpmpp_sde, dpmpp_2m, dpmpp_2m_sde,
dpmpp_3m_sde, ddim, uni_pc, lcm
```

**scheduler（Literal）**
```
normal, karras, exponential, sgm_uniform, simple, ddim_uniform, beta
```

## 與 A 的重疊

- B 問題 5（available-resources）＝ A 缺口 1：同一件事，只需做一次。
  - API endpoint 已存在：`GET /api/generate/available-resources`
  - 待新增：對應的 MCP tool `get_available_resources`

## 影響範圍（實作時需同步改）

- `backend/app/schemas/generate.py` — 加欄位、加枚舉、改繼承
- `backend/app/api/generate.py` — 補傳 lora_strength / denoise 給 apply_params
- `backend/app/core/workflow.py` — apply_params 加 lora_strength 參數
- `mcp-server/mcp_server/tools/generate.py` — generate_image 補同步參數

---

→ 相關實作項目：[checklist.md](checklist.md) #5–10, #16
