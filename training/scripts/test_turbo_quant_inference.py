#!/usr/bin/env python3
"""
End-to-end TurboQuant inference test on KTO model.

Compares generation quality and memory usage:
  1. Standard DynamicCache (baseline)
  2. TurboQuantCache 3-bit (compressed)

Usage:
    python training/scripts/test_turbo_quant_inference.py
"""

import gc
import logging
import os
import sys
import time
from typing import Optional

# Ensure project root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import torch

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)


# ── Monkey-patch: accelerate 1.13 passes _is_hf_initialized from
# parameter.__dict__ into Params4bit(), which rejects it.
# Filter out foreign kwargs before constructing bnb params.
def _patch_accelerate_bnb_compat() -> None:
    """Patch accelerate.utils.modeling to filter stale kwargs for bnb Params4bit."""
    try:
        import inspect

        import accelerate.utils.modeling as _mod

        _orig = _mod.set_module_tensor_to_device
        _src = inspect.getsource(_orig)
        if "_is_hf_initialized" not in _src:
            # Not affected or already patched
            return

        _BNB_CLASSES = {"Int8Params", "FP4Params", "Params4bit"}

        def _patched(
            module,
            tensor_name,
            device,
            value=None,
            dtype=None,
            fp16_statistics=None,
            tied_params_map=None,
            non_blocking=False,
        ):
            # Before calling original, scrub _is_hf_initialized from bnb params
            if tensor_name in module._parameters:
                param = module._parameters[tensor_name]
                if type(param).__name__ in _BNB_CLASSES and hasattr(param, "_is_hf_initialized"):
                    del param.__dict__["_is_hf_initialized"]
            return _orig(
                module,
                tensor_name,
                device,
                value=value,
                dtype=dtype,
                fp16_statistics=fp16_statistics,
                tied_params_map=tied_params_map,
                non_blocking=non_blocking,
            )

        _mod.set_module_tensor_to_device = _patched
        logger.info("Patched accelerate bnb compat (_is_hf_initialized filter)")
    except Exception as e:
        logger.warning(f"Could not patch accelerate: {e}")


_patch_accelerate_bnb_compat()

KTO_MODEL_PATH = "C:/Work/MITS/training/models/mits-kto"

TEST_PROMPTS = [
    {
        "system": "Ты — репетитор по математике. Отвечай на русском.",
        "user": "Реши уравнение: $3x - 7 = 2x + 5$",
    },
    # Uncomment for full test (slow on CPU):
    # {
    #     "system": "Ты — репетитор по физике. Отвечай на русском.",
    #     "user": "Тело массой 2 кг падает с высоты 10 м. Какова его кинетическая энергия у земли?",
    # },
    # {
    #     "system": "Ты — репетитор по информатике. Отвечай на русском.",
    #     "user": "Объясни, что такое хеш-таблица и где она применяется.",
    # },
]


def get_gpu_memory_mb() -> float:
    """Get current GPU memory usage in MB."""
    if torch.cuda.is_available():
        return torch.cuda.memory_allocated() / 1024 / 1024
    return 0.0


def get_gpu_reserved_mb() -> float:
    """Get reserved GPU memory in MB."""
    if torch.cuda.is_available():
        return torch.cuda.memory_reserved() / 1024 / 1024
    return 0.0


def load_model():
    """Load KTO model with NF4 quantization.

    Uses the original CausalLM config (config.json.bak) for HuggingFace loading,
    since AutoModelForCausalLM can't load ConditionalGeneration wrapper.
    Falls back to CPU offload if VRAM is insufficient.
    """
    import shutil

    from transformers import AutoModelForCausalLM, AutoTokenizer

    # Temporarily restore CausalLM config for HF loading
    cfg_path = f"{KTO_MODEL_PATH}/config.json"
    cfg_bak = f"{KTO_MODEL_PATH}/config.json.bak"
    cfg_ollama = f"{KTO_MODEL_PATH}/config.json.ollama"

    # Save current (ConditionalGeneration) config and restore original (CausalLM)
    if os.path.exists(cfg_bak):
        shutil.copy(cfg_path, cfg_ollama)
        shutil.copy(cfg_bak, cfg_path)
        logger.info("Switched config.json to CausalLM format for HF loading")

    try:
        logger.info("Loading tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(KTO_MODEL_PATH, trust_remote_code=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        # Check available VRAM; NF4 9B needs ~6GB free
        use_gpu = torch.cuda.is_available() and os.environ.get("FORCE_CPU") != "1"
        if use_gpu:
            props = torch.cuda.get_device_properties(0)
            free_mb = (props.total_memory - torch.cuda.memory_allocated()) // (1024 * 1024)
            logger.info(
                f"GPU VRAM: {free_mb} MB free / {props.total_memory // (1024 * 1024)} MB total"
            )
            use_gpu = free_mb > 6500

        if use_gpu:
            from transformers import BitsAndBytesConfig

            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
            )
            logger.info("Loading model in NF4 on GPU...")
            model = AutoModelForCausalLM.from_pretrained(
                KTO_MODEL_PATH,
                quantization_config=bnb_config,
                device_map="cuda:0",
                dtype=torch.float16,
                low_cpu_mem_usage=True,
                trust_remote_code=True,
            )
        else:
            logger.info("Loading model in fp16 on CPU (close GPU apps for NF4 mode)...")
            model = AutoModelForCausalLM.from_pretrained(
                KTO_MODEL_PATH,
                device_map="cpu",
                trust_remote_code=True,
                torch_dtype=torch.float16,
            )
        model.eval()

        mem = get_gpu_memory_mb()
        logger.info(f"Model loaded. GPU memory: {mem:.0f} MB")
        return model, tokenizer
    finally:
        # Restore ConditionalGeneration config for Ollama
        if os.path.exists(cfg_ollama):
            shutil.copy(cfg_ollama, cfg_path)
            os.remove(cfg_ollama)
            logger.info("Restored config.json to ConditionalGeneration format")


def generate_with_cache(
    model,
    tokenizer,
    system: str,
    user: str,
    cache: Optional[object] = None,
    max_new_tokens: int = 256,
) -> dict:
    """Generate response with optional custom cache."""
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    input_text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(input_text, return_tensors="pt")
    inputs = {k: v.to(model.device) for k, v in inputs.items()}
    input_len = inputs["input_ids"].shape[1]

    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    mem_before = get_gpu_memory_mb()

    generate_kwargs = {
        **inputs,
        "max_new_tokens": max_new_tokens,
        "temperature": 1.0,
        "do_sample": True,
        "top_p": 0.95,
        "top_k": 20,
        "pad_token_id": tokenizer.eos_token_id,
    }
    if cache is not None:
        generate_kwargs["past_key_values"] = cache

    t0 = time.perf_counter()
    with torch.no_grad():
        outputs = model.generate(**generate_kwargs)
    elapsed = time.perf_counter() - t0

    output_ids = outputs[0][input_len:]
    n_tokens = len(output_ids)
    response = tokenizer.decode(output_ids, skip_special_tokens=True)

    mem_after = get_gpu_memory_mb()
    peak_mem = torch.cuda.max_memory_allocated() / 1024 / 1024 if torch.cuda.is_available() else 0.0

    return {
        "response": response,
        "n_tokens": n_tokens,
        "elapsed": elapsed,
        "tok_per_sec": n_tokens / elapsed if elapsed > 0 else 0,
        "mem_before": mem_before,
        "mem_after": mem_after,
        "peak_mem": peak_mem,
        "kv_cache_mem": peak_mem - mem_before,
    }


def main():
    logger.info("=" * 60)
    logger.info("TurboQuant End-to-End Inference Test (KTO model)")
    logger.info("=" * 60)

    model, tokenizer = load_model()
    model_mem = get_gpu_memory_mb()

    # Get head_dim from model config
    head_dim = getattr(model.config, "head_dim", 128)
    logger.info(f"Model head_dim: {head_dim}")

    results = {"standard": [], "turbo_3bit": []}

    for i, prompt in enumerate(TEST_PROMPTS):
        logger.info(f"\n--- Prompt {i + 1}/{len(TEST_PROMPTS)} ---")
        logger.info(f"  User: {prompt['user'][:80]}")

        # 1. Standard DynamicCache (baseline)
        logger.info("  [Standard cache]")
        gc.collect()
        torch.cuda.empty_cache()
        r_std = generate_with_cache(
            model, tokenizer, prompt["system"], prompt["user"], max_new_tokens=64
        )
        results["standard"].append(r_std)
        logger.info(
            f"    {r_std['n_tokens']} tok, {r_std['tok_per_sec']:.1f} tok/s, "
            f"peak={r_std['peak_mem']:.0f} MB, kv_overhead={r_std['kv_cache_mem']:.0f} MB"
        )
        logger.info(f"    Response: {r_std['response'][:200]}")

        # 2. TurboQuantCache 3-bit
        logger.info("  [TurboQuant 3-bit cache]")
        gc.collect()
        torch.cuda.empty_cache()

        from src.inference.turbo_quant import TurboQuantConfig
        from src.inference.turbo_quant_cache import TurboQuantCache

        # Pass layer_types for Qwen3.5 hybrid model support
        layer_types = getattr(model.config, "layer_types", None)
        tq_config = TurboQuantConfig(key_bits=3, value_bits=3, head_dim=head_dim)
        tq_cache = TurboQuantCache(tq_config, layer_types=layer_types)

        r_tq = generate_with_cache(
            model, tokenizer, prompt["system"], prompt["user"], cache=tq_cache, max_new_tokens=64
        )
        results["turbo_3bit"].append(r_tq)
        logger.info(
            f"    {r_tq['n_tokens']} tok, {r_tq['tok_per_sec']:.1f} tok/s, "
            f"peak={r_tq['peak_mem']:.0f} MB, kv_overhead={r_tq['kv_cache_mem']:.0f} MB"
        )
        logger.info(f"    Response: {r_tq['response'][:200]}")

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Model memory: {model_mem:.0f} MB")

    for mode in ["standard", "turbo_3bit"]:
        rs = results[mode]
        if not rs:
            continue
        n = len(rs)
        avg_tok_s = sum(r["tok_per_sec"] for r in rs) / n
        avg_peak = sum(r["peak_mem"] for r in rs) / n
        avg_kv = sum(r["kv_cache_mem"] for r in rs) / n
        logger.info(
            f"  {mode:12s}: speed={avg_tok_s:.1f} tok/s, "
            f"peak={avg_peak:.0f} MB, kv_overhead={avg_kv:.0f} MB"
        )

    # Compression ratio
    std_kv = sum(r["kv_cache_mem"] for r in results["standard"])
    tq_kv = sum(r["kv_cache_mem"] for r in results["turbo_3bit"])
    if tq_kv > 0:
        ratio = std_kv / tq_kv
        savings = (1 - tq_kv / std_kv) * 100 if std_kv > 0 else 0
        logger.info(f"\n  KV cache compression: {ratio:.1f}x ({savings:.0f}% savings)")

    logger.info("\nDone.")


if __name__ == "__main__":
    main()
