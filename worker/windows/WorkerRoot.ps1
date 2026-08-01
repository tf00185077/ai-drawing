$script:DirectDWorkerRoot = "D:\code\AI-Drawing-Worker"

function Assert-WorkerInstallParentNoReparse {
    param([Parameter(Mandatory = $true)][string]$Path)

    $FullPath = [IO.Path]::GetFullPath($Path)
    $ParentPath = [IO.Path]::GetDirectoryName($FullPath.TrimEnd("\"))
    $DriveRoot = [IO.Path]::GetPathRoot($ParentPath)
    $Cursor = $DriveRoot
    $Relative = $ParentPath.Substring($DriveRoot.Length)
    foreach ($Part in @($Relative.Split(@("\", "/"), [StringSplitOptions]::RemoveEmptyEntries))) {
        $Cursor = Join-Path $Cursor $Part
        if (-not (Test-Path -LiteralPath $Cursor)) { break }
        $Item = Get-Item -LiteralPath $Cursor -Force -ErrorAction Stop
        if (($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "WORKER_ROOT_REPARSE"
        }
    }
    return $FullPath
}

function Resolve-WorkerInstallRoot {
    param([Parameter(Mandatory = $true)][string]$Path)

    if ($Path -ne $Path.Trim() -or -not [IO.Path]::IsPathRooted($Path) -or $Path.StartsWith("\\")) {
        throw "WORKER_ROOT_INVALID"
    }
    $FullPath = [IO.Path]::GetFullPath($Path).TrimEnd("\")
    if (-not $FullPath.Equals($script:DirectDWorkerRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "WORKER_ROOT_INVALID"
    }
    Assert-WorkerInstallParentNoReparse -Path $FullPath | Out-Null
    return $FullPath
}
