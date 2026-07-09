# Phase 0+1: живой чат через llama-server (фундамент интеграции) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: используйте superpowers:executing-plans (inline, рекомендовано для инфраструктуры с долгоживущими серверами) или superpowers:subagent-driven-development. Шаги помечены чекбоксами (`- [ ]`).

**Goal:** Поднять стек end-to-end так, чтобы во `frontend/` (текущий дизайн) шёл **живой сократический чат**, где токены генерирует модель, обслуживаемая **llama-server (llama-swap :8081)**, и всё это доступно с другого устройства по LAN.

**Architecture:** В `orchestrator_service.initialize()` уже есть переключатель LLM-бэкендов (HF/Ollama). Добавляем третью ветку `llamacpp` → новый `OpenAICompatLLMClient`, который реализует тот же интерфейс (`generate`, `generate_stream` с yield `("thinking"|"content", token)`), обращаясь к OpenAI-совместимому `POST /v1/chat/completions`. Чат-WS (`process_message_stream`) и фронт остаются без изменений.

**Tech Stack:** FastAPI, `requests` (SSE-стриминг), llama-swap (OpenAI API, :8081), Next.js 14, pytest.

**Scope:** только **chat-режим** (прямой тьютор). Guided-режим (tool-calling агентов через llama-server) — отдельный план (риск). Темизация/рестайл — отдельные планы (Ф2/Ф3).

---

### Task 1: Конфиг backend — настройки llamacpp-бэкенда + CORS для LAN

**Files:**
- Modify: `backend/app/config.py`

- [ ] **Step 1: Добавить поля в `BackendSettings`**

В `backend/app/config.py` после строки `OLLAMA_HOST` добавить:

```python
    # LLM backend selection: "ollama" | "llamacpp"
    LLM_BACKEND: str = "ollama"
    # llama-server / llama-swap OpenAI-compatible base (used when LLM_BACKEND=llamacpp)
    LLM_BASE_URL: str = "http://127.0.0.1:8090/v1"  # llama-swap direct (mits-eval-*); 8081 = OpenCode router.py
    # Model tag as configured in llama-swap.yaml (e.g. mits-eval-kto / mits-eval-gspo)
    LLM_MODEL: str = "mits-eval-kto"
```

И расширить CORS (значение по умолчанию оставить, переопределяется через env):

```python
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
```

- [ ] **Step 2: Проверить, что конфиг читается**

Run: `python -c "from backend.app.config import backend_settings as s; print(s.LLM_BACKEND, s.LLM_BASE_URL, s.LLM_MODEL)"`
Expected: `ollama http://127.0.0.1:8081/v1 mits-eval-kto`

- [ ] **Step 3: Commit**

```bash
git add backend/app/config.py
git commit -m "feat(backend): add llamacpp LLM backend config + LAN CORS default"
```

---

### Task 2: OpenAI-совместимый LLM-клиент (порт проверенного SSE-парсера)

**Files:**
- Create: `src/models/openai_llm_client.py`
- Test: `tests/test_openai_llm_client.py`

- [ ] **Step 1: Написать падающий тест на разбор SSE-стрима**

`tests/test_openai_llm_client.py`:

```python
"""Unit-тест разбора OpenAI SSE-стрима в ("thinking"/"content", token)."""
from src.models.openai_llm_client import parse_sse_line


def test_parse_content_delta():
    line = b'data: {"choices":[{"delta":{"content":"Hello"}}]}'
    assert parse_sse_line(line) == [("content", "Hello")]


def test_parse_reasoning_delta():
    line = b'data: {"choices":[{"delta":{"reasoning_content":"hmm"}}]}'
    assert parse_sse_line(line) == [("thinking", "hmm")]


def test_parse_done_and_blank():
    assert parse_sse_line(b"") == []
    assert parse_sse_line(b"data: [DONE]") == []
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `python -m pytest tests/test_openai_llm_client.py -v`
Expected: FAIL (`ModuleNotFoundError: src.models.openai_llm_client`).

- [ ] **Step 3: Реализовать клиент**

`src/models/openai_llm_client.py`:

```python
"""OpenAI-совместимый LLM-клиент для llama-server / llama-swap (:8081).

Реализует тот же контракт, что src/models/llm_client.LLMClient, в части,
нужной chat-режиму: generate(), generate_stream() (yield ("thinking"|"content", token)),
check_connection(), list_models(). Логика SSE портирована из
scripts/eval_local_llamaserver.py::call_llama_server_stream (DRY).
"""
from __future__ import annotations

import json
from typing import Callable, Generator, List, Optional, Tuple

import requests
import structlog

from backend.app.config import backend_settings

logger = structlog.get_logger()

DEFAULT_SAMPLING = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0}


def parse_sse_line(raw_line: bytes) -> List[Tuple[str, str]]:
    """Разобрать одну SSE-строку → список ("thinking"|"content", token)."""
    if not raw_line:
        return []
    s = raw_line.decode("utf-8", errors="replace").strip()
    if not s.startswith("data: "):
        return []
    payload = s[6:]
    if payload == "[DONE]":
        return []
    try:
        chunk = json.loads(payload)
    except json.JSONDecodeError:
        return []
    choices = chunk.get("choices") or []
    if not choices:
        return []
    delta = choices[0].get("delta", {}) or {}
    out: List[Tuple[str, str]] = []
    if delta.get("reasoning_content"):
        out.append(("thinking", delta["reasoning_content"]))
    if delta.get("content"):
        out.append(("content", delta["content"]))
    return out


class OpenAICompatLLMClient:
    def __init__(self, model: str = None, base_url: str = None, **_):
        self.model = model or backend_settings.LLM_MODEL
        self.base_url = (base_url or backend_settings.LLM_BASE_URL).rstrip("/")
        self.chat_url = f"{self.base_url}/chat/completions"
        logger.info("openai_llm_client_initialized", model=self.model, base_url=self.base_url)

    def list_models(self) -> List[str]:
        try:
            r = requests.get(f"{self.base_url}/models", timeout=5)
            r.raise_for_status()
            return [m.get("id", "") for m in r.json().get("data", [])]
        except requests.RequestException:
            return []

    def check_connection(self) -> bool:
        try:
            return requests.get(f"{self.base_url}/models", timeout=5).ok
        except requests.RequestException:
            return False

    def _body(self, messages, thinking, stream, temperature, max_tokens):
        body = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "chat_template_kwargs": {"enable_thinking": bool(thinking)},
            **DEFAULT_SAMPLING,
        }
        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        return body

    def generate(self, prompt: str, system: Optional[str] = None, thinking: bool = None,
                 temperature: float = None, max_tokens: int = None, **_) -> str:
        messages = ([{"role": "system", "content": system}] if system else []) + \
                   [{"role": "user", "content": prompt}]
        body = self._body(messages, thinking, False, temperature, max_tokens)
        r = requests.post(self.chat_url, json=body, timeout=(30, 600))
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    def generate_stream(self, prompt: str, system: Optional[str] = None, thinking: bool = None,
                        on_token: Optional[Callable[[str], None]] = None,
                        on_thinking: Optional[Callable[[str], None]] = None,
                        **kwargs) -> Generator[Tuple[str, str], None, None]:
        messages = ([{"role": "system", "content": system}] if system else []) + \
                   [{"role": "user", "content": prompt}]
        body = self._body(messages, thinking, True,
                          kwargs.get("temperature"), kwargs.get("max_tokens"))
        with requests.post(self.chat_url, json=body, stream=True, timeout=(30, 120)) as r:
            r.raise_for_status()
            for raw_line in r.iter_lines(decode_unicode=False):
                for kind, tok in parse_sse_line(raw_line):
                    if kind == "thinking" and on_thinking:
                        on_thinking(tok)
                    elif kind == "content" and on_token:
                        on_token(tok)
                    yield (kind, tok)
```

- [ ] **Step 4: Запустить тест — убедиться, что проходит**

Run: `python -m pytest tests/test_openai_llm_client.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/models/openai_llm_client.py tests/test_openai_llm_client.py
git commit -m "feat(llm): OpenAI-compatible client for llama-server (chat streaming)"
```

---

### Task 3: Внедрить ветку `llamacpp` в orchestrator_service

**Files:**
- Modify: `backend/app/services/orchestrator_service.py` (внутри `initialize()`, перед Ollama-веткой ~стр. 254)

- [ ] **Step 1: Добавить ветку выбора бэкенда**

Перед блоком `# ─── Ollama backend (default) ───` (после HF-блока) вставить:

```python
            # ─── llama-server (OpenAI-compatible) backend ───
            if self._llm_client is None and backend_settings.LLM_BACKEND == "llamacpp":
                from src.models.openai_llm_client import OpenAICompatLLMClient

                self._llm_client = OpenAICompatLLMClient(model=backend_settings.LLM_MODEL)
                self._backend_kind = "llamacpp"
                self._backend_info = {
                    "kind": "llamacpp",
                    "model": backend_settings.LLM_MODEL,
                    "base_url": backend_settings.LLM_BASE_URL,
                    "turbo_quant": True,
                    "context_length": 32768,
                }
                logger.info(f"llama-server backend ready: {backend_settings.LLM_MODEL}")
```

(Существующая Ollama-ветка `if self._llm_client is None:` остаётся фолбэком.)

- [ ] **Step 2: Smoke — клиент создаётся и видит модель**

Run (с поднятым llama-swap, см. Task 4):
`python -c "import os; os.environ['LLM_BACKEND']='llamacpp'; from src.models.openai_llm_client import OpenAICompatLLMClient as C; c=C(); print('models:', c.list_models()); print(c.generate('2+2=? Кратко.', max_tokens=32, thinking=False))"`
Expected: список содержит `mits-eval-kto`; печатается короткий ответ модели.

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/orchestrator_service.py
git commit -m "feat(backend): wire llamacpp backend branch into orchestrator init"
```

---

### Task 4: Запустить llama-swap (:8081)

**Files:** none (операционный шаг). Конфиг: `C:/OpenCode/llama-swap/llama-swap.yaml` (модели `mits-eval-*`).

- [ ] **Step 1: Стартовать llama-swap (фон)**

PowerShell (фоновый процесс):
`Start-Process -FilePath "C:/OpenCode/llama-swap/llama-swap.exe" -ArgumentList '--config','C:/OpenCode/llama-swap/llama-swap.yaml','--listen','127.0.0.1:8081' -WindowStyle Hidden`
(Точные аргументы сверить с тем, как стек запускается в проекте; конфиг уже содержит `mits-eval-kto`.)

- [ ] **Step 2: Дождаться готовности**

Run: `curl -s http://127.0.0.1:8081/v1/models`
Expected: JSON со списком моделей, включая `mits-eval-kto`. (Первый запрос на модель грузит её — 5-10 c.)

---

### Task 5: Запустить backend на 0.0.0.0:8000 с llamacpp

**Files:** none (операционный шаг) или `backend/.env`.

- [ ] **Step 1: Поднять uvicorn с env**

PowerShell:
```powershell
$env:LLM_BACKEND="llamacpp"
$env:LLM_MODEL="mits-eval-kto"
$env:CORS_ORIGINS="http://localhost:3000,http://192.168.8.167:3000"
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```
(Запускать в фоне/отдельном окне — процесс долгоживущий.)

- [ ] **Step 2: Проверить health + бэкенд**

Run: `curl -s http://127.0.0.1:8000/api/v1/health`
Expected: JSON; в нём backend kind = `llamacpp` (или статус ready). Если показывает ollama — env не подхватился.

---

### Task 6: Запустить frontend на LAN

**Files:**
- Create: `frontend/.env.local`

- [ ] **Step 1: Прописать адрес backend для устройств**

`frontend/.env.local`:
```
NEXT_PUBLIC_API_URL=http://192.168.8.167:8000
```

- [ ] **Step 2: Подтвердить, как строится WS-URL**

Прочитать `frontend/src/hooks/useWebSocket.ts` — убедиться, что ws-URL выводится из `NEXT_PUBLIC_API_URL` (`http`→`ws`) и путь совпадает с роутом backend (`/ws/{id}` или `/api/v1/ws/{id}`). При расхождении — поправить вывод URL в хуке.

- [ ] **Step 3: Запустить dev-сервер на всех интерфейсах**

Run (в `frontend/`): `npm run dev -- -H 0.0.0.0 -p 3000`
Expected: `Ready ... http://0.0.0.0:3000`.

---

### Task 7: Проверить живой чат end-to-end (Playwright)

- [ ] **Step 1: Открыть фронт и отправить сообщение**

Через Playwright MCP: navigate `http://127.0.0.1:3000` → залогиниться/создать сессию (или открыть существующий чат-роут) → ввести «Помоги решить x²−5x+6=0» → отправить.

- [ ] **Step 2: Наблюдать стриминг и проверить контент**

Expected: токены приходят по WS; ответ — **сократический** (наводящие вопросы, без готового ответа), идёт стримингом. Сделать скриншот, визуально подтвердить.

- [ ] **Step 3: Проверить логи backend**

Expected: в логах `First token sent via WebSocket`, без `Streaming error`. Бэкенд использует llamacpp (запрос ушёл на :8081).

---

### Task 8: Доступ с другого устройства (LAN) + firewall

- [ ] **Step 1: Разрешить входящие на 3000/8000 (Private)**

PowerShell (elevated — через `! ` в сессии, если нет прав):
```powershell
New-NetFirewallRule -DisplayName "MITS demo 3000/8000" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 3000,8000 -Profile Private
```

- [ ] **Step 2: Открыть с телефона/ноутбука**

На устройстве в той же Wi-Fi: `http://192.168.8.167:3000` → отправить сообщение в чат → увидеть живой ответ.
Expected: интерфейс открывается, чат отвечает вживую через llama-server.

- [ ] **Step 3: Commit (если менялся useWebSocket / env-пример)**

```bash
git add frontend/src/hooks/useWebSocket.ts frontend/.env.local 2>$null
git commit -m "chore(frontend): LAN API URL + WS URL derivation for live demo"
```

---

## Self-Review

- **Покрытие спеки (Ф0+Ф1):** llama-server-путь (Task 1-5), запуск стека (4-6), живой чат (7), LAN (8) — ✅. Тема/рестайл (Ф2/Ф3) и guided-tools — намеренно в отдельных планах.
- **Плейсхолдеры:** код Task 2-3 полный; Task 4/6 содержат две точки сверки (аргументы llama-swap; вывод WS-URL) — это явные шаги-проверки, не заглушки.
- **Консистентность типов:** `generate_stream` отдаёт `("thinking"|"content", token)` — тот же контракт, что у `LLMClient` (см. `llm_client.py:481,490,495`), значит `process_message_stream` не требует правок.
- **Риск:** warmup в `initialize()` зовёт `generate("Привет", max_tokens=5)` — реализован в новом клиенте ✅. Guided-режим (`chat_with_tools`) в этом плане не используется (chat-режим зовёт только generate/generate_stream).
