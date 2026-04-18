# Задачи: ToM-Tutor — Агент Theory-of-Mind для персонализации тьюторинга

**Вход**: документы дизайна из `/specs/017-tom-tutor/`
**Пререквизиты**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Тесты**: включены — критично для проверки graceful degradation и A/B сравнения.

**Организация**: задачи сгруппированы по User Stories. US1 (gap re-ranking) — главный diploma target.

## Формат: `[ID] [P?] [Story] Описание`

- **[P]** — можно выполнять параллельно (разные файлы, нет зависимостей)
- **[Story]** — к какой user story относится задача
- Каждая задача содержит точный путь к файлу

---

## Фаза 1: Setup

**Цель**: убедиться, что ветка готова, существующие фичи 016 работают, тестовая инфраструктура в порядке.

- [ ] T001 Проверить, что находимся на ветке `017-tom-tutor` и все тесты 016 проходят — запустить `python -m pytest tests/test_knowledge_forge.py tests/test_navigator.py tests/test_navigator_tools.py tests/test_graph_evolution.py tests/test_resource_profiles.py tests/test_source_extractor.py -q`
- [ ] T002 [P] Создать пустые файлы тестов: `tests/test_mental_model_agent.py` и `tests/test_tom_integration.py` с базовыми pytest-заглушками
- [ ] T003 [P] Проверить, что Ollama запущена и отвечает — `curl -s http://localhost:11434/api/tags` (если не запущена, задокументировать как known issue для моков в тестах)

---

## Фаза 2: Foundational (блокирующие пререквизиты)

**Цель**: реализовать core-типы данных и feature flag, от которых зависят все user stories.

**КРИТИЧНО**: ни одна user story не может начинаться до завершения этой фазы.

- [ ] T004 Добавить dataclass `BeliefState` в `src/data/schemas.py` согласно data-model.md — 9 полей (active_misconception, active_misconception_node_id, belief_about_topic, predicted_reactions, candidate_misconceptions, confidence, reasoning, generated_at, profile_used) + classmethod `BeliefState.empty()` для fallback
- [ ] T005 [P] Добавить поле `enable_tom_agent: bool` в `ResourceProfile` dataclass в `src/resource_profiles.py` — значения по профилям: lite=False (по умолчанию, включается вручную после проверки латентности), standard=True, max=True
- [ ] T006 [P] Добавить поле `tom_prompt_style: str` в `ResourceProfile` — значения: "short" для lite, "full" для standard/max
- [ ] T007 Написать unit-тесты для `BeliefState` в `tests/test_mental_model_agent.py` — валидация границ confidence, корректность `empty()`, сериализация в dict/JSON
- [ ] T008 [P] Написать unit-тесты для новых полей профиля в `tests/test_resource_profiles.py` — проверить, что `feature_enabled("enable_tom_agent")` возвращает False на lite и True на standard/max

**Чекпоинт**: BeliefState и флаг профиля готовы. User Stories могут начинаться.

---

## Фаза 3: User Story 1 — Tutor выбирает педагогически релевантный gap (Priority: P1) MVP

**Цель**: ToM-агент выдаёт BeliefState → Navigator использует её для переранжирования prereq в `diagnose_gap()` → root-hit rate растёт с 60% до ≥80%.

**Независимый тест**: прогнать 5 сценариев из `evaluation/baseline_eval.py` с включённой ToM и измерить root-hit rate.

### Тесты для US1

- [ ] T009 [P] [US1] Написать integration-тест `test_mental_model_agent_returns_valid_belief` в `tests/test_mental_model_agent.py` — при валидном LLM-ответе агент возвращает BeliefState с confidence > 0 и заполненным belief_about_topic
- [ ] T010 [P] [US1] Написать тест `test_mental_model_agent_invalid_json` в `tests/test_mental_model_agent.py` — при невалидном JSON возвращает empty BeliefState без исключений, логирует fallback
- [ ] T011 [P] [US1] Написать тест `test_mental_model_agent_timeout` в `tests/test_mental_model_agent.py` — при таймауте LLM возвращает empty BeliefState в пределах hard-cap + 100 мс
- [ ] T012 [P] [US1] Написать тест `test_diagnose_gap_reranks_with_belief` в `tests/test_navigator.py` — на сценарии, где baseline возвращает "неверный" root_gap, с belief_state возвращает ожидаемый gap
- [ ] T013 [P] [US1] Написать тест `test_diagnose_gap_no_belief_unchanged` в `tests/test_navigator.py` — при belief_state=None поведение идентично baseline

### Реализация US1

- [ ] T014 [US1] Создать класс `MentalModelAgent(BaseAgent)` в `src/agents/mental_model_agent.py` — конструктор с llm_client и опциональным knowledge_graph, поле `_profile = get_active_profile()`
- [ ] T015 [US1] Реализовать метод `_build_prompt_short()` в `src/agents/mental_model_agent.py` — короткий промпт для lite-профиля (~100 токенов input, cap 150 output), без few-shot примеров, одношаговый JSON-output
- [ ] T016 [US1] Реализовать метод `_build_prompt_full()` в `src/agents/mental_model_agent.py` — полный промпт для standard/max (~400 токенов input, cap 500 output) с 2 few-shot примерами и 3-шаговым reasoning (misconception → topic belief → reaction prediction)
- [ ] T017 [US1] Реализовать метод `infer()` в `src/agents/mental_model_agent.py` — выбирает промпт по `tom_prompt_style`, вызывает `llm.generate(format="json", num_predict=N)`, парсит JSON, при ошибке возвращает `BeliefState.empty()`, логирует `tom.invoked`/`tom.completed`/`tom.fallback`
- [ ] T018 [US1] Реализовать one-pass JSON repair в `src/agents/mental_model_agent.py` — при первом парсинг-фейле добавить к промпту "Re-output valid JSON only:" и повторить ровно один раз; если снова fail — empty BeliefState
- [ ] T019 [US1] Расширить `diagnose_gap()` в `src/knowledge/navigator.py` — добавить параметр `belief_state: Optional[BeliefState] = None`. Когда не None и confidence ≥ 0.5, вычислить relevance score для каждого prereq (теги ∩ misconception tokens, наличие COMMON_ERROR_FOR ребра от misconception узла, difficulty match), пересортировать missing_prerequisites по (relevance_score desc, depth desc), установить root_gap в top-ranked
- [ ] T020 [US1] Добавить keyword-tokenizer helper в `src/knowledge/navigator.py` (или в новом `src/knowledge/text_utils.py`) — простая функция `_tokenize(text: str) -> set[str]` с стемингом для русского (например, отбрасывать последние 2-3 символа), работает без внешних NLP-зависимостей — требование Lite-профиля

**Чекпоинт**: MentalModelAgent работает, diagnose_gap использует belief_state, все 5 unit/integration-тестов проходят. MVP готов для измерения root-hit rate.

---

## Фаза 4: User Story 2 — Planner учитывает предсказанные реакции ученика (Priority: P2)

**Цель**: Planner получает BeliefState → выбирает стратегию по predicted_reactions, а не только по правилам.

**Независимый тест**: сравнить выбор стратегии на 10 сценариях с/без belief_state, убедиться, что хотя бы на 3 сценариях стратегия меняется в ожидаемую сторону.

### Тесты для US2

- [ ] T021 [P] [US2] Написать тест `test_planner_uses_predicted_reactions` в `tests/test_tom_integration.py` — mock Planner с belief_state, где predicted_reactions["encourage"]="rebuilds confidence" → Planner выбирает ENCOURAGE для frustrated студента
- [ ] T022 [P] [US2] Написать тест `test_planner_low_confidence_ignores_belief` в `tests/test_tom_integration.py` — при confidence=0.2 Planner игнорирует belief_state и использует rule-based логику

### Реализация US2

- [ ] T023 [US2] Расширить сигнатуру `create_plan()` в `src/agents/planner.py` — добавить параметр `belief_state: Optional[BeliefState] = None` после существующего `graph_context`
- [ ] T024 [US2] Добавить метод `_strategy_from_belief()` в `src/agents/planner.py` — принимает belief_state, если confidence ≥ 0.5 и predicted_reactions непусто, возвращает стратегию с наиболее благоприятной предсказанной реакцией; иначе None
- [ ] T025 [US2] Интегрировать `_strategy_from_belief()` в `create_plan()` — если метод вернул стратегию, использовать её вместо rule-based выбора; если belief_state.active_misconception_node_id не None, сместить к CONCEPTUAL_REPAIR
- [ ] T026 [US2] Логировать решение Planner в `src/agents/planner.py` — при подмене стратегии под влиянием belief_state писать в лог: стратегия до, стратегия после, confidence

**Чекпоинт**: Planner меняет стратегию под влиянием belief_state, fallback на rule-based логику работает.

---

## Фаза 5: User Story 3 — Graceful degradation и resource-aware выполнение (Priority: P2)

**Цель**: система работает на Lite-профиле (16 GB, CPU), корректно обрабатывает LLM-ошибки, не падает никогда.

**Независимый тест**: прогнать полный оркестратор с ToM в 4 условиях: (a) LLM работает, (b) timeout, (c) invalid JSON, (d) Ollama недоступна. Все 4 пути должны давать валидный ответ студенту.

### Тесты для US3

- [ ] T027 [P] [US3] Написать тест `test_orchestrator_with_tom_enabled` в `tests/test_tom_integration.py` — полный pipeline run с включённой ToM, убедиться, что ответ валиден
- [ ] T028 [P] [US3] Написать тест `test_orchestrator_with_tom_disabled` в `tests/test_tom_integration.py` — `enable_tom_agent=False` → pipeline работает идентично baseline, MentalModelAgent не вызывается
- [ ] T029 [P] [US3] Написать тест `test_orchestrator_llm_outage` в `tests/test_tom_integration.py` — mock LLMClient бросает исключение → pipeline завершается успешно, лог содержит ровно один ERROR
- [ ] T030 [P] [US3] Написать тест `test_mental_model_lite_prompt_latency` в `tests/test_mental_model_agent.py` — с lite-профилем промпт ≤200 input tokens, в тесте используется mock LLM с измеряемой латентностью

### Реализация US3

- [ ] T031 [US3] Добавить новый stage `MENTAL_MODEL = "mental_model"` в `AgentStage` enum в `src/agents/orchestrator.py`
- [ ] T032 [US3] Инициализировать `self.mental_model_agent` в `AgentOrchestrator.__init__()` — создаётся только если `feature_enabled("enable_tom_agent")`, иначе None
- [ ] T033 [US3] Добавить вызов MENTAL_MODEL stage в `AgentOrchestrator.process()` — между PROFILER и GRAPH_NAV стадиями, wrap в try/except для graceful degradation, при ошибке сохранить `belief_state = BeliefState.empty()` и продолжить
- [ ] T034 [US3] Передать `belief_state` в `planner.create_plan(...)` в orchestrator.py — рядом с существующим `graph_context=`
- [ ] T035 [US3] Передать `belief_state` в `navigator.diagnose_gap(...)` в orchestrator.py при выполнении GRAPH_NAV — чтобы re-ranking работал
- [ ] T036 [US3] Добавить timeout в `MentalModelAgent.infer()` — использовать `signal`-based timeout или async wait_for со значениями из профиля (2000мс lite, 1000мс standard/max); при истечении вернуть empty BeliefState

**Чекпоинт**: pipeline устойчив к LLM-ошибкам, ToM можно полностью отключать через профиль, latency budget не нарушается.

---

## Фаза 6: User Story 4 — Evaluation suite и A/B сравнение (Priority: P3)

**Цель**: воспроизводимый скрипт выдаёт Markdown-отчёт со сравнением метрик baseline vs ToM.

**Независимый тест**: запустить `python evaluation/tom_ab_eval.py` — получить отчёт с цифрами root-hit rate до/после, misconception accuracy, Socratic quality delta.

### Реализация US4

- [ ] T037 [P] [US4] Создать файл `evaluation/scenarios/tom_scenarios.json` — 15+ сценариев с полями: name, mastery, student_message, topic, expected_misconception, expected_belief, expected_root_gap
- [ ] T038 [US4] Создать скрипт `evaluation/tom_ab_eval.py` — загружает 5 сценариев из `baseline_eval.py` + 15 из tom_scenarios.json, прогоняет каждый в двух режимах (ToM off/on), собирает результаты
- [ ] T039 [US4] Реализовать функцию `eval_gap_reranking()` в `evaluation/tom_ab_eval.py` — для каждого сценария запустить `diagnose_gap` без belief_state и с belief_state (от реальной LLM-инференции), сравнить root_hit и any_hit
- [ ] T040 [US4] Реализовать функцию `eval_misconception_accuracy()` в `evaluation/tom_ab_eval.py` — для каждого сценария сравнить `belief_state.active_misconception` с expected_misconception (keyword overlap ≥ 0.5 = hit)
- [ ] T041 [US4] Реализовать функцию `eval_socratic_quality()` в `evaluation/tom_ab_eval.py` — 20 диалогов (из существующего `data/training/dialogs.jsonl` — sample), прогнать планировщик с/без belief_state, измерить долю стратегий типа SCAFFOLDED/PROBLEMATIZE vs TELL
- [ ] T042 [US4] Реализовать генерацию Markdown-отчёта в `evaluation/tom_ab_eval.py` — формат: таблица "Metric | Baseline | ToM | Delta" + per-scenario детали + ошибки
- [ ] T043 [US4] Запустить A/B evaluation — `python evaluation/tom_ab_eval.py`, сохранить артефакт в `evaluation/reports/tom_ab_2026-XX-XX.md`

**Чекпоинт**: есть воспроизводимый артефакт с цифрами для диплома.

---

## Фаза 7: Polish & Cross-Cutting

**Цель**: качество кода, документация на русском, финальные коммиты.

- [ ] T044 [P] Запустить `ruff check src/agents/mental_model_agent.py src/knowledge/navigator.py src/agents/planner.py src/agents/orchestrator.py src/data/schemas.py src/resource_profiles.py evaluation/tom_ab_eval.py tests/test_mental_model_agent.py tests/test_tom_integration.py` и исправить все замечания
- [ ] T045 [P] Добавить type hints ко всем публичным методам в `src/agents/mental_model_agent.py` согласно PEP 484
- [ ] T046 [P] Создать `docs/TOM_TUTOR.md` на русском — описание архитектуры агента, промпт-стратегии per profile, примеры использования, troubleshooting
- [ ] T047 Обновить `docs/ARCHITECTURE.md` — пометить фичу 017 как DONE в Feature Timeline, добавить ссылки на `docs/TOM_TUTOR.md` и `evaluation/reports/tom_ab_*.md`
- [ ] T048 Запустить весь набор тестов — `python -m pytest tests/test_knowledge_forge.py tests/test_navigator.py tests/test_navigator_tools.py tests/test_graph_evolution.py tests/test_resource_profiles.py tests/test_source_extractor.py tests/test_mental_model_agent.py tests/test_tom_integration.py -v` и убедиться, что все проходят
- [ ] T049 Валидировать quickstart.md — выполнить все code blocks из `specs/017-tom-tutor/quickstart.md` и исправить расхождения с реальной реализацией
- [ ] T050 Обновить `CLAUDE.md` Recent Changes — добавить суммари по ToM-Tutor (архитектура, метрики, ключевые решения)

---

## Зависимости и порядок выполнения

### Зависимости фаз

- **Setup (Фаза 1)**: без зависимостей — можно начинать сразу
- **Foundational (Фаза 2)**: зависит от Setup — БЛОКИРУЕТ все user stories
- **US1 (Фаза 3)**: зависит от Фазы 2 — **MVP**
- **US2 (Фаза 4)**: зависит от US1 (нужны MentalModelAgent и BeliefState)
- **US3 (Фаза 5)**: зависит от US1 (нужен MentalModelAgent для интеграции в pipeline)
- **US4 (Фаза 6)**: зависит от US1+US3 (нужна рабочая pipeline для evaluation)
- **Polish (Фаза 7)**: зависит от всех user stories, которые вошли в scope

### Цепочка зависимостей user stories

```text
Фаза 1 (Setup)
    ↓
Фаза 2 (Foundational: BeliefState + profile flag)
    ↓
Фаза 3 (US1: MentalModelAgent + gap re-ranking)  ← MVP!
    ↓
    ├→ Фаза 4 (US2: Planner integration) ────┐
    │                                         │
    └→ Фаза 5 (US3: orchestrator + degradation)
                                              ↓
                                         Фаза 6 (US4: A/B evaluation)
                                              ↓
                                         Фаза 7 (Polish)
```

### Возможности параллелизации

- **Фаза 1**: T002 и T003 параллельны
- **Фаза 2**: T005, T006 параллельны с T004; T007, T008 параллельны
- **Фаза 3**: все 5 тестов (T009-T013) можно писать параллельно; T014 нужен перед T015-T018; T019 параллелен с T014-T018 (разные файлы)
- **Фаза 4**: T021, T022 параллельны; реализация T023-T026 последовательна (один файл)
- **Фаза 5**: тесты T027-T030 параллельны; T031 нужен перед T032-T036 (один файл, один stage)
- **Фаза 6**: T037 параллелен со всем остальным; T038-T042 последовательны (один файл)
- **Фаза 7**: T044, T045, T046 параллельны

---

## Стратегия имплементации

### MVP (сначала US1)

1. Завершить Фазу 1: Setup (проверка 016 тестов)
2. Завершить Фазу 2: Foundational (BeliefState + flag)
3. Завершить Фазу 3: US1 — MentalModelAgent + gap re-ranking
4. **ОСТАНОВИТЬСЯ И ВАЛИДИРОВАТЬ**: запустить baseline_eval.py — увидеть root-hit rate 60% → ?
5. Коммит MVP, дальше решать по результатам

### Инкрементальная поставка

1. Setup + Foundational → ядро готово
2. + US1 (gap re-ranking) → **MVP с измеримой метрикой** (root-hit rate)
3. + US2 (Planner) → стратегии учитывают ToM
4. + US3 (orchestrator) → устойчивость + graceful degradation
5. + US4 (evaluation) → готовый артефакт для диплома
6. + Polish → документация на русском, финал

### Рекомендация по датам (1-неделя)

| День | Задачи | Deliverable |
|------|--------|-------------|
| 1 | Фаза 1 + Фаза 2 | BeliefState, profile flag, тесты |
| 2 | Фаза 3 (T014-T020) | MentalModelAgent + re-ranking |
| 3 | Фаза 3 тесты + T009-T013 | MVP готов, re-run baseline_eval |
| 4 | Фаза 4 + Фаза 5 | Planner + orchestrator + degradation |
| 5 | Фаза 6 (T037-T042) | A/B evaluation артефакт |
| 6 | Фаза 7 + verification | docs/TOM_TUTOR.md, всё на месте |
| 7 | Буфер / запасной | Исправление багов, повторный A/B |

---

## Заметки

- Все коммиты на английском по проектной конвенции (CLAUDE.md), но комментарии в тестах и docs/TOM_TUTOR.md — на русском, согласно запросу пользователя
- [P] = разные файлы, без зависимостей
- [Story] метка связывает задачу с конкретной user story для трассировки
- Каждая user story должна быть независимо тестируема
- Тесты пишутся до реализации (в US1 и US2 — обязательно)
- Коммит после каждой задачи или логической группы (например, все тесты US1 → 1 коммит, реализация US1 → 1-2 коммита)
- Останавливаться на каждом чекпоинте, проверять независимо
- Избегать: неясных задач, конфликтов по файлам, cross-story зависимостей, которые ломают независимость
