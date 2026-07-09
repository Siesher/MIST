# Research: ToM-Tutor

**Feature**: 017-tom-tutor | **Date**: 2026-04-18

## R1: Prompt-Only vs Fine-Tuned ToM

**Decision**: Prompt-only ToM using existing fine-tuned Qwen3.5-9B.

**Rationale**:
- Emergent ToM capability in LLMs ≥7B is empirically demonstrated (Kosinski 2023, [arXiv:2302.02083](https://arxiv.org/abs/2302.02083); Strachan et al., *Nature Human Behaviour* 2024).
- The architectural novelty for the diploma — "ToM as a pipeline stage in LLM tutors" — is validated regardless of how ToM reasoning is implemented.
- Fine-tuning would require 500–1000 annotated (student_message, belief_state) pairs (~1 week) plus Colab compute (~3 hrs), consuming 30% of remaining timeline for marginal quality gain.
- Prompt-based iteration cycle: minutes vs days for fine-tuning.

**Alternatives considered**:
- **LoRA adapter** (Hu et al. 2021, [arXiv:2106.09685](https://arxiv.org/abs/2106.09685)): rejected for budget reasons; reserved as explicit "future work" section in diploma.
- **Few-shot in-context examples only**: strict subset of prompt-only; we'll include 2–3 exemplars inside the prompt for calibration.
- **Zero-shot with CoT**: chosen as fallback when examples don't fit context budget (lite profile).

## R2: BeliefState Schema Structure

**Decision**: Structured dataclass with 4 fields (misconception, topic belief, predicted reactions, confidence) produced via Ollama JSON mode.

**Rationale**:
- JSON mode in Ollama 0.4+ supports structured output for open-source models without ReAct gymnastics (see Ollama docs, `format="json"` parameter).
- A minimal schema avoids over-specification that might force the model into hallucination. Each field has a clear purpose for downstream consumers:
  - `active_misconception` → Navigator uses to re-rank gaps
  - `belief_about_topic` → Tutor uses to shape explanation
  - `predicted_reactions` → Planner uses to pick strategy
  - `confidence` → gates whether any of the above are trusted

**Alternatives considered**:
- **Free-form text** (e.g. "What is the student thinking?"): rejected — downstream consumers need structured access.
- **Richer schema** (emotional state, meta-cognitive flags, attention focus): rejected for MVP — simpler schema forces the prompt to focus.
- **Multiple specialized calls** (one for misconception, one for reaction prediction): rejected — doubles latency on lite profile.

## R3: Pipeline Insertion Point

**Decision**: New `MENTAL_MODEL` stage between `PROFILER` and `PLANNER` in the Orchestrator pipeline.

**Rationale**:
- Profiler currently produces `StudentProfile` with errors, confidence, cognitive load — these inform ToM reasoning, so ToM must run **after** Profiler.
- Planner consumes the belief state to pick strategy, so ToM must run **before** Planner.
- This preserves the GenMentor-style architecture mandated by the project constitution (principle II).
- Matches how cognitive architectures (ACT-R, SOAR) position theory-of-mind between perception and decision stages.

**Alternatives considered**:
- **Inside Planner**: rejected — mixes concerns, hard to disable for A/B eval.
- **In parallel with Profiler**: rejected — Profiler's errors feed ToM reasoning, so sequential dependency exists.
- **At the very start (before Profiler)**: rejected — ToM needs mastery data and error analysis, which Profiler produces.

## R4: Navigator Integration — Gap Re-ranking

**Decision**: Extend `PersonalizedNavigator.diagnose_gap()` with an optional `belief_state` parameter. When present, rerank missing prerequisites by semantic similarity between the active misconception and each prerequisite's tags/content.

**Rationale**:
- Baseline already has 100% any-hit recall — the right gap is always in the returned list. We only need to re-order, not re-discover.
- Re-ranking is cheap (no new graph traversal) and preserves backward compatibility (belief_state=None → current behavior).
- Semantic similarity can be approximated by simple keyword overlap on lite profile (no embeddings required).
- This directly attacks the 60% → 80% root-hit target identified in baseline.

**Alternatives considered**:
- **Full embedding-based similarity** (sentence-transformers): rejected on lite — adds 500 MB model, not needed for 81-node graph.
- **LLM-based re-ranking** (ask LLM which gap to prioritize): rejected — doubles inference cost per gap diagnosis.
- **Rule-based relevance scoring** (chosen) — look at node tags, misconception node links, difficulty delta to student mastery.

## R5: Resource Profile Awareness

**Decision**: Two prompt variants — `lite` uses ~100 input / 200 output tokens; `standard`/`max` uses ~400 input / 500 output tokens with multi-step CoT.

**Rationale**:
- On lite CPU the Qwen3.5-9B Q4_K_M model produces ~12 tok/s. 500 output tokens = 42 seconds — unacceptable.
- 200 output tokens on lite = 17 seconds worst case, still over the 1.5 s budget. **We must cap on lite at ≤100 output tokens** or use draft-only inference.
- Re-check latency after implementation; if the lite variant still exceeds budget, the feature flag allows disabling ToM entirely on lite.
- The `enable_tom_agent` flag already follows the existing `feature_enabled("enable_tom_agent")` pattern from `src/resource_profiles.py`.

**Alternatives considered**:
- **Always full prompt**: rejected — would violate FR-010 on lite.
- **Never run on lite**: rejected — partial benefit is valuable, and we can cap output.
- **Stream tokens and cut off**: rejected — belief state must be complete JSON.

## R6: Evaluation Methodology

**Decision**: Extend existing `evaluation/baseline_eval.py` infrastructure with a new `tom_ab_eval.py` script that runs the same scenarios twice (ToM off and ToM on) and produces a single Markdown comparison report.

**Rationale**:
- Reuses the exact infrastructure that produced baseline (same scenarios, same metrics), giving apples-to-apples comparison.
- Produces a single deliverable artifact for the diploma (the A/B report).
- 15 new ToM-specific scenarios with ground-truth belief states (active misconception labeled) provide the missing evaluation angle for FR-002 and SC-002.

**Alternatives considered**:
- **Use external benchmark** (HI-TOM, ToMBench): rejected — these measure general ToM, not tutoring-specific ToM.
- **Human evaluation**: rejected for MVP — costly and subjective; could add later as bonus.
- **LLM-as-judge**: kept as supplementary metric for Socratic quality scoring where ground truth is subjective.

## Summary of Decisions

| # | Decision Area | Choice |
|---|---------------|--------|
| R1 | ToM technique | Prompt-only with existing fine-tuned model |
| R2 | Output schema | 4-field structured JSON dataclass |
| R3 | Pipeline position | MENTAL_MODEL stage between Profiler and Planner |
| R4 | Navigator integration | Optional belief_state param in diagnose_gap, re-ranking only |
| R5 | Profile strategy | Two prompt variants with token budgets per profile |
| R6 | Evaluation | A/B on same scenarios + 15 new ToM-specific scenarios |

## Related Papers & References

| Work | Relevance |
|------|-----------|
| Kosinski (2023), [arXiv:2302.02083](https://arxiv.org/abs/2302.02083) | Empirical evidence of emergent ToM in LLMs — justifies R1 |
| Strachan et al. (2024), *Nature Human Behaviour* | State-of-the-art LLM ToM benchmarking |
| Gandhi et al. (2023), [arXiv:2306.15448](https://arxiv.org/abs/2306.15448) | Social reasoning in language models |
| Sclar et al. (2023), [arXiv:2310.16755](https://arxiv.org/abs/2310.16755) | HI-TOM higher-order ToM benchmark — for future comparison |
| Bayesian Knowledge Tracing (Corbett & Anderson 1995) | MITS already uses BKT for mastery — ToM complements, not replaces |
| VanLehn (2011) *The Relative Effectiveness of Human Tutoring…* | Establishes that adaptation to student mental state is a key driver of ITS effectiveness |
