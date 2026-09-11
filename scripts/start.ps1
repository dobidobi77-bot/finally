# Start FinAlly. Idempotent - safe to run repeatedly.
# Usage: .\scripts\start.ps1 [-Build] [-Open]
#   -Build  rebuild the image before starting
#   -Open   open http://localhost:8000 in the default browser once healthy
# Windows PowerShell 5.1 compatible.
[CmdletBinding()]
param(
    [switch]$Build,
    [switch]$Open
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'common.ps1')

Initialize-DotEnv

$composeArgs = @('up', '-d')
if ($Build) {
    $composeArgs += '--build'
}
Invoke-Compose -Arguments $composeArgs

Write-Host ""
Write-Host "FinAlly is starting at $AppUrl"
Write-Host "Logs:  docker compose logs -f"
Write-Host "Stop:  .\scripts\stop.ps1"
Write-Host "Reset: .\scripts\reset.ps1   (wipes the portfolio)"

if ($Open) {
    if (Wait-ForHealth -TimeoutSec 120) {
        Start-Process $AppUrl
    }
}
