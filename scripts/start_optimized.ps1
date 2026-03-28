# MITS Optimized Launcher
# Hardware: Ryzen 9 9950x + 32GB RAM + RTX 2080 8GB

param(
    [switch]$SetupModel,
    [switch]$OllamaOnly
)

$Host.UI.RawUI.WindowTitle = "MITS"

Write-Host ""
Write-Host "  MITS - Optimized for your hardware" -ForegroundColor Cyan
Write-Host "  Ryzen 9 9950x | 32GB RAM | RTX 2080 8GB" -ForegroundColor DarkGray
Write-Host ""

# ─────────────────────────────────────────────────────────────
# Environment Setup
# ─────────────────────────────────────────────────────────────

# Copy optimized config
if (Test-Path ".env.optimized") {
    Copy-Item ".env.optimized" ".env" -Force
    Write-Host "  [OK] Loaded optimized config" -ForegroundColor Green
}

# Ollama environment
$env:OLLAMA_NUM_THREADS = "16"
$env:OLLAMA_NUM_PARALLEL = "2"
$env:OLLAMA_FLASH_ATTENTION = "1"
$env:OLLAMA_KEEP_ALIVE = "5m"
$env:OLLAMA_BATCH_SIZE = "512"
$env:OLLAMA_MAX_LOADED_MODELS = "1"

# ─────────────────────────────────────────────────────────────
# Setup optimized model (first run only)
# ─────────────────────────────────────────────────────────────

if ($SetupModel) {
    Write-Host ""
    Write-Host "  Creating optimized model..." -ForegroundColor Yellow

    $modelfile = "scripts/glm-optimized.Modelfile"
    if (Test-Path $modelfile) {
        ollama create glm-optimized -f $modelfile
        Write-Host "  [OK] Model 'glm-optimized' created" -ForegroundColor Green
        Write-Host "  Update MODEL_NAME=glm-optimized in .env" -ForegroundColor Yellow
    } else {
        Write-Host "  [ERROR] Modelfile not found" -ForegroundColor Red
    }
    exit
}

# ─────────────────────────────────────────────────────────────
# Check Ollama
# ─────────────────────────────────────────────────────────────

$ollamaRunning = $false
try {
    $response = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 2
    $ollamaRunning = $true
    Write-Host "  [OK] Ollama running" -ForegroundColor Green
} catch {
    Write-Host "  [..] Starting Ollama..." -ForegroundColor Yellow
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 3

    try {
        $response = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 5
        $ollamaRunning = $true
        Write-Host "  [OK] Ollama started" -ForegroundColor Green
    } catch {
        Write-Host "  [ERROR] Failed to start Ollama" -ForegroundColor Red
        exit 1
    }
}

if ($OllamaOnly) {
    Write-Host ""
    Write-Host "  Ollama is ready. Press Ctrl+C to stop." -ForegroundColor Cyan
    while ($true) { Start-Sleep -Seconds 60 }
}

# ─────────────────────────────────────────────────────────────
# Preload model
# ─────────────────────────────────────────────────────────────

Write-Host "  [..] Preloading model..." -ForegroundColor Yellow

$modelName = if ($env:MODEL_NAME) { $env:MODEL_NAME } else { "glm-4.7-flash" }

try {
    $body = @{ model = $modelName } | ConvertTo-Json
    Invoke-RestMethod -Uri "http://localhost:11434/api/generate" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 120 | Out-Null
    Write-Host "  [OK] Model loaded: $modelName" -ForegroundColor Green
} catch {
    Write-Host "  [WARN] Model preload failed (will load on first request)" -ForegroundColor Yellow
}

# ─────────────────────────────────────────────────────────────
# Start MITS
# ─────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "  Starting MITS..." -ForegroundColor Cyan
Write-Host "  http://localhost:7860" -ForegroundColor White
Write-Host ""

# Activate venv if exists
if (Test-Path "venv/Scripts/Activate.ps1") {
    . venv/Scripts/Activate.ps1
}

python run.py
