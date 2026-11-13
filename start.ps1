param([switch]$MiniApp)
$ErrorActionPreference = 'Stop'
if ($MiniApp) { & (Join-Path $PSScriptRoot 'start-miniapp.ps1'); exit }
Set-Location $PSScriptRoot
if (!(Test-Path -LiteralPath '.env')) { throw 'Create .env from .env.example and configure API keys first.' }
docker info --format '{{.ServerVersion}}' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop and run this script again.' }
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { throw 'Service startup failed. Run docker compose logs --tail 50.' }
Write-Host 'Finance AI: http://localhost:3000'
Write-Host 'Telegram connection: http://localhost:3000/telegram'
Write-Host 'Health: http://localhost:8000/api/v1/health'
