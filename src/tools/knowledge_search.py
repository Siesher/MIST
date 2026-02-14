"""
MITS Knowledge Search Tool

Provides RAG-based hint and explanation retrieval from the knowledge base.
"""

import time
from typing import Optional, List, Dict, Any

from src.tools import BaseTool, ToolResult, ToolType


class KnowledgeSearchTool(BaseTool):
    """
    Knowledge base search tool using RAG.

    Searches the local knowledge base for:
    - Hints and explanations
    - Common misconceptions
    - Step-by-step solutions
    - Related concepts
    """

    def __init__(self):
        self._rag = None
        self._initialized = False

    @property
    def name(self) -> str:
        return "knowledge_search"

    @property
    def description(self) -> str:
        return "Searches the tutoring knowledge base for hints, explanations, and related concepts"

    def _get_rag(self):
        """Lazy load RAG retriever."""
        if not self._initialized:
            try:
                from src.knowledge.rag_retriever import TutoringRAG
                self._rag = TutoringRAG()
                self._initialized = True
            except ImportError:
                self._initialized = True  # Mark as initialized but RAG unavailable
            except Exception as e:
                self._initialized = True
                # Log error but don't crash

        return self._rag

    def execute(self, query: str, **kwargs) -> ToolResult:
        """
        Search the knowledge base.

        Args:
            query: Search query (topic, problem, or question)
            **kwargs:
                topic: Specific topic to search within
                search_type: 'hints', 'misconceptions', 'concepts', or 'all'
                limit: Maximum results

        Returns:
            ToolResult with knowledge base matches
        """
        start_time = time.time()

        try:
            rag = self._get_rag()

            if rag is None:
                return ToolResult(
                    success=False,
                    result=None,
                    error="База знаний недоступна",
                    tool_type=ToolType.KNOWLEDGE_SEARCH,
                    execution_time_ms=(time.time() - start_time) * 1000
                )

            topic = kwargs.get('topic')
            search_type = kwargs.get('search_type', 'all')
            limit = kwargs.get('limit', 5)

            # Perform retrieval
            context = rag.retrieve_context(
                problem=query,
                student_response=kwargs.get('student_response', ''),
                topic=topic
            )

            # Format results based on search type
            results = self._format_context(context, search_type, limit)

            execution_time = (time.time() - start_time) * 1000

            return ToolResult(
                success=True,
                result=results,
                tool_type=ToolType.KNOWLEDGE_SEARCH,
                execution_time_ms=execution_time
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            return ToolResult(
                success=False,
                result=None,
                error=f"Ошибка поиска в базе знаний: {str(e)}",
                tool_type=ToolType.KNOWLEDGE_SEARCH,
                execution_time_ms=execution_time
            )

    def can_handle(self, query: str) -> bool:
        """Check if query should use knowledge base."""
        query_lower = query.lower()

        # Knowledge base keywords
        kb_keywords = [
            'подсказк', 'hint', 'объясн', 'explain',
            'как решать', 'how to solve', 'метод',
            'ошибк', 'mistake', 'misconception',
            'пример', 'example', 'формул', 'formula',
        ]

        return any(kw in query_lower for kw in kb_keywords)

    def _format_context(
        self,
        context: Any,
        search_type: str,
        limit: int
    ) -> Dict[str, Any]:
        """Format RAG context for tool result."""
        result = {
            "hints": [],
            "misconceptions": [],
            "concepts": [],
            "summary": ""
        }

        if context is None:
            result["summary"] = "Ничего не найдено в базе знаний"
            return result

        # Extract hints
        if hasattr(context, 'hints') and (search_type in ['hints', 'all']):
            for hint in context.hints[:limit]:
                if hasattr(hint, 'content'):
                    result["hints"].append({
                        "content": hint.content,
                        "level": getattr(hint, 'level', 'general'),
                        "topic": getattr(hint, 'topic', 'unknown')
                    })

        # Extract misconceptions
        if hasattr(context, 'misconceptions') and (search_type in ['misconceptions', 'all']):
            for misc in context.misconceptions[:limit]:
                if hasattr(misc, 'error_pattern'):
                    result["misconceptions"].append({
                        "pattern": misc.error_pattern,
                        "correction": getattr(misc, 'correction', ''),
                        "explanation": getattr(misc, 'explanation', '')
                    })

        # Extract concepts
        if hasattr(context, 'concepts') and (search_type in ['concepts', 'all']):
            for concept in context.concepts[:limit]:
                if hasattr(concept, 'name'):
                    result["concepts"].append({
                        "name": concept.name,
                        "definition": getattr(concept, 'definition', ''),
                        "prerequisites": getattr(concept, 'prerequisites', [])
                    })

        # Generate summary
        summary_parts = []
        if result["hints"]:
            summary_parts.append(f"Найдено {len(result['hints'])} подсказок")
        if result["misconceptions"]:
            summary_parts.append(f"{len(result['misconceptions'])} типичных ошибок")
        if result["concepts"]:
            summary_parts.append(f"{len(result['concepts'])} связанных понятий")

        result["summary"] = ", ".join(summary_parts) if summary_parts else "Ничего не найдено"

        return result


# Convenience function
def search_knowledge(query: str, topic: Optional[str] = None) -> ToolResult:
    """
    Quick knowledge base search.

    Args:
        query: Search query
        topic: Optional topic filter

    Returns:
        ToolResult with knowledge base matches
    """
    searcher = KnowledgeSearchTool()
    return searcher.execute(query, topic=topic)
