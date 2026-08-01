$ErrorActionPreference = "Stop"

$Root = "C:\AI-Drawing-Worker"
$TaskName = "AI-Drawing NVIDIA Worker"
$Source = Split-Path -Parent $MyInvocation.MyCommand.Path
$Manifest = Get-Content (Join-Path $Source "worker-manifest.json") -Raw | ConvertFrom-Json
$Utf8NoBom = New-Object System.Text.UTF8Encoding -ArgumentList $false
. (Join-Path $Source "WorkerSecurity.ps1")
. (Join-Path $Source "Migrate-Worker.ps1")

if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run Setup.cmd as Administrator."
}

# An in-place upgrade must not copy a live Python/ComfyUI runtime or launch a
# second listener. Only stop the fixed task/ports for a recognized owned
# installation; a fresh install does not terminate unrelated local services.
$ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
$OwnedInstall = Test-Path -LiteralPath (Join-Path $Root ".ai-drawing-worker-owned") -PathType Leaf
if ($ExistingTask -or $OwnedInstall) {
    if ($ExistingTask -and $ExistingTask.State -eq "Running") {
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    }
    $ExistingListenerPids = Get-NetTCPConnection -LocalPort 8188, 8791 -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($ListenerPid in $ExistingListenerPids) {
        Stop-Process -Id $ListenerPid -Force -ErrorAction Stop
    }
}

$Profiles = Get-NetConnectionProfile | Where-Object {
    $_.IPv4Connectivity -ne "Disconnected" -and $_.NetworkCategory -eq "Private"
}
if (-not $Profiles) {
    throw "Active Windows network must be Private before installing the Worker firewall rule."
}

$NvidiaSmi = Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue
if (-not $NvidiaSmi) {
    throw "NVIDIA driver is missing or nvidia-smi.exe is not available."
}
$GpuRows = & $NvidiaSmi.Source --query-gpu=name,memory.total,driver_version --format=csv,noheader,nounits
if (-not $GpuRows) { throw "No NVIDIA GPU was detected." }
Write-Host "Detected NVIDIA GPU: $($GpuRows[0])"

if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) {
    $Winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $Winget) {
        throw "Git is missing and winget is unavailable. Install Git for Windows and retry."
    }
    & $Winget.Source install --id Git.Git --exact --silent --accept-package-agreements --accept-source-agreements
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
        [Environment]::GetEnvironmentVariable("Path", "User")
}
if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) {
    throw "Git installation did not become available."
}

$Drive = Get-PSDrive -Name C
$Required = ([int64]$Manifest.minimum_free_gb * 1GB + [int64]$Manifest.cache_gb * 1GB + 10GB)
if ($Drive.Free -lt $Required) {
    throw "C: needs enough free space for runtime, temporary files, the $($Manifest.cache_gb)GB model cache, and the $($Manifest.minimum_free_gb)GB reserve."
}

if (Test-Path -LiteralPath $Root) {
    Assert-ExistingWorkerRoot -Path $Root
} else {
    New-SecureUpdaterDirectory -Path $Root
}

New-Item -ItemType Directory -Force -Path (Join-Path $Root "app"), (Join-Path $Root "config"), (Join-Path $Root "config\update-owned\state"), (Join-Path $Root "runtime"), (Join-Path $Root "runtime\logs"), (Join-Path $Root "shared\models"), (Join-Path $Root "shared\cache"), (Join-Path $Root "shared\partial"), (Join-Path $Root "shared\input"), (Join-Path $Root "shared\output") | Out-Null
[IO.File]::WriteAllText((Join-Path $Root ".ai-drawing-worker-owned"), "AI-Drawing NVIDIA Worker`n", $Utf8NoBom)
Reset-SecureUpdaterChildAcl -Path (Join-Path $Root ".ai-drawing-worker-owned")

$ExistingConfigPath = Join-Path $Root "config\worker.json"
if (Test-Path $ExistingConfigPath) {
    $ExistingConfig = Get-Content $ExistingConfigPath -Raw | ConvertFrom-Json
    $Token = [string]$ExistingConfig.token
}
if (-not $Token) {
    $TokenBytes = New-Object byte[] 32
    $Rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $Rng.GetBytes($TokenBytes) } finally { $Rng.Dispose() }
    $Token = [Convert]::ToBase64String($TokenBytes)
}
$Config = @{
    token = $Token
    cache_gb = [int]$Manifest.cache_gb
    minimum_free_gb = [int]$Manifest.minimum_free_gb
} | ConvertTo-Json
[IO.File]::WriteAllText((Join-Path $Root "config\worker.json"), $Config + "`n", $Utf8NoBom)

Copy-Item (Join-Path $Source "worker.py") (Join-Path $Root "app\worker.py") -Force
Copy-Item (Join-Path $Source "Start-Worker.cmd") (Join-Path $Root "Start-Worker.cmd") -Force
Copy-Item (Join-Path $Source "Start-Worker.ps1") (Join-Path $Root "Start-Worker.ps1") -Force
Copy-Item (Join-Path $Source "Restart-Worker.ps1") (Join-Path $Root "Restart-Worker.ps1") -Force
Copy-Item (Join-Path $Source "Wait-Restart-Result.ps1") (Join-Path $Root "Wait-Restart-Result.ps1") -Force
Copy-Item (Join-Path $Source "Restart-Worker.cmd") (Join-Path $Root "Restart-Worker.cmd") -Force
Copy-Item (Join-Path $Source "restart_contract.py") (Join-Path $Root "app\restart_contract.py") -Force
Copy-Item (Join-Path $Source "update_contract.py") (Join-Path $Root "app\update_contract.py") -Force
Copy-Item (Join-Path $Source "Migrate-Worker.ps1") (Join-Path $Root "Migrate-Worker.ps1") -Force
Copy-Item (Join-Path $Source "worker-manifest.json") (Join-Path $Root "worker-manifest.json") -Force

$UvRoot = Join-Path $Root "runtime\uv"
$env:UV_UNMANAGED_INSTALL = $UvRoot
$Uv = Join-Path $UvRoot "uv.exe"
if (-not (Test-Path $Uv)) {
    $env:UV_NO_MODIFY_PATH = "1"
    Invoke-RestMethod "https://astral.sh/uv/$($Manifest.uv)/install.ps1" | Invoke-Expression
}

$PythonRoot = Join-Path $Root "runtime\python"
& $Uv python install $Manifest.python --install-dir $PythonRoot
$Python = (Get-ChildItem $PythonRoot -Recurse -Filter python.exe | Select-Object -First 1).FullName
if (-not $Python) { throw "Pinned Python installation failed." }
[IO.File]::WriteAllText((Join-Path $Root "config\python-path.txt"), $Python + "`n", $Utf8NoBom)

$UpdaterRuntime = Join-Path $Root "updater-runtime"
if (-not (Test-Path (Join-Path $UpdaterRuntime "Scripts\python.exe"))) {
    & $Python -m venv $UpdaterRuntime
}
$UpdaterPython = Join-Path $UpdaterRuntime "Scripts\python.exe"
if (-not (Test-Path $UpdaterPython -PathType Leaf)) {
    throw "Updater-owned Python installation failed."
}
$UpdaterPackage = Join-Path $Root "updater"
New-Item -ItemType Directory -Force -Path $UpdaterPackage | Out-Null
Copy-Item (Join-Path $Source "updater\*") $UpdaterPackage -Recurse -Force
Protect-UpdaterTree -Path $UpdaterRuntime
Protect-UpdaterTree -Path $UpdaterPackage

$ComfyRoot = Join-Path $Root "runtime\ComfyUI"
if (-not (Test-Path (Join-Path $ComfyRoot ".git"))) {
    git clone --branch $Manifest.comfyui_version --depth 1 $Manifest.comfyui_repository $ComfyRoot
}
git -C $ComfyRoot fetch --tags --force
git -C $ComfyRoot checkout --detach $Manifest.comfyui_version

& $Uv pip install --python $Python -r (Join-Path $ComfyRoot "requirements.txt")
& $Uv pip install --python $Python torch torchvision torchaudio --index-url $Manifest.pytorch_index
& $Uv pip install --python $Python -r (Join-Path $Source "requirements.txt")

$CustomRoot = Join-Path $ComfyRoot "custom_nodes"
New-Item -ItemType Directory -Force -Path $CustomRoot | Out-Null
foreach ($Node in $Manifest.custom_nodes) {
    if (-not $Node.repository -or -not $Node.revision) {
        throw "Every custom node must have a pinned repository and revision."
    }
    $NodeRoot = Join-Path $CustomRoot $Node.name
    if (-not (Test-Path (Join-Path $NodeRoot ".git"))) {
        git clone --no-checkout $Node.repository $NodeRoot
    }
    git -C $NodeRoot fetch --force origin $Node.revision
    git -C $NodeRoot checkout --detach $Node.revision
    $NodeRequirements = Join-Path $NodeRoot "requirements.txt"
    if (Test-Path $NodeRequirements) {
        & $Uv pip install --python $Python -r $NodeRequirements
    }
}

schtasks.exe /Create /TN $TaskName /SC ONLOGON /RL HIGHEST /TR "`"$Root\Start-Worker.cmd`"" /F | Out-Null

$SourceRepositoryRoot = "C:\AI-Drawing-Worker-Source"
$ExpectedRemoteUrl = [string]$Manifest.source_repository
$ExpectedBranch = [string]$Manifest.source_branch
if (-not $ExpectedRemoteUrl -or -not $ExpectedBranch) {
    throw "Worker source repository configuration is missing."
}
if (-not (Test-Path (Join-Path $SourceRepositoryRoot ".git"))) {
    git clone --branch $ExpectedBranch --single-branch -- $ExpectedRemoteUrl $SourceRepositoryRoot
}
$ActualRemoteUrl = (git -C $SourceRepositoryRoot remote get-url origin).Trim()
if ($LASTEXITCODE -ne 0 -or -not $ActualRemoteUrl) {
    throw "Worker source repository remote is unavailable."
}
[IO.File]::WriteAllText((Join-Path $Root "config\expected-remote-url.txt"), $ExpectedRemoteUrl + "`n", $Utf8NoBom)

$ProgramDataRoot = Join-Path $env:ProgramData "AI-Drawing-Worker"
if (Test-Path -LiteralPath $ProgramDataRoot) {
    Assert-SecureUpdaterTree -Path $ProgramDataRoot
} else {
    New-SecureUpdaterDirectory -Path $ProgramDataRoot
}
$BootstrapPath = Join-Path $ProgramDataRoot "UpdaterBootstrap.ps1"
Copy-Item (Join-Path $Source "UpdaterBootstrap.ps1") $BootstrapPath -Force
$UpdaterEnvironment = @(
    "AI_DRAWING_PROJECT_ROOT=$SourceRepositoryRoot"
    "AI_DRAWING_WORKER_ROOT=$Root"
    "AI_DRAWING_WORKER_REMOTE=origin"
    "AI_DRAWING_WORKER_BRANCH=$ExpectedBranch"
)
$UpdaterEnvironmentText = ($UpdaterEnvironment -join [Environment]::NewLine) + [Environment]::NewLine
[IO.File]::WriteAllText((Join-Path $ProgramDataRoot "updater.env"), $UpdaterEnvironmentText, $Utf8NoBom)
Install-FixedMigrationEnvironment -ProgramDataRoot $ProgramDataRoot | Out-Null
Protect-UpdaterTree -Path $ProgramDataRoot

$UpdaterTaskAction = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
    -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$env:ProgramData\AI-Drawing-Worker\UpdaterBootstrap.ps1`""
$UpdaterTaskPrincipal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$UpdaterTaskSettings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Register-ScheduledTask -TaskName "AI-Drawing Worker Updater" -Action $UpdaterTaskAction `
    -Principal $UpdaterTaskPrincipal -Settings $UpdaterTaskSettings -Force | Out-Null

$RestartTaskAction = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
    -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$Root\Restart-Worker.ps1`""
$RestartTaskPrincipal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$RestartTaskSettings = New-ScheduledTaskSettingsSet -MultipleInstances Queue -ExecutionTimeLimit (New-TimeSpan -Minutes 3)
Register-ScheduledTask -TaskName "AI-Drawing NVIDIA Worker Restart" -Action $RestartTaskAction `
    -Principal $RestartTaskPrincipal -Settings $RestartTaskSettings -Force | Out-Null

Get-NetFirewallRule -DisplayName $TaskName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -DisplayName $TaskName -Direction Inbound -Action Allow -Protocol TCP `
    -LocalPort $Manifest.listen_port -Profile Private -RemoteAddress LocalSubnet | Out-Null

$Desktop = [Environment]::GetFolderPath("Desktop")
$DesktopLauncher = Join-Path $Desktop "一鍵重啟 AI-Drawing Worker.cmd"
Copy-Item (Join-Path $Source "Restart-Worker.cmd") $DesktopLauncher -Force
$PrivateProfile = $Profiles | Where-Object { $_.NetworkCategory -eq "Private" } | Select-Object -First 1
$WorkerIp = Get-NetIPAddress -AddressFamily IPv4 -InterfaceIndex $PrivateProfile.InterfaceIndex |
    Where-Object { $_.IPAddress -notlike "169.254.*" } |
    Select-Object -ExpandProperty IPAddress -First 1
if (-not $WorkerIp) { throw "Could not determine a private-LAN IPv4 address." }
$Pairing = @"
NVIDIA_WORKER_URL=http://$($WorkerIp):$($Manifest.listen_port)
NVIDIA_WORKER_TOKEN=$Token
"@
Set-Content -Path (Join-Path $Desktop "AI-Drawing-Worker-Pairing.txt") -Value $Pairing -Encoding UTF8

$Adapter = Get-NetAdapter -InterfaceIndex $PrivateProfile.InterfaceIndex
$Mac = $Adapter.MacAddress
$Gateway = Get-NetRoute -InterfaceIndex $PrivateProfile.InterfaceIndex -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue |
    Sort-Object RouteMetric | Select-Object -ExpandProperty NextHop -First 1

Write-Host ""
Write-Host "============================================================"
Write-Host " Recommended: reserve this Worker IP in your router DHCP settings"
Write-Host "============================================================"
Write-Host "  Adapter MAC : $Mac"
Write-Host "  Worker IP   : $WorkerIp   (reserve this address)"
if ($Gateway) {
    Write-Host "  Router page : http://$Gateway   (opening the login page)"
} else {
    Write-Host "  Router page : open the router admin page manually (usually http://192.168.x.1)"
}
Write-Host "  After reserving the IP, the desktop pairing file remains valid."
Write-Host "============================================================"
if ($Gateway) {
    try { Start-Process "http://$Gateway" } catch { }
}

# Convert the freshly installed legacy directories into the versioned managed
# layout before the Worker can advertise protocol 2/update capability.  A
# failure leaves the legacy runtime intact and aborts installation rather than
# exposing a Worker that cannot activate or roll back its first update.
$InstalledCommit = (& git.exe -C $SourceRepositoryRoot rev-parse HEAD 2>$null).Trim()
if ($LASTEXITCODE -ne 0 -or $InstalledCommit -notmatch "^[0-9a-f]{40}$") {
    throw "MIGRATION_COMMIT_INVALID"
}
$ManagedRelease = Initialize-ManagedWorkerLayout -Root $Root -Commit $InstalledCommit
if (-not (Test-Path -LiteralPath (Join-Path $Root "current")) -or
    -not (Test-Path -LiteralPath (Join-Path $ManagedRelease "source-commit.txt") -PathType Leaf) -or
    -not (Test-Path -LiteralPath (Join-Path $Root "releases") -PathType Container)) {
    throw "MIGRATION_LAYOUT_INVALID"
}

Start-Process (Join-Path $Root "Start-Worker.cmd")
Write-Host "Worker installed. Copy AI-Drawing-Worker-Pairing.txt to the Mac operator."
