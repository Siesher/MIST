"""
PathSlime: Lévy-Gaussian hybrid Slime Mould Algorithm for multi-path learning.

Bio-inspired pathfinder, генерирует k diverse learning paths через граф знаний
вместо единственного оптимума (как Dijkstra). Каждая "колония" эволюционирует
через:

1. **Lévy flight** perturbation — heavy-tailed jumps для diversification
2. **Gaussian mutation** — local refinement (замена 1-2 рёбер)
3. **Diversity pressure** — штраф за edge overlap с другими колониями

Multi-objective fitness по стилям (quick / gradual / example_rich / mixed).

References:
- Nakagaki et al. (2000), Nature 407:470 — Physarum maze solving
- Li et al. (2020), FGCS — Slime Mould Algorithm
- LRSMA (2023-24), MDPI Biomimetics — Lévy-Rotation SMA for path planning
- Viswanathan et al. (1999), Nature 401:911 — Lévy flight optimality

Интерфейс через `PersonalizedNavigator.find_alternative_paths()`.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

import numpy as np

from src.knowledge.knowledge_forge import EdgeType, KnowledgeGraph, NodeType
from src.knowledge.levy_sampler import levy_multiplier

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────


@dataclass
class StyleConfig:
    """Весовые коэффициенты multi-objective fitness для одного стиля.

    Фиксированные профили (из research.md R5):
    - quick:       (0.60, 0.20, 0.15, 0.05) — минимум длины
    - gradual:     (0.25, 0.30, 0.35, 0.10) — плавная сложность
    - example_rich:(0.25, 0.25, 0.15, 0.35) — больше примеров
    - mixed:       (0.40, 0.30, 0.20, 0.10) — сбалансирован
    """

    name: str
    w_length: float
    w_mastery: float
    w_difficulty: float
    w_examples: float

    def __post_init__(self) -> None:
        total = self.w_length + self.w_mastery + self.w_difficulty + self.w_examples
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"weights must sum to 1.0, got {total} for {self.name}")


STYLES: Dict[str, StyleConfig] = {
    "quick": StyleConfig("quick", 0.60, 0.20, 0.15, 0.05),
    "gradual": StyleConfig("gradual", 0.25, 0.30, 0.35, 0.10),
    "example_rich": StyleConfig("example_rich", 0.25, 0.25, 0.15, 0.35),
    "mixed": StyleConfig("mixed", 0.40, 0.30, 0.20, 0.10),
}


@dataclass
class PathSlimeConfig:
    """Runtime parameters. Derived from active resource profile."""

    k: int = 3
    colony_size: int = 10
    max_iterations: int = 35
    levy_alpha: float = 1.5
    gaussian_sigma: float = 0.3
    diversity_lambda: float = 0.35
    timeout_ms: int = 500
    conductivity_decay: float = 0.15
    early_stop_patience: int = 5

    @classmethod
    def from_active_profile(cls) -> "PathSlimeConfig":
        """Load parameters from current resource profile."""
        try:
            from src.resource_profiles import get_active_profile

            p = get_active_profile()
            return cls(
                k=p.path_slime_k,
                max_iterations=p.path_slime_iterations,
                timeout_ms=p.path_slime_timeout_ms,
            )
        except Exception:
            return cls()


# ─────────────────────────────────────────────────────────────────────
# Output type
# ─────────────────────────────────────────────────────────────────────


@dataclass
class AlternativePaths:
    """Result of find_alternative_paths(). Contains k diverse paths + metadata."""

    target: str
    paths: List  # List[LearningPath] — forward ref избегаем circular import
    diversity_score: float = 0.0
    style: str = "mixed"
    truncated: bool = False
    iterations_run: int = 0
    elapsed_ms: float = 0.0
    error: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────
# Colony — один эволюционирующий путь
# ─────────────────────────────────────────────────────────────────────


@dataclass
class Colony:
    """Один "слизевик" — candidate path evolving through graph.

    Внутреннее состояние: текущий path + fitness + локальная conductivity
    на использованных рёбрах (Physarum-style reinforcement).
    """

    id: int
    path: List[str] = field(default_factory=list)
    fitness: float = 0.0
    conductivity: Dict[Tuple[str, str], float] = field(default_factory=dict)
    stagnation: int = 0

    def edges(self) -> List[Tuple[str, str]]:
        """Список рёбер пути."""
        return [(self.path[i], self.path[i + 1]) for i in range(len(self.path) - 1)]

    def edge_set(self) -> set:
        """Множество рёбер пути (для Jaccard diversity)."""
        return set(self.edges())


# ─────────────────────────────────────────────────────────────────────
# PathSlime engine
# ─────────────────────────────────────────────────────────────────────


class PathSlime:
    """Bio-inspired optimizer для k diverse paths.

    Usage:
        engine = PathSlime(graph, mastery, config)
        result = engine.run(target_id="math:...", style="mixed")
    """

    def __init__(
        self,
        graph: KnowledgeGraph,
        mastery: Dict[str, float],
        config: Optional[PathSlimeConfig] = None,
        seed: Optional[int] = None,
    ) -> None:
        self.graph = graph
        self.mastery = mastery
        self.config = config or PathSlimeConfig.from_active_profile()
        self._rng = np.random.default_rng(seed)

        # Cache: список outgoing prerequisite edges для каждого node
        # Используется для быстрой random traversal.
        self._outgoing_cache: Dict[str, List[str]] = {}

        # Node difficulty cache
        self._diff_cache: Dict[str, float] = {}

        # Example density: сколько ILLUSTRATES-узлов ссылается на concept
        self._example_density: Dict[str, int] = {}

    # ── Main entry point ─────────────────────────────────────────

    def run(self, target_id: str, style: str = "mixed") -> AlternativePaths:
        """Запустить оптимизацию, вернуть k diverse paths к target_id."""
        t_start = time.perf_counter()

        if self.graph.get_node(target_id) is None:
            return AlternativePaths(target=target_id, paths=[], error="target not found")

        style_cfg = STYLES.get(style) or STYLES["mixed"]
        if style not in STYLES:
            logger.warning(f"unknown style '{style}', falling back to 'mixed'")

        # Уже мастерован — возвращаем тривиальный 1-узловой "путь"
        if self.mastery.get(target_id, 0.0) >= 0.7:
            from src.knowledge.navigator import LearningPath

            return AlternativePaths(
                target=target_id,
                paths=[LearningPath(target=target_id, path=[target_id], total_cost=0.0)],
                diversity_score=1.0,
                style=style,
                elapsed_ms=(time.perf_counter() - t_start) * 1000,
            )

        # Initialize k colonies
        colonies = []
        for i in range(self.config.k):
            col = self._spawn_colony(i, target_id)
            if col is not None and col.path:
                col.fitness = self._fitness(col.path, style_cfg, colonies[:i])
                colonies.append(col)

        if not colonies:
            # Не смогли даже один путь — fallback к Dijkstra
            return self._dijkstra_fallback(target_id, style, t_start)

        best_fitness_history: List[float] = []

        # Evolution loop
        iter_run = 0
        truncated = False
        for iteration in range(self.config.max_iterations):
            iter_run = iteration + 1

            # Timeout check
            elapsed_ms = (time.perf_counter() - t_start) * 1000
            if elapsed_ms > self.config.timeout_ms:
                truncated = True
                logger.info(
                    f"path_slime.timeout at iteration {iteration}, elapsed {elapsed_ms:.0f}ms"
                )
                break

            # Evolve each colony
            for col in colonies:
                self._evolve_colony(col, target_id, style_cfg, colonies)

            # Early stop: если max fitness не улучшилось за patience итераций
            cur_best = max(c.fitness for c in colonies)
            best_fitness_history.append(cur_best)
            if len(best_fitness_history) > self.config.early_stop_patience:
                recent = best_fitness_history[-self.config.early_stop_patience :]
                if max(recent) - min(recent) < 1e-4:
                    logger.info(f"path_slime.early_stop at iter {iteration}")
                    break

        # Дедупликация: если 2 колонии пришли к identical paths, оставим одну
        unique_paths = self._deduplicate(colonies)

        # Compute diversity
        diversity = self._diversity_score(unique_paths)

        # Convert к LearningPath
        from src.knowledge.navigator import LearningPath

        learning_paths = []
        for col in unique_paths:
            mastery_along = [self.mastery.get(nid, 0.0) for nid in col.path]
            new_count = sum(1 for m in mastery_along if m < 0.7)
            learning_paths.append(
                LearningPath(
                    target=target_id,
                    path=list(col.path),
                    total_cost=1.0 - col.fitness,  # invert: lower cost = better
                    estimated_concepts_to_learn=new_count,
                    mastery_along_path=mastery_along,
                )
            )

        elapsed = (time.perf_counter() - t_start) * 1000
        logger.info(
            f"path_slime.done iters={iter_run} paths={len(learning_paths)} "
            f"diversity={diversity:.2f} elapsed={elapsed:.0f}ms"
        )

        return AlternativePaths(
            target=target_id,
            paths=learning_paths,
            diversity_score=diversity,
            style=style,
            truncated=truncated,
            iterations_run=iter_run,
            elapsed_ms=elapsed,
        )

    # ── Colony lifecycle ─────────────────────────────────────────

    def _spawn_colony(self, colony_id: int, target_id: str) -> Optional[Colony]:
        """Создать новую колонию с начальным путём от master → target."""
        start_nodes = self._find_start_nodes()
        if not start_nodes:
            return None

        # Random start node, varies between colonies
        start = self._rng.choice(start_nodes)
        path = self._sample_path(start, target_id)
        if not path:
            return None

        col = Colony(id=colony_id, path=path)
        return col

    def _find_start_nodes(self) -> List[str]:
        """Nodes where traversal can start — mastered concepts или graph entry points."""
        mastered = [
            nid
            for nid, m in self.mastery.items()
            if m >= 0.7
            and self.graph.get_node(nid) is not None
            and self.graph.get_node(nid).node_type == NodeType.CONCEPT
        ]
        if mastered:
            return mastered

        # Cold start: use nodes без prerequisites как entry points
        entry_points = []
        for nid, node in self.graph._nodes.items():
            if node.node_type != NodeType.CONCEPT:
                continue
            incoming = self.graph.get_neighbors(
                nid, edge_type=EdgeType.PREREQUISITE, direction="incoming"
            )
            if not incoming:
                entry_points.append(nid)
        return entry_points

    def _sample_path(self, start: str, target: str, max_len: int = 15) -> List[str]:
        """Случайный путь start → target через PREREQUISITE edges с Lévy perturbation.

        Строит путь forward: из start → куда бы ни пошёл по outgoing PREREQUISITE.
        Target is reached либо через BFS shortening, либо через limited random walk.
        """
        # Использовать BFS и разбавить случайностью: найти все пути длины ≤ max_len
        # от start к target, затем выбрать один с Lévy-perturbed probabilities.
        # Для простоты MVP: directed random walk с BFS fallback.

        # 1. Сначала проверим, что target достижим из start (иначе abort)
        reachable = self.graph.find_path(start, target, edge_types=[EdgeType.PREREQUISITE])
        if reachable is None:
            return []

        # 2. Random walk с bias towards target (через BFS precomputed distances)
        path = [start]
        current = start
        visited = {start}
        for _ in range(max_len):
            if current == target:
                return path
            outgoing = self._outgoing_prereqs(current)
            # Keep only unvisited
            candidates = [n for n in outgoing if n not in visited]
            if not candidates:
                break
            # Фильтр: оставить только кандидатов с reachable путём до target
            # (без этого random walk попадает в dead-end ветки графа).
            reachable_candidates = []
            reachable_rest_len = []
            for cand in candidates:
                if cand == target:
                    reachable_candidates.append(cand)
                    reachable_rest_len.append(0)
                    continue
                rest = self.graph.find_path(cand, target, edge_types=[EdgeType.PREREQUISITE])
                if rest is not None:
                    reachable_candidates.append(cand)
                    reachable_rest_len.append(len(rest))
            if not reachable_candidates:
                break
            candidates = reachable_candidates
            # Score candidates: preference для тех, что ближе к target
            scores = []
            for cand, rest_len in zip(candidates, reachable_rest_len):
                if rest_len == 0:
                    scores.append(10.0)  # is target, strong attraction
                else:
                    # Shorter rest = better, плюс небольшое floor для diversity
                    scores.append(0.3 + 1.0 / (rest_len + 1))
            weights = np.array(scores)
            levy = levy_multiplier(alpha=self.config.levy_alpha, n=len(candidates), rng=self._rng)
            perturbed = weights * levy
            if perturbed.sum() <= 0:
                perturbed = np.ones(len(candidates))
            perturbed = perturbed / perturbed.sum()
            chosen_idx = int(self._rng.choice(len(candidates), p=perturbed))
            current = candidates[chosen_idx]
            path.append(current)
            visited.add(current)

        # Если не дошли до target обычным walk — append shortest path от current
        if path[-1] != target:
            finish = self.graph.find_path(path[-1], target, edge_types=[EdgeType.PREREQUISITE])
            if finish:
                # finish[0] == path[-1], так что extend от finish[1:]
                for nid in finish[1:]:
                    if nid not in visited:
                        path.append(nid)
                        visited.add(nid)
        return path if path[-1] == target else []

    def _outgoing_prereqs(self, node_id: str) -> List[str]:
        """Cached: узлы, для которых node_id является PREREQUISITE."""
        if node_id in self._outgoing_cache:
            return self._outgoing_cache[node_id]
        out = self.graph.get_neighbors(
            node_id, edge_type=EdgeType.PREREQUISITE, direction="outgoing"
        )
        ids = [n.id for _, n in out]
        self._outgoing_cache[node_id] = ids
        return ids

    # ── Evolution ────────────────────────────────────────────────

    def _evolve_colony(
        self,
        col: Colony,
        target_id: str,
        style: StyleConfig,
        all_colonies: List[Colony],
    ) -> None:
        """Один шаг эволюции колонии."""
        # 50/50 между Lévy jump и Gaussian refinement
        if self._rng.random() < 0.5:
            new_path = self._levy_perturb(col.path, target_id)
        else:
            new_path = self._gaussian_refine(col.path, target_id)

        if not new_path or new_path[-1] != target_id:
            col.stagnation += 1
            return

        # Fitness с diversity penalty
        new_fitness = self._fitness(new_path, style, [c for c in all_colonies if c.id != col.id])
        if new_fitness > col.fitness:
            col.path = new_path
            col.fitness = new_fitness
            col.stagnation = 0
        else:
            col.stagnation += 1

    def _levy_perturb(self, path: List[str], target: str) -> List[str]:
        """Обрезать случайный хвост пути и rebuild через Lévy sampling."""
        if len(path) < 3:
            return path
        # Rand cut point между 1 и len-1
        cut = int(self._rng.integers(1, len(path) - 1))
        prefix = path[: cut + 1]
        regenerated = self._sample_path(prefix[-1], target, max_len=15 - cut)
        if not regenerated:
            return path
        # prefix[-1] == regenerated[0], extend:
        return prefix + regenerated[1:]

    def _gaussian_refine(self, path: List[str], target: str) -> List[str]:
        """Заменить 1-2 соседних узла на альтернативный prereq chain."""
        if len(path) < 3:
            return path
        # Pick random interior node (not start/target)
        i = int(self._rng.integers(1, len(path) - 1))
        # Try replacing path[i] with an alternative
        prev_node = path[i - 1]
        next_node = path[i + 1]
        alternatives = [
            n
            for n in self._outgoing_prereqs(prev_node)
            if n != path[i] and n in self._prereqs_of(next_node)
        ]
        if not alternatives:
            return path
        new_mid = alternatives[int(self._rng.integers(0, len(alternatives)))]
        return path[:i] + [new_mid] + path[i + 1 :]

    def _prereqs_of(self, node_id: str) -> List[str]:
        """Nodes являющиеся prerequisites для node_id (incoming PREREQUISITE)."""
        incoming = self.graph.get_neighbors(
            node_id, edge_type=EdgeType.PREREQUISITE, direction="incoming"
        )
        return [n.id for _, n in incoming]

    # ── Fitness ──────────────────────────────────────────────────

    def _fitness(
        self,
        path: List[str],
        style: StyleConfig,
        other_colonies: List[Colony],
    ) -> float:
        """Multi-objective fitness score ∈ [0, 1] с diversity penalty."""
        if not path or len(path) < 1:
            return 0.0

        # 1. Length component — shorter is better, normalized by 15 (max reasonable)
        length_component = max(0.0, 1.0 - len(path) / 15.0)

        # 2. Mastery coverage — mean mastery вдоль пути
        mastery_values = [self.mastery.get(nid, 0.0) for nid in path]
        mastery_component = float(np.mean(mastery_values)) if mastery_values else 0.0

        # 3. Difficulty smoothness — minimize max jump
        difficulties = []
        for nid in path:
            node = self.graph.get_node(nid)
            if node:
                difficulties.append(node.difficulty)
        if len(difficulties) < 2:
            difficulty_component = 1.0
        else:
            jumps = [
                abs(difficulties[i + 1] - difficulties[i]) for i in range(len(difficulties) - 1)
            ]
            max_jump = max(jumps) if jumps else 0.0
            difficulty_component = max(0.0, 1.0 - max_jump)

        # 4. Example density — ILLUSTRATES edges to concepts in path
        example_count = 0
        for nid in path:
            incoming_ill = self.graph.get_neighbors(
                nid, edge_type=EdgeType.ILLUSTRATES, direction="incoming"
            )
            example_count += len(incoming_ill)
        example_component = min(1.0, example_count / max(1, len(path)))

        base_fitness = (
            style.w_length * length_component
            + style.w_mastery * mastery_component
            + style.w_difficulty * difficulty_component
            + style.w_examples * example_component
        )

        # Diversity penalty: штраф за overlap с другими colonies
        if other_colonies:
            my_edges = set((path[i], path[i + 1]) for i in range(len(path) - 1))
            if my_edges:
                overlaps = []
                for other in other_colonies:
                    other_edges = other.edge_set()
                    if not other_edges:
                        continue
                    overlap = len(my_edges & other_edges) / max(len(my_edges | other_edges), 1)
                    overlaps.append(overlap)
                mean_overlap = np.mean(overlaps) if overlaps else 0.0
                base_fitness -= self.config.diversity_lambda * mean_overlap

        return float(max(0.0, min(1.0, base_fitness)))

    # ── Diversity & deduplication ───────────────────────────────

    def _deduplicate(self, colonies: List[Colony]) -> List[Colony]:
        """Удалить colonies с идентичными путями."""
        seen = set()
        unique = []
        for col in sorted(colonies, key=lambda c: -c.fitness):
            key = tuple(col.path)
            if key in seen:
                continue
            seen.add(key)
            unique.append(col)
        return unique

    @staticmethod
    def _diversity_score(colonies: List[Colony]) -> float:
        """Средняя pairwise Jaccard distance между edge sets."""
        if len(colonies) < 2:
            return 1.0
        distances = []
        for i in range(len(colonies)):
            for j in range(i + 1, len(colonies)):
                a = colonies[i].edge_set()
                b = colonies[j].edge_set()
                if not a and not b:
                    distances.append(0.0)
                    continue
                union = a | b
                inter = a & b
                jaccard = 1.0 - (len(inter) / len(union) if union else 0.0)
                distances.append(jaccard)
        return float(np.mean(distances)) if distances else 0.0

    # ── Dijkstra fallback ────────────────────────────────────────

    def _dijkstra_fallback(self, target_id: str, style: str, t_start: float) -> AlternativePaths:
        """При полном fail алгоритма — вернуть Dijkstra путь."""
        logger.warning("path_slime.fallback to Dijkstra")
        from src.knowledge.navigator import PersonalizedNavigator

        try:
            # Используем встроенный Dijkstra через navigator
            fallback_nav = PersonalizedNavigator(self.graph, self.mastery)
            path = fallback_nav.find_optimal_path("fallback", target_id)
            if path is not None:
                return AlternativePaths(
                    target=target_id,
                    paths=[path],
                    diversity_score=1.0,
                    style=style,
                    error="fallback_to_dijkstra",
                    elapsed_ms=(time.perf_counter() - t_start) * 1000,
                )
        except Exception as e:
            logger.error(f"path_slime.dijkstra_fallback_failed: {e}")

        return AlternativePaths(
            target=target_id,
            paths=[],
            style=style,
            error="all_methods_failed",
            elapsed_ms=(time.perf_counter() - t_start) * 1000,
        )
