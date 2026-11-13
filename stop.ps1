$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
docker compose --profile miniapp stop
if ($LASTEXITCODE -ne 0) { throw 'Could not stop all services.' }
Write-Host 'Services stopped. Database volume and financial history are preserved.'
