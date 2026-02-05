# Quickstart: GLM STEM Pruning

**Feature**: 003-glm-math-pruning
**Time Required**: ~2.5 hours total (dataset: 15min, pruning: 2h, conversion: 15min)

## Prerequisites

### Local Machine (Windows 11)
- Python 3.11+
- Ollama installed and running
- RTX 2080 8GB + 32GB RAM
- Git

### Cloud Resources
- Cerebras API key (free tier: 1M tokens/day)
- Google Colab Pro+ subscription
- Google Drive with 50GB free space

## Step 1: Setup Local Environment

```bash
# Navigate to MITS repository
cd C:/Work/MITS

# Create virtual environment (if not exists)
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install cerebras-cloud-sdk openai jsonschema tqdm python-dotenv

# API keys are already configured in .env file:
# CEREBRAS_API_KEY_1 through CEREBRAS_API_KEY_10
# The generation script will use key rotation for faster generation
```

## Step 2: Generate Calibration Dataset

### Rate Limits (Free Tier)

| Resource | Per Key | With 10 Keys |
|----------|---------|--------------|
| Requests/min | 30 | 300 |
| Tokens/day | 1M | 10M |

**Estimated time**: ~10-15 minutes with key rotation

### Option A: Run locally (recommended)

```bash
# Generate dataset using Cerebras API with key rotation
python training/generate_calibration.py \
    --output training/calibration_data/stem_calibration.jsonl \
    --num-examples 1000 \
    --domains code,math,physics,chemistry,biology,socratic \
    --use-key-rotation \
    --env-file .env

# The script will automatically:
# 1. Load CEREBRAS_API_KEY_1 through CEREBRAS_API_KEY_10 from .env
# 2. Rotate between keys to maximize throughput
# 3. Respect rate limits (30 req/min per key)
# 4. Checkpoint progress to resume if interrupted

# Validate dataset
python -c "
import json
with open('training/calibration_data/stem_calibration.jsonl') as f:
    examples = [json.loads(line) for line in f]
    domains = {}
    for ex in examples:
        domains[ex['domain']] = domains.get(ex['domain'], 0) + 1
    print(f'Total: {len(examples)}')
    print(f'Domains: {domains}')
"
```

### Option B: Use pre-generated dataset

Download from Google Drive: [stem_calibration.jsonl](link_to_be_added)

## Step 3: Run REAP Pruning (Colab)

### 3.1 Open Colab Notebook

1. Go to [Google Colab](https://colab.research.google.com)
2. Open `notebooks/glm_stem_pruning.ipynb` from Drive
3. Select Runtime → Change runtime type → A100 GPU

### 3.2 Mount Drive and Upload Dataset

```python
from google.colab import drive
drive.mount('/content/drive')

# Copy calibration dataset
!cp /content/drive/MyDrive/MITS/stem_calibration.jsonl /content/
```

### 3.3 Install REAP

```python
!git clone https://github.com/CerebrasResearch/reap.git
%cd reap
!pip install -e .
```

### 3.4 Run Pruning

```python
!bash experiments/pruning-cli.sh \
    0 \
    zai-org/GLM-4.7-Flash \
    reap \
    42 \
    0.35 \
    /content/stem_calibration.jsonl \
    true true true false false
```

### 3.5 Save to Drive

```python
!cp -r /content/reap/outputs/pruned_model /content/drive/MyDrive/MITS/glm-stem-pruned
```

## Step 4: Convert to GGUF

### 4.1 On Colab (recommended for speed)

```python
!git clone https://github.com/ggml-org/llama.cpp
%cd llama.cpp
!pip install -r requirements.txt

# Convert to GGUF
!python convert_hf_to_gguf.py /content/drive/MyDrive/MITS/glm-stem-pruned \
    --outfile /content/drive/MyDrive/MITS/glm-stem-pruned-f16.gguf \
    --outtype f16

# Quantize
!make llama-quantize
!./llama-quantize \
    /content/drive/MyDrive/MITS/glm-stem-pruned-f16.gguf \
    /content/drive/MyDrive/MITS/glm-stem-pruned-q4km.gguf \
    Q4_K_M
```

### 4.2 Download GGUF to Local Machine

Download `glm-stem-pruned-q4km.gguf` from Google Drive (~11GB)

## Step 5: Register with Ollama

### 5.1 Create Modelfile

```dockerfile
# models/glm-stem-pruned/Modelfile
FROM ./glm-stem-pruned-q4km.gguf

PARAMETER temperature 0.2
PARAMETER top_p 0.9
PARAMETER top_k 2
PARAMETER repeat_penalty 1.0
PARAMETER num_ctx 4096
PARAMETER num_gpu 25

SYSTEM """You are a Socratic STEM tutor. Guide students through questions and hints, never giving direct answers. Support mathematics, programming, physics, chemistry, and biology."""
```

### 5.2 Import to Ollama

```bash
cd models/glm-stem-pruned

# Create model in Ollama
ollama create glm-stem-pruned -f Modelfile

# Verify
ollama list
```

## Step 6: Validate

### 6.1 Quick Test

```bash
ollama run glm-stem-pruned "Help me understand why the derivative of sin(x) is cos(x)"
```

### 6.2 Run Benchmarks

```bash
python evaluation/benchmark_models.py \
    --model glm-stem-pruned \
    --benchmarks gsm8k,humaneval,sciq,mmlu-stem \
    --samples 50
```

### 6.3 Compare with Baseline

```bash
python evaluation/benchmark_models.py \
    --model glm-4.7-flash \
    --benchmarks gsm8k,humaneval,sciq,mmlu-stem \
    --samples 50 \
    --compare glm-stem-pruned
```

## Troubleshooting

### Cerebras API Rate Limit
- Free tier per key: 30 req/min, 64K tokens/min, 1M tokens/day
- With 10 keys (from .env): effective 300 req/min, 10M tokens/day
- If hitting limits, script auto-rotates to next key
- Use `--checkpoint` to resume interrupted generation

### Colab A100 OOM
- Reduce batch size: Add `--batch-size 1` to pruning command
- Use gradient checkpointing: Already enabled by default
- Try A100 80GB runtime if available

### GGUF Conversion Fails
- Ensure llama.cpp is up to date: `git pull`
- Check GLM architecture support in llama.cpp issues
- Try f32 output first, then quantize

### Ollama Import Fails
- Check Modelfile syntax
- Ensure GGUF file is complete (check SHA256)
- Try with fewer GPU layers: `num_gpu 20`

## Expected Results

| Metric | Target | Typical Result |
|--------|--------|----------------|
| Model Size | 19-20B | ~19.5B |
| GGUF Size | <12GB | ~11GB |
| GSM8K Retention | 95%+ | 96-98% |
| HumanEval Retention | 95%+ | 95-97% |
| TTFT (RTX 2080) | <3s | 2.5s |
| Speed (RTX 2080) | 5+ t/s | 6-8 t/s |

## Next Steps

After successful validation:

1. Update `src/config.py` to use `glm-stem-pruned` as primary model
2. Run MITS integration tests
3. Document results in `docs/MODEL_BENCHMARK_RESULTS.md`
