# Confirmed Gaps

本文件只記錄已由目前程式碼確認、分配給此批次的缺口。它不是 proposal、design、spec 或 tasks，不包含目標、方案、實作方法或批次內優先級。

**Execution order:** 3/4

**Previous batch:** `make-lora-training-recipe-explicit`

**Next batch:** `complete-lora-training-clients-and-verification`

## Durable queue and restart state

- Backend 啟動 LoRA worker 時不會從 durable DB 重新載入 queued jobs。
- Backend 重啟後，DB 中既有 queued row 與 in-memory queue 可能不一致。
- Backend 重啟後，舊 running job 沒有 reconciliation terminal state。
- in-memory aggregate status 可以顯示 idle，同時 durable DB 仍保有 nonterminal jobs。
- LoRA worker 沒有明確的 graceful shutdown／join lifecycle。
- active trainer process 與 Backend shutdown 沒有一致的 lifecycle record。
- 目前沒有真正的 training state resume；epoch `.safetensors` 不包含 optimizer、scheduler 與 global-step state。

## Dataset concurrency


- Dataset／training lock 使用 process-local `threading.Lock`。
- 多 Backend worker／process 之間沒有共同的 dataset mutation／training exclusion state。

## Cancellation

- dequeue、running registration 與 cancellation 之間沒有 durable atomic ownership contract。
- cancellation 只對單一 `Popen` process 呼叫 `terminate()`。
- 沒有完整 process-group termination state。
- 沒有 TERM grace-period 與後續 KILL 的 lifecycle fields。
- durable job 只保存 `cancel_requested_at`，沒有 TERM timestamp、KILL timestamp、process exit timestamp 與 final cancellation reason。
- Backend 沒有與 active trainer PID 綁定的 macOS power assertion state。

## Output and artifact ownership

- output name 只由 dataset folder 衍生，同一 dataset 的不同 jobs 共用相同 output namespace。
- worker 找不到標準輸出檔時，會接受第一個 `prefix*.safetensors` glob 結果。
- fallback artifact 選取沒有排序與 current-job ownership evidence。
- process exit 0 後的 artifact 存在性檢查無法排除同名 stale artifact。
- durable per-job artifact 與 ComfyUI 可變 registration alias 沒有分離的 identity。
- registration alias 沒有明確 version／overwrite record。
- training output verified 與 registration success 沒有獨立狀態。
- registration 失敗時 job 仍會寫成 `status=completed`、`stage=completed`。
- registration failure 沒有獨立 terminal semantics。

## Smoke-test lifecycle

- smoke-test operation 只保存 generation submission 狀態。
- LoRA job 不會自動 reconciliation generation job 的 terminal completed／failed state。
- `smoke_test_artifact` 沒有由目前 smoke-test submission flow 填入最終 Gallery artifact。
- `smoke_test_status=submitted` 無法證明新 LoRA 已成功產圖。

## Logs and progress state

- log tail implementation 會先讀取完整 log 檔，再截取最後 N 行。
- worker 的 `output_lines` list 會隨 subprocess output 持續增長。
- durable progress 沒有 current step 與 total step 的獨立欄位。
- progress、epoch 與 step evidence 主要依賴文字解析，沒有完整 structured runtime record。
- cancellation、process termination 與 final status 的完整時間序列沒有出現在 job status。
