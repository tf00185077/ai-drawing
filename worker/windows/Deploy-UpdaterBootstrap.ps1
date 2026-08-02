$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$script:UpdaterBootstrapRepositoryRoot = "D:\code\ai-drawing"
$script:UpdaterBootstrapRemoteUrl = "https://github.com/tf00185077/ai-drawing.git"

function Assert-UpdaterBootstrapExpectedCommit {
    param(
        [Parameter(Mandatory = $true)][string]$ExpectedCommit
    )

    if ($ExpectedCommit -cnotmatch "^[0-9a-f]{40}$") {
        throw "UPDATER_BOOTSTRAP_COMMIT_INVALID"
    }
}

function Assert-UpdaterBootstrapElevation {
    param(
        [scriptblock]$AdministratorProbe = {
            $Identity = [Security.Principal.WindowsIdentity]::GetCurrent()
            $Principal = New-Object Security.Principal.WindowsPrincipal($Identity)
            return $Principal.IsInRole(
                [Security.Principal.WindowsBuiltInRole]::Administrator
            )
        }
    )

    if (-not (& $AdministratorProbe)) {
        throw "UPDATER_BOOTSTRAP_ELEVATION_REQUIRED"
    }
}

function Assert-UpdaterBootstrapNoReparseComponents {
    param(
        [Parameter(Mandatory = $true)][string]$Path
    )

    $Candidate = [IO.Path]::GetFullPath($Path)
    while (-not [string]::IsNullOrEmpty($Candidate)) {
        if ([IO.Directory]::Exists($Candidate) -or [IO.File]::Exists($Candidate)) {
            $Item = Get-Item -LiteralPath $Candidate -Force -ErrorAction Stop
            if (($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "UPDATER_BOOTSTRAP_REPARSE_POINT"
            }
        }
        $Parent = [IO.Path]::GetDirectoryName($Candidate)
        if ([string]::IsNullOrEmpty($Parent) -or $Parent -eq $Candidate) {
            break
        }
        $Candidate = $Parent
    }
}

function Assert-UpdaterBootstrapNoReparseTree {
    param(
        [Parameter(Mandatory = $true)][string]$Path
    )

    Assert-UpdaterBootstrapNoReparseComponents -Path $Path
    $Root = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    $Pending = New-Object "System.Collections.Generic.Stack[System.IO.FileSystemInfo]"
    $Pending.Push($Root)
    while ($Pending.Count -gt 0) {
        $Item = $Pending.Pop()
        if (($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "UPDATER_BOOTSTRAP_REPARSE_POINT"
        }
        if ($Item.PSIsContainer) {
            foreach ($Child in @(Get-ChildItem -LiteralPath $Item.FullName -Force -ErrorAction Stop)) {
                if (($Child.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                    throw "UPDATER_BOOTSTRAP_REPARSE_POINT"
                }
                $Pending.Push($Child)
            }
        }
    }
}

function Assert-TrustedUpdaterBootstrapRepository {
    param(
        [Parameter(Mandatory = $true)][string]$RepositoryRoot,
        [Parameter(Mandatory = $true)][string]$ExpectedCommit,
        [string]$TrustedRepositoryRoot = $script:UpdaterBootstrapRepositoryRoot,
        [string]$TrustedRemoteUrl = $script:UpdaterBootstrapRemoteUrl
    )

    Assert-UpdaterBootstrapExpectedCommit -ExpectedCommit $ExpectedCommit
    Assert-UpdaterBootstrapNoReparseComponents -Path $RepositoryRoot
    $Canonical = (Resolve-Path -LiteralPath $RepositoryRoot -ErrorAction Stop).Path
    $TrustedCanonical = [IO.Path]::GetFullPath($TrustedRepositoryRoot)
    if (-not $Canonical.Equals($TrustedCanonical, [StringComparison]::OrdinalIgnoreCase)) {
        throw "UPDATER_BOOTSTRAP_REPOSITORY_INVALID"
    }

    $PreviousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        & git.exe -C $Canonical fetch --prune origin main 2>$null | Out-Null
        $FetchExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $PreviousErrorActionPreference
    }
    if ($FetchExitCode -ne 0) {
        throw "UPDATER_BOOTSTRAP_FETCH_FAILED"
    }

    $Branch = [string](& git.exe -C $Canonical branch --show-current 2>$null)
    if ($LASTEXITCODE -ne 0) {
        throw "UPDATER_BOOTSTRAP_REPOSITORY_INVALID"
    }
    $Head = [string](& git.exe -C $Canonical rev-parse HEAD 2>$null)
    if ($LASTEXITCODE -ne 0) {
        throw "UPDATER_BOOTSTRAP_REPOSITORY_INVALID"
    }
    $OriginMain = [string](& git.exe -C $Canonical rev-parse origin/main 2>$null)
    if ($LASTEXITCODE -ne 0) {
        throw "UPDATER_BOOTSTRAP_REPOSITORY_INVALID"
    }
    $Remote = [string](& git.exe -C $Canonical remote get-url origin 2>$null)
    if ($LASTEXITCODE -ne 0) {
        throw "UPDATER_BOOTSTRAP_REPOSITORY_INVALID"
    }
    $Dirty = @(& git.exe -C $Canonical status --porcelain --untracked-files=no 2>$null)
    if ($LASTEXITCODE -ne 0) {
        throw "UPDATER_BOOTSTRAP_REPOSITORY_INVALID"
    }

    $Branch = $Branch.Trim()
    $Head = $Head.Trim()
    $OriginMain = $OriginMain.Trim()
    $Remote = $Remote.Trim().TrimEnd("/")
    $ExpectedRemote = $TrustedRemoteUrl.Trim().TrimEnd("/")
    if ($Branch -ne "main") {
        throw "UPDATER_BOOTSTRAP_BRANCH_INVALID"
    }
    if ($Remote -cne $ExpectedRemote) {
        throw "UPDATER_BOOTSTRAP_REMOTE_INVALID"
    }
    if ($Head -cne $OriginMain) {
        throw "UPDATER_BOOTSTRAP_SOURCE_STALE"
    }
    if ($Head -cne $ExpectedCommit) {
        throw "UPDATER_BOOTSTRAP_COMMIT_MISMATCH"
    }
    if ($Dirty.Count -ne 0) {
        throw "UPDATER_BOOTSTRAP_SOURCE_DIRTY"
    }
}

function Assert-UpdaterBootstrapWorkerPaths {
    param(
        [Parameter(Mandatory = $true)][string]$WorkerRoot,
        [Parameter(Mandatory = $true)][string]$ProgramDataRoot,
        [Parameter(Mandatory = $true)][string]$ExpectedCommit
    )

    Assert-UpdaterBootstrapExpectedCommit -ExpectedCommit $ExpectedCommit
    Assert-UpdaterBootstrapNoReparseComponents -Path $WorkerRoot
    Assert-UpdaterBootstrapNoReparseTree -Path $ProgramDataRoot
    Assert-ExistingWorkerRoot -Path $WorkerRoot

    $InstalledUpdater = Join-Path $WorkerRoot "updater"
    Assert-UpdaterBootstrapNoReparseTree -Path $InstalledUpdater
    Assert-SecureUpdaterTree -Path $InstalledUpdater
    Assert-SecureUpdaterTree -Path $ProgramDataRoot

    $DeploymentRoot = Join-Path $WorkerRoot "updater-deployment-owned"
    if (Test-Path -LiteralPath $DeploymentRoot) {
        Assert-UpdaterBootstrapNoReparseTree -Path $DeploymentRoot
        Assert-SecureUpdaterTree -Path $DeploymentRoot
    }
    foreach ($Leaf in @("staging-$ExpectedCommit", "backup-$ExpectedCommit")) {
        $Candidate = Join-Path $DeploymentRoot $Leaf
        if (Test-Path -LiteralPath $Candidate) {
            Assert-UpdaterBootstrapNoReparseTree -Path $Candidate
            Assert-SecureUpdaterTree -Path $Candidate
        }
    }
}

function Assert-UpdaterBootstrapProductionContext {
    param(
        [Parameter(Mandatory = $true)][string]$RepositoryRoot,
        [Parameter(Mandatory = $true)][string]$WorkerRoot,
        [Parameter(Mandatory = $true)][string]$ProgramDataRoot,
        [Parameter(Mandatory = $true)][string]$ExpectedCommit
    )

    Assert-UpdaterBootstrapElevation
    Assert-UpdaterBootstrapExpectedCommit -ExpectedCommit $ExpectedCommit
    Assert-TrustedUpdaterBootstrapRepository -RepositoryRoot $RepositoryRoot `
        -ExpectedCommit $ExpectedCommit

    $SecurityPath = Join-Path $RepositoryRoot "worker\windows\WorkerSecurity.ps1"
    Assert-UpdaterBootstrapNoReparseComponents -Path $SecurityPath
    if (-not (Test-Path -LiteralPath $SecurityPath -PathType Leaf)) {
        throw "UPDATER_BOOTSTRAP_SECURITY_HELPER_INVALID"
    }
    . $SecurityPath
    Assert-UpdaterBootstrapWorkerPaths -WorkerRoot $WorkerRoot `
        -ProgramDataRoot $ProgramDataRoot -ExpectedCommit $ExpectedCommit
}

function Assert-UpdaterBootstrapStageStructure {
    param(
        [Parameter(Mandatory = $true)][string]$StagingPath
    )

    Assert-UpdaterBootstrapNoReparseTree -Path $StagingPath
    foreach ($Relative in @(
        "updater\__init__.py",
        "updater\cli.py",
        "updater\runtime.py",
        "updater\windows_runtime.py",
        "updater\state.py",
        "UpdaterBootstrap.ps1"
    )) {
        if (-not (Test-Path -LiteralPath (Join-Path $StagingPath $Relative) -PathType Leaf)) {
            throw "UPDATER_BOOTSTRAP_STAGE_INVALID"
        }
    }
}

function Assert-UpdaterBootstrapTreeAcl {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][Security.Principal.SecurityIdentifier]$OwnerSid,
        [Parameter(Mandatory = $true)][Security.Principal.SecurityIdentifier[]]$AllowedSids
    )

    $Tree = @(Get-UpdaterTreeNoFollow -Path $Path)
    Assert-ExpectedUpdaterAcl -Path $Tree[0].FullName -OwnerSid $OwnerSid `
        -AllowedSids $AllowedSids -RequireProtected -RequireInheritable
    foreach ($Child in @($Tree | Select-Object -Skip 1)) {
        Assert-ExpectedUpdaterAcl -Path $Child.FullName -OwnerSid $OwnerSid `
            -AllowedSids $AllowedSids
    }
}

function New-UpdaterBootstrapStage {
    param(
        [Parameter(Mandatory = $true)][string]$RepositoryRoot,
        [Parameter(Mandatory = $true)][string]$WorkerRoot,
        [Parameter(Mandatory = $true)][string]$ExpectedCommit,
        [Security.Principal.SecurityIdentifier]$OwnerSid,
        [Security.Principal.SecurityIdentifier[]]$AllowedSids
    )

    Assert-UpdaterBootstrapExpectedCommit -ExpectedCommit $ExpectedCommit
    Assert-UpdaterBootstrapNoReparseComponents -Path $RepositoryRoot
    Assert-UpdaterBootstrapNoReparseComponents -Path $WorkerRoot
    $Repository = (Resolve-Path -LiteralPath $RepositoryRoot -ErrorAction Stop).Path
    $Worker = (Resolve-Path -LiteralPath $WorkerRoot -ErrorAction Stop).Path

    $UpdaterSource = Join-Path $Repository "worker\windows\updater"
    $BootstrapSource = Join-Path $Repository "worker\windows\UpdaterBootstrap.ps1"
    Assert-UpdaterBootstrapNoReparseTree -Path $UpdaterSource
    Assert-UpdaterBootstrapNoReparseComponents -Path $BootstrapSource
    if (-not (Test-Path -LiteralPath $BootstrapSource -PathType Leaf)) {
        throw "UPDATER_BOOTSTRAP_SOURCE_INVALID"
    }

    $UseCustomAcl = $PSBoundParameters.ContainsKey("OwnerSid") -or
        $PSBoundParameters.ContainsKey("AllowedSids")
    if ($UseCustomAcl -and ($null -eq $OwnerSid -or $null -eq $AllowedSids)) {
        throw "UPDATER_BOOTSTRAP_SECURITY_PRINCIPALS_INVALID"
    }

    $DeploymentRoot = Join-Path $Worker "updater-deployment-owned"
    if (Test-Path -LiteralPath $DeploymentRoot) {
        Assert-UpdaterBootstrapNoReparseTree -Path $DeploymentRoot
        if ($UseCustomAcl) {
            Assert-UpdaterBootstrapTreeAcl -Path $DeploymentRoot `
                -OwnerSid $OwnerSid -AllowedSids $AllowedSids
        } else {
            Assert-SecureUpdaterTree -Path $DeploymentRoot
        }
    } elseif ($UseCustomAcl) {
        New-SecureUpdaterDirectory -Path $DeploymentRoot -OwnerSid $OwnerSid `
            -AllowedSids $AllowedSids
    } else {
        New-SecureUpdaterDirectory -Path $DeploymentRoot
    }

    $Staging = Join-Path $DeploymentRoot "staging-$ExpectedCommit"
    if (Test-Path -LiteralPath $Staging) {
        Assert-UpdaterBootstrapNoReparseTree -Path $Staging
        throw "UPDATER_BOOTSTRAP_STAGE_EXISTS"
    }
    if ($UseCustomAcl) {
        New-SecureUpdaterDirectory -Path $Staging -OwnerSid $OwnerSid `
            -AllowedSids $AllowedSids
    } else {
        New-SecureUpdaterDirectory -Path $Staging
    }

    $Tracked = @(& git.exe -C $Repository ls-files -- `
        "worker/windows/updater" "worker/windows/UpdaterBootstrap.ps1" 2>$null)
    if ($LASTEXITCODE -ne 0) {
        throw "UPDATER_BOOTSTRAP_TRACKED_SOURCE_INVALID"
    }
    foreach ($GitPath in $Tracked) {
        $Normalized = ([string]$GitPath).Trim().Replace("/", "\")
        if ([string]::IsNullOrEmpty($Normalized)) {
            continue
        }
        if (
            $Normalized -ne "worker\windows\UpdaterBootstrap.ps1" -and
            -not $Normalized.StartsWith(
                "worker\windows\updater\",
                [StringComparison]::Ordinal
            )
        ) {
            throw "UPDATER_BOOTSTRAP_TRACKED_SOURCE_INVALID"
        }
        $SourcePath = Join-Path $Repository $Normalized
        Assert-UpdaterBootstrapNoReparseComponents -Path $SourcePath
        if (-not (Test-Path -LiteralPath $SourcePath -PathType Leaf)) {
            throw "UPDATER_BOOTSTRAP_TRACKED_SOURCE_INVALID"
        }
        $StageRelative = $Normalized.Substring("worker\windows\".Length)
        $DestinationPath = Join-Path $Staging $StageRelative
        $DestinationParent = [IO.Path]::GetDirectoryName($DestinationPath)
        if (-not (Test-Path -LiteralPath $DestinationParent -PathType Container)) {
            [void][IO.Directory]::CreateDirectory($DestinationParent)
        }
        Assert-UpdaterBootstrapNoReparseComponents -Path $DestinationParent
        Copy-Item -LiteralPath $SourcePath -Destination $DestinationPath -ErrorAction Stop
    }

    Assert-UpdaterBootstrapStageStructure -StagingPath $Staging
    if ($UseCustomAcl) {
        Assert-UpdaterBootstrapTreeAcl -Path $Staging -OwnerSid $OwnerSid `
            -AllowedSids $AllowedSids
    } else {
        Protect-UpdaterTree -Path $Staging
    }
    return $Staging
}

function Get-ProductionUpdaterBootstrapAdapter {
    return [pscustomobject]@{
        ValidateContext = {
            param($RepositoryRoot, $WorkerRoot, $ProgramDataRoot, $ExpectedCommit)
            Assert-UpdaterBootstrapProductionContext -RepositoryRoot $RepositoryRoot `
                -WorkerRoot $WorkerRoot -ProgramDataRoot $ProgramDataRoot `
                -ExpectedCommit $ExpectedCommit
        }
        AcquireLock = { param($ProgramDataRoot) throw "UPDATER_BOOTSTRAP_NOT_IMPLEMENTED" }
        StopUpdaterTask = { throw "UPDATER_BOOTSTRAP_NOT_IMPLEMENTED" }
        Stage = {
            param($RepositoryRoot, $WorkerRoot, $ProgramDataRoot, $ExpectedCommit)
            New-UpdaterBootstrapStage -RepositoryRoot $RepositoryRoot `
                -WorkerRoot $WorkerRoot -ExpectedCommit $ExpectedCommit
        }
        ValidateStage = {
            param($Staging)
            Assert-UpdaterBootstrapStageStructure -StagingPath $Staging
            Assert-SecureUpdaterTree -Path $Staging
        }
        Backup = { param($WorkerRoot, $ProgramDataRoot, $ExpectedCommit) throw "UPDATER_BOOTSTRAP_NOT_IMPLEMENTED" }
        Activate = { param($Staging, $WorkerRoot, $ProgramDataRoot) throw "UPDATER_BOOTSTRAP_NOT_IMPLEMENTED" }
        Protect = { param($WorkerRoot, $ProgramDataRoot) throw "UPDATER_BOOTSTRAP_NOT_IMPLEMENTED" }
        Smoke = { param($WorkerRoot, $ProgramDataRoot) throw "UPDATER_BOOTSTRAP_NOT_IMPLEMENTED" }
        ValidateTask = { param($ProgramDataRoot) throw "UPDATER_BOOTSTRAP_NOT_IMPLEMENTED" }
        CleanupSuccess = { param($Staging) throw "UPDATER_BOOTSTRAP_NOT_IMPLEMENTED" }
        Rollback = { param($Backup, $WorkerRoot, $ProgramDataRoot) throw "UPDATER_BOOTSTRAP_NOT_IMPLEMENTED" }
        ValidateRollback = { param($WorkerRoot, $ProgramDataRoot) throw "UPDATER_BOOTSTRAP_NOT_IMPLEMENTED" }
        ReleaseLock = { param($ProgramDataRoot) }
    }
}

function Get-UpdaterBootstrapStageErrorCode {
    param(
        [Parameter(Mandatory = $true)][string]$Stage
    )

    switch ($Stage) {
        "activating" { return "UPDATER_BOOTSTRAP_ACTIVATION_FAILED" }
        "smoke-testing" { return "UPDATER_BOOTSTRAP_SMOKE_FAILED" }
        "validating-task" { return "UPDATER_BOOTSTRAP_TASK_INVALID" }
        default { return "UPDATER_BOOTSTRAP_STAGE_FAILED" }
    }
}

function Invoke-UpdaterBootstrapTransaction {
    param(
        [Parameter(Mandatory = $true)][string]$RepositoryRoot,
        [Parameter(Mandatory = $true)][string]$WorkerRoot,
        [Parameter(Mandatory = $true)][string]$ProgramDataRoot,
        [Parameter(Mandatory = $true)][string]$ExpectedCommit,
        [Parameter(Mandatory = $true)]$Adapter
    )

    $Stage = "validating-context"
    $Backup = $null
    $LockHeld = $false

    try {
        & $Adapter.ValidateContext $RepositoryRoot $WorkerRoot $ProgramDataRoot $ExpectedCommit
        & $Adapter.AcquireLock $ProgramDataRoot
        $LockHeld = $true
        & $Adapter.StopUpdaterTask
        $Stage = "staging"
        $Staging = & $Adapter.Stage $RepositoryRoot $WorkerRoot $ProgramDataRoot $ExpectedCommit
        & $Adapter.ValidateStage $Staging
        $Stage = "backing-up"
        $Backup = & $Adapter.Backup $WorkerRoot $ProgramDataRoot $ExpectedCommit
        $Stage = "activating"
        & $Adapter.Activate $Staging $WorkerRoot $ProgramDataRoot
        $Stage = "protecting"
        & $Adapter.Protect $WorkerRoot $ProgramDataRoot
        $Stage = "smoke-testing"
        & $Adapter.Smoke $WorkerRoot $ProgramDataRoot
        $Stage = "validating-task"
        & $Adapter.ValidateTask $ProgramDataRoot
        & $Adapter.CleanupSuccess $Staging
        return [pscustomobject]@{
            status = "ready"
            error_code = $null
            backup = $Backup
        }
    } catch {
        $Code = Get-UpdaterBootstrapStageErrorCode -Stage $Stage
        if ($null -eq $Backup) {
            return [pscustomobject]@{
                status = "failed_before_switch"
                error_code = $Code
                backup = $null
            }
        }

        try {
            & $Adapter.Rollback $Backup $WorkerRoot $ProgramDataRoot
            & $Adapter.ValidateRollback $WorkerRoot $ProgramDataRoot
            return [pscustomobject]@{
                status = "rolled_back"
                error_code = $Code
                backup = $Backup
            }
        } catch {
            return [pscustomobject]@{
                status = "recovery_required"
                error_code = "UPDATER_BOOTSTRAP_RECOVERY_REQUIRED"
                backup = $Backup
            }
        }
    } finally {
        if ($LockHeld) {
            & $Adapter.ReleaseLock $ProgramDataRoot
        }
    }
}
