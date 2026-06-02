# 代理人 A · 生圖模組 · 擴展性審核報告

> 依據 `python-extensibility-review` skill 審核，審核日期：2026-03-07

## Overall Verdict

**有風險（Minor–Major）** — 可正常運作，Phase 4 前建議處理部分項目。

## 關鍵後續項目（依優先序）

| 優先 | 項目 | Fix Urgency | 說明 |
|------|------|-------------|------|
| 1 | `MAX_PENDING`、`WORKFLOW_TEMPLATE` 移至 config | when-touching | 便於部署調整 |
| 2 | 每圖一 Session 改為單一 transaction | when-touching | 降低 DB 連線壓力 |
| 3 | queue recording 抽象／注入 | before-phase-4 | Phase 4 lora_trainer 需共用 recording |
| 4 | queue 類別化、消除模組級全域狀態 | when-touching | 多實例、測試隔離 |
| 5 | workflow 結構可配置化 | when-touching | 若 workflow 結構開始多樣化時 |

## 主要風險摘要

- **結構假設耦合**：`workflow.apply_params` 依賴固定 `class_type`，結構變更需改程式
- **隱藏全域狀態**：`queue.py` 使用模組級 `_pending`、`_running` 等
- **無 DI 注入**：queue worker 直接 `get_comfy_client()`、`recording_save()`，測試需 patch

## 完整報告

詳見對話紀錄或重新執行 `python-extensibility-review` skill 對 `core/workflow.py`、`core/queue.py`、`api/generate.py` 審核。
