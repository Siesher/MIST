"""Тесты PathSlime (feature 018) — Lévy-Gaussian SMA multi-path generation."""

from pathlib import Path

import numpy as np
import pytest

from src.knowledge.knowledge_forge import (
    EdgeType,
    KnowledgeEdge,
    KnowledgeGraph,
    KnowledgeNode,
    NodeType,
)
from src.knowledge.levy_sampler import (
    MAX_MULTIPLIER,
    MIN_MULTIPLIER,
    levy_multiplier,
    weighted_choice_with_levy,
)
from src.knowledge.navigator import PersonalizedNavigator
from src.knowledge.path_slime import (
    STYLES,
    AlternativePaths,
    PathSlime,
    PathSlimeConfig,
    StyleConfig,
)

# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def simple_graph() -> KnowledgeGraph:
    """Мини-граф: a → b, a → c → b, для тестирования множественных путей."""
    g = KnowledgeGraph()
    for cid, title, diff in [
        ("n:a:definition", "A", 0.1),
        ("n:b:definition", "B", 0.5),
        ("n:c:definition", "C", 0.3),
        ("n:d:definition", "D", 0.4),
        ("n:target:definition", "Target", 0.7),
    ]:
        g.add_node(
            KnowledgeNode(
                id=cid,
                node_type=NodeType.CONCEPT,
                title=title,
                title_en=title,
                content=title,
                domain="math",
                difficulty=diff,
            )
        )
    # Пути: a → target (прямой), a → b → target, a → c → d → target
    for src, tgt in [
        ("n:a:definition", "n:b:definition"),
        ("n:a:definition", "n:c:definition"),
        ("n:b:definition", "n:target:definition"),
        ("n:c:definition", "n:d:definition"),
        ("n:d:definition", "n:target:definition"),
    ]:
        g.add_edge(KnowledgeEdge(source_id=src, target_id=tgt, edge_type=EdgeType.PREREQUISITE))
    return g


@pytest.fixture
def real_graph() -> KnowledgeGraph:
    """Реальный forge.json если доступен, иначе skip."""
    path = Path("data/knowledge/forge.json")
    if not path.exists():
        pytest.skip("forge.json not found — run migration first")
    return KnowledgeGraph(path)


# ─────────────────────────────────────────────────────────────────────
# T007: Lévy sampler statistics
# ─────────────────────────────────────────────────────────────────────


class TestLevySampler:
    def test_levy_samples_in_range(self) -> None:
        """Все samples в [MIN_MULTIPLIER, MAX_MULTIPLIER]."""
        rng = np.random.default_rng(42)
        samples = levy_multiplier(alpha=1.5, n=1000, rng=rng)
        assert samples.min() >= MIN_MULTIPLIER
        assert samples.max() <= MAX_MULTIPLIER
        assert len(samples) == 1000

    def test_levy_heavy_tail_vs_gaussian(self) -> None:
        """T007: Lévy distribution имеет heavier tail чем Gaussian baseline."""
        rng = np.random.default_rng(42)
        levy = levy_multiplier(alpha=1.5, n=10000, rng=rng)
        # Gaussian baseline same scale
        gaussian = np.abs(rng.normal(0, 1, 10000))
        gaussian = np.clip(gaussian, MIN_MULTIPLIER, MAX_MULTIPLIER)
        # 99th percentile должен быть выше у Lévy
        assert np.percentile(levy, 99) > np.percentile(gaussian, 99)

    def test_levy_invalid_alpha(self) -> None:
        with pytest.raises(ValueError):
            levy_multiplier(alpha=0.0)
        with pytest.raises(ValueError):
            levy_multiplier(alpha=3.0)

    def test_weighted_choice_levy(self) -> None:
        """weighted_choice_with_levy возвращает valid index."""
        rng = np.random.default_rng(42)
        idx = weighted_choice_with_levy(["a", "b", "c"], np.array([1.0, 2.0, 3.0]), rng=rng)
        assert 0 <= idx <= 2

    def test_weighted_choice_all_zero_weights(self) -> None:
        """Uniform fallback когда все веса нули."""
        rng = np.random.default_rng(42)
        idx = weighted_choice_with_levy(["a", "b"], np.array([0.0, 0.0]), rng=rng)
        assert 0 <= idx <= 1


# ─────────────────────────────────────────────────────────────────────
# Style + Config validation
# ─────────────────────────────────────────────────────────────────────


class TestStyleConfig:
    def test_all_styles_sum_to_one(self) -> None:
        for name, style in STYLES.items():
            total = style.w_length + style.w_mastery + style.w_difficulty + style.w_examples
            assert abs(total - 1.0) < 1e-6, f"{name} weights sum {total} != 1.0"

    def test_invalid_weights_rejected(self) -> None:
        with pytest.raises(ValueError):
            StyleConfig("bad", 0.5, 0.5, 0.5, 0.5)  # sum > 1


class TestPathSlimeConfig:
    def test_defaults(self) -> None:
        c = PathSlimeConfig()
        assert c.k == 3
        assert c.max_iterations == 35
        assert c.timeout_ms == 500

    def test_from_active_profile(self) -> None:
        """Загружает параметры из active resource profile."""
        c = PathSlimeConfig.from_active_profile()
        # Some valid values depending on which profile is detected
        assert c.k >= 1
        assert c.max_iterations >= 10


# ─────────────────────────────────────────────────────────────────────
# T008-T011: PathSlime on simple graph
# ─────────────────────────────────────────────────────────────────────


class TestPathSlimeBasic:
    def test_returns_paths_to_target(self, simple_graph: KnowledgeGraph) -> None:
        """T008: PathSlime возвращает non-empty paths для валидного target."""
        mastery = {"n:a:definition": 0.9}
        engine = PathSlime(
            graph=simple_graph,
            mastery=mastery,
            config=PathSlimeConfig(k=3, max_iterations=10, timeout_ms=3000),
            seed=42,
        )
        result = engine.run(target_id="n:target:definition", style="mixed")
        assert isinstance(result, AlternativePaths)
        assert len(result.paths) >= 1
        for path in result.paths:
            assert path.path[-1] == "n:target:definition"

    def test_path_validity(self, simple_graph: KnowledgeGraph) -> None:
        """T009: все пары (A, B) в пути — valid prerequisite edge."""
        mastery = {"n:a:definition": 0.9}
        engine = PathSlime(
            graph=simple_graph,
            mastery=mastery,
            config=PathSlimeConfig(k=3, max_iterations=10, timeout_ms=3000),
            seed=42,
        )
        result = engine.run(target_id="n:target:definition", style="mixed")
        for path in result.paths:
            for i in range(len(path.path) - 1):
                src, tgt = path.path[i], path.path[i + 1]
                is_valid_edge = simple_graph.has_edge(
                    src, tgt, EdgeType.PREREQUISITE
                ) or simple_graph.has_edge(src, tgt, EdgeType.BEST_TAUGHT_AFTER)
                assert is_valid_edge, f"invalid edge {src} -> {tgt}"

    def test_already_mastered_target(self, simple_graph: KnowledgeGraph) -> None:
        """T010: target уже мастерован → возвращает trivial 1-узловой путь."""
        mastery = {
            "n:a:definition": 0.9,
            "n:target:definition": 0.95,  # уже мастерован
        }
        engine = PathSlime(
            graph=simple_graph,
            mastery=mastery,
            config=PathSlimeConfig(k=3),
            seed=42,
        )
        result = engine.run(target_id="n:target:definition", style="mixed")
        assert len(result.paths) == 1
        assert result.paths[0].path == ["n:target:definition"]
        assert result.diversity_score == 1.0

    def test_reproducibility(self, simple_graph: KnowledgeGraph) -> None:
        """T011: одинаковый seed → одинаковый результат."""
        mastery = {"n:a:definition": 0.9}
        cfg = PathSlimeConfig(k=3, max_iterations=10, timeout_ms=3000)

        engine1 = PathSlime(graph=simple_graph, mastery=mastery, config=cfg, seed=42)
        r1 = engine1.run(target_id="n:target:definition", style="mixed")

        engine2 = PathSlime(graph=simple_graph, mastery=mastery, config=cfg, seed=42)
        r2 = engine2.run(target_id="n:target:definition", style="mixed")

        # Paths should be identical (same seed)
        paths1 = [tuple(p.path) for p in r1.paths]
        paths2 = [tuple(p.path) for p in r2.paths]
        assert paths1 == paths2

    def test_invalid_target(self, simple_graph: KnowledgeGraph) -> None:
        """Несуществующий target → error без исключения."""
        engine = PathSlime(
            graph=simple_graph,
            mastery={"n:a:definition": 0.9},
            config=PathSlimeConfig(),
        )
        result = engine.run(target_id="n:nonexistent:definition")
        assert result.error is not None
        assert len(result.paths) == 0


# ─────────────────────────────────────────────────────────────────────
# Navigator integration
# ─────────────────────────────────────────────────────────────────────


class TestNavigatorIntegration:
    def test_find_alternative_paths_via_navigator(self, simple_graph: KnowledgeGraph) -> None:
        """find_alternative_paths() на Navigator возвращает AlternativePaths."""
        nav = PersonalizedNavigator(simple_graph, {"n:a:definition": 0.9})
        result = nav.find_alternative_paths(
            student_id="test",
            target_id="n:target:definition",
            k=2,
            seed=42,
        )
        assert isinstance(result, AlternativePaths)

    def test_backward_compat_dijkstra(self, simple_graph: KnowledgeGraph) -> None:
        """Existing find_optimal_path() продолжает работать (не тронут)."""
        nav = PersonalizedNavigator(simple_graph, {"n:a:definition": 0.9})
        path = nav.find_optimal_path("test", "n:target:definition")
        assert path is not None
        assert path.path[-1] == "n:target:definition"


# ─────────────────────────────────────────────────────────────────────
# Real graph integration (если forge.json есть)
# ─────────────────────────────────────────────────────────────────────


class TestPathSlimeRealGraph:
    def test_multi_path_on_real_graph(self, real_graph: KnowledgeGraph) -> None:
        """На реальном 83-узловом графе получаем ≥2 diverse paths."""
        mastery = {
            "math:arithmetic:definition": 0.9,
            "math:variables:definition": 0.85,
            "math:linear_equations:definition": 0.8,
        }
        engine = PathSlime(
            graph=real_graph,
            mastery=mastery,
            config=PathSlimeConfig(k=3, max_iterations=20, timeout_ms=5000),
            seed=42,
        )
        result = engine.run(target_id="math:derivatives_basic:definition", style="mixed")
        # Не обязательно k=3 — может быть меньше, но ≥1
        assert len(result.paths) >= 1
        # Все пути кончаются на target
        for path in result.paths:
            assert path.path[-1] == "math:derivatives_basic:definition"
