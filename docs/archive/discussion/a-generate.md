# A. 生圖 function 完整化

## 使用情境確認

使用者口語描述 → agent 自行構建 SD prompt → 選對的 workflow → 呼叫 MCP 生圖。
**Agent 本身是自然語言處理層，不需要系統去解析口語。**

## 決策：UI 下拉選單不需要

目標消費者是 agent，非人工操作 UI。Checkpoint/LoRA 選擇交由 agent 判斷，不需要前端下拉。

## 確認的缺口與解法

| 缺口 | 結論 | 解法 |
|------|------|------|
| 1. Agent 無法探索可用資源 | 必做 | 新增 `get_available_resources` MCP tool（對應已有的 `GET /api/generate/available-resources`） |
| 2. generate_image 參數不完整 | 調整方向 | 核心方向改為「補好 Skill 文件讓 agent 自己構建 prompt」；workflow 現有 5 個（txt2img、txt2img+lora、img2img+lora+pose、txt2img+lora+pose、controlnet_pose）暫時夠用 |
| 3. Agent 無法知道任務完成 | 必做 | DB 加 `job_id` 欄位（migration）+ 新增 `get_job_result(job_id)` MCP tool |
| 4. 無法取消任務 | 需要 | 新增 cancel endpoint + `cancel_job` MCP tool |
| 5. img2img/pose 入口複雜 | 暫緩 | Skill 文件引導 agent 自行組 custom workflow，不額外包 tool |

## 現有 workflow 模板（5 個，暫不擴充）

- `default` — txt2img，無 LoRA
- `default_lora` — txt2img + LoRA
- `txt2img_lora_pose` — txt2img + LoRA + ControlNet pose
- `img2img_lora_pose` — img2img + LoRA + ControlNet pose
- `controlnet_pose` — txt2img + ControlNet pose，無 LoRA

## DB 問題（缺口 3 的前提）

`GeneratedImage` model 目前無 `job_id` 欄位，recording 寫入時也未帶入。
需要加欄位 + migration 才能讓 `get_job_result(job_id)` 運作。

---

→ 相關實作項目：[checklist.md](checklist.md) #1–4, #13–15
