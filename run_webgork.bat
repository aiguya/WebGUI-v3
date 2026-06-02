@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_CMD="
if exist "%LocalAppData%\Python\pythoncore-3.14-64\python.exe" (
  set "PYTHON_CMD=%LocalAppData%\Python\pythoncore-3.14-64\python.exe"
)

where py >nul 2>nul
if not defined PYTHON_CMD if %errorlevel%==0 (
  py -3 -c "import sys" >nul 2>nul
  if %errorlevel%==0 set "PYTHON_CMD=py -3"
)

if not defined PYTHON_CMD (
  where python >nul 2>nul
  if %errorlevel%==0 (
    python -c "import sys" >nul 2>nul
    if %errorlevel%==0 set "PYTHON_CMD=python"
  )
)

if not defined PYTHON_CMD (
  where python3 >nul 2>nul
  if %errorlevel%==0 (
    python3 -c "import sys" >nul 2>nul
    if %errorlevel%==0 set "PYTHON_CMD=python3"
  )
)

if not defined PYTHON_CMD (
  echo Python was not found.
  echo.
  echo Install Python 3.10 or newer from:
  echo https://www.python.org/downloads/
  echo.
  echo During installation, enable "Add python.exe to PATH".
  pause
  exit /b 1
)

%PYTHON_CMD% -c "import flask, requests, dotenv, imageio_ffmpeg" >nul 2>nul
if not %errorlevel%==0 (
  echo Installing required Python packages...
  %PYTHON_CMD% -m pip install -r requirements.txt
  if not %errorlevel%==0 (
    echo.
    echo Failed to install requirements.
    pause
    exit /b 1
  )
)

echo Starting WebGUI.v3...
echo URL: http://127.0.0.1:7863
echo.
echo Keep this window open while using WebGUI.
echo Press Ctrl+C in this window to stop the server.
echo.

set "WEBGORK_OPEN_BROWSER=1"
set "WEBGORK_PORT=7863"
%PYTHON_CMD% app.py

echo.
echo WebGUI stopped.
pause
