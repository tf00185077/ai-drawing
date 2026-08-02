$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$script:UpdaterBootstrapTransactionLockHandle = $null

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

function Assert-UpdaterBootstrapRepositoryState {
    param(
        [Parameter(Mandatory = $true)][string]$RepositoryRoot,
        [Parameter(Mandatory = $true)][string]$ExpectedCommit,
        [Parameter(Mandatory = $true)][string]$TrustedRepositoryRoot,
        [Parameter(Mandatory = $true)][string]$TrustedRemoteUrl
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

function Assert-TrustedUpdaterBootstrapRepository {
    param(
        [Parameter(Mandatory = $true)][string]$RepositoryRoot,
        [Parameter(Mandatory = $true)][string]$ExpectedCommit
    )

    Assert-UpdaterBootstrapRepositoryState -RepositoryRoot $RepositoryRoot `
        -ExpectedCommit $ExpectedCommit `
        -TrustedRepositoryRoot "D:\code\ai-drawing" `
        -TrustedRemoteUrl "https://github.com/tf00185077/ai-drawing.git"
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
    $InstalledUpdater = Join-Path $WorkerRoot "updater"
    if (Test-Path -LiteralPath $InstalledUpdater) {
        Assert-UpdaterBootstrapNoReparseComponents -Path $InstalledUpdater
    }
    Assert-ExistingWorkerRoot -Path $WorkerRoot
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

function Import-UpdaterBootstrapWorkerSecurity {
    param(
        [Parameter(Mandatory = $true)][string]$SecurityPath
    )

    . $SecurityPath
    foreach ($FunctionName in @(
        "Assert-NotReparsePoint",
        "New-UpdaterDirectorySecurity",
        "Assert-ExpectedUpdaterAcl",
        "New-SecureUpdaterDirectory",
        "Set-SecureUpdaterRootAcl",
        "Reset-SecureUpdaterChildAcl",
        "Assert-SecureUpdaterPath",
        "Get-UpdaterTreeNoFollow",
        "Protect-UpdaterTree",
        "Assert-SecureUpdaterTree",
        "Assert-ExistingWorkerRoot"
    )) {
        $Imported = Get-Command -Name $FunctionName -CommandType Function -ErrorAction Stop
        Set-Item -Path ("Function:script:{0}" -f $FunctionName) `
            -Value $Imported.ScriptBlock -Force
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
    Import-UpdaterBootstrapWorkerSecurity -SecurityPath $SecurityPath
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

function Get-UpdaterBootstrapWorkerStageCommit {
    param(
        [Parameter(Mandatory = $true)][string]$WorkerStagingPath
    )

    $Canonical = [IO.Path]::GetFullPath($WorkerStagingPath)
    $Parent = [IO.Path]::GetDirectoryName($Canonical)
    $Leaf = [IO.Path]::GetFileName($Canonical)
    if (
        [IO.Path]::GetFileName($Parent) -cne "updater-deployment-owned" -or
        $Leaf -cnotmatch "^staging-([0-9a-f]{40})$"
    ) {
        throw "UPDATER_BOOTSTRAP_STAGE_INVALID"
    }
    return $Matches[1]
}

function Get-UpdaterBootstrapProgramDataStagePath {
    param(
        [Parameter(Mandatory = $true)][string]$WorkerStagingPath,
        [Parameter(Mandatory = $true)][string]$ProgramDataRoot
    )

    $Commit = Get-UpdaterBootstrapWorkerStageCommit `
        -WorkerStagingPath $WorkerStagingPath
    $DeploymentRoot = Join-Path $ProgramDataRoot "updater-bootstrap-deployment-owned"
    return (Join-Path $DeploymentRoot "staging-$Commit")
}

function Assert-UpdaterBootstrapProgramDataStage {
    param(
        [Parameter(Mandatory = $true)][string]$WorkerStagingPath,
        [Parameter(Mandatory = $true)][string]$ProgramDataRoot
    )

    $Staging = Get-UpdaterBootstrapProgramDataStagePath `
        -WorkerStagingPath $WorkerStagingPath -ProgramDataRoot $ProgramDataRoot
    $Bootstrap = Join-Path $Staging "UpdaterBootstrap.ps1"
    Assert-UpdaterBootstrapNoReparseTree -Path $Staging
    Assert-UpdaterBootstrapNoReparseComponents -Path $Bootstrap
    if (-not (Test-Path -LiteralPath $Bootstrap -PathType Leaf)) {
        throw "UPDATER_BOOTSTRAP_STAGE_INVALID"
    }
    Assert-SecureUpdaterTree -Path $Staging
}

function Assert-UpdaterBootstrapSwitchStage {
    param(
        [Parameter(Mandatory = $true)][string]$WorkerStagingPath,
        [Parameter(Mandatory = $true)][string]$ProgramDataRoot
    )

    Assert-UpdaterBootstrapStageStructure -StagingPath $WorkerStagingPath
    Assert-SecureUpdaterTree -Path $WorkerStagingPath
    Assert-UpdaterBootstrapProgramDataStage `
        -WorkerStagingPath $WorkerStagingPath -ProgramDataRoot $ProgramDataRoot
}

function New-UpdaterBootstrapProgramDataStage {
    param(
        [Parameter(Mandatory = $true)][string]$WorkerStagingPath,
        [Parameter(Mandatory = $true)][string]$ProgramDataRoot,
        [Parameter(Mandatory = $true)][string]$ExpectedCommit
    )

    Assert-UpdaterBootstrapExpectedCommit -ExpectedCommit $ExpectedCommit
    $WorkerCommit = Get-UpdaterBootstrapWorkerStageCommit `
        -WorkerStagingPath $WorkerStagingPath
    if ($WorkerCommit -cne $ExpectedCommit) {
        throw "UPDATER_BOOTSTRAP_COMMIT_MISMATCH"
    }
    Assert-UpdaterBootstrapNoReparseTree -Path $WorkerStagingPath
    Assert-SecureUpdaterTree -Path $WorkerStagingPath

    $BootstrapSource = Join-Path $WorkerStagingPath "UpdaterBootstrap.ps1"
    Assert-UpdaterBootstrapNoReparseComponents -Path $BootstrapSource
    if (-not (Test-Path -LiteralPath $BootstrapSource -PathType Leaf)) {
        throw "UPDATER_BOOTSTRAP_STAGE_INVALID"
    }

    Assert-UpdaterBootstrapNoReparseTree -Path $ProgramDataRoot
    Assert-SecureUpdaterTree -Path $ProgramDataRoot
    $DeploymentRoot = Join-Path $ProgramDataRoot "updater-bootstrap-deployment-owned"
    if (Test-Path -LiteralPath $DeploymentRoot) {
        Assert-UpdaterBootstrapNoReparseTree -Path $DeploymentRoot
        Assert-SecureUpdaterTree -Path $DeploymentRoot
    } else {
        New-SecureUpdaterDirectory -Path $DeploymentRoot
        Assert-UpdaterBootstrapNoReparseTree -Path $DeploymentRoot
        Assert-SecureUpdaterTree -Path $DeploymentRoot
    }

    $Staging = Join-Path $DeploymentRoot "staging-$ExpectedCommit"
    if (Test-Path -LiteralPath $Staging) {
        Assert-UpdaterBootstrapNoReparseTree -Path $Staging
        throw "UPDATER_BOOTSTRAP_STAGE_EXISTS"
    }
    New-SecureUpdaterDirectory -Path $Staging
    Copy-Item -LiteralPath $BootstrapSource `
        -Destination (Join-Path $Staging "UpdaterBootstrap.ps1") -ErrorAction Stop
    Assert-UpdaterBootstrapNoReparseTree -Path $Staging
    Protect-UpdaterTree -Path $Staging
    Assert-SecureUpdaterTree -Path $Staging
    return $Staging
}

function Enter-UpdaterBootstrapTransactionLock {
    param(
        [Parameter(Mandatory = $true)][string]$ProgramDataRoot
    )

    if ($null -ne $script:UpdaterBootstrapTransactionLockHandle) {
        throw "UPDATER_BOOTSTRAP_TRANSACTION_BUSY"
    }
    Assert-UpdaterBootstrapNoReparseTree -Path $ProgramDataRoot
    Assert-SecureUpdaterTree -Path $ProgramDataRoot
    $LockPath = Join-Path $ProgramDataRoot "updater-bootstrap-deployment.lock"
    Assert-UpdaterBootstrapNoReparseComponents -Path $LockPath
    try {
        $Handle = [IO.File]::Open(
            $LockPath,
            [IO.FileMode]::OpenOrCreate,
            [IO.FileAccess]::ReadWrite,
            [IO.FileShare]::None
        )
    } catch {
        throw "UPDATER_BOOTSTRAP_TRANSACTION_BUSY"
    }
    try {
        Assert-UpdaterBootstrapNoReparseComponents -Path $LockPath
        $script:UpdaterBootstrapTransactionLockHandle = $Handle
    } catch {
        $Handle.Dispose()
        throw
    }
}

function Exit-UpdaterBootstrapTransactionLock {
    param(
        [Parameter(Mandatory = $true)][string]$ProgramDataRoot
    )

    $Handle = $script:UpdaterBootstrapTransactionLockHandle
    if ($null -eq $Handle) {
        return
    }
    $script:UpdaterBootstrapTransactionLockHandle = $null
    $Handle.Dispose()
    $LockPath = Join-Path $ProgramDataRoot "updater-bootstrap-deployment.lock"
    if (Test-Path -LiteralPath $LockPath) {
        Assert-UpdaterBootstrapNoReparseComponents -Path $LockPath
        try {
            Remove-Item -LiteralPath $LockPath -Force -ErrorAction Stop
        } catch [IO.IOException] {
            # A following transaction may already own the same exclusive file.
        }
    }
}

function Stop-UpdaterBootstrapTask {
    param(
        [scriptblock]$TaskLookup = {
            param($Name)
            Get-ScheduledTask -TaskName $Name -ErrorAction Stop
        },
        [scriptblock]$TaskStopper = {
            param($Name)
            Stop-ScheduledTask -TaskName $Name -ErrorAction Stop
        },
        [scriptblock]$Delay = {
            param($Milliseconds)
            Start-Sleep -Milliseconds $Milliseconds
        },
        [scriptblock]$UtcNow = { [DateTime]::UtcNow }
    )

    $TaskName = "AI-Drawing Worker Updater"
    $Deadline = (& $UtcNow).AddSeconds(30)
    $Task = & $TaskLookup $TaskName
    if ([string]$Task.State -eq "Running") {
        & $TaskStopper $TaskName
    }
    do {
        $State = [string](& $TaskLookup $TaskName).State
        if ($State -ne "Running") {
            return
        }
        & $Delay 200
    } while ((& $UtcNow) -lt $Deadline)
    if ($State -eq "Running") {
        throw "UPDATER_BOOTSTRAP_TASK_BUSY"
    }
}

function Get-UpdaterBootstrapBackupDescriptor {
    param(
        [Parameter(Mandatory = $true)][string]$WorkerRoot,
        [Parameter(Mandatory = $true)][string]$ProgramDataRoot,
        [Parameter(Mandatory = $true)][string]$ExpectedCommit
    )

    $DeploymentRoot = Join-Path $WorkerRoot "updater-deployment-owned"
    return [pscustomobject]@{
        expected_commit = $ExpectedCommit
        installed_updater = Join-Path $WorkerRoot "updater"
        installed_bootstrap = Join-Path $ProgramDataRoot "UpdaterBootstrap.ps1"
        updater_backup = Join-Path $DeploymentRoot "backup-$ExpectedCommit"
        bootstrap_backup = Join-Path $ProgramDataRoot "UpdaterBootstrap.ps1.backup-$ExpectedCommit"
    }
}

function New-UpdaterBootstrapBackup {
    param(
        [Parameter(Mandatory = $true)][string]$WorkerRoot,
        [Parameter(Mandatory = $true)][string]$ProgramDataRoot,
        [Parameter(Mandatory = $true)][string]$ExpectedCommit
    )

    Assert-UpdaterBootstrapExpectedCommit -ExpectedCommit $ExpectedCommit
    $Descriptor = Get-UpdaterBootstrapBackupDescriptor -WorkerRoot $WorkerRoot `
        -ProgramDataRoot $ProgramDataRoot -ExpectedCommit $ExpectedCommit
    $DeploymentRoot = [IO.Path]::GetDirectoryName([string]$Descriptor.updater_backup)

    Assert-UpdaterBootstrapNoReparseTree -Path ([string]$Descriptor.installed_updater)
    Assert-UpdaterBootstrapNoReparseComponents -Path ([string]$Descriptor.installed_bootstrap)
    if (-not (Test-Path -LiteralPath ([string]$Descriptor.installed_bootstrap) -PathType Leaf)) {
        throw "UPDATER_BOOTSTRAP_BOOTSTRAP_INVALID"
    }
    Assert-UpdaterBootstrapNoReparseTree -Path $DeploymentRoot
    Assert-UpdaterBootstrapNoReparseTree -Path $ProgramDataRoot
    if (Test-Path -LiteralPath ([string]$Descriptor.updater_backup)) {
        Assert-UpdaterBootstrapNoReparseTree -Path ([string]$Descriptor.updater_backup)
        throw "UPDATER_BOOTSTRAP_BACKUP_EXISTS"
    }
    if (Test-Path -LiteralPath ([string]$Descriptor.bootstrap_backup)) {
        Assert-UpdaterBootstrapNoReparseComponents -Path ([string]$Descriptor.bootstrap_backup)
        throw "UPDATER_BOOTSTRAP_BACKUP_EXISTS"
    }
    Assert-UpdaterBootstrapNoReparseComponents -Path ([string]$Descriptor.updater_backup)
    Assert-UpdaterBootstrapNoReparseComponents -Path ([string]$Descriptor.bootstrap_backup)
    Assert-SecureUpdaterTree -Path ([string]$Descriptor.installed_updater)
    Assert-SecureUpdaterTree -Path $DeploymentRoot
    Assert-SecureUpdaterTree -Path $ProgramDataRoot

    $UpdaterMoved = $false
    $BootstrapMoved = $false
    try {
        Move-Item -LiteralPath ([string]$Descriptor.installed_updater) `
            -Destination ([string]$Descriptor.updater_backup) -ErrorAction Stop
        $UpdaterMoved = $true
        Move-Item -LiteralPath ([string]$Descriptor.installed_bootstrap) `
            -Destination ([string]$Descriptor.bootstrap_backup) -ErrorAction Stop
        $BootstrapMoved = $true
        Assert-UpdaterBootstrapNoReparseTree -Path ([string]$Descriptor.updater_backup)
        Assert-UpdaterBootstrapNoReparseComponents -Path ([string]$Descriptor.bootstrap_backup)
        Assert-SecureUpdaterTree -Path ([string]$Descriptor.updater_backup)
        Assert-SecureUpdaterTree -Path $ProgramDataRoot
        return $Descriptor
    } catch {
        $OriginalFailure = $_
        try {
            if ($BootstrapMoved) {
                Assert-UpdaterBootstrapNoReparseComponents `
                    -Path ([string]$Descriptor.bootstrap_backup)
                Move-Item -LiteralPath ([string]$Descriptor.bootstrap_backup) `
                    -Destination ([string]$Descriptor.installed_bootstrap) -ErrorAction Stop
            }
            if ($UpdaterMoved) {
                Assert-UpdaterBootstrapNoReparseTree -Path ([string]$Descriptor.updater_backup)
                Move-Item -LiteralPath ([string]$Descriptor.updater_backup) `
                    -Destination ([string]$Descriptor.installed_updater) -ErrorAction Stop
            }
            Protect-UpdaterBootstrapInstallation -WorkerRoot $WorkerRoot `
                -ProgramDataRoot $ProgramDataRoot
        } catch {
            throw "UPDATER_BOOTSTRAP_RECOVERY_REQUIRED"
        }
        throw $OriginalFailure
    }
}

function Install-UpdaterBootstrapStage {
    param(
        [Parameter(Mandatory = $true)][string]$StagingPath,
        [Parameter(Mandatory = $true)][string]$WorkerRoot,
        [Parameter(Mandatory = $true)][string]$ProgramDataRoot
    )

    Assert-UpdaterBootstrapSwitchStage -WorkerStagingPath $StagingPath `
        -ProgramDataRoot $ProgramDataRoot
    $StagedUpdater = Join-Path $StagingPath "updater"
    $ProgramDataStaging = Get-UpdaterBootstrapProgramDataStagePath `
        -WorkerStagingPath $StagingPath -ProgramDataRoot $ProgramDataRoot
    $StagedBootstrap = Join-Path $ProgramDataStaging "UpdaterBootstrap.ps1"
    $InstalledUpdater = Join-Path $WorkerRoot "updater"
    $InstalledBootstrap = Join-Path $ProgramDataRoot "UpdaterBootstrap.ps1"
    Assert-UpdaterBootstrapNoReparseTree -Path $StagedUpdater
    Assert-UpdaterBootstrapNoReparseComponents -Path $StagedBootstrap
    Assert-UpdaterBootstrapNoReparseComponents -Path $InstalledUpdater
    Assert-UpdaterBootstrapNoReparseComponents -Path $InstalledBootstrap
    if ((Test-Path -LiteralPath $InstalledUpdater) -or (Test-Path -LiteralPath $InstalledBootstrap)) {
        throw "UPDATER_BOOTSTRAP_ACTIVATION_FAILED"
    }
    $UpdaterSourceRoot = [IO.Path]::GetPathRoot([IO.Path]::GetFullPath($StagedUpdater))
    $UpdaterDestinationRoot = [IO.Path]::GetPathRoot([IO.Path]::GetFullPath($InstalledUpdater))
    $BootstrapSourceRoot = [IO.Path]::GetPathRoot([IO.Path]::GetFullPath($StagedBootstrap))
    $BootstrapDestinationRoot = [IO.Path]::GetPathRoot(
        [IO.Path]::GetFullPath($InstalledBootstrap)
    )
    if (
        -not $UpdaterSourceRoot.Equals(
            $UpdaterDestinationRoot,
            [StringComparison]::OrdinalIgnoreCase
        ) -or
        -not $BootstrapSourceRoot.Equals(
            $BootstrapDestinationRoot,
            [StringComparison]::OrdinalIgnoreCase
        )
    ) {
        throw "UPDATER_BOOTSTRAP_ACTIVATION_FAILED"
    }
    Move-Item -LiteralPath $StagedUpdater -Destination $InstalledUpdater -ErrorAction Stop
    Move-Item -LiteralPath $StagedBootstrap -Destination $InstalledBootstrap -ErrorAction Stop
    Assert-UpdaterBootstrapNoReparseTree -Path $InstalledUpdater
    Assert-UpdaterBootstrapNoReparseComponents -Path $InstalledBootstrap
}

function Protect-UpdaterBootstrapInstallation {
    param(
        [Parameter(Mandatory = $true)][string]$WorkerRoot,
        [Parameter(Mandatory = $true)][string]$ProgramDataRoot
    )

    $InstalledUpdater = Join-Path $WorkerRoot "updater"
    Assert-UpdaterBootstrapNoReparseTree -Path $InstalledUpdater
    Assert-UpdaterBootstrapNoReparseTree -Path $ProgramDataRoot
    Protect-UpdaterTree -Path $InstalledUpdater
    Assert-SecureUpdaterTree -Path $InstalledUpdater
    Protect-UpdaterTree -Path $ProgramDataRoot
    Assert-SecureUpdaterTree -Path $ProgramDataRoot
}

function Invoke-UpdaterBootstrapPythonCommand {
    param(
        [Parameter(Mandatory = $true)][string]$WorkerRoot,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$FailureCode,
        [scriptblock]$PythonInvoker
    )

    $UpdaterPython = Join-Path $WorkerRoot "updater-runtime\Scripts\python.exe"
    Assert-UpdaterBootstrapNoReparseComponents -Path $UpdaterPython
    if (-not (Test-Path -LiteralPath $UpdaterPython -PathType Leaf)) {
        throw $FailureCode
    }
    Push-Location -LiteralPath $WorkerRoot
    try {
        if ($null -eq $PythonInvoker) {
            & $UpdaterPython @Arguments 2>$null | Out-Null
            $ExitCode = $LASTEXITCODE
        } else {
            $ExitCode = & $PythonInvoker -Python $UpdaterPython `
                -Arguments $Arguments 2>$null
        }
    } finally {
        Pop-Location
    }
    if ([int]$ExitCode -ne 0) {
        throw $FailureCode
    }
}

function Invoke-UpdaterBootstrapImportSmoke {
    param(
        [Parameter(Mandatory = $true)][string]$WorkerRoot,
        [Parameter(Mandatory = $true)][string]$ProgramDataRoot,
        [scriptblock]$PythonInvoker
    )

    Assert-UpdaterBootstrapNoReparseTree -Path (Join-Path $WorkerRoot "updater")
    Assert-UpdaterBootstrapNoReparseTree -Path $ProgramDataRoot
    $ImportCommand = "from updater.cli import ProductionUpdaterServices; " +
        "ProductionUpdaterServices.from_program_data(); " +
        "import updater.runtime, updater.windows_runtime, updater.state"
    Invoke-UpdaterBootstrapPythonCommand -WorkerRoot $WorkerRoot `
        -Arguments @("-B", "-c", $ImportCommand) `
        -FailureCode "UPDATER_BOOTSTRAP_IMPORT_FAILED" -PythonInvoker $PythonInvoker
}

function Invoke-UpdaterBootstrapSmoke {
    param(
        [Parameter(Mandatory = $true)][string]$WorkerRoot,
        [Parameter(Mandatory = $true)][string]$ProgramDataRoot,
        [scriptblock]$PythonInvoker
    )

    Invoke-UpdaterBootstrapImportSmoke -WorkerRoot $WorkerRoot `
        -ProgramDataRoot $ProgramDataRoot -PythonInvoker $PythonInvoker
    Invoke-UpdaterBootstrapPythonCommand -WorkerRoot $WorkerRoot `
        -Arguments @("-B", "-m", "updater.recovery") `
        -FailureCode "UPDATER_BOOTSTRAP_RECOVERY_FAILED" -PythonInvoker $PythonInvoker
}

function Assert-UpdaterBootstrapScheduledTaskAction {
    param(
        [Parameter(Mandatory = $true)][string]$ProgramDataRoot,
        [scriptblock]$TaskLookup = {
            param($Name)
            Get-ScheduledTask -TaskName $Name -ErrorAction Stop
        }
    )

    $TaskName = "AI-Drawing Worker Updater"
    $BootstrapPath = Join-Path $ProgramDataRoot "UpdaterBootstrap.ps1"
    Assert-UpdaterBootstrapNoReparseComponents -Path $BootstrapPath
    if (-not (Test-Path -LiteralPath $BootstrapPath -PathType Leaf)) {
        throw "UPDATER_BOOTSTRAP_TASK_INVALID"
    }
    $Task = & $TaskLookup $TaskName
    $Actions = @($Task.Actions)
    if ($Actions.Count -ne 1) {
        throw "UPDATER_BOOTSTRAP_TASK_INVALID"
    }
    $ExpectedExecutable = Join-Path $env:SystemRoot `
        "System32\WindowsPowerShell\v1.0\powershell.exe"
    $ExpectedArguments = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"" +
        $BootstrapPath + "`""
    if (
        -not [string]::Equals(
            [string]$Actions[0].Execute,
            $ExpectedExecutable,
            [StringComparison]::OrdinalIgnoreCase
        ) -or
        -not [string]::Equals(
            [string]$Actions[0].Arguments,
            $ExpectedArguments,
            [StringComparison]::Ordinal
        )
    ) {
        throw "UPDATER_BOOTSTRAP_TASK_INVALID"
    }
}

function Remove-UpdaterBootstrapStage {
    param(
        [Parameter(Mandatory = $true)][string]$StagingPath
    )

    $Canonical = [IO.Path]::GetFullPath($StagingPath)
    $Parent = [IO.Path]::GetDirectoryName($Canonical)
    if (
        [IO.Path]::GetFileName($Parent) -ne "updater-deployment-owned" -or
        -not [IO.Path]::GetFileName($Canonical).StartsWith(
            "staging-",
            [StringComparison]::Ordinal
        )
    ) {
        throw "UPDATER_BOOTSTRAP_STAGE_INVALID"
    }
    Assert-UpdaterBootstrapNoReparseTree -Path $Canonical
    Remove-Item -LiteralPath $Canonical -Recurse -Force -ErrorAction Stop
}

function Remove-UpdaterBootstrapProgramDataStage {
    param(
        [Parameter(Mandatory = $true)][string]$WorkerStagingPath,
        [Parameter(Mandatory = $true)][string]$ProgramDataRoot
    )

    $Staging = Get-UpdaterBootstrapProgramDataStagePath `
        -WorkerStagingPath $WorkerStagingPath -ProgramDataRoot $ProgramDataRoot
    Assert-UpdaterBootstrapNoReparseTree -Path $Staging
    Assert-SecureUpdaterTree -Path $Staging
    Remove-Item -LiteralPath $Staging -Recurse -Force -ErrorAction Stop
}

function Remove-UpdaterBootstrapSwitchStage {
    param(
        [Parameter(Mandatory = $true)][string]$WorkerStagingPath,
        [Parameter(Mandatory = $true)][string]$ProgramDataRoot
    )

    Assert-UpdaterBootstrapNoReparseTree -Path $WorkerStagingPath
    Assert-SecureUpdaterTree -Path $WorkerStagingPath
    $ProgramDataStaging = Get-UpdaterBootstrapProgramDataStagePath `
        -WorkerStagingPath $WorkerStagingPath -ProgramDataRoot $ProgramDataRoot
    Assert-UpdaterBootstrapNoReparseTree -Path $ProgramDataStaging
    Assert-SecureUpdaterTree -Path $ProgramDataStaging
    Remove-UpdaterBootstrapStage -StagingPath $WorkerStagingPath
    Remove-UpdaterBootstrapProgramDataStage `
        -WorkerStagingPath $WorkerStagingPath -ProgramDataRoot $ProgramDataRoot
}

function Assert-UpdaterBootstrapBackupDescriptor {
    param(
        [Parameter(Mandatory = $true)]$Backup,
        [Parameter(Mandatory = $true)][string]$WorkerRoot,
        [Parameter(Mandatory = $true)][string]$ProgramDataRoot
    )

    $Commit = [string]$Backup.expected_commit
    Assert-UpdaterBootstrapExpectedCommit -ExpectedCommit $Commit
    $Expected = Get-UpdaterBootstrapBackupDescriptor -WorkerRoot $WorkerRoot `
        -ProgramDataRoot $ProgramDataRoot -ExpectedCommit $Commit
    foreach ($Name in @(
        "installed_updater",
        "installed_bootstrap",
        "updater_backup",
        "bootstrap_backup"
    )) {
        $ActualPath = [IO.Path]::GetFullPath([string]$Backup.$Name)
        $ExpectedPath = [IO.Path]::GetFullPath([string]$Expected.$Name)
        if (-not $ActualPath.Equals($ExpectedPath, [StringComparison]::OrdinalIgnoreCase)) {
            throw "UPDATER_BOOTSTRAP_RECOVERY_REQUIRED"
        }
    }
}

function Restore-UpdaterBootstrapBackup {
    param(
        [Parameter(Mandatory = $true)]$Backup,
        [Parameter(Mandatory = $true)][string]$WorkerRoot,
        [Parameter(Mandatory = $true)][string]$ProgramDataRoot
    )

    Assert-UpdaterBootstrapBackupDescriptor -Backup $Backup -WorkerRoot $WorkerRoot `
        -ProgramDataRoot $ProgramDataRoot
    $UpdaterBackup = [string]$Backup.updater_backup
    $BootstrapBackup = [string]$Backup.bootstrap_backup
    $InstalledUpdater = [string]$Backup.installed_updater
    $InstalledBootstrap = [string]$Backup.installed_bootstrap
    Assert-UpdaterBootstrapNoReparseTree -Path $UpdaterBackup
    Assert-UpdaterBootstrapNoReparseComponents -Path $BootstrapBackup
    if (-not (Test-Path -LiteralPath $BootstrapBackup -PathType Leaf)) {
        throw "UPDATER_BOOTSTRAP_RECOVERY_REQUIRED"
    }
    Assert-SecureUpdaterTree -Path $UpdaterBackup
    Assert-UpdaterBootstrapNoReparseTree -Path $ProgramDataRoot
    if (Test-Path -LiteralPath $InstalledUpdater) {
        Assert-UpdaterBootstrapNoReparseTree -Path $InstalledUpdater
        Remove-Item -LiteralPath $InstalledUpdater -Recurse -Force -ErrorAction Stop
    }
    if (Test-Path -LiteralPath $InstalledBootstrap) {
        Assert-UpdaterBootstrapNoReparseComponents -Path $InstalledBootstrap
        Remove-Item -LiteralPath $InstalledBootstrap -Force -ErrorAction Stop
    }
    Move-Item -LiteralPath $UpdaterBackup -Destination $InstalledUpdater -ErrorAction Stop
    Move-Item -LiteralPath $BootstrapBackup -Destination $InstalledBootstrap -ErrorAction Stop
    Protect-UpdaterBootstrapInstallation -WorkerRoot $WorkerRoot `
        -ProgramDataRoot $ProgramDataRoot
}

function Assert-UpdaterBootstrapRollback {
    param(
        [Parameter(Mandatory = $true)][string]$WorkerRoot,
        [Parameter(Mandatory = $true)][string]$ProgramDataRoot
    )

    $InstalledUpdater = Join-Path $WorkerRoot "updater"
    Assert-UpdaterBootstrapNoReparseTree -Path $InstalledUpdater
    Assert-UpdaterBootstrapNoReparseTree -Path $ProgramDataRoot
    Assert-SecureUpdaterTree -Path $InstalledUpdater
    Assert-SecureUpdaterTree -Path $ProgramDataRoot
    Invoke-UpdaterBootstrapImportSmoke -WorkerRoot $WorkerRoot `
        -ProgramDataRoot $ProgramDataRoot
}

function Get-ProductionUpdaterBootstrapAdapter {
    return [pscustomobject]@{
        ValidateContext = {
            param($RepositoryRoot, $WorkerRoot, $ProgramDataRoot, $ExpectedCommit)
            Assert-UpdaterBootstrapProductionContext -RepositoryRoot $RepositoryRoot `
                -WorkerRoot $WorkerRoot -ProgramDataRoot $ProgramDataRoot `
                -ExpectedCommit $ExpectedCommit
        }
        AcquireLock = {
            param($ProgramDataRoot)
            Enter-UpdaterBootstrapTransactionLock -ProgramDataRoot $ProgramDataRoot
        }
        StopUpdaterTask = { Stop-UpdaterBootstrapTask }
        Stage = {
            param($RepositoryRoot, $WorkerRoot, $ProgramDataRoot, $ExpectedCommit)
            $WorkerStaging = New-UpdaterBootstrapStage -RepositoryRoot $RepositoryRoot `
                -WorkerRoot $WorkerRoot -ExpectedCommit $ExpectedCommit
            $null = New-UpdaterBootstrapProgramDataStage `
                -WorkerStagingPath $WorkerStaging -ProgramDataRoot $ProgramDataRoot `
                -ExpectedCommit $ExpectedCommit
            return $WorkerStaging
        }
        ValidateStage = {
            param($Staging, $ProgramDataRoot)
            if ([string]::IsNullOrEmpty([string]$ProgramDataRoot)) {
                Assert-UpdaterBootstrapStageStructure -StagingPath $Staging
                Assert-SecureUpdaterTree -Path $Staging
            } else {
                Assert-UpdaterBootstrapSwitchStage -WorkerStagingPath $Staging `
                    -ProgramDataRoot $ProgramDataRoot
            }
        }
        Backup = {
            param($WorkerRoot, $ProgramDataRoot, $ExpectedCommit)
            New-UpdaterBootstrapBackup -WorkerRoot $WorkerRoot `
                -ProgramDataRoot $ProgramDataRoot -ExpectedCommit $ExpectedCommit
        }
        Activate = {
            param($Staging, $WorkerRoot, $ProgramDataRoot)
            Install-UpdaterBootstrapStage -StagingPath $Staging -WorkerRoot $WorkerRoot `
                -ProgramDataRoot $ProgramDataRoot
        }
        Protect = {
            param($WorkerRoot, $ProgramDataRoot)
            Protect-UpdaterBootstrapInstallation -WorkerRoot $WorkerRoot `
                -ProgramDataRoot $ProgramDataRoot
        }
        Smoke = {
            param($WorkerRoot, $ProgramDataRoot)
            Invoke-UpdaterBootstrapSmoke -WorkerRoot $WorkerRoot `
                -ProgramDataRoot $ProgramDataRoot
        }
        ValidateTask = {
            param($ProgramDataRoot)
            Assert-UpdaterBootstrapScheduledTaskAction -ProgramDataRoot $ProgramDataRoot
        }
        CleanupSuccess = {
            param($Staging, $ProgramDataRoot)
            Remove-UpdaterBootstrapSwitchStage -WorkerStagingPath $Staging `
                -ProgramDataRoot $ProgramDataRoot
        }
        Rollback = {
            param($Backup, $WorkerRoot, $ProgramDataRoot)
            Restore-UpdaterBootstrapBackup -Backup $Backup -WorkerRoot $WorkerRoot `
                -ProgramDataRoot $ProgramDataRoot
        }
        ValidateRollback = {
            param($WorkerRoot, $ProgramDataRoot)
            Assert-UpdaterBootstrapRollback -WorkerRoot $WorkerRoot `
                -ProgramDataRoot $ProgramDataRoot
        }
        ReleaseLock = {
            param($ProgramDataRoot)
            Exit-UpdaterBootstrapTransactionLock -ProgramDataRoot $ProgramDataRoot
        }
    }
}

function Get-UpdaterBootstrapStageErrorCode {
    param(
        [Parameter(Mandatory = $true)][string]$Stage
    )

    switch ($Stage) {
        "stopping-updater-task" { return "UPDATER_BOOTSTRAP_TASK_BUSY" }
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
    $Result = $null

    try {
        & $Adapter.ValidateContext $RepositoryRoot $WorkerRoot $ProgramDataRoot $ExpectedCommit
        $Stage = "acquiring-lock"
        & $Adapter.AcquireLock $ProgramDataRoot
        $LockHeld = $true
        $Stage = "stopping-updater-task"
        & $Adapter.StopUpdaterTask
        $Stage = "staging"
        $Staging = & $Adapter.Stage $RepositoryRoot $WorkerRoot $ProgramDataRoot $ExpectedCommit
        & $Adapter.ValidateStage $Staging $ProgramDataRoot
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
        $Stage = "cleaning-up"
        & $Adapter.CleanupSuccess $Staging $ProgramDataRoot
        $Result = [pscustomobject]@{
            status = "ready"
            error_code = $null
            backup = $Backup
        }
    } catch {
        if ([string]$_.Exception.Message -eq "UPDATER_BOOTSTRAP_RECOVERY_REQUIRED") {
            $Result = [pscustomobject]@{
                status = "recovery_required"
                error_code = "UPDATER_BOOTSTRAP_RECOVERY_REQUIRED"
                backup = $Backup
            }
        } else {
            $Code = Get-UpdaterBootstrapStageErrorCode -Stage $Stage
            if ($null -eq $Backup) {
                $Result = [pscustomobject]@{
                    status = "failed_before_switch"
                    error_code = $Code
                    backup = $null
                }
            } else {
                try {
                    & $Adapter.Rollback $Backup $WorkerRoot $ProgramDataRoot
                    & $Adapter.ValidateRollback $WorkerRoot $ProgramDataRoot
                    $Result = [pscustomobject]@{
                        status = "rolled_back"
                        error_code = $Code
                        backup = $Backup
                    }
                } catch {
                    $Result = [pscustomobject]@{
                        status = "recovery_required"
                        error_code = "UPDATER_BOOTSTRAP_RECOVERY_REQUIRED"
                        backup = $Backup
                    }
                }
            }
        }
    } finally {
        if ($LockHeld) {
            try {
                & $Adapter.ReleaseLock $ProgramDataRoot | Out-Null
            } catch {
                $Result = [pscustomobject]@{
                    status = "recovery_required"
                    error_code = "UPDATER_BOOTSTRAP_RECOVERY_REQUIRED"
                    backup = $Backup
                }
            }
        }
    }
    return $Result
}
