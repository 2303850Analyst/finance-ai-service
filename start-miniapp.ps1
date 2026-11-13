param([switch]$SkipBuild)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (!(Test-Path -LiteralPath '.env')) { throw 'Configure .env first.' }
docker info --format '{{.ServerVersion}}' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop first.' }
if ($SkipBuild) { docker compose --profile miniapp up -d postgres backend telegram frontend miniapp-gateway }
else { docker compose --profile miniapp up -d --build postgres backend telegram frontend miniapp-gateway }
if ($LASTEXITCODE -ne 0) { throw 'Could not start Mini App services.' }

function Get-StatusCode([string]$Address) {
    try { return [int](Invoke-WebRequest -Uri $Address -UseBasicParsing -TimeoutSec 5).StatusCode }
    catch { if ($_.Exception.Response) { return [int]$_.Exception.Response.StatusCode }; return 0 }
}
$ready = $false
for ($attempt = 0; $attempt -lt 90; $attempt++) {
    if ((Get-StatusCode 'http://127.0.0.1:8080/miniapp') -eq 200) { $ready = $true; break }
    Start-Sleep -Seconds 2
}
if (!$ready) { throw 'Mini App is not ready. Check service logs.' }
if ((Get-StatusCode 'http://127.0.0.1:8080/api/v1/miniapp/bootstrap') -ne 401) { throw 'Telegram authentication check failed. External access was not started.' }
if ((Get-StatusCode 'http://127.0.0.1:8080/api/v1/accounts') -ne 404) { throw 'Local route isolation check failed. External access was not started.' }
docker compose --profile miniapp up -d cloudflared
if ($LASTEXITCODE -ne 0) { throw 'Could not start the HTTPS connection.' }
$publicOrigin = $null
for ($attempt = 0; $attempt -lt 60; $attempt++) {
    $tunnelLog = docker compose --profile miniapp logs --no-color --tail 100 cloudflared 2>&1 | Out-String
    $urls = [regex]::Matches($tunnelLog, 'https://[a-z0-9-]+\.trycloudflare\.com')
    if ($urls.Count -gt 0) { $publicOrigin = $urls[$urls.Count - 1].Value; break }
    Start-Sleep -Seconds 2
}
if (!$publicOrigin) { throw 'No temporary HTTPS address was received. Retry when the network is available.' }
$miniappAddress = $publicOrigin + '/miniapp'
$publicReady = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    if ((Get-StatusCode $miniappAddress) -eq 200) { $publicReady = $true; break }
    Start-Sleep -Seconds 2
}
if (!$publicReady) { throw 'The HTTPS address is not reachable yet. Retry before updating the Telegram menu.' }
if ((Get-StatusCode ($publicOrigin + '/api/v1/miniapp/bootstrap')) -ne 401 -or
    (Get-StatusCode ($publicOrigin + '/api/v1/accounts')) -ne 404) {
    docker compose --profile miniapp stop cloudflared | Out-Null
    throw 'Public access checks failed. The HTTPS connection was stopped.'
}
docker compose exec -T -e "MINIAPP_URL=$miniappAddress" backend python -m app.configure_miniapp
if ($LASTEXITCODE -ne 0) { throw 'Could not update the Telegram menu. Check Telegram binding and network access.' }
$runtime = @{ url = $miniappAddress; updated_at = [DateTime]::UtcNow.ToString('o') } | ConvertTo-Json
[IO.File]::WriteAllText((Join-Path $PSScriptRoot '.miniapp-runtime.json'), $runtime, [Text.UTF8Encoding]::new($false))
Write-Host 'Mini App is ready. Open the bot and press Open FinAI.'
Write-Host $miniappAddress
Write-Host 'Keep this computer and Docker running. After a tunnel restart run this script again to refresh the menu.'
