$ErrorActionPreference = "Stop"

$script:MigrationSourceRoot = "C:\AI-Drawing-Worker"
$script:MigrationPayloadRoot = $PSScriptRoot
$script:MigrationProgramDataRoot = Join-Path $env:ProgramData "AI-Drawing-Worker"
$script:MigrationEnvironmentPath = Join-Path $script:MigrationProgramDataRoot "updater.env"
$script:MigrationTargetEnvironmentPath = Join-Path $script:MigrationProgramDataRoot "migration.env"
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

function Assert-MigrationTargetPathNoFollow {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Path
    )

    $FullRoot = [IO.Path]::GetFullPath($Root).TrimEnd("\")
    $FullPath = [IO.Path]::GetFullPath($Path).TrimEnd("\")
    if (
        -not $FullPath.Equals($FullRoot, [StringComparison]::OrdinalIgnoreCase) -and
        -not $FullPath.StartsWith($FullRoot + "\", [StringComparison]::OrdinalIgnoreCase)
    ) {
        throw "MIGRATION_PATH_INVALID"
    }
    $DriveRoot = [IO.Path]::GetPathRoot($FullPath)
    $Cursor = $DriveRoot
    $Relative = $FullPath.Substring($DriveRoot.Length)
    foreach ($Part in @($Relative.Split(@("\", "/"), [StringSplitOptions]::RemoveEmptyEntries))) {
        $Cursor = Join-Path $Cursor $Part
        if (-not (Test-Path -LiteralPath $Cursor)) { break }
        $Item = Get-Item -LiteralPath $Cursor -Force -ErrorAction Stop
        if (($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "MIGRATION_REPARSE_POINT"
        }
    }
}

function Assert-MigrationTargetTreeNoFollow {
    param([Parameter(Mandatory = $true)][string]$Root)

    Assert-MigrationTargetPathNoFollow -Root $Root -Path $Root
    if (Test-Path -LiteralPath $Root -PathType Container) {
        Get-MigrationTreeNoFollow -Root $Root | Out-Null
    }
}

function New-MigrationDirectorySafe {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Path
    )

    Assert-MigrationTargetPathNoFollow -Root $Root -Path $Path
    if (-not (Test-Path -LiteralPath $Path)) {
        [IO.Directory]::CreateDirectory($Path) | Out-Null
    }
    $Item = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    if (-not $Item.PSIsContainer -or ($Item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw "MIGRATION_REPARSE_POINT"
    }
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

function Install-FixedMigrationEnvironment {
    param([Parameter(Mandatory = $true)][string]$ProgramDataRoot)

    $Root = Get-Item -LiteralPath $ProgramDataRoot -Force -ErrorAction Stop
    if (-not $Root.PSIsContainer -or ($Root.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw "MIGRATION_CONFIG_INVALID"
    }
    $Path = Join-Path $Root.FullName "migration.env"
    [IO.File]::WriteAllText(
        $Path,
        "AI_DRAWING_WORKER_MIGRATION_TARGET=D:\code\AI-Drawing-Worker`r`n",
        $script:Utf8NoBom
    )
}

function Read-FixedMigrationTargetEnvironment {
    param([Parameter(Mandatory = $true)][string]$Path)

    try {
        $Lines = @(Get-Content -LiteralPath $Path -Encoding UTF8 -ErrorAction Stop | Where-Object { $_ })
        if ($Lines.Count -ne 1) { throw "invalid" }
        $Prefix = "AI_DRAWING_WORKER_MIGRATION_TARGET="
        if (-not $Lines[0].StartsWith($Prefix, [StringComparison]::Ordinal)) { throw "invalid" }
        $Target = $Lines[0].Substring($Prefix.Length)
        if (-not $Target) { throw "invalid" }
        return $Target
    } catch {
        throw "MIGRATION_CONFIG_INVALID"
    }
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
        [Parameter(Mandatory = $true)]$Records,
        [Parameter(Mandatory = $true)][string]$TargetRoot
    )

    $Parent = Split-Path -Parent $Target
    New-MigrationDirectorySafe -Root $TargetRoot -Path $Parent
    Assert-MigrationTargetPathNoFollow -Root $TargetRoot -Path $Target
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
        [Parameter(Mandatory = $true)][string]$TargetRoot,
        [string[]]$ExcludedRoots = @()
    )

    if (-not (Test-Path -LiteralPath $Source -PathType Container)) { return }
    $CanonicalSource = (Get-Item -LiteralPath $Source -Force).FullName.TrimEnd("\")
    New-MigrationDirectorySafe -Root $TargetRoot -Path $Target
    foreach ($File in @(Get-MigrationTreeNoFollow -Root $CanonicalSource)) {
        $Relative = $File.FullName.Substring($CanonicalSource.Length).TrimStart("\", "/")
        $RootName = $Relative.Split(@("\", "/"), [StringSplitOptions]::RemoveEmptyEntries)[0]
        if ($ExcludedRoots -contains $RootName) { continue }
        Copy-MigrationFileVerified -Source $File.FullName -Target (Join-Path $Target $Relative) -Records $Records -TargetRoot $TargetRoot
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
        [Parameter(Mandatory = $true)][string]$Target,
        [Parameter(Mandatory = $true)][string]$Root
    )

    Assert-MigrationTargetPathNoFollow -Root $Root -Path $Target
    if (Test-Path -LiteralPath $Link) {
        # A prior interrupted bootstrap may have already created this exact
        # managed junction. Validate its parent without following the link,
        # then accept only the expected target so reruns are idempotent.
        Assert-MigrationTargetPathNoFollow -Root $Root -Path (Split-Path -Parent $Link)
        $Existing = Get-Item -LiteralPath $Link -Force -ErrorAction Stop
        if (-not ($Existing.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw "MIGRATION_LAYOUT_INVALID"
        }
        $ExistingTarget = $Existing.Target
        if ($ExistingTarget -is [array]) { $ExistingTarget = $ExistingTarget[0] }
        if (-not [IO.Path]::GetFullPath([string]$ExistingTarget).TrimEnd("\").Equals(
            (Get-Item -LiteralPath $Target -Force -ErrorAction Stop).FullName.TrimEnd("\"),
            [StringComparison]::OrdinalIgnoreCase
        )) { throw "MIGRATION_LAYOUT_INVALID" }
        return
    }
    Assert-MigrationTargetPathNoFollow -Root $Root -Path $Link
    $TargetItem = Get-Item -LiteralPath $Target -Force -ErrorAction Stop
    if (-not $TargetItem.PSIsContainer) { throw "MIGRATION_LAYOUT_INVALID" }
    $Parent = Split-Path -Parent $Link
    New-MigrationDirectorySafe -Root $Root -Path $Parent
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
    if (-not (Test-Path -LiteralPath $TargetRoot -PathType Container)) { throw "MIGRATION_TARGET_INVALID" }
    $Release = Join-Path (Join-Path $TargetRoot "releases") $Commit

    # A crash after creating release-local shared junctions but before current
    # is published must be safely retryable. Remove only known links whose
    # targets exactly match this managed root; unknown reparse points remain a
    # hard failure in the tree-wide no-follow check below.
    foreach ($Pair in @(
        @((Join-Path $Release "ComfyUI\models"), (Join-Path $TargetRoot "shared\models")),
        @((Join-Path $Release "ComfyUI\input"), (Join-Path $TargetRoot "shared\input")),
        @((Join-Path $Release "ComfyUI\output"), (Join-Path $TargetRoot "shared\output")),
        @((Join-Path $Release ".cache"), (Join-Path $TargetRoot "shared\cache")),
        @((Join-Path $Release "cache\.partial"), (Join-Path $TargetRoot "shared\partial"))
    )) {
        $Link = $Pair[0]
        $ExpectedTarget = $Pair[1]
        if (Test-Path -LiteralPath $Link) {
            $Item = Get-Item -LiteralPath $Link -Force -ErrorAction Stop
            if (-not ($Item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { continue }
            $ActualTarget = $Item.Target
            if ($ActualTarget -is [array]) { $ActualTarget = $ActualTarget[0] }
            if (-not [IO.Path]::GetFullPath([string]$ActualTarget).TrimEnd("\").Equals(
                [IO.Path]::GetFullPath($ExpectedTarget).TrimEnd("\"),
                [StringComparison]::OrdinalIgnoreCase
            )) { throw "MIGRATION_LAYOUT_INVALID" }
            Remove-Item -LiteralPath $Link -Force -ErrorAction Stop
        }
    }
    Assert-MigrationTargetTreeNoFollow -Root $TargetRoot
    foreach ($Relative in @("config", "shared", "releases", "updater", "tools", "shared\models", "shared\cache", "shared\partial", "shared\input", "shared\output", "shared\logs")) {
        New-MigrationDirectorySafe -Root $TargetRoot -Path (Join-Path $TargetRoot $Relative)
    }
    New-MigrationDirectorySafe -Root $TargetRoot -Path $Release

    $IsProductionSource = $SourceRoot.Equals($script:MigrationSourceRoot, [StringComparison]::OrdinalIgnoreCase)
    if ($IsProductionSource) {
        Copy-MigrationTreeVerified -Source $script:MigrationPayloadRoot -Target (Join-Path $Release "worker\windows") -Records $Records -TargetRoot $TargetRoot
    } else {
        Copy-MigrationTreeVerified -Source (Join-Path $SourceRoot "app") -Target (Join-Path $Release "worker\windows") -Records $Records -TargetRoot $TargetRoot
    }
    Copy-MigrationTreeVerified -Source (Join-Path $SourceRoot "runtime\python") -Target (Join-Path $Release ".venv") -Records $Records -TargetRoot $TargetRoot
    Copy-MigrationTreeVerified -Source (Join-Path $SourceRoot "runtime\ComfyUI") -Target (Join-Path $Release "ComfyUI") -Records $Records -TargetRoot $TargetRoot -ExcludedRoots @("models", "input", "output")
    Copy-MigrationTreeVerified -Source (Join-Path $SourceRoot "config") -Target (Join-Path $TargetRoot "config") -Records $Records -TargetRoot $TargetRoot
    Copy-MigrationTreeVerified -Source (Join-Path $SourceRoot "shared") -Target (Join-Path $TargetRoot "shared") -Records $Records -TargetRoot $TargetRoot
    Copy-MigrationTreeVerified -Source (Join-Path $SourceRoot "runtime\ComfyUI\models") -Target (Join-Path $TargetRoot "shared\models") -Records $Records -TargetRoot $TargetRoot
    Copy-MigrationTreeVerified -Source (Join-Path $SourceRoot "runtime\ComfyUI\input") -Target (Join-Path $TargetRoot "shared\input") -Records $Records -TargetRoot $TargetRoot
    Copy-MigrationTreeVerified -Source (Join-Path $SourceRoot "runtime\ComfyUI\output") -Target (Join-Path $TargetRoot "shared\output") -Records $Records -TargetRoot $TargetRoot
    Copy-MigrationTreeVerified -Source (Join-Path $SourceRoot "runtime\logs") -Target (Join-Path $TargetRoot "shared\logs") -Records $Records -TargetRoot $TargetRoot
    $UpdaterSource = if ($IsProductionSource) { Join-Path $script:MigrationPayloadRoot "updater" } else { Join-Path $SourceRoot "updater" }
    Copy-MigrationTreeVerified -Source $UpdaterSource -Target (Join-Path $TargetRoot "updater") -Records $Records -TargetRoot $TargetRoot
    Copy-MigrationTreeVerified -Source (Join-Path $SourceRoot "updater-runtime") -Target (Join-Path $TargetRoot "updater-runtime") -Records $Records -TargetRoot $TargetRoot

    foreach ($Name in @(".ai-drawing-worker-owned", "Start-Worker.cmd", "Start-Worker.ps1", "WorkerPaths.ps1", "Uninstall-Worker.cmd", "Migrate-Worker.ps1", "UpdaterBootstrap.ps1", "WorkerSecurity.ps1", "worker-manifest.json", "requirements.txt", "Restart-Worker.ps1", "Restart-Worker.cmd", "Wait-Restart-Result.ps1")) {
        $SurfaceRoot = if ($IsProductionSource -and $Name -ne ".ai-drawing-worker-owned") { $script:MigrationPayloadRoot } else { $SourceRoot }
        $Source = Join-Path $SurfaceRoot $Name
        if (Test-Path -LiteralPath $Source -PathType Leaf) {
            Copy-MigrationFileVerified -Source $Source -Target (Join-Path $TargetRoot $Name) -Records $Records -TargetRoot $TargetRoot
            if ($Name -in @("worker-manifest.json", "requirements.txt")) {
                Copy-MigrationFileVerified -Source $Source -Target (Join-Path (Join-Path $Release "worker\windows") $Name) -Records $Records -TargetRoot $TargetRoot
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
        New-MigrationJunction -Link $Pair[0] -Target $Pair[1] -Root $TargetRoot
    }
    New-MigrationJunction -Link (Join-Path $TargetRoot "current") -Target $Release -Root $TargetRoot
}

function Initialize-ManagedWorkerLayout {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Commit
    )

    $CanonicalRoot = (Get-Item -LiteralPath $Root -Force -ErrorAction Stop).FullName.TrimEnd("\")
    $Current = Join-Path $CanonicalRoot "current"
    $Release = Join-Path (Join-Path $CanonicalRoot "releases") $Commit
    $HadCurrent = Test-Path -LiteralPath $Current
    $Records = New-Object "System.Collections.Generic.List[object]"
    try {
        if (-not $HadCurrent) {
            $Release = New-FirstMigrationRelease -SourceRoot $CanonicalRoot -TargetRoot $CanonicalRoot -Commit $Commit -Records $Records
            Assert-MigrationCopies -Records $Records
            New-MigrationReleaseLinks -Release $Release -TargetRoot $CanonicalRoot
        }
        $CurrentItem = Get-Item -LiteralPath $Current -Force -ErrorAction Stop
        if (-not ($CurrentItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw "MIGRATION_LAYOUT_INVALID" }
        $CurrentTarget = $CurrentItem.Target
        if ($CurrentTarget -is [array]) { $CurrentTarget = $CurrentTarget[0] }
        if (-not [IO.Path]::GetFullPath([string]$CurrentTarget).TrimEnd("\").Equals(
            [IO.Path]::GetFullPath($Release).TrimEnd("\"), [StringComparison]::OrdinalIgnoreCase
        )) { throw "MIGRATION_LAYOUT_INVALID" }
        foreach ($Required in @("source-commit.txt", ".managed-release.json", "worker\windows\worker.py", "ComfyUI\main.py")) {
            if (-not (Test-Path -LiteralPath (Join-Path $Release $Required) -PathType Leaf)) { throw "MIGRATION_LAYOUT_INVALID" }
        }
        return $Release
    } catch {
        # Never leave a newly-created, unverified current active.  The legacy
        # runtime remains intact and a rerun can resume exact verified copies.
        if (-not $HadCurrent -and (Test-Path -LiteralPath $Current)) {
            try {
                $Item = Get-Item -LiteralPath $Current -Force -ErrorAction Stop
                if ($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                    Remove-Item -LiteralPath $Current -Force -ErrorAction Stop
                }
            } catch { }
        }
        throw
    }
}

function Assert-MigrationHealth {
    param(
        [Parameter(Mandatory = $true)]$Evidence,
        [Parameter(Mandatory = $true)][string]$ExpectedCommit,
        [Parameter(Mandatory = $true)][string]$ExpectedTokenHash
    )

    if (-not (Test-MigrationHealth -Evidence $Evidence -ExpectedCommit $ExpectedCommit -ExpectedTokenHash $ExpectedTokenHash)) {
        throw "MIGRATION_HEALTH_FAILED"
    }
}

function Test-MigrationHealth {
    param(
        [Parameter(Mandatory = $true)]$Evidence,
        [Parameter(Mandatory = $true)][string]$ExpectedCommit,
        [Parameter(Mandatory = $true)][string]$ExpectedTokenHash
    )

    return -not (
        $null -eq $Evidence -or
        $Evidence.cuda_available -ne $true -or
        -not [string]$Evidence.gpu_name -or
        $Evidence.status_ok -ne $true -or
        $Evidence.resource_plan_ok -ne $true -or
        $Evidence.preflight_ok -ne $true -or
        $Evidence.object_info_ok -ne $true -or
        [string]$Evidence.source_commit -ne $ExpectedCommit -or
        [string]$Evidence.token_sha256 -ne $ExpectedTokenHash
    )
}

function Wait-MigrationHealth {
    param(
        [Parameter(Mandatory = $true)][hashtable]$Adapter,
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Mode,
        [Parameter(Mandatory = $true)][string]$ExpectedCommit,
        [Parameter(Mandatory = $true)][string]$ExpectedTokenHash
    )

    [int64]$DeadlineMilliseconds = [int64](& $Adapter["GetMonotonicMilliseconds"]) + 120000
    while ($true) {
        [int64]$Now = [int64](& $Adapter["GetMonotonicMilliseconds"])
        [int64]$Remaining = $DeadlineMilliseconds - $Now
        if ($Remaining -le 0) { throw "MIGRATION_HEALTH_FAILED" }
        $CallTimeoutSeconds = [Math]::Max(1, [Math]::Min(10, [int][Math]::Ceiling($Remaining / 1000.0)))
        try {
            $Evidence = & $Adapter["ValidateWorker"] $Root $Mode $ExpectedCommit $ExpectedTokenHash $CallTimeoutSeconds
            if (Test-MigrationHealth -Evidence $Evidence -ExpectedCommit $ExpectedCommit -ExpectedTokenHash $ExpectedTokenHash) {
                return $Evidence
            }
        } catch {
            # Connection and incomplete-health failures are expected while the fixed task starts.
        }
        $Now = [int64](& $Adapter["GetMonotonicMilliseconds"])
        $Remaining = $DeadlineMilliseconds - $Now
        if ($Remaining -le 0) { throw "MIGRATION_HEALTH_FAILED" }
        $WaitMilliseconds = [int][Math]::Min(1000, $Remaining)
        & $Adapter["WaitForHealthRetry"] $WaitMilliseconds
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

    $RequiredAdapterKeys = @("GetSourceInventory", "GetFreeBytes", "InitializeTarget", "AssertSecureTarget", "GetMonotonicMilliseconds", "WaitForHealthRetry", "ProtectTarget", "CaptureSwitchState", "SwitchTaskActions", "RestoreSwitchState", "StopWorker", "StartWorker", "ValidateWorker")
    foreach ($Key in $RequiredAdapterKeys) {
        if (-not $Adapter.ContainsKey($Key) -or $Adapter[$Key] -isnot [scriptblock]) {
            throw "MIGRATION_ADAPTER_INVALID"
        }
    }
    $Source = (Get-Item -LiteralPath $SourceRoot -Force -ErrorAction Stop).FullName.TrimEnd("\")
    $Target = [IO.Path]::GetFullPath($TargetRoot).TrimEnd("\")
    if ($Source.Equals($Target, [StringComparison]::OrdinalIgnoreCase)) { throw "MIGRATION_PATH_INVALID" }
    Assert-MigrationTargetPathNoFollow -Root $Target -Path $Target
    $ConfigPath = Join-Path $Source "config\worker.json"
    $Records = New-Object "System.Collections.Generic.List[object]"
    $Before = $null
    $SwitchState = $null
    $SwitchAttempted = $false
    $Switched = $false
    $SourceStopped = $false
    $TargetStarted = $false
    $BackedUp = $false
    $BackupRoot = $null
    $Stage = "initializing-target"

    try {
        & $Adapter["InitializeTarget"] $Target
        Assert-MigrationTargetTreeNoFollow -Root $Target
        $Stage = "verifying-target-security"
        & $Adapter["AssertSecureTarget"] $Target
        $Stage = "inventorying-source"
        $Before = & $Adapter["GetSourceInventory"] $Source $ConfigPath
        if ($null -eq $Before) { throw "MIGRATION_INVENTORY_INVALID" }
        $Available = [int64](& $Adapter["GetFreeBytes"] $Target)
        Assert-MigrationCapacity -SourceBytes $Before.total_bytes -AvailableBytes $Available -ReserveBytes $ReserveBytes
        $Stage = "capturing-switch-state"
        $SwitchState = & $Adapter["CaptureSwitchState"] $EnvironmentPath
        if ($null -eq $SwitchState) { throw "MIGRATION_SWITCH_STATE_INVALID" }
        $Stage = "copying"
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
        Wait-MigrationHealth -Adapter $Adapter -Root $Target -Mode "staged" -ExpectedCommit $Commit -ExpectedTokenHash $Before.token_sha256 | Out-Null

        $SwitchAttempted = $true
        Write-FixedMigrationWorkerRoot -Path $EnvironmentPath -WorkerRoot $Target
        & $Adapter["SwitchTaskActions"] $Target
        $Switched = $true
        & $Adapter["StopWorker"] $Source
        $SourceStopped = $true
        & $Adapter["StartWorker"] $Target
        $TargetStarted = $true
        Wait-MigrationHealth -Adapter $Adapter -Root $Target -Mode "production-before-backup" -ExpectedCommit $Commit -ExpectedTokenHash $Before.token_sha256 | Out-Null

        & $Adapter["StopWorker"] $Target
        $BackupRoot = $Source + ".backup-" + (Get-Date -Format "yyyyMMdd-HHmmss")
        if (Test-Path -LiteralPath $BackupRoot) { throw "MIGRATION_BACKUP_EXISTS" }
        [IO.Directory]::Move($Source, $BackupRoot)
        $BackedUp = $true
        & $Adapter["StartWorker"] $Target
        Wait-MigrationHealth -Adapter $Adapter -Root $Target -Mode "production-after-backup" -ExpectedCommit $Commit -ExpectedTokenHash $Before.token_sha256 | Out-Null
        return [pscustomobject]@{ status = "ready"; backup_root = $BackupRoot; release_root = $Release }
    } catch {
        $Code = if ([string]$_.Exception.Message -match "^MIGRATION_[A-Z_]+$") { [string]$_.Exception.Message } else { "MIGRATION_FAILED" }
        if (-not $SwitchAttempted -and -not $BackedUp) {
            return [pscustomobject]@{ status = "failed_before_switch"; error_code = $Code; failed_stage = $Stage; backup_root = $null }
        }
        try {
            if ($TargetStarted) { & $Adapter["StopWorker"] $Target }
            if ($BackedUp -and -not (Test-Path -LiteralPath $Source)) {
                [IO.Directory]::Move($BackupRoot, $Source)
                $BackedUp = $false
            }
            & $Adapter["RestoreSwitchState"] $SwitchState
            if ($SourceStopped) { & $Adapter["StartWorker"] $Source }
            return [pscustomobject]@{ status = "rolled_back"; error_code = $Code; backup_root = $null }
        } catch {
            return [pscustomobject]@{ status = "recovery_required"; error_code = "MIGRATION_RECOVERY_REQUIRED"; backup_root = $BackupRoot }
        }
    }
}

function Get-ProductionMigrationContext {
    $Environment = Read-FixedMigrationEnvironment -Path $script:MigrationEnvironmentPath
    if (-not ([string]$Environment.AI_DRAWING_WORKER_ROOT).Equals($script:MigrationSourceRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "MIGRATION_CONFIG_INVALID"
    }
    $MigrationTarget = Read-FixedMigrationTargetEnvironment -Path $script:MigrationTargetEnvironmentPath
    $Target = [IO.Path]::GetFullPath([string]$MigrationTarget)
    if ([IO.Path]::GetPathRoot($Target) -ne "D:\") { throw "MIGRATION_CONFIG_INVALID" }
    return [pscustomobject]@{
        source_root = $script:MigrationSourceRoot
        target_root = $Target
        environment_path = $script:MigrationEnvironmentPath
        project_root = [string]$Environment.AI_DRAWING_PROJECT_ROOT
    }
}

function Initialize-ProductionMigrationPrerequisites {
    if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator
    )) {
        throw "MIGRATION_ADMIN_REQUIRED"
    }
    if (
        -not (Test-Path -LiteralPath (Join-Path $script:MigrationSourceRoot ".ai-drawing-worker-owned") -PathType Leaf) -or
        -not (Test-Path -LiteralPath (Join-Path $script:MigrationSourceRoot "config\worker.json") -PathType Leaf)
    ) {
        throw "MIGRATION_SOURCE_INVALID"
    }

    $ProjectRoot = (& git.exe -C $script:MigrationPayloadRoot rev-parse --show-toplevel 2>$null).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $ProjectRoot -or -not (Test-Path -LiteralPath (Join-Path $ProjectRoot ".git"))) {
        throw "MIGRATION_PROJECT_INVALID"
    }

    . (Join-Path $script:MigrationPayloadRoot "WorkerSecurity.ps1")
    if (Test-Path -LiteralPath $script:MigrationProgramDataRoot) {
        Assert-SecureUpdaterTree -Path $script:MigrationProgramDataRoot
    } else {
        New-SecureUpdaterDirectory -Path $script:MigrationProgramDataRoot
    }

    Copy-Item (Join-Path $script:MigrationPayloadRoot "UpdaterBootstrap.ps1") `
        (Join-Path $script:MigrationProgramDataRoot "UpdaterBootstrap.ps1") -Force
    $UpdaterEnvironment = @(
        "AI_DRAWING_PROJECT_ROOT=$ProjectRoot"
        "AI_DRAWING_WORKER_ROOT=$script:MigrationSourceRoot"
        "AI_DRAWING_WORKER_REMOTE=origin"
        "AI_DRAWING_WORKER_BRANCH=main"
    )
    [IO.File]::WriteAllText(
        $script:MigrationEnvironmentPath,
        (($UpdaterEnvironment -join [Environment]::NewLine) + [Environment]::NewLine),
        $script:Utf8NoBom
    )
    Install-FixedMigrationEnvironment -ProgramDataRoot $script:MigrationProgramDataRoot | Out-Null
    Protect-UpdaterTree -Path $script:MigrationProgramDataRoot

    $PowerShell = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
    $Action = New-ScheduledTaskAction -Execute $PowerShell `
        -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$script:MigrationProgramDataRoot\UpdaterBootstrap.ps1`""
    $Principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    $Settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2)
    Register-ScheduledTask -TaskName "AI-Drawing Worker Updater" -Action $Action `
        -Principal $Principal -Settings $Settings -Force | Out-Null
}

function Get-ProductionMigrationAdapter {
    . (Join-Path $PSScriptRoot "WorkerSecurity.ps1")
    $ProgramDataRoot = $script:MigrationProgramDataRoot
    $WorkerTask = "AI-Drawing NVIDIA Worker"
    $UpdaterTask = "AI-Drawing Worker Updater"
    $RestartTask = "AI-Drawing NVIDIA Worker Restart"
    return @{
        GetSourceInventory = {
            param($Root, $ConfigPath)
            Get-MigrationInventory -Root $Root -ConfigPath $ConfigPath
        }.GetNewClosure()
        GetFreeBytes = { param($Root) ([IO.DriveInfo]::new([IO.Path]::GetPathRoot($Root))).AvailableFreeSpace }.GetNewClosure()
        InitializeTarget = {
            param($Root)
            if (Test-Path -LiteralPath $Root) {
                Assert-ExistingWorkerRoot -Path $Root
            } else {
                New-SecureUpdaterDirectory -Path $Root
                $Marker = Join-Path $Root ".ai-drawing-worker-owned"
                [IO.File]::WriteAllText($Marker, "AI-Drawing NVIDIA Worker`n", $script:Utf8NoBom)
                Reset-SecureUpdaterChildAcl -Path $Marker
                Assert-ExistingWorkerRoot -Path $Root
            }
        }.GetNewClosure()
        AssertSecureTarget = {
            param($Root)
            try {
                Assert-SecureUpdaterTree -Path $Root
            } catch {
                throw "MIGRATION_TARGET_SECURITY_INVALID"
            }
        }.GetNewClosure()
        GetMonotonicMilliseconds = {
            [int64]([Diagnostics.Stopwatch]::GetTimestamp() * 1000 / [Diagnostics.Stopwatch]::Frequency)
        }.GetNewClosure()
        WaitForHealthRetry = { param($Milliseconds) Start-Sleep -Milliseconds $Milliseconds }.GetNewClosure()
        ProtectTarget = { param($Root) Protect-UpdaterTree -Path $Root }.GetNewClosure()
        CaptureSwitchState = {
            param($EnvironmentPath)
            $Captured = @()
            foreach ($Name in @($WorkerTask, $UpdaterTask, $RestartTask)) {
                $Task = Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
                if ($Task) {
                    $Captured += [pscustomobject]@{
                        name = $Name
                        actions = @($Task.Actions)
                        principal = $Task.Principal
                        settings = $Task.Settings
                    }
                }
            }
            if (($Captured.name -notcontains $WorkerTask) -or ($Captured.name -notcontains $UpdaterTask)) { throw "MIGRATION_TASK_INVALID" }
            return [pscustomobject]@{
                environment_path = $EnvironmentPath
                environment_bytes = [IO.File]::ReadAllBytes($EnvironmentPath)
                tasks = $Captured
            }
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
        RestoreSwitchState = {
            param($State)
            [IO.File]::WriteAllBytes([string]$State.environment_path, [byte[]]$State.environment_bytes)
            foreach ($Record in @($State.tasks)) {
                Set-ScheduledTask -TaskName $Record.name -Action $Record.actions `
                    -Principal $Record.principal -Settings $Record.settings | Out-Null
            }
        }.GetNewClosure()
        StopWorker = {
            param($Root)
            $Task = Get-ScheduledTask -TaskName $WorkerTask -ErrorAction Stop
            if ($Task.State -eq "Running") { Stop-ScheduledTask -TaskName $WorkerTask -ErrorAction Stop }
        }.GetNewClosure()
        StartWorker = { param($Root) Start-ScheduledTask -TaskName $WorkerTask -ErrorAction Stop }.GetNewClosure()
        ValidateWorker = {
            param($Root, $Mode, $ExpectedCommit, $ExpectedTokenHash, $CallTimeoutSeconds)
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
                $System = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8188/system_stats" -TimeoutSec $CallTimeoutSeconds
                $Objects = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8188/object_info" -TimeoutSec $CallTimeoutSeconds
                $Status = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8791/v1/worker/status" -Headers $Headers -TimeoutSec $CallTimeoutSeconds
                $Plan = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8791/v1/resources/plan" -Headers $Headers -ContentType "application/json" -Body '{"resources":[]}' -TimeoutSec $CallTimeoutSeconds
                $Preflight = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8791/v1/workflows/preflight" -Headers $Headers -ContentType "application/json" -Body '{"node_types":["CheckpointLoaderSimple","CLIPTextEncode","EmptyLatentImage","KSampler","VAEDecode","SaveImage"]}' -TimeoutSec $CallTimeoutSeconds
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
    Initialize-ProductionMigrationPrerequisites
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
