# GUIDE для агентов-авторов глав ВКР (общее состояние)

> Этот файл — единый источник терминологии, чисел, стиля. **Читай его ПЕРВЫМ.** Соблюдай дословно
> названия, числа и конвенции, чтобы главы были консистентны между собой.

## Тема ВКР
«Разработка интеллектуальной системы обучения STEM-дисциплинам на основе мультиагентной архитектуры
и дообученной языковой модели». Автор: Сухацкий М. О., рук. Корлякова М. О., кафедра ИУК3 МГТУ.

## Формат вывода (КРИТИЧНО)
- Файл секции: `docs/diploma/chapters/{section_id}.md`. **НЕ пиши заголовок секции** (его добавляет
  сборщик) — начинай сразу с тела.
- Подзаголовки внутри секции: `## Название` (станет Heading 3).
- Формулы: LaTeX. Inline `$E=mc^2$`, блочные `$$ ... $$`. Десятичная запятая в формулах: `55{,}1`.
- Списки: `- пункт` или `1. пункт`. Жирный `**текст**`, курсив `*текст*`.
- Таблицы: markdown `| a | b |`. Рисунки: маркер `[Рис. N: описание]` (изображения вставит автор вручную).
- Ссылки на литературу: `[N]` (номер из списка ниже). Cross-ref на разделы: «в разделе 2.3».
- Язык: академический русский; англоязычный термин — в скобках при первом упоминании
  (например «обучение с подкреплением (reinforcement learning, RL)»).

## Пайплайн обучения (4 стадии — дословно)
`Qwen3.5-9B → GSPO → KTO → DPO → V-STaR-DPO`
1. **GSPO** (Group Sequence Policy Optimization) — тройная GDPO-нормированная награда.
2. **KTO** (Kahneman-Tversky Optimization, [32]) — сократический alignment, unpaired preferences.
3. **DPO** (Direct Preference Optimization, [3]) — базовая полировка формата.
4. **V-STaR-DPO** (Phase 019) — composite scorer `correctness×0,5 + PRM×0,3 + no_spoiler×0,2`,
   within-task pairing, hard-only.

## Ключевые числа (используй ТОЛЬКО эти)
- Базовая точность Qwen3.5-9B: **55,1%** (macro). По доменам: математика 79,1%, физика 74,4%,
  химия 46,7%, информатика 46,5%, биология 28,6%.
- По стадиям: GSPO **63,5%** (+8,4 п.п.), KTO **64,8%** (+1,3), DPO **66,5%** (+1,7),
  V-STaR-DPO — `TODO[V-STaR-final]` (результаты ещё собираются).
- Обрезка completions: **100% → 14,3%** благодаря ThinkingBudgetProcessor.
- Бенчмарк: **3678 задач** = MGSM Russian (250) + ruMMLU STEM (3210) + авторский набор (218),
  5 доменов (математика, физика, химия, биология, информатика).
- Доля сократических вопросов: 34% → 61% (после KTO).
- V-STaR generation: 426 hard-задач, N=4 → 1704 траектории. Распределение n_correct бимодальное:
  0/4 — 37%, 4/4 — 48%, mixed — 15,3%. DPO-пары: **84** (A=65 correctness-mixed + B=19 completeness).
- ThinkingBudget: бюджет 1500 токенов; при 90% логит `</think>` +5,0; при 100% прочие → −∞.
- ReDit: гауссов шум σ=0,05. GSPO: LoRA r=16/α=32, lr 5·10⁻⁷, G=8, MAX_COMPLETION=2048, ε(seq)=3·10⁻⁴.
- Knowledge Tracing: mastery = 0,4·BKT + 0,5·DKT + 0,1·recency.

## Технологический стек
- Модель: Qwen3.5-9B (bf16 на A100 80GB при обучении; GGUF Q4_K_M через Ollama при деплое).
- Backend: FastAPI, SQLAlchemy 2.0, SQLite, JWT (PyJWT + Argon2), WebSocket-стриминг.
- Frontend: Next.js 14 (App Router), TypeScript, Tailwind, shadcn/ui, Zustand, KaTeX.
- Core: ChromaDB + sentence-transformers (RAG), SymPy/ChemPy (верификация), structlog.
- Агенты: Profiler → Planner → Tutor → Verifier (+ Affective, TaskGen). Knowledge Forge (граф навыков
  40+ компетенций), ToM-агент, PathSlime (slime-mold навигация), ресурсные профили.
- Обучение: Unsloth, TRL (GRPOTrainer/KTOTrainer/DPOTrainer), PEFT; Google Colab / Lightning AI.

## Источники контента (готовый текст для адаптации)
- `docs/diploma/_extracted/nir.md` (680 строк) — controlled reasoning, pipeline, результаты обучения.
- `docs/diploma/_extracted/kursovoy.md` (882 строки) — навигация: Knowledge Forge, ToM, PathSlime.
- `docs/diploma/DIPLOMA_PLAN.md` — полная структура глав + список литературы (40 источников).
- Формулы в `_extracted/*.md` были картинками → **дописывай как LaTeX вручную**.

## Список литературы (ключевые номера для ссылок [N])
1 VanLehn (2011) ITS effectiveness · 2 Qwen3 Technical Report · 3 Rafailov DPO · 4 Shao DeepSeekMath GRPO ·
5 Corbett&Anderson BKT · 6 Piech DKT · 8 Sweller CLT · 15 Bloom · 16 Vygotsky ZPD ·
21 Vaswani Attention · 23 Wei CoT · 25 Guo DeepSeek-R1 · 26 Schulman PPO · 27 Ouyang InstructGPT ·
28 Hu LoRA · 32 Ethayarajh KTO · 33 Tversky&Kahneman Prospect Theory · 34 Hosseini V-STaR ·
35 Wang Math-Shepherd · 37 Cobbe GSM8K · 38 Hendrycks MMLU · 39 Shi MGSM. (полный список — DIPLOMA_PLAN.md)

## Объём (ориентир, не жёстко)
Целевые объёмы секций — в placeholder'ах внутри `STRUCTURE` (`scripts/build_vkr_skeleton.py`). Пиши
содержательно, академически; placeholder в .docx будет заменён твоим контентом.
