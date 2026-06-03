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
  pause
  exit /b 1
)

%PYTHON_CMD% -c "import flask, requests, dotenv, imageio_ffmpeg" >nul 2>nul
if not %errorlevel%==0 (
  echo Installing required Python packages...
  %PYTHON_CMD% -m pip install -r requirements.txt
  if not %errorlevel%==0 (
    echo Failed to install requirements.
    pause
    exit /b 1
  )
)

powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing http://127.0.0.1:7863/health -TimeoutSec 2 > $null; exit 0 } catch { exit 1 }" >nul 2>nul
if not %errorlevel%==0 (
  echo Starting WebGUI.v3 server...
  start "WebGUI.v3 Server" /min cmd /c "set WEBGORK_OPEN_BROWSER=0&& set WEBGORK_PORT=7863&& %PYTHON_CMD% app.py"
  powershell -NoProfile -Command "$ok=$false; for($i=0; $i -lt 30; $i++){ try { Invoke-WebRequest -UseBasicParsing http://127.0.0.1:7863/health -TimeoutSec 1 > $null; $ok=$true; break } catch { Start-Sleep -Milliseconds 500 } }; if(-not $ok){ exit 1 }"
  if not %errorlevel%==0 (
    echo Server did not start.
    pause
    exit /b 1
  )
)

set "CHROME_EXE="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME_EXE=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not defined CHROME_EXE if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME_EXE=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not defined CHROME_EXE if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set "CHROME_EXE=%LocalAppData%\Google\Chrome\Application\chrome.exe"

if defined CHROME_EXE (
  start "" "%CHROME_EXE%" --app=http://127.0.0.1:7863/?v=20260604-v3-30 --class=WebGUIv3
) else (
  start "" http://127.0.0.1:7863/?v=20260604-v3-30
)

endlocal
