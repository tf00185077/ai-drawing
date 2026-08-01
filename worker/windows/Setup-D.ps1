$ErrorActionPreference = "Stop"
$Root = "D:\code\AI-Drawing-Worker"

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)) { throw "DIRECT_D_ADMIN_REQUIRED" }

$PreparedMarker = Join-Path $Root ".clean-install-prepared"
if (-not (Test-Path -LiteralPath $PreparedMarker -PathType Leaf)) {
    throw "DIRECT_D_CLEANUP_REQUIRED"
}

$InstallerArguments = @{ Root = $Root }
if (-not (Test-Path -LiteralPath (Join-Path $Root "config\worker.json"))) {
    $InstallerArguments.GenerateNewToken = $true
}
& (Join-Path $PSScriptRoot "Install-Worker.ps1") @InstallerArguments
Remove-Item -LiteralPath $PreparedMarker -Force -ErrorAction Stop
Write-Host "Direct-to-D Worker installation completed."
