# Quickstart: ToM-Tutor

## Prerequisites

- Completed feature 016 (Knowledge Forge + Living KG + Resource Profiles) — this is on main now
- `data/knowledge/forge.json` generated (via `scripts/migrate_to_forge.py`)
- Ollama running with `mits-tutor-9b-kto` (or equivalent Qwen3.5-9B)
- Python venv activated

## 1. Verify Environment

```bash
# Check profile detection:
python scripts/detect_resources.py --list

# Check Ollama:
curl -s http://localhost:11434/api/tags | python -m json.tool
```

## 2. Try ToM on a Mock Student

Once `MentalModelAgent` is implemented, this will work end-to-end:

```python
from src.agents.mental_model_agent import MentalModelAgent
from src.models.llm_client import LLMClient
from src.knowledge.knowledge_forge import KnowledgeGraph
from pathlib import Path

llm = LLMClient()
graph = KnowledgeGraph(Path("data/knowledge/forge.json"))

agent = MentalModelAgent(llm_client=llm, knowledge_graph=graph)

belief = agent.infer(
    student_message="производная от суммы = сумме производных, значит (fg)' = f'g'",
    student_profile=mock_profile,
    history=[],
)

print(f"Active misconception: {belief.active_misconception}")
print(f"Belief about topic: {belief.belief_about_topic}")
print(f"Confidence: {belief.confidence:.2f}")
```

Expected (ground truth for this example):
- `active_misconception`: "Неверное обобщение правила суммы на правило произведения"
- `confidence ≥ 0.7`

## 3. Run A/B Evaluation

```bash
# Once tom_ab_eval.py is implemented:
python evaluation/tom_ab_eval.py

# Outputs:
# - evaluation/reports/tom_ab_YYYY-MM-DD.md (comparison table)
# - evaluation/reports/tom_ab_YYYY-MM-DD.json (raw numbers)
```

Target results (from success criteria):
- Root-hit rate: 60% → ≥80%
- Misconception accuracy: ≥75% on 15 new scenarios
- Socratic quality delta: ≥+10% without telling-rate regression

## 4. Disable ToM for Comparison

```bash
# Environment flag:
export MITS_DISABLE_TOM=1

# Or via profile config:
export MITS_PROFILE=lite  # and set enable_tom_agent=False in profile
```

## 5. Run Tests

```bash
pytest tests/test_mental_model_agent.py tests/test_tom_integration.py -v
```

## Key Files (to be created during implementation)

| File | Purpose |
|------|---------|
| `src/agents/mental_model_agent.py` | The ToM agent |
| `src/data/schemas.py` (modified) | BeliefState dataclass |
| `src/agents/orchestrator.py` (modified) | MENTAL_MODEL pipeline stage |
| `src/agents/planner.py` (modified) | belief_state parameter |
| `src/knowledge/navigator.py` (modified) | diagnose_gap belief_state re-ranking |
| `src/resource_profiles.py` (modified) | enable_tom_agent flag |
| `evaluation/tom_ab_eval.py` | A/B evaluation script |
| `evaluation/scenarios/tom_scenarios.json` | 15+ ground-truth ToM scenarios |
| `tests/test_mental_model_agent.py` | Unit tests |
| `tests/test_tom_integration.py` | Integration tests |

## Debugging

**If `confidence` is always 0:**
- Check Ollama is running: `curl localhost:11434`
- Check LLM returns valid JSON: `python -c "from src.models.llm_client import LLMClient; c = LLMClient(); print(c.generate('Hi', format='json'))"`
- Check logs in `data/logs/` for `tom.fallback` entries

**If latency is too high:**
- Verify current profile: `python scripts/detect_resources.py`
- On lite, the `num_predict` cap should be ≤150
- Check Ollama model: `ollama list` — should show Q4_K_M for lite

**If Navigator re-ranking doesn't change root_gap:**
- Check belief_state.active_misconception is not None
- Check misconception content has words overlapping with prereq tags
- Set logging to DEBUG to see relevance scores
