$ErrorActionPreference = "Stop"
$Ports = @(8188, 8791)
$ProgramDataRoot = Join-Path $env:ProgramData "AI-Drawing-Worker"
$EnvironmentPath = Join-Path $ProgramDataRoot "updater.env"

function Get-FixedWorkerRoot {
    if (-not (Test-Path -LiteralPath $EnvironmentPath -PathType Leaf)) { throw "RESTART_CONFIG_INVALID" }
    $Found = $null
    foreach ($Line in [IO.File]::ReadAllLines($EnvironmentPath)) {
        if (-not $Line -or $Line.StartsWith("#")) { continue }
        $Parts = $Line -split '=', 2
        if ($Parts.Count -ne 2) { throw "RESTART_CONFIG_INVALID" }
        if ($Parts[0] -eq "AI_DRAWING_WORKER_ROOT") { $Found = $Parts[1] }
    }
    if (-not $Found -or -not [IO.Path]::IsPathRooted($Found) -or $Found.StartsWith("\\")) { throw "RESTART_CONFIG_INVALID" }
    return [IO.Path]::GetFullPath($Found)
}

$Root = Get-FixedWorkerRoot
$Runtime = Join-Path $Root "config\update-owned\restart"
$StateRoot = Join-Path $Root "config\update-owned\state"
$RequestPath = Join-Path $StateRoot "restart-request.json"
$ResultPath = Join-Path $StateRoot "restart-status.json"
$PublicResultRoot = Join-Path $env:ProgramData "AI-Drawing-Worker-Public"
$PublicResultPath = Join-Path $PublicResultRoot "restart-status.json"
$LockPath = Join-Path $Runtime "restart.lock"
$LogPath = Join-Path $Runtime ("restart-{0}.log" -f (Get-Date -Format "yyyyMMdd-HHmmss"))
$LockStream = $null
$RequestId = $null

function Write-AtomicJson([hashtable]$Value) {
    foreach ($Destination in @($ResultPath, $PublicResultPath)) {
        $Temporary = "$Destination.tmp"
        [IO.File]::WriteAllText($Temporary, ($Value | ConvertTo-Json -Depth 4), (New-Object Text.UTF8Encoding($false)))
        Move-Item -LiteralPath $Temporary -Destination $Destination -Force
    }
}

function Write-SafeLog([string]$Message) {
    [IO.File]::AppendAllText($LogPath, ((Get-Date).ToString("o") + " " + $Message + [Environment]::NewLine))
}

function Write-State([string]$State, [string]$ErrorCode = "") {
    $Value = @{ request_id=$RequestId; state=$State; timestamp=(Get-Date).ToUniversalTime().ToString("o") }
    if ($ErrorCode) { $Value.error_code = $ErrorCode }
    Write-AtomicJson $Value
}

try {
    New-Item -ItemType Directory -Force -Path $Runtime, $StateRoot, $PublicResultRoot | Out-Null
    # OpenOrCreate plus FileShare.None is an OS-owned live lock.  A terminated
    # task releases the handle automatically; the harmless file may remain and
    # is never deleted out from under a successor that already acquired it.
    $LockStream = [IO.File]::Open($LockPath, [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::Write, [IO.FileShare]::None)
    foreach ($Path in @((Join-Path $Root "Start-Worker.ps1"))) {
        if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "RESTART_INSTALLATION_INCOMPLETE" }
    }
    try { $Request = Get-Content -LiteralPath $RequestPath -Raw -Encoding UTF8 | ConvertFrom-Json } catch { $Request = $null }
    if ($Request -and $Request.request_id -is [string] -and $Request.request_id) {
        $RequestId = [string]$Request.request_id
    } else {
        $RequestId = [Guid]::NewGuid().ToString()
        [IO.File]::WriteAllText($RequestPath, (@{request_id=$RequestId;timestamp=(Get-Date).ToUniversalTime().ToString("o")} | ConvertTo-Json), (New-Object Text.UTF8Encoding($false)))
    }
    Write-State "restarting"
    Write-SafeLog "Restart requested."

    $ListenerPids = Get-NetTCPConnection -LocalPort $Ports -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($ListenerPid in $ListenerPids) { Stop-Process -Id $ListenerPid -Force -ErrorAction Stop }
    $StartWorkerArguments = '-NoProfile -ExecutionPolicy Bypass -File "{0}"' -f (Join-Path $Root "Start-Worker.ps1")
    Start-Process powershell.exe -WindowStyle Hidden -ArgumentList $StartWorkerArguments | Out-Null
    Write-State "started"
    Write-SafeLog "Worker start process launched."
    exit 0
} catch {
    if (-not $RequestId) { $RequestId = [Guid]::NewGuid().ToString() }
    try { Write-State "failed" "RESTART_FAILED"; Write-SafeLog "Restart failed. See installation and service logs." } catch { }
    exit 1
} finally {
    if ($LockStream) { $LockStream.Dispose() }
    Get-ChildItem $Runtime -Filter "restart-*.log" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -Skip 5 | Remove-Item -Force -ErrorAction SilentlyContinue
}
