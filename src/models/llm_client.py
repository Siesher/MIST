"""
MITS LLM Client

Client for interacting with Ollama LLM backend.
Supports streaming, thinking mode, and JSON mode.
"""

import json
import re
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple

import ollama
import structlog

from src.config import settings

logger = structlog.get_logger()


class LLMClient:
    """
    Client for Ollama LLM interactions.

    Features:
    - Thinking mode support (Nemotron <think>, Qwen3 /think, GLM reasoning)
    - JSON mode for structured output
    - Streaming generation with callbacks
    - Conversation management
    - Model-specific sampling parameters

    Supported models:
    - glm-4.7-flash: Uses internal reasoning, temp=0.2, rep_penalty=1.0
    - deepseek-r1: Chain-of-thought reasoning, temp=0.3
    - nemotron-3-nano: Uses <think> tags automatically
    - qwen3: Uses /think prefix to enable thinking
    """

    def __init__(
        self,
        model: str = None,
        host: str = None,
        temperature: float = None,
        max_tokens: int = None,
    ):
        self.host = host or settings.OLLAMA_HOST
        # timeout: повисший Ollama-сервер без него блокировал поток навсегда
        # (10 мин — потолок на длинную генерацию с thinking)
        self.client = ollama.Client(host=self.host, timeout=600)

        # Resolve model with fallback support
        requested_model = model or settings.MODEL_NAME
        self.model = self._resolve_model_with_fallback(requested_model)

        # Model-specific defaults
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._apply_model_defaults()

        # Log hardware configuration
        gpu_layers = getattr(settings, "GPU_LAYERS", "auto")
        ctx_length = getattr(settings, "CONTEXT_LENGTH", 4096)
        logger.info(
            "llm_client_initialized",
            model=self.model,
            host=self.host,
            gpu_layers=gpu_layers,
            context_length=ctx_length,
        )

    def _resolve_model_with_fallback(self, requested_model: str) -> str:
        """
        Check if requested model is available, fall back to fallback model if not.

        Args:
            requested_model: The model to try first

        Returns:
            Available model name (requested or fallback)
        """
        try:
            available_models = self.list_models()

            # Check if requested model is available
            if any(requested_model in m for m in available_models):
                return requested_model

            # Try fallback
            fallback_model = getattr(settings, "MODEL_FALLBACK", None)
            if fallback_model and any(fallback_model in m for m in available_models):
                logger.warning(
                    "model_fallback_activated",
                    requested=requested_model,
                    fallback=fallback_model,
                    reason="requested model not available",
                )
                return fallback_model

            # Neither available - return requested and let it fail naturally
            logger.warning(
                "model_not_found",
                requested=requested_model,
                available=available_models[:5],  # Log first 5
            )
            return requested_model

        except Exception as e:
            # Ollama not reachable - return requested model
            logger.warning("ollama_unreachable", error=str(e))
            return requested_model

    def _apply_model_defaults(self):
        """Apply model-specific default parameters."""
        model_lower = self.model.lower()

        # MITS fine-tuned models (Qwen3.5-9B based, thinking mode)
        # Modelfile has RENDERER qwen3.5, so thinking is handled by Ollama
        if "mits" in model_lower:
            if self._temperature is None:
                self._temperature = 1.0  # Thinking mode needs high exploration
            self._top_p = 0.95
            self._top_k = 20
            self._min_p = 0.0
            self._repetition_penalty = 1.0

        # Qwen2.5: excellent Russian support, standard parameters
        elif "qwen" in model_lower:
            if self._temperature is None:
                self._temperature = getattr(settings, "TEMPERATURE", 0.7)
            self._top_p = getattr(settings, "TOP_P", 0.9)
            self._top_k = getattr(settings, "TOP_K", 40)
            self._min_p = getattr(settings, "MIN_P", 0.0)
            self._repetition_penalty = getattr(settings, "REPETITION_PENALTY", 1.05)

        # REAP-pruned GLM: use config settings (higher temp needed, min_p for stability)
        elif "reap" in model_lower:
            if self._temperature is None:
                self._temperature = settings.TEMPERATURE  # 0.7 default
            self._top_p = getattr(settings, "TOP_P", 0.95)
            self._top_k = getattr(settings, "TOP_K", 0)
            self._min_p = getattr(settings, "MIN_P", 0.01)
            self._repetition_penalty = 1.0  # CRITICAL: DO NOT increase

        # Original GLM models: temp=0.3, rep_penalty=1.0 (higher causes repetition!)
        # Use config values but with sensible defaults
        elif "glm" in model_lower:
            if self._temperature is None:
                self._temperature = getattr(settings, "TEMPERATURE", 0.3)
            self._top_p = getattr(settings, "TOP_P", 0.9)
            self._top_k = getattr(settings, "TOP_K", 20)  # Higher top_k prevents repetition loops
            self._min_p = getattr(settings, "MIN_P", 0.0)
            self._repetition_penalty = 1.0  # CRITICAL: DO NOT increase

        # DeepSeek-R1: temp=0.3 for reasoning
        elif "deepseek" in model_lower:
            if self._temperature is None:
                self._temperature = 0.3
            self._top_p = 0.95
            self._top_k = 50
            self._min_p = 0.0
            self._repetition_penalty = 1.0

        # Qwen/Nemotron: use config defaults
        else:
            if self._temperature is None:
                self._temperature = settings.TEMPERATURE
            self._top_p = getattr(settings, "TOP_P", 0.9)
            self._top_k = getattr(settings, "TOP_K", 50)
            self._min_p = getattr(settings, "MIN_P", 0.0)
            self._repetition_penalty = getattr(settings, "REPETITION_PENALTY", 1.0)

        if self._max_tokens is None:
            self._max_tokens = settings.MAX_TOKENS

    def _is_mits_model(self) -> bool:
        """Check if current model is MITS fine-tuned (Qwen3.5-9B based)."""
        return "mits" in self.model.lower()

    def _is_reap_model(self) -> bool:
        """Check if current model is REAP-pruned GLM."""
        return "reap" in self.model.lower()

    def _is_glm_model(self) -> bool:
        """Check if current model is GLM (including REAP variant)."""
        return "glm" in self.model.lower()

    def _is_deepseek_model(self) -> bool:
        """Check if current model is DeepSeek."""
        return "deepseek" in self.model.lower()

    def _is_qwen_model(self) -> bool:
        """Check if current model is Qwen."""
        return "qwen" in self.model.lower()

    def _get_options(self, temperature: float = None, max_tokens: int = None) -> dict:
        """Get model-specific options for Ollama API."""
        temp = temperature if temperature is not None else self._temperature

        options = {
            "temperature": temp,
            "top_p": self._top_p,
            "top_k": self._top_k,
            "repeat_penalty": self._repetition_penalty,
        }

        # min_p sampling (key for REAP model stability)
        min_p = getattr(self, "_min_p", 0.0)
        if min_p > 0:
            options["min_p"] = min_p

        # GPU/CPU offload settings
        gpu_layers = getattr(settings, "GPU_LAYERS", None)
        if gpu_layers is not None and gpu_layers >= 0:
            options["num_gpu"] = gpu_layers

        # Context length
        context_length = getattr(settings, "CONTEXT_LENGTH", None)
        if context_length:
            options["num_ctx"] = context_length

        # KV cache quantization (reduces VRAM usage)
        kv_cache_k = getattr(settings, "KV_CACHE_K_TYPE", None)
        kv_cache_v = getattr(settings, "KV_CACHE_V_TYPE", None)
        if kv_cache_k:
            options["cache_type_k"] = kv_cache_k
        if kv_cache_v:
            options["cache_type_v"] = kv_cache_v

        # Flash Attention (Turing+ GPUs: RTX 2080, 3080, 4080, etc.)
        flash_attn = getattr(settings, "FLASH_ATTENTION", False)
        if flash_attn:
            options["flash_attn"] = True

        # CPU thread count (0 = auto-detect)
        num_thread = getattr(settings, "NUM_THREAD", 0)
        if num_thread > 0:
            options["num_thread"] = num_thread

        # Batch size for prompt processing
        num_batch = getattr(settings, "NUM_BATCH", None)
        if num_batch:
            options["num_batch"] = num_batch

        # GLM bug: num_predict causes empty responses for short prompts
        # Only set num_predict for non-GLM models or when explicitly needed
        if not self._is_glm_model():
            max_tok = max_tokens if max_tokens is not None else self._max_tokens
            options["num_predict"] = max_tok

        # Speculative decoding (arXiv 2302.01318): draft model proposes N tokens,
        # main model verifies in one batched forward. 1.5-3x speedup on predictable
        # sequences (math/code). No quality loss - final tokens match greedy main model.
        # Настройки — из src.config (та же .env, что у backend/): src/ не
        # импортирует backend/ (направление слоёв).
        if settings.SPECULATIVE_DECODING and settings.SPECULATIVE_DRAFT_MODEL:
            options["draft_model"] = settings.SPECULATIVE_DRAFT_MODEL
            options["num_draft"] = int(settings.SPECULATIVE_NUM_DRAFT)

        return options

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
        Generate a completion from the LLM.

        Args:
            prompt: User prompt
            system: System prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            thinking: Enable Qwen3 thinking mode
            json_mode: Request JSON output

        Returns:
            Generated text
        """
        thinking = thinking if thinking is not None else settings.THINKING_MODE

        messages = []
        if system:
            messages.append({"role": "system", "content": system})

        # Thinking mode handling:
        # - GLM: uses internal reasoning, no prefix needed, just lower temp
        # - DeepSeek-R1: chain-of-thought built-in
        # - Nemotron: generates <think> automatically, no prefix needed
        # - Qwen3: requires /think prefix to enable thinking
        user_content = prompt
        if thinking and self._is_qwen_model() and not prompt.startswith("/think"):
            user_content = f"/think\n{prompt}"

        messages.append({"role": "user", "content": user_content})

        options = self._get_options(temperature, max_tokens)

        if json_mode:
            options["format"] = "json"

        try:
            # Ollama 0.4+ supports top-level `think` param for Qwen3.5-family
            # models (RENDERER qwen3.5). When think=False, model skips the
            # hidden thinking block and puts content directly in message.content.
            # Critical for JSON mode: thinking tokens eat the max_tokens budget,
            # leaving empty content.
            chat_kwargs = {
                "model": self.model,
                "messages": messages,
                "options": options,
                "keep_alive": "30m",
            }
            if thinking is False:
                chat_kwargs["think"] = False

            response = self.client.chat(**chat_kwargs)

            content = response["message"]["content"]

            # Extract response from thinking tags if present
            if thinking:
                # GLM format: "Thinking...\n...\n...done thinking.\n[response]"
                if "...done thinking." in content:
                    thinking_content, response_content = self._parse_glm_thinking(content)
                    logger.debug(
                        "glm_thinking_extracted",
                        thinking_length=len(thinking_content),
                        response_length=len(response_content),
                    )
                    return response_content
                # Qwen/Nemotron format: "<think>...</think>[response]"
                elif "<think>" in content:
                    thinking_content, response_content = self._parse_thinking(content)
                    logger.debug(
                        "thinking_extracted",
                        thinking_length=len(thinking_content),
                        response_length=len(response_content),
                    )
                    return response_content

            return content

        except Exception as e:
            logger.error("llm_generation_failed", error=str(e))
            raise

    def generate_stream(
        self,
        prompt: str,
        system: Optional[str] = None,
        thinking: bool = None,
        json_mode: bool = False,
        on_token: Optional[Callable[[str], None]] = None,
        on_thinking: Optional[Callable[[str], None]] = None,
        **kwargs,
    ) -> Generator[Tuple[str, str], None, None]:
        """
        Stream generation for real-time UI.

        Args:
            prompt: User prompt
            system: System prompt
            thinking: Enable thinking mode
            json_mode: Request JSON output
            on_token: Callback for each token (for UI updates)
            on_thinking: Callback for thinking content

        Yields:
            ("thinking" | "content", token) — тот же контракт, что у
            OpenAICompatLLMClient.generate_stream (аннотация Generator[str]
            была стейл: тело всегда yield'ило кортежи).
        """
        thinking = thinking if thinking is not None else settings.THINKING_MODE

        messages = []
        if system:
            messages.append({"role": "system", "content": system})

        # Thinking mode handling (same as generate)
        user_content = prompt
        if thinking and self._is_qwen_model() and not prompt.startswith("/think"):
            user_content = f"/think\n{prompt}"

        messages.append({"role": "user", "content": user_content})

        options = self._get_options(kwargs.get("temperature"), kwargs.get("max_tokens"))

        if json_mode:
            options["format"] = "json"

        try:
            stream = self.client.chat(
                model=self.model,
                messages=messages,
                stream=True,
                options=options,
                keep_alive="30m",  # Keep model loaded
            )

            full_response = ""
            in_thinking = False
            thinking_buffer = ""
            response_buffer = ""

            first_chunk_logged = False
            for chunk in stream:
                # Handle both dict and Pydantic model responses (ollama-python >= 0.3)
                token = ""
                thinking_token = ""

                if hasattr(chunk, "message"):
                    message = chunk.message
                    # GLM models output to 'thinking' field for CoT, 'content' for response
                    if hasattr(message, "thinking"):
                        thinking_token = message.thinking or ""
                    if hasattr(message, "content"):
                        token = message.content or ""
                    elif isinstance(message, dict):
                        thinking_token = message.get("thinking", "")
                        token = message.get("content", "")
                elif isinstance(chunk, dict):
                    msg = chunk.get("message", {})
                    thinking_token = msg.get("thinking", "")
                    token = msg.get("content", "")

                # Debug first chunk
                if not first_chunk_logged:
                    logger.info(
                        "STREAM_FIRST_CHUNK",
                        thinking_token=repr(thinking_token[:50]) if thinking_token else "(none)",
                        content_token=repr(token[:50]) if token else "(none)",
                    )
                    first_chunk_logged = True

                # GLM outputs thinking tokens first (in 'thinking' field), then content (in 'content' field)
                # Yield both with appropriate flags
                if thinking_token:
                    thinking_buffer += thinking_token
                    if on_thinking:
                        on_thinking(thinking_token)
                    # Yield thinking token for UI display
                    yield ("thinking", thinking_token)
                    if not token:
                        continue  # Still in thinking phase

                if not token:
                    continue  # Skip empty tokens

                full_response += token

                # Обработка thinking mode
                if thinking:
                    if "<think>" in full_response and not in_thinking:
                        in_thinking = True
                        # Извлекаем часть после <think>
                        idx = full_response.find("<think>")
                        thinking_buffer = full_response[idx + 7 :]
                        continue

                    if in_thinking:
                        if "</think>" in full_response:
                            # Конец thinking
                            in_thinking = False
                            idx = full_response.find("</think>")
                            thinking_buffer = full_response[full_response.find("<think>") + 7 : idx]
                            response_buffer = full_response[idx + 8 :]

                            if on_thinking:
                                on_thinking(thinking_buffer)

                            # Теперь стримим ответ
                            if response_buffer:
                                if on_token:
                                    on_token(response_buffer)
                                yield ("content", response_buffer)
                        else:
                            # Всё ещё в thinking - не выводим
                            thinking_buffer += token
                            continue
                    else:
                        # После thinking - выводим
                        if on_token:
                            on_token(token)
                        yield ("content", token)
                else:
                    # Без thinking mode - выводим всё
                    if on_token:
                        on_token(token)
                    yield ("content", token)

        except Exception as e:
            logger.error("stream_generation_failed", error=str(e))
            raise

    def generate_stream_simple(self, prompt: str, system: Optional[str] = None, **kwargs) -> Generator[str, None, None]:
        """
        Простой streaming без обработки thinking.
        Для случаев когда нужен сырой вывод.
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        stream = self.client.chat(
            model=self.model,
            messages=messages,
            stream=True,
            options=self._get_options(kwargs.get("temperature"), kwargs.get("max_tokens")),
        )

        for chunk in stream:
            # Handle both dict and Pydantic model responses
            if hasattr(chunk, "message"):
                message = chunk.message
                token = message.content if hasattr(message, "content") else message.get("content", "")
            else:
                token = chunk.get("message", {}).get("content", "")
            if token:
                yield token

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Chat with conversation history.

        Args:
            messages: List of {"role": "user/assistant/system", "content": "..."}

        Returns:
            Assistant response
        """
        try:
            response = self.client.chat(
                model=self.model,
                messages=messages,
                options=self._get_options(kwargs.get("temperature"), kwargs.get("max_tokens")),
            )
            return response["message"]["content"]
        except Exception as e:
            logger.error("chat_failed", error=str(e))
            raise

    def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        available_functions: Dict[str, Callable],
        max_tool_rounds: int = 3,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Multi-round tool calling via Ollama Tools API.

        Loop:
        1. ollama.chat(messages, tools)
        2. If response has tool_calls → execute each → append role='tool' result
        3. Repeat until model returns text or max_tool_rounds reached

        Args:
            messages: Conversation messages
            tools: Ollama tool definitions (OpenAI-compatible)
            available_functions: Map of function name → callable
            max_tool_rounds: Safety limit for tool call loops

        Returns:
            {content, tool_calls_made, thinking}
        """
        options = self._get_options(
            kwargs.get("temperature"),
            kwargs.get("max_tokens"),
        )
        # Disable thinking mode for tool calling (conflicts with structured output)
        if self._is_qwen_model():
            messages = [
                {**m, "content": m["content"].replace("/think\n", "")} if m.get("role") == "user" else m
                for m in messages
            ]

        tool_calls_made: List[Dict[str, Any]] = []
        working_messages = list(messages)

        for round_num in range(max_tool_rounds):
            try:
                response = self.client.chat(
                    model=self.model,
                    messages=working_messages,
                    tools=tools,
                    options=options,
                    keep_alive="30m",
                )
            except Exception as e:
                logger.error("chat_with_tools_failed", error=str(e), round=round_num)
                raise

            message = response.get("message", {})
            if hasattr(response, "message"):
                message = response.message

            # Extract tool_calls (handle both dict and pydantic)
            msg_tool_calls = []
            if hasattr(message, "tool_calls"):
                msg_tool_calls = message.tool_calls or []
            elif isinstance(message, dict):
                msg_tool_calls = message.get("tool_calls") or []

            if not msg_tool_calls:
                # Model responded with text — done
                content = ""
                if hasattr(message, "content"):
                    content = message.content or ""
                elif isinstance(message, dict):
                    content = message.get("content", "")

                return {
                    "content": content,
                    "tool_calls_made": tool_calls_made,
                    "thinking": "",
                }

            # Execute each tool call
            for tc in msg_tool_calls:
                # Parse tool call (dict or object)
                if hasattr(tc, "function"):
                    fn_name = tc.function.name if hasattr(tc.function, "name") else tc.function.get("name", "")
                    fn_args = (
                        tc.function.arguments if hasattr(tc.function, "arguments") else tc.function.get("arguments", {})
                    )
                else:
                    fn_name = tc.get("function", {}).get("name", "")
                    fn_args = tc.get("function", {}).get("arguments", {})

                logger.info("tool_call", function=fn_name, args=fn_args, round=round_num)

                # Execute
                fn = available_functions.get(fn_name)
                if fn is None:
                    result_str = json.dumps({"error": f"Unknown function: {fn_name}"})
                else:
                    try:
                        if isinstance(fn_args, str):
                            fn_args = json.loads(fn_args)
                        result = fn(**fn_args)
                        result_str = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
                    except Exception as e:
                        logger.warning("tool_execution_failed", function=fn_name, error=str(e))
                        result_str = json.dumps({"error": str(e)})

                tool_calls_made.append(
                    {
                        "function": fn_name,
                        "arguments": fn_args,
                        "result": result_str,
                    }
                )

                # Append assistant's tool_call message and tool result
                # Build the assistant message with the tool call
                assistant_msg = {"role": "assistant", "content": ""}
                if hasattr(message, "tool_calls"):
                    assistant_msg["tool_calls"] = message.tool_calls
                elif isinstance(message, dict) and "tool_calls" in message:
                    assistant_msg["tool_calls"] = message["tool_calls"]

                if assistant_msg not in working_messages:
                    working_messages.append(assistant_msg)

                working_messages.append(
                    {
                        "role": "tool",
                        "content": result_str,
                    }
                )

        # max_tool_rounds exhausted — return last content or empty
        logger.warning("tool_rounds_exhausted", max_rounds=max_tool_rounds)
        return {
            "content": "",
            "tool_calls_made": tool_calls_made,
            "thinking": "",
        }

    def chat_with_thinking(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, str]:
        """
        Chat with conversation history, returning thinking separately.

        Args:
            messages: List of {"role": "user/assistant/system", "content": "..."}

        Returns:
            Dict with 'thinking', 'response', and 'raw' keys
        """
        try:
            result = self.client.chat(
                model=self.model,
                messages=messages,
                options=self._get_options(kwargs.get("temperature"), kwargs.get("max_tokens")),
            )
            raw_content = result["message"]["content"]

            thinking = ""
            response = raw_content

            # Try to extract thinking based on model type
            if self._is_glm_model():
                # GLM format: "Thinking...\n...\n...done thinking.\n[response]"
                if "Thinking..." in raw_content and "...done thinking." in raw_content:
                    thinking, response = self._parse_glm_thinking(raw_content)
            elif self._is_qwen_model():
                # Qwen format: "<think>...</think>[response]"
                if "<think>" in raw_content:
                    thinking, response = self._parse_thinking(raw_content)
            else:
                # Generic: try both formats
                if "<think>" in raw_content:
                    thinking, response = self._parse_thinking(raw_content)
                elif "Thinking..." in raw_content:
                    thinking, response = self._parse_glm_thinking(raw_content)

            # Also check for JSON with reasoning field
            if not thinking and '"reasoning"' in raw_content:
                try:
                    import json

                    parsed = json.loads(raw_content)
                    if isinstance(parsed, dict):
                        thinking = parsed.get("reasoning", "")
                        response = parsed.get("message", raw_content)
                except (json.JSONDecodeError, TypeError):
                    pass

            return {"thinking": thinking, "response": response, "raw": raw_content}

        except Exception as e:
            logger.error("chat_with_thinking_failed", error=str(e))
            raise

    def chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> Generator[str, None, None]:
        """
        Chat with conversation history - streaming version.

        Args:
            messages: List of {"role": "user/assistant/system", "content": "..."}

        Yields:
            Generated tokens
        """
        try:
            stream = self.client.chat(
                model=self.model,
                messages=messages,
                stream=True,
                options=self._get_options(kwargs.get("temperature"), kwargs.get("max_tokens")),
            )

            for chunk in stream:
                # Handle both dict and Pydantic model responses
                if hasattr(chunk, "message"):
                    message = chunk.message
                    token = message.content if hasattr(message, "content") else message.get("content", "")
                else:
                    token = chunk.get("message", {}).get("content", "")
                if token:
                    yield token

        except Exception as e:
            logger.error("chat_stream_failed", error=str(e))
            raise

    def _parse_thinking(self, content: str) -> tuple:
        """
        Parse Qwen3 thinking output.

        Returns:
            (thinking_content, response_content)
        """
        think_match = re.search(r"<think>(.*?)</think>", content, re.DOTALL)
        thinking = think_match.group(1).strip() if think_match else ""
        response = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        return thinking, response

    def _parse_glm_thinking(self, content: str) -> tuple:
        """
        Parse GLM thinking output.

        GLM format: "Thinking...\n[reasoning]\n...done thinking.\n[response]"

        Returns:
            (thinking_content, response_content)
        """
        # Only parse if BOTH markers are present
        start_marker = "Thinking..."
        end_marker = "...done thinking."

        if start_marker in content and end_marker in content:
            # Find the thinking section
            start_idx = content.find(start_marker)
            end_idx = content.find(end_marker)

            if start_idx < end_idx:
                thinking = content[start_idx + len(start_marker) : end_idx].strip()
                response = content[end_idx + len(end_marker) :].strip()
                return thinking, response

        # If markers not found or malformed, return full content
        return "", content

    def check_connection(self) -> bool:
        """Check if Ollama server is reachable."""
        try:
            self.client.list()
            return True
        except Exception:
            return False

    def list_models(self) -> List[str]:
        """List available models."""
        try:
            response = self.client.list()
            # Handle both old dict format and new ListResponse object
            if hasattr(response, "models"):
                return [m.model if hasattr(m, "model") else m.get("name", "") for m in response.models]
            elif isinstance(response, dict):
                return [m["name"] for m in response.get("models", [])]
            return []
        except Exception:
            return []

    def get_model_info(self) -> Dict[str, Any]:
        """Получить информацию о текущей модели."""
        try:
            return self.client.show(self.model)
        except Exception:
            return {}

    def get_hardware_config(self) -> Dict[str, Any]:
        """Получить текущую конфигурацию оборудования."""
        return {
            "model": self.model,
            "host": self.host,
            "gpu_layers": getattr(settings, "GPU_LAYERS", "auto"),
            "context_length": getattr(settings, "CONTEXT_LENGTH", 4096),
            "kv_cache_k_type": getattr(settings, "KV_CACHE_K_TYPE", "f16"),
            "kv_cache_v_type": getattr(settings, "KV_CACHE_V_TYPE", "f16"),
            "temperature": self._temperature,
            "top_p": self._top_p,
            "top_k": self._top_k,
            "min_p": getattr(self, "_min_p", 0.0),
        }

    def estimate_vram_usage(self) -> Dict[str, Any]:
        """Оценить использование VRAM для текущей конфигурации."""
        gpu_layers = getattr(settings, "GPU_LAYERS", 25)
        ctx_length = getattr(settings, "CONTEXT_LENGTH", 4096)

        # Rough estimates based on model size and quantization
        model_lower = self.model.lower()

        # Base model size estimates (in GB)
        if "7b" in model_lower or "flash" in model_lower:
            base_size_gb = 4.0  # Q4 quantized 7B
            total_layers = 32
        elif "9b" in model_lower:
            base_size_gb = 5.5
            total_layers = 36
        elif "14b" in model_lower:
            base_size_gb = 8.0
            total_layers = 40
        else:
            base_size_gb = 4.0
            total_layers = 32

        # GPU VRAM = (gpu_layers / total_layers) * base_size + KV cache
        layer_ratio = min(gpu_layers, total_layers) / total_layers
        model_vram_gb = base_size_gb * layer_ratio

        # KV cache estimate: ~0.5MB per 1K context tokens per layer on GPU
        kv_cache_gb = (ctx_length / 1000) * gpu_layers * 0.0005

        total_vram_gb = model_vram_gb + kv_cache_gb

        return {
            "estimated_vram_gb": round(total_vram_gb, 2),
            "model_vram_gb": round(model_vram_gb, 2),
            "kv_cache_gb": round(kv_cache_gb, 2),
            "gpu_layers": gpu_layers,
            "total_layers": total_layers,
            "context_length": ctx_length,
            "recommendation": self._get_vram_recommendation(total_vram_gb),
        }

    def _get_vram_recommendation(self, vram_gb: float) -> str:
        """Получить рекомендацию по VRAM."""
        if vram_gb <= 4:
            return "Подходит для GTX 1650/1660 (4GB)"
        elif vram_gb <= 6:
            return "Подходит для RTX 2060/3060 (6GB)"
        elif vram_gb <= 8:
            return "Подходит для RTX 2070/2080/3070 (8GB)"
        elif vram_gb <= 12:
            return "Требуется RTX 3080/4070 (12GB)"
        else:
            return "Требуется RTX 3090/4080/4090 (16GB+)"
