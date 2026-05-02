# Feature Specification: NS-V-STaR-DPO — научный финал обучения MITS

**Feature Branch**: `019-ns-vstar-dpo`
**Created**: 2026-05-02
**Status**: Draft
**Input**: Завершить пайплайн `Qwen3.5-9B → GSPO → KTO` заменой стандартной DPO-полировки на новый метод **NS-V-STaR-DPO** (No-Spoiler V-STaR DPO), объединяющий три исследовательские идеи 2024–2025 годов в едином DPO-loss: V-STaR self-improvement (arXiv:2402.06457), No-Spoiler pedagogy reward (arXiv:2505.15607, EMNLP 2025), Process Reward Model для пошаговой оценки рассуждений (Qwen2.5-Math-PRM-7B). Перед основной фазой — обязательный честный bf16 re-eval всех чекпоинтов на Colab для устранения inference artifact (base оценивался через Cerebras API full precision, GSPO/KTO — через Ollama q4_k_m).

## Научная новизна *(motivation)*

| Источник | Идея | Наш вклад |
|---|---|---|
| V-STaR (arXiv:2402.06457) | Verifier-guided self-improvement on in-distribution generations | Перенос идеи из general math problem solving в pedagogy domain — Сократический тьюторинг |
| No-Spoiler RL (arXiv:2505.15607, EMNLP 2025) | Pedagogy-as-reward (no answer leak, scaffolding, engagement) | Композитный reward с PRM и correctness, не только pedagogy |
| Qwen2.5-Math-PRM-7B (arXiv:2410.10288) | Step-level reasoning quality | Использование PRM как **одного из 3-х компонентов** DPO-сигнала, не финального verifier |
| MathTutorBench (arXiv:2502.18940, EMNLP 2025) | Pedagogical benchmark | Применение к non-English (Russian) STEM, ablation-driven attribution каждой идеи |
| Within-task pairing | Top-vs-bottom completions одной задачи | Устранение cross-task confounder, отсутствующее в стандартных RLHF датасетах |

**Главное утверждение**: первое (по доступному обзору литературы) объединение **V-STaR + No-Spoiler + PRM** в одном DPO-loss с within-task pairing на сократических диалогах русскоязычной STEM (math/physics/chem/bio/cs).

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Честный re-eval (Phase 0) (Priority: P1)

Текущая регрессия в метриках (base 90.2% → GSPO 72.4% → KTO 62.1% accuracy на calc subset) частично объясняется тем, что base оценен через Cerebras API (full precision), а GSPO/KTO — через локальный Ollama q4_k_m. До любого нового обучения нужно переоценить все три чекпоинта в одинаковом протоколе bf16 через Hugging Face transformers на Colab (RTX 6000 / A100 80GB), с одинаковым DECODING_CONFIG (`num_predict=4096`, `enable_thinking=True`, `temperature=0.0`, `SYSTEM_PROMPT_CALC`).

**Why this priority**: Без apple-to-apple baseline невозможно отделить эффект квантизации от эффекта RL drift, и любой новый эксперимент (Phase 1+) измеряется относительно ложного якоря. Фундамент валидности всех последующих заявлений в дипломе.

**Independent Test**: Запустить `notebooks/honest_eval_full_precision.ipynb` на Colab A100, получить отчёт `evaluation/reports/honest_full_precision_YYYYMMDD.json` со значениями `accuracy / socratic_score / leak_rate` для base, gspo, kto. Проверить, что цифры воспроизводимы при повторном запуске.

**Acceptance Scenarios**:

1. **Given** notebook готов с `BASE_MODEL_ID='Qwen/Qwen3.5-9B'` и тремя адаптерами, **When** все ячейки исполнены на A100, **Then** получен JSON-отчёт с `accuracy`, `socratic_score`, `leak_rate` для base/gspo/kto.
2. **Given** один и тот же commit hash и данные, **When** eval запущен дважды, **Then** numeric extraction совпадает (judge может мизерно расходиться из-за temperature judge — фиксируем seed).
3. **Given** результаты, **When** сравниваем с прежними Ollama-числами, **Then** различие attributed по двум осям: квантизация (∆ от bf16 vs q4) и реальный RL drift (∆ adapter vs base в bf16).

---

### User Story 2 — NS-V-STaR-DPO training (Priority: P1)

После Phase 0 запускается основная новая методология: с GSPO-чекпоинта (или иного, выбранного на основе honest eval как лучшего предка для self-training) генерируется N=4 ответа на каждую из 3875 сократических задач (`data/training/dialogs.jsonl`), каждый ответ оценивается тремя независимыми компонентами:

1. **Correctness** — programmatic verify (SymPy/ChemPy) + final-answer match с `ground_truth`
2. **Step-level reasoning** — Qwen2.5-Math-PRM-7B aggregate score по шагам
3. **Pedagogy** — Cerebras Combined Judge (no_answer_leak, scaffolding, engagement)

Композитный score = `w₁·correctness + w₂·PRM + w₃·pedagogy`. **Within-task pairing**: top-vs-bottom 1 пара per task → до 3875 DPO-пар (или 0, если top-bottom margin < τ). Тренируется final adapter `Siesher/mits-qwen3-9b-nsvstar-dpo` на A100 80GB.

**Why this priority**: Это main contribution — метод, защищаемый в дипломе. Содержит весь scientific novelty.

**Independent Test**: Прогнать full pipeline на 200-задачной mini-subset, получить ≥1 valid pair per task в 80% случаев, тренировка на mini завершается без NaN, eval на benchmark показывает Δaccuracy or Δsocratic ≥ +1pp относительно best-of-three baseline.

**Acceptance Scenarios**:

1. **Given** seed checkpoint и 3875 задач, **When** vstar_generate с N=4, **Then** получено 15500 completions с metadata.
2. **Given** completions, **When** scored 3 компонентами, **Then** для ≥80% задач есть pair с `composite_margin ≥ τ`.
3. **Given** DPO-pairs, **When** train run завершён 1 epoch на A100, **Then** loss падает монотонно, no NaN, output adapter loadable через `PeftModel.from_pretrained`.
4. **Given** trained adapter, **When** evaluated на honest benchmark, **Then** Pareto-улучшение хотя бы по одной из axis (accuracy / pedagogy) без регресса >2pp по другой.

---

### User Story 3 — Ablations: −PRM, −NoSpoiler (Priority: P2)

Чтобы доказать **каждую** компоненту научной новизны (а не "просто работает"), нужны ablation runs: тренировка с `w₂=0` (без PRM) и `w₃=0` (без No-Spoiler). Это изолирует вклад каждой идеи и позволяет писать в дипломе "PRM contributes +X pp на reasoning subset, No-Spoiler contributes +Y pp на pedagogy axis".

**Why this priority**: Без ablations научное утверждение weak — рецензент справедливо спросит "а что именно из трёх идей даёт прирост?". Это standard requirement для EMNLP/NeurIPS-уровня contribution.

**Independent Test**: Получить три adapter: full NS-V-STaR-DPO, −PRM, −NoSpoiler. На едином benchmark измерить axis-by-axis вклад. Differences интерпретируемы.

**Acceptance Scenarios**:

1. **Given** all three adapters trained, **When** evaluated на honest benchmark + MathTutorBench, **Then** results можно представить как 2D bar chart (accuracy / pedagogy axes).
2. **Given** ablation results, **When** statistical analysis на 218-task benchmark, **Then** confidence intervals подтверждают direction-of-effect для каждой компоненты.

---

### User Story 4 — MathTutorBench pedagogy eval (Priority: P2)

Помимо custom benchmark (218 задач), измеряем модель на **MathTutorBench** (arXiv:2502.18940, EMNLP 2025) — стандартизированном pedagogical benchmark для tutoring LLMs. Это даёт external validity и позволяет сравнить с published baselines.

**Why this priority**: Internal benchmark может содержать unintended biases (он состоит из наших Russian STEM задач). MathTutorBench — peer-reviewed external standard.

**Independent Test**: Запустить eval на MathTutorBench, получить reported metrics. Если есть Russian split — использовать его, иначе English subset для external validity.

**Acceptance Scenarios**:

1. **Given** MathTutorBench loaded и адаптеры доступны, **When** прогнаны 4 модели (best-of-three baseline, ns-vstar-dpo, ablation-noprm, ablation-nospoiler), **Then** получены comparable metrics с published numbers.

---

### User Story 5 — Diploma writeup с Pareto front (Priority: P1)

Финальный артефакт — chapter в дипломе с (а) описанием метода, (б) honest baseline numbers, (в) Pareto front (accuracy vs pedagogy) по 4 моделям + 2 ablations, (г) ablation analysis, (д) discussion of limitations.

**Why this priority**: Конечная цель — защита диплома. Без writeup технические достижения не имеют value для defense.

**Independent Test**: Главу прочитывает научный руководитель, замечания инкорпорируются.

---

### Edge Cases

- **GSPO checkpoint хуже base после honest re-eval**: переключаемся на base/KTO как seed для V-STaR (whichever is best). Composite scorer тогда отбирает best generations from новой seed.
- **Все 4 completions per task имеют одинаковый score** (degenerate generation): пропускаем task, не создаём пару — никакого random tie-breaking.
- **PRM 7B + tutor 9B OOM на одной GPU**: PRM scoring запускается отдельной сессией, scores персистятся в JSON cache → training session не нуждается в PRM.
- **Cerebras rate limit при judge calls**: rotating pool из 10 ключей (уже реализован в `training/cerebras_client.py`), exponential backoff, persistent cache scores → JSON.
- **MathTutorBench не имеет Russian split**: используем English subset как external validity, custom benchmark остаётся primary для in-language claims; документировать в `research.md`.
- **Compute budget overrun (>600 vu)**: fallback — сократить N с 4 до 2 (потеряем некоторые pairs, но сохраним ablations); в худшем случае сделать только −PRM ablation, без −NoSpoiler.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST произвести bf16 re-eval base/GSPO/KTO с identical decoding protocol до любого нового обучения.
- **FR-002**: System MUST генерировать N=4 completions per task через V-STaR loop от выбранного seed checkpoint.
- **FR-003**: System MUST оценивать каждый completion тремя независимыми компонентами (correctness, PRM, pedagogy).
- **FR-004**: System MUST формировать DPO pairs только within-task (chosen и rejected — completions одной задачи) для устранения cross-task confounders.
- **FR-005**: System MUST обучать adapter с минимум одной epoch на 80GB GPU без NaN, output loadable через PEFT.
- **FR-006**: System MUST производить минимум 2 ablations (−PRM, −NoSpoiler) для атрибуции вклада компонентов.
- **FR-007**: System MUST evaluate финальный adapter на (а) custom 218-task honest benchmark, (б) MathTutorBench external benchmark.
- **FR-008**: System MUST сохранять Cerebras judge scores и PRM scores в JSON-кэш с ключом sha256(prompt+completion) — повторные запуски используют кэш.
- **FR-009**: System MUST публиковать всё на HF Hub (`Siesher/mits-qwen3-9b-nsvstar-dpo`, `*-ablation-noprm`, `*-ablation-nospoiler`) с model card, описывающим composite reward weights.
- **FR-010**: System MUST документировать composite reward weights и обоснование их выбора в `research.md` (decision log + sensitivity sweep).
- **FR-011**: System MUST детерминистично восстанавливать seed_choice (best of base/GSPO/KTO) на основе Phase 0 honest report через `specs/019-ns-vstar-dpo/seed_choice.md`.

### Key Entities

- **NS-V-STaR-DPO Engine** — pipeline-orchestrator: V-STaR loop + composite scorer + DPO trainer.
- **Composite Scorer** — функция `(completion, ground_truth) → (correctness, prm_score, pedagogy_score, composite)`.
- **DPO Pair** — `{task_id, prompt, chosen, rejected, scores_chosen, scores_rejected, margin}`.
- **Honest Eval Report** — `{model_id, dataset, decoding_config, per-task results, aggregate metrics}`.
- **Ablation Manifest** — описание variant: какие weights обнулены и почему.
- **Score Cache Entry** — `{key: sha256, component: prm|pedagogy, value: float, timestamp, model_version}`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Phase 0 honest re-eval завершён — известны bf16 `accuracy / socratic_score / leak_rate` для base/GSPO/KTO в едином протоколе. Заносится в `evaluation/reports/honest_full_precision_YYYYMMDD.json`.
- **SC-002**: NS-V-STaR-DPO adapter улучшает Pareto front: либо `accuracy ≥ baseline + 1pp` без `socratic_drop > 2pp`, либо `socratic ≥ baseline + 2pp` без `accuracy_drop > 1pp` (на honest benchmark).
- **SC-003**: Ablation −PRM показывает заметное падение (≥0.5pp) по reasoning-heavy подмножеству (multi-step problems в benchmark) — изолирует вклад PRM.
- **SC-004**: Ablation −NoSpoiler показывает рост `leak_rate` (≥3pp) при сохранении accuracy — изолирует вклад pedagogy reward.
- **SC-005**: На MathTutorBench финальная модель в worst case паритетна seed baseline, в best case — улучшает на ≥2pp (external validity).
- **SC-006**: Бюджет вычислений ≤ 600 vu (RTX 6000 @ 8.71/h) → суммарно ≤ 68.9 GPU-hours включая generation, scoring, training, evaluations и ablations.
- **SC-007**: Полная воспроизводимость: dataset cards на HF + commit hashes + JSON cache scores + Modelfile/training notebook коммитнуты в репозиторий.
- **SC-008**: Diploma chapter (~10–12 pages в .docx) с honest numbers, Pareto chart, ablation table, discussion — готов к показу научному руководителю не позднее чем за 2 недели до защиты.
