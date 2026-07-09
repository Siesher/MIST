# Design: Refactor DIPLOMA_PLAN.md под 4-stage pipeline

**Дата:** 2026-05-24
**Автор:** Сухацкий М. О. (с Claude Code)
**Ветка:** 019-ns-vstar-dpo
**Статус:** Approved design → ready for implementation plan

---

## Контекст и проблема

`docs/diploma/DIPLOMA_PLAN.md` — детальный план ВКР (~80-100 стр., 4 главы + приложения). План
написан под **устаревший** pipeline `GSPO → RAFT++ → DPO` (3 стадии). Актуальный pipeline:

```
Qwen3.5-9B → GSPO → KTO → DPO → V-STaR-DPO (Phase 019)
```

RAFT++ заменён на **KTO** (Kahneman-Tversky Optimization, arXiv:2402.01306), и добавлена
**Stage 4 — V-STaR-DPO** (Variational STaR + No-Spoiler judge + PRM composite scoring, Phase 019).

Также bibliography плана содержит 16 источников — недостаточно для технической ВКР бакалавра
(норма ~40), и распределена неравномерно (8/16 — RL/GRPO refs, главы 1.1 ITS и 1.2 Pedagogy
недопредставлены).

**Образец оформления:** `ВКР(10) (3).docx` — той же кафедры ИУК3 «Системы автоматического
управления» (73 стр., 26 рисунков, 6 таблиц). Начинается с раздела **АННОТАЦИЯ** (не «Реферат»):
страниц/рисунков/таблиц → тема → объект → предмет → цель → актуальность → практическая значимость
→ полученные результаты. Стили: `Heading 1` (главы), `Normal` (текст).

## Goals

1. Переписать Главы 3.5-3.8 как **4 stages** (по одной sub-секции на stage)
2. Переписать структуру Главы 4 под 4-stage progression (таблицы +1 столбец, +секция 4.7)
3. Расширить bibliography 16 → **40 sources** по всем главам
4. Синхронизировать `DIPLOMA_DIAGRAMS.md` (3 диаграммы с RAFT++ refs)
5. Заложить placeholder-маркеры для V-STaR результатов (заполнить после full run)

## Non-goals

- Полный write-up глав (это последующие заходы) — сейчас только **план/структура**
- Создание самого `ВКР.docx` (skeleton) — отдельная задача
- Изменение кода pipeline / запуск экспериментов

---

## Section 1: Новая структура Глав 3-4

### Глава 3. Реализация — секции 3.5-3.8 (по stages)

| Секция | Название | Объём | Статус |
|--------|----------|-------|--------|
| 3.5 | Stage 1: GSPO с тройной GDPO-наградой | ~3 стр. | keep |
| 3.6 | Stage 2: KTO — Socratic alignment (Kahneman-Tversky) | ~3 стр. | **NEW** (заменяет RAFT++) |
| 3.7 | Stage 3: DPO — базовая polish стадия | ~2 стр. | refactor |
| 3.8 | Stage 4: V-STaR-DPO composite (Phase 019) | ~3-4 стр. | **NEW** |

**3.6 (KTO) содержит:**
- Теория KTO (Ethayarajh 2024) — Kahneman-Tversky value function, loss aversion
- Преимущество над DPO/RAFT++: unpaired preferences, asymmetric β
- Датасет: `dialogs.jsonl` (3875 Socratic) + `preference_pairs.jsonl` (12597)
- Гиперпараметры: LoRA r=16, lr=5e-7, β=0.1, batch=8, 2 epochs

**3.8 (V-STaR-DPO) содержит:**
- Теория V-STaR (Hosseini 2024) — N trajectories/problem → within-task DPO pairs
- Composite scorer: `correctness × 0.5 + PRM(Skywork-o1) × 0.3 + no_spoiler_judge × 0.2`
  — PRM это **process** reward (оценивает reasoning steps, не финальный answer)
- Hard-only pivot (Option B): фокус на failure mode Phase 0a regression
- Within-task pairing: best vs worst trajectory из N=4 на problem
- Subset: 426 hard problems → 1692 trajectories

### Глава 4. Экспериментальное исследование

| Секция | Изменение |
|--------|-----------|
| 4.2 | Базовая модель — keep (55.1% baseline) |
| 4.3 | Per-stage results — stage-колонки 3 → **4** (GSPO/KTO/DPO/V-STaR-DPO); + колонка Base = 5 числовых колонок (было 4) |
| 4.4 | Per-stage ablation — добавлены ablation для KTO (β-tuning) + V-STaR (composite weights) |
| 4.5 | Качественный анализ — + примеры V-STaR within-task pairs |
| 4.6 | Knowledge Tracing — keep |
| **4.7 NEW** | V-STaR detailed analysis — Pareto-фронт (correctness vs no-spoiler), per-domain gains |

**Известные числа (из тезисов StudVesna2026):**
- Base 55.1% → GSPO +8.4 (63.5%) → KTO +1.3 (64.8%) → DPO +1.7 (66.5%)
- Stage 4 (V-STaR-DPO): **placeholder, заполнить после run**

---

## Section 2: Bibliography 16 → 40 sources

Существующие 16 sources сохраняются. Добавляются 24 новых, распределённых по главам:

**Гл. 1.1 ITS (+2):** Koedinger & Anderson (1997); Aleven et al. (2016)
**Гл. 1.2 Pedagogy (+2):** Wood, Bruner & Ross (1976) [scaffolding]; Chi (2009)
**Гл. 1.3 LLMs (+5):** Vaswani (2017); Brown (2020) GPT-3; Wei (2022) CoT; Wang (2022) Self-Consistency; Guo (2025) DeepSeek-R1
**Гл. 1.4 RL (+4):** Schulman (2017) PPO; Ouyang (2022) InstructGPT; Hu (2021) LoRA; Muennighoff (2025) s1
**Гл. 1.5 KT (+2):** Pandey & Karypis (2019) SAKT; Yudelson et al. (2013) Individualized BKT
**Гл. 3 Phase 019 (+5):** Ethayarajh (2024) KTO; Tversky & Kahneman (1992) Prospect Theory; Hosseini (2024) V-STaR; Wang (2024) Math-Shepherd; Skywork (2024) PRM card
**Гл. 4 Eval (+3):** Cobbe (2021) GSM8K; Hendrycks (2021) MMLU; Shi (2023) MGSM
**No-spoiler (+1):** Daheim et al. (2024) Stepwise Verification with LLM Tutors

**Сохранить как related work (не удалять):** Yuan (2023) RAFT — alternative to KTO; ReST/STaR (Zelikman 2022) — predecessor V-STaR.

> **Disambiguation note:** в списке два разных Wang — Wang X. (2022, Self-Consistency) и Wang P. (2024, Math-Shepherd). При оформлении указывать инициалы во избежание confusion. Аналогично: Guo (2025, DeepSeek-R1) ≠ существующий ref Shao (2024, DeepSeekMath).

---

## Section 3: DIPLOMA_DIAGRAMS.md sync + commit plan

### 3a. Diagram updates

**Диаграмма 1 (Общая архитектура), TRAINING subgraph:** RAFT++ → KTO, добавить VSTAR box;
flow `GSPO --> KTO --> DPO --> VSTAR`.

**Диаграмма 3 (Пайплайн обучения):** rename S2 (RAFT++→KTO), добавить **subgraph S4** с
под-компонентами: V-STaR generation (N=4) → Composite scorer → Within-task pairing; arrow `S3 --> S4`.
Title: `3. Пайплайн обучения (4-Stage RL)`.

**Диаграмма 4 (Потоки данных):** rename Stage2, добавить Stage 4 датасеты:
`vstar_subset_hard.jsonl`, `vstar_trajectories_hard.jsonl`, `vstar_dpo_pairs.jsonl`.

### 3b. Placeholder marker convention

```markdown
<!-- TODO[V-STaR-final]: Заменить после full run -->
- Stage 4 (V-STaR-DPO): +X.X п.п. (до Y.Y%)
- Hard subset: A.A% → B.B%
```
Поиск: `grep -rn "TODO\[V-STaR" docs/diploma/`

### 3c. Commit plan (2 atomic commits)

1. `docs(019): DIPLOMA_PLAN refactor — 4-stage pipeline + extended bibliography`
2. `docs(019): DIPLOMA_DIAGRAMS sync — 4-stage pipeline`

---

## Self-review checklist (после написания обоих файлов)

- [ ] No "TBD"/vague phrasings вне `TODO[V-STaR-final]` маркеров
- [ ] 24 новые цитаты пронумерованы 17-40, без collision с 1-16
- [ ] Глава 4 таблица per-stage accuracy: 4 stage-колонки (GSPO/KTO/DPO/V-STaR-DPO) + Base + Domain
- [ ] Stage 2 (KTO) и Stage 4 (V-STaR-DPO) sub-секции имеют ≥3 цитаты каждая
- [ ] DIPLOMA_DIAGRAMS.md и DIPLOMA_PLAN.md без contradictions в названиях stage

---

## Open questions / риски

- **V-STaR результаты:** full run ETA был ~10:30 (2026-05-23). Если завершён — placeholders
  заполняются реальными числами при имплементации; если нет — остаются маркеры.
- **Объём bibliography:** 40 sources — на нижней границе нормы. При write-up можно добить до 45-50.
