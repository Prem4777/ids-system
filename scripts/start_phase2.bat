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

rem Phase 2 baseline: keep scan and burst hybrid overrides, disable slow override.
set "IDS_ENABLE_SCAN_OVERRIDE=1"
set "IDS_ENABLE_BURST_OVERRIDE=1"
set "IDS_ENABLE_SLOW_OVERRIDE=0"

echo [INFO] Starting Phase 2 mode (IoT optional)...
echo [INFO] Clearing ports 8000 and 5000 from stale processes...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000,5000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }"

echo [INFO] Starting backend...
start "IDS Backend (Phase2)" "%PY%" -m uvicorn app:app --app-dir "%ROOT%\backend" --host 0.0.0.0 --port 8000

timeout /t 2 >nul

echo [INFO] Starting dashboard...
start "IDS Dashboard (Phase2)" "%PY%" -m streamlit run "%ROOT%\dashboard\app.py" --server.address 0.0.0.0 --server.port 5000

timeout /t 2 >nul

echo [INFO] Starting profiler...
start "IDS Profiler (Phase2)" "%PY%" "%ROOT%\profiler\packet_profiler.py" --api http://127.0.0.1:8000/predict --window-seconds 3

echo.
echo [READY] Phase 2 stack started.
echo Backend docs (local): http://127.0.0.1:8000/docs
echo Dashboard (local):    http://127.0.0.1:5000
echo Use target 127.0.0.1 for same-laptop simulation.
echo.
echo Close each opened terminal window to stop a service.

endlocal
