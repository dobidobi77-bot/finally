# Shared helpers for scripts/*.ps1. Dot-source it; do not run it directly.
#
#   . (Join-Path $PSScriptRoot 'common.ps1')
#
# Windows PowerShell 5.1 compatible: no &&, no ternary, no null-coalescing.
# Sets $Root, cds into it, and defines:
#   Invoke-Compose -Arguments @(...) [-Files @(...)]   run docker compose
#   Initialize-DotEnv                                  create .env when missing
#   Wait-ForHealth -TimeoutSec N                       poll /api/health

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$AppUrl = 'http://localhost:8000'
$TestFiles = @('docker-compose.yml', 'docker-compose.test.yml')

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "docker is not installed or not on PATH."
    exit 1
}

# Prefer the compose plugin ('docker compose'); fall back to the standalone
# 'docker-compose' binary. Probing runs with EAP relaxed because Windows
# PowerShell turns native stderr into terminating errors when EAP is 'Stop'.
$ComposeExe = 'docker'
$ComposePrefix = @('compose')
$previousEap = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    & docker compose version 2>&1 | Out-Null
    $pluginOk = ($LASTEXITCODE -eq 0)
} catch {
    $pluginOk = $false
}
$ErrorActionPreference = $previousEap

if (-not $pluginOk) {
    if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
        $ComposeExe = 'docker-compose'
        $ComposePrefix = @()
    } else {
        Write-Error "Neither 'docker compose' nor 'docker-compose' is available."
        exit 1
    }
}

function Invoke-Compose {
    <# Run a compose command; exits the script with compose's code on failure. #>
    param(
        [string[]]$Arguments,
        [string[]]$Files = @()
    )
    $all = @() + $ComposePrefix
    foreach ($f in $Files) {
        $all += @('-f', $f)
    }
    $all += $Arguments
    & $ComposeExe @all
    if ($LASTEXITCODE -ne 0) {
        Write-Error "docker compose $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
        exit $LASTEXITCODE
    }
}

function Initialize-DotEnv {
    if (-not (Test-Path '.env')) {
        Write-Host "No .env found - creating one from .env.example."
        Write-Host "Edit .env and add your OPENROUTER_API_KEY to enable the AI chat."
        Copy-Item '.env.example' '.env'
    }
}

function Wait-ForHealth {
    <# Poll /api/health until cache_ready is true. Returns $true, or $false on timeout. #>
    param([int]$TimeoutSec = 120)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    $last = '<none>'
    Write-Host "Waiting for $AppUrl/api/health (up to ${TimeoutSec}s)..."
    while ((Get-Date) -lt $deadline) {
        try {
            $body = Invoke-RestMethod -Uri "$AppUrl/api/health" -TimeoutSec 5
            $last = ($body | ConvertTo-Json -Compress)
            if ($body.cache_ready -eq $true) {
                Write-Host "Healthy: $last"
                return $true
            }
        } catch {
            $last = "no response ($($_.Exception.GetType().Name))"
        }
        Start-Sleep -Seconds 1
    }
    Write-Host "ERROR: app not healthy after ${TimeoutSec}s. Last response: $last"
    Write-Host "Logs: docker compose logs"
    return $false
}
