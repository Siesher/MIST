"""
Cerebras API client with key rotation for high-throughput dataset generation.

Supports 10 API keys from .env for effective 300 req/min rate.
"""

import os
import sys
import time
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from collections import deque

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from openai import OpenAI
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


@dataclass
class RateLimitTracker:
    """Track rate limits per API key."""
    requests_per_minute: int = 30
    tokens_per_minute: int = 64000
    request_times: deque = field(default_factory=lambda: deque(maxlen=30))

    def can_make_request(self) -> bool:
        """Check if we can make a request without exceeding rate limit."""
        now = time.time()
        # Remove requests older than 60 seconds
        while self.request_times and now - self.request_times[0] > 60:
            self.request_times.popleft()
        return len(self.request_times) < self.requests_per_minute

    def record_request(self):
        """Record a request timestamp."""
        self.request_times.append(time.time())

    def wait_time(self) -> float:
        """Calculate how long to wait before next request."""
        if not self.request_times:
            return 0
        oldest = self.request_times[0]
        wait = 60 - (time.time() - oldest)
        return max(0, wait)


class CerebrasClient:
    """
    Cerebras API client with automatic key rotation.

    Usage:
        client = CerebrasClient()
        response = client.generate("Explain quantum entanglement step by step")
    """

    BASE_URL = "https://api.cerebras.ai/v1"
    DEFAULT_MODEL = "qwen-3-235b-a22b-instruct-2507"

    def __init__(
        self,
        env_file: str = ".env",
        model: str = DEFAULT_MODEL,
        max_retries: int = 3,
        backoff_factor: float = 2.0
    ):
        """
        Initialize client with API keys from environment.

        Args:
            env_file: Path to .env file with CEREBRAS_API_KEY_1..10
            model: Model name to use
            max_retries: Max retries per request
            backoff_factor: Exponential backoff multiplier
        """
        load_dotenv(env_file)

        self.model = model
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

        # Load all API keys
        self.api_keys: List[str] = []
        for i in range(1, 11):
            key = os.getenv(f"CEREBRAS_API_KEY_{i}")
            if key and key.startswith("csk-"):
                self.api_keys.append(key)

        if not self.api_keys:
            raise ValueError("No valid Cerebras API keys found in environment")

        logger.info(f"Loaded {len(self.api_keys)} Cerebras API keys")

        # Initialize clients for each key
        self.clients: List[OpenAI] = [
            OpenAI(base_url=self.BASE_URL, api_key=key)
            for key in self.api_keys
        ]

        # Rate limit trackers per key
        self.rate_limiters: List[RateLimitTracker] = [
            RateLimitTracker() for _ in self.api_keys
        ]

        self.current_key_index = 0
        self.total_requests = 0
        self.total_tokens = 0

    def _get_available_client(self) -> tuple[OpenAI, int]:
        """Get the next available client that isn't rate limited."""
        start_index = self.current_key_index

        for _ in range(len(self.clients)):
            idx = self.current_key_index
            limiter = self.rate_limiters[idx]

            if limiter.can_make_request():
                return self.clients[idx], idx

            # Try next key
            self.current_key_index = (self.current_key_index + 1) % len(self.clients)

        # All keys are rate limited, wait for the one with shortest wait
        min_wait = float('inf')
        best_idx = 0
        for idx, limiter in enumerate(self.rate_limiters):
            wait = limiter.wait_time()
            if wait < min_wait:
                min_wait = wait
                best_idx = idx

        if min_wait > 0:
            logger.info(f"All keys rate limited, waiting {min_wait:.1f}s")
            time.sleep(min_wait + 0.1)

        return self.clients[best_idx], best_idx

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7
    ) -> str:
        """
        Generate a response using Cerebras API with automatic key rotation.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Generated text response
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        last_error = None

        for attempt in range(self.max_retries):
            client, key_idx = self._get_available_client()

            try:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature
                )

                # Record successful request
                self.rate_limiters[key_idx].record_request()
                self.total_requests += 1

                if response.usage:
                    self.total_tokens += response.usage.total_tokens

                # Rotate to next key for load balancing
                self.current_key_index = (key_idx + 1) % len(self.clients)

                return response.choices[0].message.content

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                if "rate" in error_str or "429" in error_str:
                    # Rate limit hit, mark this key and try another
                    logger.warning(f"Rate limit hit on key {key_idx + 1}, rotating")
                    self.rate_limiters[key_idx].record_request()
                    self.current_key_index = (key_idx + 1) % len(self.clients)
                else:
                    # Other error, apply backoff
                    wait_time = self.backoff_factor ** attempt
                    logger.warning(f"Request failed: {e}, retrying in {wait_time}s")
                    time.sleep(wait_time)

        raise RuntimeError(f"Failed after {self.max_retries} retries: {last_error}")

    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics."""
        return {
            "total_requests": self.total_requests,
            "total_tokens": self.total_tokens,
            "keys_available": len(self.api_keys),
            "current_key_index": self.current_key_index
        }


def create_client(env_file: str = ".env") -> CerebrasClient:
    """Factory function to create a Cerebras client."""
    return CerebrasClient(env_file=env_file)
