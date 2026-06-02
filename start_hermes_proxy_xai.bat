@echo off
cd /d "%~dp0"
echo Starting Hermes xAI proxy on http://127.0.0.1:8645/v1
echo Keep this window open while using WebGork Studio V2.
echo.
".hermes-venv\Scripts\hermes.exe" proxy start --provider xai --host 127.0.0.1 --port 8645
pause
