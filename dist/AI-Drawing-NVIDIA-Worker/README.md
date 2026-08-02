# AI-Drawing NVIDIA Worker（Windows 11）

## Direct-to-D 全新安裝

此套件將 Worker 直接安裝到：

```text
D:\code\AI-Drawing-Worker
```

大型 Python／ComfyUI runtime、模型、cache、input/output 都位於 D 槽。C 槽只保留很小的 privileged updater 控制資料：

```text
C:\ProgramData\AI-Drawing-Worker
```

此流程是破壞性的 clean install，不是 migration。它會移除舊 C 槽 Worker、舊 Token、模型、cache、input/output、舊 pairing 與失敗 migration 內容，且不提供 C 槽 rollback。

## 安裝流程

1. 以系統管理員 PowerShell 執行 `Clean-Install-Worker.ps1`，先取得 deletion plan 與 `plan_sha256`。
2. 核對所有目標與容量後，以相同 hash 加上 `-Apply -ExpectedPlanSha256 <hash>` 執行清理。
3. 右鍵執行 `Setup-D.cmd`，或在系統管理員 PowerShell 執行 `Setup-D.ps1`。
4. 等待 Python、CUDA PyTorch、ComfyUI、custom nodes、managed release 與排程安裝完成。
5. 將桌面的新 `AI-Drawing-Worker-Pairing.txt` 提供給 Mac operator。舊 pairing 必然失效。

不要把 Token、pairing 檔內容或 `worker.json` 上傳到 Git 或貼到對話中。

## 成功條件

- ComfyUI 在 `127.0.0.1:8188` healthy 且回報 CUDA GPU。
- Worker 在 `0.0.0.0:8791` healthy，未帶 Token 請求回 401。
- Worker status 回報 protocol 2、正確 source commit、update/restart capability。
- `D:\code\AI-Drawing-Worker\current` 指向正確的 versioned release。
- 三個固定排程與 ProgramData updater metadata 都指向 D 槽 root。

若安裝失敗，保留 D 槽 Worker 目錄與 logs 供診斷；不要再次執行廣泛清理，也不要手動刪除未知 junction。

## Mac 配對

新的 pairing 檔包含 Windows Worker URL 與新 Token。匯入 Mac 後，再由 Mac Backend 驗證 discovery、protocol 2、CUDA／ComfyUI ready、restart 與 update。

在所有實機驗證完成前，維持：

```text
NVIDIA_WORKER_AUTO_UPDATE=false
```

## Updater bootstrap deployment (Windows PowerShell 5.1 Administrator)

Open **Windows PowerShell 5.1 as Administrator** and run exactly:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
$ExpectedCommit = (& git.exe -C "D:\code\ai-drawing" rev-parse HEAD).Trim()
& "D:\code\ai-drawing\worker\windows\Deploy-UpdaterBootstrap.ps1" `
    -ExpectedCommit $ExpectedCommit
```

Wait for `UPDATER_BOOTSTRAP_READY` before proceeding. Keep
`NVIDIA_WORKER_AUTO_UPDATE=false` throughout this one-time deployment. Do not
rerun a failed request ID. If the result is
`UPDATER_BOOTSTRAP_RECOVERY_REQUIRED`, do not delete backup or staging paths
and do not submit an update.
