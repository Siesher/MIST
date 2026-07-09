"""Tests for navigator tool definitions, dispatch, and integration."""

import json
from pathlib import Path

import pytest

from src.knowledge.knowledge_forge import (
    EdgeType,
    KnowledgeEdge,
    KnowledgeGraph,
    KnowledgeNode,
    NodeType,
)
from src.tools import navigator_tools
from src.tools.navigator_tools import (
    NAVIGATOR_FUNCTIONS,
    NAVIGATOR_TOOL_DEFINITIONS,
    diagnose_gap,
    explore_concept,
    get_learning_frontier,
    reset_cache,
    set_mastery_source,
    suggest_next,
)


@pytest.fixture(autouse=True)
def _clean_cache():
    """Reset navigator cache before each test."""
    reset_cache()
    yield
    reset_cache()


@pytest.fixture
def forge_graph(tmp_path: Path) -> Path:
    """Create a small forge.json for testing."""
    g = KnowledgeGraph()

    concepts = [
        ("math:algebra:definition", "Алгебра", "Algebra", 0.2),
        ("math:limits:definition", "Пределы", "Limits", 0.5),
        ("math:derivatives:definition", "Производная", "Derivative", 0.6),
    ]
    for cid, title, title_en, diff in concepts:
        g.add_node(
            KnowledgeNode(
                id=cid,
                node_type=NodeType.CONCEPT,
                title=title,
                title_en=title_en,
                content=f"Определение: {title}",
                domain="math",
                difficulty=diff,
            )
        )

    g.add_node(
        KnowledgeNode(
            id="math:sign_error:misconception",
            node_type=NodeType.MISCONCEPTION,
            title="Ошибка знака",
            title_en="Sign error",
            content="Частая ошибка при дифференцировании.",
            domain="math",
            difficulty=0.5,
        )
    )

    g.add_edge(
        KnowledgeEdge(
            source_id="math:algebra:definition",
            target_id="math:limits:definition",
            edge_type=EdgeType.PREREQUISITE,
        )
    )
    g.add_edge(
        KnowledgeEdge(
            source_id="math:limits:definition",
            target_id="math:derivatives:definition",
            edge_type=EdgeType.PREREQUISITE,
        )
    )
    g.add_edge(
        KnowledgeEdge(
            source_id="math:sign_error:misconception",
            target_id="math:derivatives:definition",
            edge_type=EdgeType.COMMON_ERROR_FOR,
        )
    )

    path = tmp_path / "forge.json"
    g.save(path)

    # Monkey-patch FORGE_PATH for tests
    navigator_tools.FORGE_PATH = path
    return path


class TestToolDefinitions:
    """Verify tool definitions match Ollama format."""

    def test_tool_count(self) -> None:
        assert len(NAVIGATOR_TOOL_DEFINITIONS) == 5

    def test_function_count(self) -> None:
        assert len(NAVIGATOR_FUNCTIONS) == 5

    def test_tool_names_match_functions(self) -> None:
        tool_names = {t["function"]["name"] for t in NAVIGATOR_TOOL_DEFINITIONS}
        func_names = set(NAVIGATOR_FUNCTIONS.keys())
        assert tool_names == func_names

    def test_ollama_format(self) -> None:
        for tool in NAVIGATOR_TOOL_DEFINITIONS:
            assert tool["type"] == "function"
            assert "name" in tool["function"]
            assert "description" in tool["function"]
            assert "parameters" in tool["function"]
            assert tool["function"]["parameters"]["type"] == "object"


class TestExploreConceptTool:
    """Test explore_concept dispatch."""

    def test_returns_concept_with_mastery(self, forge_graph: Path) -> None:
        mastery = {"math:algebra:definition": 0.9}
        set_mastery_source(mastery)

        result = json.loads(
            explore_concept(
                concept_id="math:limits:definition",
                student_id="s1",
            )
        )

        assert result["concept"]["title"] == "Пределы"
        assert "prerequisites" in result["student"]
        # Algebra should show as mastered prerequisite
        prereqs = result["student"]["prerequisites"]
        assert len(prereqs) > 0
        assert prereqs[0]["status"] == "mastered"

    def test_nonexistent_concept(self, forge_graph: Path) -> None:
        result = json.loads(
            explore_concept(
                concept_id="math:nonexistent:definition",
                student_id="s1",
            )
        )
        assert "error" in result

    def test_includes_misconceptions(self, forge_graph: Path) -> None:
        set_mastery_source({})
        result = json.loads(
            explore_concept(
                concept_id="math:derivatives:definition",
                student_id="s1",
            )
        )
        assert len(result["misconceptions"]) > 0
        assert result["misconceptions"][0]["title"] == "Ошибка знака"


class TestDiagnoseGapTool:
    """Test diagnose_gap dispatch."""

    def test_finds_missing_prereq(self, forge_graph: Path) -> None:
        mastery = {"math:algebra:definition": 0.9, "math:limits:definition": 0.3}
        set_mastery_source(mastery)

        result = json.loads(
            diagnose_gap(
                concept_id="math:derivatives:definition",
                student_id="s1",
            )
        )

        assert "math:limits:definition" in result["missing_prerequisites"]

    def test_finds_misconceptions(self, forge_graph: Path) -> None:
        set_mastery_source({})
        result = json.loads(
            diagnose_gap(
                concept_id="math:derivatives:definition",
                student_id="s1",
            )
        )
        assert "math:sign_error:misconception" in result["misconceptions"]


class TestSuggestNextTool:
    """Test suggest_next dispatch."""

    def test_suggests_ready_concept(self, forge_graph: Path) -> None:
        mastery = {"math:algebra:definition": 0.9}
        set_mastery_source(mastery)

        result = json.loads(suggest_next(student_id="s1"))
        assert "node_id" in result
        # Should suggest limits (algebra mastered, limits not yet)
        assert result["node_id"] == "math:limits:definition"


class TestGetLearningFrontierTool:
    """Test get_learning_frontier dispatch."""

    def test_returns_frontier_list(self, forge_graph: Path) -> None:
        mastery = {"math:algebra:definition": 0.9}
        set_mastery_source(mastery)

        result = json.loads(get_learning_frontier(student_id="s1"))
        assert isinstance(result, list)
        assert len(result) > 0
        assert "readiness" in result[0]


class TestGracefulDegradation:
    """Test that tools handle missing graph gracefully."""

    def test_no_graph_returns_error(self) -> None:
        # Point to nonexistent file
        navigator_tools.FORGE_PATH = Path("/nonexistent/forge.json")
        result = json.loads(
            explore_concept(
                concept_id="math:test:definition",
                student_id="s1",
            )
        )
        assert "error" in result

    def test_tutor_agent_imports_cleanly(self) -> None:
        """Verify tutor agent loads even if graph is missing."""
        import src.agents.tutor_agent

        assert hasattr(src.agents.tutor_agent, "HAS_NAVIGATOR_TOOLS")
