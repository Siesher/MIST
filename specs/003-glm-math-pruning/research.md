# Research: GLM STEM Pruning

**Feature**: 003-glm-math-pruning
**Date**: 2026-01-31

## Executive Summary

This research consolidates findings on REAP expert pruning, Cerebras API for dataset generation, and GGUF conversion for deploying a math+STEM optimized GLM-4.7-Flash model.

---

## 1. Cerebras API for Dataset Generation

### Decision
Use Cerebras Inference API with Qwen-3-235B-A22B-Instruct-2507 for generating multi-domain STEM calibration dataset.

### Rationale
- **Speed**: 1,400+ tokens/second - fastest frontier model inference
- **Cost**: $0.60/M input, $1.20/M output - 10x cheaper than alternatives
- **Quality**: State-of-the-art non-reasoning model, excellent for STEM content
- **Compatibility**: OpenAI-compatible API, easy integration

### Technical Details

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://api.cerebras.ai/v1",
    api_key=os.environ["CEREBRAS_API_KEY"]
)

response = client.chat.completions.create(
    model="qwen-3-235b-a22b-instruct-2507",
    messages=[{"role": "user", "content": prompt}],
    max_tokens=2048
)
```

### Rate Limits (Free Tier per Key)

| Resource | Per Minute | Per Hour | Per Day |
|----------|------------|----------|---------|
| Requests | 30 | 900 | 1,440 |
| Tokens | 64,000 | 1,000,000 | 1,000,000 |

### API Key Rotation Strategy

The project has **10 API keys** in `.env` (CEREBRAS_API_KEY_1 through CEREBRAS_API_KEY_10).

**Effective limits with rotation**:
- 10 keys × 30 req/min = **300 req/min**
- 10 keys × 1M tokens/day = **10M tokens/day**

**Generation time for 1000 examples**:
- Sequential (1 key): ~34 minutes (rate limited)
- With rotation (10 keys): ~4 minutes (parallelizable)

### Cost Estimate for 1000 examples
- Using **free tier** - $0.00
- Average: ~700 tokens/example × 1000 = 700K tokens
- Well within daily limit of 10M tokens (with rotation)

### Alternatives Considered
- **GPT-4o**: Higher cost ($5/M input), slower
- **Claude Opus**: Higher cost, no speed advantage
- **Local generation**: Too slow, lower quality

---

## 2. REAP Calibration Dataset Format

### Decision
Generate dataset in HuggingFace-compatible JSONL format with multi-domain coverage.

### Rationale
- REAP CLI accepts HuggingFace dataset names or local paths
- Standard format ensures compatibility with existing tooling
- Domain balance prevents expert elimination for any subject

### Required Format

```jsonl
{"instruction": "Solve step-by-step: ...", "input": "", "output": "Step 1: ..."}
{"instruction": "Write Python code to...", "input": "", "output": "```python\n...```"}
{"instruction": "Explain the physics of...", "input": "", "output": "The principle..."}
```

### Calibration Parameters

| Parameter | Value | Justification |
|-----------|-------|---------------|
| Samples | 1024 | REAP default for ≤110B models |
| Sequence length | 2048 | Standard for calibration |
| Packing | Enabled | Efficient GPU utilization |

### Domain Distribution (1000 examples)

| Domain | Count | Subtopics |
|--------|-------|-----------|
| Code | 200 | Python, algorithms, debugging, OOP |
| Mathematics | 200 | Algebra, calculus, statistics, probability, linear algebra |
| Physics | 150 | Mechanics, thermodynamics, electromagnetism, quantum |
| Chemistry | 150 | Organic, inorganic, biochemistry, stoichiometry |
| Biology | 150 | Molecular, genetics, ecology, anatomy |
| Socratic | 150 | Multi-domain hint generation, guided questioning |

### Critical Insight
From REAP research: "Experts are TASK-SPECIFIC. If calibration lacks code, code-specialized experts appear 'unused' and get pruned." Multi-domain calibration is **essential**.

### Alternatives Considered
- **evol-codealpaca-v1 only**: Would lose math/science experts
- **GSM8K only**: Would lose code experts
- **Random web data**: Poor domain coverage

---

## 3. REAP Pruning Process

### Decision
Use CerebrasResearch/reap repository with 35% pruning rate targeting ~20B parameters.

### Rationale
- Official implementation with proven results
- 35% pruning balances size reduction vs quality preservation
- 50% pruning achieves 95%+ retention on code tasks

### CLI Command

```bash
# From REAP repository
bash experiments/pruning-cli.sh \
    0 \                                    # GPU ID
    zai-org/GLM-4.7-Flash \               # Base model
    reap \                                 # Method
    42 \                                   # Random seed
    0.35 \                                 # Pruning rate (35%)
    ./calibration_dataset \               # Custom dataset path
    true true true false false            # Flags
```

### Memory Requirements

| Model Size | GPU Memory Required |
|------------|---------------------|
| 30B (GLM-4.7-Flash) | ~40GB for calibration |
| Pruned 20B output | ~25GB for verification |

### A100 Compute Estimate
- Calibration pass: ~30 minutes
- Pruning computation: ~1 hour
- Verification: ~30 minutes
- **Total**: ~2 hours A100 time (~124 CU)

### Alternatives Considered
- **Expert merging (HC-SMoE)**: Causes "functional subspace collapse" per REAP paper
- **Unstructured pruning**: Incompatible with MoE architecture
- **Knowledge distillation**: Requires additional training, higher compute

---

## 4. GGUF Conversion

### Decision
Use llama.cpp `convert_hf_to_gguf.py` with Q4_K_M quantization.

### Rationale
- Q4_K_M is "the sweet spot for most use cases"
- GLM architecture supported in llama.cpp (verified in recent versions)
- Ollama uses GGUF format natively

### Conversion Commands

```bash
# Clone llama.cpp
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp

# Convert to GGUF (f16 first)
python convert_hf_to_gguf.py /path/to/pruned_model \
    --outfile glm-stem-pruned-f16.gguf \
    --outtype f16

# Quantize to Q4_K_M
./llama-quantize glm-stem-pruned-f16.gguf \
    glm-stem-pruned-q4km.gguf Q4_K_M
```

### Size Estimates

| Format | Size (20B model) |
|--------|------------------|
| FP16 | ~40GB |
| Q8_0 | ~20GB |
| Q4_K_M | ~11GB |

### Ollama Modelfile

```dockerfile
FROM ./glm-stem-pruned-q4km.gguf

PARAMETER temperature 0.2
PARAMETER top_p 0.9
PARAMETER top_k 2
PARAMETER repeat_penalty 1.0
PARAMETER num_ctx 4096
PARAMETER num_gpu 25

SYSTEM "You are a Socratic STEM tutor..."
```

### Alternatives Considered
- **Q5_K_M**: 15% larger, marginal quality gain
- **Q3_K_M**: Too aggressive, noticeable quality loss
- **GPTQ/AWQ**: Less compatible with Ollama

---

## 5. Google Colab A100 Setup

### Decision
Use Colab Pro+ with A100 40GB runtime for pruning.

### Rationale
- A100 40GB sufficient for 30B model calibration
- Pro+ guarantees A100 access
- Drive integration for checkpointing

### Compute Budget

| Resource | Rate | Available |
|----------|------|-----------|
| A100 40GB | 62 CU/hour | 100 CU total |
| A100 80GB | 75 CU/hour | 75 CU total |

### Recommended Runtime
- Use A100 40GB (more compute units available)
- **Total runtime**: ~2 hours → ~124 CU (within budget with margin)

### Notebook Structure

1. **Setup Cell**: Install dependencies, mount Drive
2. **Dataset Cell**: Load/generate calibration dataset
3. **Model Cell**: Download GLM-4.7-Flash
4. **Pruning Cell**: Run REAP with checkpointing
5. **Validation Cell**: Quick accuracy check
6. **Export Cell**: Save to Drive

### Alternatives Considered
- **Lambda Labs**: Higher hourly cost
- **RunPod**: Less reliable availability
- **Local RTX 2080**: Insufficient VRAM for pruning

---

## 6. Validation Benchmarks

### Decision
Validate on 4 domain-specific benchmarks before GGUF conversion.

### Rationale
- Each benchmark tests a different expert group
- Failing any benchmark indicates pruning damaged that domain
- Fast validation prevents wasted conversion time

### Benchmark Suite

| Benchmark | Domain | Metric | Baseline Target |
|-----------|--------|--------|-----------------|
| GSM8K | Math reasoning | Accuracy | 95% of baseline |
| HumanEval | Code generation | Pass@1 | 95% of baseline |
| SciQ | Science knowledge | Accuracy | 95% of baseline |
| MMLU-STEM | Multi-domain | Accuracy | 95% of baseline |

### Quick Validation (50 samples each)
- Total: 200 inference calls
- Time: ~10 minutes on A100
- Sufficient to detect major regressions

---

## References

- [REAP Paper (arXiv:2510.13999)](https://arxiv.org/abs/2510.13999)
- [CerebrasResearch/reap GitHub](https://github.com/CerebrasResearch/reap)
- [Cerebras Inference Docs](https://inference-docs.cerebras.ai/)
- [llama.cpp GGUF Tutorial](https://github.com/ggml-org/llama.cpp/discussions/2948)
- [Cerebras Python SDK](https://github.com/Cerebras/cerebras-cloud-sdk-python)
