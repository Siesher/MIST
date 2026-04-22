#!/usr/bin/env python3
"""
Расширитель академических документов — добавляет существенное содержимое
(псевдокод, примеры, разбор результатов, большой код в приложения)
после генерации базового скелета через generate_diploma_docs.py.

Usage:
    python scripts/generate_diploma_docs.py   # сначала базовый скелет
    python scripts/extend_diploma_docs.py     # потом расширение
"""

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt

DOCS_DIR = Path("docs")


def add_para(doc, text: str, indent: float = 1.25) -> None:
    p = doc.add_paragraph(text)
    p.paragraph_format.first_line_indent = Cm(indent)
    p.paragraph_format.line_spacing = 1.5


def add_code(doc, code: str) -> None:
    p = doc.add_paragraph(code)
    p.paragraph_format.line_spacing = 1.0
    p.paragraph_format.left_indent = Cm(0.5)
    for run in p.runs:
        run.font.name = "Consolas"
        run.font.size = Pt(10)


def add_heading_safe(doc, text: str, level: int = 2) -> None:
    h = doc.add_heading(text, level=level)
    h.alignment = WD_ALIGN_PARAGRAPH.LEFT


def extend_nir() -> None:
    """Дописать НИР с подробным содержимым."""
    path = DOCS_DIR / "НИР_Сухацкий_2026_knowledge_forge.docx"
    doc = Document(str(path))

    # ── Приложение А — расширенный код и разбор ─────────────
    doc.add_page_break()
    add_heading_safe(doc, "ПРИЛОЖЕНИЕ А — Ключевые алгоритмы и фрагменты кода", level=1)

    # A.1 — псевдокод SessionAnalyzer
    add_heading_safe(doc, "А.1. Псевдокод модуля анализа тьюторских сессий", level=2)
    add_para(
        doc,
        "Модуль SessionAnalyzer извлекает предложения об эволюции "
        "графа из трассы реальной тьюторской сессии. Ниже приведён "
        "псевдокод основной функции analyze() на языке Python.",
    )
    add_code(
        doc,
        "def analyze(self, trace: SessionTrace) -> List[GraphProposal]:\n"
        '    """Извлечь предложения по изменению графа из сессии."""\n'
        "    proposals: List[GraphProposal] = []\n"
        "    # Сигнал 1: пропущенный prerequisite\n"
        "    proposals.extend(self._detect_missed_prerequisites(trace))\n"
        "    # Сигнал 2: новая misconception (по content-hash key)\n"
        "    proposals.extend(self._detect_new_misconceptions(trace))\n"
        "    # Сигнал 3: чередование ошибок между концептами\n"
        "    proposals.extend(self._detect_confusion_patterns(trace))\n"
        "    # Сигнал 4: ускоренное усвоение после prereq\n"
        "    proposals.extend(self._detect_pedagogical_ordering(trace))\n"
        "    return proposals\n"
        "\n"
        "def _detect_missed_prerequisites(self, trace):\n"
        '    """Ученик провалил topic X, также ошибся в C, но graph\n'
        '    не предсказывал C как prereq для X."""\n'
        "    if trace.resolved or not trace.errors:\n"
        "        return []\n"
        "    gap = self._nav.diagnose_gap(trace.student_id, trace.topic_id)\n"
        "    predicted_missing = set(gap.missing_prerequisites)\n"
        "    proposals = []\n"
        "    for error in trace.errors:\n"
        "        err_concept = error.get('concept_id')\n"
        "        if err_concept in predicted_missing or err_concept == trace.topic_id:\n"
        "            continue\n"
        "        if not self._graph.get_node(err_concept):\n"
        "            continue\n"
        "        if self._graph.has_edge(err_concept, trace.topic_id, PREREQUISITE):\n"
        "            continue  # уже есть\n"
        "        prop = GraphProposal(kind=NEW_EDGE, payload={...})\n"
        "        prop.add_evidence(trace.session_id, reason='missed_prereq')\n"
        "        proposals.append(prop)\n"
        "    return proposals\n",
    )

    # A.2 — псевдокод rule-based verifier
    add_heading_safe(doc, "А.2. Rule-based верификатор предложений", level=2)
    add_para(
        doc,
        "Верификатор rule_based_verifier проверяет педагогическую "
        "корректность предложения до его мерджа в граф. Ключевое "
        "правило — предотвращение циклов в prerequisite-отношениях.",
    )
    add_code(
        doc,
        "def rule_based_verifier(proposal, graph) -> Tuple[bool, str]:\n"
        "    p = proposal.payload\n"
        "    if proposal.kind == NEW_NODE:\n"
        "        existing = graph.get_node(p['id'])\n"
        "        if existing and existing.confidence >= proposal.confidence:\n"
        "            return False, 'node exists with higher confidence'\n"
        "        if len(p.get('content', '')) < 15:\n"
        "            return False, 'content too short'\n"
        "        return True, 'new_node passes rules'\n"
        "\n"
        "    if proposal.kind == NEW_EDGE:\n"
        "        src, tgt, et = p['source_id'], p['target_id'], p['edge_type']\n"
        "        if not graph.get_node(src) or not graph.get_node(tgt):\n"
        "            return False, 'endpoint missing'\n"
        "        if src == tgt:\n"
        "            return False, 'self-loop'\n"
        "        try:\n"
        "            et_enum = EdgeType(et)\n"
        "        except ValueError:\n"
        "            return False, f'unknown edge_type: {et}'\n"
        "        if graph.has_edge(src, tgt, et_enum):\n"
        "            return False, 'edge already exists'\n"
        "        # Cycle prevention for PREREQUISITE edges\n"
        "        if et_enum == PREREQUISITE:\n"
        "            reverse_path = graph.find_path(\n"
        "                tgt, src, edge_types=[PREREQUISITE])\n"
        "            if reverse_path:\n"
        "                return False, 'would create prerequisite cycle'\n"
        "        return True, 'new_edge passes rules'\n"
        "    return False, f'unknown kind: {proposal.kind}'\n",
    )

    # A.3 — полный промпт ToM (full variant)
    add_heading_safe(doc, "А.3. Полный промпт ToM-агента (standard/max профиль)", level=2)
    add_para(
        doc,
        "Системная часть промпта явно перечисляет 5 признаков активной "
        "misconception, что критично для повышения detection recall.",
    )
    add_code(
        doc,
        "SYSTEM: You are a cognitive scientist modeling a Russian-speaking\n"
        "student's mental state during STEM tutoring. Your analysis will\n"
        "drive teaching decisions. Reason step-by-step in 3 stages\n"
        "(misconception -> topic belief -> reaction prediction), then\n"
        "output a single JSON object. All content in Russian. Keys in English.\n"
        "\n"
        "CRITICAL: Actively identify error patterns when student shows\n"
        "ANY of these signs:\n"
        "- States a wrong mathematical/logical fact as true\n"
        "- Applies a rule incorrectly (wrong sign, operation, formula)\n"
        "- Over-generalizes (e.g. treats nonlinear as linear)\n"
        "- Confuses similar-looking concepts\n"
        "- Shows gap in foundational understanding\n"
        "Default to IDENTIFYING the error pattern, not to null.\n"
        "Set active_misconception=null ONLY when student asks a genuine\n"
        "open question without demonstrating any wrong belief.\n"
        "\n"
        "Confidence rubric:\n"
        "- 0.8+ if student explicitly demonstrated the error\n"
        "- 0.5-0.8 for strong inference from error pattern\n"
        "- 0.2-0.5 for weak signal\n"
        "- 0.0-0.2 if truly no usable signal\n",
    )

    # A.4 — псевдокод PathSlime.run
    add_heading_safe(doc, "А.4. Главный цикл PathSlime", level=2)
    add_para(
        doc,
        "Ниже приведён полный псевдокод метода run() класса PathSlime. "
        "Ключевая особенность — early_stop по patience и timeout-check.",
    )
    add_code(
        doc,
        "def run(self, target_id: str, style: str = 'mixed') -> AlternativePaths:\n"
        "    t_start = time.perf_counter()\n"
        "    if self.graph.get_node(target_id) is None:\n"
        "        return AlternativePaths(target=target_id, paths=[],\n"
        "                                error='target not found')\n"
        "    style_cfg = STYLES.get(style) or STYLES['mixed']\n"
        "\n"
        "    # Trivial case: target already mastered\n"
        "    if self.mastery.get(target_id, 0.0) >= 0.7:\n"
        "        return AlternativePaths(..., diversity_score=1.0)\n"
        "\n"
        "    # Initialize k colonies with random sampled paths\n"
        "    colonies = []\n"
        "    for i in range(self.config.k):\n"
        "        col = self._spawn_colony(i, target_id)\n"
        "        if col and col.path:\n"
        "            col.fitness = self._fitness(col.path, style_cfg, colonies[:i])\n"
        "            colonies.append(col)\n"
        "    if not colonies:\n"
        "        return self._dijkstra_fallback(target_id, style, t_start)\n"
        "\n"
        "    best_fitness_history = []\n"
        "    truncated = False\n"
        "    for iteration in range(self.config.max_iterations):\n"
        "        elapsed_ms = (time.perf_counter() - t_start) * 1000\n"
        "        if elapsed_ms > self.config.timeout_ms:\n"
        "            truncated = True\n"
        "            break\n"
        "        # Evolve each colony (50% Levy, 50% Gaussian)\n"
        "        for col in colonies:\n"
        "            self._evolve_colony(col, target_id, style_cfg, colonies)\n"
        "        # Early stop: no improvement for `patience` iterations\n"
        "        cur_best = max(c.fitness for c in colonies)\n"
        "        best_fitness_history.append(cur_best)\n"
        "        if len(best_fitness_history) > self.config.early_stop_patience:\n"
        "            recent = best_fitness_history[-self.config.early_stop_patience:]\n"
        "            if max(recent) - min(recent) < 1e-4:\n"
        "                break\n"
        "\n"
        "    unique_paths = self._deduplicate(colonies)\n"
        "    diversity = self._diversity_score(unique_paths)\n"
        "    return AlternativePaths(\n"
        "        target=target_id, paths=self._convert_paths(unique_paths),\n"
        "        diversity_score=diversity, style=style,\n"
        "        truncated=truncated, iterations_run=iteration + 1,\n"
        "        elapsed_ms=(time.perf_counter() - t_start) * 1000)\n",
    )

    # A.5 — псевдокод Lévy sampling (Mantegna 1994)
    add_heading_safe(doc, "А.5. Алгоритм Mantegna (1994) для Lévy-sampling", level=2)
    add_para(
        doc,
        "Алгоритм Mantegna — быстрый приближённый метод генерации "
        "Lévy-stable samples через отношение нормально распределённых "
        "величин. Работает для α ∈ (0, 2], включая наш диапазон α = 1,5.",
    )
    add_code(
        doc,
        "def levy_multiplier(alpha: float = 1.5, n: int = 1,\n"
        "                   rng: Optional[np.random.Generator] = None) -> np.ndarray:\n"
        '    """Генерация n samples из Lévy-stable distribution."""\n'
        "    from math import gamma, pi, sin\n"
        "    if rng is None:\n"
        "        rng = np.random.default_rng()\n"
        "    # Mantegna 1994 — sigma_u for Gaussian numerator\n"
        "    sigma_u = (\n"
        "        gamma(1 + alpha) * sin(pi * alpha / 2) /\n"
        "        (gamma((1 + alpha) / 2) * alpha * 2 ** ((alpha - 1) / 2))\n"
        "    ) ** (1 / alpha)\n"
        "    u = rng.normal(0, sigma_u, n)\n"
        "    v = rng.normal(0, 1, n)\n"
        "    # Absolute value: positive multipliers для scaling рёбер\n"
        "    samples = np.abs(u / (np.abs(v) ** (1 / alpha)))\n"
        "    return np.clip(samples, MIN_MULTIPLIER, MAX_MULTIPLIER)\n",
    )

    # A.6 — разбор одного failure scenario
    add_heading_safe(doc, "А.6. Разбор provavшей misconception detection", level=2)
    add_para(
        doc,
        "Из 20 экспериментальных сценариев единственный, оставшийся с "
        "miss после tuning промпта — «what_is_function». Разбор показывает "
        "природу этой ошибки:",
    )
    add_para(
        doc,
        "Входное сообщение ученика: «А что такое функция? Это просто "
        "формула с x, подставил число и получил другое число?»",
    )
    add_para(
        doc,
        "Ожидаемый root gap: `math:functions_basics:definition`. "
        "Baseline Dijkstra возвращает `math:linear_equations:definition` "
        "(по глубине). ToM с conf=0.85 тоже выбрал linear_equations: "
        "LLM распознал misconception («функция = подстановка в формулу»), "
        "но LLM-ranking предпочёл более глубокий prereq в цепочке.",
    )
    add_para(
        doc,
        "Анализ показывает, что в конкретном графе linear_equations "
        "появляется на несколько слоёв глубже чем functions_basics, но "
        "педагогически релевантен functions_basics. Это указывает на "
        "направление дальнейших исследований: добавить в промпт "
        "LLM-ранжирования контекст о том, какая пререкизит «ближе» к "
        "целевому концепту по семантическому смыслу, а не только по "
        "структуре графа.",
    )

    # A.7 — Таблица всех 20 ToM scenarios
    doc.add_page_break()
    add_heading_safe(doc, "А.7. Полная таблица 20 экспериментальных сценариев ToM", level=2)
    add_para(doc, "Полный список сценариев, использованных в A/B-оценке ToM-Tutor:")
    scenarios_data = [
        ("product_rule_explicit", "explicit", "intermediate", "derivatives_basic", "HIT"),
        ("chain_rule_explicit", "explicit", "intermediate", "chain_rule", "HIT"),
        ("integral_constant_omission", "explicit", "intermediate", "antiderivatives", "HIT"),
        ("linear_sign_error", "explicit", "entry", "linear_equations", "HIT"),
        ("fraction_confusion_at_percentages", "explicit", "entry", "percentages", "HIT"),
        ("power_to_power_error", "explicit", "intermediate", "exponential_functions", "HIT"),
        ("limits_intuition_confused", "confused", "intermediate", "derivatives_definition", "HIT"),
        ("what_is_function", "open_question", "entry", "derivatives_basic", "miss"),
        ("cold_start_variables", "open_question", "entry", "quadratic_equations", "HIT"),
        ("trig_basic_confusion", "confused", "intermediate", "trig_basics", "HIT"),
        (
            "confident_wrong_quadratic_with_gap",
            "confident_wrong",
            "intermediate",
            "quadratic_equations",
            "HIT",
        ),
        (
            "confident_wrong_derivative",
            "confident_wrong",
            "intermediate",
            "derivatives_basic",
            "HIT",
        ),
        ("missing_factoring_prereq", "explicit", "intermediate", "factoring", "HIT"),
        ("percentages_needs_fractions", "open_question", "entry", "percentages", "HIT"),
        ("logarithm_needs_exponential", "confused", "advanced", "logarithms", "HIT"),
        ("systems_needs_linear", "explicit", "intermediate", "systems_of_equations", "HIT"),
        (
            "inverse_needs_functions_basics",
            "confused",
            "intermediate",
            "function_transformations",
            "HIT",
        ),
        ("implicit_diff_needs_chain", "confused", "advanced", "implicit_differentiation", "HIT"),
        ("trig_identity_needs_basics", "explicit", "intermediate", "trig_identities", "HIT"),
        ("recursion_needs_functions", "confused", "intermediate", "recursion", "HIT"),
    ]
    table = doc.add_table(rows=len(scenarios_data) + 1, cols=5)
    table.style = "Table Grid"
    headers = ["Сценарий", "Категория", "Сложность", "Целевой концепт", "Итог"]
    for i, h in enumerate(headers):
        table.rows[0].cells[i].text = h
        for p in table.rows[0].cells[i].paragraphs:
            for run in p.runs:
                run.bold = True
    for r_idx, row in enumerate(scenarios_data):
        for c_idx, v in enumerate(row):
            table.rows[r_idx + 1].cells[c_idx].text = str(v)

    # ─── Дополнительные разделы в Главе 3 — детальный разбор
    # Add more context in section 3.3 если осталось место
    doc.add_page_break()
    add_heading_safe(doc, "А.8. Архитектурная диаграмма пайплайна", level=2)
    add_para(
        doc,
        "Ниже приведена ASCII-диаграмма многоагентного пайплайна MITS "
        "с новой стадией MENTAL_MODEL:",
    )
    add_code(
        doc,
        "Входное сообщение ученика\n"
        "    ↓\n"
        "1. ROUTING     — классификация запроса (QUESTION/ANSWER/HINT/...)\n"
        "    ↓\n"
        "2. PROFILER    — диагностика ошибок, когнитивной нагрузки\n"
        "                 → StudentProfile\n"
        "    ↓\n"
        "3. MENTAL_MODEL ← НОВАЯ СТАДИЯ (фича 017)\n"
        "                 → BeliefState с predicted_reactions\n"
        "    ↓\n"
        "4. GRAPH_NAV   — загрузка context из Knowledge Forge\n"
        "                 (diagnose_gap с ToM re-ranking)\n"
        "    ↓\n"
        "5. PLANNER     — выбор стратегии с учётом belief_state\n"
        "                 → TeachingPlan\n"
        "    ↓\n"
        "6. RAG         — backup извлечение (legacy, fallback)\n"
        "    ↓\n"
        "7. TUTOR       — генерация ответа с tool calling\n"
        "                 (SKI + Navigator tools, включая find_alternative_paths)\n"
        "    ↓\n"
        "8. VERIFIER    — контроль качества\n"
        "    ↓\n"
        "Ответ ученику\n",
    )

    doc.save(str(path))
    print(f"  Extended: {path}")


def extend_coursework() -> None:
    """Дописать Курсовой проект."""
    path = DOCS_DIR / "Курсовой_проект_Сухацкий_2026.docx"
    doc = Document(str(path))

    # Extend Приложение А
    doc.add_page_break()
    add_heading_safe(doc, "ПРИЛОЖЕНИЕ Б — Дополнительные фрагменты исходного кода", level=1)

    add_heading_safe(doc, "Б.1. Dataclass BeliefState (src/data/schemas.py)", level=2)
    add_code(
        doc,
        "class BeliefState(BaseModel):\n"
        '    """Ephemeral snapshot of student\'s mental state."""\n'
        "    active_misconception: Optional[str] = None\n"
        "    active_misconception_node_id: Optional[str] = None\n"
        "    belief_about_topic: str = ''\n"
        "    predicted_reactions: Dict[str, str] = Field(default_factory=dict)\n"
        "    candidate_misconceptions: List[str] = Field(default_factory=list)\n"
        "    confidence: float = Field(default=0.0, ge=0.0, le=1.0)\n"
        "    reasoning: str = ''\n"
        "    generated_at: str = Field(\n"
        "        default_factory=lambda: datetime.now().isoformat())\n"
        "    profile_used: str = ''\n"
        "\n"
        "    @classmethod\n"
        "    def empty(cls, profile_name: str = '') -> 'BeliefState':\n"
        "        return cls(active_misconception=None, belief_about_topic='',\n"
        "                   predicted_reactions={}, confidence=0.0,\n"
        "                   reasoning='', profile_used=profile_name)\n"
        "\n"
        "    def is_usable(self, min_confidence: float = 0.3) -> bool:\n"
        "        return self.confidence >= min_confidence\n",
    )

    add_heading_safe(doc, "Б.2. Navigator.diagnose_gap() с ToM re-ranking", level=2)
    add_code(
        doc,
        "def diagnose_gap(self, student_id: str, failed_concept_id: str,\n"
        "                 belief_state: Optional['BeliefState'] = None\n"
        "                ) -> GapDiagnosis:\n"
        '    """Диагностика пробела с опциональным ToM re-ranking."""\n'
        "    all_mastery = self._mastery.get_all_mastery(student_id)\n"
        "    missing: List[Tuple[str, int]] = []  # (node_id, depth)\n"
        "    visited: Set[str] = set()\n"
        "    def _collect_gaps(node_id: str, depth: int) -> None:\n"
        "        if node_id in visited:\n"
        "            return\n"
        "        visited.add(node_id)\n"
        "        prereqs = self._graph.get_neighbors(\n"
        "            node_id, edge_type=PREREQUISITE, direction='incoming')\n"
        "        for _, prereq_node in prereqs:\n"
        "            mastery = all_mastery.get(prereq_node.id, MASTERY_UNKNOWN)\n"
        "            if mastery < MASTERY_THRESHOLD:\n"
        "                missing.append((prereq_node.id, depth + 1))\n"
        "                _collect_gaps(prereq_node.id, depth + 1)\n"
        "    _collect_gaps(failed_concept_id, 0)\n"
        "    # ToM-aware re-ranking (017)\n"
        "    if belief_state and belief_state.is_usable(min_confidence=0.5):\n"
        "        missing = self._rerank_by_belief(missing, belief_state, all_mastery)\n"
        "    else:\n"
        "        missing.sort(key=lambda x: -x[1])  # depth DESC\n"
        "    root_gap = missing[0][0] if missing else None\n"
        "    return GapDiagnosis(failed_concept=failed_concept_id,\n"
        "                        missing_prerequisites=[m[0] for m in missing],\n"
        "                        root_gap=root_gap, ...)\n",
    )

    add_heading_safe(doc, "Б.3. PathSlime._sample_path() — генерация пути с Lévy", level=2)
    add_code(
        doc,
        "def _sample_path(self, start: str, target: str,\n"
        "                 max_len: int = 15) -> List[str]:\n"
        '    """Сгенерировать random walk start -> target с Lévy."""\n'
        "    reachable = self.graph.find_path(start, target,\n"
        "                                     edge_types=[PREREQUISITE])\n"
        "    if reachable is None:\n"
        "        return []\n"
        "    path = [start]\n"
        "    current = start\n"
        "    visited = {start}\n"
        "    for _ in range(max_len):\n"
        "        if current == target:\n"
        "            return path\n"
        "        outgoing = self._outgoing_prereqs(current)\n"
        "        candidates = [n for n in outgoing if n not in visited]\n"
        "        if not candidates:\n"
        "            break\n"
        "        # КРИТИЧНО: отфильтровать кандидатов с недостижимым target\n"
        "        reachable_cands = []\n"
        "        reachable_rest_len = []\n"
        "        for cand in candidates:\n"
        "            if cand == target:\n"
        "                reachable_cands.append(cand)\n"
        "                reachable_rest_len.append(0)\n"
        "                continue\n"
        "            rest = self.graph.find_path(cand, target,\n"
        "                                        edge_types=[PREREQUISITE])\n"
        "            if rest is not None:\n"
        "                reachable_cands.append(cand)\n"
        "                reachable_rest_len.append(len(rest))\n"
        "        if not reachable_cands:\n"
        "            break\n"
        "        # Score + Lévy perturbation\n"
        "        candidates = reachable_cands\n"
        "        scores = [10.0 if rl == 0 else 0.3 + 1.0 / (rl + 1)\n"
        "                  for rl in reachable_rest_len]\n"
        "        weights = np.array(scores)\n"
        "        levy = levy_multiplier(alpha=self.config.levy_alpha,\n"
        "                               n=len(candidates), rng=self._rng)\n"
        "        perturbed = weights * levy\n"
        "        perturbed = perturbed / perturbed.sum()\n"
        "        chosen_idx = int(self._rng.choice(len(candidates), p=perturbed))\n"
        "        current = candidates[chosen_idx]\n"
        "        path.append(current)\n"
        "        visited.add(current)\n"
        "    # Finish: shortest path от last node если не дошли\n"
        "    if path[-1] != target:\n"
        "        finish = self.graph.find_path(path[-1], target,\n"
        "                                      edge_types=[PREREQUISITE])\n"
        "        if finish:\n"
        "            for nid in finish[1:]:\n"
        "                if nid not in visited:\n"
        "                    path.append(nid)\n"
        "                    visited.add(nid)\n"
        "    return path if path[-1] == target else []\n",
    )

    add_heading_safe(doc, "Б.4. Интеграция MENTAL_MODEL stage в оркестраторе", level=2)
    add_code(
        doc,
        "# В AgentOrchestrator.process(), между PROFILER и GRAPH_NAV:\n"
        "belief_state = None\n"
        "try:\n"
        "    from src.data.schemas import BeliefState as _BeliefState\n"
        "    from src.resource_profiles import feature_enabled\n"
        "    if (feature_enabled('enable_tom_agent')\n"
        "        and self.mental_model_agent is not None\n"
        "        and profile is not None):\n"
        "        mm_stage = trace.start_stage(AgentStage.MENTAL_MODEL)\n"
        "        try:\n"
        "            belief_state = self.mental_model_agent.infer(\n"
        "                student_message=context.student_input,\n"
        "                student_profile=profile,\n"
        "                history=session.recent_turns(3) if session else [],\n"
        "                graph_context=graph_context,\n"
        "                topic=context.topic or '')\n"
        "            mm_stage.complete(True,\n"
        "                output_summary=f'conf={belief_state.confidence:.2f}')\n"
        "        except Exception as e:\n"
        "            mm_stage.complete(False, error=str(e))\n"
        "            belief_state = _BeliefState.empty()\n"
        "except ImportError:\n"
        "    pass\n"
        "\n"
        "# Далее в PLANNER stage:\n"
        "plan = self.planner.create_plan(\n"
        "    profile=profile or StudentProfile(),\n"
        "    context=planner_context,\n"
        "    graph_context=graph_context,\n"
        "    belief_state=belief_state)  # NEW parameter\n",
    )

    add_heading_safe(doc, "Б.5. Скрипт миграции skill_graph в Knowledge Forge", level=2)
    add_code(
        doc,
        "# scripts/migrate_to_forge.py — фрагмент migrate_skill_graph()\n"
        "def migrate_skill_graph(graph: KnowledgeGraph) -> int:\n"
        '    """Перенос SKILL_GRAPH в граф знаний — 51 концепт + рёбра."""\n'
        "    added, skipped = 0, 0\n"
        "    # Phase 1: nodes\n"
        "    for skill_id, skill_data in SKILL_GRAPH.items():\n"
        "        category = skill_data.get('category', 'math')\n"
        "        node_id = f'{category}:{skill_id}:definition'\n"
        "        if graph.get_node(node_id) is not None:\n"
        "            skipped += 1\n"
        "            continue\n"
        "        node = KnowledgeNode(\n"
        "            id=node_id, node_type=NodeType.CONCEPT,\n"
        "            title=skill_data.get('name_ru', skill_data['name']),\n"
        "            title_en=skill_data['name'],\n"
        "            content=f'Определение: {...}',\n"
        "            domain=category,\n"
        "            difficulty=skill_data.get('difficulty', 0.5),\n"
        "            source='skill_graph_migration',\n"
        "            confidence=1.0)\n"
        "        graph.add_node(node)\n"
        "        added += 1\n"
        "    # Phase 2: edges PREREQUISITE\n"
        "    edges_added = 0\n"
        "    for skill_id, skill_data in SKILL_GRAPH.items():\n"
        "        category = skill_data.get('category', 'math')\n"
        "        target_id = f'{category}:{skill_id}:definition'\n"
        "        for prereq_id in skill_data.get('prerequisites', []):\n"
        "            prereq_data = SKILL_GRAPH.get(prereq_id)\n"
        "            if prereq_data is None:\n"
        "                continue\n"
        "            source_id = f'{prereq_data[\"category\"]}:{prereq_id}:definition'\n"
        "            if graph.has_edge(source_id, target_id, EdgeType.PREREQUISITE):\n"
        "                continue\n"
        "            graph.add_edge(KnowledgeEdge(\n"
        "                source_id=source_id, target_id=target_id,\n"
        "                edge_type=EdgeType.PREREQUISITE))\n"
        "            edges_added += 1\n"
        "    return added, edges_added  # 51 nodes, 57 edges\n",
    )

    add_heading_safe(doc, "Б.6. Структура resource profile", level=2)
    add_code(
        doc,
        "@dataclass(frozen=True)\n"
        "class ResourceProfile:\n"
        "    name: ProfileName\n"
        "    min_ram_gb: int\n"
        "    min_vram_gb: int = 0\n"
        "    llm_quantization: str = 'Q4_K_M'\n"
        "    llm_context_tokens: int = 4096\n"
        "    llm_gpu_layers: int = 0\n"
        "    # Feature flags\n"
        "    enable_rubert_affect: bool = False\n"
        "    enable_dkt: bool = False\n"
        "    enable_llm_verifier: bool = False\n"
        "    enable_tom_agent: bool = False      # фича 017\n"
        "    enable_path_slime: bool = True      # фича 018\n"
        "    # ToM-специфичные параметры\n"
        "    tom_prompt_style: str = 'short'     # 'short' / 'full'\n"
        "    tom_output_cap: int = 150\n"
        "    # PathSlime-специфичные параметры\n"
        "    path_slime_k: int = 3\n"
        "    path_slime_iterations: int = 35\n"
        "    path_slime_timeout_ms: int = 500\n",
    )

    doc.save(str(path))
    print(f"  Extended: {path}")


def main() -> None:
    print("Extending НИР with detailed pseudocode and analysis...")
    extend_nir()

    print("Extending Курсовой with code fragments...")
    extend_coursework()

    # Check new sizes
    print("\nFinal sizes:")
    for path in [
        DOCS_DIR / "НИР_Сухацкий_2026_knowledge_forge.docx",
        DOCS_DIR / "Курсовой_проект_Сухацкий_2026.docx",
    ]:
        doc = Document(str(path))
        total = sum(len(p.text) for p in doc.paragraphs)
        pages = total // 2200
        print(f"  {path.name}: ~{pages} pages ({total} chars)")


if __name__ == "__main__":
    main()
