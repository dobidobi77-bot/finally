# Stop FinAlly. Idempotent. Never removes the database.
# Usage: .\scripts\stop.ps1
# Windows PowerShell 5.1 compatible.
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'common.ps1')

# 'down' without -v leaves the finally-data volume untouched.
Invoke-Compose -Arguments @('down')

Write-Host "FinAlly stopped. The finally-data volume is untouched."
