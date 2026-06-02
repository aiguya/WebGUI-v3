@echo off
cd /d "%~dp0"
echo Starting Hermes xAI proxy on http://127.0.0.1:8645/v1
echo Keep this window open while using WebGUI.v3.
echo.
if not defined HERMES_EXE set "HERMES_EXE=%~dp0.hermes-venv\Scripts\hermes.exe"
if not exist "%HERMES_EXE%" set "HERMES_EXE=%~dp0vendor\hermes-agent\venv\Scripts\hermes.exe"
if not exist "%HERMES_EXE%" set "HERMES_EXE=%~dp0..\https-gall-dcinside-com-mgallery-board-Version-2\.hermes-venv\Scripts\hermes.exe"
if not exist "%HERMES_EXE%" set "HERMES_EXE=%~dp0..\https-gall-dcinside-com-mgallery-board-Version-2\vendor\hermes-agent\venv\Scripts\hermes.exe"
if not exist "%HERMES_EXE%" (
  echo Hermes executable was not found.
  pause
  exit /b 1
)
"%HERMES_EXE%" proxy start --provider xai --host 127.0.0.1 --port 8645
pause
