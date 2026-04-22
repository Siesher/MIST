# ============================================================
# MITS - Activate TurboQuant HF backend
# ============================================================
# What it does:
#   1. Kills Ollama to free VRAM (~5.5 GiB)
#   2. Checks free VRAM via nvidia-smi
#   3. Runs test script (load + benchmark)
#   4. If test passed -> flips backend/.env to HF mode
#
# Run:    .\scripts\activate_turbo_quant.ps1
# Revert: .\scripts\activate_turbo_quant.ps1 -Revert
# ============================================================

param(
    [switch]$Revert,
    [switch]$SkipTest,
    [string]$Config = "qwen3.5-9b-turbo"
)

$ErrorActionPreference = "Stop"

$RepoRoot = "C:\Work\MITS"
$EnvFile  = "$RepoRoot\backend\.env"

if ($Revert) {
    Write-Host "==== Revert to Ollama ====" -ForegroundColor Yellow
    (Get-Content $EnvFile) -replace "USE_HF_BACKEND=true", "USE_HF_BACKEND=false" |
        Set-Content $EnvFile -Encoding UTF8
    Write-Host "OK - backend/.env reverted. Restart uvicorn." -ForegroundColor Green
    return
}

Write-Host "==== Activate TurboQuant HF Backend ====" -ForegroundColor Cyan

# --- 1. Kill Ollama to free VRAM ---
Write-Host ""
Write-Host "[1/4] Killing Ollama to free VRAM..." -ForegroundColor Yellow
$ollama = Get-Process -Name "ollama*" -ErrorAction SilentlyContinue
if ($ollama) {
    Stop-Process -Name "ollama*" -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3
    Write-Host "  OK - Ollama terminated ($($ollama.Count) processes)" -ForegroundColor Green
} else {
    Write-Host "  Ollama not running" -ForegroundColor Gray
}

# --- 2. Check VRAM ---
Write-Host ""
Write-Host "[2/4] Checking free VRAM..." -ForegroundColor Yellow
try {
    $vram = & nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader,nounits 2>$null
    if ($vram) {
        $parts = $vram -split ","
        $used  = [int]$parts[0].Trim()
        $total = [int]$parts[1].Trim()
        $free  = $total - $used
        Write-Host ("  VRAM: {0} / {1} MiB (free: {2} MiB)" -f $used, $total, $free) -ForegroundColor Gray
        if ($free -lt 7500) {
            Write-Host "  WARNING - less than 7.5 GiB free. Model may OOM." -ForegroundColor Red
            Write-Host "  Close other GPU apps (browser, VS Code extensions, games)." -ForegroundColor Red
        } else {
            Write-Host "  OK - enough VRAM" -ForegroundColor Green
        }
    }
} catch {
    Write-Host "  nvidia-smi unavailable, skipping check" -ForegroundColor Gray
}

# --- 3. Run test script ---
if (-not $SkipTest) {
    Write-Host ""
    Write-Host "[3/4] Running load benchmark..." -ForegroundColor Yellow
    Write-Host "  (takes 1-3 minutes; first run may download KTO adapter ~100MB)" -ForegroundColor Gray
    Push-Location $RepoRoot
    try {
        & python -X utf8 scripts/test_hf_turbo.py --config $Config
        $testExit = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    if ($testExit -ne 0) {
        Write-Host ""
        Write-Host "  FAIL - test failed. NOT switching backend." -ForegroundColor Red
        Write-Host "  Check output above - likely OOM or compatibility issue." -ForegroundColor Red
        return
    }
    Write-Host ""
    Write-Host "  OK - test passed" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "[3/4] Skipping test (-SkipTest)" -ForegroundColor Gray
}

# --- 4. Flip env flag ---
Write-Host ""
Write-Host "[4/4] Switching backend/.env to HF backend..." -ForegroundColor Yellow
$content = Get-Content $EnvFile -Raw
$content = $content -replace "USE_HF_BACKEND=false", "USE_HF_BACKEND=true"
$content = $content -replace "HF_MODEL_CONFIG=\S+", "HF_MODEL_CONFIG=$Config"
Set-Content $EnvFile -Value $content -Encoding UTF8
Write-Host "  OK - USE_HF_BACKEND=true, HF_MODEL_CONFIG=$Config" -ForegroundColor Green

Write-Host ""
Write-Host "==== Done ====" -ForegroundColor Green
Write-Host ""
Write-Host "Restart backend:" -ForegroundColor Cyan
Write-Host "  cd C:\Work\MITS"
Write-Host "  python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload"
Write-Host ""
Write-Host "StatusBar will show chips 'HF / TQ / 32K ctx' once backend is up." -ForegroundColor Cyan
Write-Host ""
Write-Host "To revert:" -ForegroundColor Gray
Write-Host "  .\scripts\activate_turbo_quant.ps1 -Revert"
