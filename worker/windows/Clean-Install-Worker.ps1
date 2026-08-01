param(
    [switch]$Apply,
    [string]$ExpectedPlanSha256,
    [string]$DownloadsRoot = (Join-Path $env:USERPROFILE "Downloads")
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "WorkerSecurity.ps1")
$script:DevelopmentRoot = "D:\code\ai-drawing"
$script:FixedCleanRoots = @(
    @{ path = "C:\AI-Drawing-Worker"; kind = "worker" },
    @{ path = "C:\AI-Drawing-Worker-Source"; kind = "source" },
    @{ path = "C:\ProgramData\AI-Drawing-Worker"; kind = "programdata" },
    @{ path = "D:\code\AI-Drawing-Worker"; kind = "worker" }
)
$script:FixedTaskNames = @(
    "AI-Drawing NVIDIA Worker",
    "AI-Drawing Worker Updater",
    "AI-Drawing NVIDIA Worker Restart"
)
$script:ExpectedRemote = "https://github.com/tf00185077/ai-drawing"

function Get-CleanInstallSha256 {
    param([Parameter(Mandatory = $true)][string]$Value)
    $Bytes = [Text.Encoding]::UTF8.GetBytes($Value)
    $Hasher = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($Hasher.ComputeHash($Bytes))).Replace("-", "").ToLowerInvariant() }
    finally { $Hasher.Dispose() }
}

function Get-CleanInstallTreeStats {
    param([Parameter(Mandatory = $true)][string]$Path)
    $Root = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    if ($Root.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "CLEAN_INSTALL_REPARSE" }
    [int64]$Bytes = 0
    [int64]$Files = 0
    $Pending = New-Object 'Collections.Generic.Stack[IO.DirectoryInfo]'
    $Pending.Push($Root)
    while ($Pending.Count -gt 0) {
        $Directory = $Pending.Pop()
        foreach ($Item in @(Get-ChildItem -LiteralPath $Directory.FullName -Force -ErrorAction Stop)) {
            if ($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) { continue }
            if ($Item.PSIsContainer) { $Pending.Push($Item) }
            else { $Files += 1; $Bytes += [int64]$Item.Length }
        }
    }
    return [pscustomobject]@{ file_count = $Files; total_bytes = $Bytes }
}

function Assert-CleanInstallTarget {
    param([Parameter(Mandatory = $true)][string]$Path, [Parameter(Mandatory = $true)][string]$Kind)
    $FullPath = [IO.Path]::GetFullPath($Path).TrimEnd("\")
    if ($FullPath.Equals($script:DevelopmentRoot, [StringComparison]::OrdinalIgnoreCase)) { throw "CLEAN_INSTALL_SCOPE_INVALID" }
    $Item = Get-Item -LiteralPath $FullPath -Force -ErrorAction Stop
    if (-not $Item.PSIsContainer -or ($Item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw "CLEAN_INSTALL_REPARSE" }
    if ($Kind -eq "worker") {
        $Marker = Join-Path $FullPath ".ai-drawing-worker-owned"
        if ((Get-Content -LiteralPath $Marker -Raw -Encoding UTF8 -ErrorAction Stop).Trim() -ne "AI-Drawing NVIDIA Worker") {
            throw "CLEAN_INSTALL_OWNERSHIP_INVALID"
        }
    } elseif ($Kind -eq "source") {
        $GitConfig = Join-Path $FullPath ".git\config"
        if (-not (Test-Path -LiteralPath $GitConfig -PathType Leaf)) { throw "CLEAN_INSTALL_OWNERSHIP_INVALID" }
        $Remote = (& git.exe config --file $GitConfig --get remote.origin.url 2>$null).Trim().TrimEnd("/")
        if ($Remote.EndsWith(".git", [StringComparison]::OrdinalIgnoreCase)) { $Remote = $Remote.Substring(0, $Remote.Length - 4) }
        if ($LASTEXITCODE -ne 0 -or -not $Remote.Equals($script:ExpectedRemote, [StringComparison]::OrdinalIgnoreCase)) {
            throw "CLEAN_INSTALL_OWNERSHIP_INVALID"
        }
    } elseif ($Kind -eq "programdata") {
        if (-not (Test-Path -LiteralPath (Join-Path $FullPath "updater.env") -PathType Leaf)) {
            throw "CLEAN_INSTALL_OWNERSHIP_INVALID"
        }
    } elseif ($Kind -eq "package") {
        $Name = [IO.Path]::GetFileName($FullPath)
        if ($Name -notlike "AI-Drawing-NVIDIA-Worker-fixed-*") { throw "CLEAN_INSTALL_SCOPE_INVALID" }
    } else { throw "CLEAN_INSTALL_SCOPE_INVALID" }
    return $FullPath
}

function Get-CleanInstallDeletionPlan {
    param([Parameter(Mandatory = $true)][string]$DownloadsRoot)
    $Records = New-Object 'Collections.Generic.List[object]'
    foreach ($Candidate in $script:FixedCleanRoots) {
        if (-not (Test-Path -LiteralPath $Candidate.path)) { continue }
        $Path = Assert-CleanInstallTarget -Path $Candidate.path -Kind $Candidate.kind
        $Stats = Get-CleanInstallTreeStats -Path $Path
        $Records.Add([pscustomobject]@{ path = $Path; kind = $Candidate.kind; file_count = $Stats.file_count; total_bytes = $Stats.total_bytes })
    }
    $CanonicalDownloads = [IO.Path]::GetFullPath($DownloadsRoot).TrimEnd("\")
    if (Test-Path -LiteralPath $CanonicalDownloads -PathType Container) {
        foreach ($Item in @(Get-ChildItem -LiteralPath $CanonicalDownloads -Force -Filter "AI-Drawing-NVIDIA-Worker-fixed-*")) {
            $Path = [IO.Path]::GetFullPath($Item.FullName)
            if (-not [IO.Path]::GetDirectoryName($Path).Equals($CanonicalDownloads, [StringComparison]::OrdinalIgnoreCase)) { throw "CLEAN_INSTALL_SCOPE_INVALID" }
            if ($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "CLEAN_INSTALL_REPARSE" }
            if ($Item.PSIsContainer) { $Stats = Get-CleanInstallTreeStats -Path $Path }
            else { $Stats = [pscustomobject]@{ file_count = 1; total_bytes = [int64]$Item.Length } }
            $Records.Add([pscustomobject]@{ path = $Path; kind = "package"; file_count = $Stats.file_count; total_bytes = $Stats.total_bytes })
        }
    }
    $Sorted = @($Records | Sort-Object path)
    $Payload = ConvertTo-Json $Sorted -Compress -Depth 5
    return [pscustomobject]@{
        targets = $Sorted
        total_bytes = [int64](($Sorted | Measure-Object -Property total_bytes -Sum).Sum)
        plan_sha256 = Get-CleanInstallSha256 -Value $Payload
    }
}

function Invoke-CleanInstallDeletion {
    param(
        [Parameter(Mandatory = $true)]$Plan,
        [Parameter(Mandatory = $true)][string]$ExpectedPlanSha256,
        [Parameter(Mandatory = $true)][string]$DownloadsRoot
    )
    $Fresh = Get-CleanInstallDeletionPlan -DownloadsRoot $DownloadsRoot
    if (-not $Fresh.plan_sha256.Equals($ExpectedPlanSha256, [StringComparison]::OrdinalIgnoreCase) -or
        -not $Plan.plan_sha256.Equals($ExpectedPlanSha256, [StringComparison]::OrdinalIgnoreCase)) {
        throw "CLEAN_INSTALL_PLAN_MISMATCH"
    }
    foreach ($TaskName in $script:FixedTaskNames) {
        $Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        if ($Task -and $Task.State -eq "Running") { Stop-ScheduledTask -TaskName $TaskName -ErrorAction Stop }
    }
    foreach ($ListenerPid in @(Get-NetTCPConnection -State Listen -LocalPort 8188,8791 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique)) {
        Stop-Process -Id $ListenerPid -Force -ErrorAction Stop
    }
    foreach ($TaskName in $script:FixedTaskNames) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    }
    Get-NetFirewallRule -DisplayName "AI-Drawing NVIDIA Worker" -ErrorAction SilentlyContinue | Remove-NetFirewallRule
    foreach ($Record in @($Fresh.targets | Sort-Object { $_.path.Length } -Descending)) {
        if (Test-Path -LiteralPath $Record.path) { Remove-Item -LiteralPath $Record.path -Recurse -Force -ErrorAction Stop }
    }
    $WorkerRoot = "D:\code\AI-Drawing-Worker"
    $ProgramDataRoot = "C:\ProgramData\AI-Drawing-Worker"
    foreach ($Root in @($WorkerRoot, $ProgramDataRoot)) {
        New-Item -ItemType Directory -Path $Root -ErrorAction Stop | Out-Null
        Set-SecureUpdaterRootAcl -Path $Root
    }
    $Utf8NoBom = New-Object Text.UTF8Encoding -ArgumentList $false
    $OwnershipMarker = Join-Path $WorkerRoot ".ai-drawing-worker-owned"
    [IO.File]::WriteAllText($OwnershipMarker, "AI-Drawing NVIDIA Worker`n", $Utf8NoBom)
    Reset-SecureUpdaterChildAcl -Path $OwnershipMarker
    $PreparedMarker = Join-Path $WorkerRoot ".clean-install-prepared"
    [IO.File]::WriteAllText($PreparedMarker, "direct-d-clean-install-v1`n", $Utf8NoBom)
    Reset-SecureUpdaterChildAcl -Path $PreparedMarker
    Assert-ExistingWorkerRoot -Path $WorkerRoot
    Assert-SecureUpdaterTree -Path $ProgramDataRoot
    return [pscustomobject]@{ status = "prepared"; released_bytes = $Fresh.total_bytes; worker_root = $WorkerRoot }
}

if ($MyInvocation.InvocationName -ne ".") {
    $Plan = Get-CleanInstallDeletionPlan -DownloadsRoot $DownloadsRoot
    if (-not $Apply) { $Plan | ConvertTo-Json -Depth 6; exit 0 }
    if (-not $ExpectedPlanSha256) { throw "CLEAN_INSTALL_PLAN_HASH_REQUIRED" }
    Invoke-CleanInstallDeletion -Plan $Plan -ExpectedPlanSha256 $ExpectedPlanSha256 -DownloadsRoot $DownloadsRoot | ConvertTo-Json -Compress
}
