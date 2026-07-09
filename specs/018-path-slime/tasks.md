# Задачи: PathSlime — Bio-inspired multi-path generation

**Вход**: документы дизайна из `/specs/018-path-slime/`
**Пререквизиты**: spec.md, plan.md, research.md, data-model.md, contracts/

**Тесты**: включены — критичны для алгоритма с вероятностным поведением.

**Организация**: задачи сгруппированы по User Stories. US1 (student path choice) — главная diploma value.

## Формат: `[ID] [P?] [Story] Описание`

---

## Фаза 1: Setup

- [x] T001 Проверить, что находимся на ветке `018-path-slime` и ветки 016+017 merged
- [x] T002 [P] Установить `scipy` в venv (требуется для `scipy.stats.levy_stable`); добавить в dev requirements
- [x] T003 [P] Создать пустой файл `tests/test_path_slime.py` с pytest заглушкой

---

## Фаза 2: Foundational (блокирующие пререквизиты)

- [x] T004 Добавить поля `enable_path_slime: bool` и `path_slime_k/iterations/timeout` в `ResourceProfile` (src/resource_profiles.py)
  - lite: enable=True, k=2, iter=20, timeout=1500
  - standard: enable=True, k=3, iter=35, timeout=500
  - max: enable=True, k=5, iter=50, timeout=300
- [x] T005 [P] Создать `src/knowledge/levy_sampler.py` — функция `levy_multiplier(alpha=1.5, n=1)` возвращает scaled Lévy-stable samples (clamped to [0.1, 10.0])
- [x] T006 [P] Создать файл `src/knowledge/path_slime.py` с dataclass skeletons (`Colony`, `AlternativePaths`, `StyleConfig`, `PathSlimeConfig`)
- [x] T007 Написать unit test `test_levy_sampler_statistics` в `tests/test_path_slime.py` — убедиться, что distribution имеет heavy tail (variance > Gaussian baseline на 2σ)

**Checkpoint**: все типы и случайный sampling готовы.

---

## Фаза 3: User Story 1 — Multi-path generation (Priority: P1) MVP

**Цель**: `find_alternative_paths()` возвращает k diverse valid paths на реальном forge.json графе.

### Тесты для US1

- [x] T008 [P] [US1] Тест `test_path_slime_basic` в `tests/test_path_slime.py` — k=3 diverse paths, diversity ≥ 0.3, все возвращаемые пути валидны
- [x] T009 [P] [US1] Тест `test_path_slime_validity` — каждое последовательное ребро — prerequisite relationship в графе
- [x] T010 [P] [US1] Тест `test_path_slime_already_mastered` — если target мастерован, возвращается 1 путь с этим target
- [x] T011 [P] [US1] Тест `test_path_slime_reproducibility` — одинаковый seed → одинаковый результат

### Реализация US1

- [x] T012 [US1] Реализовать `Colony.__init__()` в `src/knowledge/path_slime.py` — инициализация path от random start node (one of mastered concepts или graph entry points) до random prerequisite hop
- [x] T013 [US1] Реализовать `Colony._extend_path_to_target()` — BFS/DFS с randomness через Lévy multipliers для выбора рёбер. Guard против cycles через visited set
- [x] T014 [US1] Реализовать `Colony.fitness()` — multi-objective scoring по `StyleConfig`:
  - length component: 1 - (len(path) / max_reasonable_length)
  - mastery component: mean(mastery of intermediate nodes)
  - difficulty smoothness: 1 - max(|diff[i+1] - diff[i]|)
  - examples density: count(ILLUSTRATES links from path nodes) / len(path)
- [x] T015 [US1] Реализовать `Colony.lévy_perturb()` — заменяет длинный хвост пути на новый, используя `levy_multiplier` для выбора прыжка
- [x] T016 [US1] Реализовать `Colony.gaussian_refine()` — локальная мутация: заменить 1-2 соседних узла на альтернативные prerequisite path
- [x] T017 [US1] Реализовать diversity pressure в `PathSlime.step()` — штраф для overlap рёбер между colonies: для каждой colony fitness_adjusted = fitness - λ × edge_overlap_ratio
- [x] T018 [US1] Реализовать `PathSlime.run()` — main loop: init k colonies → for i in iterations: evolve each colony → apply diversity pressure → early stop если все converged → return top-k по fitness
- [x] T019 [US1] Реализовать timeout handling в `PathSlime.run()` — проверка `time.perf_counter()` vs timeout_ms, возврат best-so-far с `truncated=True`
- [x] T020 [US1] Реализовать `PersonalizedNavigator.find_alternative_paths()` — точка входа: создаёт `PathSlime`, запускает, возвращает `AlternativePaths` с computed diversity score
- [x] T021 [US1] Реализовать fallback к Dijkstra в `find_alternative_paths()` — если `PathSlime.run()` вернул меньше k путей или все failed validity, вернуть [dijkstra result] с diversity=1.0

**Checkpoint**: MVP работает — `find_alternative_paths(k=3)` возвращает 3 diverse valid paths на тестовом графе.

---

## Фаза 4: User Story 2 — Learning Styles (Priority: P2)

### Тесты

- [ ] T022 [P] [US2] Тест `test_path_slime_styles_differ` — style="quick" даёт путь короче style="gradual" (в 80%+ scenarios)
- [ ] T023 [P] [US2] Тест `test_path_slime_example_rich_higher_density` — плотность EXAMPLE nodes выше в "example_rich"

### Реализация

- [ ] T024 [US2] Добавить 4 fixed `StyleConfig` профилей в `path_slime.py`: quick, gradual, example_rich, mixed с весами из research.md R5
- [ ] T025 [US2] Реализовать lookup style → weights в `PathSlime.__init__()`, default = "mixed", invalid style → warning + fallback "mixed"

---

## Фаза 5: User Story 3 — LLM Tool Integration (Priority: P2)

### Тесты

- [ ] T026 [P] [US3] Тест `test_find_alternative_paths_tool_valid` в `tests/test_path_slime.py` — вызов через `navigator_tools.find_alternative_paths()` возвращает валидный JSON
- [ ] T027 [P] [US3] Тест `test_find_alternative_paths_tool_invalid_target` — invalid target возвращает `{"error": ...}` без исключения

### Реализация

- [ ] T028 [US3] Добавить tool definition в `NAVIGATOR_TOOL_DEFINITIONS` в `src/tools/navigator_tools.py` (per contracts/path-slime-tool.md)
- [ ] T029 [US3] Реализовать dispatch function `find_alternative_paths(target_concept_id, student_id, k=3, style="mixed")` в `src/tools/navigator_tools.py`:
  - Использует cached `get_navigator(_mastery_source)`
  - Вызывает `nav.find_alternative_paths(...)`
  - Форматирует response как JSON per contract
- [ ] T030 [US3] Добавить `find_alternative_paths` в `NAVIGATOR_FUNCTIONS` dispatch dict

---

## Фаза 6: User Story 4 — Resource Profile Awareness (Priority: P3)

### Тесты

- [ ] T031 [P] [US4] Тест `test_path_slime_lite_profile_k2` — при `MITS_PROFILE=lite` k=2, iterations=20
- [ ] T032 [P] [US4] Тест `test_path_slime_timeout_truncated` — с очень коротким timeout (50ms) возвращает `truncated=True` без исключения

### Реализация

- [ ] T033 [US4] Прочитать profile в `PathSlime.__init__()` через `get_active_profile()` и установить config.k/iterations/timeout если не override

---

## Фаза 7: Evaluation & Polish

- [ ] T034 [P] Создать `evaluation/scenarios/path_scenarios.json` — 20 сценариев с различными targets (basic/intermediate/advanced topics), mastery profiles
- [ ] T035 Создать `evaluation/path_slime_eval.py` — A/B сравнение PathSlime vs random-perturbed Dijkstra (k independent runs с Gaussian noise on weights):
  - Metrics: diversity_score, path validity %, latency p50/p95
  - Output: `evaluation/reports/path_slime_YYYY-MM-DD.md`
- [ ] T036 Запустить eval: `python -X utf8 evaluation/path_slime_eval.py`
- [ ] T037 [P] Создать `docs/architecture/PATH_SLIME.md` — описание алгоритма, references, example outputs, troubleshooting
- [ ] T038 [P] Обновить `docs/architecture/ARCHITECTURE.md` — пометить фичу 018 как DONE, добавить ссылки на eval
- [ ] T039 `ruff check src/knowledge/path_slime.py src/knowledge/levy_sampler.py src/tools/navigator_tools.py tests/test_path_slime.py` — lint clean
- [ ] T040 Полный прогон тестов: `pytest tests/test_path_slime.py tests/test_navigator.py tests/test_knowledge_forge.py -v`

---

## Зависимости и порядок

```text
Фаза 1 (Setup) 
    ↓
Фаза 2 (Foundational: types + sampler) ── БЛОКИРУЕТ US1-US4
    ↓
Фаза 3 (US1: MVP pathfinding) ── MVP!
    ↓
    ├→ Фаза 4 (US2: styles)
    ├→ Фаза 5 (US3: tool integration)
    └→ Фаза 6 (US4: profile awareness)
         ↓
    Фаза 7 (Evaluation + Polish)
```

## MVP scope

Фазы 1+2+3 = **20 задач** → `find_alternative_paths(k=3)` работает на реальном графе.

## Параллелизация

- Фаза 2: T005, T006 параллельны; T007 зависит от T005
- Фаза 3: все 4 теста (T008-T011) можно писать параллельно
- Реализация T012-T021 последовательна (один файл, один алгоритм)
- Фазы 4-6 параллельны после US1
- Фаза 7: T037, T038, T039 параллельны

## Расписание (3-4 дня)

| День | Задачи | Deliverable |
|------|--------|-------------|
| 1 | Фазы 1-2 + T012-T016 | Types, sampler, Colony init + extend + fitness |
| 2 | T017-T021 + тесты US1 | MVP алгоритм, diversity pressure, fallback |
| 3 | Фазы 4-5 | Styles + tool integration |
| 4 | Фазы 6-7 | Evaluation, docs, polish |

## Заметки

- Коммиты на английском (проектная конвенция)
- Docs/comments на русском (per запрос)
- Commit after каждая фаза complete
- Jaccard distance = `1 - |A ∩ B| / |A ∪ B|` на множествах рёбер (не узлов!)
- Early termination: если best fitness не улучшилось за 5 итераций → stop
