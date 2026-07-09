"""
MITS HuggingFace Model Client

Client for fine-tuned HuggingFace models.
API-compatible with LLMClient for seamless backend switching.
"""

import re
from threading import Thread
from typing import Any, Callable, Dict, Generator, List, Optional

import structlog
import torch
from peft import PeftModel
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TextIteratorStreamer,
)

from src.config import settings
from src.inference.turbo_quant import TurboQuantConfig
from src.inference.turbo_quant_cache import TurboQuantCache

logger = structlog.get_logger()


class HuggingFaceClient:
    """
    Client for HuggingFace models - API compatible with LLMClient.

    Features:
    - Load fine-tuned models (base + LoRA adapter)
    - 4-bit quantization support
    - JSON mode for structured output
    - Streaming generation with callbacks
    - Thinking mode parsing (same as Nemotron/Qwen)
    - TurboQuant KV cache compression (arXiv:2504.19874)
    """

    def __init__(
        self,
        model_path: str = None,
        adapter_path: Optional[str] = None,
        quantize: bool = None,
        device: str = "auto",
        turbo_quant_config: Optional[TurboQuantConfig] = None,
        max_memory_gib: Optional[float] = None,
    ):
        """
        Initialize HuggingFace client.

        Args:
            model_path: Path to base model or HuggingFace model ID
            adapter_path: Optional path to LoRA adapter
            quantize: Use 4-bit quantization (default from settings)
            device: "auto" | "cuda" | "cpu". If "cuda" — pins everything to GPU:0
                with explicit max_memory, bypassing Accelerate's conservative
                heuristic that tries to split small models to CPU.
            max_memory_gib: Explicit GPU memory budget (e.g. 7.0 for RTX 2080 8GB).
                Only used when device="cuda" or "auto". Auto-detected if None.
        """
        self.model_path = model_path or getattr(settings, "HF_MODEL_PATH", None)
        self.adapter_path = adapter_path or getattr(settings, "HF_ADAPTER_PATH", None)
        self.quantize = quantize if quantize is not None else getattr(settings, "HF_QUANTIZE", True)
        self.device = device
        self.turbo_quant_config = turbo_quant_config

        if not self.model_path:
            raise ValueError(
                "model_path is required. Set HF_MODEL_PATH in config or pass directly."
            )

        logger.info(
            "hf_client_initializing",
            model=self.model_path,
            adapter=self.adapter_path,
            quantize=self.quantize,
        )

        # Setup quantization
        bnb_config = None
        if self.quantize:
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
            )

        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_path, trust_remote_code=True)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        # ── Device mapping: pin entire model to GPU:0 ──
        # Accelerate's "auto" with max_memory budget uses a predictive heuristic
        # that over-estimates model footprint for 9B+bnb4bit on 8GB cards and
        # refuses to load (even when it would actually fit). Passing an explicit
        # dict device_map={"": 0} bypasses the predictor — bnb gets everything
        # on GPU as required, and real OOM surfaces only if it truly can't fit.
        if torch.cuda.is_available() and device in ("auto", "cuda"):
            device_map_kwarg: Any = {"": 0}
            free_bytes, total_bytes = torch.cuda.mem_get_info(0)
            logger.info(
                "hf_device_map_pinned",
                device=0,
                free_gib=round(free_bytes / (1024**3), 2),
                total_gib=round(total_bytes / (1024**3), 2),
            )
        elif device == "cpu":
            device_map_kwarg = {"": "cpu"}
        else:
            device_map_kwarg = device

        # Load model (low_cpu_mem_usage=True streams weights layer-by-layer,
        # avoiding the 2× peak RAM during sharded loading)
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_path,
            quantization_config=bnb_config,
            device_map=device_map_kwarg,
            low_cpu_mem_usage=True,
            trust_remote_code=True,
            torch_dtype=torch.bfloat16,
        )

        # Load LoRA adapter if provided
        if self.adapter_path:
            logger.info("loading_lora_adapter", path=self.adapter_path)
            self.model = PeftModel.from_pretrained(self.model, self.adapter_path)

        self.model.eval()

        # Initialize TurboQuant if configured
        if self.turbo_quant_config:
            logger.info(
                "turbo_quant_enabled",
                key_bits=self.turbo_quant_config.key_bits,
                value_bits=self.turbo_quant_config.value_bits,
            )

        logger.info("hf_client_initialized", model=self.model_path)

    def _create_kv_cache(self) -> Optional[TurboQuantCache]:
        """Create TurboQuant KV cache if configured.

        For hybrid architectures (Qwen3.5 uses mamba/linear-attn + transformer),
        passes the per-layer type map so the cache keeps conv/recurrent states
        separate from quantized KV.
        """
        if self.turbo_quant_config is None:
            return None

        # Detect hybrid layer structure (Qwen3.5 interleaves linear_attention
        # and full_attention blocks). Fallback to None → cache treats all layers
        # as full attention (only correct for pure transformer models).
        layer_types = None
        try:
            cfg = self.model.config
            if hasattr(cfg, "layer_types") and cfg.layer_types is not None:
                layer_types = list(cfg.layer_types)
            elif hasattr(cfg, "layers_block_type") and cfg.layers_block_type is not None:
                # Some hybrid configs use layers_block_type: ["attention", "mamba", ...]
                mapping = {"attention": "full_attention", "mamba": "linear_attention"}
                layer_types = [mapping.get(t, t) for t in cfg.layers_block_type]
        except Exception:
            layer_types = None

        device = next(self.model.parameters()).device
        return TurboQuantCache(
            self.turbo_quant_config,
            device=device,
            layer_types=layer_types,
        )

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = None,
        max_tokens: int = None,
        thinking: bool = None,
        json_mode: bool = False,
    ) -> str:
        """
        Generate a completion - API compatible with LLMClient.

        Args:
            prompt: User prompt
            system: System prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            thinking: Parse <think> tags (for API compatibility)
            json_mode: Request JSON output

        Returns:
            Generated text
        """
        temperature = temperature or settings.TEMPERATURE
        max_tokens = max_tokens or settings.MAX_TOKENS
        thinking = thinking if thinking is not None else settings.THINKING_MODE

        # Build messages
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        # Apply chat template
        input_text = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        # Tokenize
        inputs = self.tokenizer(input_text, return_tensors="pt")
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}

        # Generate (with optional TurboQuant KV cache)
        kv_cache = self._create_kv_cache()
        generate_kwargs = {
            **inputs,
            "max_new_tokens": max_tokens,
            "temperature": temperature if temperature > 0 else 1.0,
            "do_sample": temperature > 0,
            "pad_token_id": self.tokenizer.eos_token_id,
            "eos_token_id": self.tokenizer.eos_token_id,
        }
        if kv_cache is not None:
            generate_kwargs["past_key_values"] = kv_cache

        with torch.no_grad():
            outputs = self.model.generate(**generate_kwargs)

        # Decode
        response = self.tokenizer.decode(
            outputs[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True
        )

        # Parse thinking tags if present
        if thinking and "<think>" in response:
            _, response = self._parse_thinking(response)

        # Extract JSON if requested
        if json_mode:
            response = self._extract_json(response)

        return response.strip()

    def generate_stream(
        self,
        prompt: str,
        system: Optional[str] = None,
        thinking: bool = None,
        json_mode: bool = False,
        on_token: Optional[Callable[[str], None]] = None,
        on_thinking: Optional[Callable[[str], None]] = None,
        **kwargs,
    ) -> Generator[str, None, None]:
        """
        Stream generation for real-time UI - API compatible with LLMClient.

        Args:
            prompt: User prompt
            system: System prompt
            thinking: Parse <think> tags
            json_mode: Request JSON output
            on_token: Callback for each token
            on_thinking: Callback for thinking content

        Yields:
            Generated tokens
        """
        thinking = thinking if thinking is not None else settings.THINKING_MODE
        temperature = kwargs.get("temperature", settings.TEMPERATURE)
        max_tokens = kwargs.get("max_tokens", settings.MAX_TOKENS)

        # Build messages
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        input_text = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        inputs = self.tokenizer(input_text, return_tensors="pt")
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}

        # Setup streamer
        streamer = TextIteratorStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)

        # Generate in thread (with optional TurboQuant KV cache)
        kv_cache = self._create_kv_cache()
        generation_kwargs = {
            **inputs,
            "streamer": streamer,
            "max_new_tokens": max_tokens,
            "temperature": temperature if temperature > 0 else 1.0,
            "do_sample": temperature > 0,
            "pad_token_id": self.tokenizer.eos_token_id,
        }
        if kv_cache is not None:
            generation_kwargs["past_key_values"] = kv_cache

        thread = Thread(target=self.model.generate, kwargs=generation_kwargs)
        thread.start()

        # Process stream with thinking mode handling
        full_response = ""
        in_thinking = False
        thinking_buffer = ""

        for token in streamer:
            full_response += token

            if thinking:
                # Handle thinking tags
                if "<think>" in full_response and not in_thinking:
                    in_thinking = True
                    continue

                if in_thinking:
                    if "</think>" in full_response:
                        # End of thinking
                        in_thinking = False
                        idx = full_response.find("</think>")
                        thinking_buffer = full_response[full_response.find("<think>") + 7 : idx]
                        response_part = full_response[idx + 8 :]

                        if on_thinking:
                            on_thinking(thinking_buffer)

                        # Yield response part
                        if response_part:
                            if on_token:
                                on_token(response_part)
                            yield response_part
                    else:
                        # Still in thinking
                        thinking_buffer += token
                        continue
                else:
                    # After thinking or no thinking
                    if on_token:
                        on_token(token)
                    yield token
            else:
                # No thinking mode
                if on_token:
                    on_token(token)
                yield token

        thread.join()

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Chat with conversation history - API compatible with LLMClient.

        Args:
            messages: List of {"role": "user/assistant/system", "content": "..."}

        Returns:
            Assistant response
        """
        temperature = kwargs.get("temperature", settings.TEMPERATURE)
        max_tokens = kwargs.get("max_tokens", settings.MAX_TOKENS)

        input_text = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        inputs = self.tokenizer(input_text, return_tensors="pt")
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}

        kv_cache = self._create_kv_cache()
        generate_kwargs = {
            **inputs,
            "max_new_tokens": max_tokens,
            "temperature": temperature if temperature > 0 else 1.0,
            "do_sample": temperature > 0,
            "pad_token_id": self.tokenizer.eos_token_id,
        }
        if kv_cache is not None:
            generate_kwargs["past_key_values"] = kv_cache

        with torch.no_grad():
            outputs = self.model.generate(**generate_kwargs)

        return self.tokenizer.decode(
            outputs[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True
        ).strip()

    def chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> Generator[str, None, None]:
        """
        Chat with conversation history - streaming version.

        Args:
            messages: Conversation history

        Yields:
            Generated tokens
        """
        temperature = kwargs.get("temperature", settings.TEMPERATURE)
        max_tokens = kwargs.get("max_tokens", settings.MAX_TOKENS)

        input_text = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        inputs = self.tokenizer(input_text, return_tensors="pt")
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}

        streamer = TextIteratorStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)

        kv_cache = self._create_kv_cache()
        generation_kwargs = {
            **inputs,
            "streamer": streamer,
            "max_new_tokens": max_tokens,
            "temperature": temperature if temperature > 0 else 1.0,
            "do_sample": temperature > 0,
            "pad_token_id": self.tokenizer.eos_token_id,
        }
        if kv_cache is not None:
            generation_kwargs["past_key_values"] = kv_cache

        thread = Thread(target=self.model.generate, kwargs=generation_kwargs)
        thread.start()

        for token in streamer:
            yield token

        thread.join()

    def _parse_thinking(self, content: str) -> tuple:
        """Parse thinking output from <think> tags."""
        think_match = re.search(r"<think>(.*?)</think>", content, re.DOTALL)
        thinking = think_match.group(1).strip() if think_match else ""
        response = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        return thinking, response

    def _extract_json(self, text: str) -> str:
        """Extract JSON object from response text."""
        # Try to find JSON object
        match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if match:
            return match.group(0)
        return text

    def check_connection(self) -> bool:
        """Always return True for local model."""
        return True

    def list_models(self) -> List[str]:
        """Return loaded model."""
        return [self.model_path]

    def get_model_info(self) -> Dict[str, Any]:
        """Get model information."""
        return {
            "model_path": self.model_path,
            "adapter_path": self.adapter_path,
            "quantized": self.quantize,
            "device": str(self.model.device),
            "dtype": str(self.model.dtype),
        }


# ═══════════════════════════════════════════════════════════════════════════
# Factory Function
# ═══════════════════════════════════════════════════════════════════════════


def create_client(backend: str = None, **kwargs):
    """
    Create appropriate LLM client based on backend setting.

    Args:
        backend: "ollama" or "huggingface" (default from settings)
        **kwargs: Backend-specific arguments.
            For HuggingFace backend, pass turbo_quant_config=TurboQuantConfig(...)
            to enable TurboQuant KV cache compression.

    Returns:
        LLMClient or HuggingFaceClient instance
    """
    backend = backend or getattr(settings, "MODEL_BACKEND", "ollama")

    if backend == "ollama":
        from src.models.llm_client import LLMClient

        # TurboQuant not applicable to Ollama (uses llama.cpp quantization)
        kwargs.pop("turbo_quant_config", None)
        return LLMClient(**kwargs)
    elif backend == "huggingface":
        return HuggingFaceClient(**kwargs)
    else:
        raise ValueError(f"Unknown backend: {backend}. Use 'ollama' or 'huggingface'.")


def create_client_from_config(config_name: str):
    """Create LLM client from a named ModelConfiguration.

    Automatically sets up TurboQuant if enabled in the config.

    Args:
        config_name: Key in MODEL_CONFIGS (e.g. "qwen3.5-9b-turbo").

    Returns:
        Configured LLM client instance.
    """
    from src.inference.model_config import get_model_config

    config = get_model_config(config_name)
    if config is None:
        raise ValueError(f"Unknown model config: {config_name}")

    if config.backend == "huggingface":
        tq_config = None
        if config.turbo_quant_enabled:
            tq_config = TurboQuantConfig(
                key_bits=config.turbo_quant_key_bits,
                value_bits=config.turbo_quant_value_bits,
            )
        return HuggingFaceClient(
            model_path=config.hf_model_path,
            adapter_path=config.hf_adapter_path,
            turbo_quant_config=tq_config,
        )
    elif config.backend in ("ollama", "llama.cpp"):
        from src.models.llm_client import LLMClient

        return LLMClient(model=config.ollama_model)
    else:
        raise ValueError(f"Unknown backend: {config.backend}")
