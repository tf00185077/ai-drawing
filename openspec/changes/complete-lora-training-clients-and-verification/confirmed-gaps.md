# Confirmed Gaps

本文件只記錄已由目前程式碼確認、分配給此批次的缺口。它不是 proposal、design、spec 或 tasks，不包含目標、方案、實作方法或批次內優先級。

**Execution order:** 4/4

**Previous batch:** `harden-lora-training-runtime-lifecycle`

**Next batch:** None

## MCP client surface

- MCP LoRA dataset surface 只有 list 與 agent inspect。
- Dataset prepare 沒有 MCP tool。
- Dataset validate 沒有 MCP tool。
- Caption assessment 沒有 MCP tool。
- Metadata get／validate／update 沒有完整 MCP tool surface。
- Dataset curate dry-run／apply／rollback 沒有 MCP tool。
- Dataset restore 沒有 MCP tool。
- Agent 執行完整 dataset workflow 時仍需直接呼叫 Backend HTTP。
- 已載入的 live MCP schema 沒有獨立驗證證據。

## Bundled frontend surface

- LoRA training page沒有完整 model-family selector。
- LoRA training page沒有 Anima diffusion model、text encoder、VAE 與 tokenizer controls。
- LoRA training page沒有 mixed precision control。
- LoRA training page沒有 network module control。
- LoRA training page沒有明確 trainable-scope／Text Encoder opt-in control。
- LoRA training page沒有完整 dataset/profile approval evidence 顯示。
- LoRA training page沒有個別 durable job logs view。
- LoRA training page沒有個別 durable job cancellation flow。
- LoRA training page沒有完整 registration state。
- LoRA training page沒有 smoke-test terminal result／artifact closure。
- LoRA training page主要使用 aggregate in-memory status，無法顯示完整 durable effective recipe。
- SDXL checkbox、model family 與 Anima-specific fields 的 precedence 沒有完整 client contract。
- LoRA training page的既有自動化測試未覆蓋完整 recipe controls、個別 durable job lifecycle 與 terminal smoke artifact closure。

## Contract and persistence verification evidence

- 沒有針對 Backend restart 後 queued reload exactly once 的測試。
- 沒有針對 orphaned running job reconciliation 的測試。
- 沒有針對 in-memory queue 與 durable nonterminal rows 一致性的測試。
- 沒有涵蓋 cancellation dequeue／process-start race 的測試。
- 沒有涵蓋 silent／low-newline trainer cancellation 的測試證據。
- 沒有涵蓋 process-group TERM／KILL 與 child-process exit 的測試。
- 沒有預放同名 stale artifact 並證明 current job 不會誤收的測試。
- 沒有涵蓋 training success 但 registration failure terminal semantics 的測試。
- 沒有涵蓋 smoke submitted 後 generation completed／failed reconciliation 的測試。
- Source-level MCP tests 不會證明實際 reload 後的 live MCP schema 已暴露新欄位。

## Runtime verification evidence

- 沒有 bounded real trainer probe 證明 effective batch、scope、bucket、cache、optimizer、scheduler、seed 與 precision。
- 沒有真實 runtime log evidence 證明 Anima 只建立預期的 DiT／UNet LoRA modules 與 optimizers。
- 沒有 Apple MPS bounded probe 覆蓋 public preflight／Start 可接受的 precision 與 batch 組合。
- 沒有從 public client payload、Backend durable params、實際 argv 到 artifact metadata 的一致性證據。
- 沒有使用 recipe version／hash 比對 direct run、Backend run 與重跑結果的驗證證據。
- smoke-test submission 沒有端到端追蹤到 terminal generation 與 Gallery artifact 的證據。
