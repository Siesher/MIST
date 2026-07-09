"""
MITS Inference Module.

Компоненты для оптимизации инференса:
- cache: Кэширование ответов и эмбеддингов
- batch_processor: Пакетная обработка запросов
- hint_prefetcher: Предзагрузка подсказок
- model_manager: Управление моделями
- metrics: Метрики производительности
"""

from src.inference.batch_processor import (
    BatchItem,
    BatchProcessor,
    BatchResult,
    EmbeddingBatchProcessor,
    get_embedding_processor,
)
from src.inference.cache import (
    CacheEntry,
    LRUCache,
    RAGQueryCache,
    ResponseCache,
    TutoringCacheManager,
    get_cache_manager,
    get_rag_cache,
)
from src.inference.hint_prefetcher import (
    HintPrefetcher,
    PrefetchedHint,
    PrefetchTask,
    get_hint_prefetcher,
    init_prefetcher,
)

__all__ = [
    # Cache
    "ResponseCache",
    "LRUCache",
    "CacheEntry",
    "TutoringCacheManager",
    "RAGQueryCache",
    "get_cache_manager",
    "get_rag_cache",
    # Batch Processing
    "BatchProcessor",
    "BatchItem",
    "BatchResult",
    "EmbeddingBatchProcessor",
    "get_embedding_processor",
    # Hint Prefetching
    "HintPrefetcher",
    "PrefetchedHint",
    "PrefetchTask",
    "get_hint_prefetcher",
    "init_prefetcher",
]
