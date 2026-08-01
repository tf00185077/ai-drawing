$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Builder = Join-Path $PSScriptRoot "build-windows-worker.py"
$Python = Get-Command py.exe -ErrorAction SilentlyContinue
if ($Python) {
    & $Python.Source -3.11 $Builder
} else {
    $Python = Get-Command python.exe -ErrorAction Stop
    & $Python.Source $Builder
}
if ($LASTEXITCODE -ne 0) { throw "Windows Worker distribution build failed." }
