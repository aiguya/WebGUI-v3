@echo off
setlocal
cd /d "%~dp0"

echo Starting WebGUI.v3 as a standalone web app...
echo.

if exist "%~dp0start_webgui_v3_hermes.bat" (
  call "%~dp0start_webgui_v3_hermes.bat"
) else (
  call "%~dp0run_webgork_app.bat"
)

endlocal