Взаимодействие системы MITS с языковой моделью реализовано через единый клиентский класс `LLMClient`, инкапсулирующий работу с Ollama REST API. Применение паттерна Facade обеспечивает изоляцию агентного ядра от деталей конкретного inference-бэкенда: все агенты вызывают методы `LLMClient` и не имеют прямых зависимостей от Ollama, что упрощает возможную замену бэкенда (например, на llama.cpp server или vLLM).

## Модуль LLMClient

Класс `LLMClient` инициализируется с параметрами модели и хоста Ollama:

```python
class LLMClient:
    def __init__(self, model: str = None, host: str = None,
                 temperature: float = None, max_tokens: int = None):
        self.host = host or settings.OLLAMA_HOST
        self.client = ollama.Client(host=self.host)
        requested_model = model or settings.MODEL_NAME
        self.model = self._resolve_model_with_fallback(requested_model)
        self._apply_model_defaults()
```

Метод `_resolve_model_with_fallback()` проверяет доступность запрошенной модели через `ollama.list()` и при её отсутствии автоматически переключается на `MODEL_FALLBACK` из конфигурации. Это обеспечивает непрерывную работу системы при временной недоступности основной модели.

## Метод generate()

Метод `generate()` реализует синхронную генерацию с полной поддержкой thinking mode:

```python
def generate(self, prompt: str, system: Optional[str] = None,
             temperature: float = None, max_tokens: int = None,
             thinking: bool = None, json_mode: bool = False) -> str:
    thinking = thinking if thinking is not None else settings.THINKING_MODE
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    # Для Qwen3-семейства thinking активируется префиксом /think
    user_content = prompt
    if thinking and self._is_qwen_model() and not prompt.startswith("/think"):
        user_content = f"/think\n{prompt}"
    messages.append({"role": "user", "content": user_content})
    options = self._get_options(temperature, max_tokens)
    if json_mode:
        options["format"] = "json"
    response = self.client.chat(model=self.model, messages=messages,
                                 options=options, keep_alive="30m")
    content = response["message"]["content"]
    # Извлечение ответа из thinking-блока
    if thinking and "<think>" in content:
        _, content = self._parse_thinking(content)
    return content
```

Параметр `keep_alive="30m"` удерживает модель в памяти Ollama в течение 30 минут после последнего запроса, исключая повторную загрузку весов при частых обращениях. Для моделей семейства Qwen3.5 thinking-режим активируется через параметр `think=False` при необходимости его отключения (в частности, для JSON-режима агентов, где thinking-токены конкурируют с полезной нагрузкой за бюджет `max_tokens`).

## Метод generate_stream()

Метод `generate_stream()` реализует потоковую генерацию через синхронный генератор Python:

```python
def generate_stream(self, prompt: str, system: Optional[str] = None,
                    thinking: bool = None, ...) -> Generator[str, None, None]:
    stream = self.client.chat(model=self.model, messages=messages,
                               stream=True, options=options)
    in_thinking = False
    thinking_buffer = ""
    for chunk in stream:
        token = chunk.message.content or ""
        thinking_token = getattr(chunk.message, "thinking", "")
        if thinking_token:
            yield ("thinking", thinking_token)
            continue
        if thinking and "<think>" in full_response and not in_thinking:
            in_thinking = True
            ...
        if in_thinking and "</think>" in full_response:
            in_thinking = False
            yield ("content", response_after_think)
        elif not in_thinking:
            yield ("content", token)
```

Генератор возвращает кортежи `(тип, токен)`, где тип принимает значения `"thinking"` или `"content"`. Это позволяет WebSocket-хэндлеру маршрутизировать токены в разные каналы: thinking-токены отправляются клиенту как событие `thinking_token` для отображения в `ThinkingPanel`, content-токены — как событие `token` для основного поля ответа.

## Интеграция с Ollama

Для деплоя дообученной модели используется Ollama (версия 0.5+) с форматом GGUF Q4\_K\_M. GGUF-квантизация снижает потребление RAM с ~18 ГБ (bf16) до ~6 ГБ без существенной потери качества на коротких генерациях. Конфигурация модели задаётся через Modelfile:

```
FROM ./mits-qwen35-9b-final.Q4_K_M.gguf
RENDERER qwen3.5
PARSER qwen3.5
PARAMETER num_ctx 8192
PARAMETER temperature 1.0
PARAMETER top_k 20
SYSTEM "Ты — сократический STEM-репетитор..."
```

Директивы `RENDERER qwen3.5` и `PARSER qwen3.5` активируют специализированную обработку thinking-блоков Ollama для моделей семейства Qwen3.5: при потоковой генерации Ollama автоматически разделяет thinking-токены (поле `message.thinking`) от content-токенов (поле `message.content`), что упрощает парсинг на стороне `LLMClient`.

## Кеширование запросов

Слой кеширования реализован в классе `ResponseCache` (`src/inference/cache.py`). Кеш поддерживает два режима поиска:

1. **Точное совпадение** — по MD5-хешу конкатенации `(problem_context, student_input)`. Гарантирует нулевую задержку для идентичных запросов.

2. **Семантическое совпадение** — через косинусное расстояние между эмбеддингами запроса (модель `paraphrase-multilingual-MiniLM-L12-v2`). Позволяет обслуживать похожие запросы («с чего начать» и «как подступиться к задаче») из кеша. Порог сходства: $\cos(\mathbf{q}, \mathbf{k}) \geq 0{,}90$.

Ключ кеша формируется функцией `_make_key()`:

```python
def _make_key(self, student_input: str, problem_context: str) -> str:
    combined = f"{problem_context.strip()}|{student_input.strip()}"
    return hashlib.md5(combined.encode()).hexdigest()
```

LRU-кеш (`LRUCache`) с максимальным размером 1000 записей обеспечивает автоматическое вытеснение редко используемых ответов. TTL-инвалидация применяется к RAG-кешу: эмбеддинги хранятся 2 часа, результаты retrieval — 30 минут (`RAGQueryCache`). Это предотвращает устаревание результатов при обновлении базы знаний.

Контекстно-зависимое совпадение (context-aware matching) дополнительно учитывает хеш педагогического контекста `compute_context_hash(topic, difficulty, student_level)`: ответы с совпадающим контекстом получают бонус +0,05 к score сходства, что приоритизирует релевантные записи при наличии нескольких семантически близких вариантов.
