# Quickstart: PathSlime

## Prerequisites

- Knowledge Forge готов (016 выполнена, `data/knowledge/forge.json` существует)
- Python venv активирован, `numpy` + `scipy` установлены

## 1. Базовый вызов

```python
from pathlib import Path
from src.knowledge.knowledge_forge import KnowledgeGraph
from src.knowledge.navigator import PersonalizedNavigator

graph = KnowledgeGraph(Path("data/knowledge/forge.json"))

# Student с частичным mastery
mastery = {
    "math:arithmetic:definition": 0.9,
    "math:variables:definition": 0.85,
    "math:linear_equations:definition": 0.75,
    "math:functions_basics:definition": 0.7,
}
nav = PersonalizedNavigator(graph, mastery)

# Find 3 alternative paths к целевому концепту
result = nav.find_alternative_paths(
    student_id="demo",
    target_id="math:derivatives_basic:definition",
    k=3,
    style="mixed",
)

print(f"Found {len(result.paths)} paths, diversity: {result.diversity_score:.2f}")
for i, path in enumerate(result.paths):
    titles = [graph.get_node(nid).title for nid in path.path]
    print(f"  Path {i+1}: {' → '.join(titles)}")
```

Expected output:
```
Found 3 paths, diversity: 0.42
  Path 1: Переменные → Линейные → Квадратные → Функции → ... → Производные базовые
  Path 2: Переменные → ... (альтернативный маршрут)
  Path 3: ... (третий вариант с другим фокусом)
```

## 2. Стили обучения

```python
# "Quick" — минимум концептов
r_quick = nav.find_alternative_paths(student_id="demo", target_id="...", style="quick", k=1)

# "Example-rich" — максимум примеров по пути
r_examples = nav.find_alternative_paths(student_id="demo", target_id="...", style="example_rich", k=1)

# "Gradual" — плавное нарастание сложности
r_gradual = nav.find_alternative_paths(student_id="demo", target_id="...", style="gradual", k=1)

print(f"Quick length: {len(r_quick.paths[0].path)}")
print(f"Example-rich length: {len(r_examples.paths[0].path)}")
```

## 3. Через Ollama tool (для тьютора)

Когда MentalModelAgent / Navigator tools зарегистрированы, тьютор автоматически имеет доступ:

```python
from src.tools.navigator_tools import find_alternative_paths

result_json = find_alternative_paths(
    target_concept_id="math:derivatives_basic:definition",
    student_id="demo",
    k=3,
    style="mixed",
)
# result_json — JSON строка, готовая для LLM context
```

## 4. Evaluation

```bash
# Полный A/B: PathSlime vs Random-perturbed Dijkstra
python evaluation/path_slime_eval.py

# Output: evaluation/reports/path_slime_YYYY-MM-DD.md + .json
```

## 5. Resource Profile Awareness

| Профиль | k | Iterations | Timeout |
|---------|:-:|:----------:|:-------:|
| lite | 2 | 20 | 1500ms |
| standard | 3 | 35 | 500ms |
| max | 5 | 50 | 300ms |

```bash
# Forced lite mode:
export MITS_PROFILE=lite
python evaluation/path_slime_eval.py  # будет использовать k=2
```

## 6. Ключевые файлы

| Файл | Роль |
|------|------|
| `src/knowledge/path_slime.py` | Основной engine (Lévy-Gaussian SMA) |
| `src/knowledge/levy_sampler.py` | Discrete Lévy flight helper |
| `src/knowledge/navigator.py` | `find_alternative_paths()` точка входа |
| `src/tools/navigator_tools.py` | Ollama tool для тьютора |
| `src/resource_profiles.py` | `enable_path_slime` flag + k/iter per profile |
| `evaluation/path_slime_eval.py` | A/B comparison script |
| `evaluation/scenarios/path_scenarios.json` | 20 test scenarios |

## 7. Debugging

**diversity_score = 0** (все пути совпадают):
- Увеличьте `diversity_lambda` (default 0.3 → 0.5)
- Проверьте, что у target есть ≥ 2 distinct prerequisite chains (через `nav._graph.find_path`)

**truncated=True постоянно**:
- Уменьшите k или iterations
- Профайл неправильно определён: `python scripts/ollama/detect_resources.py`

**Пути невалидны** (fail prerequisite check):
- Check `test_path_slime.py::test_path_slime_validity` — скорее всего bug в repair step
