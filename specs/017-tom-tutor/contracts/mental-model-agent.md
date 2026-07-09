# Contract: MentalModelAgent

**Feature**: 017-tom-tutor

## Public API

```python
class MentalModelAgent(BaseAgent):
    def __init__(
        self,
        llm_client: LLMClient,
        knowledge_graph: Optional[KnowledgeGraph] = None,
    ) -> None: ...

    def infer(
        self,
        student_message: str,
        student_profile: StudentProfile,
        history: list[ConversationTurn],
        graph_context: Optional[dict] = None,
    ) -> BeliefState: ...
```

## Input Specification

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| student_message | str | yes | Latest message from the student (Russian). |
| student_profile | StudentProfile | yes | Profile from Profiler (errors, confidence, cognitive load). |
| history | list[ConversationTurn] | yes | Last 3 conversation turns (can be empty). |
| graph_context | dict or None | no | Output of Navigator.get_concept_context for the current topic, when available. |

## Output Specification

Returns a `BeliefState` (see [data-model.md](../data-model.md)).

Must **never** raise an exception to callers. On any failure (timeout,
LLM error, invalid JSON), returns an empty BeliefState with `confidence=0.0`
and logs the failure internally.

## Prompt Strategy per Profile

### Lite Profile

- Input tokens: ~100 (short system prompt + minimal context)
- Output tokens: cap at 150 via `num_predict=150`
- No few-shot examples
- Single JSON object output
- Target latency: ≤1.5 s on CPU

```
Role: Analyze student's mental state in 1 step.
Student said: {msg}
Known errors: {errors}
Output JSON only: {active_misconception, belief_about_topic,
                  predicted_reactions, confidence}
```

### Standard / Max Profile

- Input tokens: ~400 (includes graph context + 2 few-shot examples)
- Output tokens: cap at 500
- Multi-step reasoning: first identify misconception, then predict reactions
- Target latency: ≤0.7 s on GPU

```
Role: Reason about student's mental state in 3 steps.
[few-shot example 1]
[few-shot example 2]
Now analyze:
  Student said: {msg}
  Known errors: {errors}
  Graph context: {misconception nodes, related concepts}
  Session history: {last 3 turns}
Step 1: What misconception might be active?
Step 2: How does the student model this topic?
Step 3: Predict reactions to strategies: [scaffolded, conceptual_repair, encourage]
Output JSON with reasoning trace.
```

## Graceful Degradation Contract

The agent MUST handle these failure modes without raising:

| Failure | Behavior |
|---------|----------|
| LLM timeout (>budget) | Return empty BeliefState, log WARNING with latency |
| LLM returns invalid JSON | Attempt 1 repair pass; if still invalid, return empty BeliefState |
| LLM returns partial JSON (missing fields) | Fill missing fields with defaults (None / empty dict / 0.0) |
| Ollama unreachable | Return empty BeliefState, log ERROR once per session |
| `enable_tom_agent` profile flag is False | Agent should not be instantiated in orchestrator; orchestrator checks flag before calling |

## Latency SLA

| Profile | p50 target | p95 target | Hard cap |
|---------|:----------:|:----------:|:--------:|
| lite | 800 ms | 1500 ms | 2000 ms (then return empty) |
| standard | 350 ms | 700 ms | 1000 ms |
| max | 300 ms | 600 ms | 800 ms |

On timeout, the agent returns empty BeliefState — the pipeline does not block.

## Logging Contract

Every invocation logs at INFO level:
- `tom.invoked` — with profile_used, student_id
- `tom.completed` — with confidence, latency_ms, misconception_detected (bool)
- `tom.fallback` — when falling back to empty BeliefState, with reason

Belief state content is logged at DEBUG level (includes student_message,
so privacy-sensitive — gated by DEBUG level only).

## Integration Points

```python
# In Orchestrator.process()
if feature_enabled("enable_tom_agent") and self.mental_model_agent is not None:
    belief_state = self.mental_model_agent.infer(
        student_message=context.student_input,
        student_profile=profile,
        history=session.recent_turns(3),
        graph_context=graph_context,  # from GRAPH_NAV stage
    )
else:
    belief_state = BeliefState.empty()

# Pass to Planner
plan = self.planner.create_plan(
    profile=profile,
    context=planner_context,
    graph_context=graph_context,
    belief_state=belief_state,  # NEW parameter
)
```

## Testing Contract

### Unit tests (`tests/test_mental_model_agent.py`)

1. Valid LLM response → parsed into BeliefState correctly
2. Invalid JSON → returns empty BeliefState, no exception raised
3. Timeout → returns empty BeliefState within hard cap + small epsilon
4. Lite profile → uses short prompt (assert prompt length)
5. Standard profile → uses full prompt with few-shot examples

### Integration tests (`tests/test_tom_integration.py`)

1. Full orchestrator run with ToM enabled produces valid response
2. Orchestrator with ToM disabled works identically to before
3. LLM outage mid-session triggers exactly one ERROR log, session continues
4. Navigator.diagnose_gap with belief_state re-orders correctly
5. Planner.create_plan with belief_state picks different strategy than without (on designed scenario)
