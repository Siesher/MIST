# Quickstart: Advanced STEM Training Pipeline

**Feature**: 014-advanced-training-pipeline
**Date**: 2026-02-12

## Prerequisites

- Google Colab Pro+ with A100 GPU (40GB or 80GB)
- HuggingFace account with access to `Siesher/mits-qwen3-4b-sft` and `Siesher/mits-stem-training-data`
- Google Drive mounted for checkpoint storage

## Pipeline Execution Order

Run notebooks sequentially on Colab. Each stage loads the previous stage's checkpoint.

```
Stage 1: sft_qwen3_4b.ipynb        (EXISTING — already trained)
Stage 2: grpo_qwen3_4b.ipynb       (MODIFIED — curriculum + GDPO)
Stage 3: raft_plus_qwen3_4b.ipynb   (NEW)
Stage 4: star_loop.ipynb            (MODIFIED — AdaSTaR)
Stage 5: dpo_polish_qwen3_4b.ipynb  (NEW)
```

## Configuration

Each notebook has an `A100_VRAM_GB` variable at the top:

```python
A100_VRAM_GB = 40  # Change to 80 for A100 80GB
```

This automatically adjusts batch sizes, generation counts, and memory parameters.

## Implementation Order (for developers)

1. **stem_rewards.py** — Update reward infrastructure first (foundation dependency)
2. **grpo_qwen3_4b.ipynb** — Add curriculum learning to existing GSPO notebook
3. **raft_plus_qwen3_4b.ipynb** — Create new RAFT++ notebook
4. **star_loop.ipynb** — Upgrade to AdaSTaR
5. **dpo_polish_qwen3_4b.ipynb** — Create new DPO polish notebook

## Key Files

| File | Action | Dependencies |
|------|--------|-------------|
| `training/scripts/stem_rewards.py` | MODIFY | verify_answers.py |
| `notebooks/grpo_qwen3_4b.ipynb` | MODIFY | stem_rewards.py, sort_curriculum.py |
| `notebooks/raft_plus_qwen3_4b.ipynb` | CREATE | verify_answers.py |
| `notebooks/star_loop.ipynb` | MODIFY | verify_answers.py, sort_curriculum.py |
| `notebooks/dpo_polish_qwen3_4b.ipynb` | CREATE | verify_answers.py, stem_rewards.py |

## Verification

After each stage, check the saved JSON metrics:
- `gspo_eval_metrics.json` — per-domain reward and accuracy after GSPO
- `raft_eval_metrics.json` — accuracy delta over GSPO
- `star_eval_metrics.json` — per-iteration accuracy + staleness stats
- `dpo_eval_metrics.json` — accuracy vs format score trade-off

Final model: `checkpoints/dpo_qwen3_4b/final_adapter/`
