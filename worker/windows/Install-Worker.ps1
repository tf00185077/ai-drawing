$ErrorActionPreference = "Stop"

$Root = "C:\AI-Drawing-Worker"
$Source = Split-Path -Parent $MyInvocation.MyCommand.Path
$Manifest = Get-Content (Join-Path $Source "worker-manifest.json") -Raw | ConvertFrom-Json

if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run Setup.cmd as Administrator."
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

if ((Test-Path $Root) -and -not (Test-Path (Join-Path $Root ".ai-drawing-worker-owned"))) {
    throw "$Root exists but is not owned by this installer."
}

New-Item -ItemType Directory -Force -Path $Root, (Join-Path $Root "app"), (Join-Path $Root "config"), (Join-Path $Root "runtime") | Out-Null
Set-Content -Path (Join-Path $Root ".ai-drawing-worker-owned") -Value "AI-Drawing NVIDIA Worker"

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
Set-Content -Path (Join-Path $Root "config\worker.json") -Value $Config -Encoding UTF8

Copy-Item (Join-Path $Source "worker.py") (Join-Path $Root "app\worker.py") -Force
Copy-Item (Join-Path $Source "Start-Worker.cmd") (Join-Path $Root "Start-Worker.cmd") -Force
Copy-Item (Join-Path $Source "Start-Worker.ps1") (Join-Path $Root "Start-Worker.ps1") -Force
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
Set-Content -Path (Join-Path $Root "config\python-path.txt") -Value $Python -Encoding UTF8

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

$TaskName = "AI-Drawing NVIDIA Worker"
schtasks.exe /Create /TN $TaskName /SC ONLOGON /RL HIGHEST /TR "`"$Root\Start-Worker.cmd`"" /F | Out-Null

Get-NetFirewallRule -DisplayName $TaskName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -DisplayName $TaskName -Direction Inbound -Action Allow -Protocol TCP `
    -LocalPort $Manifest.listen_port -Profile Private -RemoteAddress LocalSubnet | Out-Null

$Desktop = [Environment]::GetFolderPath("Desktop")
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
Write-Host " 建議：在分享器設定 DHCP 保留，讓此 Worker 內網 IP 固定"
Write-Host "============================================================"
Write-Host "  網卡 MAC : $Mac"
Write-Host "  綁定 IP  : $WorkerIp   (建議直接保留目前這個位址)"
if ($Gateway) {
    Write-Host "  管理頁面 : http://$Gateway   (已為你開啟登入頁)"
} else {
    Write-Host "  管理頁面 : 請手動開啟分享器管理介面 (通常是 http://192.168.x.1)"
}
Write-Host "  設定後桌面配對檔的 IP 會長期有效，Mac 端 .env 不需再改。"
Write-Host "============================================================"
if ($Gateway) {
    try { Start-Process "http://$Gateway" } catch { }
}

Start-Process (Join-Path $Root "Start-Worker.cmd")
Write-Host "Worker installed. Copy AI-Drawing-Worker-Pairing.txt to the Mac operator."
