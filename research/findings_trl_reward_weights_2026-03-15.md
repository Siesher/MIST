# TRL reward_weights in GRPOConfig: Version Research

Date: 2026-03-15

## Executive Summary

`reward_weights` in `GRPOConfig` was introduced in **TRL v0.15.0** (PR #2676 by @hesamsheikh, titled "Add reward weight in multi-reward settings for GRPO"). It is present in every subsequent release including v0.24.0. The latest TRL release is v0.29.0 (Feb 25, 2026), and the latest Unsloth is 2026.3.4 (Mar 8, 2026), which officially supports TRL >= 0.25.0 and works best with TRL 0.27.1.

---

## 1. When Was reward_weights Added?

| TRL Version | reward_weights present? | Notes |
|-------------|------------------------|-------|
| v0.15.0     | YES (first time)       | PR #2676 "Add reward weight in multi-reward settings for GRPO" |
| v0.15.2     | YES                    | Confirmed via grpo_config.py source |
| v0.23.0     | YES                    | Confirmed |
| v0.24.0     | YES                    | Confirmed -- **fully available** |
| v0.29.0     | YES                    | Confirmed, also has multi_objective_aggregation |
| main        | YES                    | Also has multi_objective_aggregation (GDPO) |

**Verdict**: `reward_weights` has been available since TRL v0.15.0. TRL 0.24.0 fully supports it.

---

## 2. Current reward_weights Definition (main branch)

```python
reward_weights: list[float] | None = field(
    default=None,
    metadata={
        "help": "Weights for each reward function. Must match the number of reward functions. If `None`, all "
        "rewards are weighted equally with weight `1.0`."
    },
)
```

Validation in GRPOTrainer: number of reward_weights must equal number of reward functions.

---

## 3. multi_objective_aggregation (GDPO-style decoupled normalization)

This parameter is the key enabler of GDPO-style behavior (normalize each reward independently, then sum with weights):

```python
multi_objective_aggregation: str = "sum_then_normalize"
# Options:
#   "sum_then_normalize"  -- weighted sum first, then normalize (default)
#   "normalize_then_sum"  -- normalize each reward separately, then weighted sum (GDPO paper suggestion)
```

- Present in v0.29.0 (confirmed)
- NOT present in v0.15.2 (not listed in docs)
- Exact introduction version: between v0.15.2 and v0.29.0 (likely added mid-2025 or later)
- The "normalize_then_sum" mode corresponds to the GDPO paper approach

---

## 4. TRL Version Timeline (2025-2026)

| Version | Release Date |
|---------|-------------|
| 0.20.0  | Jul 29, 2025 |
| 0.21.0  | Aug 5, 2025  |
| 0.22.0  | Aug 29, 2025 |
| 0.23.0  | Sep 10, 2025 |
| 0.24.0  | Oct 16, 2025 |
| 0.25.0  | Nov 5, 2025  |
| 0.25.1  | Nov 12, 2025 |
| 0.26.0  | Dec 9, 2025  |
| 0.26.1  | Dec 12, 2025 |
| 0.26.2  | Dec 18, 2025 |
| 0.27.0  | Jan 16, 2026 |
| 0.27.1  | Jan 24, 2026 |
| 0.27.2  | Feb 3, 2026  |
| 0.28.0  | Feb 10, 2026 |
| 0.29.0  | Feb 25, 2026 |

---

## 5. Unsloth 2026.3.x TRL Compatibility

| Item | Detail |
|------|--------|
| Latest Unsloth version | 2026.3.4 (released Mar 8, 2026) |
| TRL minimum requirement | >= 0.25.0 |
| Best-tested TRL version | 0.27.1 (>80% notebook coverage) |
| Latest TRL available | 0.29.0 (Feb 25, 2026) |
| Transformers best-tested | 5.1.0 |

Unsloth February-2026 release notes: "trl==0.27.1 and transformers==5.1.0 are supported well -- previous coverage was 30% of all our 120 notebooks, but now we have >80% coverage."

---

## 6. Practical Recommendation for MITS GSPO Notebook

For the triple-reward GDPO pipeline (correctness + format + Socratic, weights [0.7, 0.15, 0.15]):

1. `reward_weights` -- available in TRL >= 0.15.0. No version concern. Use directly.
2. `multi_objective_aggregation="normalize_then_sum"` -- available in TRL >= 0.29.0 (confirmed in v0.29.0, absent from v0.15.2 docs). Use with caution if pinned to earlier TRL.
   - If on TRL 0.27.1 (Unsloth default), this parameter may NOT be present.
   - Fall back to manual per-reward normalization before summing if needed.
3. Safe target: TRL 0.29.0 + Unsloth 2026.3.4 for full GDPO-style support.

---

## Key References

- TRL v0.15.0 release notes: https://github.com/huggingface/trl/releases/tag/v0.15.0
- TRL GRPOConfig (main): https://github.com/huggingface/trl/blob/main/trl/trainer/grpo_config.py
- TRL GRPO Trainer docs: https://huggingface.co/docs/trl/main/en/grpo_trainer
- Unsloth PyPI: https://pypi.org/project/unsloth/
- Unsloth February-2026 release: https://github.com/unslothai/unsloth/releases/tag/February-2026
- GDPO paper (referenced in TRL docs): "GDPO: Group reward-Decoupled Normalization Policy Optimization for Multi-reward RL Optimization"
