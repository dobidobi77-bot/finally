# Reset FinAlly to a fresh state: stop the app, DELETE the finally-data volume
# (portfolio, trades, chat history - everything), start again and wait until
# /api/health reports cache_ready. Unrecoverable.
#
# Usage: .\scripts\reset.ps1 [-Yes] [-Test]
#   -Yes   skip the confirmation prompt
#   -Test  restart with docker-compose.test.yml layered in (simulator + mock LLM)
# PowerShell also accepts --yes / --test, so the same invocation works as on bash.
#
# The database lives in the named volume, not under .\db, so the volume must go.
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

if (-not $Yes) {
    Write-Host "This will stop FinAlly and delete the finally-data volume:"
    Write-Host "  cash balance, positions, trade history, watchlist and chat history."
    Write-Host "This cannot be undone."
    $answer = Read-Host "Type 'yes' to continue"
    if ($answer -ne 'yes') {
        Write-Host "Aborted. Nothing was changed."
        exit 1
    }
}

Initialize-DotEnv

Write-Host "Stopping FinAlly and removing the finally-data volume..."
Invoke-Compose -Files $files -Arguments @('down', '-v')

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
Write-Host "FinAlly has been reset and is running at $AppUrl"
