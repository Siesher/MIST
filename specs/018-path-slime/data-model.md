# Data Model: PathSlime

**Feature**: 018-path-slime | **Date**: 2026-04-18

## Entities

### Colony

Один "слизевик" — candidate path evolving на графе.

| Field | Type | Description |
|-------|------|-------------|
| id | int | Unique id (0..k-1) |
| path | list[str] | Current path (ordered list of node ids) |
| fitness | float | Current fitness score (higher is better) |
| conductivity | dict[tuple[str,str], float] | Edge conductivity weights (Physarum D(t)) |
| style | str | Fitness style ('quick' / 'gradual' / 'example_rich' / 'mixed') |
| stagnation_counter | int | Iterations without improvement |

**Validation**:
- path[0] — one of mastered start nodes
- path[-1] == target_concept
- path valid = все пары (path[i], path[i+1]) — существующие рёбра с PREREQUISITE или BEST_TAUGHT_AFTER edge_type
- conductivity value ∈ [0.01, 1.0]

**State transitions**:
- `explore()` — Lévy flight jump, обычно меняет большой кусок пути
- `refine()` — Gaussian mutation, локальное изменение (1-2 ребра)
- `decay()` — evaporation conductivity без flow

### AlternativePaths

Result объект, возвращаемый `find_alternative_paths()`.

| Field | Type | Description |
|-------|------|-------------|
| target | str | Target concept id |
| paths | list[LearningPath] | k diverse paths |
| diversity_score | float | Mean pairwise Jaccard distance (0..1) |
| style | str | Style used |
| truncated | bool | True если timeout — returned best-so-far |
| iterations_run | int | Actual iterations (может быть < max) |
| elapsed_ms | float | Total computation time |

**Validation**:
- `len(paths)` ≤ k (может быть меньше если < k unique)
- `diversity_score` ∈ [0, 1]
- Каждый `LearningPath` — reuse existing type из `navigator.py`

### StyleConfig

Named configuration fitness весов.

| Field | Type | Description |
|-------|------|-------------|
| name | str | Style identifier |
| w_length | float | Weight for path length component |
| w_mastery | float | Weight for student mastery coverage |
| w_difficulty | float | Weight for smooth difficulty progression |
| w_examples | float | Weight for EXAMPLE node density |

**Constraint**: `w_length + w_mastery + w_difficulty + w_examples == 1.0`

**Fixed profiles**:
- `quick`: (0.6, 0.2, 0.15, 0.05)
- `gradual`: (0.25, 0.3, 0.35, 0.10)
- `example_rich`: (0.25, 0.25, 0.15, 0.35)
- `mixed`: (0.40, 0.30, 0.20, 0.10)

### PathSlimeConfig

Тюнируемые параметры алгоритма, derived from active profile.

| Field | Type | Description |
|-------|------|-------------|
| k | int | Number of paths to return (colonies) |
| colony_size | int | Number of slime agents per colony |
| max_iterations | int | Maximum optimization iterations |
| levy_alpha | float | Lévy stability parameter (1.0-2.0, typically 1.5) |
| gaussian_sigma | float | Gaussian mutation std |
| diversity_lambda | float | Penalty weight for edge overlap |
| timeout_ms | int | Hard cap — return best-so-far past this |
| conductivity_decay | float | r in dD/dt = f(Q) - r·D |

**Profile-derived defaults**:
| Profile | k | colony_size | max_iter | timeout_ms |
|---------|:-:|:-----------:|:--------:|:----------:|
| lite | 2 | 6 | 20 | 1500 |
| standard | 3 | 10 | 35 | 500 |
| max | 5 | 15 | 50 | 300 |

## Relationships

```text
PersonalizedNavigator
    │
    ├── find_optimal_path() → LearningPath  [existing Dijkstra]
    └── find_alternative_paths() → AlternativePaths  [NEW PathSlime]
                                        │
                                        └── paths: list[LearningPath]

PathSlime (engine)
    │
    ├── uses: KnowledgeGraph (read-only)
    ├── uses: MasteryProvider (via navigator)
    ├── holds: list[Colony]  (size k)
    ├── reads: StyleConfig
    └── reads: PathSlimeConfig (from profile)
```

## Diversity Metric

**Pairwise Jaccard distance** на множествах рёбер:

```
jaccard(path_a, path_b) = 1 - |edges(a) ∩ edges(b)| / |edges(a) ∪ edges(b)|
diversity_score = mean(jaccard(a, b) for a != b in paths)
```

- 0.0 = все пути идентичны
- 1.0 = пути не имеют общих рёбер
- Target: ≥ 0.3 в 90% сценариев

## Persistence

**None.** Все структуры — in-memory, stateless. Алгоритм запускается на каждый вызов `find_alternative_paths()`, результат возвращается napromimodiously, не кэшируется между вызовами.

Для reproducibility — optional seed parameter в config (default None = non-deterministic).
