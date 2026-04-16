param(
  [Parameter(Mandatory=$true)][string]$TargetIp,
  [int]$Port = 8000,
  [string]$EndpointPaths = "/health,/metadata,/events?limit=20",
  [double]$RequestRate = 120,
  [double]$JitterMs = 4
)

python normal_traffic.py --target $TargetIp --port $Port --duration 180 --interval 1.0
python burst_traffic.py --target $TargetIp --port $Port --rounds 3 --burst-seconds 20 --cooldown-seconds 15 --workers 40 --endpoint-paths $EndpointPaths --request-rate $RequestRate --jitter-ms $JitterMs
python normal_traffic.py --target $TargetIp --port $Port --duration 120 --interval 1.0