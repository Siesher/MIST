"""
MITS Tools Module

Provides tools for the tutor agent:
- Calculator: Mathematical computations using SymPy
- Web Search: Educational content via DuckDuckGo
- Knowledge Search: RAG-based hint retrieval
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass
from enum import Enum


class ToolType(Enum):
    """Types of available tools."""
    CALCULATOR = "calculator"
    WEB_SEARCH = "web_search"
    KNOWLEDGE_SEARCH = "knowledge_search"
    CONCEPT_LOOKUP = "concept_lookup"
    WORKED_EXAMPLE = "worked_example"
    FORMULA_LOOKUP = "formula_lookup"
    PREREQUISITES = "prerequisites"


@dataclass
class ToolResult:
    """Result from a tool execution."""
    success: bool
    result: Any
    error: Optional[str] = None
    tool_type: Optional[ToolType] = None
    execution_time_ms: Optional[float] = None


class BaseTool(ABC):
    """Base class for all tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name for identification."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of what the tool does."""
        pass

    @abstractmethod
    def execute(self, query: str, **kwargs) -> ToolResult:
        """Execute the tool with given query."""
        pass

    def can_handle(self, query: str) -> bool:
        """Check if this tool can handle the query."""
        return True


class ToolRegistry:
    """Registry for managing available tools."""

    _instance = None
    _tools: Dict[str, BaseTool] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
        return cls._instance

    def register(self, tool: BaseTool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_all(self) -> Dict[str, BaseTool]:
        """Get all registered tools."""
        return self._tools.copy()

    def find_tool_for_query(self, query: str) -> Optional[BaseTool]:
        """Find a suitable tool for the query."""
        for tool in self._tools.values():
            if tool.can_handle(query):
                return tool
        return None


# Global registry instance
tool_registry = ToolRegistry()


def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry."""
    return tool_registry


def register_default_tools():
    """Register default tools with the global registry."""
    from src.tools.calculator import CalculatorTool
    from src.tools.web_search import WebSearchTool
    from src.tools.knowledge_search import KnowledgeSearchTool

    tool_registry.register(CalculatorTool())
    tool_registry.register(WebSearchTool())
    tool_registry.register(KnowledgeSearchTool())

    # SKI-based tools (graceful — skip if knowledge base not available)
    try:
        from src.tools.ski_tool_adapters import (
            ConceptLookupTool, WorkedExampleTool,
            FormulaTool, PrerequisitesTool,
        )
        tool_registry.register(ConceptLookupTool())
        tool_registry.register(WorkedExampleTool())
        tool_registry.register(FormulaTool())
        tool_registry.register(PrerequisitesTool())
    except Exception:
        pass  # SKI tools are optional


# Auto-register tools on import (lazy)
_tools_registered = False

def ensure_tools_registered():
    """Ensure tools are registered (call once)."""
    global _tools_registered
    if not _tools_registered:
        try:
            register_default_tools()
            _tools_registered = True
        except ImportError:
            pass  # Dependencies not installed


__all__ = [
    "ToolType",
    "ToolResult",
    "BaseTool",
    "ToolRegistry",
    "tool_registry",
    "get_tool_registry",
    "register_default_tools",
    "ensure_tools_registered",
]
