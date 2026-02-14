# Quickstart: GLM-STEM Model Integration

**Feature**: 005-glm-stem-integration
**Time to complete**: ~30 minutes (mostly download time)

## Prerequisites

- [ ] Ollama installed and running (`ollama serve`)
- [ ] 20GB free disk space
- [ ] Internet connection for HuggingFace download
- [ ] Python 3.11+ (for testing)

## Installation

### Option A: Automated Script (Recommended)

**Linux/macOS:**
```bash
cd /path/to/MITS
./scripts/install_glm_stem.sh
```

**Windows (PowerShell):**
```powershell
cd C:\Work\MITS
.\scripts\install_glm_stem.ps1
```

The script will:
1. Check disk space and Ollama availability
2. Download GGUF from HuggingFace (~13GB for Q4_K_M)
3. Create Modelfile with optimized parameters
4. Register model in Ollama as `glm-stem-42exp`
5. Run verification test

### Option B: Manual Installation

```bash
# 1. Download GGUF
mkdir -p ~/models && cd ~/models
wget https://huggingface.co/Siesher/glm-stem-42exp-gguf/resolve/main/glm-stem-42exp-q4km.gguf

# 2. Create Modelfile
cat > Modelfile << 'EOF'
FROM ./glm-stem-42exp-q4km.gguf

PARAMETER temperature 0.2
PARAMETER top_p 0.9
PARAMETER top_k 2
PARAMETER repeat_penalty 1.0
PARAMETER num_ctx 4096

SYSTEM """You are a Socratic math tutor. Guide students through problems step-by-step without giving direct answers."""
EOF

# 3. Register in Ollama
ollama create glm-stem-42exp -f Modelfile

# 4. Verify
ollama run glm-stem-42exp "Solve: 2x + 5 = 13"
```

## Verification

### Quick Test
```bash
ollama run glm-stem-42exp "What is the derivative of x^2?"
```

Expected: Response mentioning "2x" with explanation.

### Full Test Suite
```bash
cd /path/to/MITS
pytest tests/test_glm_stem.py -v
```

Expected: All 20 tests pass (>90% accuracy).

## Configuration

The model is now default. No `.env` changes required.

To verify:
```python
from src.config import settings
print(settings.MODEL_NAME)  # Should print: glm-stem-42exp
```

To override (if needed):
```bash
# In .env
MODEL_NAME=glm-4.7-flash  # Use original model instead
```

## Usage in Code

```python
from src.models.llm_client import LLMClient

# Automatically uses glm-stem-42exp
client = LLMClient()
response = client.generate("Solve: x^2 - 4 = 0")
print(response)
```

## Troubleshooting

### Model not found
```
Error: model 'glm-stem-42exp' not found
```
**Solution**: Run installation script or `ollama create` manually.

### Out of memory
```
Error: CUDA out of memory
```
**Solution**: Use Q4_K_M variant, ensure no other GPU processes.

### Slow generation
**Solution**: Check GPU is being used with `nvidia-smi`. If CPU-only, expect ~1 token/sec.

### Download interrupted
**Solution**: Re-run script. `huggingface_hub` will resume from where it stopped.

## Performance Expectations

| Metric | Value |
|--------|-------|
| First token latency | <2s on 8GB GPU |
| Generation speed | ~20-30 tok/s on RTX 2080 |
| VRAM usage | ~5.5GB (Q4_K_M) |
| RAM usage | ~6GB additional |

## Next Steps

1. Start MITS: `python -m interface.gradio_app`
2. Test tutoring with math problems
3. Check logs for model confirmation: `llm_client_initialized model=glm-stem-42exp`
