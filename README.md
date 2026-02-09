# 🐝 MITS — Математическая Интеллектуальная Система Обучения

> Intelligent Tutoring System для математики и программирования с сократическим методом обучения

## ✨ Возможности

### 📐 Математика
- 13+ предгенерированных задач (производные, интегралы, пределы, уравнения)
- Адаптивный выбор задач на основе Knowledge Tracing (BKT)
- Пошаговые подсказки и решения
- LaTeX рендеринг формул

### 💻 Программирование
- **50+ алгоритмических задач** (Easy/Medium/Hard)
- Категории: массивы, строки, сортировка, поиск, ДП, графы и др.
- **Автоматическая проверка** на скрытых тестах
- **Анализ кода:** сложность, антипаттерны, рекомендации
- Безопасная песочница для выполнения

### 🤖 AI Репетитор
- Модель: Qwen3-30B-A3B-Instruct-2507 (MoE, 3B активных параметров)
- Сократический метод — направляет через вопросы
- Не даёт готовых ответов!

### 📊 Отслеживание прогресса
- Knowledge Tracing с Bayesian Knowledge Tracing
- 40+ навыков с иерархией prerequisites
- Персональный профиль знаний
- Метрики: Success@10, Telling@10

## 🚀 Быстрый старт

### 1. Установка

```bash
# Клонирование
git clone <repository>
cd MITS

# Виртуальное окружение
python -m venv venv
.\venv\Scripts\Activate.ps1  # Windows
source venv/bin/activate     # Linux/Mac

# Зависимости
pip install -r requirements.txt
```

### 2. Установка модели GLM-STEM

```bash
# Установите Ollama: https://ollama.ai
ollama serve

# Установите оптимизированную STEM модель (рекомендуется)
./scripts/install_glm_stem.sh          # Linux/macOS
.\scripts\install_glm_stem.ps1         # Windows

# ИЛИ вручную:
# ollama pull qwen3:30b-a3b-instruct-2507
```

**GLM-STEM** — REAP-pruned модель (42 эксперта вместо 64), оптимизированная для STEM задач:
- ~33% меньше VRAM (~5.5GB vs ~7.5GB)
- Сохраняет качество на математике и программировании
- Скачивается с [HuggingFace](https://huggingface.co/Siesher/glm-stem-42exp-gguf)

### 3. Запуск MITS

```bash
# Единый интерфейс (рекомендуется)
python run.py

# Только программирование
python run.py coding

# Только математика  
python run.py math

# Тесты
python run.py test
```

Откройте: **http://localhost:7860**

## 📁 Структура проекта

```
MITS/
├── interface/              # Интерфейсы
│   ├── unified_app.py      # Единый интерфейс ⭐
│   ├── coding_app.py       # Программирование
│   ├── app_v2.py           # Математика v2
│   └── universal_app.py    # Свободный диалог
│
├── src/
│   ├── execution/          # Выполнение кода
│   │   ├── code_executor.py    # Песочница
│   │   └── code_analyzer.py    # AST анализ
│   │
│   ├── data/               # Банки задач
│   │   ├── algo_task_bank.py       # Алгоритмы
│   │   ├── algo_tasks_collection.py # 30 задач
│   │   ├── algo_tasks_extra.py     # +20 задач
│   │   └── task_bank.py            # Математика
│   │
│   ├── models/             # LLM и Knowledge Tracing
│   │   ├── llm_client.py
│   │   ├── knowledge_tracing.py
│   │   └── prompts.py
│   │
│   └── utils/              # Утилиты
│       └── session_logger.py
│
├── tests/
│   └── test_coding.py      # Тесты системы
│
├── data/                   # Данные
│   ├── students/           # Профили студентов
│   ├── logs/               # Логи сессий
│   └── algo_tasks.json     # Банк задач
│
└── run.py                  # Точка входа
```

## 🧪 Примеры задач

### Easy
- Two Sum — найти два числа с заданной суммой
- Palindrome — проверка на палиндром
- FizzBuzz — классика
- Fibonacci — числа Фибоначчи

### Medium
- Binary Search — бинарный поиск
- Valid Parentheses — правильная скобочная последовательность
- Maximum Subarray — алгоритм Кадане
- Merge Intervals — слияние интервалов

### Hard
- LCS — наибольшая общая подпоследовательность
- Edit Distance — редакционное расстояние
- Knapsack — задача о рюкзаке
- Number of Islands — поиск в графе

## 📊 Метрики

| Метрика | Цель | Описание |
|---------|------|----------|
| Success@10 | >60% | Задач решённых за ≤10 попыток |
| Telling@10 | <15% | Сессий где показали ответ |
| Hint Efficiency | <2.5 | Среднее подсказок до успеха |
| KT AUC-ROC | >0.75 | Точность предсказания успеха |

## 🛠 Технологии

- **Backend:** Python 3.11+ / FastAPI + WebSocket
- **Frontend:** Next.js 14 + Tailwind CSS + TypeScript
- **LLM:** Ollama + GLM-STEM-42exp (REAP-pruned, ~5.5GB VRAM)
- **Fallback:** GLM-4.7-Flash (64 experts, ~7.5GB VRAM)
- **Auth:** JWT (PyJWT + Argon2)
- **DB:** SQLite + SQLAlchemy (async)
- **Math:** SymPy, KaTeX
- **ML:** PyTorch, Transformers, Unsloth (QLoRA)
- **Deploy:** Docker Compose
- **Legacy UI:** Gradio 4.x

## 📈 Roadmap

### Курсовая (сделано)
- [x] Code Executor с песочницей
- [x] 50+ алгоритмических задач
- [x] Автоматическая проверка на тестах
- [x] Code Analyzer (AST)
- [x] Единый интерфейс

### Диплом (сделано)
- [x] Next.js + FastAPI frontend migration
- [x] JWT authentication with user isolation
- [x] Session persistence (SQLite)
- [x] Three chat modes (chat, guided learning, task generator)
- [x] QLoRA fine-tuning pipeline (Colab A100)
- [x] DKT knowledge tracing (pre-trained on ASSISTments)
- [x] RuBERT emotion detection (5-class affective states)
- [x] Evaluation pipeline with benchmarks
- [x] Handwritten solution OCR (Qwen2.5-VL)
- [x] A/B experiment framework
- [x] Analytics dashboard
- [x] PDF progress export
- [x] Docker Compose deployment

## 📄 Лицензия

MIT License

---

**Автор:** Maksim  
**Университет:** Курсовая/Дипломная работа  
**Год:** 2024-2025
