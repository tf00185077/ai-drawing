$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$CacheRoot = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { $env:USERPROFILE }
$env:UV_NO_MODIFY_PATH = "1"
$env:UV_UNMANAGED_INSTALL = Join-Path $CacheRoot "ai-drawing\uv\0.11.29"
$Uv = Join-Path $env:UV_UNMANAGED_INSTALL "uv.exe"

if (-not (Test-Path $Uv)) {
    Invoke-RestMethod "https://astral.sh/uv/0.11.29/install.ps1" | Invoke-Expression
}

$env:AI_DRAWING_UV_BIN = (Resolve-Path -LiteralPath $Uv).Path

Set-Location $ProjectRoot
& $Uv run --python 3.12 --no-project scripts/bootstrap.py $args
exit $LASTEXITCODE
