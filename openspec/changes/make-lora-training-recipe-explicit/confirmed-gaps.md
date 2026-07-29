# Confirmed Gaps

本文件只記錄已由目前程式碼確認、分配給此批次的缺口。它不是 proposal、design、spec 或 tasks，不包含目標、方案、實作方法或批次內優先級。

**Execution order:** 2/4

**Previous batch:** `harden-lora-training-start-contract`

**Next batch:** `harden-lora-training-runtime-lifecycle`

## Public recipe contract

- MCP、Backend Start schema、Preflight 與 sd-scripts argv 沒有涵蓋同一組完整 training recipe 欄位。
- Public Start contract 缺少明確的 trainable scope。
- Public Start contract 缺少 gradient accumulation、workers 與 save cadence。
- Public Start contract 缺少 optimizer、scheduler 與 warmup。
- Public Start contract 缺少 training seed。
- Public Start contract 缺少完整 bucket 欄位：`enable_bucket`、`bucket_no_upscale`、`min_bucket_reso`、`max_bucket_reso`、`bucket_reso_steps`。
- Public Start contract 缺少完整 cache 欄位：`cache_latents`、`cache_text_encoder_outputs`、`cache_to_disk`。
- Preflight 無法為上述欄位產生可由 MCP 與 Backend Start 原樣提交的完整 payload。

## Trainable scope

- Text Encoder training 沒有明確 opt-in 欄位與預設語義。
- Anima 使用 `network_module=networks.lora_anima`，但目前 argv 沒有明確的 DiT-only／UNet-only scope 參數。
- requested scope 與 effective scope 沒有分開保存。
- job status 無法分別回報 requested scope 與 effective scope。
- 不支援的 model-family／scope 組合沒有專屬的 structured contract。
- runtime log 與 durable job record 沒有足夠資訊證明實際建立了哪些 trainable modules／optimizers。

## Effective recipe and provenance

- Durable params 只保存部分輸入欄位，不是完整 effective recipe。
- 沒有保存 exact sd-scripts argv。
- 沒有保存與訓練結果相關的環境摘要。
- 沒有保存 optimizer、scheduler、warmup 與 optimizer step 計算結果。
- 沒有保存 seed 的 requested／effective 語義。
- 沒有完整保存 batch、gradient accumulation、repeats、epochs 與 optimizer steps 的關係。
- 沒有完整保存 bucket 與 cache 的 effective values。
- 沒有完整保存 precision、workers 與 save cadence。
- 沒有保存 sd-scripts revision。
- 沒有完整保存解析後的 checkpoint／Anima diffusion model、text encoder、VAE 與 tokenizer identity。
- `allow_unverified_checkpoint` 沒有保存於 durable params，也沒有完整 verification evidence。
- 沒有 recipe schema version。
- 沒有 deterministic recipe hash。
- job status 無法只靠 structured fields 還原或稽核完整 effective recipe。

## Defaults and platform semantics

- Backend training batch 預設目前來自全域設定，預設值為 4，沒有依 model family、resolution 或 execution platform 分流。
- Preflight 直接回傳全域 batch 與 precision 設定，沒有 Apple MPS-aware semantics。
- `mixed_precision` 接受值與 Accelerate／MPS 實際可用組合之間沒有 public preflight contract。
- sd-scripts optimizer、scheduler、warmup、seed 與部分 cache／bucket 行為仍落入未持久化的工具預設。
- seed 的省略、隨機與固定語義沒有在 MCP、Backend、durable params、argv 與 artifact metadata 間統一。
