# Contract: `find_alternative_paths` Ollama Tool

**Feature**: 018-path-slime

## Public API

```python
class PersonalizedNavigator:
    def find_alternative_paths(
        self,
        student_id: str,
        target_id: str,
        k: int = 3,
        style: str = "mixed",
        timeout_ms: Optional[int] = None,
        seed: Optional[int] = None,
    ) -> AlternativePaths: ...
```

## Input Specification

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| student_id | str | required | Student identifier (for mastery lookup) |
| target_id | str | required | Target concept graph node id |
| k | int | 3 | Number of diverse paths to return |
| style | str | "mixed" | One of: "quick", "gradual", "example_rich", "mixed" |
| timeout_ms | int | from profile | Max computation time before returning best-so-far |
| seed | int | None | RNG seed for reproducibility |

## Output Specification

Returns `AlternativePaths` object (see [data-model.md](../data-model.md)).

Never raises exceptions to callers. On any failure:
- Returns AlternativePaths with empty `paths=[]` and descriptive error in metadata
- Logs WARNING/ERROR with context

## Ollama Tool Definition

```json
{
  "type": "function",
  "function": {
    "name": "find_alternative_paths",
    "description": "Generate k diverse learning paths from student's current knowledge to a target concept. Unlike find_learning_path (single optimum), returns multiple qualitatively different routes, enabling student choice. Useful when student asks for options or tutor wants to offer variety.",
    "parameters": {
      "type": "object",
      "properties": {
        "target_concept_id": {
          "type": "string",
          "description": "Knowledge graph node id for target concept"
        },
        "student_id": {
          "type": "string",
          "description": "Student identifier for personalized mastery"
        },
        "k": {
          "type": "integer",
          "description": "Number of alternative paths (default 3, max 5)",
          "default": 3
        },
        "style": {
          "type": "string",
          "description": "Path style preference",
          "enum": ["quick", "gradual", "example_rich", "mixed"],
          "default": "mixed"
        }
      },
      "required": ["target_concept_id", "student_id"]
    }
  }
}
```

## Dispatch Function Behavior

```python
def find_alternative_paths(
    target_concept_id: str,
    student_id: str,
    k: int = 3,
    style: str = "mixed",
) -> str:
    """Возвращает JSON строку с k путями + diversity + latency."""
```

## Return JSON Schema

```json
{
  "target": "math:derivatives_basic:definition",
  "style": "mixed",
  "paths": [
    {
      "id": "path_1",
      "nodes": [
        {"id": "math:arithmetic:definition", "title": "Арифметика", "status": "mastered"},
        {"id": "math:limits_intuition:definition", "title": "Пределы", "status": "to_learn"}
      ],
      "length": 5,
      "new_concepts": 3,
      "fitness": 0.72,
      "description_hint": "короткий путь через основы"
    }
  ],
  "diversity_score": 0.45,
  "iterations_run": 32,
  "elapsed_ms": 412,
  "truncated": false
}
```

## Error Cases

| Condition | Response | Side effect |
|-----------|----------|-------------|
| Invalid target_id | `{"error": "target not found"}` | Log WARNING |
| Empty graph | `{"error": "knowledge graph not available"}` | Log ERROR once |
| Timeout | Valid response, `"truncated": true` | Log INFO с elapsed |
| Algorithm failure | Fall back to Dijkstra: return 1 path, diversity=1.0 | Log WARNING |
| Invalid style | Use "mixed" as default, continue | Log WARNING |
| k < 1 or k > 5 | Clamp to [1, 5] | Log DEBUG |

## Latency SLA (from SC-004)

| Profile | p50 target | p95 target | Hard cap (timeout_ms) |
|---------|:----------:|:----------:|:---------------------:|
| lite | 1000 ms | 1500 ms | 2000 ms |
| standard | 300 ms | 500 ms | 800 ms |
| max | 150 ms | 300 ms | 500 ms |

At hard cap, returns best-so-far с `truncated=True`. Never blocks indefinitely.

## Integration Points

```python
# В src/tools/navigator_tools.py:
NAVIGATOR_TOOL_DEFINITIONS.append({...})  # per schema above
NAVIGATOR_FUNCTIONS["find_alternative_paths"] = find_alternative_paths

# В tutor_agent.py — automatic (уже merged via existing pattern)
```

## Testing Contract

### Unit tests (`tests/test_path_slime.py`)

1. `test_path_slime_basic` — 3 path + diversity ≥ 0.3 на простом графе
2. `test_path_slime_styles_differ` — "quick" даёт короче чем "gradual"
3. `test_path_slime_validity` — все пути respect prerequisites
4. `test_path_slime_timeout_truncated` — с tight timeout возвращает truncated=True без исключения
5. `test_path_slime_fallback_to_dijkstra` — на degenerate graph возвращает single path
6. `test_path_slime_reproducibility` — seed=42 даёт одинаковый результат
7. `test_levy_sampler_statistics` — sampled distribution имеет heavy tail (скaling verified)

### Integration test

1. `test_find_alternative_paths_tool` — через Ollama tool calling pattern
2. `test_backward_compat` — `find_optimal_path()` (Dijkstra) не изменился
