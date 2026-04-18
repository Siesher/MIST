# Feature Specification: ToM-Tutor — Theory-of-Mind Student Mental State Agent

**Feature Branch**: `017-tom-tutor`  
**Created**: 2026-04-18  
**Status**: Draft  
**Input**: Add a Theory-of-Mind (ToM) reasoning stage to the multi-agent tutoring pipeline that models the student's mental state before teaching decisions are made, to improve pedagogical gap selection and response quality.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Tutor Selects Pedagogically Relevant Gap (Priority: P1)

When a student fails at a concept, the tutor diagnoses why. Current behavior: picks the deepest unmastered prerequisite via graph traversal. New behavior: the ToM agent first infers what the student actually believes and what misconception is active, then re-ranks missing prerequisites by pedagogical relevance to that belief state.

**Why this priority**: This is the measurable diploma contribution. Baseline showed 100% recall but 60% precision on root gap selection — ToM gives the system a way to pick the *right* gap, not just *a* gap.

**Independent Test**: Re-run the 5 scenarios from `evaluation/baseline_eval.py` with ToM enabled. Measure root-hit rate improvement. Target: ≥80% (from 60% baseline).

**Acceptance Scenarios**:

1. **Given** a student with mastery gaps in both algebra and functions who just failed at derivatives, **When** the tutor diagnoses the root cause with ToM, **Then** the selected gap matches the one most aligned with the student's specific error pattern (not just DFS-deepest).
2. **Given** a student who wrote "производная от суммы = сумме производных только для линейных функций", **When** ToM analyzes the message, **Then** the detected active misconception matches a known misconception pattern in the graph.
3. **Given** the ToM agent returns low confidence (< 0.3), **When** the Planner uses the output, **Then** it falls back to the baseline diagnose_gap behavior without failing.

---

### User Story 2 — Tutor Adapts Strategy to Predicted Student Reaction (Priority: P2)

Before committing to a teaching strategy, the ToM agent predicts how the student would interpret each candidate strategy's output. The Planner uses these predictions to choose the strategy most likely to actually help this specific student at this moment.

**Why this priority**: Extends ToM impact beyond gap selection into full teaching-move decisions. Provides a second measurable metric (strategy quality) beyond just gap accuracy.

**Independent Test**: Run 20 A/B tutoring dialogs (same prompts) with and without ToM. Score each response for Socratic quality (question count, telling rate, scaffolding appropriateness). Target: ToM version shows ≥10% improvement on composite Socratic score without regressing telling rate.

**Acceptance Scenarios**:

1. **Given** a frustrated student who has tried twice, **When** ToM predicts that "HINT" strategy would discourage and "ENCOURAGE" would rebuild confidence, **Then** the Planner selects ENCOURAGE.
2. **Given** a confident student exploring new material, **When** ToM predicts that "DIRECT_INSTRUCTION" would skip necessary struggle and "SCAFFOLDED" would engage reasoning, **Then** the Planner selects SCAFFOLDED.

---

### User Story 3 — Graceful Degradation on Limited Hardware (Priority: P2)

The system works on Lite-profile hardware (16 GB RAM, no GPU) with a simplified ToM prompt and on Standard/Max profiles with full multi-step ToM reasoning. When the LLM is unavailable or returns invalid output, the system falls back to baseline behavior without crashing.

**Why this priority**: Critical for deployment — the system must not become brittle. Lite profile users get partial ToM benefits; all users get guaranteed uptime.

**Independent Test**: Run the full tutoring pipeline with (a) LLM responding correctly, (b) LLM timing out, (c) LLM returning invalid JSON, (d) LLM unavailable entirely. All four paths produce a valid response; paths b/c/d fall back to baseline.

**Acceptance Scenarios**:

1. **Given** `MITS_PROFILE=lite` environment, **When** the ToM agent runs, **Then** it uses the simplified prompt and completes within acceptable latency (≤1.5 s on CPU).
2. **Given** the LLM returns malformed JSON, **When** ToM agent parses the response, **Then** it returns an empty BeliefState with confidence=0 and the pipeline continues normally.
3. **Given** Ollama is not running at all, **When** the orchestrator reaches the MENTAL_MODEL stage, **Then** it logs the outage, skips ToM, and proceeds to Planner with no belief state.

---

### User Story 4 — Evaluation Suite Produces A/B Comparison (Priority: P3)

A dedicated evaluation script runs the same scenarios with ToM on/off and produces a Markdown report comparing gap root-hit rate, Socratic quality, and telling rate. This becomes a core artifact for the diploma.

**Why this priority**: Essential for proving the research claim but not blocking implementation. Can be built after core ToM agent works.

**Independent Test**: Running `python evaluation/tom_ab_eval.py` produces a report with side-by-side numbers for both conditions on 5+15=20 scenarios plus 20 dialogs.

**Acceptance Scenarios**:

1. **Given** baseline and ToM runs complete, **When** the eval script generates the report, **Then** it shows both numbers with delta (e.g. "60% → 82% (+22%)").
2. **Given** some scenarios fail in both conditions, **When** the report is generated, **Then** failures are listed separately so the root cause can be investigated.

---

### Edge Cases

- **Student message is empty or whitespace-only** — ToM agent skips (no mental state to infer), pipeline proceeds with no belief state.
- **Graph has no misconceptions linked to the topic** — ToM returns a belief state but `active_misconception` field is None; Planner still benefits from belief_about_topic.
- **Student message contradicts itself** ("I understand completely… I'm so confused") — ToM should flag with low confidence; downstream consumers respect the confidence flag.
- **Multiple misconceptions plausible** — ToM returns the most probable one with a secondary candidates list.
- **LLM returns a misconception not in the graph** — stored as free-text in belief state; Planner can still use it for strategy selection even if Navigator can't match to a graph node.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST infer a student belief state from the student's latest message, session history, and current profile before each teaching decision.
- **FR-002**: System MUST produce a structured belief state containing: the active misconception (if any), the student's current understanding of the topic, predicted reactions to candidate teaching strategies, and a self-reported confidence score.
- **FR-003**: System MUST integrate the belief state into the planning stage so that strategy selection and prerequisite-to-review choice both benefit from the inferred mental state.
- **FR-004**: System MUST re-rank missing prerequisites by pedagogical relevance to the belief state when diagnosing gaps, not only by structural depth.
- **FR-005**: System MUST fall back to baseline (non-ToM) behavior without errors when the belief-state inference fails, times out, or returns invalid output.
- **FR-006**: System MUST respect the active resource profile — simpler inference on lite-profile hardware, fuller inference on standard/max.
- **FR-007**: System MUST allow the ToM stage to be disabled by configuration so baseline behavior is always reachable for comparison.
- **FR-008**: System MUST log the belief state and the decision it informed, so behavior is auditable for debugging and diploma analysis.
- **FR-009**: System MUST provide an evaluation workflow that runs identical scenarios with and without the ToM stage and produces a comparison artifact.
- **FR-010**: System MUST complete the ToM inference within a latency budget appropriate to the active profile (≤1.5 s lite, ≤0.7 s standard) so it does not disrupt the conversational feel.

### Key Entities

- **BeliefState**: A structured representation of what the student is believed to think right now — which misconception is active, how they model the current topic, predicted reactions to different teaching strategies, and a confidence score for the whole inference.
- **MentalModelAgent**: The pipeline component that produces a BeliefState from student input, profile, history, and graph context.
- **Pipeline Stage (Mental Model)**: A new stage inserted between Profiler and Planner in the tutoring orchestration, so that every teaching decision sees the belief state.
- **Evaluation Scenario**: A student profile + message + expected ground truth (expected active misconception or expected pedagogically correct gap) used to measure ToM accuracy.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Gap root-hit rate on the 5 baseline scenarios improves from 60% to at least 80% when ToM is enabled.
- **SC-002**: On 15+ new ToM-specific scenarios with ground-truth belief states, the inferred active misconception matches the expected one in at least 75% of cases.
- **SC-003**: In an A/B comparison of 20 tutoring dialogs, the ToM-enabled condition shows at least 10% improvement on a composite Socratic quality score (higher question count, lower telling rate, better scaffolding appropriateness) without regressing the telling rate below the baseline floor.
- **SC-004**: ToM inference completes within 1.5 seconds on lite-profile hardware and 0.7 seconds on standard-profile hardware for 95% of requests.
- **SC-005**: The tutoring pipeline produces a valid response in 100% of runs even when the ToM stage fails (timeout, invalid output, unavailable LLM).
- **SC-006**: The evaluation artifact is reproducible — running the suite twice on the same inputs produces numerically identical results modulo documented LLM nondeterminism.
- **SC-007**: Average latency overhead from adding ToM to the pipeline is at most 1 additional LLM call per turn, measurable in session traces.
