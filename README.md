<div align="center">

<!-- Banner -->
<img src="figures/mits_banner.svg" alt="MITS Banner" width="100%" />

# 🔮 MITS — Math Intelligent Tutoring System

*«Магия — это не талант. Это терпение, практика и правильный наставник.»*

**Интеллектуальная система обучения STEM-дисциплинам с сократическим методом,
мультиагентной архитектурой и RL-обученной языковой моделью**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-818CF8?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Qwen3.5-9B](https://img.shields.io/badge/Qwen3.5--9B-Fine--tuned-C4B5FD?style=for-the-badge&logo=huggingface&logoColor=white)](https://huggingface.co/Siesher)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-000000?style=for-the-badge&logo=next.js&logoColor=white)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-C4B5FD?style=for-the-badge)](LICENSE)

[Демо](#быстрый-старт) · [Архитектура](#архитектура) · [Training Pipeline](#training-pipeline) · [Evaluation](#evaluation) · [Документация](docs/)

</div>

---

## О проекте

MITS — система, которая учит решать, а не даёт ответы. Как наставник, собравший тысячи «заклинаний» — методов, задач, подходов — она ведёт студента через сократический диалог: задаёт вопросы, даёт подсказки, проверяет решения символьно.

<table>
<tr>
<td width="50%">

**Пять доменов**
- 📐 Математика (алгебра, анализ, геометрия)
- ⚛️ Физика (механика, термодинамика, электричество)
- 🧪 Химия (неорганика, органика, аналитика)
- 🧬 Биология (молекулярная, генетика, экология)
- 💻 Информатика (алгоритмы, структуры данных)

</td>
<td width="50%">

**Ключевые особенности**
- Сократический метод — никогда не даёт готовых ответов
- Мультиагентная архитектура (Profiler → Planner → Tutor → Verifier)
- Символьная верификация (SymPy / ChemPy)
- Knowledge Tracing (BKT + DKT) — 40+ навыков
- Fine-tuned Qwen3.5-9B через 3-стадийный RL
- OCR рукописных решений (Qwen2.5-VL)

</td>
</tr>
</table>

---

## Архитектура

```
                    ┌─────────────────────────────────────────────┐
                    │         Next.js 14 + TypeScript              │
                    │    Tailwind · shadcn/ui · Zustand · WS       │
                    └──────────────────┬──────────────────────────┘
                                       │ REST + WebSocket (streaming)
                    ┌──────────────────▼──────────────────────────┐
                    │              FastAPI Backend                  │
                    │     JWT Auth · Sessions · Analytics · PDF     │
                    └──────────────────┬──────────────────────────┘
                                       │
    ┌──────────────────────────────────▼──────────────────────────────────┐
    │                     Multi-Agent Orchestrator                        │
    │                                                                     │
    │   ┌──────────┐    ┌──────────┐    ┌──────────────┐    ┌──────────┐ │
    │   │ Profiler  │ →  │ Planner  │ →  │    Tutor     │ →  │ Verifier │ │
    │   │ (уровень  │    │ (стратег │    │ (сократичес- │    │ (SymPy/  │ │
    │   │  ученика) │    │  урока)  │    │ кий диалог)  │    │ ChemPy)  │ │
    │   └──────────┘    └──────────┘    └──────────────┘    └──────────┘ │
    │                                                                     │
    │   ┌──────────┐    ┌──────────┐    ┌──────────────┐                 │
    │   │   RAG    │    │ Knowledge│    │  Few-Shot     │                 │
    │   │(ChromaDB)│    │ Tracing  │    │  Bank (SKI)   │                 │
    │   └──────────┘    └──────────┘    └──────────────┘                 │
    └──────────────────────────────┬──────────────────────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────────┐
                    │     Ollama · Qwen3.5-9B (fine-tuned)    │
                    │        Token-by-token streaming          │
                    └─────────────────────────────────────────┘
```

**Три режима работы:**

| Режим | Описание |
|:------|:---------|
| 💬 **Chat** | Свободный диалог с STEM-репетитором |
| 📚 **Guided Learning** | Полный пайплайн агентов: Profiler → Planner → Tutor → Verifier |
| 🎯 **Task Generator** | Генерация задач по теме, сложности и навыку |

---

## Training Pipeline

Модель Qwen3.5-9B дообучается 3-стадийным RL-пайплайном на Google Colab A100 80GB (bf16, без квантизации при обучении):

```
    Qwen3.5-9B-Instruct
            │
            ▼
    ╔═══════════════════╗
    ║   Stage 1: GSPO   ║  Group Sequence Policy Optimization
    ║                   ║  Triple GDPO reward: correctness (0.7)
    ║   curriculum RL   ║  + format (0.15) + Socratic (0.15)
    ╚════════╤══════════╝
             ▼
    ╔═══════════════════╗
    ║   Stage 2: KTO    ║  Kahneman-Tversky Optimization
    ║                   ║  Unpaired preferences from
    ║ Socratic align.   ║  dialogues + preference pairs
    ╚════════╤══════════╝
             ▼
    ╔═══════════════════╗
    ║   Stage 3: DPO    ║  Direct Preference Optimization
    ║                   ║  Final format and style
    ║   format polish   ║  alignment polish
    ╚════════╤══════════╝
             ▼
       Fine-tuned model
       (Ollama / GGUF)
```

| Stage | Notebook | HF Repo | Technique |
|:------|:---------|:--------|:----------|
| GSPO | `grpo_qwen3.5_9b.ipynb` | [mits-qwen3-9b-gspo](https://huggingface.co/Siesher/mits-qwen3-9b-gspo) | Triple GDPO reward (correctness + format + Socratic) |
| KTO | `kto_qwen3.5_9b.ipynb` | [mits-qwen3-9b-kto](https://huggingface.co/Siesher/mits-qwen3-9b-kto) | Kahneman-Tversky Optimization ([arXiv 2402.01306](https://arxiv.org/abs/2402.01306)) |
| DPO | `dpo_polish_qwen3.5_9b.ipynb` | [mits-qwen3-9b-final](https://huggingface.co/Siesher/mits-qwen3-9b-final) | Direct Preference Optimization |

**Данные:**
- `data/training/dialogs.jsonl` — 3 875 сократических диалогов
- `training/data/preference_pairs.jsonl` — 12 597 пар предпочтений
- Evaluation benchmark — 3 678 задач (MGSM Russian + ruMMLU STEM + custom)

---

## Evaluation

Бенчмарк из 3 678 задач по 5 доменам × 3 уровням сложности.
Стратифицированная выборка 200 задач для быстрых per-stage оценок.

```bash
# Запуск оценки стадии
python training/scripts/evaluate_stage.py run --stage gspo --model mits-tutor-9b-gspo --workers 4

# Сравнение стадий
python training/scripts/evaluate_stage.py compare --reports evaluation/reports/
```

Отчёты сохраняются в `evaluation/reports/` как JSON с разбивкой по домену и сложности.

---

## Быстрый старт

### Требования
- Python 3.11+ · Node.js 18+ · [Ollama](https://ollama.ai)

### Установка

```bash
git clone https://github.com/Siesher/MITS.git
cd MITS

# Backend
python -m venv venv
source venv/bin/activate        # Linux / Mac
# .\venv\Scripts\Activate.ps1  # Windows
pip install -r requirements.txt

# Frontend
cd frontend && npm install && cd ..
```

### Модель

```bash
ollama serve
ollama pull qwen3.5:9b                         # базовая модель
# ollama create mits-tutor -f training/Modelfile  # fine-tuned версия
```

### Запуск

```bash
# Backend (порт 8000)
cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (порт 3000)
cd frontend && npm run dev
```

→ **http://localhost:3000**

---

## Структура проекта

```
MITS/
├── frontend/                    # Next.js 14 + TypeScript
│   ├── src/app/                 #   Pages (auth, chat, dashboard)
│   ├── src/components/          #   React-компоненты
│   ├── src/hooks/               #   useChat, useWebSocket
│   └── src/store/               #   Zustand (chatStore)
│
├── backend/                     # FastAPI
│   ├── app/api/v1/              #   REST + WebSocket endpoints
│   ├── app/services/            #   Orchestrator, analytics, export
│   └── app/models/              #   SQLAlchemy ORM
│
├── src/                         # Core Python — агенты и модели
│   ├── agents/                  #   Profiler, Planner, Tutor, Verifier и др.
│   ├── models/                  #   LLM client, KT, detectors, prompts
│   ├── knowledge/               #   RAG, SKI, few-shot bank
│   ├── tools/                   #   SKI tool adapters
│   └── execution/               #   Code sandbox + AST analyzer
│
├── training/                    # ML training pipeline
│   ├── scripts/                 #   evaluate_stage, stem_rewards, export
│   └── data/                    #   Datasets, benchmark
│
├── notebooks/                   # Colab training notebooks
│   ├── grpo_qwen3.5_9b.ipynb    #   Stage 1: GSPO
│   ├── kto_qwen3.5_9b.ipynb     #   Stage 2: KTO
│   ├── dpo_polish_qwen3.5_9b.ipynb  # Stage 3: DPO
│   └── archive/                 #   Legacy (Qwen3-4B)
│
├── evaluation/                  # Evaluation reports + benchmarks
├── data/                        # Knowledge bases (RAG, skill graph)
├── docs/                        # Documentation
├── specs/                       # Feature specs (001–016)
└── tests/                       # Unit & integration tests
```

---

## Технологии

| Layer | Stack |
|:------|:------|
| **Frontend** | Next.js 14 · TypeScript · Tailwind CSS · shadcn/ui · Zustand |
| **Backend** | FastAPI · SQLAlchemy · SQLite · Alembic · JWT (PyJWT + Argon2) |
| **LLM** | Ollama · Qwen3.5-9B (fine-tuned) · WebSocket streaming |
| **ML Training** | Unsloth · TRL (GRPOTrainer, KTOTrainer, DPOTrainer) · PEFT · Transformers |
| **Evaluation** | SymPy · ChemPy · 3 678-problem benchmark |
| **Knowledge** | ChromaDB · sentence-transformers · BKT · DKT |
| **Deploy** | Docker Compose |

---

## Дорожная карта

<details>
<summary><b>Курсовая работа (2024)</b></summary>

- [x] Code Executor с песочницей
- [x] 50+ алгоритмических задач с автопроверкой
- [x] AST-анализатор кода
- [x] Gradio UI

</details>

<details>
<summary><b>Дипломная работа (2025–2026)</b> — текущий этап</summary>

- [x] Next.js 14 + FastAPI миграция
- [x] JWT аутентификация + session persistence
- [x] Три режима чата (chat, guided learning, task generator)
- [x] DKT knowledge tracing
- [x] RuBERT эмоциональный детектор
- [x] OCR рукописных решений (Qwen2.5-VL)
- [x] A/B experiment framework
- [x] Analytics dashboard + PDF экспорт
- [x] Docker Compose deployment
- [x] Миграция на Qwen3.5-9B (bf16, A100 80GB)
- [x] 3-стадийный RL pipeline (GSPO → KTO → DPO)
- [x] Evaluation benchmark (3 678 задач)
- [x] Structured Knowledge Index (SKI) + tool calling
- [ ] Textbook grounding (method cards, problem templates)
- [ ] Per-stage evaluation → hyperparameter refinement

</details>

---

## Научная основа

<details>
<summary>Ключевые статьи и методы</summary>

| Метод | Paper | Применение в MITS |
|:------|:------|:-------------------|
| GRPO | [DeepSeek-Math](https://arxiv.org/abs/2402.03300) | Основа GSPO — group-relative advantage estimation |
| GDPO | [arXiv 2601.05242](https://arxiv.org/abs/2601.05242) | Decoupled multi-objective rewards |
| KTO | [arXiv 2402.01306](https://arxiv.org/abs/2402.01306) | Kahneman-Tversky loss для Socratic alignment |
| DPO | [arXiv 2305.18290](https://arxiv.org/abs/2305.18290) | Format polish без reward model |
| BKT | Corbett & Anderson, 1994 | Bayesian Knowledge Tracing |
| DKT | [arXiv 1506.05908](https://arxiv.org/abs/1506.05908) | Deep Knowledge Tracing |
| Socratic Method | [Chi et al., 2001](https://doi.org/10.1207/s15516709cog2505_1) | Scaffolding, hinting, never telling |

</details>

---

## Лицензия

[MIT License](LICENSE) — свободно используйте, форкайте, дорабатывайте.

---

<div align="center">

*Каждый решённый пример — это заклинание, добавленное в гримуар.*
*Каждая ошибка — шаг к мастерству.*

**Сухацкий Максим** · МГТУ им. Н.Э. Баумана (Калужский филиал) · 2024–2026

[![HuggingFace](https://img.shields.io/badge/🤗_HuggingFace-Siesher-C4B5FD?style=flat-square)](https://huggingface.co/Siesher)
[![GitHub](https://img.shields.io/badge/GitHub-Siesher-818CF8?style=flat-square&logo=github)](https://github.com/Siesher)

</div>
