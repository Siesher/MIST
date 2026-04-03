"""
TurboQuant KV Cache for HuggingFace Transformers.

Custom Cache implementation that compresses key/value states using
the TurboQuant algorithm (arXiv:2504.19874).

- Keys are quantized with Q_prod (preserves inner products for attention)
- Values are quantized with Q_mse (minimizes reconstruction error)

Compatible with transformers >= 4.36 Cache API.
"""

from typing import Any, Dict, List, Optional, Tuple

import torch
import logging

from src.inference.turbo_quant import TurboQuantConfig, TurboQuantEngine

logger = logging.getLogger(__name__)


class TurboQuantCache:
    """KV cache that stores quantized keys and values using TurboQuant.

    Drop-in replacement for transformers.DynamicCache that compresses
    KV states on-the-fly during generation. Supports autoregressive
    decoding (new tokens appended incrementally).

    Quantization is applied per-layer to all heads simultaneously.
    Full-precision tensors are reconstructed on access for attention
    computation.

    Example:
        >>> config = TurboQuantConfig(key_bits=3, value_bits=3, head_dim=128)
        >>> cache = TurboQuantCache(config)
        >>> # Pass to model.generate():
        >>> outputs = model.generate(inputs, past_key_values=cache)
    """

    # Tell HF transformers this is a valid cache
    is_sliding_window = False

    def __init__(
        self,
        config: TurboQuantConfig,
        max_batch_size: int = 1,
        device: Optional[torch.device] = None,
    ):
        """Initialize TurboQuant KV cache.

        Args:
            config: TurboQuant configuration.
            max_batch_size: Maximum batch size (for pre-allocation).
            device: Device for computation.
        """
        self.config = config
        self.device = device or torch.device("cpu")

        # Initialize the quantization engine
        self.engine = TurboQuantEngine(config, device=self.device)

        # Per-layer quantized storage
        # Each entry: dict with quantized components
        self._key_cache: List[Dict[str, torch.Tensor]] = []
        self._value_cache: List[Dict[str, torch.Tensor]] = []

        # Track sequence lengths per layer
        self._seen_tokens: int = 0

        logger.info(
            f"TurboQuantCache initialized: key_bits={config.key_bits}, "
            f"value_bits={config.value_bits}, head_dim={config.head_dim}"
        )

    def __len__(self) -> int:
        """Number of layers in the cache."""
        return len(self._key_cache)

    def __bool__(self) -> bool:
        """Cache is truthy if it has any stored states."""
        return len(self._key_cache) > 0 and self._seen_tokens > 0

    def __getitem__(self, layer_idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        """Get dequantized (key, value) for a layer.

        Args:
            layer_idx: Layer index.

        Returns:
            Tuple of (key_states, value_states), both shape
            (batch_size, num_heads, seq_len, head_dim).
        """
        if layer_idx >= len(self._key_cache):
            raise IndexError(f"Layer {layer_idx} not in cache (have {len(self._key_cache)} layers)")

        key_states = self.engine.dequantize(self._key_cache[layer_idx], mode="prod")
        value_states = self.engine.dequantize(self._value_cache[layer_idx], mode="mse")

        return key_states, value_states

    def __iter__(self):
        """Iterate over layers, yielding (key, value) tuples."""
        for layer_idx in range(len(self._key_cache)):
            yield self[layer_idx]

    def update(
        self,
        key_states: torch.Tensor,
        value_states: torch.Tensor,
        layer_idx: int,
        cache_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Update the cache with new key/value states for a layer.

        Quantizes incoming states and appends to the compressed store.
        Returns the full dequantized cache for the current attention
        computation (needed by the model).

        Args:
            key_states: New key states (batch, heads, new_seq, head_dim).
            value_states: New value states (batch, heads, new_seq, head_dim).
            layer_idx: Transformer layer index.
            cache_kwargs: Additional kwargs (unused, for API compat).

        Returns:
            Tuple of full (key_cache, value_cache) for this layer,
            both shape (batch, heads, total_seq, head_dim).
        """
        # Move engine to the correct device if needed
        if key_states.device != self.device:
            self.device = key_states.device
            self.engine.to(self.device)

        # Quantize new states
        new_key_q = self.engine.quantize(key_states, mode="prod")
        new_value_q = self.engine.quantize(value_states, mode="mse")

        if layer_idx >= len(self._key_cache):
            # New layer — initialize
            self._key_cache.append(new_key_q)
            self._value_cache.append(new_value_q)
        else:
            # Append along sequence dimension (dim=2 for (B, H, S, D))
            existing_key = self._key_cache[layer_idx]
            existing_value = self._value_cache[layer_idx]
            self._key_cache[layer_idx] = _concat_quantized(existing_key, new_key_q, mode="prod")
            self._value_cache[layer_idx] = _concat_quantized(existing_value, new_value_q, mode="mse")

        # Track tokens (only count once, from layer 0)
        if layer_idx == 0:
            self._seen_tokens += key_states.shape[2]

        # Return full dequantized cache for attention computation
        return self[layer_idx]

    def get_seq_length(self, layer_idx: int = 0) -> int:
        """Get current sequence length in the cache."""
        if not self._key_cache:
            return 0
        # Infer from the stored tensor shape
        first_tensor = _get_first_tensor(self._key_cache[layer_idx])
        if first_tensor is None:
            return 0
        # Tensors are (B, H, S, D) — seq is dim 2
        return first_tensor.shape[2] if first_tensor.ndim == 4 else first_tensor.shape[0]

    def get_usable_length(self, new_seq_length: int, layer_idx: int = 0) -> int:
        """Get usable cache length (for compatibility)."""
        return self.get_seq_length(layer_idx)

    def get_max_length(self) -> Optional[int]:
        """No maximum length constraint."""
        return None

    @property
    def seen_tokens(self) -> int:
        """Total tokens processed."""
        return self._seen_tokens

    def reset(self) -> None:
        """Clear all cached states."""
        self._key_cache.clear()
        self._value_cache.clear()
        self._seen_tokens = 0

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory usage statistics.

        Returns:
            Dict with memory usage in bytes and compression ratio.
        """
        if not self._key_cache:
            return {"status": "empty"}

        seq_len = self.get_seq_length()
        # Infer num_heads from first stored tensor
        first_t = _get_first_tensor(self._key_cache[0])
        if first_t is None:
            return {"status": "empty"}

        num_heads = first_t.shape[1] if first_t.ndim == 4 else 1
        batch_size = first_t.shape[0] if first_t.ndim == 4 else 1
        num_layers = len(self._key_cache)

        per_layer = self.engine.estimate_memory_bytes(seq_len, num_heads, batch_size)

        return {
            "num_layers": num_layers,
            "seq_length": seq_len,
            "num_heads": num_heads,
            "batch_size": batch_size,
            "per_layer": per_layer,
            "total_original_bytes": per_layer["original_bytes"] * num_layers,
            "total_quantized_bytes": per_layer["quantized_bytes"] * num_layers,
            "compression_ratio": per_layer["compression_ratio"],
        }

    def to_legacy_cache(self) -> Tuple[Tuple[torch.Tensor, torch.Tensor], ...]:
        """Convert to legacy tuple-of-tuples format.

        Returns:
            Tuple of (key, value) pairs per layer, dequantized.
        """
        return tuple(self[i] for i in range(len(self._key_cache)))

    @classmethod
    def from_legacy_cache(
        cls,
        past_key_values: Tuple[Tuple[torch.Tensor, torch.Tensor], ...],
        config: TurboQuantConfig,
    ) -> "TurboQuantCache":
        """Create TurboQuantCache from a legacy cache.

        Args:
            past_key_values: Tuple of (key, value) per layer.
            config: TurboQuant configuration.

        Returns:
            New TurboQuantCache with quantized states.
        """
        if not past_key_values:
            return cls(config)

        device = past_key_values[0][0].device
        cache = cls(config, device=device)

        for layer_idx, (k, v) in enumerate(past_key_values):
            cache.update(k, v, layer_idx)

        return cache


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _concat_quantized(
    existing: Dict[str, torch.Tensor],
    new: Dict[str, torch.Tensor],
    mode: str,
) -> Dict[str, torch.Tensor]:
    """Concatenate quantized representations along the sequence dimension.

    For tensors with shape (B, H, S, D), concat on dim=2.
    For tensors with shape (B, H, S) or (...,), concat on the last
    sequence-like dimension.

    Args:
        existing: Existing quantized dict.
        new: New quantized dict.
        mode: "prod" or "mse".

    Returns:
        Merged dict.
    """
    result = {}
    for key in existing:
        e = existing[key]
        n = new[key]

        if e.ndim >= 3:
            # (B, H, S, ...) → concat on dim 2 (sequence)
            result[key] = torch.cat([e, n], dim=2)
        elif e.ndim == 2:
            # (B, H*S) or (B, S) — concat on dim 1
            result[key] = torch.cat([e, n], dim=1)
        elif e.ndim == 1:
            # (S,) — concat on dim 0
            result[key] = torch.cat([e, n], dim=0)
        else:
            # scalar — stack
            result[key] = torch.stack([e, n])

    return result


def _get_first_tensor(d: Dict[str, torch.Tensor]) -> Optional[torch.Tensor]:
    """Get the first tensor from a quantized dict (for shape inference)."""
    for v in d.values():
        if isinstance(v, torch.Tensor):
            return v
    return None


# ─────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────

def create_turbo_quant_cache(
    head_dim: int = 128,
    key_bits: int = 3,
    value_bits: int = 3,
    device: Optional[torch.device] = None,
    seed: int = 42,
) -> TurboQuantCache:
    """Convenience factory for TurboQuantCache.

    Args:
        head_dim: Attention head dimension.
        key_bits: Bits for key quantization (Q_prod).
        value_bits: Bits for value quantization (Q_mse).
        device: Computation device.
        seed: Random seed.

    Returns:
        Configured TurboQuantCache instance.
    """
    config = TurboQuantConfig(
        key_bits=key_bits,
        value_bits=value_bits,
        head_dim=head_dim,
        seed=seed,
    )
    return TurboQuantCache(config, device=device)
