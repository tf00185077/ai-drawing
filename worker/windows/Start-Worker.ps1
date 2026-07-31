$ErrorActionPreference = "Stop"
$Root = "C:\AI-Drawing-Worker"
$PythonPath = Get-Content (Join-Path $Root "config\python-path.txt") -Raw
$Python = $PythonPath.Trim()
if (-not (Test-Path $Python)) { throw "Worker Python runtime is missing." }

$ComfyRoot = Join-Path $Root "runtime\ComfyUI"
$ComfyArgs = @(
    (Join-Path $ComfyRoot "main.py"),
    "--listen", "127.0.0.1",
    "--port", "8188"
)
$LogsRoot = Join-Path $Root "runtime\logs"
New-Item -ItemType Directory -Force -Path $LogsRoot | Out-Null
$ComfyStdoutLog = Join-Path $LogsRoot "comfyui.stdout.log"
$ComfyStderrLog = Join-Path $LogsRoot "comfyui.stderr.log"
foreach ($Log in @($ComfyStdoutLog, $ComfyStderrLog)) {
    $PreviousLog = $Log -replace "\.log$", ".previous.log"
    if (Test-Path $PreviousLog) { Remove-Item $PreviousLog -Force }
    if (Test-Path $Log) { Move-Item $Log $PreviousLog }
}
$ComfyProcess = Start-Process -FilePath $Python -ArgumentList $ComfyArgs -WorkingDirectory $ComfyRoot `
    -WindowStyle Hidden -RedirectStandardOutput $ComfyStdoutLog -RedirectStandardError $ComfyStderrLog -PassThru

$Ready = $false
for ($Attempt = 0; $Attempt -lt 30; $Attempt++) {
    if ($ComfyProcess.HasExited) {
        throw "ComfyUI stopped before becoming ready. See $ComfyStdoutLog and $ComfyStderrLog."
    }
    try {
        Invoke-RestMethod "http://127.0.0.1:8188/system_stats" -TimeoutSec 2 | Out-Null
        $Ready = $true
        break
    } catch {
        Start-Sleep -Seconds 2
    }
}
if (-not $Ready) { throw "ComfyUI did not become ready within 60 seconds." }

$env:AI_DRAWING_WORKER_ROOT = $Root
& $Python -m uvicorn worker:app --app-dir (Join-Path $Root "app") --host 0.0.0.0 --port 8791
exit $LASTEXITCODE
