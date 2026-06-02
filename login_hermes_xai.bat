@echo off
cd /d "%~dp0"
echo Starting Hermes xAI OAuth login in manual-code mode...
echo.
echo 1. Open the URL printed by Hermes.
echo 2. Approve/login with xAI or Grok.
echo 3. If the browser shows a code, paste that code back into this window.
echo.
".hermes-venv\Scripts\hermes.exe" auth add xai-oauth --type oauth --manual-paste
echo.
echo Login command finished. You can close this window.
pause
