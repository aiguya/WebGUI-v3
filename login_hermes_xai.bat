@echo off
cd /d "%~dp0"
echo Starting Hermes xAI OAuth login in manual-code mode...
echo.
echo 1. Open the URL printed by Hermes.
echo 2. Approve/login with xAI or Grok.
echo 3. If the browser shows a code, paste that code back into this window.
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
"%HERMES_EXE%" auth add xai-oauth --type oauth --manual-paste
echo.
echo Login command finished. You can close this window.
pause
