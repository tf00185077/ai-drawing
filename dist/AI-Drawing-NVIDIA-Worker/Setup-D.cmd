@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Setup-D.ps1"
if errorlevel 1 (
  echo.
  echo Direct-to-D installation failed. Keep the D Worker directory for diagnosis.
  pause
  exit /b 1
)
echo.
echo AI-Drawing NVIDIA Worker direct-to-D installation completed.
pause
