@echo off
setlocal
if not exist "%~dp0shared\logs" mkdir "%~dp0shared\logs"
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0Start-Worker.ps1" 1>>"%~dp0shared\logs\launcher.stdout.log" 2>>"%~dp0shared\logs\launcher.stderr.log"
