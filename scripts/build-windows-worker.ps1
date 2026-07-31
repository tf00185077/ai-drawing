$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Source = Join-Path $ProjectRoot "worker\windows"
$Destination = Join-Path $ProjectRoot "dist\AI-Drawing-NVIDIA-Worker"

if (Test-Path $Destination) {
    Remove-Item $Destination -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
Copy-Item (Join-Path $Source "*") $Destination -Recurse -Force
Get-ChildItem -Path $Destination -Directory -Recurse -Force |
    Where-Object { $_.Name -eq "__pycache__" } |
    Remove-Item -Recurse -Force
Get-ChildItem -Path $Destination -File -Recurse -Force -Include "*.pyc", "*.pyo" |
    Remove-Item -Force

$Archive = Join-Path $ProjectRoot "dist\AI-Drawing-NVIDIA-Worker.zip"
if (Test-Path $Archive) { Remove-Item $Archive -Force }
Compress-Archive -Path (Join-Path $Destination "*") -DestinationPath $Archive
Write-Host "Built $Archive"
