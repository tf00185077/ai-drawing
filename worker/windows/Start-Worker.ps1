$ErrorActionPreference = "Stop"
$Root = (Get-Item -LiteralPath $PSScriptRoot -Force).FullName
. (Join-Path $Root "WorkerPaths.ps1")
$RecoveryPython = Join-Path $Root "updater-runtime\Scripts\python.exe"
$RecoveryModule = Join-Path $Root "updater\recovery.py"
if ((Test-Path -LiteralPath $RecoveryPython -PathType Leaf) -and (Test-Path -LiteralPath $RecoveryModule -PathType Leaf)) {
    Push-Location $Root
    try {
        & $RecoveryPython -B -m updater.recovery
        if ($LASTEXITCODE -ne 0) { throw "Managed Worker activation recovery failed." }
    } finally {
        Pop-Location
    }
}
$Current = Join-Path $Root "current"
if (Test-Path $Current) {
    $ReleaseRoot = Resolve-ManagedCurrentRelease -Root $Root
    $MigratedPythonPath = Join-Path $ReleaseRoot "python-path.txt"
    if (Test-Path -LiteralPath $MigratedPythonPath -PathType Leaf) {
        $RelativePython = (Get-Content -LiteralPath $MigratedPythonPath -Raw -Encoding UTF8).Trim()
        $Python = [IO.Path]::GetFullPath((Join-Path $ReleaseRoot $RelativePython))
        if (-not $Python.StartsWith($ReleaseRoot + "\", [StringComparison]::OrdinalIgnoreCase)) {
            throw "Worker Python path leaves the current release."
        }
    } else {
        $Python = Join-Path $ReleaseRoot ".venv\Scripts\python.exe"
    }
    $ComfyRoot = Join-Path $ReleaseRoot "ComfyUI"
    $WorkerAppRoot = Join-Path $ReleaseRoot "worker\windows"
    $env:AI_DRAWING_WORKER_RELEASE_ROOT = $ReleaseRoot
    $env:AI_DRAWING_WORKER_CONFIG_PATH = Join-Path $Root "config\worker.json"
    $env:AI_DRAWING_WORKER_PARTIAL_ROOT = Join-Path $ReleaseRoot "cache\.partial"
    $env:AI_DRAWING_WORKER_VERIFICATION_ROOT = Join-Path $Root "shared\cache\verified"
    $LogsRoot = Join-Path $Root "shared\logs"
} else {
    $PythonPath = Get-Content (Join-Path $Root "config\python-path.txt") -Raw
    $Python = $PythonPath.Trim()
    $ComfyRoot = Join-Path $Root "runtime\ComfyUI"
    $WorkerAppRoot = Join-Path $Root "app"
    $LogsRoot = Join-Path $Root "runtime\logs"
}
if (-not (Test-Path $Python)) { throw "Worker Python runtime is missing." }

$ComfyArgs = @(
    (Join-Path $ComfyRoot "main.py"),
    "--listen", "127.0.0.1",
    "--port", "8188"
)
$ComfyArgumentList = '"{0}" --listen 127.0.0.1 --port 8188' -f $ComfyArgs[0]
New-Item -ItemType Directory -Force -Path $LogsRoot | Out-Null
$ComfyStdoutLog = Join-Path $LogsRoot "comfyui.stdout.log"
$ComfyStderrLog = Join-Path $LogsRoot "comfyui.stderr.log"
foreach ($Log in @($ComfyStdoutLog, $ComfyStderrLog)) {
    $PreviousLog = $Log -replace "\.log$", ".previous.log"
    if (Test-Path $PreviousLog) { Remove-Item $PreviousLog -Force }
    if (Test-Path $Log) { Move-Item $Log $PreviousLog }
}
$ComfyProcess = Start-Process -FilePath $Python -ArgumentList $ComfyArgumentList -WorkingDirectory $ComfyRoot `
    -WindowStyle Hidden -RedirectStandardOutput $ComfyStdoutLog -RedirectStandardError $ComfyStderrLog -PassThru

$Ready = $false
for ($Attempt = 0; $Attempt -lt 300; $Attempt++) {
    if ($ComfyProcess.HasExited) {
        throw "ComfyUI stopped before becoming ready. See $ComfyStdoutLog and $ComfyStderrLog."
    }
    try {
        curl.exe --silent --fail --max-time 2 --output NUL "http://127.0.0.1:8188/system_stats"
        if ($LASTEXITCODE -eq 0) {
            $Ready = $true
            break
        }
    } catch {
    }
    Start-Sleep -Seconds 2
}
if (-not $Ready) { throw "ComfyUI did not become ready within 10 minutes." }

$env:AI_DRAWING_WORKER_ROOT = $Root
$env:AI_DRAWING_WORKER_UPDATE_STATE_ROOT = Join-Path $Root "config\update-owned"
$env:AI_DRAWING_COMFYUI_ROOT = $ComfyRoot
$ExistingPythonPath = [Environment]::GetEnvironmentVariable("PYTHONPATH", "Process")
$env:PYTHONPATH = $Root
if ($ExistingPythonPath) {
    $env:PYTHONPATH += [IO.Path]::PathSeparator + $ExistingPythonPath
}
& $Python -m uvicorn worker:app --app-dir $WorkerAppRoot --host 0.0.0.0 --port 8791
exit $LASTEXITCODE
