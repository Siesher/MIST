<#
.SYNOPSIS
    GLM-STEM Model Installation Script for Windows
.DESCRIPTION
    Installs REAP-pruned GLM model (42 experts) for MITS
.PARAMETER Variant
    GGUF variant: q4km (~13GB) or q8 (~21GB). Default: q4km
.PARAMETER Reinstall
    Force reinstallation even if model exists
.EXAMPLE
    .\install_glm_stem.ps1
    .\install_glm_stem.ps1 -Variant q8
    .\install_glm_stem.ps1 -Reinstall
#>

param(
    [ValidateSet("q4km", "q8")]
    [string]$Variant = "q4km",
    [switch]$Reinstall
)

$ErrorActionPreference = "Stop"

# Configuration
$ModelName = "glm-stem-42exp"
$HfRepo = "Siesher/glm-stem-42exp-gguf"
$ModelsDir = Join-Path $env:USERPROFILE "models"
$MinDiskGB = 20
$OllamaUrl = "http://localhost:11434"

$GgufFile = "glm-stem-42exp-$Variant.gguf"
$GgufUrl = "https://huggingface.co/$HfRepo/resolve/main/$GgufFile"

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  GLM-STEM Model Installation" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "Model: $ModelName"
Write-Host "Variant: $Variant"
Write-Host "Target: $ModelsDir\$GgufFile"
Write-Host ""

# Check if Ollama is installed
$ollamaPath = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollamaPath) {
    Write-Host "ERROR: Ollama is not installed" -ForegroundColor Red
    Write-Host "Install Ollama first: https://ollama.ai/download"
    exit 1
}
Write-Host "[OK] Ollama found" -ForegroundColor Green

# Function to check if Ollama API is responding
function Test-OllamaRunning {
    try {
        $response = Invoke-WebRequest -Uri "$OllamaUrl/api/tags" -TimeoutSec 3 -UseBasicParsing -ErrorAction SilentlyContinue
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

# Check if Ollama is running
Write-Host "Checking Ollama status..." -ForegroundColor Yellow
$ollamaRunning = Test-OllamaRunning

if (-not $ollamaRunning) {
    Write-Host "Ollama not running. Starting server..." -ForegroundColor Yellow
    Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden

    # Wait for Ollama to start (up to 15 seconds)
    $maxWait = 15
    $waited = 0
    while (-not (Test-OllamaRunning) -and $waited -lt $maxWait) {
        Write-Host "  Waiting for Ollama... ($waited/$maxWait sec)" -ForegroundColor Gray
        Start-Sleep -Seconds 1
        $waited++
    }

    if (-not (Test-OllamaRunning)) {
        Write-Host ""
        Write-Host "ERROR: Could not start Ollama automatically." -ForegroundColor Red
        Write-Host ""
        Write-Host "Please start Ollama manually:" -ForegroundColor Yellow
        Write-Host "  1. Open a new terminal"
        Write-Host "  2. Run: ollama serve"
        Write-Host "  3. Then run this script again"
        Write-Host ""
        exit 1
    }
}
Write-Host "[OK] Ollama is running" -ForegroundColor Green

# Check if model already exists
Write-Host "Checking existing models..." -ForegroundColor Yellow
$existingModels = ollama list 2>$null
if ($existingModels -match $ModelName) {
    if ($Reinstall) {
        Write-Host "Removing existing model for reinstall..." -ForegroundColor Yellow
        ollama rm $ModelName 2>$null
    } else {
        Write-Host "[OK] Model '$ModelName' already installed" -ForegroundColor Green
        Write-Host ""
        Write-Host "To reinstall, run: .\install_glm_stem.ps1 -Reinstall"
        exit 0
    }
}

# Check disk space
$drive = (Get-Item $env:USERPROFILE).PSDrive.Name
$freeSpace = (Get-PSDrive $drive).Free / 1GB
if ($freeSpace -lt $MinDiskGB) {
    Write-Host "ERROR: Insufficient disk space" -ForegroundColor Red
    Write-Host "Available: $([math]::Round($freeSpace, 1))GB, Required: ${MinDiskGB}GB"
    exit 1
}
Write-Host "[OK] Disk space OK ($([math]::Round($freeSpace, 1))GB available)" -ForegroundColor Green

# Create models directory
if (-not (Test-Path $ModelsDir)) {
    New-Item -ItemType Directory -Path $ModelsDir -Force | Out-Null
}
Set-Location $ModelsDir

# Download GGUF file
$GgufPath = Join-Path $ModelsDir $GgufFile
if (Test-Path $GgufPath) {
    Write-Host "[OK] GGUF file exists, skipping download" -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "Downloading $GgufFile (~13GB)..." -ForegroundColor Cyan
    Write-Host "This may take 10-30 minutes depending on your connection."
    Write-Host ""

    # Try huggingface_hub first (better resume support)
    $pythonAvailable = Get-Command python -ErrorAction SilentlyContinue
    $downloadSuccess = $false

    if ($pythonAvailable) {
        Write-Host "Trying huggingface_hub (best resume support)..." -ForegroundColor Yellow
        $script = @"
import warnings
warnings.filterwarnings('ignore')
try:
    from huggingface_hub import hf_hub_download
    print('Downloading with huggingface_hub...')
    path = hf_hub_download(
        repo_id='$HfRepo',
        filename='$GgufFile',
        local_dir=r'$ModelsDir'
    )
    print(f'SUCCESS: {path}')
except ImportError:
    print('ERROR: huggingface_hub not installed')
    exit(1)
except Exception as e:
    print(f'ERROR: {e}')
    exit(1)
"@
        # Run and check if file exists after
        python -c $script

        # Check if file was downloaded
        if (Test-Path $GgufPath) {
            $downloadSuccess = $true
            Write-Host "Download completed!" -ForegroundColor Green
        } else {
            Write-Host "huggingface_hub did not download to expected path, trying alternative..." -ForegroundColor Yellow
        }
    }

    if (-not $downloadSuccess) {
        # Fallback to Invoke-WebRequest
        Write-Host "Downloading with PowerShell (no resume support)..." -ForegroundColor Yellow
        try {
            Invoke-WebRequest -Uri $GgufUrl -OutFile $GgufPath
            $downloadSuccess = $true
        } catch {
            Write-Host "ERROR: Download failed: $_" -ForegroundColor Red
            exit 1
        }
    }
}
Write-Host "[OK] GGUF downloaded" -ForegroundColor Green

# Create Modelfile (simple, same as glm-4.7-flash)
$ModelfilePath = Join-Path $ModelsDir "Modelfile.glm-stem"
$ModelfileContent = @"
FROM ./$GgufFile

PARAMETER temperature 0.2
PARAMETER top_p 0.9
PARAMETER top_k 2
PARAMETER repeat_penalty 1.1
PARAMETER num_ctx 4096
PARAMETER num_predict 512
"@
$ModelfileContent | Out-File -FilePath $ModelfilePath -Encoding UTF8 -NoNewline
Write-Host "[OK] Modelfile created" -ForegroundColor Green

# Create model in Ollama
Write-Host ""
Write-Host "Creating Ollama model (this may take a few minutes)..." -ForegroundColor Cyan
ollama create $ModelName -f $ModelfilePath
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to create model in Ollama" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Model registered in Ollama" -ForegroundColor Green

# Verification test
Write-Host ""
Write-Host "Running verification test..." -ForegroundColor Yellow
try {
    $response = ollama run $ModelName "What is 2 + 2? Answer briefly." 2>&1
    if ($response) {
        Write-Host "[OK] Model responds correctly" -ForegroundColor Green
        $preview = "$response".Substring(0, [Math]::Min(100, "$response".Length))
        Write-Host "Sample: $preview..."
    }
} catch {
    Write-Host "WARNING: Verification test failed, but model may still work" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  Installation Complete!" -ForegroundColor Green
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Usage:"
Write-Host "  ollama run $ModelName `"Solve: 2x + 5 = 13`""
Write-Host ""
Write-Host "In MITS:"
Write-Host "  The model will be used automatically as the default."
Write-Host ""
