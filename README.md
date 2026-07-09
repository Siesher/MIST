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

[Демо](#быстрый-старт) · [Архитектура](#архитектура) · [Training Pipeline](#training-pipeline) · [Evaluation](#evaluation) · [Документация](docs/INDEX.md)

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
- OCR рукописных решений (Qwen3.5 native vision через llama-swap)

</td>
</tr>
</table>

---

## ✨ Ключевые фичи 2026

<div align="center">

<img src="figures/readme/feature_timeline.png" alt="Feature Timeline" width="85%" />

</div>

| Feature | Что делает | Ключевая метрика | Spec |
|:---|:---|:---|:---|
| **016 Knowledge Forge** | Живой граф знаний: 83 узла × 88 рёбер, 6 типов узлов × 10 типов рёбер, self-completion из сессий | Path validity 100% · Frontier violation 0% | [specs/016](specs/016-knowledge-forge/) |
| **017 ToM-Tutor** | Theory-of-Mind агент: моделирует пробелы и заблуждения студента, re-rank навигатора | Root-hit 70% → **95%** · 0 регрессий на 20 сценариях | [specs/017](specs/017-tom-tutor/) |
| **018 PathSlime** | Lévy-Gaussian SMA: k разных траекторий обучения, bio-inspired diversity | 3 diverse paths (k=3, α=1.5) | [specs/018](specs/018-path-slime/) |

---

## Архитектура

<div align="center">

<img src="figures/diploma/courseware_fig_2_architecture.png" alt="MITS Architecture" width="90%" />

</div>

<details>
<summary>ASCII-fallback диаграмма архитектуры</summary>

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
                    │  llama-server/llama-swap · Qwen3.5-9B   │
                    │     (GGUF Q4_K_M) · token streaming     │
                    └─────────────────────────────────────────┘
```

</details>

**Три режима работы:**

| Режим | Описание |
|:------|:---------|
| 💬 **Chat** | Свободный диалог с STEM-репетитором |
| 📚 **Guided Learning** | Полный пайплайн агентов: Profiler → Planner → Tutor → Verifier |
| 🎯 **Task Generator** | Генерация задач по теме, сложности и навыку |

---

## Training Pipeline

Модель Qwen3.5-9B дообучается 3-стадийным RL-пайплайном на RTX PRO 6000 Blackwell 96GB (bf16, без квантизации при обучении):

```
    Qwen3.5-9B-Instruct
            │
            ▼
    ╔═══════════════════╗
    ║   Stage 1: GSPO   ║  Group Sequence Policy Optimization
    ║                   ║  Triple GDPO reward: correctness (0.40)
    ║   curriculum RL   ║  + format (0.15) + Socratic (0.45)
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
       (GGUF Q4_K_M · llama-swap)
```

| Stage | Notebook | HF Repo | Technique |
|:------|:---------|:--------|:----------|
| GSPO | `grpo_qwen3.5_9b.ipynb` | [mits-qwen3-9b-gspo](https://huggingface.co/Siesher/mits-qwen3-9b-gspo) | Triple GDPO reward: correctness (0.40) + format (0.15) + Socratic (0.45) |
| KTO | `kto_qwen3.5_9b.ipynb` | [mits-qwen3-9b-kto](https://huggingface.co/Siesher/mits-qwen3-9b-kto) | Kahneman-Tversky Optimization ([arXiv 2402.01306](https://arxiv.org/abs/2402.01306)) |
| DPO | `dpo_polish_qwen3.5_9b.ipynb` | [mits-qwen3-9b-final](https://huggingface.co/Siesher/mits-qwen3-9b-final) | Direct Preference Optimization |

**Данные:**
- `data/training/dialogs.jsonl` — 3 875 сократических диалогов
- `training/data/preference_pairs.jsonl` — 12 597 пар предпочтений
- Evaluation benchmark — 3 678 задач (MGSM Russian + ruMMLU STEM + custom)

---

## 📊 Результаты обучения

<div align="center">

<img src="figures/readme/domain_heatmap.png" alt="Per-domain accuracy" width="75%" />

</div>

**Честная re-оценка (Phase 0a, 2026-05-18)** — production-aligned стек:
llama-server Q4_K_M, self-consistency voting, n=209 задач.

| Stage | Overall | Δ vs base |
|:------|:-------:|:---------:|
| **base** | **69.4%** | — |
| **GSPO** | **70.3%** | +0.9 pp |
| **KTO** | **69.9%** | +0.5 pp |

**Per-domain (n=209):**

| Domain | Base | GSPO | KTO | Δ GSPO |
|:---|:---:|:---:|:---:|:---:|
| Math | 88.4% | 90.7% | 90.7% | +2.3 pp |
| Physics | 56.8% | 65.9% | 65.9% | **+9.1 pp** |
| Chemistry | 75.6% | 66.7% | 73.3% | -8.9 pp |
| Biology | 68.4% | 68.4% | 63.2% | 0.0 pp |
| CS | 56.4% | 59.0% | 53.8% | +2.6 pp |
| **Overall** | **69.4%** | **70.3%** | **69.9%** | **+1.0 pp** |

> **Ключевые выводы:** GSPO даёт значительный прирост на физике (+9.1 pp) и математике (+2.3 pp).
> Chemistry alignment tax (-8.9 pp) — известный эффект несовпадения reward structure с символьной верификацией.
> Сложные задачи регрессируют на всех стадиях — типичный RL mode collapse.
> Источник: `docs/diploma/phase0a_results.md`.

**Colab BF16 eval ladder** (одиночный прогон, без self-consistency):
base 55.1% → GSPO 63.5% → KTO 64.8% → DPO 66.5% (+11.4 pp накопленный прирост).
Gap объясняется inference-оптимизациями production-стека (+14.3 pp к baseline).

### 📈 ToM-Tutor A/B evaluation

| Метрика | Baseline | ToM | Delta |
|:---|:---:|:---:|:---:|
| Root-hit rate | 70.0% | **95.0%** | **+25.0%** |
| Any-hit rate | 100.0% | 100.0% | ±0 |
| Misconception accuracy | — | 90.0% | — |
| Regressed scenarios | — | 0 / 20 | — |
| Avg confidence | — | 0.89 | — |

*20 сценариев в 4 категориях (explicit_misconception, confused, open_question,
confident_wrong). Latency p50 11.5 s, p95 147 s — узкое место.
Источник: `evaluation/reports/tom_ab_2026-04-18.md`.*

### 📉 Knowledge Forge baseline

| Метрика | Value |
|:---|:---:|
| Gap Diagnosis (root-hit) | 60.0% (5 сценариев) |
| Gap Diagnosis (any-hit) | 100.0% |
| Frontier Violation Rate | 0.0% (lower = better) |
| Path Validity (invalid-pair rate) | 0.0% (7 пар) |
| Graph growth | 83 → 83 узлов, 88 → 88 рёбер (1 rejected) |

*Источник: `evaluation/reports/baseline_2026-04-18.md`.*

---

## Evaluation

Бенчмарк из 3 678 задач по 5 доменам × 3 уровням сложности.
Стратифицированная выборка 200 задач для быстрых per-stage оценок.

```bash
# Запуск оценки стадии
python training/scripts/evaluate_stage.py evaluate --mode local --stage gspo --model mits-tutor-9b-gspo --workers 4

# Сравнение стадий
python training/scripts/evaluate_stage.py compare --reports-dir evaluation/reports
```

Отчёты сохраняются в `evaluation/reports/` как JSON с разбивкой по домену и сложности.

---

## Быстрый старт

### Требования
- Python 3.11+ · Node.js 18+ · [llama.cpp / llama-server](https://github.com/ggerganov/llama.cpp) (или [llama-swap](https://github.com/mostlygeek/llama-swap))
- Ollama — опциональный fallback (установи `LLM_BACKEND=ollama` в `.env`)

### Установка

```bash
git clone https://github.com/Siesher/MITS.git
cd MITS

# Backend
python -m venv venv
source venv/bin/activate        # Linux / Mac
# .\venv\Scripts\Activate.ps1  # Windows
pip install -r requirements.txt
pip install -r backend/requirements.txt

# Frontend
cd frontend && npm install && cd ..
```

### Модель

По умолчанию используется llama-server / llama-swap на `http://127.0.0.1:8090/v1`
(GGUF Q4_K_M, `LLM_BACKEND=llamacpp` в `backend/.env`).

```bash
# Запусти llama-swap или llama-server с нужной GGUF-моделью на порту 8090
# Подробнее: docs/architecture/ и scripts/ollama/

# Опциональный Ollama-fallback:
# Установи LLM_BACKEND=ollama в backend/.env, затем:
# ollama serve && ollama pull qwen3.5:9b
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
│   ├── agents/                  #   Profiler, Planner, Tutor, Verifier
│   ├── models/                  #   LLM client, KT, detectors, prompts
│   ├── knowledge/               #   RAG, SKI, few-shot bank
│   ├── tools/                   #   SKI tool adapters
│   └── execution/               #   Code sandbox + AST analyzer
│
├── training/                    # ML training pipeline
│   ├── scripts/                 #   evaluate_stage, stem_rewards, export
│   ├── data/                    #   Datasets, benchmark
│   └── Modelfile*               #   Ollama templates (9b GSPO/KTO)
│
├── notebooks/                   # Colab training notebooks
│   ├── grpo_qwen3.5_9b.ipynb    #   Stage 1: GSPO
│   ├── kto_qwen3.5_9b.ipynb     #   Stage 2: KTO
│   ├── dpo_polish_qwen3.5_9b.ipynb  # Stage 3: DPO
│   └── archive/                 #   Legacy (Qwen3-4B, GLM)
│
├── evaluation/                  # Reports + benchmarks
├── data/                        # Knowledge bases (forge.json, RAG, skills)
│
├── docs/
│   ├── diploma/                 #   НИР 2026 + Курсовой 2026 (+ PDF exports)
│   ├── architecture/            #   ARCHITECTURE, MODEL_SELECTION, ...
│   ├── training/                #   TRAINING_PIPELINE, GSPO_TECHNIQUES
│   ├── guides/                  #   quickstart, PROJECT_STATUS
│   └── archive/                 #   pre-2026, nir-drafts
│
├── scripts/
│   ├── db/                      #   init_db, migrate_to_forge
│   ├── knowledge/               #   grow_graph, ingest_pdf, embeddings
│   ├── ollama/                  #   TurboQuant + Ollama automation
│   ├── design/                  #   design handoff, social preview
│   └── diploma/                 #   one-shot diploma generators (already ran)
│
├── figures/
│   ├── diploma/                 #   Figures for НИР + Курсовой
│   └── readme/                  #   feature_timeline, domain_heatmap
│
├── specs/                       # 001–019 feature specs
└── tests/                       # Unit & integration
```

---

## Технологии

| Layer | Stack |
|:------|:------|
| **Frontend** | Next.js 14 · TypeScript · Tailwind CSS · shadcn/ui · Zustand |
| **Backend** | FastAPI · SQLAlchemy · SQLite · Alembic · JWT (PyJWT + Argon2) |
| **LLM** | llama-server/llama-swap · Qwen3.5-9B (GGUF Q4_K_M) · WebSocket streaming · Ollama (legacy fallback) |
| **ML Training** | Unsloth · TRL (GRPOTrainer, KTOTrainer, DPOTrainer) · PEFT · Transformers |
| **Evaluation** | SymPy · ChemPy · 3 678-problem benchmark |
| **Knowledge** | ChromaDB · sentence-transformers · BKT · DKT |
| **Deploy** | Docker Compose |

---

## ❓ FAQ / Troubleshooting

<details>
<summary><b>Модель долго грузится / отвечает.</b></summary>

Используй профили из `src/resource_profiles.py` (`lite` / `standard` / `max`) —
они подбирают `num_ctx` и `num_predict` под железо. TurboQuant KV compression
ускоряет inference в 1.7–2× на RTX 4090. Подробнее:
[docs/architecture/RESOURCE_PROFILES.md](docs/architecture/RESOURCE_PROFILES.md).

</details>

<details>
<summary><b>/health endpoint таймаутит.</b></summary>

В `backend/app/services/orchestrator_service.py` включён 30-секундный TTL-cache
на `_check_llm_available()`. Если всё равно медленно — проверь, что llama-server/llama-swap
запущен на `http://127.0.0.1:8090` (`LLM_BACKEND=llamacpp` в `.env`).
При Ollama-fallback (`LLM_BACKEND=ollama`): `ollama ps` / `ollama list`.

</details>

<details>
<summary><b>Ollama падает при inference или OOM.</b></summary>

Запусти `scripts/ollama/optimize_ollama.ps1` — он применяет safe defaults
для num_ctx / num_gpu / num_thread. Для моделей ≥17 GB single-shard
`ollama create --quantize` может зависнуть — используй `scripts/ollama/activate_turbo_quant.ps1` вместо этого.

</details>

<details>
<summary><b>Word lock files (<code>~$*.docx</code>) в docs/diploma/.</b></summary>

```powershell
Get-Process WINWORD -ErrorAction SilentlyContinue | Stop-Process -Force
Remove-Item docs/diploma/~$*.docx -Force
```

</details>

<details>
<summary><b>Frontend не подключается к backend по WebSocket.</b></summary>

Проверь:
1. Backend запущен на порту 8000 (`cd backend && uvicorn app.main:app --reload --port 8000`)
2. В `frontend/.env.local` переменная `NEXT_PUBLIC_WS_URL=ws://localhost:8000`
   (только базовый URL — фронтенд сам добавляет `/api/v1/ws/<sessionId>`, не дублируй путь)
3. JWT токен не истёк (в dev-режиме срок жизни = 24 часа)

</details>

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
- [x] Детектор аффекта/эмоций (rule-based в проде; RuBERT, test macro-F1 0.97, включается `AFFECT_DETECTOR_TYPE=ml`)
- [x] OCR рукописных решений (Qwen3.5 native vision через llama-swap)
- [x] A/B experiment framework
- [x] Analytics dashboard + PDF экспорт
- [ ] Docker Compose deployment (experimental, не тестировался)
- [x] Миграция на Qwen3.5-9B (bf16, RTX PRO 6000 Blackwell 96GB)
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
