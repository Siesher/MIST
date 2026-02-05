"""
MITS Base Agent

Abstract base class for all ITS agents.

Based on:
- GenMentor multi-agent architecture (WWW 2025)
- Agent interface contracts from spec
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List
from enum import Enum
from datetime import datetime
import time
import structlog

# Conditional import for LLMClient
try:
    from src.models.llm_client import LLMClient
except ImportError:
    LLMClient = None


class AgentStatus(Enum):
    """Agent health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    INITIALIZING = "initializing"


@dataclass
class AgentRequest:
    """Standard request to any agent (per contracts/agent-interfaces.md)."""
    session_id: str
    student_id: str
    context: Dict[str, Any]
    input_data: Any
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AgentResponse:
    """Standard response from any agent (per contracts/agent-interfaces.md)."""
    success: bool
    agent_name: str
    output: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    execution_time_ms: float = 0.0


@dataclass
class HealthCheckResult:
    """Result of agent health check."""
    status: AgentStatus
    agent_name: str
    latency_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    last_error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def is_healthy(self) -> bool:
        return self.status == AgentStatus.HEALTHY

    def is_operational(self) -> bool:
        return self.status in [AgentStatus.HEALTHY, AgentStatus.DEGRADED]


class AgentError(Exception):
    """Base exception for agent errors (per contracts/agent-interfaces.md)."""

    def __init__(
        self,
        agent_name: str,
        message: str,
        recoverable: bool = True,
        original_error: Optional[Exception] = None
    ):
        self.agent_name = agent_name
        self.message = message
        self.recoverable = recoverable
        self.original_error = original_error
        super().__init__(f"[{agent_name}] {message}")


class BaseAgent(ABC):
    """
    Base class for all ITS agents.

    All agents share:
    - LLM client for generation
    - System prompt defining behavior
    - Logging
    - Common interface (process method)
    - Health check capability
    - Performance metrics

    Based on GenMentor architecture (WWW 2025).
    """

    def __init__(
        self,
        name: str,
        llm_client: Optional['LLMClient'] = None,
        system_prompt: str = ""
    ):
        self._name = name
        self.llm = llm_client
        self.system_prompt = system_prompt
        self.logger = structlog.get_logger().bind(agent=name)

        # Health tracking
        self._status = AgentStatus.INITIALIZING
        self._last_error: Optional[str] = None
        self._call_count = 0
        self._error_count = 0
        self._total_latency_ms = 0.0
        self._last_health_check: Optional[HealthCheckResult] = None

        # Set to healthy after initialization
        self._status = AgentStatus.HEALTHY

        self.logger.info("agent_initialized")
    
    @property
    def name(self) -> str:
        """Agent identifier."""
        return self._name

    @property
    def status(self) -> AgentStatus:
        """Current agent status."""
        return self._status

    @abstractmethod
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process input and return output.

        Args:
            input_data: Dictionary with agent-specific inputs

        Returns:
            Dictionary with agent outputs
        """
        pass

    def process_request(self, request: AgentRequest) -> AgentResponse:
        """
        Process a standardized request and return response.

        This is the preferred interface for orchestrator communication.

        Args:
            request: AgentRequest with session context and input

        Returns:
            AgentResponse with result and metadata
        """
        start_time = time.time()
        self._call_count += 1

        try:
            # Call the agent's process method
            result = self.process(request.input_data)

            execution_time = (time.time() - start_time) * 1000
            self._total_latency_ms += execution_time

            return AgentResponse(
                success=True,
                agent_name=self._name,
                output=result,
                metadata={
                    "session_id": request.session_id,
                    "student_id": request.student_id,
                    "call_count": self._call_count
                },
                execution_time_ms=execution_time
            )

        except Exception as e:
            self._error_count += 1
            self._last_error = str(e)
            self._update_status()

            execution_time = (time.time() - start_time) * 1000
            self._total_latency_ms += execution_time

            self.logger.error(
                "agent_process_error",
                error=str(e),
                request_session=request.session_id
            )

            return AgentResponse(
                success=False,
                agent_name=self._name,
                output=None,
                error=str(e),
                execution_time_ms=execution_time
            )

    def health_check(self, timeout_ms: float = 5000) -> HealthCheckResult:
        """
        Check agent health status.

        Performs a lightweight check to verify agent is operational.

        Args:
            timeout_ms: Maximum time for health check

        Returns:
            HealthCheckResult with status and metrics
        """
        start_time = time.time()

        try:
            # Basic health check - verify internal state
            is_healthy = self._perform_health_check()

            latency = (time.time() - start_time) * 1000

            if latency > timeout_ms:
                status = AgentStatus.DEGRADED
            elif is_healthy:
                status = AgentStatus.HEALTHY
            else:
                status = AgentStatus.UNHEALTHY

            result = HealthCheckResult(
                status=status,
                agent_name=self._name,
                latency_ms=latency,
                details={
                    "call_count": self._call_count,
                    "error_count": self._error_count,
                    "error_rate": self._error_count / max(self._call_count, 1),
                    "avg_latency_ms": self._total_latency_ms / max(self._call_count, 1)
                },
                last_error=self._last_error
            )

            self._last_health_check = result
            return result

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            self._last_error = str(e)

            result = HealthCheckResult(
                status=AgentStatus.UNHEALTHY,
                agent_name=self._name,
                latency_ms=latency,
                last_error=str(e)
            )

            self._last_health_check = result
            return result

    def _perform_health_check(self) -> bool:
        """
        Perform agent-specific health check.

        Override in subclasses for custom health verification.

        Returns:
            True if healthy, False otherwise
        """
        # Base implementation: check error rate
        if self._call_count == 0:
            return True

        error_rate = self._error_count / self._call_count
        return error_rate < 0.5  # Unhealthy if >50% errors

    def _update_status(self):
        """Update agent status based on metrics."""
        if self._call_count == 0:
            return

        error_rate = self._error_count / self._call_count

        if error_rate >= 0.5:
            self._status = AgentStatus.UNHEALTHY
        elif error_rate >= 0.2:
            self._status = AgentStatus.DEGRADED
        else:
            self._status = AgentStatus.HEALTHY

    def reset_metrics(self):
        """Reset performance metrics."""
        self._call_count = 0
        self._error_count = 0
        self._total_latency_ms = 0.0
        self._last_error = None
        self._status = AgentStatus.HEALTHY

    def get_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics."""
        return {
            "agent_name": self._name,
            "status": self._status.value,
            "call_count": self._call_count,
            "error_count": self._error_count,
            "error_rate": self._error_count / max(self._call_count, 1),
            "avg_latency_ms": self._total_latency_ms / max(self._call_count, 1),
            "total_latency_ms": self._total_latency_ms,
            "last_error": self._last_error
        }

    def _call_llm(
        self,
        prompt: str,
        json_mode: bool = False,
        thinking: bool = True,
        **kwargs
    ) -> str:
        """
        Helper to call LLM with agent's system prompt.

        Args:
            prompt: User prompt
            json_mode: Request JSON output
            thinking: Use thinking mode
            **kwargs: Additional LLM parameters

        Returns:
            LLM response string

        Raises:
            AgentError: If LLM call fails
        """
        if not self.llm:
            raise AgentError(
                self._name,
                "LLM client not configured",
                recoverable=False
            )

        try:
            return self.llm.generate(
                prompt=prompt,
                system=self.system_prompt,
                json_mode=json_mode,
                thinking=thinking,
                **kwargs
            )
        except Exception as e:
            raise AgentError(
                self._name,
                f"LLM call failed: {str(e)}",
                recoverable=True,
                original_error=e
            )

    def _log_action(self, action: str, details: Optional[Dict] = None):
        """Log an agent action."""
        self.logger.info(
            "agent_action",
            action=action,
            details=details or {}
        )

    def _log_error(self, error: str, details: Optional[Dict] = None):
        """Log an agent error."""
        self.logger.error(
            "agent_error",
            error=error,
            details=details or {}
        )


# Export for contracts compliance
__all__ = [
    "BaseAgent",
    "AgentRequest",
    "AgentResponse",
    "AgentError",
    "AgentStatus",
    "HealthCheckResult"
]
