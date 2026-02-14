# Research: GLM-4.7-Flash-REAP-23B-A3B Integration

**Date**: 2026-01-30
**Branch**: `002-glm-model-integration`

## Research Questions

### RQ1: Optimal Quantization for GLM-4.7-Flash-REAP

**Question**: What quantization level provides the best quality/size tradeoff for RTX 2080 8GB + 32GB RAM?

**Decision**: **Q4_K_M** (13.5GB) with partial GPU offload

**Rationale**:
- Available quantizations from [unsloth](https://huggingface.co/unsloth/GLM-4.7-Flash-REAP-23B-A3B-GGUF):
  - IQ3_XXS: 10GB - significant quality loss on reasoning
  - **Q4_K_M: 13.5GB** - best quality/size balance
  - Q5_K_M: 16GB - better quality but slower
  - Q6_K: 19GB - near-lossless but memory constrained
- [Blind testing research](https://github.com/ggml-org/llama.cpp/discussions/5962) shows Q4_K_M retains 95%+ of original quality
- With 8GB GPU + 32GB RAM, Q4_K_M allows ~25 layers on GPU, rest on CPU

**Alternatives Considered**:
- IQ4_XS (12.6GB): Slightly smaller but I-quants slower on CPU; better for GPU-only
- Q3_K_M (11.5GB): Too much quality degradation for math reasoning
- Q5_K_M (16GB): Would fit but leaves less RAM for KV cache

---

### RQ2: Further Model Compression Without Quality Loss

**Question**: Can we compress GLM-4.7-Flash-REAP even further?

**Decision**: **Already optimally compressed** - REAP removed 25% of experts (64→48)

**Rationale**:
- REAP method from [Cerebras](https://www.cerebras.ai/blog/reap) already applied:
  - Original: 30B parameters, 64 experts
  - REAP version: 23B parameters, 48 experts
  - Claimed: "near-identical performance" on code/agentic tasks
- Further expert pruning (e.g., 48→32) would require:
  - Custom REAP application with calibration data
  - Fine-tuning to recover accuracy
  - A100 GPU for processing (user has Colab Pro+)
- **Verdict**: Not recommended for initial integration; can explore later

**Additional Compression Options** (for future):
1. **More aggressive quantization**: IQ3_M would save ~3GB but lose 3-5% accuracy
2. **Context reduction**: Limit to 2048 tokens instead of 4096 saves KV cache
3. **Custom expert pruning**: 48→36 experts on Colab A100 (research project)

---

### RQ3: Optimal Layer Distribution (GPU/CPU Split)

**Question**: How many layers should be on GPU vs CPU for best performance?

**Decision**: **25 GPU layers** + `--n-cpu-moe 22` for MoE expert offload

**Rationale**:
- GLM-4.7-Flash has 47 transformer layers
- [MoE offloading guide](https://medium.com/@david.sanftenberg/gpu-poor-how-to-configure-offloading-for-the-qwen-3-235b-a22b-moe-model-using-llama-cpp-13dc15287bed) explains:
  - `-ngl 99` + `--n-cpu-moe N` = all layers on GPU except MoE experts
  - MoE experts process via CPU, only activation vectors cross PCIe
  - Bottleneck is PCIe latency, not CPU speed
- Memory calculation for RTX 2080 8GB:
  ```
  Q4_K_M total: 13.5GB
  Per layer: ~287MB
  25 layers: ~7.2GB (fits GPU with ~0.8GB for KV cache)
  Remaining 22 layers: ~6.3GB (CPU RAM)
  ```

**Configuration**:
```bash
./llama-cli \
  -hf unsloth/GLM-4.7-Flash-REAP-23B-A3B-GGUF:Q4_K_M \
  -ngl 25 \
  --n-cpu-moe 22 \
  --cache-type-k q8_0 \
  --cache-type-v q4_0 \
  -c 4096 \
  -t 16
```

**Expected Performance**: 8-12 tokens/sec (acceptable for tutoring)

---

### RQ4: Repetition/Quality Issues Fix

**Question**: How to fix reported repetition issues with GLM-4.7-Flash?

**Decision**: Use specific sampling parameters, avoid conflicting chat templates

**Rationale**:
- [HuggingFace discussions](https://huggingface.co/unsloth/GLM-4.7-Flash-GGUF/discussions/1) identify root cause:
  - `--chat-template glm4 --jinja` conflicts with model's internal reasoning
  - Wrong temperature/repetition_penalty causes loops
- [Z.AI recommended parameters](https://huggingface.co/zai-org/GLM-4.7-Flash/discussions/6):
  ```
  temperature: 0.8
  top_p: 0.6
  top_k: 2
  repetition_penalty: 1.0  # DO NOT increase!
  ```
- For code/reasoning (our use case):
  ```
  temperature: 0.2
  top_p: 0.9
  ```

**Fix Applied**:
1. Remove `--jinja` flag if using llama-server
2. Use Unsloth GGUF (has fixes baked in)
3. Set `repetition_penalty=1.0` (never >1.05)
4. Use `temperature=0.2-0.4` for math reasoning

---

### RQ5: Math/GSM8K Performance

**Question**: What is the actual math performance of GLM-4.7-Flash-REAP?

**Decision**: **GSM8K ~98%** (base model), REAP version ~95-97% estimated

**Rationale**:
- Base GLM-4.7-Flash benchmarks:
  - AIME 25: 91.6%
  - GPQA: 75.2%
  - GSM8K: ~98% (reported by Z.AI)
- REAP compression claims "near-identical performance"
- Conservative estimate for REAP + Q4_K_M: **90-95% GSM8K**
- This exceeds our target of 90%+ (SC-001)

**Comparison Table**:

| Model | GSM8K | AIME | VRAM (Q4) |
|-------|-------|------|-----------|
| GLM-4.7-Flash-REAP-23B | ~95% | ~90% | 6.5GB* |
| DeepSeek-R1-Distill-8B | 80-85% | ~70% | 6.5GB |
| Qwen2.5-7B-Math | 75-88% | ~65% | 4GB |

*With partial offload

---

### RQ6: Ollama vs llama.cpp Backend

**Question**: Which backend is better for this integration?

**Decision**: **Ollama** (primary) with llama.cpp fallback

**Rationale**:
- Ollama advantages:
  - Already used in project (`src/models/llm_client.py`)
  - Automatic model management
  - Built-in partial offload (`OLLAMA_GPU_LAYER_COUNT`)
  - GLM-4.7-Flash available: `ollama pull glm-4.7-flash`
- llama.cpp advantages:
  - More granular control (`--n-cpu-moe`)
  - GGUF files from unsloth repository
  - Better for custom configurations
- **Strategy**:
  - Default: Ollama for simplicity
  - Advanced: llama-server for power users needing MoE offload control

**Ollama Configuration**:
```bash
# Environment variables for partial offload
OLLAMA_GPU_LAYER_COUNT=25
OLLAMA_NUM_PARALLEL=1
OLLAMA_FLASH_ATTENTION=1

# Pull model
ollama pull glm-4.7-flash
```

---

### RQ7: Fallback Model Selection

**Question**: Which model should be the fallback if GLM has issues?

**Decision**: **DeepSeek-R1-Distill-Qwen-8B**

**Rationale**:
- Advantages:
  - Proven reasoning quality (distilled from R1 671B)
  - GSM8K: 80-85%
  - VRAM: 6.5GB (fits entirely on GPU)
  - Chain-of-thought reasoning (good for Socratic tutoring)
  - Stable, well-tested
- Available in Ollama: `ollama pull deepseek-r1:8b`

**Alternatives Considered**:
- Qwen3-8B: Good but less focused on reasoning
- Phi-4-mini-reasoning: Math-only, limited scope
- Nemotron-Cascade-8B: Excellent but may have availability issues

---

## Summary of Decisions

| Decision | Choice | Key Reason |
|----------|--------|------------|
| Quantization | Q4_K_M (13.5GB) | Best quality/size for 8GB+32GB |
| Further compression | Not needed | REAP already optimal |
| GPU layers | 25 layers | 7.2GB fits in 8GB VRAM |
| MoE offload | 22 layers to CPU | Use `--n-cpu-moe 22` |
| Sampling params | temp=0.2, rep_penalty=1.0 | Fixes repetition issues |
| Math performance | ~95% GSM8K | Exceeds 90% target |
| Primary backend | Ollama | Project compatibility |
| Fallback model | DeepSeek-R1-8B | Proven reasoning quality |

## Sources

- [Unsloth GLM-4.7-Flash-REAP GGUF](https://huggingface.co/unsloth/GLM-4.7-Flash-REAP-23B-A3B-GGUF)
- [Cerebras REAP Blog](https://www.cerebras.ai/blog/reap)
- [MoE Offloading Guide](https://medium.com/@david.sanftenberg/gpu-poor-how-to-configure-offloading-for-the-qwen-3-235b-a22b-moe-model-using-llama-cpp-13dc15287bed)
- [llama.cpp Quantization Comparison](https://github.com/ggml-org/llama.cpp/discussions/5962)
- [GLM-4.7-Flash Sampling Parameters](https://huggingface.co/zai-org/GLM-4.7-Flash/discussions/6)
- [Ollama GLM-4.7-Flash](https://ollama.com/library/glm-4.7-flash)
