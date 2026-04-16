@echo off
setlocal

set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
set "PY=%ROOT%\.venv\Scripts\python.exe"

if not exist "%PY%" (
  echo [ERROR] Python not found at "%PY%"
  echo Activate/create your venv first.
  exit /b 1
)

echo [INFO] Clearing ports 8000 and 5000 from stale processes...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000,5000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }"

echo [INFO] Starting backend...
start "IDS Backend" "%PY%" -m uvicorn app:app --app-dir "%ROOT%\backend" --host 0.0.0.0 --port 8000

timeout /t 2 >nul

echo [INFO] Starting dashboard...
start "IDS Dashboard" "%PY%" -m streamlit run "%ROOT%\dashboard\app.py" --server.address 0.0.0.0 --server.port 5000

timeout /t 2 >nul

echo [INFO] Starting profiler...
start "IDS Profiler" "%PY%" "%ROOT%\profiler\packet_profiler.py" --api http://127.0.0.1:8000/predict --window-seconds 3

echo.
echo [READY] Started all three services.
echo Backend docs (local): http://127.0.0.1:8000/docs
echo Dashboard (local):    http://127.0.0.1:5000
echo Access from other laptop: http://DEFENDER_IP:8000/docs and http://DEFENDER_IP:5000
echo.
echo Close each opened terminal window to stop a service.

endlocal
