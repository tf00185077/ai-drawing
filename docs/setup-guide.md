# AI 自動化出圖系統：完整啟動指南

一般使用者只需要 Git 與 Docker；Frontend、Backend 和資料目錄由 Docker Compose 管理。ComfyUI 是選用的主機服務，第一次啟動時可以使用既有路徑、自動安裝或拒絕安裝。

## 1. 前置需求

| 項目 | 要求 | 說明 |
|------|------|------|
| Git | 可執行 `git clone` | 啟動器不會替你安裝 Git。 |
| Docker | daemon 必須正在執行 | Windows/macOS 通常使用 Docker Desktop；Linux 可使用 Docker Engine。 |
| Docker Compose | `2.24` 以上 | 使用 `docker compose`，不是舊的 `docker-compose`。 |
| 網路 | 第一次啟動需要 | 取得固定版 uv/Python、建置容器；只有同意自動安裝 ComfyUI 時才會取得 ComfyUI runtime。 |
| 下載工具 | macOS/Linux 需 curl 或 wget（命令為 `curl` / `wget`） | cold cache 取得固定版 uv 時使用；兩者皆無時會回傳明確錯誤與提示。 |
| GPU driver | 只有 GPU 模式需要 | NVIDIA driver 或 Apple Silicon 的原生 macOS/MPS；啟動器不安裝 driver。 |
| 磁碟與檔案分享 | Docker 可讀專案及所選 ComfyUI 目錄 | Docker Desktop 使用者需允許對應磁碟/目錄分享。 |

一般流程不需要預先安裝 Python、Node.js、npm、Kohya sd-scripts 或 MCP Server。

## 2. Clone 後一鍵啟動

```bash
git clone https://github.com/tf00185077/ai-drawing.git
cd ai-drawing
```

Windows PowerShell：

```powershell
.\setup.ps1
```

PowerShell 也接受 `./setup.ps1`。若本機 execution policy 阻擋腳本，可只對這次程序執行：

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

macOS / Linux：

```bash
./setup.sh
```

沒有指定指令時，第一次等同 `setup`；已有設定時等同 `start`。wrapper 會在使用者 cache 內取得固定版 uv `0.11.29` 與 Python `3.12`，然後執行共用 Python launcher，不污染全域 Python/Node 環境。

啟動後的預設網址：

| 服務 | 主機網址 | 容器內 port |
|------|----------|-------------|
| Frontend | <http://127.0.0.1:5173> | `80` |
| Backend API | <http://127.0.0.1:8001> | `8000` |
| Backend docs | <http://127.0.0.1:8001/docs> | `8000` |
| ComfyUI（選用） | <http://127.0.0.1:8188> | 在主機執行，不放進 Compose |

主機 Backend 使用 `8001`，避免和容器內的 `8000` 混淆。

## 3. 第一次互動流程

`setup` 依序執行：

1. 檢查 Docker CLI、Docker daemon 與 Compose `2.24+`。
2. 檢查 Backend `8001`、Frontend `5173` 與 ComfyUI `8188`；不會終止占用 port 的程序。
3. 詢問是否設定 ComfyUI。回答否會保存 `disabled`，並繼續啟動應用程式。
4. 若回答是，先探測 `8188/system_stats`，再有限度搜尋常見目錄與上次設定，不會遞迴掃描整個磁碟。
5. 找到既有目錄時顯示路徑供確認；也可手動輸入路徑。
6. 未找到時才詢問是否自動安裝，以及安裝位置。非空目標目錄會被拒絕，不會覆蓋使用者檔案。
7. launcher 自動偵測 NVIDIA、Apple Silicon MPS 或 CPU runtime 並顯示結果；使用者可用 `--device` 明確覆寫。需要時可選 retry、改 CPU、停用或中止。
8. 只在 Linux 且容器需要存取主機 loopback ComfyUI 時，啟動受 launcher 管理的本機 relay。
9. 以暫存檔產生 `.env`、Compose override 與 state，先執行 `docker compose config`，通過後才原子替換正式設定。
10. 建立資料目錄，執行 `docker compose up -d --build --remove-orphans`，等待 Backend 與 Frontend health check。
11. 顯示實際網址與 ComfyUI 模式；失敗時回復舊設定，並清理本次新啟動且 ownership 可驗證的程序。

### ComfyUI 三種模式

| 模式 | 行為 | `stop` 是否停止 ComfyUI |
|------|------|------------------------|
| `disabled` | 不探測、不安裝；Frontend/Backend 降級啟動 | 否 |
| `external` | 使用已由使用者啟動且 API 可連線的實例 | 否 |
| `managed` | 使用可控制的既有目錄，或由 launcher 安裝並啟動 | 只有 PID 與完整程序身分都吻合時才會停止 |

自動安裝固定在 ComfyUI `v0.28.0`，使用 staged 目錄，完成依賴與 device smoke check 後才移到正式位置。它只安裝 ComfyUI、隔離的 Python runtime 與 ComfyUI 必要套件；絕不下載 checkpoint、LoRA、VAE、text encoder、其他模型或 custom nodes。

### 裝置行為

預設為自動偵測，不會無聲改寫結果；dry-run/status 會顯示模式，也可用 `--device nvidia|mps|cpu` 明確覆寫。

- Windows / Linux NVIDIA：使用 CUDA 13.0 PyTorch wheels；driver 不相容時會明確失敗，可選 CPU 或 disabled。
- Apple Silicon：使用原生 arm64 Python 與 MPS；不要從 Rosetta/x86 shell 執行。
- Intel macOS：CPU。
- 其他無可用 NVIDIA GPU 的 Windows/Linux：CPU，啟動時加 `--cpu`，生圖會較慢。

硬體偵測只決定安裝與啟動參數，不會修改 driver。

在 Apple Silicon 上若 `sysctl -in sysctl.proc_translated` 回報 `1`，launcher 會以穩定錯誤 `UNSUPPORTED_NATIVE_ARCHITECTURE` 中止並提示改用原生 arm64 終端；不會默默退回 CPU 或安裝 x86 runtime。真正的 Intel macOS（回報 `0` 或沒有該 sysctl）仍使用 CPU。

## 4. 所有 launcher 指令

以下以 macOS/Linux 為例；Windows 將 `./setup.sh` 換成 `.\setup.ps1`。

| 指令 | 用途 |
|------|------|
| `./setup.sh` | 第一次 setup；已有 state 時 start。 |
| `./setup.sh setup` | 完整設定、驗證並啟動。 |
| `./setup.sh start` | 使用既有設定啟動 Compose 與需要的 managed ComfyUI。 |
| `./setup.sh stop` | 停止 Compose、launcher-owned relay 與經身分驗證的 managed ComfyUI；不碰 external。 |
| `./setup.sh status` | 唯讀顯示 Docker、Compose、Backend、Frontend、ComfyUI、模型數與 relay。Docker 不可用時仍回報可取得的狀態。 |
| `./setup.sh reconfigure` | 重選模式、路徑、裝置或 ports，成功後才替換舊設定。 |
| `./setup.sh logs` | 顯示 bootstrap、ComfyUI、relay 與最近 200 行 Compose logs；含 secret 的行會遮罩。 |
| `./setup.sh update-comfyui` | 只更新 launcher 安裝且 provenance 完整的 ComfyUI；使用者自有目錄不會被修改。 |
| `./setup.sh dry-run ...` | launcher 不寫專案設定、不安裝 ComfyUI、不啟動或停止服務；cold cache 的 wrapper 仍可能先 bootstrap 固定版 uv/Python 到使用者 cache。 |
| `./setup.sh --help` | 顯示完整參數。 |

常用 flags：

```text
--non-interactive
--accept-alternate-ports
--comfyui-mode disabled|external|managed
--comfyui-path <path>
--device nvidia|mps|cpu
--backend-port <1-65535>
--frontend-port <1-65535>
--comfyui-port <1-65535>
--on-comfy-failure abort|retry|cpu|disabled
--on-mount-failure abort|retry|disabled
```

安全查看停用 ComfyUI 的完整計畫：

```bash
./setup.sh dry-run --non-interactive --comfyui-mode disabled
```

CI 或無人值守環境明確停用 ComfyUI：

```bash
./setup.sh setup --non-interactive --comfyui-mode disabled
```

非互動模式不猜測重要決策：managed 必須給 `--comfyui-path`，可恢復錯誤必須給對應的 `--on-*-failure`，替代 port 必須用 `--accept-alternate-ports` 接受。

## 5. 設定檔：為什麼同時用 `.env` 與 YAML

| 檔案 | 格式適合的內容 | 是否進 Git |
|------|----------------|------------|
| `.env.example` | Docker-safe 預設與 secret placeholder | 是 |
| `.env` | 扁平 key/value：模式、URL、ports、容器內路徑、API key | 否 |
| `docker-compose.yml` | 固定且可審查的服務、network、health check、ports、持久化 topology | 是 |
| `.ai-drawing/compose.local.yaml` | 依使用者 ComfyUI 路徑產生的結構化 bind mounts | 否 |
| `data/bootstrap/state.json` | launcher 模式、裝置、安裝 provenance、PID 與程序身分 | 否 |

`.env` 不是 YAML：它適合 Pydantic/Compose 的環境變數與 secret，但無法安全表達多層 service/volume 結構。YAML 適合 Compose topology 與多個 bind mount，但不應存 API key。這次設計刻意兩者並用：版控 YAML 定義固定架構，本機 `.env` 與 override 只放每台機器不同的值。

`.env`、`.ai-drawing/`、`data/` 已在 `.gitignore`。`CIVITAI_AUTHORIZATION` 若存在會在重設時保留，但不會出現在安全診斷；不要把真實 token 寫入 `.env.example`、YAML、issue 或 commit。

MCP Server 不在一鍵啟動範圍：launcher 不安裝、不設定、不啟動 MCP，也不要求 MCP client。需要者可另外用 agent 或 [mcp-setup.md](mcp-setup.md) 設定。

## 6. 資料持久化

Compose 將下列主機目錄 bind mount 至 Backend；rebuild/recreate 容器不會移除它們：

| 主機 | 容器 | 內容 |
|------|------|------|
| `data/database/` | `/data/database` | SQLite 與檔案 digest cache |
| `data/prompt_library/` | `/data/prompt_library` | Prompt Library 使用者資料 |
| `data/gallery/` | `/data/gallery` | Gallery |
| `data/outputs/` | `/data/outputs` | 產圖輸出 |
| `data/lora_train/` | `/data/lora_train` | LoRA 資料集與產物 |
| `data/logs/` | `/data/logs` | bootstrap、ComfyUI、relay、LoRA logs |

啟用 ComfyUI 時，模型目錄以 read/write bind mount 進 Backend 的 `/comfyui/...`，讓 Backend 列出既有資源；launcher 不會替你填入模型。

備份或移除前先執行 `stop`。launcher 本身不會自動刪除上述使用者資料。

## 7. 狀態與回復

### Backend API / Dashboard 五種狀態

`/api/system/status` 與 Dashboard 將應用程式健康度和 ComfyUI 依賴分開：

- `connected`：API 可連線且至少找到一個生成模型。
- `not_configured`：使用者選擇 disabled。
- `unreachable`：已設定但 `/system_stats` 無法連線。
- `no_models`：ComfyUI 已連線，尚無模型。
- `degraded`：可使用但部分目錄或狀態有警告。

### CLI `status` 狀態文字

CLI 依主機 probe 與可確認的模型數輸出 `not_configured`、`unreachable`、`no_models` 或 `connected`，另外呈現 ownership、模型數與 relay。CLI 不輸出 `degraded`；`degraded` 是 Backend API / Dashboard 對目錄警告的彙總狀態。

設定寫入採 validation-before-replace；任一替換失敗會復原整組舊檔。Compose 或 readiness 失敗時，launcher 會停止本次新建且 ownership 可證明的資源並回復原設定。`update-comfyui` 在更新或 smoke check 失敗時會嘗試 checkout 回舊 commit。它不會刪除非空使用者目錄，也不會只憑 PID 終止程序。

## 8. 疑難排解

### Docker daemon unavailable

先啟動 Docker Desktop/Engine，再確認：

```bash
docker info
docker compose version
```

Compose 必須至少 `2.24`。launcher 不會自動啟動或安裝 Docker。

### Port 已占用

launcher 不會殺掉占用者。互動模式可接受替代 port，或明確指定：

```bash
./setup.sh reconfigure --backend-port 8011 --frontend-port 5183
```

非互動接受自動替代需加 `--accept-alternate-ports`。

### Docker mount probe 失敗

確認 Docker Desktop 已分享專案磁碟與 ComfyUI 所在磁碟、路徑存在且 Docker 有權讀寫。修正後執行 `reconfigure`；不要手改產生中的暫存 YAML。

### 找不到既有 ComfyUI

輸入包含 `main.py` 與 `models/` 的根目錄。managed 模式還需要可辨識的 `.venv`、`venv` 或 Windows portable Python；只有 API 可連線但沒有可控制 Python 時會視為 external。

### ComfyUI 已連線但沒有模型

這是預期的 `no_models`，不是安裝失敗。自行把相容模型放進 ComfyUI 的 `models/checkpoints/` 或 `models/diffusion_models/`；launcher 不會下載模型。

### CUDA 或 MPS smoke check 失敗

先修正主機 driver/原生架構，或重新設定為 CPU/disabled：

```bash
./setup.sh reconfigure --device cpu
```

互動恢復也可選 `cpu`；非互動使用 `--on-comfy-failure cpu`。

### 服務沒有 ready

```bash
./setup.sh status
./setup.sh logs
```

主要檔案在 `data/logs/bootstrap.log`、`data/logs/comfyui.log`、`data/logs/comfyui-relay.log`。logs 輸出會遮罩疑似 authorization/token/password/secret 的整行。

## 9. 平台注意事項

- Windows：使用 PowerShell wrapper；managed 子程序以 hidden/detached flags 啟動。
- Linux：Docker container 無法直接存取主機 loopback 時，launcher 只綁安全的本機 Docker bridge address，並管理獨立 relay ownership。
- macOS Apple Silicon：Docker 仍只跑 Frontend/Backend；ComfyUI 留在主機才能使用 Metal/MPS。
- macOS Intel：ComfyUI 使用 CPU；不宣稱 MPS 或 NVIDIA。
- 所有平台：external ComfyUI 都由使用者擁有，`stop` 不會終止它。

## 10. 進階：手動開發啟動

這一節只供修改程式碼的開發者；一般使用者不要走這條流程。

需要 Python `3.11`、Node/npm，以及自行啟動的 ComfyUI（若要測生圖）。根目錄 `.env` 必須使用主機可讀路徑，不能直接沿用 Docker 產生的 `/data/...` 或 `/comfyui/...` 路徑。

後端：

```bash
cd backend
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

本機開發 Backend 預設為 <http://127.0.0.1:8000>。

前端（另一個終端）：

```bash
cd frontend
npm ci
npm run dev
```

測試：

```bash
uv run --python 3.12 --with pytest --with pyyaml pytest scripts/tests -q
cd backend && pytest tests -q
cd ../frontend && npm test && npm run build
```

LoRA 訓練開發仍需自行準備 Kohya sd-scripts、checkpoint、accelerate 與相應 runtime；一鍵啟動不會自動安裝這些項目。WD Tagger 第一次實際執行也可能依其既有行為下載模型，與 launcher 的 ComfyUI 安裝流程無關。
