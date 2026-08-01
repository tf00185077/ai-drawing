$ErrorActionPreference = "Stop"

function Resolve-ManagedCurrentRelease {
    param([Parameter(Mandatory = $true)][string]$Root)

    $CanonicalRoot = [IO.Path]::GetFullPath($Root).TrimEnd("\")
    $ReleasesRoot = Join-Path $CanonicalRoot "releases"
    $CurrentPath = Join-Path $CanonicalRoot "current"
    try {
        $Current = Get-Item -LiteralPath $CurrentPath -Force -ErrorAction Stop
        if (-not ($Current.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
            $Current.LinkType -ne "Junction") {
            throw "WORKER_CURRENT_INVALID"
        }
        $TargetValue = $Current.Target
        if ($TargetValue -is [array]) { $TargetValue = $TargetValue[0] }
        if (-not $TargetValue) { throw "WORKER_CURRENT_INVALID" }
        $CanonicalTarget = [IO.Path]::GetFullPath([string]$TargetValue).TrimEnd("\")
        if (-not $CanonicalTarget.StartsWith($ReleasesRoot + "\", [StringComparison]::OrdinalIgnoreCase)) {
            throw "WORKER_CURRENT_INVALID"
        }
        $Target = Get-Item -LiteralPath $CanonicalTarget -Force -ErrorAction Stop
        if (-not $Target.PSIsContainer -or
            ($Target.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
            $Target.Parent.FullName -ne $ReleasesRoot -or
            $Target.Name -notmatch "^[0-9a-f]{40}$") {
            throw "WORKER_CURRENT_INVALID"
        }
        return $Target.FullName
    } catch {
        if ($_.Exception.Message -eq "WORKER_CURRENT_INVALID") { throw }
        throw "WORKER_CURRENT_INVALID"
    }
}
