"""
MITS Base Agent

Abstract base class for all ITS agents.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import structlog

from src.models.llm_client import LLMClient


class BaseAgent(ABC):
    """
    Base class for all ITS agents.
    
    All agents share:
    - LLM client for generation
    - System prompt defining behavior
    - Logging
    - Common interface (process method)
    """
    
    def __init__(
        self,
        name: str,
        llm_client: LLMClient,
        system_prompt: str
    ):
        self.name = name
        self.llm = llm_client
        self.system_prompt = system_prompt
        self.logger = structlog.get_logger().bind(agent=name)
        
        self.logger.info("agent_initialized")
    
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
        """
        return self.llm.generate(
            prompt=prompt,
            system=self.system_prompt,
            json_mode=json_mode,
            thinking=thinking,
            **kwargs
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
