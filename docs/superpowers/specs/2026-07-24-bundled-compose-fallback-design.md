# 自帶 Docker Compose Fallback — 設計文件

- 日期：2026-07-24
- 狀態：設計已核可，待寫實作計畫
- 目標檔案：`scripts/launcher/`（`docker.py`、`constants.py`、`cli.py`）＋對應測試

## 問題

一鍵安裝（`setup.sh` / `setup.ps1` → `scripts/bootstrap.py` → launcher）目前對使用者系統上的 Docker Compose 版本設有硬性最低門檻 `COMPOSE_MINIMUM = (2, 24, 0)`。系統 compose 太舊、只有 v1、或缺少 compose plugin 的使用者，會在 `preflight()` 直接被擋下（`COMPOSE_VERSION_UNSUPPORTED` / `COMPOSE_UNAVAILABLE`），無法完成安裝。

本專案的既有設計哲學是「該鎖的版本都自己下載鎖定」：uv `0.11.29`、Python `3.12`、ComfyUI `v0.28.0`、busybox `1.36.1`。唯一還在依賴「使用者系統那一版」的就是 Docker Compose。

## 目標與非目標

**目標**：只要使用者已安裝並啟動 Docker daemon，安裝就能成功——不論其 compose 版本多舊、是否只有 v1、是否缺 plugin。

**非目標**：
- 不自動安裝 / 引導安裝 Docker 本體（假設 Docker daemon 已可用，由 `docker version` 確認）。
- 不改成「不依賴 Docker」的原生跑法。
- 不改動使用者系統上任何全域 Docker 設定。

## 核心決策：能用系統的就用系統的，不能用才自帶；自帶一律私有

- 系統 compose **≥ `COMPOSE_MINIMUM`** → 直接用系統的 `docker compose`，**不下載**。現代 Docker Desktop 使用者完全不會多一份 compose。
- 系統 compose 缺少 / 太舊 / 只有 v1 → fallback 到**釘死版本的 standalone compose 執行檔**，下載到 app 私有 cache，用**絕對路徑**內部呼叫。
- 自帶的 binary **絕不**寫入 `~/.docker/cli-plugins/`、**絕不**放上 PATH、**絕不**建立全域 `docker-compose` 別名。使用者自己終端機的 `docker compose` 完全不受影響（回應「系統多版本困擾」的顧慮）。

standalone compose（v2 單一執行檔）透過 Docker daemon socket / `DOCKER_HOST` 直接運作，不需要 docker CLI plugin；daemon 可用性已由 `preflight()` 的 `docker version` 確認。

## 版本與校驗（`constants.py`）

- 保留 `COMPOSE_MINIMUM = (2, 24, 0)`：判定系統 compose 是否夠新的門檻，同時是所有 compose 呼叫所需功能（`ps --format json`、`config --quiet`、`--env-file` 疊加、多個 `-f`、`up --build --remove-orphans`）的實際下限。
- 新增 `COMPOSE_BUNDLED_VERSION = "2.32.4"`（近兩年穩定版，≥ 門檻）。
- 新增各平台的 **SHA256 checksum 常數表**。

  > **實作時務必實際取得，不可捏造。** 來源為官方 release 資產旁的 `.sha256` 檔：
  > `https://github.com/docker/compose/releases/download/v2.32.4/docker-compose-<os>-<arch>[.exe].sha256`
  > 實作階段下載每個平台資產的 `.sha256` 內容填入常數表，並在 code review 時人工核對至少一個平台。

## 元件

### `ComposeRuntime`（新 dataclass，`docker.py`）
```
@dataclass(frozen=True)
class ComposeRuntime:
    invocation: tuple[str, ...]   # ("docker","compose") 或 (abs_path,)
    version: tuple[int, int, int]
    source: str                   # "system" | "bundled"
```

### `resolve_compose_runtime(host, runner, *, allow_download, downloader) -> ComposeRuntime`
決策流程：
1. 跑 `docker compose version --short`。解析成功且 **≥ `COMPOSE_MINIMUM`** → 回傳 `source="system"`, `invocation=("docker","compose")`。**不下載。**
2. 否則找 cache 的自帶 binary（`compose_cache_path(host)`）：
   - 已存在 → 跑 `<path> version --short` 確認可用 → 回傳 `source="bundled"`, `invocation=(path,)`。可用但無法執行 → `COMPOSE_BUNDLED_UNUSABLE`。
   - 不存在且 `allow_download=True` → 下載 → 校驗 SHA256 → POSIX `chmod +x` → 確認 `version --short` → 回傳 `source="bundled"`。
   - 不存在且 `allow_download=False` → 唯讀指令不下載，視為 compose 不可用（交由呼叫端降級）。

`downloader` 為可注入的 callable（測試用 fake），預設實作用 `urllib`（與現有 `wait_http_ready` 一致）。

### 私有 cache 路徑：`compose_cache_path(host) -> Path`
- `<CACHE_ROOT>/ai-drawing/compose/<COMPOSE_BUNDLED_VERSION>/docker-compose[.exe]`
- `CACHE_ROOT`：Windows → `%LOCALAPPDATA%`（缺則 `%USERPROFILE%`）；其餘 → `$XDG_CACHE_HOME`（缺則 `~/.cache`）。與 `setup.ps1` / `setup.sh` 對 uv 的做法一致。

### 平台/架構對應：`_compose_asset_name(host) -> str`
- `{linux,darwin,windows} × {x86_64,aarch64}` → GitHub 資產名（`docker-compose-linux-aarch64`、`docker-compose-windows-x86_64.exe` 等）。
- 無對應組合 → `COMPOSE_BUNDLED_UNSUPPORTED_ARCH`（比照現有 `UnsupportedNativeArchitecture`）。

### 下載＋校驗：`_download_compose(host, dest, downloader)`
- 下載到 `dest.with_suffix(".partial")` 之類的暫存檔 → 計算 SHA256 → 與常數表比對 → 不符則刪除並丟 `COMPOSE_CHECKSUM_MISMATCH` → 相符則原子 rename 到最終路徑 → POSIX `chmod 0o755`。
- 網路/IO 失敗 → `COMPOSE_DOWNLOAD_FAILED`。

## 接線（把 invocation 串進所有 compose 呼叫）

唯一入口是 `compose_command()`，其餘 compose 動作都經過它：

- `compose_command(project_root, *args, env_file=None, override_file=None, invocation=("docker","compose"))` — 新增 `invocation` 參數，**預設值保持現有 contract**（`test_compose_contract.py` 不需改）。回傳 `[*invocation, "--env-file", ..., "-f", ..., "-f", ..., *args]`。
- 下列函式新增 `invocation` 參數（皆有預設值，向後相容）：`_compose_required`、`validate_compose`、`compose_up`、`compose_down`、`compose_service_states`、`compose_up_services`。
- `preflight(runner, host, *, allow_download)` 改為呼叫 `resolve_compose_runtime` 並回傳含 `invocation` 的結果（擴充 `DockerPreflight` 或直接回傳 `ComposeRuntime` + docker 版本）。
- `cli.py` `DefaultServices`：
  - `preflight()` 把結果存為 `self._compose`（setup/start/reconfigure：`allow_download=True`；status/dry-run：`allow_download=False`，沿用現有「失敗則 `docker_available=False`」降級）。
  - 所有 `docker.compose_*` 呼叫與 `compose_logs()` 內那條裸 `compose_command`，都帶上 `self._compose.invocation`。
  - 若某唯讀指令未先跑 preflight 就用到 compose，退回預設 `("docker","compose")`。

## 錯誤碼（皆附中文 hint）

| Code | 情境 |
| --- | --- |
| `COMPOSE_DOWNLOAD_FAILED` | 需 fallback 但下載失敗（離線/網路） |
| `COMPOSE_CHECKSUM_MISMATCH` | 下載檔 SHA256 不符（已刪除半殘檔） |
| `COMPOSE_BUNDLED_UNSUPPORTED_ARCH` | 平台/架構無對應資產 |
| `COMPOSE_BUNDLED_UNUSABLE` | 自帶 binary 存在但 `version --short` 失敗 |

既有 `COMPOSE_UNAVAILABLE` / `COMPOSE_VERSION_UNSUPPORTED` 保留於「僅系統偵測」語意；happy path 的 setup 不再對使用者拋出 `COMPOSE_VERSION_UNSUPPORTED`——會透明 fallback。

## 測試

`resolve_compose_runtime`（fake runner + fake downloader）：
- 系統 ≥ 門檻 → 用系統、`downloader` 未被呼叫。
- 系統太舊 + cache 無 → 下載、校驗、回傳 bundled。
- cache 已存在 → 不下載。
- checksum 不符 → `COMPOSE_CHECKSUM_MISMATCH`，暫存檔被刪。
- 下載失敗 → `COMPOSE_DOWNLOAD_FAILED`。
- arch 不支援 → `COMPOSE_BUNDLED_UNSUPPORTED_ARCH`。
- `allow_download=False` 且系統不合格、cache 無 → 不下載、回報不可用。

其他：
- `test_compose_contract.py`：因 `compose_command` 預設 invocation 不變 → 應維持綠燈；另補一個帶 bundled `invocation`（絕對路徑）的 case。
- `test_docker_launcher.py`：`preflight` 回傳型別更新；補系統 vs bundled 兩路徑。
- `cli` 層：確認 setup 走 `allow_download=True`、status/dry-run 走 `allow_download=False`。

## 相容性與風險

- 現代使用者（近一年 Docker Desktop）：零行為改變、零額外下載。
- 舊版/缺 plugin 使用者：多一次一次性下載（約 60MB）到私有 cache；不干擾系統。
- 安全：只從官方 GitHub release 下載並比對釘死 SHA256 後才執行，降低下載執行檔的風險。
- 清除方式：刪 `<CACHE_ROOT>/ai-drawing/compose/` 即可，不影響系統。
