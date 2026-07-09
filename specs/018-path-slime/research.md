# Research: PathSlime

**Feature**: 018-path-slime | **Date**: 2026-04-18

## R1: Dijkstra vs Bio-inspired для multi-path

**Decision**: Bio-inspired (SMA variant) как комплементарный метод, Dijkstra остаётся primary.

**Rationale**:
- Dijkstra по определению возвращает **один** оптимум (для single-source single-target с фиксированными весами). Получить k diverse paths требует либо multiple runs с pertubation (weak baseline), либо fundamentally different подход.
- Biologically, Physarum polycephalum демонстрирует **population-level diversity** — множество "рукавов" слизевика исследуют альтернативные пути одновременно (Nakagaki et al. 2000, *Nature* 407:470).
- В образовательном контексте multiple valid paths — педагогическая реальность (quick vs thorough vs example-rich), не выбираемая через single-criterion optimization.

**Alternatives considered**:
- **k-shortest paths (Yen's algorithm)**: возвращает k путей, но почти всегда они очень похожи (отличаются на 1-2 рёбра). Не решает diversity problem.
- **Random-perturbed Dijkstra**: running Dijkstra k раз с random noise на edge weights. Используется **только** как baseline для сравнения, диверсити скромная.
- **Monte Carlo Tree Search**: overkill для 83-узлового графа, primarily designed for game trees.
- **SMA + Lévy + Gaussian (наш выбор)**: экспериментально доказан для path planning (LRSMA variants 2023-24).

## R2: Выбор SMA варианта

**Decision**: Собственный **Lévy-Gaussian hybrid** (вдохновлён LRSMA и SMA-GM).

**Rationale**:
- **LRSMA** (Lévy Rotation SMA, 2023) — специально для path planning на weighted graphs. Lévy flights natively генерируют path diversity (heavy-tailed step distribution → дальние прыжки = разные пути).
- **SMA-GM** (Gaussian Mutation, 2024) — Gaussian perturbation для local refinement и anti-stagnation. Хорошо комбинируется с Lévy.
- Для нашей задачи нужно **одновременно**: (a) diversity между k colonies — Lévy, (b) local optimization внутри colony — Gaussian, (c) anti-coalescence — diversity pressure (штраф за перекрытие рёбер).

**Alternatives considered**:
- **Pure SMA** (Li 2020) — базовая версия, известна premature convergence. Отвергнута.
- **BWSMA** (2025) — Best-Worst management, designed для high-dim continuous optimization. Наш граф мал и дискретен — overkill.
- **EMSMA** (2024) — leader covariance learning, complex implementation. Отвергнута из-за сроков.
- **MISMA** (2024, Multi-Strategy) — interesting, но комбинация 3 strategies усложняет калибровку.

Выбранный подход: **простой + доказанный + специализированный под graph path planning**.

## R3: Lévy distribution для discrete graph

**Decision**: Lévy flight реализуется как **probabilistic edge selection** с heavy-tailed weight на переход.

**Rationale**:
- В continuous space Lévy flight — step length from Lévy α-stable distribution (α=1.5 typically).
- На graph у нас дискретная навигация — шаг = выбор ребра. Реализация: весa переходов масштабируются Lévy-распределённым multiplier, что приводит к occasional "long jumps" через ребра с низкой conductivity (exploration).
- Используем `scipy.stats.levy_stable(alpha=1.5, beta=0)` для генерации multipliers.

**Alternatives considered**:
- **Power-law sampling** — простая alternative к scipy.stats, но выбор α нужно калибровать вручную.
- **Gaussian steps** (без Lévy) — Gaussian декаivает быстрее, хуже для exploration.
- **Reserved: edge-relabeling** — перемаркировка вершин в continuous space для native Lévy. Слишком сложно для 83 узлов.

## R4: Diversity pressure — anti-coalescence для k colonies

**Decision**: Penalty term в fitness: `-λ × edge_overlap_ratio` где overlap — среднее число colonies, использующих то же ребро.

**Rationale**:
- Без diversity pressure все k colonies сходятся к глобальному оптимуму (Dijkstra path).
- Penalty на overlap заставляет colonies разойтись по альтернативным путям.
- Исследование: Determinantal Point Processes (DPP) в ML literature (Kulesza & Taskar 2012) используют похожий mechanism для diverse sets.
- Simple implementation: λ=0.3, overlap = mean(|path_i ∩ path_j|) / mean path length.

**Alternatives considered**:
- **Niching** (island model) — fully independent colonies без cross-talk. Даёт diversity но недоиспользует shared information.
- **Tabu list** — исключение узлов из последующих paths. Слишком жёстко, может make target unreachable.

## R5: Multi-objective fitness weights per learning style

**Decision**: 4 named styles с fixed weight profiles.

**Rationale**:
- User-facing concept "style" понятнее чем raw weights.
- Достаточно 4 вариантов для diploma scope (quick, gradual, example_rich, mixed).

| Style | length | mastery | difficulty | examples |
|-------|:------:|:-------:|:----------:|:--------:|
| quick | 0.6 | 0.2 | 0.15 | 0.05 |
| gradual | 0.25 | 0.3 | 0.35 | 0.10 |
| example_rich | 0.25 | 0.25 | 0.15 | 0.35 |
| mixed | 0.40 | 0.30 | 0.20 | 0.10 |

- Веса нормализованы, сумма = 1.0.
- "quick" приоритизирует короткий путь; "example_rich" — узлы ILLUSTRATES/EXAMPLE; "gradual" — плавное difficulty progression.

**Alternatives considered**:
- **Pareto front** — возвращать все non-dominated solutions, пусть пользователь выберет. Более "честно", но UX сложнее.
- **LLM-generated weights** — попросить LLM выбрать веса по student profile. Overkill + ещё один LLM call.

## R6: Latency budget allocation

**Decision**: 3-уровневые параметры в resource_profiles.py.

| Profile | k | colony_size | iterations | Target latency |
|---------|:-:|:-----------:|:----------:|:-------------:|
| lite | 2 | 6 | 20 | ≤1500ms CPU |
| standard | 3 | 10 | 35 | ≤500ms |
| max | 5 | 15 | 50 | ≤300ms GPU |

**Rationale**:
- Complexity estimate: O(iter × colony × edges_visited_per_step) ≈ 35 × 10 × 10 = 3500 operations per run для standard. Python pure: ~1ms per op = 350ms. ✓ укладываемся.
- Lite: 20 × 6 × 10 = 1200 operations CPU ≈ 1000ms. ✓.
- Max: 50 × 15 × 15 = 11250 operations ≈ 3000ms. Нужна numpy-векторизация для этого уровня → deferred, на диплом достаточно standard.

## Citations

| Work | Role |
|------|------|
| Nakagaki, Yamada, Tóth (2000), *Nature* 407:470 | Оригинальное открытие Physarum maze-solving |
| Tero, Kobayashi, Nakagaki (2007), *J Theor Biol* | Mathematical Physarum Solver (ODE-based) |
| Tero et al. (2010), *Science* 327:439 | Tokyo rail benchmark, applied SMA direction |
| Li, Chen, Wang, Mirjalili (2020), *FGCS* | Slime Mould Algorithm (metaheuristic form) |
| LRSMA (2023-24, MDPI Biomimetics) | Lévy-Rotation SMA для mobile robot path planning |
| SMA-GM (2024, MDPI Math) | Gaussian Mutation SMA, escape local optima |
| Viswanathan et al. (1999), *Nature* 401:911 | Lévy flights как optimal search strategy |
| Kulesza & Taskar (2012), *FnT ML* | Determinantal Point Processes for diverse sets |
| Yen (1971), *Management Science* | k-shortest paths (baseline comparison) |

## Summary of Decisions

| # | Decision | Choice |
|---|----------|--------|
| R1 | Pathfinder architecture | SMA komплементарно к Dijkstra, не замена |
| R2 | SMA variant | Lévy-Gaussian hybrid (custom, вдохновлён LRSMA + SMA-GM) |
| R3 | Lévy on discrete graph | Heavy-tailed multiplier на edge weights через `scipy.stats.levy_stable` |
| R4 | Diversity enforcement | Fitness penalty на pairwise edge overlap |
| R5 | Learning styles | 4 fixed weight profiles (quick/gradual/example_rich/mixed) |
| R6 | Resource scaling | k, colony_size, iterations адаптируются к profile |
