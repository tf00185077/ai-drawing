@echo off
setlocal
echo This removes the Worker firewall rule and auto-start task.
echo Runtime and cached models will be moved only after separate confirmation.
pause
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "schtasks.exe /Delete /TN 'AI-Drawing NVIDIA Worker' /F 2>$null; Get-NetFirewallRule -DisplayName 'AI-Drawing NVIDIA Worker' -ErrorAction SilentlyContinue | Remove-NetFirewallRule"
echo Startup and firewall integration removed. C:\AI-Drawing-Worker remains recoverable.
pause
