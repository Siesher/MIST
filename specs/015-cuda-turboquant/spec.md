# Feature Specification: TurboQuant KV Cache Compression

**Feature Branch**: `015-cuda-turboquant`
**Created**: 2026-03-28
**Status**: Draft
**Input**: Implement TurboQuant (arXiv:2504.19874, ICLR 2026) — online vector quantization for KV cache compression with near-optimal distortion rate. Custom CUDA kernels for Qwen3.5-9B inference acceleration.

**Paper**: [TurboQuant: Online Vector Quantization with Near-optimal Distortion Rate](https://arxiv.org/abs/2504.19874)
**Authors**: Amir Zandieh, Majid Daliri, Majid Hadian, Vahab Mirrokni (Google Research)

## Background

TurboQuant is an online vector quantization algorithm that achieves near-optimal distortion rates (within ~2.7x of information-theoretic lower bounds) for compressing high-dimensional vectors. Unlike weight quantization (GPTQ/AWQ), TurboQuant targets the **KV cache** — the attention mechanism's memory bottleneck during inference.

**Algorithm components:**
1. **Random rotation** — applies a random orthogonal transform to input vectors, inducing a concentrated Beta distribution across coordinates
2. **Optimal scalar quantizers** — applies per-coordinate MSE-optimal quantization to the rotated vectors (PolarQuant)
3. **QJL residual correction** — applies a 1-bit Quantized Johnson-Lindenstrauss transform to the quantization residuals, recovering inner product accuracy

**Key results from the paper:**
- 3.5 bits/channel: absolute quality neutrality on LLM benchmarks
- 2.5 bits/channel: marginal quality degradation
- 6x+ KV memory reduction across benchmarks
- 8x speedup in attention logit computation on H100 GPUs
- Data-oblivious: no fine-tuning or calibration data required
- Models tested: Gemma, Mistral, Llama-3.1-8B-Instruct

## User Scenarios & Testing

### User Story 1 — KV Cache Compression for Longer Contexts (Priority: P1)

A MITS developer runs the Qwen3.5-9B tutor model on a consumer GPU (8–12 GB VRAM). Currently `num_ctx=4096` is limited by KV cache memory. With TurboQuant compressing the KV cache to 3–4 bits per channel, the effective context window can grow to 8192–16384 tokens without additional VRAM, enabling longer multi-turn Socratic dialogues.

**Why this priority**: KV cache is the primary memory bottleneck for local inference. Expanding context directly impacts tutoring quality (longer sessions, better memory of student progress).

**Independent Test**: Run Qwen3.5-9B with TurboQuant-compressed KV cache on a 12GB GPU. Verify `num_ctx=8192` fits in memory and produces identical or near-identical outputs vs baseline `num_ctx=4096` with fp16 KV cache.

**Acceptance Scenarios**:

1. **Given** a Qwen3.5-9B model loaded with 12GB VRAM budget, **When** TurboQuant KV compression is enabled at 4 bits/channel, **Then** the model serves `num_ctx=8192` without OOM errors.
2. **Given** identical prompts, **When** comparing fp16 KV cache vs TurboQuant 3.5-bit KV cache, **Then** output quality on the MITS 150-problem eval benchmark degrades by less than 2% accuracy.
3. **Given** a multi-turn Socratic dialogue of 20+ exchanges, **When** using compressed KV cache, **Then** the model correctly references information from early turns.

---

### User Story 2 — Faster Attention Computation (Priority: P2)

During inference, attention logit computation is memory-bandwidth-bound. TurboQuant's fused quantized-attention CUDA kernel computes attention directly on compressed KV vectors, avoiding the dequantize→compute→requantize roundtrip. The MITS tutor responds faster, improving the student experience.

**Why this priority**: Latency directly impacts student engagement. Sub-2-second first-token latency keeps students in flow state.

**Independent Test**: Benchmark attention kernel latency on the same model with fp16 KV vs TurboQuant 4-bit KV. Measure tokens/second and time-to-first-token.

**Acceptance Scenarios**:

1. **Given** a prompt of 2048 tokens, **When** using TurboQuant fused attention, **Then** time-to-first-token improves by at least 30% compared to fp16 KV baseline.
2. **Given** continuous token generation, **When** KV cache is compressed, **Then** sustained throughput (tokens/second) improves by at least 20%.

---

### User Story 3 — PyTorch Integration for Benchmarking (Priority: P3)

A researcher (MITS developer) benchmarks TurboQuant against Ollama's built-in `q8_0`/`q4_0` KV cache quantization to validate the approach before deeper integration. The researcher uses a Python API to compress/decompress tensors and measure distortion.

**Why this priority**: Validation step before committing to Ollama-level integration. Reduces risk by proving quality on MITS-specific data.

**Independent Test**: Run the PyTorch TurboQuant module on sample KV tensors from Qwen3.5-9B, measure MSE distortion, compare to Ollama's native KV quant.

**Acceptance Scenarios**:

1. **Given** KV tensors extracted from Qwen3.5-9B inference, **When** compressed with TurboQuant at 4 bits/channel, **Then** MSE distortion is lower than Ollama's `q4_0` KV quantization at the same bit budget.
2. **Given** the PyTorch module, **When** called with `turbo_quant.compress(kv_tensor, bits=3.5)`, **Then** it returns compressed representation and `turbo_quant.decompress()` reconstructs with documented distortion bounds.

---

### Edge Cases

- What happens when input vectors have extreme outlier values (common in attention heads)?
- How does compression quality degrade with very short sequences (< 128 tokens) where statistical assumptions weaken?
- What happens when VRAM is insufficient for even the compressed KV cache at large context sizes?
- How does the random rotation matrix interact with model-specific attention patterns (GQA in Qwen3.5)?

## Requirements

### Functional Requirements

- **FR-001**: System MUST implement the TurboQuant three-stage pipeline: random rotation → per-coordinate scalar quantization → QJL residual correction
- **FR-002**: System MUST support configurable bit widths: 2.5, 3, 3.5, and 4 bits per channel
- **FR-003**: System MUST provide CUDA kernels for: (a) KV tensor compression, (b) KV tensor decompression, (c) fused compressed-attention (Q × compressed-K → logits)
- **FR-004**: System MUST expose a Python/PyTorch API for compress/decompress operations with standard tensor inputs
- **FR-005**: System MUST operate in data-oblivious mode (no calibration dataset required) — the random rotation matrix is generated once per model load
- **FR-006**: System MUST support Grouped Query Attention (GQA) as used by Qwen3.5-9B (fewer KV heads than query heads)
- **FR-007**: System MUST provide benchmarking utilities to compare distortion and throughput against fp16 and Ollama native KV quantization (`q4_0`, `q8_0`)
- **FR-008**: System MUST handle the head dimension sizes used by Qwen3.5-9B (128-dimensional KV vectors)

### Key Entities

- **KVCache**: Per-layer key and value tensors, shape `[batch, num_kv_heads, seq_len, head_dim]`
- **CompressedKVCache**: Quantized representation storing: rotated-and-quantized codes (uint8/uint4), scale factors, QJL sign bits for residuals
- **RotationMatrix**: Random orthogonal matrix of shape `[head_dim, head_dim]`, generated once per model load, shared across layers
- **QuantizationConfig**: Bit width, number of QJL random projections, optional per-head settings

## Success Criteria

### Measurable Outcomes

- **SC-001**: KV cache memory usage reduced by at least 4x at 4-bit and 6x at 3-bit compared to fp16 baseline, measured on Qwen3.5-9B with `num_ctx=4096`
- **SC-002**: Model can serve `num_ctx=8192` on a 12GB GPU where previously limited to `num_ctx=4096` with fp16 KV cache
- **SC-003**: Accuracy on MITS 150-problem eval benchmark with TurboQuant KV (3.5 bits) within 2% of fp16 KV baseline
- **SC-004**: Time-to-first-token improves by at least 30% for prompts of 2048+ tokens
- **SC-005**: Inner product distortion within 3x of the information-theoretic lower bound (as proven in the paper)
- **SC-006**: Compression and decompression add less than 5% overhead to total inference time

## Assumptions

- Consumer GPU target: NVIDIA RTX 3060/4060 (12GB) to RTX 3090/4090 (24GB), Compute Capability 8.0+ (Ampere/Ada)
- Qwen3.5-9B uses GQA with specific head_dim=128 — kernels optimized for this dimension
- Ollama's GGUF inference engine may not expose internal KV cache hooks — initial implementation targets standalone PyTorch benchmarking; Ollama integration is a follow-up
- The random rotation matrix fits in GPU constant memory for head_dim=128 (128×128×4 = 64KB)
- No training or fine-tuning is required — the algorithm is data-oblivious by design

## Dependencies

- CUDA Toolkit 12.x + cuBLAS
- PyTorch 2.x with CUDA support (for Python bindings and testing)
- Access to Qwen3.5-9B model weights (already available via Ollama in MITS)
- NVIDIA GPU with Compute Capability ≥ 8.0 (for efficient int4/int8 tensor core operations)
