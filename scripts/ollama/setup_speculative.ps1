# ============================================================
# MITS - Setup Speculative Decoding via Ollama 0.19+
# ============================================================
# What it does:
#   1. Pulls qwen2.5:0.5b as draft model (~400MB)
#   2. Tests if Ollama supports native draft_model option
#   3. Reports feasibility + next steps
# ============================================================

param(
    [string]$DraftModel = "qwen2.5:0.5b",
    [string]$MainModel  = "mits-tutor-9b-fast"
)

$ErrorActionPreference = "Stop"

Write-Host "==== Speculative Decoding Setup ====" -ForegroundColor Cyan

# 1. Ensure Ollama running
Write-Host ""
Write-Host "[1/4] Checking Ollama..." -ForegroundColor Yellow
$running = Get-Process -Name "ollama*" -ErrorAction SilentlyContinue
if (-not $running) {
    Write-Host "  Starting Ollama server..." -ForegroundColor Gray
    Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 3
}
Write-Host "  OK" -ForegroundColor Green

# 2. Pull draft model
Write-Host ""
Write-Host "[2/4] Pulling draft model $DraftModel (~400MB)..." -ForegroundColor Yellow
$list = & ollama list 2>&1 | Out-String
if ($list -match [regex]::Escape($DraftModel)) {
    Write-Host "  OK - $DraftModel already present" -ForegroundColor Green
} else {
    & ollama pull $DraftModel
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  FAIL - could not pull draft model" -ForegroundColor Red
        return
    }
    Write-Host "  OK - pulled" -ForegroundColor Green
}

# 3. Test native speculative support
Write-Host ""
Write-Host "[3/4] Testing native draft_model option in Ollama API..." -ForegroundColor Yellow

$payload = @{
    model  = $MainModel
    prompt = "1+1="
    stream = $false
    options = @{
        num_predict  = 8
        draft_model  = $DraftModel
        num_draft    = 5
    }
} | ConvertTo-Json -Depth 5

try {
    $response = Invoke-RestMethod -Uri "http://localhost:11434/api/generate" `
        -Method Post -Body $payload -ContentType "application/json" `
        -ErrorAction Stop
    $timing = $response.eval_duration
    $tokens = $response.eval_count
    $tps = if ($timing -gt 0) { [math]::Round($tokens * 1e9 / $timing, 1) } else { 0 }
    Write-Host "  API accepted draft_model option. tokens=$tokens, tok/s=$tps" -ForegroundColor Green
    $nativeSupport = $true
} catch {
    $errMsg = $_.Exception.Message
    if ($errMsg -match "unsupported|unknown|invalid") {
        Write-Host "  Ollama does not support draft_model natively in this version." -ForegroundColor Yellow
        Write-Host "  Will use Python-level speculative fallback." -ForegroundColor Gray
    } else {
        Write-Host "  API error: $errMsg" -ForegroundColor Red
    }
    $nativeSupport = $false
}

# 4. Write config flag
Write-Host ""
Write-Host "[4/4] Writing config..." -ForegroundColor Yellow

$envFile = "C:\Work\MITS\backend\.env"
$content = Get-Content $envFile -Raw

if ($content -notmatch "SPECULATIVE_DECODING") {
    $append = @"

# ─── Speculative Decoding (faster math/code generation) ───
SPECULATIVE_DECODING=$($nativeSupport.ToString().ToLower())
SPECULATIVE_DRAFT_MODEL=$DraftModel
SPECULATIVE_NUM_DRAFT=5
"@
    Add-Content -Path $envFile -Value $append -Encoding UTF8
    Write-Host "  OK - appended config to backend/.env" -ForegroundColor Green
} else {
    Write-Host "  Config already present (edit backend/.env to change)" -ForegroundColor Gray
}

Write-Host ""
Write-Host "==== Done ====" -ForegroundColor Green
Write-Host ""
if ($nativeSupport) {
    Write-Host "Native speculative decoding ACTIVE in Ollama." -ForegroundColor Cyan
    Write-Host "Expected speedup: 1.5-3x on math/code (per arXiv 2302.01318)." -ForegroundColor Cyan
} else {
    Write-Host "Native support NOT detected. Python fallback will be used if enabled." -ForegroundColor Yellow
    Write-Host "Upgrade Ollama to get native speculative: winget upgrade ollama" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "Restart backend to pick up config:" -ForegroundColor Gray
Write-Host "  python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload"
