# Discord Bot 直呼本機生圖 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 `discord-bot/`，讓使用者用 `/draw` 從 style preset（含 profile）選畫風、輸入 prompt/寬/高/張數，直接呼叫 backend 生圖，`/result id:<job_id>` 反查並貼回圖；全程不經 LLM。

**Architecture:** discord.py 前端 + httpx 呼叫既有 backend HTTP 端點。可測的純邏輯（驗證、payload/URL 組裝、backend 呼叫）抽成獨立模組並用 mock 測；discord UI 為薄 glue，靠手動 smoke。不改動 backend。

**Tech Stack:** Python 3.11、discord.py 2.x、httpx、python-dotenv、pytest + pytest-asyncio。

## Global Constraints

- 不改動 `backend/`——只新增 `discord-bot/`。
- Secret 只進被 git ignore 的 `.env`；`.env.example` 僅放占位符（AGENTS.md 安全規則）。
- 寬/高範圍 256–2048（整數）；張數範圍 1–8（整數），留空視為 4。
- batch 由使用者輸入，經 compose `overrides.batch_size` 帶入。
- `/result` 用 `GET /api/gallery/?image_name=<job_id[:8]>&limit=8` 撈回該 job 全部圖。
- backend 端點契約（勿更動呼叫形狀）：
  - `GET /api/style-presets/` → `{items:[{id, name, chinese_name, profiles:[...]}]}`
  - `POST /api/style-presets/{id}/compose` body `{content_prompt, profile?, overrides?}` → `{preset_id, profile, generation}`
  - `POST /api/generate/` body=generation → 201 `{job_id, status, message}`
  - `GET /api/generate/job/{job_id}` → `{status, ...}`（status ∈ queued/running/failed/completed；failed 帶 `error`/`node_errors`）
  - `GET /api/gallery/?image_name=&limit=` → `{items:[{id, image_path, image_url, ...}], total}`
  - `/gallery/<相對路徑>` 為靜態圖檔（`image_url` 即 `/gallery/...`）。
- 所有工作在分支 `feat/discord-bot` 上；每個 Task 結尾 commit。

---

### Task 1: 專案骨架 + 設定載入

**Files:**
- Create: `discord-bot/requirements.txt`
- Create: `discord-bot/.env.example`
- Create: `discord-bot/.gitignore`
- Create: `discord-bot/pytest.ini`
- Create: `discord-bot/bot/__init__.py`（空檔）
- Create: `discord-bot/bot/config.py`
- Create: `discord-bot/tests/__init__.py`（空檔）
- Test: `discord-bot/tests/test_config.py`

**Interfaces:**
- Produces:
  - `bot.config.Config`（frozen dataclass，欄位 `discord_token: str`、`guild_id: int`、`backend_base_url: str`）
  - `bot.config.load_config(env: dict | None = None) -> Config`
  - `bot.config.ConfigError(Exception)`

- [ ] **Step 1: 建立依賴與設定範本檔**

`discord-bot/requirements.txt`:
```
discord.py>=2.3,<3
httpx>=0.27,<1
python-dotenv>=1.0,<2
pytest>=8,<9
pytest-asyncio>=0.23,<1
```

`discord-bot/.env.example`:
```
# Discord bot token（Developer Portal 取得，勿提交真實值）
DISCORD_TOKEN=
# 只在此 Discord 伺服器註冊指令
GUILD_ID=
# backend 位址，預設同機
BACKEND_BASE_URL=http://localhost:8000
```

`discord-bot/.gitignore`:
```
.env
__pycache__/
*.pyc
.pytest_cache/
```

`discord-bot/pytest.ini`:
```
[pytest]
asyncio_mode = auto
testpaths = tests
```

- [ ] **Step 2: 寫失敗測試**

`discord-bot/tests/test_config.py`:
```python
import pytest

from bot.config import Config, ConfigError, load_config


def test_load_config_reads_all_fields():
    cfg = load_config({
        "DISCORD_TOKEN": "tok",
        "GUILD_ID": "123",
        "BACKEND_BASE_URL": "http://localhost:8000/",
    })
    assert cfg == Config(discord_token="tok", guild_id=123, backend_base_url="http://localhost:8000")


def test_backend_base_url_defaults():
    cfg = load_config({"DISCORD_TOKEN": "tok", "GUILD_ID": "1"})
    assert cfg.backend_base_url == "http://localhost:8000"


def test_missing_token_raises():
    with pytest.raises(ConfigError) as e:
        load_config({"GUILD_ID": "1"})
    assert "DISCORD_TOKEN" in str(e.value)


def test_non_integer_guild_raises():
    with pytest.raises(ConfigError):
        load_config({"DISCORD_TOKEN": "t", "GUILD_ID": "abc"})
```

- [ ] **Step 3: 執行測試確認失敗**

Run: `cd discord-bot && python -m pytest tests/test_config.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'bot.config'`）

- [ ] **Step 4: 實作 config.py**

`discord-bot/bot/config.py`:
```python
"""環境變數載入；缺必要值即 fail-fast。"""
import os
from dataclasses import dataclass


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Config:
    discord_token: str
    guild_id: int
    backend_base_url: str


def load_config(env: dict | None = None) -> Config:
    if env is None:
        from dotenv import load_dotenv

        load_dotenv()
        env = dict(os.environ)

    token = env.get("DISCORD_TOKEN")
    guild = env.get("GUILD_ID")
    base = env.get("BACKEND_BASE_URL") or "http://localhost:8000"

    missing = [name for name, value in (("DISCORD_TOKEN", token), ("GUILD_ID", guild)) if not value]
    if missing:
        raise ConfigError(f"缺少環境變數：{', '.join(missing)}")

    try:
        guild_id = int(guild)
    except (TypeError, ValueError):
        raise ConfigError("GUILD_ID 必須是整數")

    return Config(discord_token=token, guild_id=guild_id, backend_base_url=base.rstrip("/"))
```

- [ ] **Step 5: 執行測試確認通過**

Run: `cd discord-bot && python -m pytest tests/test_config.py -v`
Expected: PASS（4 passed）

- [ ] **Step 6: Commit**

```bash
git add discord-bot/
git commit -m "feat(discord-bot): scaffold project and config loader"
```

---

### Task 2: 輸入驗證純函式

**Files:**
- Create: `discord-bot/bot/validation.py`
- Test: `discord-bot/tests/test_validation.py`

**Interfaces:**
- Produces:
  - `bot.validation.ValidationError(Exception)`
  - `parse_dimension(raw: str, *, field: str) -> int`（256–2048，否則 raise）
  - `parse_count(raw: str, *, default: int = 4) -> int`（空字串→default；1–8，否則 raise）
  - `build_gallery_download_url(base_url: str, image_url: str) -> str`

- [ ] **Step 1: 寫失敗測試**

`discord-bot/tests/test_validation.py`:
```python
import pytest

from bot.validation import (
    ValidationError,
    build_gallery_download_url,
    parse_count,
    parse_dimension,
)


def test_parse_dimension_valid():
    assert parse_dimension("1024", field="寬") == 1024
    assert parse_dimension("  512 ", field="寬") == 512


@pytest.mark.parametrize("raw", ["255", "2049", "abc", "", "3.5"])
def test_parse_dimension_invalid(raw):
    with pytest.raises(ValidationError):
        parse_dimension(raw, field="寬")


def test_parse_count_empty_returns_default():
    assert parse_count("") == 4
    assert parse_count("   ") == 4


def test_parse_count_valid():
    assert parse_count("1") == 1
    assert parse_count("8") == 8


@pytest.mark.parametrize("raw", ["0", "9", "-1", "x"])
def test_parse_count_invalid(raw):
    with pytest.raises(ValidationError):
        parse_count(raw)


def test_build_gallery_download_url():
    assert build_gallery_download_url("http://h:8000", "/gallery/2026/x.png") == "http://h:8000/gallery/2026/x.png"
    assert build_gallery_download_url("http://h:8000/", "gallery/x.png") == "http://h:8000/gallery/x.png"
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd discord-bot && python -m pytest tests/test_validation.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'bot.validation'`）

- [ ] **Step 3: 實作 validation.py**

`discord-bot/bot/validation.py`:
```python
"""Modal 輸入的純函式驗證與 URL 組裝。"""


class ValidationError(Exception):
    pass


def parse_dimension(raw: str, *, field: str) -> int:
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        raise ValidationError(f"{field}必須是整數")
    if not (256 <= value <= 2048):
        raise ValidationError(f"{field}必須介於 256–2048")
    return value


def parse_count(raw: str, *, default: int = 4) -> int:
    text = str(raw or "").strip()
    if text == "":
        return default
    try:
        value = int(text)
    except ValueError:
        raise ValidationError("張數必須是整數")
    if not (1 <= value <= 8):
        raise ValidationError("張數必須介於 1–8")
    return value


def build_gallery_download_url(base_url: str, image_url: str) -> str:
    return f"{base_url.rstrip('/')}/{image_url.lstrip('/')}"
```

- [ ] **Step 4: 執行測試確認通過**

Run: `cd discord-bot && python -m pytest tests/test_validation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add discord-bot/bot/validation.py discord-bot/tests/test_validation.py
git commit -m "feat(discord-bot): input validation helpers"
```

---

### Task 3: ApiClient 低階 backend 呼叫

**Files:**
- Create: `discord-bot/bot/api_client.py`
- Test: `discord-bot/tests/test_api_client.py`

**Interfaces:**
- Consumes: 無（httpx 注入）
- Produces:
  - `bot.api_client.BackendError(Exception)`（附 `.status_code: int | None`）
  - `class ApiClient`：
    - `__init__(self, base_url: str, client: httpx.AsyncClient | None = None)`
    - `async list_presets() -> list[dict]`
    - `async compose(preset_id: str, *, content_prompt: str, profile: str | None = None, overrides: dict | None = None) -> dict`（回 generation）
    - `async submit_generate(generation: dict) -> str`（回 job_id）
    - `async get_job(job_id: str) -> dict`
    - `async list_job_images(job_id: str) -> list[dict]`
    - `async download(image_url: str) -> bytes`

- [ ] **Step 1: 寫失敗測試**

`discord-bot/tests/test_api_client.py`:
```python
import httpx
import pytest

from bot.api_client import ApiClient, BackendError


def make_api(handler):
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    return ApiClient("http://test", client=client)


async def test_list_presets():
    def handler(req):
        assert req.url.path == "/api/style-presets/"
        return httpx.Response(200, json={"items": [{"id": "a", "name": "A", "profiles": []}]})

    api = make_api(handler)
    items = await api.list_presets()
    assert items[0]["id"] == "a"


async def test_compose_sends_overrides_and_returns_generation():
    def handler(req):
        assert req.url.path == "/api/style-presets/p1/compose"
        import json

        body = json.loads(req.content)
        assert body["content_prompt"] == "a cat"
        assert body["profile"] == "day"
        assert body["overrides"] == {"width": 1024, "height": 768, "batch_size": 6}
        return httpx.Response(200, json={"preset_id": "p1", "profile": "day", "generation": {"prompt": "x", "batch_size": 6}})

    api = make_api(handler)
    gen = await api.compose("p1", content_prompt="a cat", profile="day", overrides={"width": 1024, "height": 768, "batch_size": 6})
    assert gen == {"prompt": "x", "batch_size": 6}


async def test_submit_generate_returns_job_id():
    def handler(req):
        assert req.url.path == "/api/generate/"
        return httpx.Response(201, json={"job_id": "job-123", "status": "queued"})

    api = make_api(handler)
    assert await api.submit_generate({"prompt": "x"}) == "job-123"


async def test_get_job():
    def handler(req):
        assert req.url.path == "/api/generate/job/job-123"
        return httpx.Response(200, json={"status": "running", "job_id": "job-123"})

    api = make_api(handler)
    assert (await api.get_job("job-123"))["status"] == "running"


async def test_list_job_images_filters_by_job_prefix():
    def handler(req):
        assert req.url.path == "/api/gallery/"
        assert req.url.params["image_name"] == "job-1234"
        assert req.url.params["limit"] == "8"
        return httpx.Response(200, json={"items": [{"id": 1, "image_url": "/gallery/x.png"}], "total": 1})

    api = make_api(handler)
    items = await api.list_job_images("job-1234-abcd-efgh")
    assert items[0]["image_url"] == "/gallery/x.png"


async def test_download_returns_bytes():
    def handler(req):
        assert req.url.path == "/gallery/x.png"
        return httpx.Response(200, content=b"PNGDATA")

    api = make_api(handler)
    assert await api.download("/gallery/x.png") == b"PNGDATA"


async def test_backend_error_maps_detail_message():
    def handler(req):
        return httpx.Response(404, json={"detail": "找不到風格 preset: p9"})

    api = make_api(handler)
    with pytest.raises(BackendError) as e:
        await api.compose("p9", content_prompt="x")
    assert e.value.status_code == 404
    assert "找不到風格 preset" in str(e.value)
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd discord-bot && python -m pytest tests/test_api_client.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'bot.api_client'`）

- [ ] **Step 3: 實作 api_client.py（低階）**

`discord-bot/bot/api_client.py`:
```python
"""backend HTTP 包裝——唯一知道 backend 契約的地方。"""
import httpx


class BackendError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _error_message(response: httpx.Response) -> str:
    try:
        data = response.json()
    except Exception:
        return response.text or f"HTTP {response.status_code}"
    if isinstance(data, dict):
        detail = data.get("detail", data)
        if isinstance(detail, dict):
            return detail.get("message") or detail.get("error") or str(detail)
        return str(detail)
    return str(data)


class ApiClient:
    def __init__(self, base_url: str, client: httpx.AsyncClient | None = None):
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.AsyncClient(base_url=self._base_url, timeout=30.0)

    def _check(self, response: httpx.Response) -> httpx.Response:
        if response.status_code >= 400:
            raise BackendError(_error_message(response), status_code=response.status_code)
        return response

    async def list_presets(self) -> list[dict]:
        r = self._check(await self._client.get("/api/style-presets/"))
        return r.json().get("items", [])

    async def compose(self, preset_id: str, *, content_prompt: str,
                      profile: str | None = None, overrides: dict | None = None) -> dict:
        body: dict = {"content_prompt": content_prompt}
        if profile:
            body["profile"] = profile
        if overrides:
            body["overrides"] = overrides
        r = self._check(await self._client.post(f"/api/style-presets/{preset_id}/compose", json=body))
        return r.json()["generation"]

    async def submit_generate(self, generation: dict) -> str:
        r = self._check(await self._client.post("/api/generate/", json=generation))
        return r.json()["job_id"]

    async def get_job(self, job_id: str) -> dict:
        r = self._check(await self._client.get(f"/api/generate/job/{job_id}"))
        return r.json()

    async def list_job_images(self, job_id: str) -> list[dict]:
        r = self._check(await self._client.get(
            "/api/gallery/", params={"image_name": job_id[:8], "limit": 8}
        ))
        return r.json().get("items", [])

    async def download(self, image_url: str) -> bytes:
        r = self._check(await self._client.get(image_url))
        return r.content
```

- [ ] **Step 4: 執行測試確認通過**

Run: `cd discord-bot && python -m pytest tests/test_api_client.py -v`
Expected: PASS（7 passed）

- [ ] **Step 5: Commit**

```bash
git add discord-bot/bot/api_client.py discord-bot/tests/test_api_client.py
git commit -m "feat(discord-bot): backend api client (low-level calls)"
```

---

### Task 4: ApiClient 高階編排（compose→submit、撈結果）

**Files:**
- Modify: `discord-bot/bot/api_client.py`（新增兩個方法）
- Test: `discord-bot/tests/test_api_client.py`（新增測試）

**Interfaces:**
- Consumes: Task 3 的 `ApiClient` 低階方法
- Produces（`ApiClient` 新增）：
  - `async compose_and_submit(preset_id: str, profile: str | None, prompt: str, width: int, height: int, count: int) -> str`（回 job_id；overrides 帶 `{width, height, batch_size: count}`）
  - `async collect_job_result(job_id: str) -> dict`。回傳形狀：
    - queued/running：`{"status": "<queued|running>"}`
    - failed：`{"status": "failed", "error": <str|None>, "node_errors": <list>}`
    - completed：`{"status": "completed", "images": [(filename, bytes), ...], "urls": [絕對url, ...]}`

- [ ] **Step 1: 寫失敗測試（附加到 test_api_client.py 末尾）**

```python
async def test_compose_and_submit_builds_overrides():
    calls = {}

    def handler(req):
        import json

        if req.url.path.endswith("/compose"):
            calls["overrides"] = json.loads(req.content)["overrides"]
            return httpx.Response(200, json={"preset_id": "p", "profile": None, "generation": {"prompt": "x"}})
        if req.url.path == "/api/generate/":
            calls["generation"] = json.loads(req.content)
            return httpx.Response(201, json={"job_id": "J1", "status": "queued"})
        raise AssertionError(req.url.path)

    api = make_api(handler)
    job_id = await api.compose_and_submit("p", None, "a dog", 800, 600, 3)
    assert job_id == "J1"
    assert calls["overrides"] == {"width": 800, "height": 600, "batch_size": 3}


async def test_collect_job_result_running():
    def handler(req):
        return httpx.Response(200, json={"status": "running"})

    api = make_api(handler)
    assert await api.collect_job_result("J1") == {"status": "running"}


async def test_collect_job_result_failed():
    def handler(req):
        return httpx.Response(200, json={"status": "failed", "error": "boom", "node_errors": ["n1"]})

    api = make_api(handler)
    out = await api.collect_job_result("J1")
    assert out["status"] == "failed"
    assert out["node_errors"] == ["n1"]


async def test_collect_job_result_completed_downloads_all():
    def handler(req):
        if req.url.path == "/api/generate/job/J1abcd99":
            return httpx.Response(200, json={"status": "completed", "image_id": 1})
        if req.url.path == "/api/gallery/":
            return httpx.Response(200, json={"items": [
                {"id": 1, "image_url": "/gallery/a.png"},
                {"id": 2, "image_url": "/gallery/b.png"},
            ], "total": 2})
        if req.url.path == "/gallery/a.png":
            return httpx.Response(200, content=b"AAA")
        if req.url.path == "/gallery/b.png":
            return httpx.Response(200, content=b"BBB")
        raise AssertionError(req.url.path)

    api = make_api(handler)
    out = await api.collect_job_result("J1abcd99")
    assert out["status"] == "completed"
    assert [name for name, _ in out["images"]] == ["a.png", "b.png"]
    assert [data for _, data in out["images"]] == [b"AAA", b"BBB"]
    assert out["urls"] == ["http://test/gallery/a.png", "http://test/gallery/b.png"]
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd discord-bot && python -m pytest tests/test_api_client.py -k "compose_and_submit or collect_job_result" -v`
Expected: FAIL（`AttributeError: 'ApiClient' object has no attribute 'compose_and_submit'`）

- [ ] **Step 3: 新增高階方法（append 到 `ApiClient` class 內，import 頂端加 `from .validation import build_gallery_download_url`）**

在 `discord-bot/bot/api_client.py` 頂端 import 區加：
```python
from .validation import build_gallery_download_url
```

在 `ApiClient` class 內（`download` 之後）新增：
```python
    async def compose_and_submit(self, preset_id: str, profile: str | None,
                                 prompt: str, width: int, height: int, count: int) -> str:
        overrides = {"width": width, "height": height, "batch_size": count}
        generation = await self.compose(preset_id, content_prompt=prompt, profile=profile, overrides=overrides)
        return await self.submit_generate(generation)

    async def collect_job_result(self, job_id: str) -> dict:
        job = await self.get_job(job_id)
        status = job.get("status")
        if status in ("queued", "running"):
            return {"status": status}
        if status == "failed":
            return {
                "status": "failed",
                "error": job.get("error"),
                "node_errors": job.get("node_errors", []),
            }
        items = await self.list_job_images(job_id)
        images: list[tuple[str, bytes]] = []
        urls: list[str] = []
        for item in items:
            image_url = item.get("image_url")
            if not image_url:
                continue
            data = await self.download(image_url)
            filename = image_url.rsplit("/", 1)[-1]
            images.append((filename, data))
            urls.append(build_gallery_download_url(self._base_url, image_url))
        return {"status": "completed", "images": images, "urls": urls}
```

- [ ] **Step 4: 執行測試確認通過**

Run: `cd discord-bot && python -m pytest tests/test_api_client.py -v`
Expected: PASS（全部 api_client 測試）

- [ ] **Step 5: Commit**

```bash
git add discord-bot/bot/api_client.py discord-bot/tests/test_api_client.py
git commit -m "feat(discord-bot): compose->submit and job-result orchestration"
```

---

### Task 5: Discord UI 元件（selects + modal）

**Files:**
- Create: `discord-bot/bot/views.py`
- Test: `discord-bot/tests/test_views.py`

**Interfaces:**
- Consumes: Task 4 的 `ApiClient`（`compose_and_submit`）、Task 2 的 `parse_dimension`/`parse_count`/`ValidationError`、Task 3 的 `BackendError`
- Produces:
  - `build_preset_options(presets: list[dict]) -> list[discord.SelectOption]`（label 取 `chinese_name` → `name` → `id`，上限 25）
  - `build_profile_options(profiles: list[str]) -> list[discord.SelectOption]`（上限 25）
  - `class DrawModal(discord.ui.Modal)`：`__init__(self, api, preset_id, profile)`，4 個 TextInput：prompt/width/height/count
  - `class ProfileSelect(discord.ui.Select)`、`class PresetSelect(discord.ui.Select)`、`class PresetView(discord.ui.View)`

- [ ] **Step 1: 寫失敗測試**

`discord-bot/tests/test_views.py`:
```python
from bot.views import DrawModal, build_preset_options, build_profile_options


def test_preset_options_prefers_chinese_name():
    opts = build_preset_options([
        {"id": "a", "name": "Alpha", "chinese_name": "阿爾法", "profiles": []},
        {"id": "b", "name": "Beta", "profiles": []},
    ])
    assert [(o.label, o.value) for o in opts] == [("阿爾法", "a"), ("Beta", "b")]


def test_preset_options_capped_at_25():
    presets = [{"id": str(i), "name": f"n{i}", "profiles": []} for i in range(40)]
    assert len(build_preset_options(presets)) == 25


def test_profile_options():
    opts = build_profile_options(["day", "night"])
    assert [o.value for o in opts] == ["day", "night"]


def test_draw_modal_has_four_inputs():
    modal = DrawModal(api=None, preset_id="p", profile=None)
    labels = [child.label for child in modal.children]
    assert len(labels) == 4
    # prompt / 寬 / 高 / 張數 四欄都在
    assert any("寬" in l for l in labels)
    assert any("高" in l for l in labels)
    assert any("張數" in l for l in labels)
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd discord-bot && python -m pytest tests/test_views.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'bot.views'`）

- [ ] **Step 3: 實作 views.py**

`discord-bot/bot/views.py`:
```python
"""Discord UI 元件：兩層 select + 生圖 modal。薄 glue，邏輯委派給 api_client/validation。"""
import discord

from .api_client import BackendError
from .validation import ValidationError, parse_count, parse_dimension


def build_preset_options(presets: list[dict]) -> list[discord.SelectOption]:
    options = []
    for p in presets[:25]:
        label = p.get("chinese_name") or p.get("name") or p["id"]
        desc = (p.get("name") or "")[:100] or None
        options.append(discord.SelectOption(label=str(label)[:100], value=p["id"], description=desc))
    return options


def build_profile_options(profiles: list[str]) -> list[discord.SelectOption]:
    return [discord.SelectOption(label=str(name)[:100], value=str(name)) for name in profiles[:25]]


class DrawModal(discord.ui.Modal, title="生圖設定"):
    def __init__(self, api, preset_id: str, profile: str | None):
        super().__init__()
        self._api = api
        self._preset_id = preset_id
        self._profile = profile
        self.prompt = discord.ui.TextInput(
            label="Prompt", style=discord.TextStyle.paragraph, required=True, max_length=2000
        )
        self.width = discord.ui.TextInput(label="寬 (256-2048)", default="1024", required=True, max_length=4)
        self.height = discord.ui.TextInput(label="高 (256-2048)", default="1024", required=True, max_length=4)
        self.count = discord.ui.TextInput(label="張數 (1-8)", default="4", required=False, max_length=1)
        for item in (self.prompt, self.width, self.height, self.count):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            width = parse_dimension(self.width.value, field="寬")
            height = parse_dimension(self.height.value, field="高")
            count = parse_count(self.count.value)
        except ValidationError as exc:
            await interaction.response.send_message(f"⚠️ {exc}，請重跑 /draw", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            job_id = await self._api.compose_and_submit(
                self._preset_id, self._profile, self.prompt.value, width, height, count
            )
        except BackendError as exc:
            await interaction.followup.send(f"❌ {exc}", ephemeral=True)
            return
        await interaction.followup.send(
            f"✅ 已排入生圖（{count} 張）\njob id：`{job_id}`\n用 `/result id:{job_id}` 查詢結果",
            ephemeral=True,
        )


class ProfileSelect(discord.ui.Select):
    def __init__(self, api, preset_id: str, profiles: list[str]):
        super().__init__(placeholder="選擇風格變體（profile）", options=build_profile_options(profiles))
        self._api = api
        self._preset_id = preset_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(DrawModal(self._api, self._preset_id, self.values[0]))


class PresetSelect(discord.ui.Select):
    def __init__(self, api, presets: list[dict]):
        super().__init__(placeholder="選擇畫風 preset", options=build_preset_options(presets))
        self._api = api
        self._presets = {p["id"]: p for p in presets}

    async def callback(self, interaction: discord.Interaction):
        preset = self._presets[self.values[0]]
        profiles = preset.get("profiles") or []
        if profiles:
            view = discord.ui.View(timeout=300)
            view.add_item(ProfileSelect(self._api, preset["id"], profiles))
            await interaction.response.edit_message(content="選擇風格變體：", view=view)
        else:
            await interaction.response.send_modal(DrawModal(self._api, preset["id"], None))


class PresetView(discord.ui.View):
    def __init__(self, api, presets: list[dict]):
        super().__init__(timeout=300)
        self.add_item(PresetSelect(api, presets))
```

- [ ] **Step 4: 執行測試確認通過**

Run: `cd discord-bot && python -m pytest tests/test_views.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: Commit**

```bash
git add discord-bot/bot/views.py discord-bot/tests/test_views.py
git commit -m "feat(discord-bot): preset/profile selects and draw modal"
```

---

### Task 6: Bot 組裝與 slash 指令

**Files:**
- Create: `discord-bot/bot/main.py`
- Test: `discord-bot/tests/test_main.py`

**Interfaces:**
- Consumes: Task 1 `Config`、Task 4 `ApiClient`、Task 3 `BackendError`、Task 5 `PresetView`、Task 2 `build_gallery_download_url`
- Produces:
  - `build_bot(config: Config) -> tuple[discord.Client, discord.app_commands.CommandTree, ApiClient]`（註冊 `/draw`、`/result` 到 `config.guild_id`）
  - `main() -> None`（載入設定、建 bot、`client.run(token)`）
  - 常數 `DISCORD_UPLOAD_LIMIT_BYTES = 24 * 1024 * 1024`

- [ ] **Step 1: 寫失敗測試**

`discord-bot/tests/test_main.py`:
```python
import discord

from bot.config import Config
from bot.main import build_bot


def test_build_bot_registers_commands():
    config = Config(discord_token="t", guild_id=123, backend_base_url="http://test")
    client, tree, api = build_bot(config)
    guild = discord.Object(id=123)
    names = {c.name for c in tree.get_commands(guild=guild)}
    assert names == {"draw", "result"}
    assert api._base_url == "http://test"
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd discord-bot && python -m pytest tests/test_main.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'bot.main'`）

- [ ] **Step 3: 實作 main.py**

`discord-bot/bot/main.py`:
```python
"""Bot 進入點：註冊 /draw、/result 到指定 guild。"""
import io

import discord
from discord import app_commands

from .api_client import ApiClient, BackendError
from .config import Config, load_config
from .views import PresetView

DISCORD_UPLOAD_LIMIT_BYTES = 24 * 1024 * 1024


def build_bot(config: Config):
    intents = discord.Intents.none()
    client = discord.Client(intents=intents)
    tree = app_commands.CommandTree(client)
    api = ApiClient(config.backend_base_url)
    guild = discord.Object(id=config.guild_id)

    @tree.command(name="draw", description="從畫風 preset 直接生圖", guild=guild)
    async def draw(interaction: discord.Interaction):
        try:
            presets = await api.list_presets()
        except BackendError as exc:
            await interaction.response.send_message(f"❌ 後端錯誤：{exc}", ephemeral=True)
            return
        except Exception:
            await interaction.response.send_message("❌ 後端連不上，請確認 backend 有啟動", ephemeral=True)
            return
        if not presets:
            await interaction.response.send_message("目前沒有可用的 preset", ephemeral=True)
            return
        await interaction.response.send_message(
            "選擇畫風：", view=PresetView(api, presets), ephemeral=True
        )

    @tree.command(name="result", description="用 job id 反查生圖結果", guild=guild)
    @app_commands.describe(id="生圖時取得的 job id")
    async def result(interaction: discord.Interaction, id: str):
        await interaction.response.defer(thinking=True)
        try:
            outcome = await api.collect_job_result(id)
        except BackendError as exc:
            if exc.status_code == 404:
                await interaction.followup.send("找不到這個 job id")
            else:
                await interaction.followup.send(f"❌ 後端錯誤：{exc}")
            return
        except Exception:
            await interaction.followup.send("❌ 後端連不上，請確認 backend 有啟動")
            return

        status = outcome["status"]
        if status in ("queued", "running"):
            await interaction.followup.send(f"⏳ 狀態：{status}，尚未完成")
            return
        if status == "failed":
            errs = "；".join(str(x) for x in (outcome.get("node_errors") or []))
            detail = errs or outcome.get("error") or "未知錯誤"
            await interaction.followup.send(f"❌ 生圖失敗：{detail}")
            return

        images = outcome.get("images") or []
        if not images:
            await interaction.followup.send("完成，但找不到圖檔")
            return

        total = sum(len(data) for _, data in images)
        if total > DISCORD_UPLOAD_LIMIT_BYTES:
            links = "\n".join(outcome.get("urls") or [])
            await interaction.followup.send(f"✅ 完成，共 {len(images)} 張（檔案過大，改附連結）：\n{links}")
            return

        files = [discord.File(io.BytesIO(data), filename=name) for name, data in images]
        await interaction.followup.send(f"✅ 完成，共 {len(files)} 張", files=files)

    @client.event
    async def on_ready():
        await tree.sync(guild=guild)
        print(f"Logged in as {client.user} — commands synced to guild {config.guild_id}")

    return client, tree, api


def main() -> None:
    config = load_config()
    client, _tree, _api = build_bot(config)
    client.run(config.discord_token)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 執行測試確認通過**

Run: `cd discord-bot && python -m pytest tests/test_main.py -v`
Expected: PASS

- [ ] **Step 5: 全套測試 + import smoke**

Run: `cd discord-bot && python -m pytest -v && python -c "import bot.main"`
Expected: 全 PASS，import 無錯

- [ ] **Step 6: Commit**

```bash
git add discord-bot/bot/main.py discord-bot/tests/test_main.py
git commit -m "feat(discord-bot): bot entrypoint with /draw and /result"
```

---

### Task 7: README + 進度更新

**Files:**
- Create: `discord-bot/README.md`
- Modify: `docs/PROGRESS.md`（頂端加一段）

**Interfaces:** 無（文件）

- [ ] **Step 1: 寫 README**

`discord-bot/README.md`:
````markdown
# ai-drawing Discord Bot

用 Discord slash 指令直接呼叫本機 backend 生圖，不經過 LLM。

## 設定

1. `cp .env.example .env`，填入：
   - `DISCORD_TOKEN`：Discord Developer Portal → 你的 App → Bot → Token
   - `GUILD_ID`：你的伺服器 ID（開啟 Discord 開發者模式後右鍵伺服器 → 複製 ID）
   - `BACKEND_BASE_URL`：預設 `http://localhost:8000`
2. Bot 需勾選 `applications.commands` scope 邀進伺服器。
3. 安裝依賴並啟動：

```bash
cd discord-bot
python -m venv .venv && . .venv/Scripts/activate   # Windows；macOS/Linux 用 . .venv/bin/activate
pip install -r requirements.txt
python -m bot.main
```

## 指令

- `/draw` — 選 preset（有 profile 再選 profile）→ 填 prompt/寬/高/張數 → 回 job id
- `/result id:<job_id>` — 反查；完成就把圖貼回來

## 測試

```bash
cd discord-bot && python -m pytest -v
```

## 手動 smoke（需先啟動 backend + ComfyUI）

1. 啟 backend：`cd ../backend && uvicorn app.main:app --reload`
2. 啟 bot：`python -m bot.main`，確認 console 印出 commands synced
3. Discord 打 `/draw` → 下拉出現 12 個 preset → 選一個 → （有 profile 則選）→ 填 prompt/寬高/張數 → 送出取得 job id
4. 等數十秒後 `/result id:<job_id>` → 應貼回張數對應的圖

## 已知限制

- preset 超過 25 個需改分頁（目前 12 個）。
- `/result` 以 `job_id` 前 8 碼過濾 gallery，理論上相撞會誤撈（個人自用機率極低）。
- 6–8 張且單張偏大、合計超過 ~24MB 時，改回貼 gallery 連結而非附件。
````

- [ ] **Step 2: 更新 PROGRESS.md（在第一段 `## ` 之前插入新段落）**

在 `docs/PROGRESS.md` 最上方（第一個 `## ` 標題之前）插入：
```markdown
## 2026-07-24 Discord Bot 直呼本機生圖

新增 `discord-bot/`（discord.py），使用者用 `/draw` 從既有 style preset（含 profile 變體）選畫風、
填 prompt/寬/高/張數（1–8）後直接呼叫 backend 生圖，全程不經 LLM；`/result id:<job_id>` 反查並貼回圖。
Bot 只做互動↔HTTP 轉譯，生圖決策（prompt 合併、KSampler 參數、workflow）仍由 backend 端點負責，
**未改動 backend**。batch 經 compose `overrides.batch_size` 帶入；`/result` 以
`GET /api/gallery/?image_name=<job_id[:8]>` 撈回同 job 全部圖。指令只註冊到指定 GUILD_ID。
設計與計畫見 `docs/superpowers/{specs,plans}/2026-07-24-discord-bot*.md`。驗證：`discord-bot` pytest 全綠。

```

- [ ] **Step 3: Commit**

```bash
git add discord-bot/README.md docs/PROGRESS.md
git commit -m "docs(discord-bot): README and progress note"
```

---

## Self-Review

**Spec coverage：**
- 目標（preset→profile→prompt/寬高/張數→生圖，不經 LLM）→ Task 5 + 6 ✅
- 模組切分（config/api_client/validation/views/main）→ Task 1–6 ✅
- api_client 端點表 → Task 3/4 ✅
- `/draw` 兩層下拉+Modal → Task 5（PresetSelect→ProfileSelect→DrawModal）✅
- `/result` 用 image_name 前 8 碼撈全部 → Task 3 `list_job_images` + Task 4 `collect_job_result` ✅
- batch 由使用者輸入經 overrides → Task 4 `compose_and_submit` ✅
- 錯誤處理表（連不上/404/503/驗證/查無/檔案過大）→ Task 6 command + Task 2 驗證 ✅
- 安全（.env、.gitignore、guild 限定）→ Task 1 + Task 6 ✅
- 測試（validation/api_client + 手動 smoke）→ Task 2/3/4/5/6 + Task 7 README ✅
- 已知限制記錄 → Task 7 README ✅

**Placeholder scan：** 無 TBD/TODO；每個 code step 均為完整可貼上的程式碼。

**Type consistency：** `compose_and_submit(preset_id, profile, prompt, width, height, count)`、
`collect_job_result` 回傳形狀、`build_gallery_download_url(base_url, image_url)`、
`build_preset_options`/`build_profile_options`、`build_bot(config)` 在定義與使用處一致。

---

## Execution Handoff

計畫已存到 `docs/superpowers/plans/2026-07-24-discord-bot.md`。
