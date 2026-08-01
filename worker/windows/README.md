# AI-Drawing NVIDIA Worker（Windows 11）

此資料夾是 Windows 一鍵安裝來源。它會建立獨立的
`C:\AI-Drawing-Worker`，不修改其他 ComfyUI。

## 安裝

1. 確認 Windows目前的有線網路設為「私人網路」。
2. 右鍵以系統管理員執行 `Setup.cmd`。
3. 等待固定版本 Python、ComfyUI、CUDA PyTorch及 Worker安裝完成。
4. 將桌面的 `AI-Drawing-Worker-Pairing.txt` 安全地提供給 Mac端。

## 既有舊版升級

舊版 `C:\AI-Drawing-Worker` 不需刪除，也不需重新下載模型。解壓新版 ZIP 到暫存
資料夾後，以系統管理員重新執行 `Setup.cmd`；安裝程式會保留既有 Token、建立
versioned `current/releases` runtime，並安裝 `AI-Drawing Worker Updater` 與
`AI-Drawing NVIDIA Worker Restart` 系統排程。

Setup 使用 uv 管理的固定版本 Python，並以明確的 standalone interpreter 安裝模式
安裝所有必要套件；任何必要套件安裝失敗都會立即停止。首次建立 managed runtime
前，只會移除 target 仍位於同一個 `runtime\python` 內的已驗證 uv Python alias
junction；其他 reparse point 一律拒絕，不會跟隨或刪除。

要將 managed runtime 移到 `D:\code\AI-Drawing-Worker`，Setup 成功後以系統管理員執行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\AI-Drawing-Worker-Source\worker\windows\Migrate-Worker.ps1
```

遷移採 transaction/health-check/rollback；成功後會切換排程與桌面一鍵重啟入口。
失敗時保留舊 runtime，不要手動刪除 `C:\AI-Drawing-Worker` 或 migration backup。

ComfyUI只監聽 `127.0.0.1:8188`。Worker使用8791埠，Windows防火牆僅允許
Private profile及LocalSubnet。

## Mac配對

把配對檔中的兩行加入 Mac ai-drawing `.env`：

```text
NVIDIA_WORKER_URL=http://WINDOWS_IP:8791
NVIDIA_WORKER_TOKEN=產生的隨機權杖
NVIDIA_WORKER_DISCOVERY_ENABLED=true
NVIDIA_WORKER_DISCOVERY_CIDR=192.168.1.0/24
NVIDIA_WORKER_HOSTNAME=DESKTOP-AV90PQ4
NVIDIA_WORKER_PROTOCOL_VERSION=2
```

若 DHCP 改變 Windows IP，Mac Backend 只會在上述 IPv4 `/24` 掃描 `8791`
連接埠，並以既有 Bearer Token 驗證 `/v1/worker/status` 的 hostname 與 protocol
version。僅有唯一匹配時才在目前 Backend runtime 改用新 URL；不會覆寫 `.env`。
可用 `NVIDIA_WORKER_DISCOVERY_ENABLED=false` 完全停用掃描。

Backend重啟須由操作者另行批准。重啟後可查：

```text
GET /api/workers/status
```

生成請求設定 `"execution_target": "worker"` 才會使用 Windows。預設仍是
`local`；Worker失敗不會自動改送Mac。

## 容量

預設模型快取上限70GB，並保留至少20GB可用空間。大型資源第一次使用時會從
Mac傳輸；相同SHA-256資源後續直接重用。

## 移除

`Uninstall-Worker.cmd`只移除開機啟動與防火牆規則。完整runtime與模型快取不會
自動刪除，避免不可逆資料損失。
