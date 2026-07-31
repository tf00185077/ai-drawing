@echo off
setlocal
set "AI_DRAWING_WORKER_ROOT=C:\AI-Drawing-Worker"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%AI_DRAWING_WORKER_ROOT%\Start-Worker.ps1"
