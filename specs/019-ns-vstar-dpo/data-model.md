# Data Model: NS-V-STaR-DPO

**Feature**: 019-ns-vstar-dpo

## Schemas

### Honest Eval Report

`evaluation/reports/honest_full_precision_YYYYMMDD.json`

```json
{
  "run_id": "honest_full_precision_20260502",
  "timestamp": "2026-05-02T10:30:00Z",
  "git_commit": "<hash>",
  "decoding_config": {
    "num_predict": 4096,
    "enable_thinking": true,
    "temperature": 0.0,
    "system_prompt": "SYSTEM_PROMPT_CALC"
  },
  "dataset": {
    "path": "training/data/eval_dataset.jsonl",
    "size_total": 218,
    "size_calc_subset": 143,
    "filter": "answer_type in [numeric, latex_boxed]"
  },
  "models": [
    {
      "model_id": "base",
      "checkpoint": "Qwen/Qwen3.5-9B",
      "adapter_id": null,
      "metrics": {
        "accuracy": 0.0,
        "socratic_score": 0.0,
        "leak_rate": 0.0,
        "format_compliance": 0.0
      },
      "per_task_path": "results/per_task_base.jsonl"
    }
  ]
}
```

### V-STaR Completions

`data/vstar/completions.jsonl` (one record per task)

```json
{
  "task_id": "<uuid>",
  "prompt": "<full chat-templated prompt>",
  "ground_truth": "<expected final answer>",
  "domain": "math|physics|chem|bio|cs",
  "difficulty": "easy|medium|hard",
  "completions": [
    {
      "idx": 0,
      "text": "<full thinking + final answer>",
      "thinking_text": "<thinking block>",
      "final_answer": "<extracted answer>",
      "tokens": 1234,
      "temperature": 0.7,
      "seed": 42
    }
  ],
  "metadata": {
    "seed_model_id": "Siesher/mits-qwen3-9b-{gspo|kto|base}",
    "generation_timestamp": "2026-05-XX",
    "decoding_config_id": "<sha256>"
  }
}
```

### Score Cache Entry

`data/cache/{prm,pedagogy}_scores.json`

```json
{
  "<sha256(model_id + prompt + completion)>": {
    "component": "prm",
    "value": 0.78,
    "model_version": "Skywork/Skywork-o1-Open-PRM-Qwen-2.5-1.5B",
    "details": {
      "step_scores": [0.9, 0.85, 0.7, 0.65, 0.8],
      "aggregation": "mean"
    },
    "timestamp": "2026-05-XX",
    "run_id": "<run hash>"
  }
}
```

### Subset Manifest (lean-demo)

`data/vstar/subset_manifest.json` — produced by `training/scripts/build_subset.py`

```json
{
  "manifest_version": "1.0",
  "feature": "019-ns-vstar-dpo",
  "scope": "lean-demo",
  "source_dataset": "data/training/dialogs.jsonl",
  "source_size": 3875,
  "target_size": 1000,
  "actual_size": 1014,
  "stratify_by": ["domain", "difficulty"],
  "random_state": 42,
  "task_ids": ["<uuid_1>", "<uuid_2>", "..."],
  "proportions": {
    "by_domain": {"math": 0.40, "physics": 0.20, "chem": 0.15, "bio": 0.15, "cs": 0.10},
    "by_difficulty": {"easy": 0.30, "medium": 0.50, "hard": 0.20},
    "by_domain_difficulty": {
      "math_easy": 0.12, "math_medium": 0.20, "math_hard": 0.08,
      "physics_easy": 0.06, "...": "..."
    }
  },
  "edge_cases_applied": [
    {"domain": "cs", "difficulty": "hard", "available": 67, "target": 80, "action": "include_all_67"}
  ],
  "git_commit": "<hash>"
}
```

### Composite Score (per completion)

In-memory or `data/scores/composite_scores.jsonl`

```json
{
  "task_id": "<uuid>",
  "completion_idx": 0,
  "correctness": 1.0,
  "prm_score": 0.78,
  "pedagogy_score": 0.85,
  "weights": {"correctness": 0.5, "prm": 0.25, "pedagogy": 0.25},
  "composite": 0.9075
}
```

### DPO Pair

`data/vstar/dpo_pairs.jsonl`

```json
{
  "pair_id": "<task_id>__<chosen_idx>__<rejected_idx>",
  "task_id": "<uuid>",
  "prompt": "<full chat-templated prompt>",
  "chosen": "<completion text>",
  "rejected": "<completion text>",
  "scores_chosen": {"correctness": 1.0, "prm": 0.78, "pedagogy": 0.85, "composite": 0.9075},
  "scores_rejected": {"correctness": 0.0, "prm": 0.42, "pedagogy": 0.55, "composite": 0.3675},
  "margin": 0.54,
  "metadata": {
    "weights_id": "default_v1",
    "tau": 0.15,
    "seed_model_id": "Siesher/mits-qwen3-9b-gspo"
  }
}
```

### Ablation Manifest

`data/vstar/ablations/{noprm,nospoiler}_manifest.json`

```json
{
  "ablation_id": "noprm",
  "weights": {"correctness": 0.5, "prm": 0.0, "pedagogy": 0.5},
  "rationale": "Изолирует вклад PRM. Pedagogy-only reward + correctness.",
  "expected_effect": "Падение на reasoning-heavy подмножестве (multi-step), сохранение pedagogy axis",
  "training_config": {
    "base_pairs": "data/vstar/dpo_pairs_noprm.jsonl",
    "trainer_config": "training/configs/dpo_default.yaml"
  }
}
```

### Final Comparison Report

`evaluation/reports/final_comparison_YYYYMMDD.json`

```json
{
  "models": [
    "base", "gspo", "kto", "ns_vstar_dpo", "ablation_noprm", "ablation_nospoiler"
  ],
  "benchmarks": ["honest_218task", "mathtutorbench_500subset"],
  "metrics_per_model": {
    "ns_vstar_dpo": {
      "honest_218task": {
        "accuracy": 0.0,
        "socratic_score": 0.0,
        "leak_rate": 0.0,
        "ci_95": [0.0, 0.0]
      },
      "mathtutorbench_500subset": {
        "scaffolding_score": 0.0,
        "answer_leak_score": 0.0
      }
    }
  },
  "pareto_front": ["best-of model_id list по accuracy/pedagogy frontier"],
  "ablation_attribution": {
    "prm_contribution_pp": 0.0,
    "nospoiler_contribution_pp": 0.0
  }
}
```

## Entity Relationships

```text
Honest Eval Report (Phase 0)
        │
        └─→ seed_choice.md (D-001)
              │
              └─→ V-STaR Completions (Phase 1)
                    │
                    ├─→ PRM Score Cache (Phase 2)
                    └─→ Pedagogy Score Cache (Phase 3)
                          │
                          └─→ Composite Scores (Phase 4)
                                │
                                └─→ DPO Pairs (Phase 4)
                                      │
                                      └─→ Trained Adapter (Phase 5)
                                            │
                                            ├─→ −PRM Ablation (Phase 6)
                                            ├─→ −NoSpoiler Ablation (Phase 6)
                                            └─→ Final Comparison Report (Phase 7)
                                                  │
                                                  └─→ Diploma chapter (Phase 8)
```

## Validation Rules

- **Honest Eval Report**: `accuracy ∈ [0,1]`, `git_commit` non-empty, all 3 models present.
- **Completions**: `len(completions) == N` per task, `task_id` unique, `final_answer` extractable.
- **Score Cache**: keys = sha256, values = `{component, value, model_version}`. Reject entries без `model_version`.
- **DPO Pair**: `margin ≥ τ`, `chosen.composite > rejected.composite`, `task_id` consistent.
- **Final Comparison**: 6 models × 2 benchmarks, no missing cells.
