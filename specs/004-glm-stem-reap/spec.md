# Feature Specification: GLM-4.7-Flash STEM REAP Pruning

**Feature Branch**: `004-glm-stem-reap`
**Created**: 2026-02-01
**Status**: Draft
**Input**: User description: "Создать полностью готовый Colab notebook для REAP pruning модели GLM-4.7-Flash с использованием двуязычного STEM калибровочного датасета (1490 примеров). Цель: уменьшить модель на 25-35% с сохранением качества для STEM тьюторинга на русском и английском. Выход: GGUF для Ollama."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run REAP Pruning in Colab (Priority: P1)

Пользователь открывает notebook в Google Colab Pro+ (A100 40GB), запускает все ячейки последовательно и получает pruned модель GLM-4.7-Flash, оптимизированную для STEM-тьюторинга.

**Why this priority**: Это основная цель - создать работающий pipeline для уменьшения модели с сохранением качества на STEM-задачах.

**Independent Test**: Notebook запускается от начала до конца без ошибок, на выходе получается pruned модель.

**Acceptance Scenarios**:

1. **Given** пользователь в Colab с A100 40GB, **When** запускает все ячейки notebook, **Then** получает pruned модель без ошибок
2. **Given** pruned модель создана, **When** проверяется размер, **Then** модель на 25-35% меньше оригинала (48 экспертов из 64)
3. **Given** калибровочный датасет загружен, **When** REAP анализирует активации, **Then** используются все 1490 STEM примеров

---

### User Story 2 - Convert to GGUF for Local Use (Priority: P2)

После pruning пользователь конвертирует модель в GGUF формат и квантизирует до Q4_K_M для локального использования.

**Why this priority**: Конечная цель - запуск модели локально для MITS.

**Independent Test**: GGUF файл создаётся и может быть использован с llama.cpp или LMStudio.

**Acceptance Scenarios**:

1. **Given** pruned модель в HF формате, **When** запускается convert_hf_to_gguf.py, **Then** создаётся GGUF файл
2. **Given** GGUF FP16 создан, **When** квантизируется в Q4_K_M, **Then** размер уменьшается до ~10-12GB

---

### User Story 3 - Validate STEM Quality (Priority: P2)

Пользователь проверяет качество pruned модели на примерах из разных STEM-доменов.

**Why this priority**: Важно убедиться, что pruning не ухудшил качество на целевых задачах.

**Independent Test**: Модель генерирует осмысленные ответы на тестовые промпты из каждого домена.

**Acceptance Scenarios**:

1. **Given** pruned модель загружена, **When** отправляется математический промпт на русском, **Then** получается корректное решение
2. **Given** pruned модель загружена, **When** отправляется код-промпт на английском, **Then** генерируется рабочий код

---

### User Story 4 - Upload to HuggingFace (Priority: P3)

Пользователь загружает готовый GGUF на HuggingFace для скачивания на локальную машину.

**Why this priority**: Удобство доставки модели с Colab.

**Independent Test**: Файл доступен для скачивания с HuggingFace.

**Acceptance Scenarios**:

1. **Given** GGUF файл готов, **When** выполняется upload_file(), **Then** файл появляется в репозитории

---

### Edge Cases

- Что если GPU памяти не хватает? → Уменьшить samples_per_category или использовать offloading
- Что если REAP не находит модель? → Добавить конфигурацию в MODEL_ATTRS через патч
- Что если llama.cpp не поддерживает архитектуру? → Предоставить альтернативный путь

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Notebook MUST проверять наличие A100 GPU с ≥40GB памяти
- **FR-002**: Notebook MUST устанавливать все зависимости автоматически
- **FR-003**: Notebook MUST загружать GLM-4.7-Flash модель с HuggingFace
- **FR-004**: Notebook MUST загружать Siesher/mits-calibration-dataset (1490 примеров)
- **FR-005**: Notebook MUST добавлять поддержку Glm4MoeLiteForCausalLM в REAP
- **FR-006**: Notebook MUST выполнять REAP pruning с ~35% сокращением экспертов
- **FR-007**: Notebook MUST сохранять pruned модель в HuggingFace формате
- **FR-008**: Notebook MUST конвертировать модель в GGUF формат
- **FR-009**: Notebook MUST квантизировать GGUF до Q4_K_M
- **FR-010**: Notebook MUST включать валидацию на тестовых STEM примерах
- **FR-011**: Notebook MUST предоставлять опциональную загрузку на HuggingFace

### Key Entities

- **CalibrationDataset**: 1490 STEM примеров (math, code, physics, chemistry, biology, socratic)
- **OriginalModel**: GLM-4.7-Flash (30B params, 64 experts, 4 active)
- **PrunedModel**: GLM-4.7-Flash-STEM (~23B params, ~48 experts)
- **GGUFOutput**: Quantized GGUF (Q4_K_M, ~10-12GB)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Notebook выполняется полностью без ошибок на Colab Pro+ A100
- **SC-002**: Pruned модель содержит на 25-35% меньше экспертов (48 из 64)
- **SC-003**: GGUF файл создаётся размером 10-15GB (Q4_K_M)
- **SC-004**: Модель отвечает осмысленно на тестовые промпты каждого STEM домена
- **SC-005**: Время выполнения не превышает 3 часов

## Assumptions

- Пользователь имеет Colab Pro+ с A100 40GB
- Пользователь авторизован в HuggingFace Hub
- Датасет Siesher/mits-calibration-dataset публичен
- llama.cpp поддерживает GLM архитектуру

## Known Limitations

- REAP pruned модели могут иметь проблемы совместимости с некоторыми inference движками
- Рекомендуется использовать LMStudio или vLLM для inference
- Q4_K_M квантизация даёт минимальную потерю качества
