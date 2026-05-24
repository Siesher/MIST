# DIPLOMA_PLAN Refactor под 4-stage pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Привести `DIPLOMA_PLAN.md` и `DIPLOMA_DIAGRAMS.md` в соответствие с актуальным 4-stage pipeline (GSPO → KTO → DPO → V-STaR-DPO) и расширить bibliography 16 → 40 sources.

**Architecture:** Чистый документ-refactor двух markdown-файлов. Глава 3 единой секции «Реализация пайплайна» разбивается на 4 stage-секции (3.5-3.8) + renumber Бенчмарка в 3.9; Глава 4 получает +1 stage-колонку в таблицах и новую секцию 4.7; bibliography +24 источника; 3 Mermaid-диаграммы синхронизируются. V-STaR числовые результаты остаются placeholder-маркерами `TODO[V-STaR-final]`.

**Tech Stack:** Markdown, Mermaid (flowchart), git. Verification через `grep`/`rg` (нет кода → нет unit-тестов; «тест» = структурная проверка).

> **TDD-адаптация:** для markdown «failing test» = grep-проверка, показывающая что целевая структура ещё НЕ на месте; «passing test» = та же проверка после edit показывает корректное состояние. Дисциплина та же: verify-before → edit → verify-after → commit.

> **Spec:** `docs/superpowers/specs/2026-05-24-diploma-plan-refactor-design.md`

---

## File Structure

| Файл | Ответственность | Изменение |
|------|-----------------|-----------|
| `docs/diploma/DIPLOMA_PLAN.md` | Структура ВКР (главы, объёмы, bibliography) | Главы 3.5-3.9, Глава 4, Список литературы |
| `docs/diploma/DIPLOMA_DIAGRAMS.md` | Mermaid-диаграммы системы | Диаграммы 1, 3, 4 |

**Порядок:** сначала весь DIPLOMA_PLAN.md (Tasks 1-3) → commit (Task 4) → DIPLOMA_DIAGRAMS.md (Tasks 5-7) → commit (Task 8). Два atomic commits.

---

## Task 1: Глава 3 — разбить на 4 stage-секции + renumber Бенчмарк

**Files:**
- Modify: `docs/diploma/DIPLOMA_PLAN.md` (секция «#### 3.5. Реализация пайплайна обучения» и «#### 3.6. Бенчмарк»)

- [ ] **Step 1: Verify current state (failing check)**

Run: `rg -n "RAFT\+\+" docs/diploma/DIPLOMA_PLAN.md`
Expected: matches в строках ~162-163 (Stage 2 — RAFT++) и в bibliography (RAFT). Эти строки Главы 3 будут заменены.

Run: `rg -n "^#### 3\.(5|6)\." docs/diploma/DIPLOMA_PLAN.md`
Expected: `3.5. Реализация пайплайна обучения` и `3.6. Бенчмарк и инструменты оценки` — текущая нумерация (2 секции, до refactor).

- [ ] **Step 2: Replace single 3.5 pipeline section + renumbered 3.6 → full 3.5-3.9**

Edit `DIPLOMA_PLAN.md`. Заменить блок от `#### 3.5. Реализация пайплайна обучения` до строки перед `**Выводы по главе 3:**` (включая старую 3.6 Бенчмарк) на:

```markdown
#### 3.5. Stage 1 — GSPO с тройной GDPO-наградой (~3 стр.)
- Группы по G=8-16 completions на промпт, sequence-level importance sampling (ε=3e-4)
- Тройная GDPO-нормированная награда: correctness 0.7 + format 0.15 + Socratic 0.15
- 7 оптимизаций: Dr.GRPO, ReDit (reward dithering σ=0.05), GDPO, LEAD, Clip-Higher, Zero-Var Mask, Seq-IS
- ThinkingBudgetProcessor: гарантированное завершение `</think>` (бюджет 1500 токенов)
- Curriculum: easy → medium → hard
- Гиперпараметры: LoRA r=16/α=32, lr=5e-7, MAX_COMPLETION=2048
- Чекпойнт: HF `Siesher/mits-qwen3-9b-gspo`

#### 3.6. Stage 2 — KTO Socratic alignment (~3 стр.)
- Теория KTO (Kahneman-Tversky Optimization, Ethayarajh 2024): выравнивание через value-функцию из prospect theory (Tversky & Kahneman 1992) вместо парного DPO-лосса
- Ключевое преимущество над RAFT++/DPO: **unpaired** preferences — каждый пример помечается desirable/undesirable независимо, не требует chosen/rejected пар
- Loss aversion: асимметричные веса desirable (λ_D) vs undesirable (λ_U) сигналов
- Датасет: `data/training/dialogs.jsonl` (3875 Socratic dialogues) + `training/data/preference_pairs.jsonl` (12597 pairs, разложены в unpaired)
- Цель стадии: повысить долю ответов с сократическими вопросами (наводящие vs прямой ответ)
- Гиперпараметры: LoRA r=16, lr=5e-7, β=0.1, batch=8, 2 epochs
- Чекпойнт: HF `Siesher/mits-qwen3-9b-kto`

#### 3.7. Stage 3 — DPO базовая polish (~2 стр.)
- Direct Preference Optimization (Rafailov 2023): финальная полировка формата и стиля
- Preference pairs из контрастов KTO-выходов (desirable vs undesirable генерации)
- Фокус: устранение остаточных format-нарушений, стабилизация длины ответа
- Гиперпараметры: β=0.1, lr=5e-7, 1 epoch
- Чекпойнт: HF `Siesher/mits-qwen3-9b-final`

#### 3.8. Stage 4 — V-STaR-DPO composite (Phase 019) (~3-4 стр.)
- Теория V-STaR (Hosseini 2024): Variational STaR — генерация N траекторий на задачу, отбор verifier'ом → within-task preference pairs
- **Composite scorer**: `correctness × 0.5 + PRM × 0.3 + no_spoiler_judge × 0.2`
  - correctness — SymPy/ChemPy верификация финального ответа
  - PRM — **process** reward (Skywork-o1-Open-PRM-Qwen-2.5-1.5B, Math-Shepherd-style): оценивает корректность reasoning-шагов, не только финальный ответ
  - no_spoiler_judge — LLM-судья педагогической пригодности (наводит, не выдаёт решение; Daheim 2024)
- **Hard-only pivot** (Option B): фокус на failure mode регрессии Phase 0a — обучение только на hard-задачах
- Within-task pairing: best vs worst траектория из N=4 на одну задачу → DPO-пара
- Subset: 426 hard-задач (math 100, physics 100, chemistry 48, biology 78, cs 100) → 1692 траектории
- Источник subset: `rl_combined.jsonl`, 0% overlap с eval (verified)
- Чекпойнт: HF `Siesher/mits-qwen3-9b-vstar` (planned)

#### 3.9. Бенчмарк и инструменты оценки (~2 стр.)
- build_eval_benchmark.py: сборка из MGSM + ruMMLU + custom (3678 задач)
- evaluate_stage.py: inference + verify (SymPy, ChemPy) + report
- Структура отчетов: per-domain accuracy, answer extraction rate, truncation rate
```

- [ ] **Step 3: Verify post-state (passing check)**

Run: `rg -n "^#### 3\.(5|6|7|8|9)\." docs/diploma/DIPLOMA_PLAN.md`
Expected: 5 секций — `3.5. Stage 1 — GSPO`, `3.6. Stage 2 — KTO`, `3.7. Stage 3 — DPO`, `3.8. Stage 4 — V-STaR-DPO`, `3.9. Бенчмарк`.

Run: `rg -n "RAFT\+\+" docs/diploma/DIPLOMA_PLAN.md`
Expected: NO matches в Главе 3 (только возможный related-work mention в Главе 1.4 и bibliography остаётся).

Run: `rg -c "Чекпойнт: HF" docs/diploma/DIPLOMA_PLAN.md`
Expected: 4 (по одному на stage 3.5-3.8).

(Commit откладывается до Task 4 — весь DIPLOMA_PLAN.md одним commit.)

---

## Task 2: Глава 4 — расширить таблицы (+1 stage) + добавить секцию 4.7

**Files:**
- Modify: `docs/diploma/DIPLOMA_PLAN.md` (секции 4.3, 4.4, 4.5 + новая 4.7)

- [ ] **Step 1: Verify current state**

Run: `rg -n "^#### 4\.(3|4|5|6)\." docs/diploma/DIPLOMA_PLAN.md`
Expected: 4.3 (Результаты по стадиям), 4.4 (Ablation), 4.5 (Качественный анализ), 4.6 (Knowledge Tracing). НЕТ 4.7.

Run: `rg -n "Base → GSPO → RAFT\+\+ → DPO" docs/diploma/DIPLOMA_PLAN.md`
Expected: match в строке ~191 (старая 3-stage таблица-ссылка).

- [ ] **Step 2: Update 4.3 — таблица per-stage (+ V-STaR-DPO колонка)**

Edit `DIPLOMA_PLAN.md`. Заменить содержимое секции `#### 4.3. Результаты по стадиям обучения` на:

```markdown
#### 4.3. Результаты по стадиям обучения (~5 стр.)
- **Таблица:** Accuracy per stage per domain — колонки: Domain | Base | GSPO | KTO | DPO | V-STaR-DPO (4 stage-колонки + Base)
- **Графики:** Кривые обучения, convergence plots по стадиям
- Stage 1 (GSPO): RL with verifiable rewards + curriculum — +8.4 п.п. (55.1% → 63.5%)
- Stage 2 (KTO): Socratic alignment — +1.3 п.п. (63.5% → 64.8%)
- Stage 3 (DPO): format polish — +1.7 п.п. (64.8% → 66.5%)
<!-- TODO[V-STaR-final]: Заменить после full run -->
- Stage 4 (V-STaR-DPO): +X.X п.п. (66.5% → Y.Y%)
```

- [ ] **Step 3: Update 4.4 — ablation (+ KTO, V-STaR)**

Edit `DIPLOMA_PLAN.md`. Заменить содержимое секции `#### 4.4. Ablation study` на:

```markdown
#### 4.4. Ablation study (~3 стр.)
- Вклад каждой из 7 оптимизаций GSPO (Dr.GRPO, ReDit, GDPO, LEAD, Clip-Higher, Zero-Var, Seq-IS)
- Эффект ThinkingBudgetProcessor: с ним 14.3% обрезок vs 100% без него
- Эффект curriculum learning (easy→hard vs random)
- **KTO β-tuning**: влияние β и асимметрии λ_D/λ_U на долю сократических вопросов
- **V-STaR composite weights**: ablation весов scorer (correctness/PRM/no-spoiler), вариант −PRM (lean-demo)
- Эффект hard-only pivot vs полный difficulty mix
```

- [ ] **Step 4: Update 4.5 — добавить V-STaR pairs пример**

Edit `DIPLOMA_PLAN.md`. В секции `#### 4.5. Качественный анализ` добавить bullet после строки про move types:

```markdown
- Примеры V-STaR within-task pairs: best vs worst траектория одной hard-задачи (различия в reasoning quality и no-spoiler соблюдении)
```

- [ ] **Step 5: Insert new section 4.7 after 4.6**

Edit `DIPLOMA_PLAN.md`. После секции `#### 4.6. Анализ Knowledge Tracing` (перед `**Выводы по главе 4:**`) вставить:

```markdown
#### 4.7. Детальный анализ V-STaR-DPO (~3 стр.)
- **Pareto-фронт**: trade-off correctness vs no-spoiler score — показать что composite scoring находит решения, недостижимые при оптимизации одной метрики
- Per-domain V-STaR gains: какие домены выиграли больше от hard-only обучения
<!-- TODO[V-STaR-final]: Заменить после full run -->
- Hard subset accuracy: A.A% → B.B%
- Анализ yield: доля usable траекторий (~33% на sanity), распределение по N=4
- Эффект PRM: корреляция process-reward и финальной корректности на hard-задачах
```

- [ ] **Step 6: Update строку 191 ссылку на 4-stage**

Edit `DIPLOMA_PLAN.md`. Заменить:
`- **Таблица:** Accuracy per stage per domain (Base → GSPO → RAFT++ → DPO)`
на:
`- **Таблица:** Accuracy per stage per domain (Base → GSPO → KTO → DPO → V-STaR-DPO)`

(Эта строка может уже быть заменена в Step 2 если входит в секцию 4.3 — проверить; если осталась, заменить здесь.)

- [ ] **Step 7: Verify post-state**

Run: `rg -n "^#### 4\.7\." docs/diploma/DIPLOMA_PLAN.md`
Expected: `4.7. Детальный анализ V-STaR-DPO` exists.

Run: `rg -n "TODO\[V-STaR-final\]" docs/diploma/DIPLOMA_PLAN.md`
Expected: 2 matches (в 4.3 и 4.7).

Run: `rg -n "RAFT\+\+" docs/diploma/DIPLOMA_PLAN.md`
Expected: NO matches в Главе 4 (Base→GSPO→KTO→DPO→V-STaR-DPO везде).

---

## Task 3: Bibliography — добавить 24 источника (17-40)

**Files:**
- Modify: `docs/diploma/DIPLOMA_PLAN.md` (секция `### СПИСОК ЛИТЕРАТУРЫ`)

- [ ] **Step 1: Verify current state**

Run: `rg -n "^[0-9]+\. " docs/diploma/DIPLOMA_PLAN.md`
Expected: пронумерованные источники 1-16 в секции СПИСОК ЛИТЕРАТУРЫ.

- [ ] **Step 2: Insert sources 17-40**

Edit `DIPLOMA_PLAN.md`. После пункта 16 (Vygotsky 1978), перед `**Технические источники**`, вставить:

```markdown
17. Koedinger, K. R., & Anderson, J. R. (1997). Intelligent Tutoring Goes To School in the Big City. *International Journal of Artificial Intelligence in Education*, 8.
18. Aleven, V., et al. (2016). Instruction Based on Adaptive Learning Technologies. In *Handbook of Research on Learning and Instruction* (2nd ed.). Routledge.
19. Wood, D., Bruner, J. S., & Ross, G. (1976). The Role of Tutoring in Problem Solving. *Journal of Child Psychology and Psychiatry*, 17(2).
20. Chi, M. T. H. (2009). Active-Constructive-Interactive: A Conceptual Framework. *Topics in Cognitive Science*, 1(1).
21. Vaswani, A., et al. (2017). Attention is All You Need. *NeurIPS*.
22. Brown, T., et al. (2020). Language Models are Few-Shot Learners (GPT-3). *NeurIPS*.
23. Wei, J., et al. (2022). Chain-of-Thought Prompting Elicits Reasoning in LLMs. *NeurIPS*.
24. Wang, X., et al. (2022). Self-Consistency Improves Chain-of-Thought Reasoning. *ICLR 2023*. arXiv:2203.11171.
25. Guo, D., et al. (2025). DeepSeek-R1: Incentivizing Reasoning Capability via RL. arXiv:2501.12948.
26. Schulman, J., et al. (2017). Proximal Policy Optimization Algorithms. arXiv:1707.06347.
27. Ouyang, L., et al. (2022). Training Language Models to Follow Instructions with Human Feedback (InstructGPT). *NeurIPS*.
28. Hu, E. J., et al. (2021). LoRA: Low-Rank Adaptation of Large Language Models. *ICLR 2022*. arXiv:2106.09685.
29. Muennighoff, N., et al. (2025). s1: Simple Test-Time Scaling. arXiv:2501.19393.
30. Pandey, S., & Karypis, G. (2019). A Self-Attentive Model for Knowledge Tracing (SAKT). *EDM*. arXiv:1907.06837.
31. Yudelson, M. V., Koedinger, K. R., & Gordon, G. J. (2013). Individualized Bayesian Knowledge Tracing Models. *AIED*.
32. Ethayarajh, K., et al. (2024). KTO: Model Alignment as Prospect Theoretic Optimization. arXiv:2402.01306.
33. Tversky, A., & Kahneman, D. (1992). Advances in Prospect Theory: Cumulative Representation of Uncertainty. *Journal of Risk and Uncertainty*, 5(4).
34. Hosseini, A., et al. (2024). V-STaR: Training Verifiers for Self-Taught Reasoners. arXiv:2402.06457.
35. Wang, P., et al. (2024). Math-Shepherd: Verify and Reinforce LLMs Step-by-step. *ACL 2024*. arXiv:2312.08935.
36. Skywork Team. (2024). Skywork-o1-Open-PRM-Qwen-2.5-1.5B [Model card]. *HuggingFace*.
37. Cobbe, K., et al. (2021). Training Verifiers to Solve Math Word Problems (GSM8K). arXiv:2110.14168.
38. Hendrycks, D., et al. (2021). Measuring Massive Multitask Language Understanding (MMLU). *ICLR 2021*.
39. Shi, F., et al. (2023). Language Models are Multilingual Chain-of-Thought Reasoners (MGSM). *ICLR 2023*. arXiv:2210.03057.
40. Daheim, N., et al. (2024). Stepwise Verification and Remediation of Student Reasoning Errors with LLM Tutors. *EMNLP 2024*. arXiv:2407.09136.
```

- [ ] **Step 3: Verify post-state**

Run: `rg -c "^[0-9]+\. " docs/diploma/DIPLOMA_PLAN.md`
Expected: 40 пронумерованных источников.

Run: `rg -n "^40\. Daheim" docs/diploma/DIPLOMA_PLAN.md`
Expected: 1 match (последний источник на месте).

---

## Task 4: Commit DIPLOMA_PLAN.md

**Files:** только `docs/diploma/DIPLOMA_PLAN.md`

- [ ] **Step 1: Stage only the plan file**

Run: `git add docs/diploma/DIPLOMA_PLAN.md`

- [ ] **Step 2: Verify staging**

Run: `git status --short docs/diploma/DIPLOMA_PLAN.md`
Expected: `M  docs/diploma/DIPLOMA_PLAN.md` (staged, зелёный M).

- [ ] **Step 3: Commit**

```bash
git commit -m "docs(019): DIPLOMA_PLAN refactor — 4-stage pipeline + extended bibliography

- Глава 3.5-3.8 разбита на 4 stages (GSPO, KTO, DPO, V-STaR-DPO), Бенчмарк → 3.9
- Глава 4: таблицы +1 stage-колонка, новая секция 4.7 V-STaR analysis
- Bibliography 16 -> 40 sources (Vaswani, CoT, KTO, V-STaR, PRM, MGSM)
- V-STaR placeholders TODO[V-STaR-final] для post-run fill-in
- RAFT++ remains в related work / alternatives

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: DIPLOMA_DIAGRAMS.md — Диаграмма 1 (TRAINING subgraph)

**Files:**
- Modify: `docs/diploma/DIPLOMA_DIAGRAMS.md:56-62` (TRAINING subgraph) + flow arrows строки ~97

- [ ] **Step 1: Verify current state**

Run: `rg -n "Stage 1: GSPO|Stage 2: RAFT|Stage 3: DPO" docs/diploma/DIPLOMA_DIAGRAMS.md`
Expected: matches в строках 57-59 (TRAINING subgraph диаграммы 1) и 190/197/206 (диаграмма 3).

- [ ] **Step 2: Replace TRAINING subgraph nodes**

Edit `DIPLOMA_DIAGRAMS.md`. Заменить:

```
        GSPO["Stage 1: GSPO"]
        RAFT["Stage 2: RAFT++"]
        DPO["Stage 3: DPO"]
        Eval["Evaluation<br/>3678 задач"]
        HF["HuggingFace Hub<br/>Адаптеры + Датасеты"]
```

на:

```
        GSPO["Stage 1: GSPO<br/>triple reward"]
        KTO["Stage 2: KTO<br/>Socratic alignment"]
        DPO["Stage 3: DPO<br/>basic polish"]
        VSTAR["Stage 4: V-STaR-DPO<br/>composite scoring"]
        Eval["Evaluation<br/>3678 задач"]
        HF["HuggingFace Hub<br/>Адаптеры + Датасеты"]
```

- [ ] **Step 3: Replace flow arrow**

Edit `DIPLOMA_DIAGRAMS.md`. Заменить:
`    GSPO --> RAFT --> DPO`
на:
`    GSPO --> KTO --> DPO --> VSTAR`

Затем заменить (строка ~101):
`    RAFT --> HF`
на:
`    VSTAR --> HF`

- [ ] **Step 4: Verify post-state**

Run: `rg -n "RAFT" docs/diploma/DIPLOMA_DIAGRAMS.md`
Expected: matches ТОЛЬКО в диаграммах 3 и 4 (которые правятся в Tasks 6-7), НЕ в диаграмме 1.

Run: `rg -n "GSPO --> KTO --> DPO --> VSTAR" docs/diploma/DIPLOMA_DIAGRAMS.md`
Expected: 1 match.

---

## Task 6: DIPLOMA_DIAGRAMS.md — Диаграмма 3 (Пайплайн обучения)

**Files:**
- Modify: `docs/diploma/DIPLOMA_DIAGRAMS.md:184-242` (диаграмма 3)

- [ ] **Step 1: Replace title**

Edit `DIPLOMA_DIAGRAMS.md`. Заменить:
`## 3. Пайплайн обучения (3-Stage RL)`
на:
`## 3. Пайплайн обучения (4-Stage RL)`

- [ ] **Step 2: Replace S2 subgraph (RAFT++ → KTO)**

Edit `DIPLOMA_DIAGRAMS.md`. Заменить блок:

```
    subgraph S2["Stage 2: RAFT++"]
        R1["GVM-RAFT<br/>Динамическая аллокация"]
        R2["800 задач/раунд<br/>Стратифицированная выборка"]
        R3["SFT на верных<br/>решениях"]
        R4["Сохранение негативов<br/>→ DPO"]
        R1 --> R2 --> R3
        R2 --> R4
    end
```

на:

```
    subgraph S2["Stage 2: KTO"]
        K1["Kahneman-Tversky<br/>Optimization"]
        K2["Unpaired preferences<br/>desirable/undesirable"]
        K3["Socratic alignment<br/>β=0.1"]
        K1 --> K2 --> K3
    end
```

- [ ] **Step 3: Add S4 subgraph (V-STaR-DPO) after S3 block**

Edit `DIPLOMA_DIAGRAMS.md`. После закрывающего `end` блока S3 (`subgraph S3["Stage 3: DPO"]`...`end`, строка ~211), добавить:

```

    subgraph S4["Stage 4: V-STaR-DPO"]
        V1["V-STaR generation<br/>N=4 траектории/задача"]
        V2["Composite scorer<br/>correct×0.5 + PRM×0.3 + no-spoiler×0.2"]
        V3["Within-task pairing<br/>best vs worst"]
        V1 --> V2 --> V3
    end
```

- [ ] **Step 4: Update flow arrows + checkpoint + style**

Edit `DIPLOMA_DIAGRAMS.md`. Заменить:
```
    S3 --> EVAL
    S3 --> DEPLOY
```
на:
```
    S3 --> S4
    S4 --> EVAL
    S4 --> DEPLOY
```

Заменить:
`    S2 -.->|checkpoint| HF2["HF: mits-qwen3-9b-raft"]`
на:
`    S2 -.->|checkpoint| HF2["HF: mits-qwen3-9b-kto"]`

После строки `    S3 -.->|checkpoint| HF3["HF: mits-qwen3-9b-final"]` добавить:
`    S4 -.->|checkpoint| HF4["HF: mits-qwen3-9b-vstar"]`

Заменить style-блок:
```
    style S1 fill:#e3f2fd
    style S2 fill:#e8f5e9
    style S3 fill:#fce4ec
    style EVAL fill:#f3e5f5
    style DEPLOY fill:#e0f2f1
```
на:
```
    style S1 fill:#e3f2fd
    style S2 fill:#e8f5e9
    style S3 fill:#fce4ec
    style S4 fill:#fff3e0
    style EVAL fill:#f3e5f5
    style DEPLOY fill:#e0f2f1
```

- [ ] **Step 5: Verify post-state**

Run: `rg -n "subgraph S4|Stage 4: V-STaR-DPO" docs/diploma/DIPLOMA_DIAGRAMS.md`
Expected: 1 match (S4 subgraph добавлен).

Run: `rg -n "S3 --> S4|S4 --> EVAL" docs/diploma/DIPLOMA_DIAGRAMS.md`
Expected: 2 matches (arrows корректны).

Run: `rg -n "RAFT" docs/diploma/DIPLOMA_DIAGRAMS.md`
Expected: matches ТОЛЬКО в диаграмме 4 (Task 7).

---

## Task 7: DIPLOMA_DIAGRAMS.md — Диаграмма 4 (Поток данных)

**Files:**
- Modify: `docs/diploma/DIPLOMA_DIAGRAMS.md:248-318` (диаграмма 4)

- [ ] **Step 1: Replace Stage2 node + NegDS dataset**

Edit `DIPLOMA_DIAGRAMS.md`. Заменить:
`        Stage2["RAFT++<br/>raft_plus_qwen3.5_9b.ipynb"]`
на:
`        Stage2["KTO<br/>kto_qwen3.5_9b.ipynb"]`

Заменить:
`        NegDS["raft_negatives.jsonl<br/>Негативы для DPO"]`
на:
`        VstarDS["vstar_subset_hard.jsonl<br/>426 hard + траектории"]`

- [ ] **Step 2: Add Stage4 node to TRAINING_FLOW subgraph**

Edit `DIPLOMA_DIAGRAMS.md`. После `        Stage3["DPO<br/>dpo_polish_qwen3.5_9b.ipynb"]` добавить:
`        Stage4["V-STaR-DPO<br/>ns_vstar_dpo.ipynb"]`

- [ ] **Step 3: Fix Artifacts node + dataflow arrows**

Edit `DIPLOMA_DIAGRAMS.md`. Заменить:
`        Negatives["Негативные пары<br/>RAFT++ → DPO"]`
на:
`        VstarPairs["vstar_dpo_pairs.jsonl<br/>within-task pairs"]`

Заменить блок arrows:
```
    Stage1 --> Stage2
    Stage2 --> Stage3
    Stage2 -->|negatives| NegDS
    NegDS --> Stage3

    Stage1 --> Adapters
    Stage2 --> Adapters
    Stage3 --> Adapters
    Stage3 --> GGUF
```
на:
```
    Stage1 --> Stage2
    Stage2 --> Stage3
    Stage3 --> Stage4
    Stage4 -->|trajectories| VstarDS
    VstarDS --> VstarPairs
    VstarPairs --> Stage4

    Stage1 --> Adapters
    Stage2 --> Adapters
    Stage3 --> Adapters
    Stage4 --> Adapters
    Stage4 --> GGUF
```

- [ ] **Step 4: Verify post-state**

Run: `rg -n "RAFT" docs/diploma/DIPLOMA_DIAGRAMS.md`
Expected: NO matches (все RAFT++ ссылки убраны из всех 3 диаграмм).

Run: `rg -n "Stage4|vstar_subset_hard|vstar_dpo_pairs" docs/diploma/DIPLOMA_DIAGRAMS.md`
Expected: ≥3 matches (Stage4 node + 2 датасета).

---

## Task 8: Commit DIPLOMA_DIAGRAMS.md

**Files:** только `docs/diploma/DIPLOMA_DIAGRAMS.md`

- [ ] **Step 1: Stage only the diagrams file**

Run: `git add docs/diploma/DIPLOMA_DIAGRAMS.md`

- [ ] **Step 2: Verify staging + final RAFT check**

Run: `git status --short docs/diploma/DIPLOMA_DIAGRAMS.md`
Expected: `M  docs/diploma/DIPLOMA_DIAGRAMS.md`

Run: `rg -c "RAFT" docs/diploma/DIPLOMA_PLAN.md docs/diploma/DIPLOMA_DIAGRAMS.md`
Expected: DIPLOMA_DIAGRAMS.md = 0; DIPLOMA_PLAN.md ≤ 2 (только related-work mentions).

- [ ] **Step 3: Commit**

```bash
git commit -m "docs(019): DIPLOMA_DIAGRAMS sync — 4-stage pipeline

- Диаграммы 1, 3, 4: RAFT++ → KTO + add Stage 4 V-STaR-DPO
- Диаграмма 3: subgraph S4 (generation/composite scorer/within-task pairing)
- Диаграмма 4: vstar_subset_hard.jsonl, vstar_dpo_pairs.jsonl dataflow
- Title: 3-Stage RL → 4-Stage RL

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review (выполнено при написании плана)

**1. Spec coverage:**
- Section 1 (Главы 3-4 структура) → Tasks 1, 2 ✓
- Section 2 (bibliography 40) → Task 3 ✓
- Section 3 (диаграммы sync) → Tasks 5, 6, 7 ✓
- Section 3 (commit plan) → Tasks 4, 8 ✓
- Section 3 (placeholder convention) → Task 2 Steps 2, 5 (TODO[V-STaR-final]) ✓
- **Gap найден и закрыт:** spec не упоминал renumber старой 3.6 Бенчмарк → 3.9. Добавлено в Task 1 Step 2.

**2. Placeholder scan:** `TODO[V-STaR-final]` и `X.X%`/`Y.Y%`/`A.A%`/`B.B%` — это intentional spec-defined маркеры для post-run fill-in (не plan failures). Все шаги имеют реальный контент.

**3. Type consistency:** stage-имена консистентны во всех tasks — `GSPO`/`KTO`/`DPO`/`V-STaR-DPO`. HF repo имена: `mits-qwen3-9b-{gspo,kto,final,vstar}`. Mermaid node IDs: `GSPO/KTO/DPO/VSTAR` (диаграмма 1), `S1/S2/S3/S4` (диаграмма 3), `Stage1-4` (диаграмма 4) — без коллизий.
