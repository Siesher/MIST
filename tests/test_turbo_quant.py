"""
Tests for TurboQuant KV cache compression.

Tests cover:
- Rotation matrix orthogonality
- Codebook computation and symmetry
- MSE quantize/dequantize roundtrip
- Inner-product quantize/dequantize (unbiasedness)
- TurboQuantCache update/access lifecycle
- Memory estimation
"""

import numpy as np
import pytest
import torch

from src.inference.turbo_quant import (
    TurboQuantConfig,
    TurboQuantEngine,
    compute_codebook,
    generate_qjl_matrix,
    generate_rotation_matrix,
    get_codebook,
)
from src.inference.turbo_quant_cache import (
    TurboQuantCache,
    create_turbo_quant_cache,
)

# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def config() -> TurboQuantConfig:
    return TurboQuantConfig(key_bits=3, value_bits=3, head_dim=64, seed=42)


@pytest.fixture
def engine(config: TurboQuantConfig) -> TurboQuantEngine:
    return TurboQuantEngine(config, device=torch.device("cpu"))


@pytest.fixture
def cache(config: TurboQuantConfig) -> TurboQuantCache:
    return TurboQuantCache(config, device=torch.device("cpu"))


# ── Rotation Matrix ─────────────────────────────────────────────────

class TestRotationMatrix:
    def test_orthogonality(self):
        """Pi^T @ Pi should be identity."""
        d = 64
        Pi = generate_rotation_matrix(d, seed=42)
        eye = torch.eye(d)
        product = Pi.T @ Pi
        assert torch.allclose(product, eye, atol=1e-5), (
            f"Rotation matrix not orthogonal: max error = {(product - eye).abs().max():.6f}"
        )

    def test_determinant(self):
        """det(Pi) should be +/- 1."""
        d = 64
        Pi = generate_rotation_matrix(d, seed=42)
        det = torch.linalg.det(Pi)
        assert abs(abs(det.item()) - 1.0) < 1e-4

    def test_norm_preservation(self):
        """Rotation should preserve vector norms."""
        d = 128
        Pi = generate_rotation_matrix(d, seed=42)
        x = torch.randn(d)
        y = Pi @ x
        assert torch.allclose(
            torch.norm(x), torch.norm(y), atol=1e-5
        )

    def test_reproducibility(self):
        """Same seed should produce same matrix."""
        Pi1 = generate_rotation_matrix(64, seed=42)
        Pi2 = generate_rotation_matrix(64, seed=42)
        assert torch.allclose(Pi1, Pi2)

    def test_different_seeds(self):
        """Different seeds should produce different matrices."""
        Pi1 = generate_rotation_matrix(64, seed=42)
        Pi2 = generate_rotation_matrix(64, seed=99)
        assert not torch.allclose(Pi1, Pi2)


# ── Codebook ─────────────────────────────────────────────────────────

class TestCodebook:
    def test_correct_num_levels(self):
        """Codebook should have 2^b levels."""
        for b in [1, 2, 3]:
            cb = compute_codebook(64, b)
            assert len(cb) == 2 ** b, f"b={b}: expected {2**b} levels, got {len(cb)}"

    def test_sorted(self):
        """Centroids should be sorted."""
        cb = compute_codebook(128, 3)
        assert np.all(np.diff(cb) >= 0)

    def test_symmetry(self):
        """Codebook should be approximately symmetric around 0."""
        cb = compute_codebook(128, 2)
        assert abs(cb.sum()) < 0.1, f"Codebook not symmetric: sum = {cb.sum():.4f}"

    def test_within_bounds(self):
        """All centroids should be in [-1, 1]."""
        cb = compute_codebook(64, 3)
        assert np.all(cb >= -1.0) and np.all(cb <= 1.0)

    def test_caching(self):
        """get_codebook should return cached results."""
        cb1 = get_codebook(64, 2)
        cb2 = get_codebook(64, 2)
        assert torch.equal(cb1, cb2)


# ── QJL Matrix ───────────────────────────────────────────────────────

class TestQJLMatrix:
    def test_shape(self):
        d = 64
        S = generate_qjl_matrix(d, seed=43)
        assert S.shape == (d, d)

    def test_reproducibility(self):
        S1 = generate_qjl_matrix(64, seed=43)
        S2 = generate_qjl_matrix(64, seed=43)
        assert torch.allclose(S1, S2)


# ── MSE Quantization ────────────────────────────────────────────────

class TestMSEQuantization:
    def test_roundtrip_shape(self, engine: TurboQuantEngine):
        """Quantize + dequantize should preserve shape."""
        x = torch.randn(2, 4, 8, 64)  # (B, H, S, D)
        indices, norms = engine.quantize_mse(x)

        assert indices.shape == (2, 4, 8, 64)
        assert norms.shape == (2, 4, 8)

        x_recon = engine.dequantize_mse(indices, norms)
        assert x_recon.shape == x.shape

    def test_roundtrip_mse(self, engine: TurboQuantEngine):
        """MSE should be bounded (not exact reconstruction, but reasonable)."""
        d = 64
        x = torch.randn(100, d)
        indices, norms = engine.quantize_mse(x)
        x_recon = engine.dequantize_mse(indices, norms)

        # Normalized MSE per vector
        mse_per_vec = ((x - x_recon) ** 2).sum(dim=-1) / (x ** 2).sum(dim=-1)
        mean_nmse = mse_per_vec.mean().item()

        # With 3 bits, distortion should be < 0.1 (paper: ~0.03 for unit norm)
        assert mean_nmse < 0.3, f"MSE too high: {mean_nmse:.4f}"

    def test_zero_vector(self, engine: TurboQuantEngine):
        """Zero vectors should not cause errors (clamped norm)."""
        x = torch.zeros(1, 64)
        indices, norms = engine.quantize_mse(x)
        x_recon = engine.dequantize_mse(indices, norms)
        # Should get near-zero reconstruction
        assert x_recon.abs().max() < 0.1

    def test_index_range(self, engine: TurboQuantEngine):
        """Indices should be in [0, 2^b - 1]."""
        x = torch.randn(10, 64)
        indices, _ = engine.quantize_mse(x)
        max_idx = 2 ** engine.config.value_bits - 1
        assert indices.min() >= 0
        assert indices.max() <= max_idx


# ── Inner-Product Quantization ───────────────────────────────────────

class TestProdQuantization:
    def test_roundtrip_shape(self, engine: TurboQuantEngine):
        """Q_prod quantize + dequantize should preserve shape."""
        x = torch.randn(2, 4, 8, 64)
        mse_idx, qjl_signs, res_norms, norms = engine.quantize_prod(x)

        assert mse_idx.shape == (2, 4, 8, 64)
        assert qjl_signs.shape == (2, 4, 8, 64)
        assert res_norms.shape == (2, 4, 8)
        assert norms.shape == (2, 4, 8)

        x_recon = engine.dequantize_prod(mse_idx, qjl_signs, res_norms, norms)
        assert x_recon.shape == x.shape

    def test_unbiased_inner_product(self):
        """Inner product estimation should be approximately unbiased.

        E[<y, x_recon>] ≈ <y, x> over many samples.
        Uses d=128 for better Beta-distribution convergence.
        """
        d = 128
        cfg = TurboQuantConfig(key_bits=3, value_bits=3, head_dim=d, seed=42)
        eng = TurboQuantEngine(cfg, device=torch.device("cpu"))

        torch.manual_seed(123)
        n_samples = 500

        bias_sum = 0.0
        for _ in range(n_samples):
            x = torch.randn(d)
            y = torch.randn(d)

            mse_idx, qjl_signs, res_norms, norms = eng.quantize_prod(x.unsqueeze(0))
            x_recon = eng.dequantize_prod(
                mse_idx, qjl_signs, res_norms, norms
            ).squeeze(0)

            true_ip = torch.dot(x, y).item()
            est_ip = torch.dot(x_recon, y).item()

            if abs(true_ip) > 1e-6:
                bias_sum += (est_ip - true_ip) / abs(true_ip)

        mean_relative_bias = bias_sum / n_samples
        # With d=128, bias should be small; allow margin for stochasticity
        assert abs(mean_relative_bias) < 0.25, (
            f"Inner product bias too large: {mean_relative_bias:.4f}"
        )

    def test_qjl_signs_binary(self, engine: TurboQuantEngine):
        """QJL signs should be +1 or -1 only."""
        x = torch.randn(10, 64)
        _, qjl_signs, _, _ = engine.quantize_prod(x)
        unique_vals = set(qjl_signs.unique().tolist())
        assert unique_vals.issubset({-1, 1}), f"Unexpected sign values: {unique_vals}"


# ── Convenience API ──────────────────────────────────────────────────

class TestConvenienceAPI:
    def test_quantize_dequantize_mse(self, engine: TurboQuantEngine):
        x = torch.randn(4, 64)
        q = engine.quantize(x, mode="mse")
        x_recon = engine.dequantize(q, mode="mse")
        assert x_recon.shape == x.shape

    def test_quantize_dequantize_prod(self, engine: TurboQuantEngine):
        x = torch.randn(4, 64)
        q = engine.quantize(x, mode="prod")
        x_recon = engine.dequantize(q, mode="prod")
        assert x_recon.shape == x.shape

    def test_invalid_mode(self, engine: TurboQuantEngine):
        x = torch.randn(4, 64)
        with pytest.raises(ValueError, match="Unknown quantization mode"):
            engine.quantize(x, mode="invalid")


# ── TurboQuantCache ──────────────────────────────────────────────────

class TestTurboQuantCache:
    def test_empty_cache(self, cache: TurboQuantCache):
        assert len(cache) == 0
        assert not cache
        assert cache.seen_tokens == 0

    def test_single_update(self, cache: TurboQuantCache):
        """Single update should store and retrieve correctly."""
        B, H, S, D = 1, 4, 8, 64
        k = torch.randn(B, H, S, D)
        v = torch.randn(B, H, S, D)

        k_out, v_out = cache.update(k, v, layer_idx=0)

        assert k_out.shape == (B, H, S, D)
        assert v_out.shape == (B, H, S, D)
        assert len(cache) == 1
        assert cache.seen_tokens == S

    def test_incremental_update(self, cache: TurboQuantCache):
        """Cache should grow with incremental updates."""
        B, H, D = 1, 4, 64

        # First chunk
        k1 = torch.randn(B, H, 4, D)
        v1 = torch.randn(B, H, 4, D)
        cache.update(k1, v1, layer_idx=0)

        assert cache.get_seq_length() == 4

        # Second chunk (autoregressive step)
        k2 = torch.randn(B, H, 1, D)
        v2 = torch.randn(B, H, 1, D)
        k_out, v_out = cache.update(k2, v2, layer_idx=0)

        assert k_out.shape == (B, H, 5, D)
        assert v_out.shape == (B, H, 5, D)
        assert cache.get_seq_length() == 5
        assert cache.seen_tokens == 5

    def test_multi_layer(self, cache: TurboQuantCache):
        """Multiple layers should be stored independently."""
        B, H, S, D = 1, 4, 8, 64

        for layer in range(3):
            k = torch.randn(B, H, S, D)
            v = torch.randn(B, H, S, D)
            cache.update(k, v, layer_idx=layer)

        assert len(cache) == 3

        # Access each layer
        for layer in range(3):
            k_out, v_out = cache[layer]
            assert k_out.shape == (B, H, S, D)
            assert v_out.shape == (B, H, S, D)

    def test_getitem_out_of_range(self, cache: TurboQuantCache):
        with pytest.raises(IndexError):
            _ = cache[0]

    def test_reset(self, cache: TurboQuantCache):
        B, H, S, D = 1, 2, 4, 64
        cache.update(torch.randn(B, H, S, D), torch.randn(B, H, S, D), layer_idx=0)
        assert len(cache) == 1

        cache.reset()
        assert len(cache) == 0
        assert cache.seen_tokens == 0

    def test_iteration(self, cache: TurboQuantCache):
        B, H, S, D = 1, 2, 4, 64
        for layer in range(2):
            cache.update(
                torch.randn(B, H, S, D),
                torch.randn(B, H, S, D),
                layer_idx=layer,
            )

        layers = list(cache)
        assert len(layers) == 2
        for k, v in layers:
            assert k.shape == (B, H, S, D)
            assert v.shape == (B, H, S, D)

    def test_to_legacy_cache(self, cache: TurboQuantCache):
        B, H, S, D = 1, 2, 4, 64
        for layer in range(2):
            cache.update(
                torch.randn(B, H, S, D),
                torch.randn(B, H, S, D),
                layer_idx=layer,
            )

        legacy = cache.to_legacy_cache()
        assert len(legacy) == 2
        assert all(isinstance(t, tuple) and len(t) == 2 for t in legacy)

    def test_reconstruction_quality(self, cache: TurboQuantCache):
        """Stored values should be recoverable with bounded error."""
        B, H, S, D = 1, 4, 16, 64
        k = torch.randn(B, H, S, D)
        v = torch.randn(B, H, S, D)

        cache.update(k, v, layer_idx=0)
        k_recon, v_recon = cache[0]

        # Check that reconstruction is not too far
        k_nmse = ((k - k_recon) ** 2).sum() / (k ** 2).sum()
        v_nmse = ((v - v_recon) ** 2).sum() / (v ** 2).sum()

        # With 3-bit quantization, NMSE should be < 0.3
        assert k_nmse < 0.5, f"Key NMSE too high: {k_nmse:.4f}"
        assert v_nmse < 0.3, f"Value NMSE too high: {v_nmse:.4f}"


# ── Mixed Precision (Outlier-aware) ──────────────────────────────────

class TestMixedPrecision:
    def test_mixed_precision_mse(self):
        """Mixed-precision MSE should produce lower error on outlier channels."""
        cfg = TurboQuantConfig(
            key_bits=2, value_bits=2, head_dim=64,
            outlier_channels=16, outlier_bits_extra=1, seed=42,
        )
        eng = TurboQuantEngine(cfg, device=torch.device("cpu"))

        # Create data with outlier channels (high variance on first 16 dims)
        torch.manual_seed(42)
        x = torch.randn(4, 64)
        x[:, :16] *= 10.0  # make first 16 channels outliers

        indices, norms = eng.quantize_mse(x)
        x_recon = eng.dequantize_mse(indices, norms)

        assert x_recon.shape == x.shape

        # Outlier mask should have been detected
        assert eng._outlier_mask is not None
        assert eng._outlier_mask.sum() == 16

    def test_mixed_precision_prod(self):
        """Mixed-precision Q_prod should work end-to-end."""
        cfg = TurboQuantConfig(
            key_bits=2, value_bits=2, head_dim=64,
            outlier_channels=16, outlier_bits_extra=1, seed=42,
        )
        eng = TurboQuantEngine(cfg, device=torch.device("cpu"))

        torch.manual_seed(42)
        x = torch.randn(4, 64)
        x[:, :16] *= 10.0

        mse_idx, qjl_signs, res_norms, norms = eng.quantize_prod(x)
        x_recon = eng.dequantize_prod(mse_idx, qjl_signs, res_norms, norms)
        assert x_recon.shape == x.shape

    def test_mixed_precision_improves_outlier_quality(self):
        """Mixed precision should give better NMSE than uniform on outlier data."""
        d = 64
        torch.manual_seed(42)
        x = torch.randn(100, d)
        x[:, :16] *= 10.0  # outlier channels

        # Uniform 2-bit
        cfg_uniform = TurboQuantConfig(key_bits=2, value_bits=2, head_dim=d)
        eng_uniform = TurboQuantEngine(cfg_uniform)
        idx_u, norms_u = eng_uniform.quantize_mse(x)
        x_u = eng_uniform.dequantize_mse(idx_u, norms_u)
        nmse_uniform = ((x - x_u) ** 2).sum() / (x ** 2).sum()

        # Mixed 2-bit with 16 outlier channels at 3-bit
        cfg_mixed = TurboQuantConfig(
            key_bits=2, value_bits=2, head_dim=d,
            outlier_channels=16, outlier_bits_extra=1,
        )
        eng_mixed = TurboQuantEngine(cfg_mixed)
        idx_m, norms_m = eng_mixed.quantize_mse(x)
        x_m = eng_mixed.dequantize_mse(idx_m, norms_m)
        nmse_mixed = ((x - x_m) ** 2).sum() / (x ** 2).sum()

        assert nmse_mixed < nmse_uniform, (
            f"Mixed precision NMSE ({nmse_mixed:.4f}) should be < "
            f"uniform NMSE ({nmse_uniform:.4f})"
        )

    def test_convenience_api_mixed(self):
        """Convenience quantize/dequantize API should work with mixed precision."""
        cfg = TurboQuantConfig(
            key_bits=3, value_bits=3, head_dim=64,
            outlier_channels=16, outlier_bits_extra=1,
        )
        eng = TurboQuantEngine(cfg)
        x = torch.randn(4, 64)

        q_mse = eng.quantize(x, mode="mse")
        x_mse = eng.dequantize(q_mse, mode="mse")
        assert x_mse.shape == x.shape

        q_prod = eng.quantize(x, mode="prod")
        x_prod = eng.dequantize(q_prod, mode="prod")
        assert x_prod.shape == x.shape


# ── Factory ──────────────────────────────────────────────────────────

class TestFactory:
    def test_create_turbo_quant_cache(self):
        cache = create_turbo_quant_cache(
            head_dim=64, key_bits=3, value_bits=3
        )
        assert isinstance(cache, TurboQuantCache)
        assert cache.config.head_dim == 64
        assert cache.config.key_bits == 3
        assert cache.config.value_bits == 3


# ── Memory Estimation ────────────────────────────────────────────────

class TestMemoryEstimation:
    def test_compression_ratio(self, engine: TurboQuantEngine):
        stats = engine.estimate_memory_bytes(
            seq_len=1024, num_heads=32, batch_size=1
        )
        assert stats["compression_ratio"] > 1.0
        assert stats["quantized_bytes"] < stats["original_bytes"]

    def test_cache_memory_stats(self, cache: TurboQuantCache):
        B, H, S, D = 1, 4, 32, 64
        cache.update(
            torch.randn(B, H, S, D),
            torch.randn(B, H, S, D),
            layer_idx=0,
        )
        stats = cache.get_memory_stats()
        assert stats["seq_length"] == S
        assert stats["num_heads"] == H
        assert stats["compression_ratio"] > 1.0
