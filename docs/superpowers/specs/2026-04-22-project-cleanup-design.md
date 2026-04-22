# MITS Project Cleanup & Documentation Refresh — Design

**Date**: 2026-04-22
**Branch**: `018-path-slime`
**Author**: Сухацкий Максим (via Claude Opus 4.7)
**Status**: Approved by user
**Scope**: Option B (moderate reorganization, ~1.5 h)

---

## 1. Цель

Привести проект MITS к аккуратному виду после накопления артефактов за период 016–018 (Knowledge Forge → ToM-Tutor → PathSlime) и серии правок диплома. Удалить мусор, разложить файлы по смысловым папкам, обновить README реальными метриками из `evaluation/reports/`.

**Критерии успеха:**
1. Корневой каталог содержит только существенное (код, конфиги, `.venv/`, документация верхнего уровня).
2. `docs/`, `scripts/` разбиты на семантические подпапки; ни один activity-скрипт не ломается (все пути абсолютные).
3. README отражает реальные числа обучения и живого графа; где данных нет — стоит `—` или `TBD`.
4. История git чистая: каждая секция в отдельном коммите, чтобы можно было откатить по одной.

---

## 2. Non-goals

- **Не трогаем код** в `src/`, `backend/`, `frontend/`, `training/scripts/`.
- **Не удаляем** устаревшие `.docx` — отправляем в `docs/archive/`.
- **Не пересобираем** docker-compose, не трогаем `uv.lock`.
- **Не меняем** визуальный язык README (cyberpunk-баннер, emoji, ASCII остаются).
- **Не обещаем** метрики, которых нет: KTO/DPO ещё не проevalовали на полном benchmark, в таблице ставим `—`.

---

## 3. Секция 1 — Удаления

### 3.1 Гарантированный мусор
```
__pycache__/ во всех подкаталогах    (cache)
docs/~$*.docx                        (Word lock files)
mits.egg-info/                       (1.9 MB build artifact)
.pytest_cache/, .ruff_cache/         (60 KB cache)
Снимок экрана 2026-02-05 143909.png  (screenshot только sidebar, не используется)
```

### 3.2 Дубли и устаревшее
```
venv/                                (8.1 GB — дубль, есть .venv/)
design_handoff.7z                    (40 KB — есть распакованная папка)
New_style/                           (407 KB — интегрирован в frontend/)
.env.docker                          (консолидирую в .env.example)
.env.optimized                       (консолидирую в .env.example)
models/                              (ВСЯ папка — GLM + legacy Qwen 1.7B/4B Modelfile,
                                       актуальные Modelfile уже в training/)
```

### 3.3 Бэкапы и чужие работы (по решению пользователя)
```
docs/Курсовой_проект_Сухацкий_2026.bak.docx
docs/Курсовой_проект_Сухацкий_2026.pre-hardport.bak.docx
docs/НИР_Сухацкий_2026_controlled_reasoning.pre-hardport.bak.docx
docs/article_c3432f25.docx             (непонятное происхождение — удаляем)
docs/Статья_GNN_Лысенко_ОД_ИУК3-82Б.docx (работа другого студента — удаляем)
```

### 3.4 Обновление `.gitignore`
Добавить (если ещё нет):
```gitignore
venv/
.venv/
__pycache__/
*.egg-info/
.pytest_cache/
.ruff_cache/
~$*
.env
.env.docker
.env.optimized
wandb/
models/*/
!models/.gitkeep
```

**Итоговая экономия места**: ~10.1 GB (в основном `venv/`).

---

## 4. Секция 2 — Реорганизация `docs/`

### 4.1 Целевая структура

```
docs/
├── INDEX.md                          [NEW] — навигация
├── diploma/                          [NEW]
│   ├── Курсовой_проект_Сухацкий_2026.docx
│   ├── НИР_Сухацкий_2026_controlled_reasoning.docx
│   ├── DIPLOMA_PLAN.md
│   ├── DIPLOMA_DIAGRAMS.md
│   └── exports/
│       ├── Курсовой_проект.pdf
│       └── НИР.pdf                   (переименовать из "НИР (1).pdf")
├── architecture/                     [NEW]
│   ├── ARCHITECTURE.md
│   ├── MODEL_SELECTION.md
│   ├── OPTIMIZATION_PLAN.md
│   ├── RESOURCE_PROFILES.md
│   └── TURBO_QUANT_BACKEND.md
├── training/                         [NEW]
│   ├── TRAINING_PIPELINE.md
│   ├── GSPO_TECHNIQUES_DETAIL.md
│   ├── presentation_notes_main.md
│   └── presentation_notes_rl_qwen.md
├── guides/                           [NEW]
│   ├── quickstart.md
│   └── PROJECT_STATUS.md
└── archive/                          [NEW]
    ├── pre-2026/
    │   └── Курсовая_MITS_Сухацкий.docx
    └── nir-drafts/
        ├── НИР_Сухацкий_2026_knowledge_forge.docx
        ├── НИР_управляемое_рассуждение_Сухацкий.docx
        └── Новый_подход_к_дистилляции_ризонинга_Сухацкий.docx
```

### 4.2 Проверки перед перемещением
1. `grep -rn "docs/TRAINING_PIPELINE.md"` в `src/`, `scripts/`, `*.md`, `CLAUDE.md`, `README.md`. Обновить все найденные ссылки.
2. Аналогично для `DIPLOMA_PLAN.md`, `ARCHITECTURE.md`, `MODEL_SELECTION.md`, `quickstart.md`, `PROJECT_STATUS.md`.
3. `git mv` используется для всех перемещений (сохраняет историю).

### 4.3 INDEX.md — содержимое

Короткий navigation hub:
```markdown
# MITS Documentation Index

## 🎓 Diploma (2026)
- [НИР 2026 — Controlled Reasoning](diploma/НИР_Сухацкий_2026_controlled_reasoning.docx)
- [Курсовой проект 2026](diploma/Курсовой_проект_Сухацкий_2026.docx)
- [Diploma Plan](diploma/DIPLOMA_PLAN.md)
- [Diploma Diagrams](diploma/DIPLOMA_DIAGRAMS.md)

## 🏛 Architecture
- [System Architecture](architecture/ARCHITECTURE.md)
- [Model Selection](architecture/MODEL_SELECTION.md)
- [Optimization Plan](architecture/OPTIMIZATION_PLAN.md)
- [Resource Profiles](architecture/RESOURCE_PROFILES.md)
- [TurboQuant Backend](architecture/TURBO_QUANT_BACKEND.md)

## 🚀 Training
- [Training Pipeline](training/TRAINING_PIPELINE.md)
- [GSPO Techniques](training/GSPO_TECHNIQUES_DETAIL.md)
- [Presentation — Main](training/presentation_notes_main.md)
- [Presentation — RL Qwen](training/presentation_notes_rl_qwen.md)

## 📘 Guides
- [Quickstart](guides/quickstart.md)
- [Project Status](guides/PROJECT_STATUS.md)

## 🗄 Archive
Previous iterations kept for historical reference — not used in current pipeline.
- [pre-2026/](archive/pre-2026/) — coursework from 2024
- [nir-drafts/](archive/nir-drafts/) — НИР drafts before "controlled reasoning" final version
```

---

## 5. Секция 3 — Реорганизация `scripts/`

### 5.1 Целевая структура

```
scripts/
├── README.md                         [NEW]
├── migrations/                       (уже существует, не трогаем)
├── db/                               [NEW]
│   ├── init_db.py
│   └── migrate_to_forge.py
├── knowledge/                        [NEW]
│   ├── grow_knowledge_graph.py
│   ├── precompute_embeddings.py
│   └── ingest_pdf.py
├── ollama/                           [NEW]
│   ├── activate_turbo_quant.ps1
│   ├── check_ollama_config.py
│   ├── detect_resources.py
│   ├── optimize_ollama.ps1
│   ├── pull-models.sh
│   ├── setup_speculative.ps1
│   ├── start_ollama_optimized.ps1
│   ├── start_optimized.ps1
│   └── test_hf_turbo.py
├── design/                           [NEW]
│   ├── build_design_handoff.py
│   └── generate_social_preview.py
└── diploma/                          [NEW]
    ├── README.md                     [NEW]
    ├── generate_diploma_docs.py
    ├── generate_nir_controlled_reasoning.py
    ├── reformat_coursework.py
    ├── extend_diploma_docs.py
    ├── extend_diploma_docs_v2.py
    ├── rewrite_coursework_academic.py
    ├── enrich_docs_figures_metrics.py
    ├── make_fig21_clean.py
    ├── redo_fig21_architecture.py
    └── fix_nir_figs_32_33.py
```

### 5.2 scripts/README.md — содержимое

```markdown
# MITS Scripts

## db/ — база данных и миграции
init_db.py, migrate_to_forge.py

## knowledge/ — граф знаний, RAG, эмбеддинги
grow_knowledge_graph.py, precompute_embeddings.py, ingest_pdf.py

## ollama/ — локальный inference-стек (Ollama + TurboQuant)
PowerShell-скрипты для оптимизации и запуска, проверка конфигурации.

## design/ — дизайн-артефакты
Сборка design handoff, генерация social preview.

## diploma/ — одноразовые скрипты подготовки диплома
⚠️ Эти скрипты УЖЕ ОТРАБОТАЛИ и сохраняются для воспроизводимости.
Запускать повторно не нужно — они меняют docs/*.docx.
```

### 5.3 scripts/diploma/README.md — содержимое

```markdown
# Diploma — One-shot Scripts

These scripts generated/modified the diploma documents (`docs/diploma/*.docx`)
and their figures in `figures/diploma/`. They ran once and their effect is
captured in the tracked `.docx` files.

**Do not re-run** unless you want to regenerate from scratch.

## Timeline
- `generate_diploma_docs.py` — first draft generation (2026-04)
- `extend_diploma_docs.py`, `extend_diploma_docs_v2.py` — metric tables, more figures
- `reformat_coursework.py` — GOST formatting (A4, margins, spacing)
- `rewrite_coursework_academic.py` — impersonal academic style (after supervisor feedback)
- `generate_nir_controlled_reasoning.py` — НИР hard-port from reference docx
- `enrich_docs_figures_metrics.py` — 9 figures + 11 metric descriptions
- `redo_fig21_architecture.py` — final clean Рис. 2.1
- `make_fig21_clean.py` — intermediate clean version
- `fix_nir_figs_32_33.py` — final arrow/legend fixes for НИР Рис. 3.2 и 3.3
```

---

## 6. Секция 4 — Корневая уборка + `models/`

### 6.1 Конечный корень

```
MITS/
├── .claude/, .git/, .specify/, .venv/, wandb/       (dev/runtime)
├── backend/, frontend/, src/                        (code)
├── data/, evaluation/, tests/, training/            (data + ML)
├── docs/, figures/, notebooks/, specs/, scripts/    (docs + scripts)
├── tools/                                           (llama.cpp)
├── design_handoff/                                  (UI design sources)
├── CLAUDE.md, README.md, LICENSE
├── .env, .env.example, .gitignore
├── pyproject.toml, uv.lock, requirements.txt
├── docker-compose.yml, run.py
```

### 6.2 Что происходит с `models/`

Проверено: **все** файлы в `models/` — deprecated:
- `models/glm-original/`, `models/glm-reap/`, `models/glm-stem-pruned/` — GLM выкинули при миграции на Qwen
- `models/Modelfile.mits-tutor-qwen3-1.7b` — legacy (1.7B model, теперь 9B)
- `models/Modelfile.mits-tutor-qwen3-4b` — legacy (4B model, теперь 9B)
- `models/Modelfile-reap-q8`, `models/Modelfile-reap-v2` — GLM-REAP (deprecated)

Актуальные Modelfile уже лежат в `training/` (`Modelfile`, `Modelfile.9b-gspo`, `Modelfile.9b-kto`, `Modelfile.9b-kto-fast`, `Modelfile.9b-kto-turbo`).

**Действие:** удалить `models/` целиком.

### 6.3 Консолидация `.env.*`

Сейчас:
- `.env` — рабочий (не трогаем)
- `.env.example` — шаблон для новых разработчиков
- `.env.docker` — для docker-compose
- `.env.optimized` — с TurboQuant настройками

План: в `.env.example` добавить комментированные секции `# === Docker ===` и `# === Optimized (TurboQuant) ===` с соответствующими опциями. `.env.docker` и `.env.optimized` удаляются.

---

## 7. Секция 5 — README обновление

### 7.1 Стиль остаётся

Cyberpunk-баннер, emoji, badges, ASCII-диаграммы — **не меняем**. Только добавляем/обновляем разделы.

### 7.2 Новые и обновлённые разделы

| № | Раздел | Тип | Содержимое |
|---|---|---|---|
| 1 | ✨ Ключевые фичи | NEW | Timeline 016→017→018, по 2–3 строки |
| 2 | Архитектура | UPDATE | Встроить `figures/diploma/courseware_fig_2_architecture.png`, ASCII в `<details>` |
| 3 | 📊 Результаты обучения | NEW | Таблица per-stage × per-domain (реальные числа) + `nir_fig_4_per_stage_accuracy.png` |
| 4 | 📈 ToM & Knowledge Forge | NEW | A/B метрики: 70%→95% root-hit, 0 regressions, 83 nodes × 88 edges |
| 5 | 📁 Структура проекта | UPDATE | Обновить tree после реорганизации |
| 6 | ❓ FAQ / Troubleshooting | NEW | `<details>` блок с 4–5 типовыми проблемами |

### 7.3 Таблица результатов — честные числа

Источник: `evaluation/reports/compare_base_vs_gspo_20260331_115146.json`,
`evaluation/reports/summary.csv`, `quick_eval_gspo.json`.

```markdown
| Domain    | Base (n=143) | GSPO (n=141) | KTO | DPO |
|:----------|:------------:|:------------:|:---:|:---:|
| Math      | 100.0%       | 82.6%        | —   | —   |
| Physics   | 96.7%        | 90.0%        | —   | —   |
| Chemistry | 90.0%        | 96.6%        | —   | —   |
| Biology   | 80.0%        | 80.0%        | —   | —   |
| CS        | 86.2%        | 89.7%        | —   | —   |
| **Overall** | **90.2%**  | **87.9%**    | —   | —   |

> ⚠️ Small sample (143 задачи, стратифицированный). GSPO показала
> mixed effects: снижение на math (100% → 82.6%), но прирост на
> chemistry (+6.6%) и CS (+3.5%). Full-benchmark eval (n=3678) и
> стадии KTO/DPO — в работе.
```

### 7.4 ToM A/B — честные числа

Источник: `evaluation/reports/tom_ab_2026-04-18.md`.

```markdown
| Метрика | Baseline | ToM | Delta |
|---------|:--------:|:---:|:-----:|
| Root-hit rate           | 70.0%  | **95.0%** | **+25.0%** |
| Any-hit rate            | 100.0% | 100.0%    | ±0 |
| Misconception accuracy  | —      | 90.0%     | — |
| Regressed scenarios     | —      | 0 / 20    | — |
| Avg confidence          | —      | 0.89      | — |

*20 сценариев, 4 категории (explicit_misconception, confused, open_question,
confident_wrong). Latency: p50 11.5s, p95 147s — узкое место.*
```

### 7.5 Новые диаграммы

Генерирую 2 новые картинки в `figures/readme/`:

1. **`feature_timeline.png`** — horizontal timeline
   ```
   016 Knowledge Forge (2026-03) → 017 ToM-Tutor (2026-04) → 018 PathSlime (2026-04)
   ```
   matplotlib, даты из git log commits, стиль — в тон cyberpunk-баннеру (тёмный фон, фиолетовые блоки).

2. **`domain_heatmap.png`** — heatmap domain × stage (accuracy).
   seaborn heatmap, `—` для KTO/DPO клеток (plt-text).

### 7.6 FAQ-блок

```markdown
<details>
<summary>❓ FAQ / Troubleshooting</summary>

**Модель долго грузится в Ollama.**
Используй профили из `src/resource_profiles.py` (lite / standard / max) —
подбирают num_ctx и num_predict под железо. Подробнее: `docs/architecture/RESOURCE_PROFILES.md`.

**/health endpoint таймаутит.**
В orchestrator_service включён 30-секундный TTL-cache для `_check_llm_available()`.
Если всё равно медленно — Ollama не запущена или модель не подтянута.

**Ollama падает / OOM.**
`scripts/ollama/optimize_ollama.ps1` применяет safe defaults. TurboQuant
на моделях ≥17 GB single-shard может зависать при `ollama create --quantize` — см. note в memory.

**Word lock files (`~$*.docx`) в docs/.**
`Stop-Process -Name WINWORD -Force` в PowerShell, потом удалить файлы.
</details>
```

### 7.7 Структура проекта (обновление tree в README)

```
MITS/
├── frontend/                    # Next.js 14 + TypeScript
├── backend/                     # FastAPI
├── src/                         # Core Python — agents + models
├── training/
│   ├── scripts/                 # evaluate_stage.py, stem_rewards, ...
│   ├── data/                    # datasets, benchmark
│   └── Modelfile*               # Ollama Modelfile templates (9b GSPO/KTO)
├── notebooks/                   # Colab training + support
├── evaluation/                  # Reports + benchmarks
├── data/                        # Knowledge bases (RAG, skill graph, forge.json)
├── docs/
│   ├── diploma/                 # НИР + Курсовой 2026
│   ├── architecture/            # ARCHITECTURE, MODEL_SELECTION, ...
│   ├── training/                # TRAINING_PIPELINE, GSPO_TECHNIQUES, ...
│   ├── guides/                  # quickstart, PROJECT_STATUS
│   └── archive/                 # pre-2026, nir-drafts
├── scripts/
│   ├── db/, knowledge/          # init_db, ingest_pdf, grow_graph
│   ├── ollama/                  # Ollama + TurboQuant automation
│   ├── design/                  # design handoff, social preview
│   └── diploma/                 # one-shot diploma generators (⚠️ already ran)
├── figures/
│   ├── diploma/                 # figures for НИР + Курсовой
│   └── readme/                  # feature_timeline, domain_heatmap
├── specs/                       # 001–018 feature specs
└── tests/                       # Unit & integration
```

---

## 8. Порядок выполнения (коммиты)

Каждая секция — отдельный коммит для обратимости.

1. `chore(cleanup): remove build artifacts and duplicates`
   - Секция 1 целиком (все удаления + .gitignore).
2. `chore(docs): reorganize docs/ into semantic subdirs + archive`
   - Секция 2 (git mv + INDEX.md).
3. `chore(scripts): reorganize into db/knowledge/ollama/design/diploma`
   - Секция 3 (git mv + README.md + scripts/diploma/README.md).
4. `chore(root): consolidate .env files, move Modelfiles to training/modelfiles`
   - Секция 4 (удаление `models/`, `.env.*`-консолидация).
5. `docs(readme): add metrics tables, feature timeline, FAQ`
   - Секция 5 целиком (README + 2 новые картинки в `figures/readme/`).

Итого 5 коммитов. Если что-то ломается, `git reset --hard HEAD^` откатит именно этот этап.

---

## 9. Риски и митигация

| Риск | Митигация |
|---|---|
| Сломанные ссылки после `git mv docs/*.md` | Сначала `grep -rn`, потом `sed`, потом `git mv` |
| `docs/*.docx` заблокированы Word | `Stop-Process WINWORD` перед началом |
| Потеря `.env.docker` / `.env.optimized` | Перед удалением — читаю содержимое, переношу уникальные ключи в `.env.example` с комментариями |
| Новые картинки генерируются некрасиво | Тестовые прогоны, сравнение с существующими figures/diploma/*.png |
| `tools/llama.cpp/` — submodule или просто клон | Перед любыми действиями: `git submodule status` — если submodule, не трогаю |

---

## 10. Вне scope (отдельными задачами, если захочется)

- Написать CHANGELOG.md
- CONTRIBUTING.md
- Full benchmark eval по KTO/DPO (нужен Colab)
- Новая mermaid-диаграмма архитектуры
- Запись демо-GIF работы UI
- Обновление CLAUDE.md с новыми путями

---

**Approved by user** (all 5 sections confirmed in brainstorming session 2026-04-22).
