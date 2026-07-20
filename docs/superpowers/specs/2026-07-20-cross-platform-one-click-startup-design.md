# Cross-Platform One-Click Startup Design

## Goal

讓使用者在 Windows、macOS 或 Linux 上 clone repository 後，只需執行一個專案提供的啟動命令，即可設定並啟動 AI Drawing 網站與 Backend。啟動器會詢問是否使用 ComfyUI；使用者可連接既有安裝、要求自動安裝，或拒絕安裝。沒有 ComfyUI 或模型時，應用仍可啟動並清楚顯示降級狀態。

## Success Criteria

1. Windows 使用者執行 `./setup.ps1`，macOS／Linux 使用者執行 `./setup.sh`，不需事先安裝 Python、Node 或專案套件。
2. 使用者只需具備 Git、Docker、Docker Compose、網路，以及其硬體所需的主機驅動程式。
3. 啟動器可搜尋既有 ComfyUI，或將官方 ComfyUI 安裝到使用者選擇的目錄。
4. 自動安裝支援 NVIDIA CUDA、Apple Silicon MPS 與 CPU；不自動下載基礎模型或 custom nodes。
5. 使用者拒絕或無法安裝 ComfyUI 時，Frontend 與 Backend 仍能正常啟動。
6. 容器重建後，資料庫、圖片、Prompt Library、LoRA 訓練資料與 logs 仍然存在。
7. 完成後只向一般使用者顯示網站入口、API 狀態與 ComfyUI 狀態；容器內部細節保留給 `status` 與 `logs` 診斷命令。

## Scope

### Included

- Windows PowerShell 與 macOS／Linux Bash 入口。
- 共用的跨平台 bootstrap 程式。
- Docker Compose 的 Frontend、Backend、health checks、network 與持久化資料。
- 既有 ComfyUI 的自動搜尋與路徑設定。
- ComfyUI 原生自動安裝、硬體偵測、啟動、停止與狀態檢查。
- Backend 容器連接主機 ComfyUI，以及 ComfyUI model directories 的選用 bind mounts。
- 無 ComfyUI、無模型與 CPU fallback 的降級狀態。
- 首次初始化、日常啟動、停止、重新設定、狀態與 logs 操作。
- 啟動文件與跨平台驗證。

### Excluded

- MCP Server 的容器化或 MCP client 設定。
- 自動下載 checkpoint、LoRA、VAE、text encoder 或其他模型。
- 自動安裝 ComfyUI custom nodes。
- Civitai API key 的自動建立。
- 自動安裝 Git、Docker Desktop、Linux Docker Engine 或 GPU driver。
- 未經使用者要求的 ComfyUI 自動升級。

## Chosen Architecture

採用「原生互動啟動器 + Docker 應用服務 + 原生 ComfyUI」架構。

Frontend 與 Backend 由 Docker Compose 管理。ComfyUI 在主機原生執行，以便 Windows／Linux 使用 NVIDIA CUDA、Apple Silicon 使用 Metal/MPS，並保留 CPU fallback。這也允許使用者沿用既有 ComfyUI，而不必維護一份容器專用模型庫。

未選擇全容器化 ComfyUI，因為 macOS Docker 容器無法提供等價的 Metal/MPS 加速。未選擇 Windows／Linux 容器化而 macOS 原生的分裂方案，因為平台行為、GPU runtime 要求與故障排查會顯著分歧。

## Configuration Ownership

設定只保留一個 runtime 來源，避免 `.env` 與一般 application YAML 重複定義相同欄位。

| 檔案 | 是否提交 | 用途 |
|------|----------|------|
| `.env.example` | 是 | 安全預設、欄位說明與空白 secret placeholder |
| `.env` | 否 | 啟動器產生的本機 URL、ports、模式、路徑及使用者提供的 secrets |
| `docker-compose.yml` | 是 | 所有人共用的 Frontend、Backend、network、health checks 與 volumes |
| `.ai-drawing/compose.local.yaml` | 否 | 接受 ComfyUI 時才加入的主機 model directory bind mounts |
| `data/bootstrap/state.json` | 否 | 啟動器版本、由本專案啟動的 ComfyUI PID、commit 與可回復安裝資訊 |

一般 YAML 適合巢狀 application configuration，但 Docker 和現有 Pydantic settings 已以環境變數為介面，因此本變更不新增第二份 `config.yaml`。Compose override 使用 YAML 是因為它描述容器拓撲與 bind mounts，不是另一份 Backend 設定來源。

`.env`、`.ai-drawing/` 與 `data/` 必須被 `.gitignore` 排除。任何 API key 均只能保存在 `.env` 或外部 secret store；不得寫入 Compose YAML、logs、版本庫或命令列輸出。

## User Entry Points

Repository root 提供：

```text
setup.ps1   # Windows
setup.sh    # macOS / Linux
```

兩個 wrapper 暴露相同行為：

| 命令 | 行為 |
|------|------|
| 無參數／`setup` | 未初始化時進入精靈；已初始化時使用既有設定啟動 |
| `start` | 驗證既有設定並啟動 ComfyUI 與 Compose services |
| `stop` | 停止 Compose services，以及本專案啟動的 ComfyUI instance |
| `status` | 顯示 Docker、Frontend、Backend、ComfyUI 與模型可用狀態 |
| `reconfigure` | 重新選擇 ComfyUI 模式、路徑與 ports，成功後原子替換設定 |
| `logs` | 顯示或追蹤 Bootstrap、ComfyUI 與 Compose logs |
| `update-comfyui` | 明確要求時才更新自動安裝的 ComfyUI，失敗時回復原 commit |

Wrapper 不複製業務邏輯。它們只負責平台最低限度檢查、取得固定版本的 `uv` runtime，然後呼叫共用的 `scripts/bootstrap.py`。下載的 runtime 放在使用者 cache，不寫入 repository。下載失敗時顯示可重試的命令與 log 位置。

## First-Run Flow

1. 確認 Docker CLI、Docker daemon 與 `docker compose` 可用。
2. 確認 Docker Compose 版本符合專案最低版本。
3. 檢查預設 ports；若被占用，讓使用者選擇自動替代或中止，不靜默殺死其他程序。
4. 詢問是否使用 ComfyUI。
5. 若拒絕，將模式設為 `disabled`，跳到應用服務初始化。
6. 若接受，依序搜尋上次位置、標準安裝位置與有限的常見目錄；不得遞迴掃描整顆磁碟。
7. 找到候選時顯示路徑並請使用者確認；使用者也可輸入其他既有路徑。
8. 找不到或拒絕候選時，提供「自動安裝」與「返回不使用 ComfyUI」。
9. 自動安裝時使用平台的 user-data directory 作為預設值，也允許使用者改路徑。
10. 驗證 ComfyUI root、`main.py` 與 models directory shape。
11. 偵測硬體、安裝對應 runtime，啟動 ComfyUI 並輪詢 API readiness。
12. 產生暫存 `.env` 與 Compose override，執行 `docker compose config` 驗證後才原子替換正式設定。
13. 建立持久化目錄並執行 `docker compose up -d --build`。
14. 等待 Backend health check 與 Frontend HTTP readiness。
15. 顯示網站 URL、Backend 狀態、ComfyUI 狀態、是否找到模型，以及 `status`／`logs` 指令。

任何詢問都提供安全預設，按 Enter 即可繼續。非互動 CI 僅能使用已存在的 `.env` 或明確 flags，不得對 stdin 永久等待。

## ComfyUI Discovery and Installation

### Discovery

候選必須同時滿足：

- 目錄存在且可解析為絕對路徑。
- 存在 `main.py`。
- 存在或可建立 `models/`。
- 路徑不位於 repository 的 tracked subtree。

若偵測到既有執行中的 ComfyUI，先以 API 確認版本與狀態；連接它而不建立第二個 process，也不在 `stop` 時終止它。

### Automatic Installation

自動安裝採固定、已驗證的官方 ComfyUI commit。步驟為：

1. Clone 官方 repository 到選定目錄，或驗證空目錄後再建立。
2. 以 `uv` 安裝專案指定的 Python 版本並建立 ComfyUI 專用 `.venv`。
3. 偵測 runtime：Windows／Linux NVIDIA、Apple Silicon MPS、CPU。
4. 依官方 PyTorch 發佈方式安裝對應套件，再安裝該 ComfyUI commit 的 requirements。
5. 執行最小 import／device smoke check。
6. 保存安裝 commit、Python 版本、device mode 與啟動命令，供 status、update 與 rollback 使用。

NVIDIA 模式只驗證可用 driver，不替使用者安裝或修改 driver。若 GPU runtime 驗證失敗，啟動器必須說明原因並詢問是否退回 CPU，不得無提示地改用 CPU。Apple Silicon 使用原生 arm64 Python 與 PyTorch MPS；不得透過 Rosetta 建立 x86 environment。

自動安裝不下載任何模型或 custom nodes。因此安裝完成但無模型是正常且可成功的狀態。

### Process Ownership

ComfyUI logs 寫入 `data/logs/comfyui.log`。Bootstrap state 只記錄本專案實際啟動的 PID、啟動時間與 executable identity。停止前要再次核對 identity，避免 PID 重用時終止無關程序。

若 ComfyUI 已由使用者啟動，bootstrap 僅記錄 external ownership，`stop` 不終止它。若由本專案啟動，Windows 使用隱藏背景 process，macOS／Linux 使用與終端分離的 process group；三平台皆以 readiness polling 取代固定 sleep。

## Host-to-Container Connectivity

Backend 容器使用 `host.docker.internal` 連接主機 ComfyUI。Compose 對 Linux 加入：

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

ComfyUI 預設只監聽 loopback，不直接暴露到 LAN。Docker Desktop 平台使用其 host gateway；Linux 若容器無法連接 loopback service，bootstrap 啟動一個只綁 Docker bridge host address 的本機 relay，將容器流量轉送到 `127.0.0.1:8188`。Relay 遵循與 ComfyUI 相同的 ownership、PID identity 與 log 規則。

不得以 `--listen 0.0.0.0` 作為自動 fallback，因為 ComfyUI 預設沒有適合公開網路的驗證層。

## Docker Compose Services

### Backend

- 容器內監聽 `0.0.0.0:8000`。
- 主機預設映射為 `127.0.0.1:8001:8000`，與目前 Frontend 開發 proxy 及 MCP defaults 保持一致。
- `/health` 作為容器 health check。
- 依賴的 workflow、starter Prompt Library 與 style presets 必須包含在 image 或明確掛載，不能依賴 build context 外不存在的檔案。
- 第一次啟動自動初始化資料庫及需要的 persisted seed data；重複啟動必須 idempotent。
- ComfyUI 不可用時仍通過 application health，並由獨立的 dependency status 表達 degraded 狀態。

### Frontend

- Multi-stage build 產生 production assets，由 Nginx 提供。
- 主機預設映射為 `127.0.0.1:5173:80`。
- Nginx 透過 Compose network 將 `/api` 與 gallery／artifact requests 代理至 `backend:8000`。
- `depends_on` 等 Backend healthy 後才啟動，但前端仍需顯示 runtime dependency 狀態，不能假設 ComfyUI 一定存在。

### Network and Service Boundaries

- Frontend 與 Backend 使用專用 Compose network。
- Database 不對外開 port；初版沿用 SQLite，不新增 PostgreSQL service。
- MCP 不建立 service 或 profile。
- ComfyUI 不由 Compose 管理，也不新增公共 port mapping。

## Persistence Layout

所有 runtime data 放在 repository 下被忽略的 `data/`，便於備份、清理與理解：

```text
data/
├── database/
│   └── auto_draw.db
├── outputs/
├── gallery/
├── lora_train/
├── prompt_library/
├── bootstrap/
└── logs/
```

Compose 使用 bind mounts，讓資料在 `docker compose down`、image rebuild 與版本升級後保留。`docker compose down -v` 不得刪除這些 bind-mounted files。

Starter Prompt Library 首次啟動時由 image seed 到空的 persisted directory；若目錄已有資料則不得覆寫。Workflow 與不可變 starter assets 隨 image 發佈。任何 migration 都必須可重入，並在修改前建立可回復備份。

## Optional ComfyUI Directory Mounts

啟動器固定以 `docker-compose.yml` 加 `.ai-drawing/compose.local.yaml` 啟動。Disabled mode 產生不含 model mounts 的有效空 override；只有在使用者接受 ComfyUI 且路徑驗證成功時，override 才加入 mounts。使用 long bind syntax 將主機目錄映射成 Backend 使用的穩定容器路徑：

```text
/comfyui/models/checkpoints
/comfyui/models/loras
/comfyui/models/diffusion_models
/comfyui/models/text_encoders
/comfyui/models/vae
/comfyui/models/embeddings
/comfyui/models/controlnet
/comfyui/models/upscale_models
/comfyui/input
```

對應 Backend environment 只使用這些容器路徑，不直接傳入 Windows drive path。需要由 Backend 執行 Civitai resource acquisition 的模型目錄使用 read-write mount；只供辨識而不應修改的路徑使用 read-only mount。

Windows／macOS 若目錄未獲 Docker Desktop file-sharing 權限，bootstrap 在正式啟動前以短生命週期 mount probe 偵測，顯示應授權的精確目錄後中止 ComfyUI mount 設定；Frontend 與 Backend 可選擇以 disabled mode 繼續。

## Degraded Operation and Status Contract

下列狀態不阻止應用啟動：

- 使用者拒絕 ComfyUI。
- ComfyUI 尚未安裝或目前未執行。
- 沒有任何 checkpoint 或 split model。
- NVIDIA／MPS 不可用而使用者明確同意 CPU fallback。
- 尚未提供 Civitai API key。
- 某個選用 model directory 不存在。

Frontend 透過 Backend dependency status API 呈現：

- `connected`：ComfyUI API 可用。
- `not_configured`：使用者選擇 disabled。
- `unreachable`：已設定但目前無法連線。
- `no_models`：ComfyUI 可用但沒有可生圖模型。
- `degraded`：部分目錄或選用能力不可用。

狀態訊息必須包含可執行的下一步，例如執行 `setup.ps1 reconfigure`／`./setup.sh reconfigure`、啟動既有 ComfyUI，或將模型放到已顯示的目錄。無模型不得呈現為安裝失敗。

## Error Handling and Recovery

### Blocking Errors

下列問題停止啟動，保留上一份可用設定與服務：

- Docker 缺失、daemon 未啟動或 Compose 版本不符。
- 所需 port 被占用且使用者拒絕替代 port。
- 無法建立或寫入 persisted data directory。
- `.env`／Compose override 驗證失敗。
- Backend image build 或 health check 失敗。

### Recoverable Errors

ComfyUI 安裝失敗、啟動 timeout、GPU runtime 不可用、model mount 失敗及 API key 缺失均提供 disabled／CPU／retry 等明確選項，不刪除使用者既有 ComfyUI、模型或上一份設定。

所有產生設定採「寫入暫存檔 → 語法與 Compose 驗證 → 原子替換」。自動安裝先建立 staging directory，成功後才成為正式安裝；若目標為既有非空目錄則拒絕覆寫。更新 ComfyUI 前保存 commit 與 environment metadata，更新 smoke check 失敗時退回原 commit 與 lock state。

Logs 不得輸出 `.env` 全文、Authorization header、API key 或 secret-bearing command。使用者可從 `data/logs/bootstrap.log` 與 `data/logs/comfyui.log` 取得診斷資訊。

## Testing Strategy

### Bootstrap Unit Tests

使用 temporary directories、fake command runner 與 scripted answers 覆蓋：

- Windows、macOS、Linux detection。
- NVIDIA、Apple Silicon MPS 與 CPU detection。
- 路徑含空格、非 ASCII 與 Windows drive letters。
- 拒絕 ComfyUI。
- 找到既有、外部執行中與自動安裝的 ComfyUI。
- 非空安裝目錄拒絕覆寫。
- CUDA／MPS 驗證失敗與經同意的 CPU fallback。
- `.env`、override 與 state 原子替換及 rollback。
- PID identity validation。
- 非互動模式缺少必要設定時快速失敗。
- Secret redaction。

測試不得真的下載 ComfyUI、PyTorch 或啟動 Docker。

### Compose Validation

- 執行 `docker compose config` 驗證 base configuration。
- 分別驗證 disabled 與 connected override。
- 驗證 Linux host-gateway。
- 驗證所有 persisted paths 與 model mounts 使用預期 access mode。
- 驗證 Backend health dependency 與 Nginx upstream。

### Container Integration Tests

- 從空 `data/` 啟動，確認 database 與 Prompt Library seed 初始化。
- 驗證 `/health`、Frontend root、`/api` proxy 及 gallery／artifact proxy。
- 重建 Backend／Frontend images 後確認資料仍存在。
- 使用 fake ComfyUI HTTP service 驗證 connected 與 unreachable transitions。
- 完全不提供 ComfyUI override 時驗證 Backend 仍 healthy。

### Platform Smoke Matrix

發布前的人工或 CI runner smoke matrix：

| 平台 | 模式 |
|------|------|
| Windows | NVIDIA、自動安裝、既有安裝、拒絕安裝 |
| Linux | NVIDIA、CPU、host relay、拒絕安裝 |
| macOS Intel | CPU、自動安裝、拒絕安裝 |
| macOS Apple Silicon | arm64 + MPS、自動安裝、既有安裝 |

每個平台至少驗證首次設定、`start`、`status`、`stop`、`reconfigure`、重建後資料保留，以及無模型時的成功降級訊息。

## Documentation

README 的主要啟動說明只保留兩個平台命令與必要條件，不再要求一般使用者手動複製 `.env`、安裝 Backend dependencies 或初始化資料庫。完整手動／開發啟動方式移至 setup guide 的進階章節。

文件必須明確說明：

- Docker 與 Git 仍是主機必要條件。
- GPU driver 由使用者／作業系統提供。
- ComfyUI 與模型是選用能力。
- 自動安裝 ComfyUI 不包含模型。
- `.env` 與 `data/` 不得提交。
- 如何查看狀態、logs、重新設定與停止服務。

完成實作與驗證後，依 repository 規範同步更新 `docs/PROGRESS.md`。
