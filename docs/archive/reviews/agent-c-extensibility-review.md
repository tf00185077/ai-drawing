# 代理人 C（LoRA 文件工具）擴展性審核報告

> 依據 `python-extensibility-review` Skill 執行，審核範圍：`watcher.py`、`lora_docs.py`、`wd_tagger.py`、`LoraDocs.tsx`

---

## 1. Overall Verdict

**🟡 有風險（Minor）**

整體架構合理、API 契約對齊，業務邏輯與職責分離尚可。主要風險集中在：
- 模組級共享可變狀態（watcher 的 `_observer`、`_debounce_timers`）
- WD Tagger 參數硬編碼，缺乏 CaptionProvider 抽象
- `IMAGE_EXTENSIONS`、路徑 sanitize 邏輯重複

可運作、可測試，但未來擴展（如加 BLIP2、支援影片 caption）時會需重構。

---

## 2. Architecture Summary

| 模組 | 職責 | 依賴 |
|------|------|------|
| `watcher.py` | 監聽 watch_dirs，新圖觸發 WD Tagger | config, wd_tagger |
| `wd_tagger.py` | subprocess 呼叫 tag_images_by_wd14_tagger.py | config |
| `lora_docs.py` | REST API：upload、caption、batch-prefix、download-zip、files | config, wd_tagger, schemas |

**資料流**：`watch_dirs` → watchdog → `on_new_image` → WD Tagger → `.txt`  
上傳 API 直接寫檔並呼叫 `run_wd_tagger`，路徑驗證與 sanitize 在 API 層完成。

---

## 3. Positive Findings

- **職責分離**：API 層負責驗證、解析、回應；`wd_tagger` 獨立為共用服務；schema 與 API 契約對齊
- **path traversal 防護**：`_sanitize_folder`、`_resolve_image_and_caption` 正確攔截 `..` 與無效字元
- **防抖設計**：watcher 使用 debounce 避免大量上傳時重複執行 WD Tagger，實務上合理
- **測試覆蓋**：`test_lora_docs.py`、`test_watcher.py` 涵蓋主要流程與邊界，使用 mock 隔離 config 與 wd_tagger
- **設定集中**：`lora_train_dir`、`sd_scripts_path`、`watch_dirs` 均由 config 載入，無硬編碼路徑

---

## 4. Extensibility Risks

| 風險 | 說明 | 嚴重度 |
|------|------|--------|
| 隱藏共享可變狀態 | `watcher._observer`、`_debounce_timers` 為模組級變數，多實例或測試並行時可能互相影響 | **Minor** |
| CaptionProvider 未抽象 | `wd_tagger` 直接實作 WD Tagger；若加 BLIP2 需改 watcher + lora_docs 多處 | **Major** |
| IMAGE_EXTENSIONS 重複 | watcher、lora_docs 各定義一次，未來支援新格式需改兩處 | **Minor** |
| WD Tagger 參數硬編碼 | `repo_id`、`batch_size`、`thresh`、`timeout` 寫死在 wd_tagger.py | **Major** |
| GET /files 未列 API 契約 | 實際有 `/api/lora-docs/files`，但 api-contract.md 未記載 | **Minor** |

---

## 5. Coupling & Boundary Issues

- **watcher → wd_tagger**：watcher 直接 import `run_wd_tagger`，若改為 BLIP2 需改 watcher 內程式碼
- **lora_docs → wd_tagger**：同上，upload 成功後直接呼叫 `run_wd_tagger`
- **路徑 sanitize 重複**：`_sanitize_folder` 與 `_resolve_image_and_caption` 內 path traversal 邏輯相似，可抽成共用

---

## 6. Testability Issues

- **watcher 全域狀態**：`stop_watching()` 會清空 `_observer`，若測試未呼叫 `stop_watching` 可能影響後續測試（目前 test 有呼叫）
- **wd_tagger 無單元測試**：`run_wd_tagger` 僅在 lora_docs 測試中 mock，未針對 timeout、腳本不存在等情境單獨測試
- **fixture 重複**：`test_lora_docs.py` 未使用共用 fixture 覆蓋 `get_settings`，多個 test 各自 patch，尚可接受

---

## 7. Concrete Refactor Suggestions

### 7.1 抽出 CaptionProvider Protocol（Fix Urgency: before-phase-4）

```python
# app/services/caption_provider.py
from typing import Protocol
from pathlib import Path

class CaptionProvider(Protocol):
    def tag_directory(self, image_dir: Path) -> None: ...

# wd_tagger.py 實作此 Protocol
# 未來 BLIP2 可加第二實作，watcher / lora_docs 透過 DI 注入
```

### 7.2 WD Tagger 參數可配置（Fix Urgency: when-touching）

```python
# config.py 新增
wd_tagger_repo_id: str = "SmilingWolf/wd-swinv2-tagger-v3"
wd_tagger_batch_size: int = 4
wd_tagger_thresh: float = 0.35
wd_tagger_timeout: int = 120

# wd_tagger.py 從 settings 讀取
```

### 7.3 抽出 IMAGE_EXTENSIONS 常數（Fix Urgency: when-touching）

```python
# app/core/constants.py 或 app/schemas/lora_docs.py 頂層
IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"})
# watcher、lora_docs 共用
```

### 7.4 watcher 狀態封裝（Fix Urgency: when-touching）

將 `_observer`、`_debounce_timers` 封裝進 class，避免全域可變狀態：

```python
class WatcherService:
    def __init__(self): ...
    def start(self) -> None: ...
    def stop(self) -> None: ...
# main.py 建立單例並注入
```

---

## 8. Priority Order of Fixes

| 優先序 | 項目 | Fix Urgency | 理由 |
|--------|------|-------------|------|
| 1 | WD Tagger 參數可配置 | when-touching | 不同環境需調整 batch_size、thresh |
| 2 | CaptionProvider Protocol | before-phase-4 | D 軌道整合前若有 BLIP2 需求，先抽象較省事 |
| 3 | IMAGE_EXTENSIONS 共用 | when-touching | 避免重複定義 |
| 4 | api-contract 補 GET /files | when-touching | 文件完整性 |
| 5 | watcher 狀態封裝 | when-touching | 多實例／測試並行時更穩健 |

---

## 9. 使用者測試方法與預期結果

| 測試類型 | 指令／步驟 | 預期結果 |
|----------|------------|----------|
| 單元測試（lora_docs） | `cd backend && pytest tests/test_lora_docs.py -v` | 全部 PASSED |
| 單元測試（watcher） | `cd backend && pytest tests/test_watcher.py -v` | 全部 PASSED |
| API 上傳 | 起後端 → POST `/api/lora-docs/upload`（multipart files + folder） | 200，回傳 uploaded、items |
| API 下載 ZIP | GET `/api/lora-docs/download-zip?folder=my_lora` | 200，Content-Type: application/zip |
| Caption 編輯 | GET `/api/lora-docs/caption/my_lora/img1.png` → PUT 更新 | 200，內容正確 |
| 監聽觸發 | 設定 watch_dirs，放入新圖，等 DEBOUNCE_SECONDS | 同目錄產生 .txt（需 sd-scripts 環境） |

---

## 10. 總結

代理人 C 的實作**符合契約、可正常運作**，測試涵蓋度足夠。擴展性問題集中在：
1. 未來若支援 BLIP2 或其它 caption 來源，需先抽出 CaptionProvider
2. WD Tagger 參數應可配置，避免寫死

其餘為 when-touching 級別的小幅改進，不影響當前開發。
