<#
.SYNOPSIS
  Temporarily expose the MITS app to the internet via Cloudflare Tunnel (TryCloudflare).

.DESCRIPTION
  Free, HTTPS, no router/port-forwarding, fully reversible (closes when you Ctrl+C / close the
  windows). Opens TWO quick tunnels — one for the backend (:8000), one for the frontend (:3000) —
  rewrites frontend/.env.local to point at the backend tunnel, (re)starts the frontend, and prints
  the public URL.

  PREREQUISITES (start these FIRST, in separate windows):
    1. llama-server / llama-swap on :8090   (your C:\OpenCode infra)
    2. backend:  .venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
       (must include the CORS-regex change so the tunnel origin is allowed)

  SECURITY: this is OPEN — anyone with the link can register and use your 1-2 LLM slots.
  Share the link narrowly, and close the tunnels right after the demo.
    To lock it down instead, use a Cloudflare *named* tunnel + Cloudflare Access (password/email).

.NOTES
  Run from repo root:  powershell -ExecutionPolicy Bypass -File scripts\expose_public.ps1
#>

$ErrorActionPreference = "Stop"
$root = "C:\Work\MITS"

# 1. cloudflared present? (install via winget if missing)
if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
    Write-Host "cloudflared not found - installing via winget..." -ForegroundColor Yellow
    winget install --id Cloudflare.cloudflared -e --accept-source-agreements --accept-package-agreements
    if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
        Write-Error "cloudflared still not on PATH. Install manually: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/  then re-run."
        exit 1
    }
}

# 2. backend reachable?
try {
    Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/health" -TimeoutSec 5 | Out-Null
    Write-Host "backend :8000 OK" -ForegroundColor Green
} catch {
    Write-Error "Backend :8000 не отвечает. Сначала подними llama-server (:8090) и backend (uvicorn), затем перезапусти скрипт."
    exit 1
}

function Start-QuickTunnel([int]$port, [string]$logName) {
    $log = Join-Path $env:TEMP $logName
    if (Test-Path $log) { Remove-Item $log -Force }
    # --protocol http2 forces a TCP edge connection. QUIC (UDP 7844) is blocked/throttled on
    # many ISPs/routers -> "failed to dial to edge with quic: timeout" -> 502s. http2 gets through.
    Start-Process cloudflared `
        -ArgumentList "tunnel --protocol http2 --url http://localhost:$port --no-autoupdate" `
        -RedirectStandardError $log -WindowStyle Hidden -PassThru | Out-Null
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Seconds 1
        if (Test-Path $log) {
            $m = Select-String -Path $log -Pattern "https://[-a-z0-9]+\.trycloudflare\.com" -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($m) { return $m.Matches[0].Value }
        }
    }
    Write-Error "Не удалось получить URL туннеля для порта $port (лог: $log)"
    exit 1
}

# 3. backend tunnel -> public HTTPS URL
$backendUrl = Start-QuickTunnel 8000 "cf_backend.log"
$backendHost = ([Uri]$backendUrl).Host
Write-Host "backend public:  $backendUrl" -ForegroundColor Cyan

# 4. point the frontend at the backend tunnel (API over https, WS over wss)
@"
NEXT_PUBLIC_API_URL=$backendUrl
NEXT_PUBLIC_WS_URL=wss://$backendHost
"@ | Set-Content -Path (Join-Path $root "frontend\.env.local") -Encoding utf8
Write-Host "frontend/.env.local -> $backendUrl" -ForegroundColor Green

# 5. start the frontend (reads the fresh .env.local on boot)
# npm is a .cmd shim on Windows -> launch via cmd.exe so it runs reliably and we capture a log.
$feLog = Join-Path $env:TEMP "mits_frontend.log"
if (Test-Path $feLog) { Remove-Item $feLog -Force }
Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c npm run dev -- -p 3000 > `"$feLog`" 2>&1" `
    -WorkingDirectory (Join-Path $root "frontend") -WindowStyle Minimized
Write-Host "frontend starting on :3000 (waiting for it to listen)..." -ForegroundColor Yellow
$feUp = $false
for ($i = 0; $i -lt 90; $i++) {
    Start-Sleep -Seconds 1
    if (Get-NetTCPConnection -State Listen -LocalPort 3000 -ErrorAction SilentlyContinue) { $feUp = $true; break }
}
if (-not $feUp) { Write-Error "Frontend не поднялся на :3000 за 90с (лог: $feLog)"; exit 1 }
Write-Host "frontend listening on :3000" -ForegroundColor Green

# 6. frontend tunnel -> the public site URL
$frontUrl = Start-QuickTunnel 3000 "cf_frontend.log"

Write-Host "`n=====================================================" -ForegroundColor Green
Write-Host "  ПУБЛИЧНЫЙ АДРЕС САЙТА (делись только с кем нужно):" -ForegroundColor Green
Write-Host "  $frontUrl" -ForegroundColor White
Write-Host "=====================================================" -ForegroundColor Green
Write-Host "Бэкенд-туннель: $backendUrl"
Write-Host "Остановить доступ: закрой окна cloudflared (или Stop-Process -Name cloudflared)."
Write-Host "После демо верни frontend/.env.local на LAN-IP, если нужно."
