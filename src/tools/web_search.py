"""
MITS Web Search Tool

Provides web search capability using DuckDuckGo.
Free, no API key required, supports Russian queries.
"""

import time
from typing import List, Dict, Optional, Any

from src.tools import BaseTool, ToolResult, ToolType


class WebSearchTool(BaseTool):
    """
    Web search tool using DuckDuckGo.

    Features:
    - No API key required
    - Supports Russian queries
    - Privacy-focused
    - Educational content prioritization
    """

    def __init__(self, max_results: int = 5):
        self.max_results = max_results
        self._ddgs = None

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Searches the web for educational content, examples, and current information"

    def _get_ddgs(self):
        """Lazy load DuckDuckGo search."""
        if self._ddgs is None:
            try:
                from duckduckgo_search import DDGS
                self._ddgs = DDGS()
            except ImportError:
                raise ImportError("duckduckgo-search not installed. Run: pip install duckduckgo-search")
        return self._ddgs

    def execute(self, query: str, **kwargs) -> ToolResult:
        """
        Execute a web search.

        Args:
            query: Search query
            **kwargs:
                max_results: Override default max results
                region: Search region (default: 'ru-ru')

        Returns:
            ToolResult with search results
        """
        start_time = time.time()

        try:
            ddgs = self._get_ddgs()

            max_results = kwargs.get('max_results', self.max_results)
            region = kwargs.get('region', 'ru-ru')

            # Add educational context to query
            enhanced_query = self._enhance_query(query)

            # Perform search
            results = list(ddgs.text(
                enhanced_query,
                max_results=max_results,
                region=region
            ))

            # Format results
            formatted = self._format_results(results)

            execution_time = (time.time() - start_time) * 1000

            return ToolResult(
                success=True,
                result=formatted,
                tool_type=ToolType.WEB_SEARCH,
                execution_time_ms=execution_time
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            return ToolResult(
                success=False,
                result=None,
                error=self._format_error(str(e)),
                tool_type=ToolType.WEB_SEARCH,
                execution_time_ms=execution_time
            )

    def can_handle(self, query: str) -> bool:
        """Check if query needs web search."""
        query_lower = query.lower()

        # Search keywords
        search_keywords = [
            'найди', 'поищи', 'search', 'find', 'look up',
            'что такое', 'what is', 'who is', 'когда',
            'последн', 'recent', 'новост', 'news',
            '2024', '2025', '2026',  # Recent years
            'олимпиад', 'olympiad', 'егэ', 'огэ',
        ]

        return any(kw in query_lower for kw in search_keywords)

    def _enhance_query(self, query: str) -> str:
        """Enhance query for better educational results."""
        # Don't modify if already has educational context
        if any(word in query.lower() for word in ['учебник', 'пример', 'решение', 'объяснение']):
            return query

        # Add educational context for math queries
        math_keywords = ['уравнени', 'интеграл', 'производн', 'функц', 'график']
        if any(kw in query.lower() for kw in math_keywords):
            return f"{query} примеры решения"

        return query

    def _format_results(self, results: List[Dict]) -> Dict[str, Any]:
        """Format search results for display."""
        if not results:
            return {
                "count": 0,
                "results": [],
                "summary": "Результаты не найдены"
            }

        formatted_results = []
        for i, r in enumerate(results, 1):
            formatted_results.append({
                "index": i,
                "title": r.get('title', 'Без названия'),
                "url": r.get('href', r.get('link', '')),
                "snippet": r.get('body', r.get('snippet', ''))[:300],
            })

        # Create summary
        summary_parts = []
        for r in formatted_results[:3]:
            summary_parts.append(f"• {r['title']}: {r['snippet'][:100]}...")

        return {
            "count": len(formatted_results),
            "results": formatted_results,
            "summary": "\n".join(summary_parts)
        }

    def _format_error(self, error: str) -> str:
        """Format error message."""
        if 'rate' in error.lower() or 'limit' in error.lower():
            return "Превышен лимит запросов. Подождите немного и попробуйте снова."
        if 'network' in error.lower() or 'connection' in error.lower():
            return "Ошибка сети. Проверьте подключение к интернету."
        return f"Ошибка поиска: {error}"


# Convenience function
def search(query: str, max_results: int = 5) -> ToolResult:
    """
    Quick web search function.

    Args:
        query: Search query
        max_results: Maximum number of results

    Returns:
        ToolResult with search results
    """
    searcher = WebSearchTool(max_results=max_results)
    return searcher.execute(query)
