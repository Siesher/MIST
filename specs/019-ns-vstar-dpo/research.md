# Research: NS-V-STaR-DPO — научные источники и проектные решения

**Feature**: 019-ns-vstar-dpo | **Last updated**: 2026-05-02

## Источники (literature)

### V-STaR — Verifier-guided Self-Training

- **Citation**: Hosseini et al., 2024 — *V-STaR: Training Verifiers for Self-Taught Reasoners* (arXiv:2402.06457)
- **Core idea**: After SFT, generate N completions per training prompt, score with verifier, keep top — train на (prompt, top) self-distilled trajectories.
- **Why used**: Avoids cross-task confounders inherent в cross-prompt preference data; generation в model's own distribution → robust to drift.
- **Adaptation**: В оригинале verifier — correctness-only (binary). У нас verifier **композитный** — correctness + PRM + pedagogy. Это расширение V-STaR от outcome-only к multi-axis.

### No-Spoiler RL — Pedagogy as Reward

- **Citation**: arXiv:2505.15607 (EMNLP 2025) — *No-Spoiler: Reward Modeling for Pedagogical Tutoring*
- **Core idea**: Define pedagogical correctness как reward — no answer leak, scaffolding present, engagement maintained. Penalize "just-give-answer" trajectories даже если answer correct.
- **Why used**: Standard accuracy-only reward leads tutor to "просто дать ответ" → kills Socratic property. No-Spoiler counter-balances correctness pressure.
- **Adaptation**: Их reward formulation эквивалентна нашему уже-deployed Cerebras Combined Judge (`training/scripts/evaluate_stage.py::evaluate_combined_quality`). Reuse без обучения нового judge — экономия compute.

### Process Reward Model

- **Model**: `Qwen/Qwen2.5-Math-PRM-7B` (Yang et al., 2024 — arXiv:2410.10288)
- **Core idea**: Step-level scoring математической chain-of-thought (each step ∈ [0, 1] where 1 = "step is correct given the prefix").
- **Why used**: Distinguishes "lucky right answer with bad reasoning" vs "principled derivation" — orthogonal к outcome correctness и orthogonal pedagogy.
- **Adaptation**: Aggregate per-step scores via mean (см. Decision 5) → один scalar PRM-score per completion. Используется как reward component, не финальный verifier.

### MathTutorBench — Pedagogical External Benchmark

- **Citation**: arXiv:2502.18940 (EMNLP 2025) — *MathTutorBench: Benchmarking Pedagogical Capabilities of LLMs*
- **Core idea**: Standardized pedagogical benchmark — multi-turn dialogues, scaffolding rubric, answer-leak detection, computational reasoning.
- **Why used**: External validity, sanity-check внутреннего benchmark, comparability с published baselines (other tutor LLMs).
- **Adaptation**: Use English subset (Russian in benchmark отсутствует или ограничен), report alongside custom 218-task Russian benchmark. Caveat: external validity limited к English performance, in-language claims идут только через custom benchmark.

### DPO Foundations

- **Citation**: Rafailov et al., 2023 — *Direct Preference Optimization* (arXiv:2305.18290)
- **Variant used**: TRL `DPOTrainer` с β=0.1 (default conservative), sigmoid loss, no reference free, bf16 forward + fp32 master weights.

## Ключевые решения

### D-001: Seed Checkpoint для V-STaR

**Status**: pending Phase 0 result
**Default proposal**: GSPO (предполагаем best of three)
**Alternatives**: base, KTO
**Rationale**: Self-improvement осмысленен только от лучшего предка. После honest re-eval сравним bf16 metrics base/GSPO/KTO, выберем лучший по `accuracy + 0.5·socratic` (composite metric).
**Decision artifact**: `specs/019-ns-vstar-dpo/seed_choice.md` (генерируется в T003).

### D-002: Reward Weights `(w₁, w₂, w₃)`

**Default**: `(w_correctness, w_PRM, w_pedagogy) = (0.5, 0.25, 0.25)`
**Rationale**: Correctness — non-negotiable (тьютор обязан вести к правильному ответу), но pedagogy и step-quality — то, что отличает tutor от solver. Сумма `pedagogy + PRM = 0.5` уравновешивает correctness, не подавляя её.
**Alternatives considered**:
- Equal weights `(1/3, 1/3, 1/3)` — отвергнуто: позволяет "high-pedagogy + wrong-answer" pair выиграть у "low-pedagogy + correct".
- `(0.6, 0.2, 0.2)` — слишком correctness-heavy, риск убить pedagogy gains GSPO/KTO стадий.
- `(0.4, 0.3, 0.3)` — рассмотреть в sensitivity sweep.
**Validation**: Sensitivity analysis (T015) — sweep по 3 configs `[(0.5/0.25/0.25), (0.4/0.3/0.3), (0.6/0.2/0.2)]` на 200-task mini-subset с short DPO (200 steps). Выбираем лучший Pareto.
**Recorded as ablation candidates**: variants `w₂=0` (без PRM) и `w₃=0` (без pedagogy) — обязательны (FR-006).

### D-003: Number of Completions per Task (N)

**Choice**: N=4
**Rationale**: 4 completions дают C(4,2)=6 потенциальных пар, после τ-фильтра обычно остаётся 1-2 high-margin. N=8 дал бы статистическую мощность, но удваивает compute (8 vs 4 generations + 8 vs 4 PRM scores).
**Compute check**: `4 × 3875 × ~30s/completion ≈ 130 GPU-h raw → batched up to ~10 h на A100 80GB при batch_size=8`.
**Fallback**: Если valid pair coverage < 60%, увеличиваем до N=8 для подмножества "трудных" задач (where все 4 имеют tight scores).

### D-004: Pair Selection Strategy

**Choice**: Within-task top-vs-bottom, **1 pair per task** (или 0, если top-bottom margin < τ).
**Rationale**:
- Within-task устраняет cross-task confounder (разные задачи имеют разную base difficulty).
- 1 pair per task ограничивает overfit на "лёгкие" задачи (где все completions хорошие).
- τ ≈ 0.15 на composite ∈ [0, 1] — статистически значимый margin, не шум judge.
**Alternative**: Все C(N,2) pairs per task — отвергнуто, дублирующиеся pairs снижают signal-to-noise при batch DPO.

### D-005: PRM Aggregation (per-step → per-completion)

**Choice**: Arithmetic mean of step scores
**Rationale**: Простота, robustness к разной длине цепочек.
**Alternatives**:
- Min-aggregation — accentuates worst step, потенциально слишком harsh для длинных цепочек (один плохой шаг убивает completion).
- Product — overpenalizes длинные цепочки (всегда меньше для длинных).
- Geometric mean — middle ground между mean и product, рассмотреть в sensitivity sweep если mean даёт degenerate distributions.
**Decision**: start with mean, escalate to geometric mean при необходимости.

### D-006: Cache Strategy

**Choice**: JSON cache `data/cache/{prm,pedagogy}_scores_{run_id}.json`, keyed by `sha256(model_id + prompt + completion)`.
**Rationale**:
- Idempotency — re-runs не платят compute дважды.
- Особенно важно для Cerebras (paid API, 10 keys в rotation).
- `model_id` в ключе различает scores разных версий PRM или judge.
**Format**: `{key: {component, value, model_version, timestamp}}` для audit trail.

### D-007: Compute Platform

**Choice**: Primary — Colab Pro+ (A100 80GB, есть подписка); secondary — Lightning AI RTX 6000 (8.71 vu/h, есть 600 vu).
**Rationale**:
- Colab cheaper для preemptable workloads (Pro+ flat rate).
- Lightning лучше для long jobs (нет 12h idle disconnect, нет потери session state).
- DPO training (8-12 h) — Lightning.
- Eval / scoring (3-6 h) — Colab.
- Generation (8-10 h) — на грани Colab limit, лучше Lightning.

### D-008: τ threshold for valid pairs

**Choice**: τ = 0.15 (на composite ∈ [0, 1])
**Rationale**: 15% gap на composite scale соответствует distinguishable difference (примерно одна категория judge оценки). Статистически значимый margin при N=4.
**Adaptive rule**: Если coverage < 60%, снижаем до τ=0.10. Если pairs > 90% coverage, поднимаем до τ=0.20 (более строгий signal).

## Open Questions

- **Q1**: На каком scale делать sweep по reward weights (D-002)? Целеполагание: <5h compute → mini-subset 200 задач × 3 configs × short DPO (200 steps). Total ~3h на A100. Acceptable.
- **Q2**: MathTutorBench dataset размер — может потребовать дополнительный compute для full eval; ограничимся random 500-task subset, если full > 4h. Документировать subset selection в `mathtutorbench_eval.ipynb`.
- **Q3**: Production deployment final adapter — требует q4 conversion для Ollama. Это отдельная под-фаза после Phase 8 (writeup), не в scope этого spec'а.

## Citation Stack для diploma chapter

```bibtex
@article{hosseini2024vstar,
  title={V-STaR: Training Verifiers for Self-Taught Reasoners},
  author={Hosseini, Arian and others},
  journal={arXiv preprint arXiv:2402.06457},
  year={2024}
}

@article{nospoiler2025,
  title={No-Spoiler: Reward Modeling for Pedagogical Tutoring},
  journal={EMNLP 2025},
  year={2025},
  note={arXiv:2505.15607}
}

@article{yang2024prm,
  title={Process Reward Models for Math Reasoning},
  author={Yang, An and others (Qwen Team)},
  journal={arXiv preprint arXiv:2410.10288},
  year={2024}
}

@article{mathtutorbench2025,
  title={MathTutorBench: Benchmarking Pedagogical Capabilities of LLMs},
  journal={EMNLP 2025},
  year={2025},
  note={arXiv:2502.18940}
}

@article{rafailov2023dpo,
  title={Direct Preference Optimization: Your Language Model is Secretly a Reward Model},
  author={Rafailov, Rafael and others},
  journal={arXiv preprint arXiv:2305.18290},
  year={2023}
}
```
