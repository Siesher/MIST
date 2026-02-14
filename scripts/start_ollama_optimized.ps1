# MITS Ollama Optimized Launcher
# Hardware: Ryzen 9 9950x + 32GB RAM + RTX 2080 8GB

Write-Host "MITS Ollama Optimized Configuration" -ForegroundColor Cyan
Write-Host "===================================" -ForegroundColor Cyan
Write-Host ""

# ─────────────────────────────────────────────────────────────
# CPU Optimization (Ryzen 9 9950x: 16 cores / 32 threads)
# ─────────────────────────────────────────────────────────────
# Используем 16 потоков (половина) - оптимально для смешанной нагрузки
$env:OLLAMA_NUM_THREADS = "16"

# Параллельные запросы (для batch processing)
$env:OLLAMA_NUM_PARALLEL = "2"

# ─────────────────────────────────────────────────────────────
# GPU Optimization (RTX 2080 8GB)
# ─────────────────────────────────────────────────────────────
# Flash Attention для RTX 2080 (Turing, compute 7.5)
$env:OLLAMA_FLASH_ATTENTION = "1"

# Максимум VRAM для моделей (оставляем 512MB для системы)
$env:OLLAMA_GPU_MEMORY = "7680"

# ─────────────────────────────────────────────────────────────
# Memory Optimization
# ─────────────────────────────────────────────────────────────
# Держать модель в памяти дольше (5 минут)
$env:OLLAMA_KEEP_ALIVE = "5m"

# Размер batch для GPU
$env:OLLAMA_BATCH_SIZE = "512"

# ─────────────────────────────────────────────────────────────
# Performance Tuning
# ─────────────────────────────────────────────────────────────
# Отключить debug для production
$env:OLLAMA_DEBUG = "0"

# Максимум загруженных моделей
$env:OLLAMA_MAX_LOADED_MODELS = "1"

Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  CPU Threads:     $env:OLLAMA_NUM_THREADS"
Write-Host "  Parallel:        $env:OLLAMA_NUM_PARALLEL"
Write-Host "  Flash Attention: $env:OLLAMA_FLASH_ATTENTION"
Write-Host "  GPU Memory:      $env:OLLAMA_GPU_MEMORY MB"
Write-Host "  Batch Size:      $env:OLLAMA_BATCH_SIZE"
Write-Host "  Keep Alive:      $env:OLLAMA_KEEP_ALIVE"
Write-Host ""
Write-Host "Starting Ollama..." -ForegroundColor Green
Write-Host ""

# Запуск Ollama
ollama serve
