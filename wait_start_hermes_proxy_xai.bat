@echo off
setlocal
cd /d "%~dp0"

set "HERMES_EXE=%~dp0.hermes-venv\Scripts\hermes.exe"

echo Waiting for Hermes xAI OAuth login...
for /l %%i in (1,1,600) do (
  "%HERMES_EXE%" auth status xai-oauth > "%TEMP%\webgork_hermes_auth_wait.txt" 2>&1
  findstr /i /c:"logged out" "%TEMP%\webgork_hermes_auth_wait.txt" >nul 2>nul
  if errorlevel 1 goto logged_in
  timeout /t 1 /nobreak >nul
)

echo Timed out waiting for xAI OAuth login.
pause
exit /b 1

:logged_in
echo Hermes xAI OAuth login detected.
echo Starting Hermes xAI proxy on http://127.0.0.1:8645/v1
"%HERMES_EXE%" proxy start --provider xai --host 127.0.0.1 --port 8645
pause
