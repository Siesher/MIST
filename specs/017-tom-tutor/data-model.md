# Data Model: ToM-Tutor

**Feature**: 017-tom-tutor | **Date**: 2026-04-18

## Entities

### BeliefState

A structured snapshot of what the student is believed to think right now,
produced by the `MentalModelAgent` and consumed by Planner and Navigator.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| active_misconception | string or null | no | Short description (Russian) of the misconception most likely active right now. Null if no misconception detected. |
| active_misconception_node_id | string or null | no | Knowledge Forge node ID if the misconception matches an existing graph node. |
| belief_about_topic | string | yes | One-sentence summary (Russian) of how the student seems to model the current topic. |
| predicted_reactions | dict[str, str] | yes | Map of teaching strategy name → predicted student reaction (free text, one sentence). |
| candidate_misconceptions | list[string] | no | Up to 3 other plausible misconceptions ranked by likelihood. |
| confidence | float | yes | 0.0–1.0. ToM inference reliability self-assessed by the model. |
| reasoning | string | no | Brief explanation of the inference (one paragraph). Used for audit logging. |
| generated_at | string | yes | ISO 8601 timestamp of inference. |
| profile_used | string | yes | Profile name ("lite"/"standard"/"max") under which this inference ran. |

**Validation rules**:
- `confidence` must be in [0.0, 1.0].
- `predicted_reactions` must include at least one entry when `confidence ≥ 0.3`.
- `active_misconception` and `candidate_misconceptions` should not overlap.
- `belief_about_topic` must be a complete sentence, not a phrase.

**Empty BeliefState** (fallback when LLM unavailable):
```python
BeliefState(
    active_misconception=None,
    belief_about_topic="",
    predicted_reactions={},
    confidence=0.0,
    generated_at=now(),
    profile_used=active_profile.name,
)
```

When `confidence == 0.0`, all downstream consumers MUST fall back to non-ToM behavior.

## Downstream Consumers

### Planner.create_plan(belief_state=...)

Planner enriches strategy selection:
- If `belief_state.confidence ≥ 0.5` and `predicted_reactions` non-empty:
  pick the strategy whose predicted reaction is most pedagogically favorable.
- If `belief_state.active_misconception` matches a known MISCONCEPTION node:
  bias toward CONCEPTUAL_REPAIR strategy.
- Otherwise: existing rule-based logic.

### Navigator.diagnose_gap(belief_state=...)

Navigator re-ranks `missing_prerequisites`:
1. Compute relevance score for each prereq against belief state:
   - +2.0 if prereq's tags overlap with `active_misconception` tokens
   - +1.0 if prereq has a COMMON_ERROR_FOR edge from the active misconception
   - +0.5 if prereq difficulty is close to student's current mastery
2. Sort by (relevance_score desc, original_depth desc).
3. Set `root_gap` to top-ranked prerequisite.

## State Transitions

BeliefState is **ephemeral** — one instance per tutoring turn, discarded
after use. No persistence. This simplifies implementation (no DB migration)
and matches the fact that mental states change rapidly within sessions.

```text
Session turn begins
  → StudentProfile produced by Profiler
  → BeliefState produced by MentalModelAgent
  → TeachingPlan produced by Planner (using BeliefState)
  → TutorResponse produced by Tutor
  → BeliefState discarded at end of turn
Session turn ends
```

**Audit trail**: BeliefState is logged to `data/logs/session_{id}.jsonl`
under the `mental_model` key for offline inspection.

## Relationships

```text
StudentProfile (Profiler output)
    ↓
MentalModelAgent ──reads──> ResourceProfile (for prompt selection)
    ↓                ──reads──> KnowledgeGraph (for misconception nodes)
    ↓                ──reads──> session history (last 3 turns)
    ↓
BeliefState
    ↓
    ├──→ Planner.create_plan(belief_state=...)
    └──→ Navigator.diagnose_gap(belief_state=...)
```

## Persistence Format (Audit Log)

```json
{
  "session_id": "abc123",
  "turn": 3,
  "timestamp": "2026-04-18T14:32:10",
  "mental_model": {
    "active_misconception": "Ученик применяет правило суммы к произведению производных",
    "active_misconception_node_id": "math:derivatives:misconception:3",
    "belief_about_topic": "Студент считает производную линейным оператором для всех операций",
    "predicted_reactions": {
      "scaffolded": "Продолжит задавать уточняющие вопросы",
      "direct_instruction": "Примет формулу без понимания",
      "conceptual_repair": "Столкнётся с противоречием и пересмотрит правило"
    },
    "confidence": 0.82,
    "reasoning": "Студент использовал формулу (fg)' = f' g' — это классическая ошибка переноса правила суммы...",
    "profile_used": "standard",
    "generated_at": "2026-04-18T14:32:10"
  }
}
```
