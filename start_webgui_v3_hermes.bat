@echo off
setlocal
cd /d "%~dp0"

set "APP_URL=http://127.0.0.1:7863"
set "HERMES_PROXY_URL=http://127.0.0.1:8645/v1"
set "HERMES_EXE=%~dp0.hermes-venv\Scripts\hermes.exe"

if not exist "%HERMES_EXE%" (
  echo Hermes executable was not found:
  echo %HERMES_EXE%
  echo.
  echo Run the Hermes setup in this V3 folder first.
  pause
  exit /b 1
)

echo Checking Hermes xAI OAuth login...
"%HERMES_EXE%" auth status xai-oauth > "%TEMP%\webgui_v3_hermes_auth_status.txt" 2>&1
findstr /i /c:"logged out" "%TEMP%\webgui_v3_hermes_auth_status.txt" >nul 2>nul
if %errorlevel%==0 (
  echo.
  echo xAI OAuth login is required.
  echo Use the Hermes xAI OAuth panel inside WebGUI.v3 to finish login.
) else (
  echo Hermes xAI OAuth is already logged in.
)

echo.
echo Configuring WebGUI.v3 to use Hermes Proxy...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p='webgork-settings.json'; $s=@{}; if(Test-Path $p){ try { $s=Get-Content $p -Raw | ConvertFrom-Json -AsHashtable } catch { $s=@{} } }; $s.provider='hermes_proxy'; $s.hermes_base_url='%HERMES_PROXY_URL%'; $s.Remove('hermes_api_key'); $s | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $p" >nul 2>nul
powershell -NoProfile -ExecutionPolicy Bypass -Command "$body=@{provider='hermes_proxy';hermes_base_url='%HERMES_PROXY_URL%';hermes_api_key='';clear_hermes_api_key=$true}|ConvertTo-Json; try { Invoke-RestMethod -Uri '%APP_URL%/api/settings/provider' -Method Post -ContentType 'application/json' -Body $body | Out-Null } catch {}" >nul 2>nul

echo.
echo Ensuring Hermes xAI proxy is running...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$client = New-Object Net.Sockets.TcpClient; try { $iar = $client.BeginConnect('127.0.0.1',8645,$null,$null); if($iar.AsyncWaitHandle.WaitOne(400)){ $client.EndConnect($iar); exit 0 } else { exit 1 } } catch { exit 1 } finally { $client.Close() }" >nul 2>nul
if not %errorlevel%==0 (
  "%HERMES_EXE%" auth status xai-oauth > "%TEMP%\webgui_v3_hermes_auth_status.txt" 2>&1
  findstr /i /c:"logged out" "%TEMP%\webgui_v3_hermes_auth_status.txt" >nul 2>nul
  if errorlevel 1 (
    start "Hermes xAI Proxy" cmd /k ""%HERMES_EXE%" proxy start --provider xai --host 127.0.0.1 --port 8645"
  ) else (
    echo Hermes proxy will start automatically after login completes.
  )
) else (
  echo Hermes proxy is already running.
)

echo.
echo Starting WebGUI.v3...
call "%~dp0run_webgork_app.bat"

endlocal