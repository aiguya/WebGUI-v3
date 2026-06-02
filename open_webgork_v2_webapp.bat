@echo off
setlocal
cd /d "%~dp0"

echo Starting WebGork Studio V2 as a standalone web app...
echo.

if exist "%~dp0start_webgork_v2_hermes.bat" (
  call "%~dp0start_webgork_v2_hermes.bat"
) else (
  call "%~dp0run_webgork_app.bat"
)

endlocal
