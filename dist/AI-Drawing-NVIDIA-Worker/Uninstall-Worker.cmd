@echo off
setlocal
for %%T in ("AI-Drawing NVIDIA Worker" "AI-Drawing Worker Updater" "AI-Drawing NVIDIA Worker Restart") do (
  schtasks.exe /Delete /TN "%%~T" /F >nul 2>&1
)
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command ^
  "Get-NetFirewallRule -DisplayName 'AI-Drawing NVIDIA Worker' -ErrorAction SilentlyContinue | Remove-NetFirewallRule; Remove-Item -LiteralPath (Join-Path ([Environment]::GetFolderPath('Desktop')) '一鍵重啟 AI-Drawing Worker.cmd') -Force -ErrorAction SilentlyContinue"
echo Startup tasks and firewall integration removed. Worker roots, releases, backups, configuration, and shared data were retained.
