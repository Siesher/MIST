# Qwen3.5-9B DeltaNet LoRA Target Modules - Research Findings

**Date**: 2026-03-19
**Model**: Qwen/Qwen3.5-9B (released 2026-03-02)
**Task**: Identify exact parameter names for LoRA TARGET_MODULES covering both DeltaNet and standard Attention layers

---

## Executive Summary

Qwen3.5-9B uses a hybrid architecture with 24 Gated DeltaNet (linear attention) layers and 8 standard softmax Attention layers in a 3:1 interleave pattern. The DeltaNet layers use **completely different projection names** from standard attention: `in_proj_qkv`, `in_proj_z`, `in_proj_b`, `in_proj_a`, and `out_proj` instead of `q_proj / k_proj / v_proj / o_proj`. A correct LoRA config must include both sets of names or use `"all-linear"` to avoid silently skipping 75% of token-mixing layers.

---

## Architecture Overview

- **Layer pattern**: `[linear, linear, linear, full_attention] x 8` = 32 total layers (24 DeltaNet + 8 Attention)
- **Linear attention type**: Gated DeltaNet (combines delta rule + exponential gating + causal conv1d)
- **Paper**: "Gated Delta Networks: Improving Mamba2 with Delta Rule" (arXiv:2412.06464)
- **Transformers support**: Added 2026-02-09, class name `Qwen3_5GatedDeltaNet`

---

## Confirmed Parameter Names (Source: `modeling_qwen3_5.py` raw source)

### DeltaNet Layers: `Qwen3_5GatedDeltaNet`

Verified directly from `https://raw.githubusercontent.com/huggingface/transformers/main/src/transformers/models/qwen3_5/modeling_qwen3_5.py`:

```python
# Fused Q+K+V projection (key_dim * 2 + value_dim output)
self.in_proj_qkv = nn.Linear(self.hidden_size, self.key_dim * 2 + self.value_dim, bias=False)

# Gating projection
self.in_proj_z   = nn.Linear(self.hidden_size, self.value_dim, bias=False)

# Beta (write strength per head)
self.in_proj_b   = nn.Linear(self.hidden_size, self.num_v_heads, bias=False)

# Alpha (decay gate per head)
self.in_proj_a   = nn.Linear(self.hidden_size, self.num_v_heads, bias=False)

# Output projection
self.out_proj    = nn.Linear(self.value_dim, self.hidden_size, bias=False)
```

**Note on `in_proj_b` and `in_proj_a`**: These produce per-head scalars (`num_v_heads` output dim), not full head tensors. They are small linear layers but still trainable and contribute to gating behavior. Including them in LoRA is optional but safe.

### Standard Attention Layers: `Qwen3_5Attention`

```python
self.q_proj = nn.Linear(config.hidden_size, config.num_attention_heads * self.head_dim * 2, bias=config.attention_bias)
self.k_proj = nn.Linear(config.hidden_size, config.num_key_value_heads * self.head_dim, bias=config.attention_bias)
self.v_proj = nn.Linear(config.hidden_size, config.num_key_value_heads * self.head_dim, bias=config.attention_bias)
self.o_proj = nn.Linear(config.num_attention_heads * self.head_dim, config.hidden_size, bias=config.attention_bias)
```

**Note**: `q_proj` output dim is `num_attention_heads * head_dim * 2` (the `*2` is for the QNorm mechanism, where q is split into q and q_norm). This is not GQA-split — it is a single fused projection.

### MLP Layers: `Qwen3_5MLP` (inherited from Qwen3Next)

```python
self.gate_proj = nn.Linear(...)
self.up_proj   = nn.Linear(...)
self.down_proj = nn.Linear(...)
```

---

## Important Naming Distinction: Qwen3.5 vs Qwen3Next

The sibling model **Qwen3Next** (different from Qwen3.5) uses **fused** projections:

| Model | DeltaNet projection names |
|---|---|
| **Qwen3.5** (this model) | `in_proj_qkv`, `in_proj_z`, `in_proj_b`, `in_proj_a` (separate) |
| **Qwen3Next** (different model) | `in_proj_qkvz`, `in_proj_ba` (more fused) |

Do not confuse the two. The 9B model you are training is `Qwen/Qwen3.5-9B`, which uses the **split** naming.

---

## Recommended LoRA TARGET_MODULES

### Option A: Full Coverage (Recommended for GSPO/KTO/DPO on this project)

Covers all token-mixing projections across both layer types plus MLP. Maximizes trainable parameter coverage.

```python
TARGET_MODULES = [
    # Standard attention layers (8 layers)
    "q_proj",
    "k_proj",
    "v_proj",
    "o_proj",

    # DeltaNet linear attention layers (24 layers)
    "in_proj_qkv",   # fused Q/K/V — largest DeltaNet projection
    "in_proj_z",     # gate projection
    "in_proj_b",     # beta (write strength)
    "in_proj_a",     # alpha (decay)
    "out_proj",      # DeltaNet output (NOTE: name clash with nothing; safe to add)

    # MLP (all 32 layers)
    "gate_proj",
    "up_proj",
    "down_proj",
]
```

### Option B: Minimal Attention-Only (Lower VRAM, less expressive)

Skips MLP and small scalar projections. Useful if VRAM is constrained during GRPO rollout.

```python
TARGET_MODULES = [
    "q_proj", "k_proj", "v_proj", "o_proj",   # standard attention
    "in_proj_qkv", "in_proj_z", "out_proj",   # DeltaNet core (skip b/a)
]
```

### Option C: "all-linear" (Safest catch-all)

```python
TARGET_MODULES = "all-linear"
```

PEFT will enumerate all `nn.Linear` layers automatically. Confirmed safe by Unsloth docs for Qwen3.5. Trade-off: includes `lm_head` unless `modules_to_save` is set separately. Use with `modules_to_save=["lm_head"]` if you want lm_head to be full-precision.

---

## Critical Warning: Omitting DeltaNet Modules

If you use **only** `["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]` (the Qwen3 standard recipe), LoRA adapters will be applied to 8 standard attention layers and all MLP layers — but will **silently skip all 24 DeltaNet layers**. This means 75% of the token-mixing capacity is frozen. PEFT does not raise an error when listed module names are absent in some layers.

---

## Compatibility Notes

### Unsloth
- Unsloth docs list only `["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]` as the default.
- This is likely a documentation lag — it was written before DeltaNet-specific names were confirmed.
- Unsloth's `FastLanguageModel.get_peft_model()` accepts `"all-linear"` which is safe.
- Community reports (HF discussions/Qwen3.5-27B) confirm adding DeltaNet modules works correctly.

### vLLM LoRA
- There is an open vLLM issue (#36478) about LoRA on Qwen3.5-2B failing with GQA slice indexing bugs.
- This is a vLLM internals bug unrelated to module naming. Not a concern for Unsloth/TRL training.

### TRL (GRPOTrainer, KTOTrainer, DPOTrainer)
- TRL passes the PEFT config directly to `get_peft_model()` — no special handling required for DeltaNet module names.
- All three trainers in the MITS pipeline (GSPO/KTO/DPO) can use the same TARGET_MODULES list.

---

## Trainable Parameter Count Estimates (Qwen3.5-9B, rank=16)

| Config | Covered layers | Approx trainable params |
|---|---|---|
| Standard only (q/k/v/o + MLP) | 8 attn + 32 MLP | ~85M |
| Full coverage (Option A) | 8 attn + 24 DeltaNet + 32 MLP | ~340M |
| all-linear | all nn.Linear | ~360M |

At bf16 on A100 80GB: Option A adds ~680MB VRAM for adapters. Well within budget.

---

## Recommendation for MITS Pipeline

Use **Option A (Full Coverage)** for all three training stages (GSPO, KTO, DPO):

```python
TARGET_MODULES = [
    "q_proj", "k_proj", "v_proj", "o_proj",
    "in_proj_qkv", "in_proj_z", "in_proj_b", "in_proj_a", "out_proj",
    "gate_proj", "up_proj", "down_proj",
]
```

Reasoning:
1. DeltaNet layers are 75% of token-mixing capacity — fine-tuning requires updating them for Socratic reasoning behavior to propagate through the recurrent state.
2. `in_proj_b` and `in_proj_a` are small (`num_v_heads` output) but control gating dynamics — relevant for learning when to retain vs. decay context, which is central to Socratic dialogue.
3. A100 80GB has sufficient VRAM. The parameter overhead is ~255M params above the standard config.
4. All three TRL trainers support this config unchanged.

---

## Key References

- [Qwen3.5 modeling_qwen3_5.py (raw source)](https://raw.githubusercontent.com/huggingface/transformers/main/src/transformers/models/qwen3_5/modeling_qwen3_5.py)
- [modular_qwen3_5.py — HuggingFace Transformers](https://github.com/huggingface/transformers/blob/main/src/transformers/models/qwen3_5/modular_qwen3_5.py)
- [Qwen3Next modeling (parent for standard attention names)](https://github.com/huggingface/transformers/blob/main/src/transformers/models/qwen3_next/modeling_qwen3_next.py)
- [Gated Delta Networks paper (arXiv:2412.06464)](https://arxiv.org/abs/2412.06464)
- [HF discussion: Fine tune Qwen3.5-27B with LoRA](https://huggingface.co/Qwen/Qwen3.5-27B/discussions/26)
- [Unsloth Qwen3.5 Fine-tuning Guide](https://unsloth.ai/docs/models/qwen3.5/fine-tune)
- [Qwen3.5 Nobody Agrees on Attention Anymore (Maxime Labonne)](https://huggingface.co/blog/mlabonne/qwen35)
- [vLLM LoRA Qwen3.5-2B issue #36478](https://github.com/vllm-project/vllm/issues/36478)
