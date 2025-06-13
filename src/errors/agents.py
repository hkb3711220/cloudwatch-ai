"""Agent-related Exception Classes

Provides exception classes for agent system specific errors
including team management, model integration, and orchestration.

Author: CloudWatch Logs AI Agent Team
License: MIT
"""

from typing import Optional, Dict, Any, List
from .base import AgentError, ErrorContext


class AgentTeamError(AgentError):
    """Exception class for agent team management errors"""

    def __init__(
        self,
        message: str,
        team_id: Optional[str] = None,
        agent_count: Optional[int] = None,
        failed_agents: Optional[List[str]] = None,
        **kwargs
    ):
        """Initialize agent team error

        Args:
            message: Error message
            team_id: Team identifier
            agent_count: Number of agents in the team
            failed_agents: List of agent names that failed
            **kwargs: Additional AgentError arguments
        """
        super().__init__(message, **kwargs)
        self.team_id = team_id
        self.agent_count = agent_count
        self.failed_agents = failed_agents or []

    def _get_default_japanese_message(self) -> str:
        return "エージェントチームでエラーが発生しました"

    def _get_default_error_code(self) -> str:
        return "AGENT_TEAM_ERROR"

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary with team-specific fields"""
        result = super().to_dict()
        result.update(
            {
                "team_id": self.team_id,
                "agent_count": self.agent_count,
                "failed_agents": self.failed_agents,
            }
        )
        return result


class AgentModelError(AgentError):
    """Exception class for agent model integration errors"""

    def __init__(
        self,
        message: str,
        model_name: Optional[str] = None,
        model_provider: Optional[str] = None,
        api_error: Optional[str] = None,
        **kwargs
    ):
        """Initialize agent model error

        Args:
            message: Error message
            model_name: Name of the model that failed
            model_provider: Model provider (e.g., 'openai', 'anthropic')
            api_error: API error message from the provider
            **kwargs: Additional AgentError arguments
        """
        super().__init__(message, **kwargs)
        self.model_name = model_name
        self.model_provider = model_provider
        self.api_error = api_error

    def _get_default_japanese_message(self) -> str:
        return "エージェントモデルでエラーが発生しました"

    def _get_default_error_code(self) -> str:
        return "AGENT_MODEL_ERROR"

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary with model-specific fields"""
        result = super().to_dict()
        result.update(
            {
                "model_name": self.model_name,
                "model_provider": self.model_provider,
                "api_error": self.api_error,
            }
        )
        return result


class AgentOrchestratorError(AgentError):
    """Exception class for agent orchestrator errors"""

    def __init__(
        self,
        message: str,
        orchestrator_type: Optional[str] = None,
        current_step: Optional[str] = None,
        workflow_state: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        """Initialize agent orchestrator error

        Args:
            message: Error message
            orchestrator_type: Type of orchestrator (e.g., 'sequential', 'parallel')
            current_step: Current workflow step where error occurred
            workflow_state: Current state of the workflow
            **kwargs: Additional AgentError arguments
        """
        super().__init__(message, **kwargs)
        self.orchestrator_type = orchestrator_type
        self.current_step = current_step
        self.workflow_state = workflow_state or {}

    def _get_default_japanese_message(self) -> str:
        return "エージェントオーケストレーターでエラーが発生しました"

    def _get_default_error_code(self) -> str:
        return "AGENT_ORCHESTRATOR_ERROR"

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary with orchestrator-specific fields"""
        result = super().to_dict()
        result.update(
            {
                "orchestrator_type": self.orchestrator_type,
                "current_step": self.current_step,
                "workflow_state": self.workflow_state,
            }
        )
        return result


class AgentCommunicationError(AgentError):
    """Exception class for agent communication errors"""

    def __init__(
        self,
        message: str,
        source_agent: Optional[str] = None,
        target_agent: Optional[str] = None,
        communication_type: Optional[str] = None,
        message_content: Optional[str] = None,
        **kwargs
    ):
        """Initialize agent communication error

        Args:
            message: Error message
            source_agent: Agent that sent the message
            target_agent: Agent that was supposed to receive the message
            communication_type: Type of communication (e.g., 'direct', 'broadcast')
            message_content: Content of the message that failed
            **kwargs: Additional AgentError arguments
        """
        super().__init__(message, **kwargs)
        self.source_agent = source_agent
        self.target_agent = target_agent
        self.communication_type = communication_type
        self.message_content = message_content

    def _get_default_japanese_message(self) -> str:
        return "エージェント間通信でエラーが発生しました"

    def _get_default_error_code(self) -> str:
        return "AGENT_COMMUNICATION_ERROR"

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary with communication-specific fields"""
        result = super().to_dict()
        result.update(
            {
                "source_agent": self.source_agent,
                "target_agent": self.target_agent,
                "communication_type": self.communication_type,
                "message_content": self.message_content,
            }
        )
        return result
