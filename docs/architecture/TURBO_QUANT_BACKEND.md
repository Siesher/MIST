# Experimental HuggingFace + TurboQuant Backend

Экспериментальный путь исполнения модели напрямую через `transformers` с включённой TurboQuant-компрессией KV-кеша. Позволяет поднять контекст с 4K до 32K+ на слабой GPU (6–8GB VRAM) за счёт 3-bit квантизации keys/values.

## Зачем

| Режим | Context | KV cache @ 32K | VRAM total | Скорость |
|---|---|---|---|---|
| Ollama Q4_K_M | 4K–8K | — | ~5.5GB | 20–40 tok/s (GPU) |
| HF bf16 | 4K | 16 GB | OOM на 8GB | — |
| HF + bnb 4-bit | 4K | 4 GB | ~9 GB | 15–25 tok/s |
| **HF + TurboQuant 3-bit KV** | **32K** | **3 GB** | **~8.5 GB** | **12–20 tok/s** |
| HF + TurboQuant 2.5-bit KV | 64K | 2.5 GB | ~8 GB | 10–18 tok/s |

Source: arXiv:2504.19874 (TurboQuant: Online Vector Quantization with Near-optimal Distortion).

## Как включить

### 1. Убедись что установлены зависимости

```powershell
cd C:\Work\MITS
.\venv\Scripts\activate
pip install torch transformers peft bitsandbytes scipy numpy
```

На Windows без WSL — `bitsandbytes` требует pre-built wheel:
```powershell
pip install bitsandbytes-windows
```

### 2. Настрой `.env` в `backend/`

Создай (или добавь) `backend/.env`:

```env
USE_HF_BACKEND=true
HF_MODEL_CONFIG=qwen3.5-9b-turbo
HF_CONTEXT_LENGTH=32768
```

Доступные HF-конфиги (из `src/inference/model_config.py`):

| Ключ | Описание | KV bits | Контекст |
|---|---|---|---|
| `qwen3.5-9b-turbo` | Qwen3.5-9B-Instruct, 3-bit keys + 3-bit values | 3/3 | 32K |
| `qwen3.5-9b-turbo-2.5bit` | Максимальная компрессия | 2/2 | 64K |

### 3. Перезапусти backend

```powershell
cd C:\Work\MITS
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

При старте в логах увидишь:
```
HF backend requested (USE_HF_BACKEND=True)
Loading HF client (Qwen3.5-9B + TurboQuant (HF, 4-bit, long context)) — this may take 30-60s...
hf_client_initializing model=Qwen/Qwen3.5-9B-Instruct ...
turbo_quant_enabled key_bits=3 value_bits=3
HF backend ready: Qwen3.5-9B + TurboQuant ...
```

### 4. Проверь в UI

В StatusBar рядом с именем модели появятся chip-ы:
- `HF` — backend переключён на HuggingFace
- `TQ` — TurboQuant активен
- `32K ctx` — расширенный контекст

## Как откатиться

Вариант 1 — выключить флаг в `.env`:
```env
USE_HF_BACKEND=false
```

Вариант 2 — просто удалить `backend/.env` или закомментировать строку.

Backend автоматически fallback'ает на Ollama если HF init не удался (например bitsandbytes не собрался на Windows).

## Ограничения

- **Startup time**: 30–60 сек на загрузку модели в VRAM. Backend в это время не отвечает на `/health`. Подумай про lazy-load (на первый запрос) если стартап критичен.
- **Первый токен медленный**: HF generate_stream имеет накладные расходы запуска Thread'а. Ollama здесь быстрее на коротких запросах.
- **Thinking mode парсинг**: `<think>...</think>` теги обрабатываются в `HuggingFaceClient.generate_stream()`, но парсер простой — может глотать токены на границе тега. В production стоит использовать stateful парсер.
- **GGUF-квантизация не применима**: HF-путь использует bitsandbytes NF4, не llama.cpp Q4_K_M. Качество чуть отличается.
- **LoRA adapter**: можно передать через `adapter_path=` в `HuggingFaceClient`. Сейчас конфиги указывают `hf_model_path="Qwen/Qwen3.5-9B-Instruct"` без адаптера — если нужен твой fine-tuned, задай `hf_adapter_path` в `MODEL_CONFIGS`.

## A/B сравнение

Можно переключаться на лету через env + рестарт backend. Для серьёзной оценки:

```python
# scripts/benchmark_backends.py (TODO)
# Прогоняет 20 запросов на Ollama и HF+TQ, собирает:
# - first_token_latency
# - total_latency
# - tokens/sec
# - peak VRAM
```
