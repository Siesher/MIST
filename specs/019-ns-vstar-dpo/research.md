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

### Process Reward Model (lean-demo choice)

- **Model**: `Skywork/Skywork-o1-Open-PRM-Qwen-2.5-1.5B` (Skywork team, Aug 2025 update)
- **Core idea**: Step-level scoring math chain-of-thought (each step ∈ [0, 1]), specifically **tuned for o1-style long thinking traces**.
- **Why this variant** (not Qwen2.5-Math-PRM-7B):
  - **Format alignment**: Skywork-o1 trained on long reasoning traces with `<think>` blocks → matches Qwen3.5-9B thinking mode distribution
  - **Compute**: 1.5B vs 7B → ~5× faster scoring, ~3GB bf16 vs 14GB → fits with tutor 9B in одной 96GB сессии
  - **Lean-demo trade-off**: 1.5B показывает ~70% step-accuracy vs ~80% у 7B на ProcessBench; для **direction-of-effect** (within-task ranking) этого достаточно — monotonicity preserved
- **Limitation**: distribution mismatch остаётся (Qwen2.5-base PRM scoring Qwen3.5 generations). **Документировано** в diploma "Limitations" section. Mitigated тем, что PRM в основном детектирует логические ошибки (model-agnostic — `x + 5 = 13 → x = 18` неверно для любой LM).
- **Adaptation**: Aggregate per-step scores via mean (D-005) → один scalar PRM-score per completion. Reward component, не финальный verifier.
- **Future Work alternative**: Rubric Reward (arXiv:2510.07774, Oct 2025) — заменяет PRM rubric-based scoring, фундаментально решает distribution mismatch и Miracle-Steps проблему. Вынесено за scope диплома, рассмотрено для extended paper.

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

### D-002: Reward Weights `(w₁, w₂, w₃)` — LOCKED for lean-demo

**Choice**: `(w_correctness, w_PRM, w_pedagogy) = (0.5, 0.25, 0.25)` — **зафиксировано без эмпирического sweep**.
**Rationale**: Correctness — non-negotiable (тьютор обязан вести к правильному ответу), но pedagogy и step-quality — то, что отличает tutor от solver. Сумма `pedagogy + PRM = 0.5` уравновешивает correctness, не подавляя её.
**Alternatives considered (отклонены без эмпирики)**:
- Equal weights `(1/3, 1/3, 1/3)` — позволяет "high-pedagogy + wrong-answer" pair выиграть у "low-pedagogy + correct".
- `(0.6, 0.2, 0.2)` — слишком correctness-heavy, риск убить pedagogy gains GSPO/KTO стадий.
- `(0.4, 0.3, 0.3)` — близко к default, отличие в пределах PRM/judge noise.
**Why no sweep in lean-demo**: sensitivity analysis (3 configs × 200-task mini-subset × short DPO) стоит ~17 vu и 3 GPU-hours. В lean scope этот compute выделяется на **резерв для retries**. Принципиальное обоснование выбора весов считаем достаточным для proof-of-concept.
**Future Work**: sensitivity sweep — обязательное расширение для full-scale paper.
**Ablation в этом scope**: единственная — `w₂=0` (`-PRM` ablation, FR-006). `w₃=0` опускается (No-Spoiler effect уже опубликован).

### D-003: Number of Completions per Task (N) — lean-demo scope

**Choice**: N=4 на **1000-task stratified subset** (вместо full 3875).
**Rationale**:
- 4 completions дают C(4,2)=6 потенциальных пар; после τ-фильтра обычно остаётся 1-2 high-margin pairs per task.
- Subset 1000 instead of 3875: 4× меньше compute (~22 vu vs ~88 vu для Phase 1) при сохранении достаточной statistical power для direction-of-effect (1000 pairs → CIs ~2-3pp wide на accuracy metric).
- Stratified sampling сохраняет domain proportions (math/physics/chem/bio/cs) — pedagogically valid sample.
**Compute check**: `4 × 1000 × ~30s/completion ≈ 33 GPU-h raw → batched batch_size=16 на 96GB → ~2-3 h`.
**Future Work**: full 3875-task replication — extended paper scope.
**Fallback**: Если valid pair coverage < 50% на 1000-subset, снижаем τ до 0.10 (вместо увеличивания N).

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

**Choice**: Primary — Lightning AI **RTX 6000 Pro Blackwell 96GB** (8.71 vu/h, 600 vu pool); secondary — Colab Pro+ (A100 80GB) для Phase 0.
**Rationale**:
- 96GB VRAM enables co-located scoring (Skywork-PRM-1.5B + Qwen3.5-9B + KV cache в одной сессии) → -25 vu vs split-session approach.
- Lightning лучше для long jobs (нет idle disconnect).
- Lean-demo phases короткие (2-3h каждая), все умещаются в одну Lightning сессию или несколько Colab sessions.
- Phase 0 specifically на Colab — notebook готов, не нужны 96GB.

### D-008: τ threshold for valid pairs

**Choice**: τ = 0.15 (на composite ∈ [0, 1])
**Rationale**: 15% gap на composite scale соответствует distinguishable difference (примерно одна категория judge оценки). Статистически значимый margin при N=4.
**Adaptive rule (lean-demo)**: Если coverage < 50%, снижаем до τ=0.10. Если pairs > 90% coverage, поднимаем до τ=0.20.

### D-009: Subset Sampling Strategy (lean-demo)

**Choice**: Stratified by `(domain, difficulty)` from `data/training/dialogs.jsonl`, target 1000 tasks. `random_state=42`.
**Rationale**:
- Random sample может перекосить domain distribution (e.g., 80% math, 5% chem) → bias в pedagogy axis (math задачи меньше leak risk чем open-ended biology).
- Stratified гарантирует сохранение proportions полного датасета.
- 1000 tasks даёт ~700-1000 valid pairs после τ-filter — достаточно для direction-of-effect detection при wide CI.
**Edge**: если domain D имеет <100 примеров в полном датасете, включаем все имеющиеся (без strict 1000 cap → возможен subset 950-1100).
**Manifest**: `data/vstar/subset_manifest.json` с list of `task_ids`, per-domain proportions, sampling seed.

### D-010: Single-Ablation Choice — `-PRM` only (lean-demo)

**Choice**: Один ablation run — `w_PRM = 0` (composite = `0.5·correctness + 0.5·pedagogy`).
**Rationale**:
- **Why `-PRM` not `-NoSpoiler`**: PRM-component — наш delta. No-Spoiler effect уже опубликован в arXiv:2505.15607 (EMNLP 2025) — повторение чужой работы тратит compute.
- **Why not joint `-PRM-NoSpoiler` (correctness-only)**: эквивалентно стандартному outcome-only DPO (Rafailov 2023), известному since 2023.
- **Why not all three ablations**: lean scope; +176 vu compute.
**Acceptable null result**: если `-PRM` performs ≈ full NS-V-STaR-DPO, репортуется как honest negative finding в Discussion: possible causes — PRM noise, distribution mismatch, in-distribution generation already encodes step quality through correctness signal.

## Open Questions

- **Q1 (resolved by lean-demo)**: ~~Sweep по reward weights~~ → принципиальное обоснование D-002 без эмпирики. Sweep вынесен в Future Work.
- **Q2 (lean-demo scope)**: MathTutorBench size — 100-task spot check (`random_state=42`), не full benchmark.
- **Q3 (out of scope)**: Production deployment final adapter — требует q4 conversion для Ollama. Отдельная под-фаза после Phase 8 (writeup).
- **Q4 (Future Work)**: Rubric Reward (arXiv:2510.07774) как замена PRM-component — fundamentally addresses distribution mismatch и Miracle-Steps issue. Extended paper scope.

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
  year={2024},
  note={Reference for PRM methodology; we use Skywork-o1-Open-PRM-Qwen-2.5-1.5B as concrete model}
}

@misc{skywork2024prm,
  title={Skywork-o1-Open-PRM: Process Reward Model for o1-style Reasoning},
  author={Skywork AI Team},
  year={2024},
  note={HuggingFace: Skywork/Skywork-o1-Open-PRM-Qwen-2.5-1.5B, last updated Aug 2025}
}

@article{rubric2025,
  title={Curing Miracle Steps in LLM Mathematical Reasoning with Rubric Rewards},
  journal={arXiv preprint},
  year={2025},
  note={arXiv:2510.07774, listed as Future Work alternative to PRM}
}

@article{mathtutorbench2025,
  title={MathTutorBench: Benchmarking Pedagogical Capabilities of LLMs},
  journal={EMNLP 2025},
  year={2025},
  note={arXiv:2502.18940}
}

@article{processbench2024,
  title={ProcessBench: Identifying Process Errors in Mathematical Reasoning},
  author={Zheng, Chujie and others},
  journal={arXiv preprint arXiv:2412.06559},
  year={2024},
  note={Used to validate PRM choice — Skywork-o1-1.5B preserves direction-of-effect ranking}
}

@article{rafailov2023dpo,
  title={Direct Preference Optimization: Your Language Model is Secretly a Reward Model},
  author={Rafailov, Rafael and others},
  journal={arXiv preprint arXiv:2305.18290},
  year={2023}
}
```
