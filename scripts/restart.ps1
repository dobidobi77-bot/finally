# Restart FinAlly WITHOUT touching the database, and wait until /api/health
# reports cache_ready. The opposite of reset.ps1.
#
# Usage: .\scripts\restart.ps1 [-Yes] [-Test]
#   -Yes   accepted for symmetry with reset.ps1; there is nothing to confirm
#   -Test  restart with docker-compose.test.yml layered in (simulator + mock LLM)
# PowerShell also accepts --yes / --test.
# Windows PowerShell 5.1 compatible.
[CmdletBinding()]
param(
    [switch]$Yes,
    [switch]$Test
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'common.ps1')

$files = @('docker-compose.yml')
if ($Test) {
    $files = $TestFiles
}

Initialize-DotEnv

# 'down' without -v leaves the finally-data volume untouched.
Write-Host "Stopping FinAlly (data is kept)..."
Invoke-Compose -Files $files -Arguments @('down')

if ($Test) {
    Write-Host "Starting FinAlly in test mode (simulator, mock LLM)..."
} else {
    Write-Host "Starting FinAlly..."
}
Invoke-Compose -Files $files -Arguments @('up', '-d')

if (-not (Wait-ForHealth -TimeoutSec 120)) {
    exit 1
}

Write-Host ""
Write-Host "FinAlly restarted at $AppUrl"
