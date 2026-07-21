# AI 自動化出圖系統

整合 ComfyUI 生圖、Gallery、Prompt Library、資料夾監聽與 LoRA 訓練的本機工作流。Frontend 與 Backend 由 Docker Compose 管理；ComfyUI 是選用的主機服務，可以使用既有安裝、讓啟動器安裝，或完全停用。

## 三步啟動

先準備 Git、正在執行的 Docker daemon（Docker Desktop 或 Docker Engine）、Docker Compose 2.24 以上與網路連線。macOS/Linux 的 cold cache 首次 bootstrap 另需 `curl` 或 `wget`。不需要先安裝 Python 或 Node.js。

```bash
git clone https://github.com/tf00185077/ai-drawing.git
cd ai-drawing
```

Windows PowerShell：

```powershell
.\setup.ps1
```

macOS / Linux：

```bash
./setup.sh
```

第一次執行會檢查 Docker、詢問是否設定 ComfyUI、尋找既有路徑，必要時再詢問是否自動安裝。你可以在任何一個問題選擇不使用 ComfyUI；Frontend 與 Backend 仍會啟動，Dashboard 會顯示「ComfyUI 尚未設定」。

啟動完成後：

- Frontend：<http://127.0.0.1:5173>
- Backend API：<http://127.0.0.1:8001>
- API 文件：<http://127.0.0.1:8001/docs>
- ComfyUI（若啟用）：<http://127.0.0.1:8188>

> Backend 在容器內使用 port `8000`，主機固定預設映射為 `8001`。

## ComfyUI 選項

啟動器支援三種模式：

- `disabled`：拒絕安裝或暫時不用；應用程式以降級模式正常啟動。
- `external`：連接已由你啟動、且 `/system_stats` 可連線的 ComfyUI；啟動器不會停止它。
- `managed`：使用可控制的既有目錄，或安裝到你確認的路徑；啟動器只會停止自己啟動且程序身分相符的實例。

自動安裝只取得固定版本的 ComfyUI、Python runtime 與其必要依賴。它不會下載 checkpoint、LoRA、VAE、text encoder、模型或 custom nodes，也不會修改非空的既有目錄。沒有模型時，系統會顯示「ComfyUI 已連線，尚無模型」，由使用者自行放入模型。

裝置模式預設由 launcher 自動偵測並在計畫／狀態中顯示；需要時可用 `--device nvidia|mps|cpu` 明確覆寫：

- Windows / Linux NVIDIA：CUDA 模式；主機需有相容 NVIDIA driver。
- Apple Silicon：原生 arm64 Python 與 MPS；不要從 Rosetta 終端執行。
- Intel macOS 或沒有可用 GPU：CPU 模式，速度會較慢。

Apple Silicon 若從 Rosetta/x86_64 終端執行會以 `UNSUPPORTED_NATIVE_ARCHITECTURE` 中止，不會默默改用 CPU 或安裝 x86 runtime。

## 常用指令

Windows 將下列 `./setup.sh` 換成 `.\setup.ps1`：

```bash
./setup.sh setup             # 重新走完整設定並啟動
./setup.sh start             # 使用既有設定啟動
./setup.sh stop              # 停止 Compose 與 launcher-owned 程序
./setup.sh status            # 顯示 Docker、Frontend、Backend、ComfyUI、relay 狀態
./setup.sh reconfigure       # 重選 ComfyUI、路徑、裝置或 ports
./setup.sh logs              # 顯示 Compose 與啟動相關 logs
./setup.sh update-comfyui    # 只更新啟動器安裝的 ComfyUI
./setup.sh dry-run --comfyui-mode disabled  # 不寫專案設定、不安裝 ComfyUI、不啟停服務
./setup.sh --help
```

更新 launcher 安裝的 ComfyUI 時，必須依序停止、更新、再啟動；更新器不會修改仍在執行中的 Python 環境：

```bash
./setup.sh stop
./setup.sh update-comfyui
./setup.sh start
```

更新會先確認 ComfyUI 本身就是 Git repository root，再同時交易式處理固定版 source 與 `.venv`。任何步驟失敗時，只有在舊 commit、原 `.venv` 與舊 runtime smoke check 全部恢復成功後，才會回報已還原；暫存清理若未完成會另外標示 cleanup pending，不會假裝已刪除。

為避免路徑替換競態，launcher 不會自動遞迴刪除非空的 staging、backup 或 new-env 目錄。即使更新成功，也可能留下唯一命名的 `.ComfyUI.venv-backup-*` 並顯示 warning；確認沒有安裝、更新或 rollback 正在執行後，再依提示人工檢查與移除。

非互動、明確停用 ComfyUI：

```bash
./setup.sh setup --non-interactive --comfyui-mode disabled
```

完整 flags、資料保存、疑難排解與進階手動啟動請見 [docs/setup-guide.md](docs/setup-guide.md)。

`dry-run` 的 launcher 階段不會安裝 ComfyUI、寫入專案設定或改變服務；但 wrapper 在 cold cache 尚無固定版 uv/Python 時，仍可能先把 bootstrap runtime 下載到使用者 cache，之後才進入 dry-run。

## 資料與設定

啟動器會產生三個不進 Git 的本機檔案：

- `.env`：扁平的 runtime 值、ports、URL 與可能的 secrets。
- `.ai-drawing/compose.local.yaml`：需要 YAML 結構才能表達的 ComfyUI bind mounts。
- `data/bootstrap/state.json`：模式、路徑、裝置與 launcher-owned 程序身分。

Docker Compose 的固定服務拓撲放在版控內的 `docker-compose.yml`。這就是本專案同時使用 `.env` 與 YAML 的原因：兩者負責不同層次，不會互相衝突。SQLite、Prompt Library、Gallery、輸出、LoRA 訓練資料與 logs 都 bind mount 到 `data/`，重建容器不會刪除。

任何 API key 或 token 只放 `.env` 或外部 secrets 管理；不要寫進 YAML、程式碼或 commit。

## 專案模組

- 生圖：ComfyUI API、workflow 模板與批次佇列。
- 圖庫：參數記錄、Gallery 與一鍵重現。
- Prompt Library：可搜尋、組合與保存 prompt。
- LoRA 文件與訓練：資料夾監聽、caption、Kohya sd-scripts 與結果管理。
- MCP tools：供 agent 呼叫的獨立介面；本次一鍵啟動不安裝、不設定也不啟動 MCP Server。

## Agent / 新成員入口

| 你是誰 | 讀哪裡 |
|--------|--------|
| Claude Code | [CLAUDE.md](CLAUDE.md) → [AGENTS.md](AGENTS.md) |
| OpenAI Codex / GPT agents | [AGENTS.md](AGENTS.md) |
| Cursor | [.cursor/rules/](.cursor/rules/) |
| 人類 / 新成員 | 本頁 → [AGENTS.md](AGENTS.md) |

必讀順序：

1. [AGENTS.md](AGENTS.md) — 架構、安全規則與編碼慣例。
2. [docs/GOAL.md](docs/GOAL.md) — 系統目標與設計原則。
3. [docs/PROGRESS.md](docs/PROGRESS.md) — 實際進度與驗證證據。

## 開發測試

下列是開發者指令，不是一般使用者的啟動流程：

```bash
uv run --python 3.12 --with pytest --with pyyaml pytest scripts/tests -q
cd backend && pytest tests -q
cd ../frontend && npm ci && npm test && npm run build
```

MCP 測試與設定仍獨立保留；一鍵啟動流程不依賴 MCP。
