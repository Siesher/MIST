Ядро системы MITS составляет мультиагентный пайплайн, организованный по паттерну GenMentor [9]. Каждый агент инкапсулирует конкретную педагогическую функцию и взаимодействует с остальными через стандартизированные интерфейсы. Такая архитектура обеспечивает независимое тестирование агентов, возможность замены отдельных компонентов и устойчивость системы при сбоях отдельных агентов (graceful degradation).

## Базовый класс BaseAgent

Все агенты наследуют от абстрактного класса `BaseAgent`, определяющего унифицированный интерфейс взаимодействия:

```python
class BaseAgent(ABC):
    def __init__(self, name: str, llm_client: Optional[LLMClient] = None,
                 system_prompt: str = ""):
        self._name = name
        self.llm = llm_client
        self._status = AgentStatus.HEALTHY
        self._call_count = 0
        self._error_count = 0
        self._total_latency_ms = 0.0

    @abstractmethod
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Основной метод обработки — реализуется каждым агентом."""
        pass

    def health_check(self, timeout_ms: float = 5000) -> HealthCheckResult:
        """Проверка работоспособности агента."""
        start = time.time()
        is_healthy = self._perform_health_check()
        latency = (time.time() - start) * 1000
        status = AgentStatus.DEGRADED if latency > timeout_ms else (
            AgentStatus.HEALTHY if is_healthy else AgentStatus.UNHEALTHY
        )
        return HealthCheckResult(status=status, agent_name=self._name,
                                  latency_ms=latency)

    def get_metrics(self) -> Dict[str, Any]:
        """Метрики производительности агента."""
        return {
            "agent_name": self._name,
            "status": self._status.value,
            "call_count": self._call_count,
            "error_rate": self._error_count / max(self._call_count, 1),
            "avg_latency_ms": self._total_latency_ms / max(self._call_count, 1),
        }
```

Стандартизированный контракт включает три публичных метода: `process()` — основная обработка запроса; `health_check()` — проверка работоспособности с таймаутом; `get_metrics()` — сбор метрик производительности (количество вызовов, частота ошибок, средняя задержка). Помимо этого, базовый класс содержит вспомогательный метод `_call_llm()`, унифицирующий обращение к LLM через системный промпт агента.

## Orchestrator: координация агентов

`AgentOrchestrator` — центральный координатор пайплайна, реализующий последовательность: Profiler → Planner → Tutor → Verifier. Оркестратор поддерживает три режима работы: `FULL` (полный пайплайн), `FAST` (только Tutor + Verifier) и `DIAGNOSTIC` (Profiler + Planner без генерации ответа). Выбор режима определяется конфигурацией `OrchestratorMode` при инициализации сервиса.

Ключевая функция оркестратора — `process_turn()` — реализует следующую последовательность:

```python
def process_turn(self, context: TurnContext,
                 session_id: Optional[str] = None) -> TurnResult:
    trace = self._create_trace(session_id)
    # 1. Классификация запроса (T037: query routing)
    query_type = self._classify_query(context.student_input)
    routing_config = self._get_routing_config(query_type)
    # 2. Профилирование ошибок
    if routing_config.get("use_profiler"):
        profile = self.profiler.diagnose(...)   # -> StudentProfile
    # 3. ToM-Tutor (017): вывод BeliefState
    if self.mental_model_agent:
        belief_state = self.mental_model_agent.infer(...)
    # 4. Планирование стратегии
    if routing_config.get("use_planner"):
        plan = self.planner.create_plan(profile, context, belief_state)
    # 5. RAG-контекст
    if routing_config.get("use_rag"):
        rag_context = self.rag.retrieve_context(...)
    # 6. Генерация ответа (с повторами при невалидном ответе)
    for attempt in range(self.max_retries + 1):
        response = self._generate_response(context, plan, profile, rag_context)
        verification = self.verifier.verify(response, ...)
        if verification.is_valid:
            break
    return TurnResult(response=..., move_type=..., pipeline_trace=trace)
```

Интеллектуальная маршрутизация запросов (query routing) классифицирует ввод ученика по 9 типам (`HINT_REQUEST`, `ANSWER_ATTEMPT`, `CONFUSION`, `GREETING`, `NEXT_TASK`, `SOLUTION_CHECK`, `CLARIFICATION`, `QUESTION`, `OFF_TOPIC`) с помощью набора регулярных выражений. В зависимости от типа запроса конфигурация маршрутизации определяет, какие агенты запускаются: например, для `GREETING` запускается только быстрый ответ без агентного пайплайна, для `ANSWER_ATTEMPT` — полный пайплайн с профайлером.

## Graceful Degradation

Каждый агент обёрнут в блок `try/except` с соответствующим fallback-обработчиком. При сбое профайлера создаётся минимальный профиль с нейтральными значениями; при сбое планировщика применяется базовая стратегия `SCAFFOLDED`; при сбое RAG пайплайн продолжает работу без контекста; при сбое верификатора ответ считается валидным. Все сбои фиксируются в `PipelineTrace` для последующего анализа.

## Агент Profiler

`ProfilerAgent` выполняет диагностику ответа ученика и формирует `StudentProfile`. Агент генерирует промпт с текстом задачи, правильным подходом и ответом ученика, запрашивает у LLM структурированный JSON с классификацией ошибок (концептуальная, вычислительная, синтаксическая), списком заблуждений и рекомендуемым подходом. Параллельно профайлер обновляет модель ученика через `KnowledgeTracker`: регистрирует попытку, обновляет BKT-вероятности и DKT-предсказания для задействованных навыков.

## Агент Planner

`PlannerAgent` выбирает педагогическую стратегию на основе профиля ученика и контекста сессии. Реализовано 8 стратегий (``TeachingStrategy``): `GUIDED_DISCOVERY`, `SCAFFOLDED`, `ERROR_CORRECTION`, `CONCEPTUAL_REPAIR`, `ENCOURAGEMENT`, `DIRECT_INSTRUCTION`, `PEER_SIMULATION`, `METACOGNITIVE`. Выбор стратегии определяется деревом решений: при низком освоении навыка и концептуальных ошибках применяется `CONCEPTUAL_REPAIR`; при высоком освоении и вычислительных ошибках — `ERROR_CORRECTION`; при первой попытке — `SCAFFOLDED`. Дополнительно учитывается `BeliefState` от ToM-агента (017): если агент фиксирует активное заблуждение, приоритет повышается для `CONCEPTUAL_REPAIR` независимо от уровня освоения.

## Агент Tutor

`TutorAgent` — генератор сократических ответов. Агент собирает контекст из четырёх источников: системный промпт (сократический стиль, правила), педагогический план от Planner, RAG-контекст (подсказки, типичные ошибки), история диалога (последние 6 сообщений). Итоговый промпт передаётся в LLM с параметрами `thinking=True` для активации режима рассуждения. При потоковой генерации (`guided_learning` режим) агент использует `generate_stream()`, разделяя thinking-токены и content-токены по типу события для раздельной отправки через WebSocket.

## Агент Verifier

`VerifierAgent` проверяет качество ответа тьютора по 10 критериям: отсутствие прямого ответа (no_spoiler), наличие вопросительного элемента, соответствие педагогическому ходу, отсутствие токсичности, длина ответа (2–6 предложений), корректность LaTeX-синтаксиса, релевантность задаче, сократический стиль, отсутствие повторений из истории, общий score ≥ 0,7. При score < 0,7 оркестратор повторяет генерацию (до `max_retries = 2`). Верификация реализована через комбинацию regex-проверок (быстрые) и LLM-оценки (точные), что балансирует скорость и качество.
