$ErrorActionPreference = "Stop"

function Invoke-CheckedInstallerCommand {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$ErrorCode
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw $ErrorCode
    }
}

function Invoke-WorkerPipInstall {
    param(
        [Parameter(Mandatory = $true)][string]$Uv,
        [Parameter(Mandatory = $true)][string]$Python,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    Invoke-CheckedInstallerCommand -FilePath $Uv `
        -Arguments (@("pip", "install", "--system", "--break-system-packages", "--python", $Python) + $Arguments) `
        -ErrorCode "INSTALL_DEPENDENCY_FAILED"
}

function Get-ConcreteInstalledPython {
    param(
        [Parameter(Mandatory = $true)][string]$PythonRoot,
        [Parameter(Mandatory = $true)][string]$ExpectedVersion
    )

    if ($ExpectedVersion -notmatch "^[0-9]+\.[0-9]+(?:\.[0-9]+)?$") {
        throw "INSTALL_PYTHON_INVALID"
    }
    $EscapedVersion = [Regex]::Escape($ExpectedVersion)
    $PatchSuffix = if ($ExpectedVersion -match "^[0-9]+\.[0-9]+$") { "\.[0-9]+" } else { "" }
    $Pattern = "^cpython-$EscapedVersion$PatchSuffix-windows-[A-Za-z0-9_]+-none$"
    $Candidates = @(
        Get-ChildItem -LiteralPath $PythonRoot -Force -Directory -ErrorAction Stop |
            Where-Object {
                -not ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) -and
                $_.Name -match $Pattern -and
                (Test-Path -LiteralPath (Join-Path $_.FullName "python.exe") -PathType Leaf)
            } |
            ForEach-Object { Get-Item -LiteralPath (Join-Path $_.FullName "python.exe") -Force }
    )
    if ($Candidates.Count -ne 1 -or
        ($Candidates[0].Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw "INSTALL_PYTHON_INVALID"
    }
    return $Candidates[0].FullName
}

function Remove-TrustedUvPythonAliases {
    param(
        [Parameter(Mandatory = $true)][string]$PythonRoot,
        [Parameter(Mandatory = $true)][string]$SelectedPython
    )

    $CanonicalRoot = [IO.Path]::GetFullPath($PythonRoot).TrimEnd("\")
    $CanonicalPython = [IO.Path]::GetFullPath($SelectedPython)
    $AliasPattern = "^cpython-[0-9]+\.[0-9]+-windows-[A-Za-z0-9_]+-none$"
    foreach ($Alias in @(Get-ChildItem -LiteralPath $CanonicalRoot -Force -Directory -ErrorAction Stop)) {
        if (-not ($Alias.Attributes -band [IO.FileAttributes]::ReparsePoint)) { continue }
        if ($Alias.LinkType -ne "Junction" -or $Alias.Name -notmatch $AliasPattern) {
            throw "INSTALL_PYTHON_REPARSE_UNSAFE"
        }
        $TargetValue = $Alias.Target
        if ($TargetValue -is [array]) { $TargetValue = $TargetValue[0] }
        if (-not $TargetValue) { throw "INSTALL_PYTHON_REPARSE_UNSAFE" }
        $CanonicalTarget = [IO.Path]::GetFullPath([string]$TargetValue).TrimEnd("\")
        if (-not $CanonicalTarget.StartsWith($CanonicalRoot + "\", [StringComparison]::OrdinalIgnoreCase)) {
            throw "INSTALL_PYTHON_REPARSE_UNSAFE"
        }
        $Target = Get-Item -LiteralPath $CanonicalTarget -Force -ErrorAction Stop
        if (-not $Target.PSIsContainer -or
            ($Target.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
            -not $CanonicalPython.StartsWith($CanonicalTarget + "\", [StringComparison]::OrdinalIgnoreCase) -or
            $CanonicalPython.StartsWith($Alias.FullName.TrimEnd("\") + "\", [StringComparison]::OrdinalIgnoreCase)) {
            throw "INSTALL_PYTHON_REPARSE_UNSAFE"
        }
        [IO.Directory]::Delete($Alias.FullName, $false)
    }
}
