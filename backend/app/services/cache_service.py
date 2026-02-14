"""
LLM response cache service for backend API.

Wraps src/inference/cache.py ResponseCache with async interface
and TTL-based expiration for use in FastAPI orchestrator.
"""

import hashlib
import time
import logging
from typing import Optional, Dict, Any, Tuple
from collections import OrderedDict
from threading import RLock

logger = logging.getLogger(__name__)


class LLMCacheService:
    """
    In-memory LRU cache for LLM responses.

    Keyed by (prompt_hash, mode). Supports configurable max size and TTL.
    Thread-safe for concurrent access from async endpoints.
    """

    def __init__(self, max_size: int = 500, ttl_seconds: int = 3600):
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._lock = RLock()

        # Metrics
        self._hits = 0
        self._misses = 0

        logger.info(f"LLMCacheService initialized: max_size={max_size}, ttl={ttl_seconds}s")

    @staticmethod
    def _make_key(prompt: str, mode: str) -> str:
        """Create cache key from prompt hash and mode."""
        raw = f"{mode}|{prompt.strip()}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, prompt: str, mode: str) -> Optional[str]:
        """
        Look up cached response.

        Returns cached response string or None on miss/expiry.
        """
        key = self._make_key(prompt, mode)

        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None

            # Check TTL
            if time.time() - entry["created_at"] > self._ttl:
                del self._cache[key]
                self._misses += 1
                return None

            # Move to end (LRU)
            self._cache.move_to_end(key)
            entry["access_count"] += 1
            self._hits += 1
            return entry["response"]

    def put(self, prompt: str, mode: str, response: str, move_type: str = "") -> None:
        """Store a response in the cache."""
        key = self._make_key(prompt, mode)

        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key]["response"] = response
                return

            self._cache[key] = {
                "response": response,
                "move_type": move_type,
                "created_at": time.time(),
                "access_count": 0,
            }

            # Evict oldest entries when over limit
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    @property
    def stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "ttl_seconds": self._ttl,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total > 0 else 0.0,
            "total_requests": total,
        }


# Singleton
_cache_service: Optional[LLMCacheService] = None


def get_cache_service() -> LLMCacheService:
    """Get or create the cache service singleton."""
    global _cache_service
    if _cache_service is None:
        _cache_service = LLMCacheService()
    return _cache_service
