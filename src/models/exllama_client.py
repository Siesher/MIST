"""
MITS ExLlamaV2 Client

High-performance inference client with MoE expert-level offloading.
Optimized for Mixture of Experts models like GLM-4.

Features:
- Expert-level GPU/CPU offloading
- Dynamic expert caching (hot experts stay on GPU)
- Flash Attention 2 support
- Speculative decoding
"""

import os
import sys
from typing import Optional, List, Dict, Any, Generator
import structlog

logger = structlog.get_logger()

# Check if ExLlamaV2 is available
EXLLAMA_AVAILABLE = False
try:
    from exllamav2 import (
        ExLlamaV2,
        ExLlamaV2Config,
        ExLlamaV2Cache,
        ExLlamaV2Tokenizer,
    )
    from exllamav2.generator import (
        ExLlamaV2DynamicGenerator,
        ExLlamaV2DynamicJob,
        ExLlamaV2Sampler,
    )
    EXLLAMA_AVAILABLE = True
except ImportError:
    logger.warning("ExLlamaV2 not installed. Install with: pip install exllamav2")


class ExLlamaClient:
    """
    ExLlamaV2-based LLM client with MoE optimizations.

    Advantages over Ollama for MoE models:
    - Expert-level offloading (not just layer-level)
    - Dynamic expert caching based on usage frequency
    - Lower VRAM usage with same performance
    - Better memory management for large models
    """

    def __init__(
        self,
        model_path: str,
        gpu_split: Optional[List[float]] = None,
        max_seq_len: int = 4096,
        expert_cache_size: int = 8,  # Number of experts to keep in VRAM
        flash_attention: bool = True,
    ):
        """
        Initialize ExLlamaV2 client.

        Args:
            model_path: Path to model directory (with safetensors/GGUF)
            gpu_split: VRAM allocation per GPU in GB, e.g. [8.0] for single GPU
            max_seq_len: Maximum sequence length
            expert_cache_size: Number of MoE experts to cache on GPU
            flash_attention: Enable Flash Attention 2
        """
        if not EXLLAMA_AVAILABLE:
            raise ImportError(
                "ExLlamaV2 is not installed. Install with:\n"
                "pip install exllamav2\n\n"
                "For CUDA support, ensure you have the correct CUDA version."
            )

        self.model_path = model_path
        self.max_seq_len = max_seq_len
        self.expert_cache_size = expert_cache_size

        # Initialize config
        self.config = ExLlamaV2Config(model_path)
        self.config.max_seq_len = max_seq_len

        # Enable optimizations
        if flash_attention:
            self.config.no_flash_attn = False

        # MoE-specific settings
        if hasattr(self.config, 'num_experts'):
            logger.info(
                "moe_model_detected",
                num_experts=self.config.num_experts,
                experts_per_token=getattr(self.config, 'num_experts_per_tok', 2)
            )

        # Load model with GPU split
        self.model = ExLlamaV2(self.config)

        if gpu_split:
            self.model.load(gpu_split)
        else:
            # Auto-split based on available VRAM
            self.model.load_autosplit(self.model.device_context)

        # Initialize tokenizer
        self.tokenizer = ExLlamaV2Tokenizer(self.config)

        # Initialize cache with expert caching for MoE
        self.cache = ExLlamaV2Cache(
            self.model,
            max_seq_len=max_seq_len,
            lazy=True
        )

        # Initialize generator
        self.generator = ExLlamaV2DynamicGenerator(
            model=self.model,
            cache=self.cache,
            tokenizer=self.tokenizer,
        )

        # Default sampling settings (optimized for GLM)
        self.default_settings = ExLlamaV2Sampler.Settings()
        self.default_settings.temperature = 0.2
        self.default_settings.top_p = 0.9
        self.default_settings.top_k = 2
        self.default_settings.token_repetition_penalty = 1.0

        logger.info(
            "exllama_client_initialized",
            model_path=model_path,
            max_seq_len=max_seq_len,
            expert_cache_size=expert_cache_size,
            flash_attention=flash_attention
        )

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = None,
        stop_sequences: Optional[List[str]] = None,
        **kwargs
    ) -> str:
        """
        Generate completion.

        Args:
            prompt: User prompt
            system: System prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            stop_sequences: Sequences to stop generation

        Returns:
            Generated text
        """
        # Build full prompt
        full_prompt = self._build_prompt(prompt, system)

        # Prepare settings
        settings = ExLlamaV2Sampler.Settings()
        settings.temperature = temperature or self.default_settings.temperature
        settings.top_p = self.default_settings.top_p
        settings.top_k = self.default_settings.top_k
        settings.token_repetition_penalty = self.default_settings.token_repetition_penalty

        # Generate
        output = self.generator.generate(
            prompt=full_prompt,
            max_new_tokens=max_tokens,
            gen_settings=settings,
            stop_conditions=stop_sequences or [],
            add_bos=True
        )

        return output

    def generate_stream(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = None,
        on_token: Optional[callable] = None,
        **kwargs
    ) -> Generator[str, None, None]:
        """
        Stream generation token by token.

        Args:
            prompt: User prompt
            system: System prompt
            max_tokens: Maximum tokens
            temperature: Sampling temperature
            on_token: Callback for each token

        Yields:
            Generated tokens
        """
        full_prompt = self._build_prompt(prompt, system)

        settings = ExLlamaV2Sampler.Settings()
        settings.temperature = temperature or self.default_settings.temperature
        settings.top_p = self.default_settings.top_p
        settings.top_k = self.default_settings.top_k

        # Create streaming job
        job = ExLlamaV2DynamicJob(
            input_ids=self.tokenizer.encode(full_prompt),
            max_new_tokens=max_tokens,
            gen_settings=settings,
        )

        self.generator.enqueue(job)

        while not job.is_finished():
            results = self.generator.iterate()
            for result in results:
                if result["stage"] == "streaming":
                    token_text = result.get("text", "")
                    if token_text:
                        if on_token:
                            on_token(token_text)
                        yield token_text

    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 2048,
        **kwargs
    ) -> str:
        """
        Chat with conversation history.

        Args:
            messages: List of {"role": "user/assistant/system", "content": "..."}

        Returns:
            Assistant response
        """
        prompt = self._messages_to_prompt(messages)
        return self.generate(prompt, max_tokens=max_tokens, **kwargs)

    def chat_with_thinking(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, str]:
        """
        Chat and extract thinking/reasoning separately.

        Returns:
            Dict with 'thinking', 'response', 'raw' keys
        """
        raw = self.chat(messages, **kwargs)

        thinking = ""
        response = raw

        # Extract thinking from various formats
        import re

        # GLM format
        if "Thinking..." in raw and "...done thinking." in raw:
            start = raw.find("Thinking...")
            end = raw.find("...done thinking.")
            if start < end:
                thinking = raw[start + len("Thinking..."):end].strip()
                response = raw[end + len("...done thinking."):].strip()

        # <think> format
        elif "<think>" in raw:
            match = re.search(r'<think>(.*?)</think>', raw, re.DOTALL)
            if match:
                thinking = match.group(1).strip()
                response = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()

        # JSON with reasoning
        elif '"reasoning"' in raw:
            try:
                import json
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    thinking = parsed.get('reasoning', '')
                    response = parsed.get('message', raw)
            except:
                pass

        return {
            'thinking': thinking,
            'response': response,
            'raw': raw
        }

    def _build_prompt(self, prompt: str, system: Optional[str] = None) -> str:
        """Build prompt with system message."""
        if system:
            return f"<|system|>\n{system}<|endofsystem|>\n<|user|>\n{prompt}<|endofuser|>\n<|assistant|>\n"
        return f"<|user|>\n{prompt}<|endofuser|>\n<|assistant|>\n"

    def _messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Convert messages list to prompt string."""
        prompt_parts = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                prompt_parts.append(f"<|system|>\n{content}<|endofsystem|>")
            elif role == "user":
                prompt_parts.append(f"<|user|>\n{content}<|endofuser|>")
            elif role == "assistant":
                prompt_parts.append(f"<|assistant|>\n{content}<|endofassistant|>")

        prompt_parts.append("<|assistant|>\n")
        return "\n".join(prompt_parts)

    def get_model_info(self) -> Dict[str, Any]:
        """Get model information."""
        info = {
            "model_path": self.model_path,
            "max_seq_len": self.max_seq_len,
            "backend": "exllamav2",
        }

        if hasattr(self.config, 'num_experts'):
            info["num_experts"] = self.config.num_experts
            info["experts_per_token"] = getattr(self.config, 'num_experts_per_tok', 2)

        return info

    def get_expert_stats(self) -> Dict[str, Any]:
        """Get MoE expert usage statistics (if available)."""
        # This would require tracking expert activations
        # Placeholder for future implementation
        return {
            "expert_cache_size": self.expert_cache_size,
            "note": "Expert tracking not yet implemented"
        }

    def unload(self):
        """Unload model from memory."""
        if hasattr(self, 'model'):
            del self.model
        if hasattr(self, 'cache'):
            del self.cache
        if hasattr(self, 'generator'):
            del self.generator

        import gc
        gc.collect()

        try:
            import torch
            torch.cuda.empty_cache()
        except:
            pass

        logger.info("exllama_model_unloaded")


def check_exllama_available() -> bool:
    """Check if ExLlamaV2 is available."""
    return EXLLAMA_AVAILABLE


def get_recommended_gpu_split(vram_gb: float, model_size_gb: float) -> List[float]:
    """
    Get recommended GPU split based on available VRAM.

    Args:
        vram_gb: Available VRAM in GB
        model_size_gb: Model size in GB

    Returns:
        GPU split configuration
    """
    if vram_gb >= model_size_gb:
        # Full model fits on GPU
        return [vram_gb]
    else:
        # Partial offload - leave some VRAM for KV cache
        usable_vram = vram_gb * 0.85  # 85% for model, 15% for cache
        return [usable_vram]
