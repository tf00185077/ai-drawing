# 代理人 D（LoRA 訓練與產圖串接）擴展性審核報告

> 依據 `python-extensibility-review` Skill 執行，審核範圍：`lora_trainer.py`、`lora_train.py`（API）

---

## 1. Overall Verdict

**🟡 有風險（Minor）**

架構符合 internal-interfaces 契約，職責分離清楚，subprocess 路徑與參數均由 config 載入。主要風險：
- 模組級共享可變狀態（`_queue`、`_running`、`_on_complete_callbacks`、`_worker_thread`）
- Kohya 訓練參數（learning_rate、resolution、batch_size 等）硬編碼
- 無 KohyaAdapter / TrainerProtocol 抽象，未來換訓練工具或加 SDXL 時需改動多處

可運作、可測試，D3 產圖 Pipeline 與 D4 UI 可依現有介面對接。

---

## 2. Architecture Summary

| 模組 | 職責 | 依賴 |
|------|------|------|
| `lora_trainer.py` | 佇列、subprocess 呼叫 Kohya、dataset_config 生成、完成回呼 | config |
| `lora_train.py` | REST API：start、status、trigger-check（stub） | lora_trainer, schemas |

**資料流**：`POST /start` → `enqueue()` → 背景 worker → `subprocess` → `train_network.py` → 完成 → `register_on_complete` callback

---

## 3. Positive Findings

- **契約對齊**：enqueue、get_status、register_on_complete 與 internal-interfaces 完全一致
- **設定集中**：`sd_scripts_path`、`lora_train_dir`、`lora_default_checkpoint` 從 config 載入，無硬編碼
- **職責分離**：API 層只做驗證與映射，業務邏輯在 lora_trainer
- **callback 設計**：register_on_complete 為 D3 產圖 Pipeline 預留明確接入點
- **測試覆蓋**：test_lora_trainer 涵蓋 enqueue 驗證、get_status、API 202
- **subprocess 可執行檔路徑**：從 config 讀取，符合 skill 建議

---

## 4. Extensibility Risks

| 風險 | 說明 | 嚴重度 |
|------|------|--------|
| 隱藏共享可變狀態 | `_queue`、`_running`、`_on_complete_callbacks`、`_worker_thread` 為模組級，多實例或測試並行時可能互相影響 | **Minor** |
| Kohya 訓練參數硬編碼 | `learning_rate`、`resolution`、`batch_size`、`class_tokens`、`num_repeats` 寫死在 `_run_training_subprocess`、`_write_dataset_config` | **Major** |
| 無 TrainerProtocol 抽象 | 直接呼叫 subprocess；若換工具（如 diffusers、自訂腳本）或加 SDXL 需改 lora_trainer 核心 | **Major** |
| IMAGE_EXTENSIONS 重複 | lora_trainer 自訂 `_IMAGE_EXTENSIONS`，與 watcher、lora_docs 重複 | **Minor** |
| queue/recording 未注入 | D3 將在 callback 直接 import queue、recording；Phase 4 前 A/B 抽象尚未完成，D 採用 module import 可接受 | **Minor** |

---

## 5. Coupling & Boundary Issues

- **lora_trainer → config**：直接 `get_settings()`，測試需 patch，尚可接受
- **lora_trainer → subprocess**：無 Adapter，Kohya CLI 格式變更會直接影響 lora_trainer
- **output 路徑假設**：依賴 Kohya 輸出 `{output_name}.safetensors` 或 `{prefix}*.safetensors`，格式變更需改 `_get_output_lora_path` 與 worker 邏輯

---

## 6. Testability Issues

- **`_reset_for_test`**：提供清空佇列，測試使用 mock_worker 避免 subprocess，設計合理
- **worker 無單獨整合測試**：實際 subprocess 流程未測，需 Kohya 環境；可接受，單元測試已涵蓋核心邏輯
- **ValueError 字串比對**：API 用 `"已在佇列" in msg` 判斷 409，略脆弱；可改為自訂 Exception 類別

---

## 7. Concrete Refactor Suggestions

### 7.1 Kohya 訓練參數可配置（Fix Urgency: when-touching）

```python
# config.py 新增
lora_learning_rate: str = "1e-4"
lora_resolution: int = 512
lora_batch_size: int = 4
lora_class_tokens: str = "sks"
lora_num_repeats: int = 10
# lora_trainer 從 settings 讀取
```

### 7.2 抽出 TrainerProtocol（Fix Urgency: when-touching）

未來若支援 SDXL 或其它訓練方式時再抽象：

```python
class LoRATrainerProtocol(Protocol):
    def run(self, folder: str, checkpoint: str, epochs: int, output_dir: Path) -> Path: ...
# KohyaTrainer 實作，lora_trainer 透過 DI 注入
```

### 7.3 IMAGE_EXTENSIONS 共用（Fix Urgency: when-touching）

與 Agent C 審核一致，抽出至 `app/core/constants.py`，watcher、lora_docs、lora_trainer 共用。

### 7.4 佇列類別化（Fix Urgency: when-touching）

與 queue.py 相同模式，將 `_queue`、`_running`、worker 封裝進 `LoraTrainerService` class，main 建立單例注入，消除模組級全域狀態。

---

## 8. Priority Order of Fixes

| 優先序 | 項目 | Fix Urgency | 理由 |
|--------|------|-------------|------|
| 1 | Kohya 訓練參數可配置 | when-touching | 不同模型／資料需調整 resolution、lr |
| 2 | IMAGE_EXTENSIONS 共用 | when-touching | 與 C 一致 |
| 3 | TrainerProtocol 抽象 | when-touching | 僅在要加 SDXL 或第二種訓練方式時再做 |
| 4 | 佇列類別化 | when-touching | 與 queue.py 擴展性審核一致 |
| 5 | ValueError → 自訂 Exception | when-touching | API 錯誤碼判斷更穩健 |

---

## 9. 使用者測試方法與預期結果

| 測試類型 | 指令／步驟 | 預期結果 |
|----------|------------|----------|
| 單元測試 | `cd backend && pytest tests/test_lora_trainer.py -v` | 5 passed |
| API start | 起後端 → POST `/api/lora-train/start`（body: folder, checkpoint, epochs） | 202，job_id、status: queued |
| API status | GET `/api/lora-train/status` | 200，status: idle/queued/running、queue 陣列 |
| 訓練完成 | 需 Kohya 環境，真實執行訓練 | 完成後 callback 被呼叫（D3 實作後驗證） |

---

## 10. 總結

代理人 D 的 lora_trainer **符合契約、可正常運作**，測試涵蓋 enqueue、get_status、API。擴展性問題：
1. Kohya 參數應可配置，避免寫死
2. 模組級全域狀態與 queue.py 類似，when-touching 時可類別化
3. 無 TrainerProtocol 不影響 D2–D4，僅在未來加第二種訓練方式時需重構

其餘為 when-touching 級別，不阻礙 D2、D3、D4 開發。
