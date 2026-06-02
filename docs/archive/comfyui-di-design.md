# ComfyUI 模組：DI 與 Protocol 設計說明

> 本文說明 `backend/app/core/comfyui.py` 採用 Dependency Injection (DI) 與 Protocol 抽象的動機與效益。

---

## 一、依賴注入 (Dependency Injection) 的好處

### 1.1 可測性 (Testability)

**問題：** 若 `ComfyUIClient` 在建構時直接呼叫 `get_settings()`，每次方法內 `new httpx.Client`，單元測試必須：

- patch 模組層級的 `get_settings`
- patch 模組層級的 `httpx.Client`

這會導致測試脆弱：任何 import 順序、lazy import 都可能讓 patch 失效，且測試與實作細節緊耦合。

**解法：** 提供 `get_comfy_client()` 工廠，由 FastAPI `Depends` 注入。測試時：

```python
# 測試中覆寫依賴
from app.core.comfyui import get_comfy_client

def fake_comfy():
    return FakeComfyUIClient()  # 回傳固定 prompt_id、假 history

app.dependency_overrides[get_comfy_client] = fake_comfy
```

無須 patch 任何模組，測試與真實依賴完全解耦，行為可預測。

### 1.2 配置彈性 (Configuration Flexibility)

**問題：** 單一進程若需連多個 ComfyUI 實例（例如 A/B 測試、開發 / Staging 並存），硬綁 `get_settings()` 無法依情境切換。

**解法：** `get_comfy_client()` 從 config 讀取。需要時可定義額外工廠：

```python
def get_comfy_client_staging() -> ComfyUIClient:
    return ComfyUIClient(base_url=settings.comfyui_staging_url)
```

依路由或 feature flag 注入不同實例。同一介面、不同實作，由組合根（Application 啟動處）決定。

### 1.3 關注點分離 (Separation of Concerns)

**問題：** Route handler 若自己 `new ComfyUIClient()`，既處理 HTTP 請求/回應，又負責建立基礎設施。職責混雜。

**解法：** Handler 只宣告「需要 `ImageGenerationClient`」，由框架注入。建立與生命週期交給 `Depends`。

```python
@router.post("/")
async def trigger_generate(comfy: ComfyUIClient = Depends(get_comfy_client)):
    ...
```

結果：route 層更薄，職責單一，符合「薄 controller」原則。

---

## 二、Protocol 抽象的好處

### 2.1 替換實作 (Implementation Swapping)

**問題：** `generate`、`queue`、`lora_trainer` 若直接依賴 `ComfyUIClient`，未來要：

- 換成 WebSocket 版 ComfyUI
- 整合另一個生圖引擎（如 Replicate API、Stable Diffusion API）

須改動所有呼叫端，違反開放封閉原則。

**解法：** 定義 `ImageGenerationClient` Protocol，只約定 `submit_prompt`、`get_history`、`get_queue`、`fetch_image` 等行為。呼叫端依賴 Protocol，不依賴具體類別：

```python
def run_generation(client: ImageGenerationClient, workflow: dict) -> str:
    return client.submit_prompt(workflow)
```

新增 `ComfyUIWebSocketClient`、`ReplicateAdapter` 時，只需實作 Protocol，並在 DI 處替換，呼叫端零改動。

### 2.2 介面契約明確 (Explicit Contract)

**問題：** 大量使用 `dict[str, Any]` 時，呼叫端不清楚「到底需要哪些 key、回傳格式為何」。容易產生 runtime 錯誤。

**解法：** Protocol 的方法簽名即為契約。IDE 可自動完成，型別檢查器可驗證。文件即程式碼，減少溝通成本。

### 2.3 易於 Mock (Easy Mocking)

**問題：** 測試業務邏輯時，不想真的打 ComfyUI。若依賴具體類別，mock 必須繼承或造出完整實例，麻煩且容易漏掉方法。

**解法：** 依賴 Protocol 時，測試只需提供一個簡單 class，實作同名方法、回傳固定值即可。符合 Protocol 即相容：

```python
class FakeComfyClient:
    def submit_prompt(self, prompt, *, client_id=None, extra_data=None):
        return "fake-prompt-id"
    def get_history(self, prompt_id):
        return {"fake-id": {"outputs": {}}}
    def get_queue(self):
        return {"queue_running": [], "queue_pending": []}
    def fetch_image(self, filename, *, subfolder="", ftype="output"):
        return b"\x89PNG..."
```

Fake 類別可極簡，測試更專注於被測邏輯。

---

## 三、綜合效果

| 情境 | 無 DI/Protocol | 有 DI/Protocol |
|------|----------------|----------------|
| 新增類似功能 | 多處 copy-paste，改多個檔案 | 1–2 處：新實作 + 新 Depends 工廠 |
| 換生圖引擎 | 改所有呼叫端 | 只改 DI 綁定，業務層不動 |
| 單獨測試業務邏輯 | 須 patch 或起真實 ComfyUI | 注入 Fake，無須網路 |
| 外部 API 變更 | 可能散落多處 | 只改 `ComfyUIClient` 內部，Protocol 對外保持穩定 |
| 多環境 / 多實例 | 難以切換 | 不同 Depends 工廠即可 |

---

## 四、使用範例

### 4.1 在 FastAPI 路由中使用

```python
from fastapi import Depends
from app.core.comfyui import ComfyUIClient, get_comfy_client

@router.post("/")
async def trigger_generate(comfy: ComfyUIClient = Depends(get_comfy_client)):
    prompt_id = comfy.submit_prompt(workflow)
    return {"prompt_id": prompt_id}
```

### 4.2 在背景任務 / 服務中使用

```python
# 由呼叫方注入，或從 DI 取得
def run_batch(client: ImageGenerationClient, workflows: list[dict]):
    for wf in workflows:
        client.submit_prompt(wf)
```

### 4.3 測試時覆寫

```python
def test_trigger_generate(client: TestClient, app: FastAPI):
    def fake():
        return FakeComfyClient()
    app.dependency_overrides[get_comfy_client] = fake
    resp = client.post("/api/generate/", json={...})
    assert resp.status_code == 200
```

---

## 五、參考

- 專案規則：`.cursor/rules/auto-draw-project.mdc`
- 擴展性審核：`.cursor/skills/python-extensibility-review/SKILL.md`
- ComfyUI API：`.cursor/skills/comfyui-api-client/SKILL.md`
