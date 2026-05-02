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

После Phase 0 запускается основная новая методология (lean-demo scope): с seed-чекпоинта (выбранного на основе honest eval как лучшего предка для self-training) генерируется N=4 ответа на **1000 stratified-by-(domain, difficulty) задач** из 3875 сократических диалогов, каждый ответ оценивается тремя независимыми компонентами:

1. **Correctness** — programmatic verify (SymPy/ChemPy) + final-answer match с `ground_truth`
2. **Step-level reasoning** — `Skywork/Skywork-o1-Open-PRM-Qwen-2.5-1.5B` aggregate score по шагам (1.5B — fast, tuned для o1-style thinking traces)
3. **Pedagogy** — Cerebras Combined Judge (no_answer_leak, scaffolding, engagement)

Композитный score = `w₁·correctness + w₂·PRM + w₃·pedagogy` с **зафиксированными весами `(0.5, 0.25, 0.25)`** по принципиальному обоснованию (Decision 2 в research.md), без emпирического sweep (резерв compute → reserve для retries). **Within-task pairing**: top-vs-bottom 1 пара per task → до 1000 DPO-пар (или 0, если top-bottom margin < τ). Тренируется final adapter `Siesher/mits-qwen3-9b-nsvstar-dpo` на A100 80GB / RTX 6000 Pro 96GB.

**Why this priority**: Это main contribution — метод, защищаемый в дипломе. Содержит весь scientific novelty.

**Independent Test**: Прогнать full pipeline на 200-задачной mini-subset, получить ≥1 valid pair per task в 80% случаев, тренировка на mini завершается без NaN, eval на benchmark показывает Δaccuracy or Δsocratic ≥ +1pp относительно best-of-three baseline.

**Acceptance Scenarios**:

1. **Given** seed checkpoint и 3875 задач, **When** vstar_generate с N=4, **Then** получено 15500 completions с metadata.
2. **Given** completions, **When** scored 3 компонентами, **Then** для ≥80% задач есть pair с `composite_margin ≥ τ`.
3. **Given** DPO-pairs, **When** train run завершён 1 epoch на A100, **Then** loss падает монотонно, no NaN, output adapter loadable через `PeftModel.from_pretrained`.
4. **Given** trained adapter, **When** evaluated на honest benchmark, **Then** Pareto-улучшение хотя бы по одной из axis (accuracy / pedagogy) без регресса >2pp по другой.

---

### User Story 3 — Single ablation `-PRM` (Priority: P2)

Чтобы доказать **наш delta** относительно литературы (а не "просто работает"), нужен один ablation run: тренировка с `w₂=0` (без PRM-component, остаются correctness + pedagogy). Это изолирует вклад **PRM-добавки** — нашей основной научной новизны поверх уже опубликованной No-Spoiler RL работы (arXiv:2505.15607). `-NoSpoiler` ablation **не делаем** — pedagogy-reward effect уже доказан в No-Spoiler paper, повторять не нужно.

**Why this priority**: Без `-PRM` ablation рецензент справедливо спросит "а PRM-component реально что-то добавляет, или composite reward работает только за счёт No-Spoiler части?". Single ablation отвечает на этот вопрос с минимальным compute.

**Why NOT `-NoSpoiler`**: повторяет опубликованную работу. **Why NOT joint `-PRM-NoSpoiler` (correctness-only DPO)**: тоже эквивалентно стандартному outcome-only DPO, известному с 2023.

**Independent Test**: Получить два adapter: full NS-V-STaR-DPO, −PRM. На едином benchmark измерить разницу. Difference интерпретируется как "вклад PRM-component".

**Acceptance Scenarios**:

1. **Given** оба adapters trained, **When** evaluated на honest benchmark + MathTutorBench-spot, **Then** results показывают direction-of-effect для PRM-component.
2. **Given** ablation result, **When** statistical analysis на 218-task benchmark, **Then** даже с wide CI (lean scope) сохраняется monotonic ordering: full > -PRM > seed_baseline (или фиксируется null result с честным репортом).

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
- **PRM 1.5B + tutor 9B на 96GB GPU**: 3GB + 22GB + KV cache 30GB ≈ 55GB → comfortable headroom; co-located scoring в одной сессии.
- **Cerebras rate limit при judge calls**: rotating pool из 10 ключей (уже реализован в `training/cerebras_client.py`), exponential backoff, persistent cache scores → JSON.
- **MathTutorBench не имеет Russian split**: используем English 100-task spot check как external validity sanity, custom 218-task benchmark остаётся primary для in-language claims; документировать в `research.md`.
- **Stratified 1000-subset не покрывает редкие домены**: если в `dialogs.jsonl` есть domain c <100 примеров, включаем все имеющиеся (без strict 1000 cap); документируем в `subset_manifest.json`.
- **Single-ablation null result** (`-PRM` adapter ≈ full): репортуем честно как negative finding, обсуждаем в Discussion как possible cause (PRM-component уже учится из correctness via in-distribution generation; PRM добавка noise-level). Это **acceptable for diploma** — научная честность.
- **Compute budget overrun (>200 vu в lean scope)**: fallback — N=4 → N=3 (теряем 25% pairs); далее — subset 1000 → 500 tasks. Резерв 460 vu обеспечивает comfortable retry buffer.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST произвести bf16 re-eval base/GSPO/KTO с identical decoding protocol до любого нового обучения.
- **FR-002**: System MUST генерировать N=4 completions per task через V-STaR loop от выбранного seed checkpoint, на **stratified-by-(domain, difficulty) 1000-task subset** из 3875 dialogs.
- **FR-003**: System MUST оценивать каждый completion тремя независимыми компонентами (correctness, PRM via **Skywork-o1-Open-PRM-Qwen-2.5-1.5B**, pedagogy via Cerebras Combined Judge).
- **FR-004**: System MUST формировать DPO pairs только within-task (chosen и rejected — completions одной задачи) для устранения cross-task confounders.
- **FR-005**: System MUST обучать adapter с минимум одной epoch на 80GB+ GPU без NaN, output loadable через PEFT.
- **FR-006**: System MUST производить **минимум 1 ablation (`-PRM`)** для атрибуции вклада PRM-component относительно baseline No-Spoiler работы.
- **FR-007**: System MUST evaluate финальный adapter на (а) custom 218-task honest benchmark, (б) **100-task MathTutorBench spot check** (external validity sanity).
- **FR-008**: System MUST сохранять Cerebras judge scores и PRM scores в JSON-кэш с ключом sha256(model_id+prompt+completion) — повторные запуски используют кэш.
- **FR-009**: System MUST публиковать на HF Hub (`Siesher/mits-qwen3-9b-nsvstar-dpo`, `*-ablation-noprm`) с model card, описывающим composite reward weights и subset manifest.
- **FR-010**: System MUST документировать composite reward weights `(0.5, 0.25, 0.25)` как **principled defaults** (Decision 2) — без эмпирического sensitivity sweep в lean scope.
- **FR-011**: System MUST детерминистично восстанавливать seed_choice (best of base/GSPO/KTO) на основе Phase 0 honest report через `specs/019-ns-vstar-dpo/seed_choice.md`.
- **FR-012**: System MUST publish stratified subset manifest (`data/vstar/subset_manifest.json`) с list of task_ids и proportion per (domain, difficulty) — для воспроизводимости и пояснения lean scope в diploma.

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
- **SC-002**: NS-V-STaR-DPO adapter показывает direction-of-effect (lean-demo target, не SOTA): любое монотонное улучшение хотя бы по одной axis (accuracy ≥ baseline + 0.5pp ИЛИ socratic ≥ baseline + 1pp) без катастрофической регрессии (≤2pp drop) по другой. Wide CI допустим — задача demonstrate workability.
- **SC-003**: Ablation `-PRM` показывает наблюдаемую разницу (≥0.3pp по reasoning subset ИЛИ изменение pedagogy ≥0.3pp) — direction-of-effect для PRM-component, даже если CI не пересекает ноль с p<0.05 на 1000-subset.
- **SC-004**: На MathTutorBench-100 spot check финальная модель не показывает крупной деградации (worst case паритетна seed baseline на ±2pp) — sanity check external validity, без претензии на peer-comparable claim.
- **SC-005**: Бюджет вычислений ≤ 200 vu (RTX 6000 Pro 96GB @ 8.71/h) → суммарно ≤ 23 GPU-hours; реальная цель ~140 vu, остальное — резерв на retries.
- **SC-006**: Полная воспроизводимость: dataset cards на HF (subset manifest c task_ids) + commit hashes + JSON cache scores + training notebook коммитнуты в репозиторий.
- **SC-007**: Diploma chapter (~10–12 pages в .docx) с honest numbers, Pareto chart, single-ablation table, **explicit "Limitations" section** обсуждающий lean-scope decisions — готов к показу научному руководителю не позднее чем за 2 недели до защиты.
- **SC-008**: Section "Future Work" в diploma chapter включает: full-scale 3875-task replication, second ablation `-NoSpoiler` для completeness, multi-seed V-STaR, sensitivity sweep по reward weights — фиксирует scope для extended paper версии.
