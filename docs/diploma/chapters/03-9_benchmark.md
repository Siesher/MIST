Для оценки эффективности пайплайна дообучения я разработал инструментарий автоматизированного тестирования, состоящий из двух скриптов: сборки бенчмарка (`build_eval_benchmark.py`) и оценки моделей (`evaluate_stage.py`). С самого начала я закладывал в него воспроизводимость: все параметры запуска, версии моделей и случайные зёрна фиксирую в YAML-конфигурации, а результаты сохраняю в структурированных JSON-отчётах — что позволяет повторить любой эксперимент позднее.

## Сборка бенчмарка: build_eval_benchmark.py

Скрипт `training/scripts/build_eval_benchmark.py` агрегирует задачи из трёх источников в единый бенчмарк из **3678 задач** по 5 STEM-доменам:

| Источник | Задач | Домены | Формат |
|---|---|---|---|
| MGSM Russian [39] | 250 | Математика | Перевод GSM-8K на русский язык |
| ruMMLU STEM [38] | 3210 | Физика, химия, биология, информатика | Русскоязычный срез MMLU |
| Авторский набор | 218 | Все домены | Задачи 7–11 класс |

Для загрузки MGSM и ruMMLU из HuggingFace Hub используется метод `hf_hub_download()` с указанием `revision="refs/convert/parquet"`, что позволяет обойти устаревший механизм загрузочных скриптов. Авторский набор хранится в файле `training/data/custom_tasks.jsonl` в формате JSONL с полями `id`, `domain`, `difficulty`, `question`, `answer`, `verification_type`.

Каждая задача в итоговом бенчмарке содержит следующие поля:

```python
{
    "id": "math_mgsm_001",
    "domain": "math",           # math | physics | chemistry | biology | cs
    "difficulty": "medium",     # easy | medium | hard
    "source": "mgsm",
    "question": "Если ...",
    "answer": "42",
    "verification_type": "sympy" # sympy | chempy | regex_phys | exact
}
```

Бенчмарк стратифицирован по сложности (easy / medium / hard) для возможности анализа per-difficulty прироста. Распределение по сложности внутри каждого источника определяется либо исходной разметкой (ruMMLU), либо автоматической оценкой через вспомогательную LLM (MGSM и авторский набор).

## Оценка модели: evaluate_stage.py

Скрипт `training/scripts/evaluate_stage.py` реализует полный цикл inference + verification для одного чекпойнта. Архитектура скрипта предполагает параллельную обработку задач с настраиваемым числом воркеров (`--parallel`):

```python
def evaluate_stage(
    model_name: str,
    benchmark_path: str,
    output_dir: str,
    num_predict: int = 4096,   # 4096+ для thinking-моделей (важно!)
    temperature: float = 0.3,
    parallel: int = 3,
) -> EvaluationReport:
    tasks = load_benchmark(benchmark_path)
    results = []
    with ThreadPoolExecutor(max_workers=parallel) as executor:
        futures = [executor.submit(evaluate_task, task, model_name,
                                    num_predict, temperature)
                   for task in tasks]
        results = [f.result() for f in as_completed(futures)]
    return build_report(results)
```

Параметр `num_predict=4096` критичен для thinking-моделей: значение 1024 приводит к обрезанию thinking-блока до получения финального ответа, что искусственно снижает измеряемую точность (задача оценивается как неправильная при отсутствии явного ответа). Это ограничение задокументировано в `MEMORY.md`.

## Верификация ответов

Функция `verify_answer()` реализует многоуровневую проверку в зависимости от домена и типа верификации:

```python
def verify_answer(predicted: str, ground_truth: str,
                  verification_type: str) -> bool:
    extracted = extract_answer(predicted)  # regex по шаблонам ответа
    if verification_type == "sympy":
        return verify_sympy(extracted, ground_truth)
    elif verification_type == "chempy":
        return verify_chempy(extracted, ground_truth)
    elif verification_type == "regex_phys":
        return verify_physics(extracted, ground_truth, tolerance=0.05)
    else:
        return extracted.strip().lower() == ground_truth.strip().lower()
```

**SymPy-верификация** (математика): извлечённый ответ и эталон преобразуются в символьные выражения, после чего вычисляется `simplify(expr1 - expr2) == 0`. Это позволяет корректно сравнивать эквивалентные, но внешне различные формы — например, `(x+1)^2` и `x^2 + 2x + 1`.

**ChemPy-верификация** (химия): проверяется балансировка химических уравнений и стехиометрические соотношения. Реакции нормализуются через `chempy.Reaction.from_string()`, после чего сравниваются коэффициенты.

**Физическая верификация** (физика): числовые значения сравниваются с допуском $\pm 5\%$ относительно эталона, поддерживается вариативность единиц измерения через нормализацию (м/с² и m/s²).

**Exact match** (информатика, биология): нормализованное строковое сравнение после lower-case и удаления пунктуации.

## Структура отчётов

По завершении оценки формируется JSON-отчёт:

```json
{
  "model": "Siesher/mits-qwen3-9b-final",
  "timestamp": "2026-03-22T14:30:00",
  "overall_accuracy": 0.665,
  "per_domain": {
    "math":     {"accuracy": 0.882, "n_tasks": 1200, "truncated": 0.02},
    "physics":  {"accuracy": 0.843, "n_tasks": 800,  "truncated": 0.03},
    "cs":       {"accuracy": 0.586, "n_tasks": 600,  "truncated": 0.05},
    "chemistry":{"accuracy": 0.584, "n_tasks": 678,  "truncated": 0.04},
    "biology":  {"accuracy": 0.430, "n_tasks": 400,  "truncated": 0.06}
  },
  "answer_extraction_rate": 0.943,
  "truncation_rate": 0.038,
  "avg_thinking_tokens": 510
}
```

Поле `truncation_rate` отслеживает долю ответов, обрезанных по лимиту `num_predict`, — индикатор недостаточного бюджета генерации. Поле `answer_extraction_rate` показывает, в какой доле ответов удалось извлечь структурированный ответ — низкое значение указывает на проблемы с форматом генерации. Скрипт `training/scripts/compare_stages.py` автоматически агрегирует отчёты нескольких чекпойнтов в сводную таблицу прироста по стадиям, используемую в Главе 4.
