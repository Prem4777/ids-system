param(
  [Parameter(Mandatory=$true)][string]$TargetIp,
  [int]$Port = 8000,
  [string]$EndpointPaths = "/health,/metadata,/events?limit=20",
  [double]$BurstRate = 150,
  [double]$BurstJitterMs = 5
)

Write-Host "[PHASE] Baseline normal" -ForegroundColor Cyan
python normal_traffic.py --target $TargetIp --port $Port --duration 90 --interval 1.0

Write-Host "[PHASE] Scanning-like" -ForegroundColor Yellow
python scan_traffic.py --target $TargetIp --ports "20-120,443,5000,8000" --rounds 3 --delay-ms 6 --timeout 0.2 --cooldown-seconds 6

Write-Host "[PHASE] Recovery normal" -ForegroundColor Cyan
python normal_traffic.py --target $TargetIp --port $Port --duration 60 --interval 1.0

Write-Host "[PHASE] Slow-and-low abuse" -ForegroundColor Yellow
python slow_traffic.py --target $TargetIp --port $Port --duration 180 --interval 0.12 --paths $EndpointPaths

Write-Host "[PHASE] Recovery normal" -ForegroundColor Cyan
python normal_traffic.py --target $TargetIp --port $Port --duration 60 --interval 1.0

Write-Host "[PHASE] DoS burst" -ForegroundColor Red
python burst_traffic.py --target $TargetIp --port $Port --rounds 3 --burst-seconds 20 --cooldown-seconds 12 --workers 40 --endpoint-paths $EndpointPaths --request-rate $BurstRate --jitter-ms $BurstJitterMs

Write-Host "[PHASE] Final recovery normal" -ForegroundColor Cyan
python normal_traffic.py --target $TargetIp --port $Port --duration 90 --interval 1.0

Write-Host "[DONE] Multi-attack scenario complete" -ForegroundColor Green
