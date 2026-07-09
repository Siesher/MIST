# Quickstart: GLM-4.7-Flash-REAP Integration

**Feature**: `002-glm-model-integration`
**Estimated Setup Time**: 15-30 minutes

## Prerequisites

- **Hardware**: RTX 2080 (8GB VRAM), 32GB RAM, modern CPU (Ryzen 9 recommended)
- **Software**: Python 3.11+, Ollama 0.14.3+, Git
- **Storage**: ~15GB free for model files

## Quick Setup

### Step 1: Install/Update Ollama

```bash
# Windows (PowerShell as Admin)
winget install Ollama.Ollama

# Verify version (need 0.14.3+)
ollama --version
```

### Step 2: Pull the Model

```bash
# Primary model (GLM-4.7-Flash)
ollama pull glm-4.7-flash

# Fallback model
ollama pull deepseek-r1:8b
```

### Step 3: Configure Environment

Create/update `.env` file:

```env
# Model Configuration
MODEL_NAME=glm-4.7-flash
MODEL_BACKEND=ollama
OLLAMA_HOST=http://localhost:11434

# Sampling (optimized for GLM)
TEMPERATURE=0.2
MAX_TOKENS=2048
THINKING_MODE=true

# Hardware Optimization
OLLAMA_GPU_LAYER_COUNT=25
OLLAMA_NUM_PARALLEL=1
```

### Step 4: Verify Installation

```bash
# Start Ollama service
ollama serve

# Test model (in new terminal)
ollama run glm-4.7-flash "Solve step by step: If 2x + 3 = 11, what is x?"
```

Expected output: Step-by-step solution with reasoning.

### Step 5: Run MITS

```bash
cd MITS
python -m interface.gradio_app
```

Open browser at `http://localhost:7860`

---

## Configuration Options

### For Best Quality (slower)

```env
MODEL_NAME=glm-4.7-flash
TEMPERATURE=0.2
OLLAMA_GPU_LAYER_COUNT=20
```

### For Best Speed (slightly lower quality)

```env
MODEL_NAME=deepseek-r1:8b
TEMPERATURE=0.3
OLLAMA_GPU_LAYER_COUNT=99
```

### For Low VRAM (<6GB)

```env
MODEL_NAME=deepseek-r1:8b
OLLAMA_GPU_LAYER_COUNT=15
```

---

## Using llama.cpp (Advanced)

For more control over MoE offloading:

```bash
# Build llama.cpp with CUDA
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp
make GGML_CUDA=1

# Download model
huggingface-cli download unsloth/GLM-4.7-Flash-REAP-23B-A3B-GGUF \
  GLM-4.7-Flash-REAP-23B-A3B-Q4_K_M.gguf \
  --local-dir models/

# Run with optimal settings
./llama-server \
  -m models/GLM-4.7-Flash-REAP-23B-A3B-Q4_K_M.gguf \
  -ngl 25 \
  --n-cpu-moe 22 \
  --cache-type-k q8_0 \
  --cache-type-v q4_0 \
  -c 4096 \
  -t 16 \
  --host 0.0.0.0 \
  --port 8080
```

Then configure MITS to use llama.cpp:

```env
MODEL_BACKEND=llama.cpp
LLAMA_CPP_HOST=http://localhost:8080
```

---

## Troubleshooting

### "Out of memory" error

1. Reduce GPU layers: `OLLAMA_GPU_LAYER_COUNT=20`
2. Reduce context: Add `num_ctx 2048` to Modelfile
3. Switch to fallback: `MODEL_NAME=deepseek-r1:8b`

### Repetitive/looping output

1. Verify temperature is low: `TEMPERATURE=0.2`
2. Ensure `repetition_penalty` is NOT set (or =1.0)
3. Update Ollama to latest version

### Slow first response

- Normal for MoE models with partial offload
- First token latency: 2-4 seconds expected
- Subsequent tokens: 8-12/sec

### Model not found

```bash
# List available models
ollama list

# If missing, pull again
ollama pull glm-4.7-flash
```

---

## Verify Math Quality

Test with GSM8K-style problem:

```
ollama run glm-4.7-flash "A store had 50 apples. They sold 23 apples in the morning and 14 in the afternoon. How many apples are left?"
```

Expected: Correct step-by-step solution (50 - 23 - 14 = 13)

---

## Next Steps

1. Run benchmark comparison: `python evaluation/benchmark_models.py`
2. Test Socratic tutoring: Open Gradio UI and interact
3. Monitor performance: Check `data/metrics.db` for latency data
