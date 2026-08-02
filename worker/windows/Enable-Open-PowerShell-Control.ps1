param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F]{40}$')]
    [string]$ExpectedCommit
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$CurrentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
$CurrentPrincipal = New-Object Security.Principal.WindowsPrincipal($CurrentIdentity)
if (-not $CurrentPrincipal.IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)) {
    throw "ADMINISTRATOR_REQUIRED"
}

$RepositoryRoot = "D:\code\ai-drawing"
$SourceWindowsRoot = "D:\code\ai-drawing\worker\windows"
$InstalledWorkerRoot = "D:\code\AI-Drawing-Worker"
$InstalledWindowsRoot = Join-Path $InstalledWorkerRoot "current\worker\windows"
$TaskName = "AI-Drawing NVIDIA Worker"

& git.exe -C $RepositoryRoot fetch origin main
if ($LASTEXITCODE -ne 0) {
    throw "GIT_FETCH_FAILED"
}

$HeadCommit = (& git.exe -C $RepositoryRoot rev-parse HEAD)
if ($LASTEXITCODE -ne 0 -or $null -eq $HeadCommit) {
    throw "GIT_HEAD_READ_FAILED"
}
$HeadCommit = ([string]$HeadCommit).Trim()

$OriginMainCommit = (& git.exe -C $RepositoryRoot rev-parse origin/main)
if ($LASTEXITCODE -ne 0 -or $null -eq $OriginMainCommit) {
    throw "GIT_ORIGIN_MAIN_READ_FAILED"
}
$OriginMainCommit = ([string]$OriginMainCommit).Trim()

if ($HeadCommit -ne $OriginMainCommit) {
    throw "HEAD_ORIGIN_MAIN_MISMATCH"
}
if ($HeadCommit -ne $ExpectedCommit) {
    throw "HEAD_EXPECTED_COMMIT_MISMATCH"
}
if ($OriginMainCommit -ne $ExpectedCommit) {
    throw "ORIGIN_MAIN_EXPECTED_COMMIT_MISMATCH"
}

if (-not (Test-Path -LiteralPath $InstalledWindowsRoot -PathType Container)) {
    throw "INSTALLED_WORKER_RUNTIME_NOT_FOUND"
}

$WorkerTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
if ($WorkerTask.State -eq "Running") {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction Stop
}

$ListenerPids = @(
    Get-NetTCPConnection -State Listen -LocalPort 8791 -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
)
foreach ($ListenerPid in $ListenerPids) {
    Stop-Process -Id $ListenerPid -Force -ErrorAction Stop
}

Copy-Item -LiteralPath (Join-Path $SourceWindowsRoot "worker.py") -Destination (Join-Path $InstalledWindowsRoot "worker.py") -Force
Copy-Item -LiteralPath (Join-Path $SourceWindowsRoot "powershell_control.py") -Destination (Join-Path $InstalledWindowsRoot "powershell_control.py") -Force

Start-ScheduledTask -TaskName $TaskName -ErrorAction Stop

$Deadline = [DateTime]::UtcNow.AddSeconds(60)
while ([DateTime]::UtcNow -lt $Deadline) {
    $ReadyListener = @(
        Get-NetTCPConnection -State Listen -LocalPort 8791 -ErrorAction SilentlyContinue
    )
    if ($ReadyListener.Count -gt 0) {
        Write-Output "OPEN_POWERSHELL_CONTROL_READY"
        exit 0
    }
    Start-Sleep -Seconds 1
}

throw "WORKER_8791_NOT_LISTENING"
