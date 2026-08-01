$ErrorActionPreference = "SilentlyContinue"
$Started = Get-Date
$Deadline = $Started.AddSeconds(125)
$EnvironmentPath = Join-Path $env:ProgramData "AI-Drawing-Worker\updater.env"
$Root = $null
foreach ($Line in [IO.File]::ReadAllLines($EnvironmentPath)) {
    if (-not $Line -or $Line.StartsWith("#")) { continue }
    $Parts = $Line -split '=', 2
    if ($Parts.Count -eq 2 -and $Parts[0] -eq "AI_DRAWING_WORKER_ROOT") { $Root = $Parts[1] }
}
if (-not $Root -or -not [IO.Path]::IsPathRooted($Root) -or $Root.StartsWith("\\")) {
    Write-Host "FAILED: restart configuration is invalid." -ForegroundColor Red
    pause
    exit 1
}
$Root = [IO.Path]::GetFullPath($Root)
$Path = Join-Path $Root "config\update-owned\state\restart-status.json"
$SeenRequest = $null
while ((Get-Date) -lt $Deadline) {
    if (Test-Path -LiteralPath $Path) {
        $Item = Get-Item -LiteralPath $Path
        $Result = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($Item.LastWriteTime -ge $Started -and $Result.request_id) { $SeenRequest = $Result.request_id }
        if ($SeenRequest -and $Result.request_id -eq $SeenRequest) {
            if ($Result.state -eq "ready") { Write-Host "READY" -ForegroundColor Green; exit 0 }
            if ($Result.state -in @("failed", "timed_out")) {
                Write-Host ("FAILED: " + $Result.error_code) -ForegroundColor Red
                Write-Host ("Logs: " + (Join-Path $Root "config\update-owned\restart"))
                pause
                exit 1
            }
        }
    }
    Start-Sleep -Seconds 1
}
Write-Host "FAILED: restart status timed out." -ForegroundColor Red
pause
exit 1
