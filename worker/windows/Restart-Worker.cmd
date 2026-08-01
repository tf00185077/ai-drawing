@echo off
setlocal
title AI-Drawing Worker Restart
schtasks.exe /Run /TN "AI-Drawing NVIDIA Worker Restart" >nul 2>&1
if errorlevel 1 (
  echo FAILED: could not start the fixed privileged restart task.
  pause
  exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%ProgramData%\AI-Drawing-Worker\Wait-Restart-Result.ps1"
exit /b %errorlevel%
