$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Python executable not found at $python"
}

# Free common ports from stale runs.
Get-NetTCPConnection -LocalPort 8000,5000 -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }

Start-Sleep -Seconds 1

# Start backend in a new PowerShell window.
$backendCmd = "cd '$root\backend'; & '$python' -m uvicorn app:app --host 0.0.0.0 --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd | Out-Null

Start-Sleep -Seconds 2

# Start dashboard in a new PowerShell window.
$dashCmd = "cd '$root\dashboard'; & '$python' -m streamlit run app.py --server.address 0.0.0.0 --server.port 5000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $dashCmd | Out-Null

Start-Sleep -Seconds 2

Write-Host "Backend docs (local): http://127.0.0.1:8000/docs"
Write-Host "Dashboard (local):    http://127.0.0.1:5000"
Write-Host "Access from other laptop: http://DEFENDER_IP:8000/docs and http://DEFENDER_IP:5000"
