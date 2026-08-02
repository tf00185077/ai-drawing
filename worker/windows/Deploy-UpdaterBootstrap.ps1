$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

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
