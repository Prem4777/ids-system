param(
    [string]$BackendBaseUrl = "http://127.0.0.1:8000",
    [string]$DashboardUrl = "http://127.0.0.1:5000",
    [switch]$RequireSensorOnline,
    [switch]$RequireEvents
)

$ErrorActionPreference = "Stop"

function Test-JsonEndpoint {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Url
    )

    try {
        $resp = Invoke-RestMethod -Uri $Url -TimeoutSec 8
        return [pscustomobject]@{
            Name = $Name
            Url = $Url
            Ok = $true
            Detail = "reachable"
            Body = $resp
        }
    }
    catch {
        return [pscustomobject]@{
            Name = $Name
            Url = $Url
            Ok = $false
            Detail = $_.Exception.Message
            Body = $null
        }
    }
}

function Test-HttpEndpoint {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Url
    )

    try {
        $resp = Invoke-WebRequest -Uri $Url -TimeoutSec 8 -UseBasicParsing
        return [pscustomobject]@{
            Name = $Name
            Url = $Url
            Ok = ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 400)
            Detail = "status=$($resp.StatusCode)"
        }
    }
    catch {
        return [pscustomobject]@{
            Name = $Name
            Url = $Url
            Ok = $false
            Detail = $_.Exception.Message
        }
    }
}

$checks = @()
$failures = @()
$warnings = @()

$health = Test-JsonEndpoint -Name "backend_health" -Url "$BackendBaseUrl/health"
$checks += $health
if (-not $health.Ok) {
    $failures += "Backend health endpoint not reachable"
}
else {
    if (-not $health.Body.model_loaded) {
        $failures += "Backend is reachable but model is not loaded"
    }
}

$metadata = Test-JsonEndpoint -Name "backend_metadata" -Url "$BackendBaseUrl/metadata"
$checks += $metadata
if (-not $metadata.Ok) {
    $failures += "Backend metadata endpoint failed"
}

$metrics = Test-JsonEndpoint -Name "backend_metrics" -Url "$BackendBaseUrl/metrics"
$checks += $metrics
if (-not $metrics.Ok) {
    $failures += "Backend metrics endpoint failed"
}

$sensor = Test-JsonEndpoint -Name "backend_sensor_data" -Url "$BackendBaseUrl/sensor-data"
$checks += $sensor
if (-not $sensor.Ok) {
    $failures += "Sensor endpoint failed"
}
elseif ($RequireSensorOnline -and ($sensor.Body.status -ne "online")) {
    $failures += "Sensor is not online (status=$($sensor.Body.status))"
}
elseif ($sensor.Body.status -ne "online") {
    $warnings += "Sensor status is $($sensor.Body.status)"
}

$alert = Test-JsonEndpoint -Name "backend_get_alert" -Url "$BackendBaseUrl/get-alert"
$checks += $alert
if (-not $alert.Ok) {
    $failures += "Alert endpoint failed"
}

$events = Test-JsonEndpoint -Name "backend_events" -Url "$BackendBaseUrl/events?limit=5"
$checks += $events
if (-not $events.Ok) {
    $failures += "Events endpoint failed"
}
else {
    $eventCount = @($events.Body.events).Count
    if ($RequireEvents -and $eventCount -eq 0) {
        $failures += "No prediction events available"
    }
    elseif ($eventCount -eq 0) {
        $warnings += "No prediction events yet (start profiler or traffic simulation)"
    }
}

$dashboard = Test-HttpEndpoint -Name "dashboard_http" -Url $DashboardUrl
$checks += $dashboard
if (-not $dashboard.Ok) {
    $failures += "Dashboard URL not reachable"
}

Write-Host ""
Write-Host "=== IDS Readiness Report ===" -ForegroundColor Cyan
Write-Host "Backend:   $BackendBaseUrl"
Write-Host "Dashboard: $DashboardUrl"
Write-Host ""

foreach ($c in $checks) {
    if ($c.Ok) {
        Write-Host "[PASS] $($c.Name) -> $($c.Detail)" -ForegroundColor Green
    }
    else {
        Write-Host "[FAIL] $($c.Name) -> $($c.Detail)" -ForegroundColor Red
    }
}

if ($warnings.Count -gt 0) {
    Write-Host ""
    Write-Host "Warnings:" -ForegroundColor Yellow
    foreach ($w in $warnings) {
        Write-Host "- $w" -ForegroundColor Yellow
    }
}

if ($failures.Count -gt 0) {
    Write-Host ""
    Write-Host "Final Status: NOT READY" -ForegroundColor Red
    Write-Host "Failures:" -ForegroundColor Red
    foreach ($f in $failures) {
        Write-Host "- $f" -ForegroundColor Red
    }
    exit 1
}

Write-Host ""
Write-Host "Final Status: READY" -ForegroundColor Green
exit 0
