# ============================================================
# MITS — Ollama optimization script for RTX 2080 8GB on Windows
# ============================================================
# Что делает:
#   1. Убивает зомби-процессы Ollama (освобождает VRAM)
#   2. Удаляет сломанный OLLAMA_GPU_OVERHEAD=512m
#   3. Ставит оптимальные env-переменные (persistent через setx)
#   4. Перезапускает Ollama чтобы переменные применились
#   5. Создаёт mits-tutor-9b-fast Modelfile если нужен
#   6. Проверяет что всё загружено
#
# Запусти ОДИН раз:  .\scripts\optimize_ollama.ps1
# ============================================================

Write-Host "==== MITS Ollama Optimizer ====" -ForegroundColor Cyan

# ─── 1. Kill stale Ollama processes ───
Write-Host "`n[1/5] Killing stale Ollama processes..." -ForegroundColor Yellow
$processes = Get-Process -Name "ollama*" -ErrorAction SilentlyContinue
if ($processes) {
    Write-Host "Found $($processes.Count) Ollama processes. Terminating..." -ForegroundColor Gray
    Stop-Process -Name "ollama*" -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    Write-Host "  OK - processes killed" -ForegroundColor Green
} else {
    Write-Host "  No stale processes" -ForegroundColor Green
}

# ─── 2. Remove broken env ───
Write-Host "`n[2/5] Cleaning broken OLLAMA_GPU_OVERHEAD..." -ForegroundColor Yellow
[Environment]::SetEnvironmentVariable("OLLAMA_GPU_OVERHEAD", $null, "User")
[Environment]::SetEnvironmentVariable("OLLAMA_GPU_OVERHEAD", $null, "Machine")
Write-Host "  OK - removed" -ForegroundColor Green

# ─── 3. Set optimal env vars ───
Write-Host "`n[3/5] Setting optimal env vars..." -ForegroundColor Yellow

$vars = @{
    "OLLAMA_FLASH_ATTENTION" = "1"       # FA2 на Turing (SM 7.5)
    "OLLAMA_KV_CACHE_TYPE"   = "q8_0"    # K=V=q8 (безопасно для thinking mode)
    "OLLAMA_KEEP_ALIVE"      = "-1"      # модель НИКОГДА не выгружается
    "OLLAMA_NUM_PARALLEL"    = "1"       # одна сессия — не делим VRAM
    "OLLAMA_MAX_LOADED_MODELS" = "1"     # одна модель в памяти
}

foreach ($k in $vars.Keys) {
    [Environment]::SetEnvironmentVariable($k, $vars[$k], "User")
    Write-Host "  $k = $($vars[$k])" -ForegroundColor Gray
}
Write-Host "  OK - env set (User scope, persistent)" -ForegroundColor Green

# ─── 4. Restart Ollama server ───
Write-Host "`n[4/5] Restarting Ollama..." -ForegroundColor Yellow

# Set for CURRENT session too (setx is persistent but not for this shell)
foreach ($k in $vars.Keys) {
    Set-Item -Path "env:$k" -Value $vars[$k]
}

# Start server in background
Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
Start-Sleep -Seconds 3

$running = Get-Process -Name "ollama*" -ErrorAction SilentlyContinue
if ($running) {
    Write-Host "  OK - Ollama serve running (PID $($running[0].Id))" -ForegroundColor Green
} else {
    Write-Host "  WARNING - Ollama did not start. Run 'ollama serve' manually." -ForegroundColor Red
}

# ─── 5. Create fast Modelfile if not exists ───
Write-Host "`n[5/5] Checking Modelfiles..." -ForegroundColor Yellow

$models = & ollama list 2>&1 | Out-String

if ($models -notmatch "mits-tutor-9b-fast") {
    Write-Host "  Creating mits-tutor-9b-fast from Modelfile.9b-kto-fast..." -ForegroundColor Gray
    & ollama create mits-tutor-9b-fast -f "C:\Work\MITS\training\Modelfile.9b-kto-fast"
    Write-Host "  OK - mits-tutor-9b-fast created" -ForegroundColor Green
} else {
    Write-Host "  mits-tutor-9b-fast already exists" -ForegroundColor Green
}

# ─── Verification ───
Write-Host "`n==== Verification ====" -ForegroundColor Cyan
Write-Host "`nEnv vars in current shell:"
Get-ChildItem env: | Where-Object { $_.Name -like "OLLAMA_*" } | Format-Table -AutoSize

Write-Host "Loaded models:"
& ollama ps

Write-Host "`nTo warm up the model (загрузить в VRAM) выполни:"
Write-Host "  ollama run mits-tutor-9b-fast `"ping`" --verbose" -ForegroundColor Cyan

Write-Host "`n==== Done ====" -ForegroundColor Green
Write-Host "Теперь перезапусти backend:"
Write-Host "  python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload" -ForegroundColor Cyan
