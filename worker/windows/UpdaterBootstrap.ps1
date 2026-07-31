$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProgramDataRoot = Join-Path $env:ProgramData "AI-Drawing-Worker"
$ConfigPath = Join-Path $ProgramDataRoot "updater.env"
$AllowedKeys = @{
    "AI_DRAWING_PROJECT_ROOT" = $true
    "AI_DRAWING_WORKER_ROOT" = $true
    "AI_DRAWING_WORKER_REMOTE" = $true
    "AI_DRAWING_WORKER_BRANCH" = $true
}
$Values = @{}

foreach ($Line in Get-Content -LiteralPath $ConfigPath -Encoding UTF8) {
    if ($Line.Length -eq 0 -or $Line.StartsWith("#")) { continue }
    $Separator = $Line.IndexOf("=")
    if ($Separator -le 0) { throw "Malformed updater environment line." }
    $Key = $Line.Substring(0, $Separator)
    $Value = $Line.Substring($Separator + 1)
    if (-not $AllowedKeys.ContainsKey($Key)) { throw "Unknown updater environment key." }
    if ($Values.ContainsKey($Key)) { throw "Duplicate updater environment key." }
    if ($Key.Trim() -ne $Key -or $Value.Trim() -ne $Value) {
        throw "Padded updater environment entry."
    }
    $Values[$Key] = $Value
}

foreach ($RequiredKey in $AllowedKeys.Keys) {
    if (-not $Values.ContainsKey($RequiredKey) -or -not $Values[$RequiredKey]) {
        throw "Missing updater environment entry."
    }
}

$WorkerRootRaw = [string]$Values["AI_DRAWING_WORKER_ROOT"]
if (-not [IO.Path]::IsPathRooted($WorkerRootRaw) -or $WorkerRootRaw.StartsWith("\\")) {
    throw "Worker root must be a local absolute path."
}
$WorkerRoot = (Resolve-Path -LiteralPath $WorkerRootRaw -ErrorAction Stop).Path
$OwnershipMarker = Join-Path $WorkerRoot ".ai-drawing-worker-owned"
if ((Get-Content -LiteralPath $OwnershipMarker -Raw -Encoding UTF8).Trim() -ne "AI-Drawing NVIDIA Worker") {
    throw "Worker ownership marker is invalid."
}

$UpdaterPythonCandidate = Join-Path $WorkerRoot "updater-runtime\Scripts\python.exe"
$UpdaterPython = (Resolve-Path -LiteralPath $UpdaterPythonCandidate -ErrorAction Stop).Path
$WorkerPrefix = $WorkerRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
if (-not $UpdaterPython.StartsWith($WorkerPrefix, [StringComparison]::OrdinalIgnoreCase) -or -not (Test-Path -LiteralPath $UpdaterPython -PathType Leaf)) {
    throw "Updater-owned Python is invalid."
}

Push-Location $WorkerRoot
try {
    & $UpdaterPython -m updater.cli
    $UpdaterExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $UpdaterExitCode
