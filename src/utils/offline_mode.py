"""
Offline Mode Detection for MITS.

Feature 010: Utility for detecting and managing offline mode.

Checks:
- Network connectivity
- Ollama availability
- Local model presence
"""

import logging
import socket
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Load configuration
try:
    from src.config import settings
    OLLAMA_HOST = getattr(settings, 'OLLAMA_HOST', 'http://localhost:11434')
except ImportError:
    OLLAMA_HOST = 'http://localhost:11434'


@dataclass
class OfflineStatus:
    """Status of offline mode components."""
    is_offline: bool
    has_network: bool
    ollama_available: bool
    local_models: bool
    local_embeddings: bool
    local_rag: bool

    @property
    def can_operate(self) -> bool:
        """Check if system can operate (with or without network)."""
        return self.ollama_available and self.local_models

    def to_dict(self) -> Dict:
        return {
            "is_offline": self.is_offline,
            "has_network": self.has_network,
            "ollama_available": self.ollama_available,
            "local_models": self.local_models,
            "local_embeddings": self.local_embeddings,
            "local_rag": self.local_rag,
            "can_operate": self.can_operate,
        }


def check_network_connectivity(
    host: str = "8.8.8.8",
    port: int = 53,
    timeout: float = 3.0
) -> bool:
    """
    Check if network is available.

    Uses DNS server check as a lightweight connectivity test.

    Args:
        host: Host to check (default: Google DNS)
        port: Port to check
        timeout: Connection timeout

    Returns:
        True if network is available
    """
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except (socket.error, socket.timeout):
        return False


def check_ollama_available(
    host: str = None,
    timeout: float = 5.0
) -> Tuple[bool, Optional[str]]:
    """
    Check if Ollama server is available.

    Args:
        host: Ollama host URL
        timeout: Request timeout

    Returns:
        Tuple of (available, version_or_error)
    """
    host = host or OLLAMA_HOST

    try:
        import requests
        response = requests.get(f"{host}/api/version", timeout=timeout)
        if response.status_code == 200:
            version = response.json().get("version", "unknown")
            return True, version
        return False, f"HTTP {response.status_code}"
    except ImportError:
        # Try with urllib
        try:
            import urllib.request
            import urllib.error
            import json

            req = urllib.request.Request(f"{host}/api/version")
            with urllib.request.urlopen(req, timeout=timeout) as response:
                data = json.loads(response.read().decode())
                return True, data.get("version", "unknown")
        except Exception as e:
            return False, str(e)
    except Exception as e:
        return False, str(e)


def check_local_models(
    host: str = None
) -> Tuple[bool, list]:
    """
    Check for locally available models in Ollama.

    Args:
        host: Ollama host URL

    Returns:
        Tuple of (has_models, model_list)
    """
    host = host or OLLAMA_HOST

    try:
        import requests
        response = requests.get(f"{host}/api/tags", timeout=5.0)
        if response.status_code == 200:
            models = response.json().get("models", [])
            model_names = [m.get("name", "") for m in models]
            return len(model_names) > 0, model_names
        return False, []
    except Exception:
        return False, []


def check_local_embeddings() -> bool:
    """
    Check if local embedding model is available.

    Returns:
        True if sentence-transformers can work offline
    """
    try:
        from sentence_transformers import SentenceTransformer
        # Check if model is cached locally
        model_name = 'paraphrase-multilingual-MiniLM-L12-v2'
        cache_path = Path.home() / '.cache' / 'torch' / 'sentence_transformers'

        if cache_path.exists():
            for item in cache_path.iterdir():
                if model_name.replace('/', '_') in item.name:
                    return True

        # Alternative: check huggingface cache
        hf_cache = Path.home() / '.cache' / 'huggingface' / 'hub'
        if hf_cache.exists():
            for item in hf_cache.iterdir():
                if 'multilingual-MiniLM' in item.name:
                    return True

        return False
    except ImportError:
        return False


def check_local_rag() -> bool:
    """
    Check if local RAG storage is available.

    Returns:
        True if ChromaDB data exists
    """
    try:
        from src.config import settings
        chroma_path = getattr(settings, 'VECTOR_DB_PATH', Path('./data/chromadb'))
        return chroma_path.exists() and any(chroma_path.iterdir())
    except Exception:
        # Check default path
        default_path = Path('./data/chromadb')
        return default_path.exists() and any(default_path.iterdir())


def detect_offline_mode() -> OfflineStatus:
    """
    Detect current offline mode status.

    Returns:
        OfflineStatus with all component checks
    """
    has_network = check_network_connectivity()
    ollama_available, _ = check_ollama_available()
    local_models = check_local_models()[0]
    local_embeddings = check_local_embeddings()
    local_rag = check_local_rag()

    is_offline = not has_network

    status = OfflineStatus(
        is_offline=is_offline,
        has_network=has_network,
        ollama_available=ollama_available,
        local_models=local_models,
        local_embeddings=local_embeddings,
        local_rag=local_rag,
    )

    logger.info(f"Offline mode detection: {status.to_dict()}")

    return status


def get_offline_status_message(status: OfflineStatus) -> str:
    """
    Get human-readable status message.

    Args:
        status: OfflineStatus object

    Returns:
        Status message in Russian
    """
    if status.can_operate:
        if status.is_offline:
            return "🔌 Офлайн режим — система работает локально"
        else:
            return "🌐 Онлайн режим — все компоненты доступны"
    else:
        issues = []
        if not status.ollama_available:
            issues.append("Ollama недоступен")
        if not status.local_models:
            issues.append("Нет локальных моделей")

        return f"⚠️ Система недоступна: {', '.join(issues)}"


# Global status cache
_cached_status: Optional[OfflineStatus] = None
_cache_time: float = 0


def get_offline_status(use_cache: bool = True, cache_ttl: float = 60.0) -> OfflineStatus:
    """
    Get cached offline status.

    Args:
        use_cache: Use cached status if available
        cache_ttl: Cache TTL in seconds

    Returns:
        OfflineStatus
    """
    global _cached_status, _cache_time
    import time

    current_time = time.time()

    if use_cache and _cached_status is not None:
        if current_time - _cache_time < cache_ttl:
            return _cached_status

    _cached_status = detect_offline_mode()
    _cache_time = current_time

    return _cached_status


def is_offline() -> bool:
    """Quick check if system is offline."""
    return get_offline_status().is_offline


def can_operate() -> bool:
    """Quick check if system can operate."""
    return get_offline_status().can_operate


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\n=== Offline Mode Detection ===\n")

    status = detect_offline_mode()

    print(f"Network available: {status.has_network}")
    print(f"Ollama available: {status.ollama_available}")
    print(f"Local models: {status.local_models}")
    print(f"Local embeddings: {status.local_embeddings}")
    print(f"Local RAG: {status.local_rag}")
    print()
    print(f"Is offline: {status.is_offline}")
    print(f"Can operate: {status.can_operate}")
    print()
    print(get_offline_status_message(status))
