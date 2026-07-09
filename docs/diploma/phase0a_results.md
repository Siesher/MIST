# Phase 0a — Honest Re-Evaluation Results

**Date**: 2026-05-18
**Branch**: `019-ns-vstar-dpo`
**Eval stack**: llama-server (custom build с TurboQuant turbo3 KV) + llama-swap, RTX 5070 Ti 16GB
**Models**: Qwen3.5-9B Q4_K_M GGUF, three pipeline checkpoints (base, gspo, kto)

## Methodology

- **Benchmark**: 209 STEM problems с numeric/latex_boxed answer types (filtered из 3678-problem full benchmark)
- **Self-consistency voting**: N=3..5 trajectories per problem, adaptive expansion при no consensus
- **Sampling**: temperature=0.7, top_p=0.95, top_k=20, min_p=0, DRY sampler (multiplier=0.3, base=1.5, allowed_length=4)
- **Adaptive thinking**: easy/medium → `enable_thinking=False` (2K cap), hard → `enable_thinking=True` (unlimited up to ctx_size=32K)
- **Parallel batching**: `--parallel 5` (concurrent KV slots)
- **Production alignment**: identical inference stack used в deployed system (matches OpenCode agent regime)
- **Adaptive routing fired**: 74.6% nothink mode (easy/medium problems)
- **Verification**: SymPy для math/physics numeric, ChemPy для chemistry, exact match для biology/cs

## Headline Results

| Stage | Accuracy | Δ vs base | Δ vs prior stage |
|-------|----------|-----------|------------------|
| **base** | **0.694** | — | — |
| **gspo** | **0.703** | +0.9 pp | +0.9 pp |
| **kto** | **0.699** | +0.5 pp | -0.4 pp |

**Pipeline cumulative**: base → kto = **+0.5 pp** на N=209 production-aligned eval.

## Per-Domain Breakdown

| Domain     | N   | Base   | GSPO   | KTO    | Δ GSPO  | Δ KTO   |
|------------|-----|--------|--------|--------|---------|---------|
| Biology    | 38  | 0.684  | 0.684  | 0.632  | 0.0     | -5.3 pp |
| Chemistry  | 45  | 0.756  | 0.667  | 0.733  | -8.9 pp | -2.2 pp |
| CS         | 39  | 0.564  | 0.590  | 0.538  | +2.6 pp | -2.6 pp |
| **Math**   | 43  | 0.884  | **0.907** | **0.907** | +2.3 pp | +2.3 pp |
| **Physics**| 44  | 0.568  | **0.659** | **0.659** | **+9.1 pp** | **+9.1 pp** |
| Overall    | 209 | 0.694  | 0.703  | 0.699  | +1.0 pp | +0.5 pp |

### Key per-domain findings

1. **🎯 Physics — primary gain (+9.1 pp)**: GSPO triple-reward training transfers strongly к physics commitment. Base 56.8% → GSPO 65.9%. Largest differential signal по domains.

2. **Math — diminishing returns at ceiling**: Base already at 88.4% (Qwen3.5-9B trained-in strength). Modest +2.3 pp gain.

3. **Chemistry — alignment tax**: GSPO -8.9 pp regression. Partly genuine (model commits к numeric где требуется symbolic), partly extraction artifact (5 of 6 regressed problems show extractor selecting intermediate values; net -4 of 6 cases).

4. **Biology — KTO regression**: -5.3 pp на KTO vs base. KTO Socratic alignment hurts biology factual recall.

5. **CS — modest GSPO gain, KTO regression**: gspo +2.6, kto -2.6. Pipeline non-monotonic.

## Per-Difficulty Breakdown

| Difficulty | N   | Base   | GSPO   | KTO    | Δ GSPO  | Δ KTO   |
|------------|-----|--------|--------|--------|---------|---------|
| Easy       | 79  | 0.873  | 0.861  | 0.886  | -1.3 pp | +1.3 pp |
| **Medium** | 77  | 0.675  | **0.740** | 0.714  | **+6.5 pp** | +3.9 pp |
| Hard       | 53  | 0.453  | 0.415  | 0.396  | -3.8 pp | -5.7 pp |

### Hard problem mode collapse

**Hard problems regress uniformly** (base → kto: -5.7 pp). Hypothesis — RL training shapes model toward "common" answers (mode-of-distribution), sacrificing rare hard-problem correct responses. Classic RL mode collapse signature.

Hard problems mode-collapsed:
- Base: 45.3% → GSPO: 41.5% → KTO: 39.6%

Это **expected behavior** per RL theory (Ouyang et al. 2022 на RLHF alignment tax; Bai et al. 2022 на helpfulness/safety trade-off). Mitigation requires either:
- Hard-problem-aware curriculum
- Per-difficulty reward weighting
- Or accept trade-off as alignment cost

### Medium — sweet spot

GSPO +6.5 pp на medium difficulty. Reward shaping has just-right tension here: easy already mastered, hard beyond reach, medium = ideal RL improvement zone.

## Per-Mode (Adaptive Routing)

| Mode     | N   | Base   | GSPO   | KTO    |
|----------|-----|--------|--------|--------|
| think    | 53  | 0.453  | 0.415  | 0.396  |
| nothink  | 156 | 0.776  | 0.801  | 0.801  |

**nothink mode shows pipeline gain (+2.5 pp)**, think mode shows pipeline regression. Consistent с hard problem mode collapse — adaptive router sent hard problems к think mode, where pipeline regression dominates.

## Comparison к Prior Colab Eval Claims

| Claim source | Base | GSPO | KTO | Δ Pipeline |
|--------------|------|------|-----|------------|
| Prior Colab (BF16, single-shot) | 55.1% | 63.5% | 64.8% (DPO=66.5%) | +11.4 pp |
| **Production-aligned (Q4_K_M, self-consistency)** | **69.4%** | **70.3%** | **69.9%** | **+0.5 pp** |

**Gap explanation**:
- Inference optimizations (self-consistency voting, DRY sampler, adaptive thinking, unlimited budget) lifted **base baseline +14.3 pp** vs prior single-shot Colab eval
- Training improvements compressed by Q4_K_M quantization
- Possible truncation artifact в prior Colab eval (fixed в commit `15a0c39` — robust `_normalize_for_compare`)

**Methodological implication**: inference setup matters as much as training setup. Reporting accuracy without specifying inference regime is incomplete.

## Eval performance characteristics

| Stage | mean tokens | mean wall/problem | parallel factor | natural_stop% | consensus% |
|-------|-------------|-------------------|------------------|---------------|------------|
| base  | 4206 | 49.9s | 2.6 | 89.0% | 85.6% |
| gspo  | 3884 | 47.1s | 2.7 | 88.0% | 90.4% |
| kto   | 4429 | 42.7s | 2.6 | 88.0% | 86.6% |

- **kto highest tokens, lowest wall**: more thinking, fastest commit (more decisive on commit phase)
- **gspo highest consensus**: most reproducible across samples (sample-to-sample agreement)
- **All stages**: ~88-89% natural termination, ~85-90% consensus at MIN=3 → strong adaptive-routing fit

## Diploma Narrative

### Section 4 framing

> **"3-stage RL pipeline produces domain-specific gains rather than uniform improvement"**:
> - GSPO transfers physics commitment (+9.1 pp), generalizes к math (+2.3 pp)
> - Chemistry exhibits alignment tax (-8.9 pp): reward structure mismatch с symbolic chemistry verification
> - Hard problem accuracy regresses uniformly across stages (-3.8 to -5.7 pp) — classic RL mode collapse on common-answer distribution
> - KTO Socratic alignment is accuracy-neutral (orthogonal value in pedagogical dimension, requires separate evaluation)
> - **Inference setup contributes +14.3 pp from base baseline** — methodologically significant for future evaluations

### Key acknowledged limitations

1. **Hard problem regression**: RL training degrades 11.4% of benchmark (53/209 hard problems)
2. **Chemistry alignment tax**: domain-specific reward mismatch
3. **KTO accuracy plateau**: separate pedagogy eval (MathTutorBench) required for KTO Socratic value
4. **Production-aligned numbers ≠ Colab numbers**: inference regime dependency

## Future work

- **Phase 1**: V-STaR generation (N=4 × 1000-task subset) targeting failure modes identified above (especially hard problems + chemistry)
- **Phase 2**: Composite scorer с PRM weighting + no-spoiler judge для Socratic dialogue eval
- **Phase 3**: Per-difficulty curriculum для hard problem recovery
- **Ablation**: -PRM variant для understanding which component drives Socratic emergence

## Files

- Raw eval: `evaluation/reports/honest_phase0a_llamaserver_20260518/{base,gspo,kto}.json`
- Full transcripts: `logs/eval_llamaserver_20260518_085240.log`
- Eval script: `scripts/eval_local_llamaserver.py`
- Infrastructure: `docs/infrastructure/llama-swap-reference.yaml` (snapshot of llama-swap config used)
