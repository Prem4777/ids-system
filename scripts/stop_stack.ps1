# Stop backend and dashboard listeners.
Get-NetTCPConnection -LocalPort 8000,5000 -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }

Write-Host "Stopped listeners on ports 8000 and 5000 (if any)."
