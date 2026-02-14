"""
MITS Error Handling Utilities

Centralized error handling for edge cases:
- Empty input validation
- Ollama connection issues
- Malformed responses
- Timeout handling
- Graceful degradation

Based on T057: Add error handling for edge cases across all agents.
"""

from typing import Optional, Dict, Any, Callable, TypeVar, Union
from functools import wraps
from enum import Enum
import time
import structlog

logger = structlog.get_logger()

T = TypeVar('T')


class ErrorCategory(Enum):
    """Categories of errors for handling strategies."""
    INPUT_VALIDATION = "input_validation"
    CONNECTION = "connection"
    TIMEOUT = "timeout"
    MALFORMED_RESPONSE = "malformed_response"
    RESOURCE = "resource"
    INTERNAL = "internal"


class MITSError(Exception):
    """Base exception for MITS system errors."""

    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.INTERNAL,
        recoverable: bool = True,
        user_message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.category = category
        self.recoverable = recoverable
        self.user_message = user_message or self._default_user_message()
        self.details = details or {}
        super().__init__(message)

    def _default_user_message(self) -> str:
        """Generate user-friendly message based on category."""
        messages = {
            ErrorCategory.INPUT_VALIDATION: "Please check your input and try again.",
            ErrorCategory.CONNECTION: "Connection issue. Please check if Ollama is running.",
            ErrorCategory.TIMEOUT: "Request timed out. Please try again.",
            ErrorCategory.MALFORMED_RESPONSE: "Received unexpected response. Retrying...",
            ErrorCategory.RESOURCE: "System is busy. Please wait a moment.",
            ErrorCategory.INTERNAL: "An error occurred. Please try again."
        }
        return messages.get(self.category, messages[ErrorCategory.INTERNAL])


class InputValidationError(MITSError):
    """Error for invalid input."""

    def __init__(self, message: str, field: str = None, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.INPUT_VALIDATION,
            recoverable=True,
            **kwargs
        )
        self.field = field


class ConnectionError(MITSError):
    """Error for connection issues."""

    def __init__(self, message: str, service: str = "ollama", **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.CONNECTION,
            recoverable=True,
            user_message=f"Cannot connect to {service}. Is it running?",
            **kwargs
        )
        self.service = service


class TimeoutError(MITSError):
    """Error for timeout situations."""

    def __init__(self, message: str, timeout_ms: float = None, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.TIMEOUT,
            recoverable=True,
            **kwargs
        )
        self.timeout_ms = timeout_ms


class MalformedResponseError(MITSError):
    """Error for malformed LLM responses."""

    def __init__(self, message: str, raw_response: str = None, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.MALFORMED_RESPONSE,
            recoverable=True,
            **kwargs
        )
        self.raw_response = raw_response


# ============== Validation Functions ==============

def validate_input(
    text: str,
    min_length: int = 1,
    max_length: int = 10000,
    allow_empty: bool = False
) -> str:
    """
    Validate user input text.

    Args:
        text: Input text to validate
        min_length: Minimum allowed length
        max_length: Maximum allowed length
        allow_empty: Whether empty input is allowed

    Returns:
        Cleaned text

    Raises:
        InputValidationError: If validation fails
    """
    if text is None:
        if allow_empty:
            return ""
        raise InputValidationError(
            "Input cannot be None",
            field="input",
            user_message="Please enter some text."
        )

    # Clean whitespace
    cleaned = text.strip()

    if not cleaned and not allow_empty:
        raise InputValidationError(
            "Input cannot be empty",
            field="input",
            user_message="Please enter some text."
        )

    if len(cleaned) < min_length:
        raise InputValidationError(
            f"Input too short (min {min_length} characters)",
            field="input",
            user_message=f"Please enter at least {min_length} characters."
        )

    if len(cleaned) > max_length:
        raise InputValidationError(
            f"Input too long (max {max_length} characters)",
            field="input",
            user_message=f"Input is too long. Maximum {max_length} characters."
        )

    return cleaned


def validate_session_id(session_id: str) -> str:
    """Validate session ID format."""
    if not session_id or not isinstance(session_id, str):
        raise InputValidationError(
            "Invalid session ID",
            field="session_id",
            user_message="Session error. Please refresh the page."
        )
    return session_id.strip()


def validate_student_id(student_id: str) -> str:
    """Validate student ID format."""
    if not student_id or not isinstance(student_id, str):
        raise InputValidationError(
            "Invalid student ID",
            field="student_id",
            user_message="Authentication error. Please log in again."
        )
    return student_id.strip()


# ============== Connection Checking ==============

def check_ollama_connection(host: str = None) -> bool:
    """
    Check if Ollama is reachable.

    Args:
        host: Ollama host URL

    Returns:
        True if connected, False otherwise
    """
    try:
        import ollama
        from src.config import settings

        client = ollama.Client(host=host or settings.OLLAMA_HOST)
        client.list()
        return True
    except Exception as e:
        logger.warning("ollama_connection_check_failed", error=str(e))
        return False


def require_ollama(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator to require Ollama connection.

    Raises ConnectionError if Ollama is not available.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not check_ollama_connection():
            raise ConnectionError(
                "Ollama server is not reachable",
                service="ollama",
                user_message="Ollama is not running. Please start it with: ollama serve"
            )
        return func(*args, **kwargs)
    return wrapper


# ============== Retry Logic ==============

def with_retry(
    max_retries: int = 3,
    delay_ms: float = 1000,
    backoff: float = 2.0,
    recoverable_only: bool = True
) -> Callable:
    """
    Decorator for retry logic with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        delay_ms: Initial delay between retries in milliseconds
        backoff: Backoff multiplier for each retry
        recoverable_only: Only retry recoverable errors
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_error = None
            delay = delay_ms / 1000.0

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except MITSError as e:
                    last_error = e
                    if not e.recoverable and recoverable_only:
                        raise

                    if attempt < max_retries:
                        logger.warning(
                            "retry_attempt",
                            function=func.__name__,
                            attempt=attempt + 1,
                            max_retries=max_retries,
                            error=str(e)
                        )
                        time.sleep(delay)
                        delay *= backoff
                except Exception as e:
                    last_error = e
                    if attempt < max_retries:
                        logger.warning(
                            "retry_attempt",
                            function=func.__name__,
                            attempt=attempt + 1,
                            error=str(e)
                        )
                        time.sleep(delay)
                        delay *= backoff

            raise last_error
        return wrapper
    return decorator


# ============== Safe Execution ==============

def safe_execute(
    func: Callable[..., T],
    *args,
    default: T = None,
    error_handler: Callable[[Exception], T] = None,
    **kwargs
) -> T:
    """
    Safely execute a function with error handling.

    Args:
        func: Function to execute
        *args: Arguments to pass
        default: Default value on error
        error_handler: Custom error handler
        **kwargs: Keyword arguments

    Returns:
        Function result or default value
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(
            "safe_execute_error",
            function=func.__name__,
            error=str(e)
        )
        if error_handler:
            return error_handler(e)
        return default


def safe_json_parse(text: str, default: Any = None) -> Any:
    """
    Safely parse JSON with error handling.

    Args:
        text: JSON string to parse
        default: Default value on parse error

    Returns:
        Parsed JSON or default
    """
    import json
    import re

    if not text or not isinstance(text, str):
        return default

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to extract JSON from markdown code blocks
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if json_match:
        try:
            return json.loads(json_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try to find JSON object
    brace_start = text.find('{')
    brace_end = text.rfind('}')
    if brace_start != -1 and brace_end > brace_start:
        try:
            return json.loads(text[brace_start:brace_end + 1])
        except json.JSONDecodeError:
            pass

    logger.warning("json_parse_failed", text_preview=text[:100])
    return default


# ============== Fallback Responses ==============

class FallbackResponses:
    """Default fallback responses for graceful degradation."""

    TUTOR_UNAVAILABLE = (
        "I apologize, but I'm having trouble processing your request. "
        "Could you please try rephrasing your question?"
    )

    TUTOR_UNAVAILABLE_RU = (
        "Извините, возникла проблема с обработкой вашего запроса. "
        "Пожалуйста, попробуйте переформулировать вопрос."
    )

    CONNECTION_ERROR = (
        "Connection error. Please check if Ollama is running and try again."
    )

    CONNECTION_ERROR_RU = (
        "Ошибка подключения. Проверьте, запущен ли Ollama, и попробуйте снова."
    )

    EMPTY_INPUT = "Please enter your question or response."
    EMPTY_INPUT_RU = "Пожалуйста, введите ваш вопрос или ответ."

    @classmethod
    def get_fallback(
        cls,
        error_type: str = "general",
        language: str = "ru"
    ) -> str:
        """Get appropriate fallback response."""
        responses = {
            "tutor": (cls.TUTOR_UNAVAILABLE_RU if language == "ru"
                     else cls.TUTOR_UNAVAILABLE),
            "connection": (cls.CONNECTION_ERROR_RU if language == "ru"
                          else cls.CONNECTION_ERROR),
            "empty_input": (cls.EMPTY_INPUT_RU if language == "ru"
                           else cls.EMPTY_INPUT),
        }
        return responses.get(error_type, responses["tutor"])


# ============== Error Wrapper for UI ==============

def handle_ui_error(
    func: Callable,
    error_message: str = None,
    language: str = "ru"
) -> Callable:
    """
    Decorator to handle errors in UI callbacks.

    Catches exceptions and returns user-friendly error messages.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except InputValidationError as e:
            return f"Input error: {e.user_message}"
        except ConnectionError as e:
            return FallbackResponses.get_fallback("connection", language)
        except MITSError as e:
            return e.user_message
        except Exception as e:
            logger.error(
                "ui_error",
                function=func.__name__,
                error=str(e)
            )
            return error_message or FallbackResponses.get_fallback("tutor", language)
    return wrapper


# Export all
__all__ = [
    # Exceptions
    "MITSError",
    "InputValidationError",
    "ConnectionError",
    "TimeoutError",
    "MalformedResponseError",
    "ErrorCategory",
    # Validation
    "validate_input",
    "validate_session_id",
    "validate_student_id",
    # Connection
    "check_ollama_connection",
    "require_ollama",
    # Utilities
    "with_retry",
    "safe_execute",
    "safe_json_parse",
    # Fallbacks
    "FallbackResponses",
    "handle_ui_error",
]
