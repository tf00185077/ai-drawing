$ErrorActionPreference = "Stop"

$script:MigrationSourceRoot = "C:\AI-Drawing-Worker"
$script:MigrationPayloadRoot = $PSScriptRoot
$script:MigrationProgramDataRoot = Join-Path $env:ProgramData "AI-Drawing-Worker"
$script:MigrationEnvironmentPath = Join-Path $script:MigrationProgramDataRoot "updater.env"
$script:MigrationTaskNames = @(
    "AI-Drawing NVIDIA Worker",
    "AI-Drawing Worker Updater",
    "AI-Drawing NVIDIA Worker Restart"
)
$script:Utf8NoBom = New-Object Text.UTF8Encoding -ArgumentList $false

function Get-MigrationSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)

    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
}

function Get-MigrationStringSha256 {
    param([Parameter(Mandatory = $true)][string]$Value)

    $Sha = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($Sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($Value)))).Replace("-", "").ToLowerInvariant()
    } finally {
        $Sha.Dispose()
    }
}

function Get-MigrationTreeNoFollow {
    param([Parameter(Mandatory = $true)][string]$Root)

    $RootItem = Get-Item -LiteralPath $Root -Force -ErrorAction Stop
    if (-not $RootItem.PSIsContainer) { throw "MIGRATION_PATH_INVALID" }
    $Pending = New-Object "System.Collections.Generic.Stack[System.IO.DirectoryInfo]"
    $Files = New-Object "System.Collections.Generic.List[System.IO.FileInfo]"
    $Pending.Push($RootItem)
    while ($Pending.Count -gt 0) {
        $Directory = $Pending.Pop()
        if (($Directory.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "MIGRATION_REPARSE_POINT"
        }
        foreach ($Item in @(Get-ChildItem -LiteralPath $Directory.FullName -Force -ErrorAction Stop)) {
            if (($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "MIGRATION_REPARSE_POINT"
            }
            if ($Item.PSIsContainer) {
                $Pending.Push($Item)
            } else {
                $Files.Add($Item)
            }
        }
    }
    return $Files.ToArray()
}

function Get-MigrationInventory {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$ConfigPath
    )

    $CanonicalRoot = (Get-Item -LiteralPath $Root -Force -ErrorAction Stop).FullName.TrimEnd("\")
    $Files = @(Get-MigrationTreeNoFollow -Root $CanonicalRoot | Sort-Object FullName)
    $Digests = [ordered]@{}
    [int64]$TotalBytes = 0
    foreach ($File in $Files) {
        $Relative = $File.FullName.Substring($CanonicalRoot.Length).TrimStart("\", "/").Replace("\", "/")
        $Digests[$Relative] = Get-MigrationSha256 -Path $File.FullName
        $TotalBytes += [int64]$File.Length
    }

    $ConfigHash = $null
    $TokenHash = $null
    if (Test-Path -LiteralPath $ConfigPath -PathType Leaf) {
        $CanonicalConfig = (Get-Item -LiteralPath $ConfigPath -Force -ErrorAction Stop).FullName
        if (-not $CanonicalConfig.StartsWith($CanonicalRoot + "\", [StringComparison]::OrdinalIgnoreCase)) {
            throw "MIGRATION_CONFIG_INVALID"
        }
        $ConfigHash = Get-MigrationSha256 -Path $CanonicalConfig
        try {
            $Config = Get-Content -LiteralPath $CanonicalConfig -Raw -Encoding UTF8 | ConvertFrom-Json -ErrorAction Stop
            $Token = [string]$Config.token
            if (-not $Token -or $Token.Contains("`r") -or $Token.Contains("`n")) {
                throw "MIGRATION_CONFIG_INVALID"
            }
            $TokenHash = Get-MigrationStringSha256 -Value $Token
        } catch {
            throw "MIGRATION_CONFIG_INVALID"
        }
    }

    return [pscustomobject]@{
        canonical_path = $CanonicalRoot
        file_count = $Files.Count
        total_bytes = $TotalBytes
        config_sha256 = $ConfigHash
        token_sha256 = $TokenHash
        file_digests = $Digests
    }
}

function Assert-MigrationCapacity {
    param(
        [Parameter(Mandatory = $true)][int64]$SourceBytes,
        [Parameter(Mandatory = $true)][int64]$AvailableBytes,
        [Parameter(Mandatory = $true)][int64]$ReserveBytes
    )

    if ($SourceBytes -lt 0 -or $AvailableBytes -lt 0 -or $ReserveBytes -lt 0) {
        throw "MIGRATION_CAPACITY_INVALID"
    }
    if ($AvailableBytes -lt ($SourceBytes + $ReserveBytes)) {
        throw "MIGRATION_FREE_SPACE_INSUFFICIENT"
    }
}

function Read-FixedMigrationEnvironment {
    param([Parameter(Mandatory = $true)][string]$Path)

    $Allowed = @(
        "AI_DRAWING_PROJECT_ROOT",
        "AI_DRAWING_WORKER_ROOT",
        "AI_DRAWING_WORKER_REMOTE",
        "AI_DRAWING_WORKER_BRANCH"
    )
    $Values = [ordered]@{}
    try {
        foreach ($Line in @(Get-Content -LiteralPath $Path -Encoding UTF8 -ErrorAction Stop)) {
            if (-not $Line) { continue }
            $Separator = $Line.IndexOf("=")
            if ($Separator -le 0) { throw "invalid" }
            $Key = $Line.Substring(0, $Separator)
            $Value = $Line.Substring($Separator + 1)
            if ($Allowed -notcontains $Key -or $Values.Contains($Key) -or -not $Value) {
                throw "invalid"
            }
            $Values[$Key] = $Value
        }
        if ($Values.Count -ne $Allowed.Count) { throw "invalid" }
        foreach ($Key in $Allowed) {
            if (-not $Values.Contains($Key)) { throw "invalid" }
        }
    } catch {
        throw "MIGRATION_CONFIG_INVALID"
    }
    return [pscustomobject]$Values
}

function Write-FixedMigrationWorkerRoot {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$WorkerRoot
    )

    $Environment = Read-FixedMigrationEnvironment -Path $Path
    $Text = @(
        "AI_DRAWING_PROJECT_ROOT=$($Environment.AI_DRAWING_PROJECT_ROOT)",
        "AI_DRAWING_WORKER_ROOT=$WorkerRoot",
        "AI_DRAWING_WORKER_REMOTE=$($Environment.AI_DRAWING_WORKER_REMOTE)",
        "AI_DRAWING_WORKER_BRANCH=$($Environment.AI_DRAWING_WORKER_BRANCH)"
    ) -join [Environment]::NewLine
    [IO.File]::WriteAllText($Path, $Text + [Environment]::NewLine, $script:Utf8NoBom)
}

function Add-MigrationCopyRecord {
    param(
        [Parameter(Mandatory = $true)]$Records,
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Target
    )

    $SourceItem = Get-Item -LiteralPath $Source -Force -ErrorAction Stop
    $TargetItem = Get-Item -LiteralPath $Target -Force -ErrorAction Stop
    $SourceHash = Get-MigrationSha256 -Path $SourceItem.FullName
    $TargetHash = Get-MigrationSha256 -Path $TargetItem.FullName
    if ($SourceItem.Length -ne $TargetItem.Length -or $SourceHash -ne $TargetHash) {
        throw "MIGRATION_COPY_VERIFICATION_FAILED"
    }
    $Records.Add([pscustomobject]@{
        source = $SourceItem.FullName
        target = $TargetItem.FullName
        bytes = [int64]$SourceItem.Length
        sha256 = $SourceHash
    }) | Out-Null
}

function Copy-MigrationFileVerified {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Target,
        [Parameter(Mandatory = $true)]$Records
    )

    $Parent = Split-Path -Parent $Target
    if (-not (Test-Path -LiteralPath $Parent)) {
        New-Item -ItemType Directory -Path $Parent -Force | Out-Null
    }
    if (Test-Path -LiteralPath $Target) {
        $ExistingHash = Get-MigrationSha256 -Path $Target
        $SourceHash = Get-MigrationSha256 -Path $Source
        if ($ExistingHash -ne $SourceHash -or (Get-Item -LiteralPath $Target).Length -ne (Get-Item -LiteralPath $Source).Length) {
            throw "MIGRATION_COPY_CONFLICT"
        }
    } else {
        Copy-Item -LiteralPath $Source -Destination $Target
    }
    Add-MigrationCopyRecord -Records $Records -Source $Source -Target $Target
}

function Copy-MigrationTreeVerified {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Target,
        [Parameter(Mandatory = $true)]$Records,
        [string[]]$ExcludedRoots = @()
    )

    if (-not (Test-Path -LiteralPath $Source -PathType Container)) { return }
    $CanonicalSource = (Get-Item -LiteralPath $Source -Force).FullName.TrimEnd("\")
    if (-not (Test-Path -LiteralPath $Target)) {
        New-Item -ItemType Directory -Path $Target -Force | Out-Null
    }
    foreach ($File in @(Get-MigrationTreeNoFollow -Root $CanonicalSource)) {
        $Relative = $File.FullName.Substring($CanonicalSource.Length).TrimStart("\", "/")
        $RootName = $Relative.Split(@("\", "/"), [StringSplitOptions]::RemoveEmptyEntries)[0]
        if ($ExcludedRoots -contains $RootName) { continue }
        Copy-MigrationFileVerified -Source $File.FullName -Target (Join-Path $Target $Relative) -Records $Records
    }
}

function Assert-MigrationCopies {
    param([Parameter(Mandatory = $true)]$Records)

    foreach ($Record in $Records) {
        $Target = Get-Item -LiteralPath $Record.target -Force -ErrorAction Stop
        if ($Target.Length -ne $Record.bytes -or (Get-MigrationSha256 -Path $Target.FullName) -ne $Record.sha256) {
            throw "MIGRATION_COPY_VERIFICATION_FAILED"
        }
    }
}

function Assert-MigrationInventoryUnchanged {
    param(
        [Parameter(Mandatory = $true)]$Before,
        [Parameter(Mandatory = $true)]$After
    )

    if ($Before.file_count -ne $After.file_count -or $Before.total_bytes -ne $After.total_bytes) {
        throw "MIGRATION_SOURCE_CHANGED"
    }
    foreach ($Key in $Before.file_digests.Keys) {
        if (-not $After.file_digests.Contains($Key) -or $Before.file_digests[$Key] -ne $After.file_digests[$Key]) {
            throw "MIGRATION_SOURCE_CHANGED"
        }
    }
}

function New-MigrationJunction {
    param(
        [Parameter(Mandatory = $true)][string]$Link,
        [Parameter(Mandatory = $true)][string]$Target
    )

    if (Test-Path -LiteralPath $Link) { throw "MIGRATION_LAYOUT_INVALID" }
    $TargetItem = Get-Item -LiteralPath $Target -Force -ErrorAction Stop
    if (-not $TargetItem.PSIsContainer) { throw "MIGRATION_LAYOUT_INVALID" }
    $Parent = Split-Path -Parent $Link
    if (-not (Test-Path -LiteralPath $Parent)) {
        New-Item -ItemType Directory -Path $Parent -Force | Out-Null
    }
    New-Item -ItemType Junction -Path $Link -Target $TargetItem.FullName -ErrorAction Stop | Out-Null
    $LinkItem = Get-Item -LiteralPath $Link -Force -ErrorAction Stop
    if (-not ($LinkItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw "MIGRATION_LAYOUT_INVALID" }
    $ActualTarget = $LinkItem.Target
    if ($ActualTarget -is [array]) { $ActualTarget = $ActualTarget[0] }
    $ActualTarget = [IO.Path]::GetFullPath([string]$ActualTarget).TrimEnd("\")
    if (-not $ActualTarget.Equals($TargetItem.FullName.TrimEnd("\"), [StringComparison]::OrdinalIgnoreCase)) {
        throw "MIGRATION_LAYOUT_INVALID"
    }
}

function New-FirstMigrationRelease {
    param(
        [Parameter(Mandatory = $true)][string]$SourceRoot,
        [Parameter(Mandatory = $true)][string]$TargetRoot,
        [Parameter(Mandatory = $true)][string]$Commit,
        [Parameter(Mandatory = $true)]$Records
    )

    if ($Commit -notmatch "^[0-9a-f]{40}$") { throw "MIGRATION_COMMIT_INVALID" }
    if (Test-Path -LiteralPath $TargetRoot) { throw "MIGRATION_TARGET_EXISTS" }
    New-Item -ItemType Directory -Path $TargetRoot | Out-Null
    foreach ($Relative in @("config", "shared", "releases", "updater", "tools", "shared\models", "shared\cache", "shared\partial", "shared\input", "shared\output", "shared\logs")) {
        New-Item -ItemType Directory -Path (Join-Path $TargetRoot $Relative) -Force | Out-Null
    }
    $Release = Join-Path (Join-Path $TargetRoot "releases") $Commit
    New-Item -ItemType Directory -Path $Release | Out-Null

    $IsProductionSource = $SourceRoot.Equals($script:MigrationSourceRoot, [StringComparison]::OrdinalIgnoreCase)
    if ($IsProductionSource) {
        Copy-MigrationTreeVerified -Source $script:MigrationPayloadRoot -Target (Join-Path $Release "worker\windows") -Records $Records
    } else {
        Copy-MigrationTreeVerified -Source (Join-Path $SourceRoot "app") -Target (Join-Path $Release "worker\windows") -Records $Records
    }
    Copy-MigrationTreeVerified -Source (Join-Path $SourceRoot "runtime\python") -Target (Join-Path $Release ".venv") -Records $Records
    Copy-MigrationTreeVerified -Source (Join-Path $SourceRoot "runtime\ComfyUI") -Target (Join-Path $Release "ComfyUI") -Records $Records -ExcludedRoots @("models", "input", "output")
    Copy-MigrationTreeVerified -Source (Join-Path $SourceRoot "config") -Target (Join-Path $TargetRoot "config") -Records $Records
    Copy-MigrationTreeVerified -Source (Join-Path $SourceRoot "shared") -Target (Join-Path $TargetRoot "shared") -Records $Records
    Copy-MigrationTreeVerified -Source (Join-Path $SourceRoot "runtime\ComfyUI\models") -Target (Join-Path $TargetRoot "shared\models") -Records $Records
    Copy-MigrationTreeVerified -Source (Join-Path $SourceRoot "runtime\ComfyUI\input") -Target (Join-Path $TargetRoot "shared\input") -Records $Records
    Copy-MigrationTreeVerified -Source (Join-Path $SourceRoot "runtime\ComfyUI\output") -Target (Join-Path $TargetRoot "shared\output") -Records $Records
    Copy-MigrationTreeVerified -Source (Join-Path $SourceRoot "runtime\logs") -Target (Join-Path $TargetRoot "shared\logs") -Records $Records
    $UpdaterSource = if ($IsProductionSource) { Join-Path $script:MigrationPayloadRoot "updater" } else { Join-Path $SourceRoot "updater" }
    Copy-MigrationTreeVerified -Source $UpdaterSource -Target (Join-Path $TargetRoot "updater") -Records $Records
    Copy-MigrationTreeVerified -Source (Join-Path $SourceRoot "updater-runtime") -Target (Join-Path $TargetRoot "updater-runtime") -Records $Records

    foreach ($Name in @(".ai-drawing-worker-owned", "Start-Worker.cmd", "Start-Worker.ps1", "Uninstall-Worker.cmd", "Migrate-Worker.ps1", "UpdaterBootstrap.ps1", "WorkerSecurity.ps1", "worker-manifest.json", "requirements.txt", "Restart-Worker.ps1", "Restart-Worker.cmd", "Wait-Restart-Result.ps1")) {
        $SurfaceRoot = if ($IsProductionSource -and $Name -ne ".ai-drawing-worker-owned") { $script:MigrationPayloadRoot } else { $SourceRoot }
        $Source = Join-Path $SurfaceRoot $Name
        if (Test-Path -LiteralPath $Source -PathType Leaf) {
            Copy-MigrationFileVerified -Source $Source -Target (Join-Path $TargetRoot $Name) -Records $Records
            if ($Name -in @("worker-manifest.json", "requirements.txt")) {
                Copy-MigrationFileVerified -Source $Source -Target (Join-Path (Join-Path $Release "worker\windows") $Name) -Records $Records
            }
        }
    }

    $Python = Get-ChildItem -LiteralPath (Join-Path $Release ".venv") -Filter python.exe -File -Recurse | Select-Object -First 1
    if (-not $Python) { throw "MIGRATION_RUNTIME_INVALID" }
    $PythonRelative = $Python.FullName.Substring($Release.Length).TrimStart("\", "/")
    [IO.File]::WriteAllText((Join-Path $Release "python-path.txt"), $PythonRelative + "`n", $script:Utf8NoBom)
    [IO.File]::WriteAllText((Join-Path $Release "source-commit.txt"), $Commit + "`n", $script:Utf8NoBom)
    [IO.File]::WriteAllText((Join-Path $Release ".managed-release.json"), ('{"commit":"' + $Commit + '","schema":1}' + "`n"), $script:Utf8NoBom)
    [IO.File]::WriteAllText((Join-Path $Release "release-state.json"), ('{"commit":"' + $Commit + '","status":"ready"}' + "`n"), $script:Utf8NoBom)

    return $Release
}

function New-MigrationReleaseLinks {
    param(
        [Parameter(Mandatory = $true)][string]$Release,
        [Parameter(Mandatory = $true)][string]$TargetRoot
    )

    foreach ($Pair in @(
        @((Join-Path $Release "ComfyUI\models"), (Join-Path $TargetRoot "shared\models")),
        @((Join-Path $Release "ComfyUI\input"), (Join-Path $TargetRoot "shared\input")),
        @((Join-Path $Release "ComfyUI\output"), (Join-Path $TargetRoot "shared\output")),
        @((Join-Path $Release ".cache"), (Join-Path $TargetRoot "shared\cache")),
        @((Join-Path $Release "cache\.partial"), (Join-Path $TargetRoot "shared\partial"))
    )) {
        New-MigrationJunction -Link $Pair[0] -Target $Pair[1]
    }
    New-MigrationJunction -Link (Join-Path $TargetRoot "current") -Target $Release
}

function Assert-MigrationHealth {
    param(
        [Parameter(Mandatory = $true)]$Evidence,
        [Parameter(Mandatory = $true)][string]$ExpectedCommit,
        [Parameter(Mandatory = $true)][string]$ExpectedTokenHash
    )

    if (
        $null -eq $Evidence -or
        $Evidence.cuda_available -ne $true -or
        -not [string]$Evidence.gpu_name -or
        $Evidence.status_ok -ne $true -or
        $Evidence.resource_plan_ok -ne $true -or
        $Evidence.preflight_ok -ne $true -or
        $Evidence.object_info_ok -ne $true -or
        [string]$Evidence.source_commit -ne $ExpectedCommit -or
        [string]$Evidence.token_sha256 -ne $ExpectedTokenHash
    ) {
        throw "MIGRATION_HEALTH_FAILED"
    }
}

function Invoke-WorkerMigrationTransaction {
    param(
        [Parameter(Mandatory = $true)][string]$SourceRoot,
        [Parameter(Mandatory = $true)][string]$TargetRoot,
        [Parameter(Mandatory = $true)][string]$EnvironmentPath,
        [Parameter(Mandatory = $true)][string]$Commit,
        [Parameter(Mandatory = $true)][hashtable]$Adapter,
        [Parameter(Mandatory = $true)][int64]$ReserveBytes
    )

    $RequiredAdapterKeys = @("GetFreeBytes", "ProtectTarget", "CaptureTaskActions", "SwitchTaskActions", "RestoreTaskActions", "StopWorker", "StartWorker", "ValidateWorker")
    foreach ($Key in $RequiredAdapterKeys) {
        if (-not $Adapter.ContainsKey($Key) -or $Adapter[$Key] -isnot [scriptblock]) {
            throw "MIGRATION_ADAPTER_INVALID"
        }
    }
    $Source = (Get-Item -LiteralPath $SourceRoot -Force -ErrorAction Stop).FullName.TrimEnd("\")
    $Target = [IO.Path]::GetFullPath($TargetRoot).TrimEnd("\")
    if ($Source.Equals($Target, [StringComparison]::OrdinalIgnoreCase)) { throw "MIGRATION_PATH_INVALID" }
    $ConfigPath = Join-Path $Source "config\worker.json"
    $Before = Get-MigrationInventory -Root $Source -ConfigPath $ConfigPath
    $Available = [int64](& $Adapter["GetFreeBytes"] $Target)
    Assert-MigrationCapacity -SourceBytes $Before.total_bytes -AvailableBytes $Available -ReserveBytes $ReserveBytes
    $OriginalTasks = @(& $Adapter["CaptureTaskActions"])
    $Records = New-Object "System.Collections.Generic.List[object]"
    $Switched = $false
    $BackedUp = $false
    $BackupRoot = $null
    $Stage = "copying"

    try {
        $Release = New-FirstMigrationRelease -SourceRoot $Source -TargetRoot $Target -Commit $Commit -Records $Records
        $Stage = "protecting"
        & $Adapter["ProtectTarget"] $Target
        $Stage = "verifying-copy"
        Assert-MigrationCopies -Records $Records
        $Stage = "verifying-source"
        $AfterCopy = Get-MigrationInventory -Root $Source -ConfigPath $ConfigPath
        Assert-MigrationInventoryUnchanged -Before $Before -After $AfterCopy
        New-MigrationReleaseLinks -Release $Release -TargetRoot $Target
        $Stage = "validating-staged"
        $Staged = & $Adapter["ValidateWorker"] $Target "staged" $Commit $Before.token_sha256
        Assert-MigrationHealth -Evidence $Staged -ExpectedCommit $Commit -ExpectedTokenHash $Before.token_sha256

        Write-FixedMigrationWorkerRoot -Path $EnvironmentPath -WorkerRoot $Target
        & $Adapter["SwitchTaskActions"] $Target
        $Switched = $true
        & $Adapter["StopWorker"] $Source
        & $Adapter["StartWorker"] $Target
        $Production = & $Adapter["ValidateWorker"] $Target "production-before-backup" $Commit $Before.token_sha256
        Assert-MigrationHealth -Evidence $Production -ExpectedCommit $Commit -ExpectedTokenHash $Before.token_sha256

        & $Adapter["StopWorker"] $Target
        $BackupRoot = $Source + ".backup-" + (Get-Date -Format "yyyyMMdd-HHmmss")
        if (Test-Path -LiteralPath $BackupRoot) { throw "MIGRATION_BACKUP_EXISTS" }
        [IO.Directory]::Move($Source, $BackupRoot)
        $BackedUp = $true
        & $Adapter["StartWorker"] $Target
        $AfterBackup = & $Adapter["ValidateWorker"] $Target "production-after-backup" $Commit $Before.token_sha256
        Assert-MigrationHealth -Evidence $AfterBackup -ExpectedCommit $Commit -ExpectedTokenHash $Before.token_sha256
        return [pscustomobject]@{ status = "ready"; backup_root = $BackupRoot; release_root = $Release }
    } catch {
        $Code = if ([string]$_.Exception.Message -match "^MIGRATION_[A-Z_]+$") { [string]$_.Exception.Message } else { "MIGRATION_FAILED" }
        if (-not $Switched -and -not $BackedUp) {
            return [pscustomobject]@{ status = "failed_before_switch"; error_code = $Code; failed_stage = $Stage; backup_root = $null }
        }
        try {
            & $Adapter["StopWorker"] $Target
            if ($BackedUp -and -not (Test-Path -LiteralPath $Source)) {
                [IO.Directory]::Move($BackupRoot, $Source)
                $BackedUp = $false
            }
            & $Adapter["RestoreTaskActions"] $OriginalTasks
            Write-FixedMigrationWorkerRoot -Path $EnvironmentPath -WorkerRoot $Source
            & $Adapter["StartWorker"] $Source
            return [pscustomobject]@{ status = "rolled_back"; error_code = $Code; backup_root = $null }
        } catch {
            return [pscustomobject]@{ status = "recovery_required"; error_code = "MIGRATION_RECOVERY_REQUIRED"; backup_root = $BackupRoot }
        }
    }
}

function Get-ProductionMigrationContext {
    $Environment = Read-FixedMigrationEnvironment -Path $script:MigrationEnvironmentPath
    $Target = [IO.Path]::GetFullPath([string]$Environment.AI_DRAWING_WORKER_ROOT)
    if ([IO.Path]::GetPathRoot($Target) -ne "D:\") { throw "MIGRATION_CONFIG_INVALID" }
    return [pscustomobject]@{
        source_root = $script:MigrationSourceRoot
        target_root = $Target
        environment_path = $script:MigrationEnvironmentPath
        project_root = [string]$Environment.AI_DRAWING_PROJECT_ROOT
    }
}

function Get-ProductionMigrationAdapter {
    . (Join-Path $PSScriptRoot "WorkerSecurity.ps1")
    $ProgramDataRoot = $script:MigrationProgramDataRoot
    $WorkerTask = "AI-Drawing NVIDIA Worker"
    $UpdaterTask = "AI-Drawing Worker Updater"
    $RestartTask = "AI-Drawing NVIDIA Worker Restart"
    return @{
        GetFreeBytes = { param($Root) ([IO.DriveInfo]::new([IO.Path]::GetPathRoot($Root))).AvailableFreeSpace }.GetNewClosure()
        ProtectTarget = { param($Root) Protect-UpdaterTree -Path $Root }.GetNewClosure()
        CaptureTaskActions = {
            $Captured = @()
            foreach ($Name in @($WorkerTask, $UpdaterTask, $RestartTask)) {
                $Task = Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
                if ($Task) { $Captured += [pscustomobject]@{ name = $Name; actions = @($Task.Actions) } }
            }
            if (($Captured.name -notcontains $WorkerTask) -or ($Captured.name -notcontains $UpdaterTask)) { throw "MIGRATION_TASK_INVALID" }
            return $Captured
        }.GetNewClosure()
        SwitchTaskActions = {
            param($Root)
            $PowerShell = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
            $WorkerAction = New-ScheduledTaskAction -Execute $PowerShell -Argument ("-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"" + (Join-Path $Root "Start-Worker.ps1") + "`"")
            Set-ScheduledTask -TaskName $WorkerTask -Action $WorkerAction | Out-Null
            $UpdaterAction = New-ScheduledTaskAction -Execute $PowerShell -Argument ("-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"" + (Join-Path $ProgramDataRoot "UpdaterBootstrap.ps1") + "`"")
            Set-ScheduledTask -TaskName $UpdaterTask -Action $UpdaterAction | Out-Null
            if (Get-ScheduledTask -TaskName $RestartTask -ErrorAction SilentlyContinue) {
                $RestartAction = New-ScheduledTaskAction -Execute $PowerShell -Argument ("-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"" + (Join-Path $Root "Restart-Worker.ps1") + "`"")
                Set-ScheduledTask -TaskName $RestartTask -Action $RestartAction | Out-Null
            }
        }.GetNewClosure()
        RestoreTaskActions = {
            param($Actions)
            foreach ($Record in @($Actions)) { Set-ScheduledTask -TaskName $Record.name -Action $Record.actions | Out-Null }
        }.GetNewClosure()
        StopWorker = {
            param($Root)
            $Task = Get-ScheduledTask -TaskName $WorkerTask -ErrorAction Stop
            if ($Task.State -eq "Running") { Stop-ScheduledTask -TaskName $WorkerTask -ErrorAction Stop }
        }.GetNewClosure()
        StartWorker = { param($Root) Start-ScheduledTask -TaskName $WorkerTask -ErrorAction Stop }.GetNewClosure()
        ValidateWorker = {
            param($Root, $Mode, $ExpectedCommit, $ExpectedTokenHash)
            try {
                $Release = (Get-Item -LiteralPath (Join-Path $Root "current") -Force -ErrorAction Stop).Target
                if ($Release -is [array]) { $Release = $Release[0] }
                $Release = [IO.Path]::GetFullPath([string]$Release)
                $ConfigPath = Join-Path $Root "config\worker.json"
                $Config = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json -ErrorAction Stop
                $Token = [string]$Config.token
                $TokenHash = Get-MigrationStringSha256 -Value $Token
                if ($Mode -eq "staged") {
                    $Ready = (Test-Path -LiteralPath (Join-Path $Release "worker\windows\worker.py") -PathType Leaf) -and
                        (Test-Path -LiteralPath (Join-Path $Release "ComfyUI\main.py") -PathType Leaf) -and
                        ((Get-Content -LiteralPath (Join-Path $Release "source-commit.txt") -Raw).Trim() -eq $ExpectedCommit)
                    return [pscustomobject]@{ cuda_available = $Ready; gpu_name = $(if ($Ready) { "staged CUDA runtime" } else { "" }); status_ok = $Ready; resource_plan_ok = $Ready; preflight_ok = $Ready; object_info_ok = $Ready; source_commit = $ExpectedCommit; token_sha256 = $TokenHash }
                }
                $Headers = @{ Authorization = "Bearer $Token" }
                $System = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8188/system_stats" -TimeoutSec 10
                $Objects = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8188/object_info" -TimeoutSec 10
                $Status = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8791/v1/worker/status" -Headers $Headers -TimeoutSec 10
                $Plan = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8791/v1/resources/plan" -Headers $Headers -ContentType "application/json" -Body '{"resources":[]}' -TimeoutSec 10
                $Preflight = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8791/v1/workflows/preflight" -Headers $Headers -ContentType "application/json" -Body '{"node_types":["CheckpointLoaderSimple","CLIPTextEncode","EmptyLatentImage","KSampler","VAEDecode","SaveImage"]}' -TimeoutSec 10
                $Cuda = @($System.devices | Where-Object { [string]$_.type -eq "cuda" }) | Select-Object -First 1
                $RequiredNodes = @("CheckpointLoaderSimple", "CLIPTextEncode", "EmptyLatentImage", "KSampler", "VAEDecode", "SaveImage")
                $ObjectNames = @($Objects.PSObject.Properties.Name)
                $ObjectsReady = @($RequiredNodes | Where-Object { $ObjectNames -notcontains $_ }).Count -eq 0
                return [pscustomobject]@{ cuda_available = ($null -ne $Cuda); gpu_name = [string]$Cuda.name; status_ok = ($Status.comfyui -eq "ready" -and $Status.source_commit -eq $ExpectedCommit); resource_plan_ok = (@($Plan.missing).Count -eq 0); preflight_ok = ($Preflight.ready -eq $true -and @($Preflight.missing_node_types).Count -eq 0); object_info_ok = $ObjectsReady; source_commit = [string]$Status.source_commit; token_sha256 = $TokenHash }
            } catch {
                throw "MIGRATION_HEALTH_FAILED"
            }
        }.GetNewClosure()
    }
}

function Invoke-MigrationMain {
    $Context = Get-ProductionMigrationContext
    if (-not (Test-Path -LiteralPath $Context.source_root -PathType Container)) { throw "MIGRATION_SOURCE_INVALID" }
    $Commit = (& git.exe -C $Context.project_root rev-parse HEAD 2>$null).Trim()
    if ($LASTEXITCODE -ne 0 -or $Commit -notmatch "^[0-9a-f]{40}$") { throw "MIGRATION_COMMIT_INVALID" }
    $Adapter = Get-ProductionMigrationAdapter
    $Result = Invoke-WorkerMigrationTransaction -SourceRoot $Context.source_root -TargetRoot $Context.target_root -EnvironmentPath $Context.environment_path -Commit $Commit -Adapter $Adapter -ReserveBytes 20GB
    if ($Result.status -ne "ready") { throw [string]$Result.error_code }
    return $Result
}

if ($MyInvocation.InvocationName -ne ".") {
    Invoke-MigrationMain | ConvertTo-Json -Compress
}
