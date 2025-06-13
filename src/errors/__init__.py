"""CloudWatch Logs AI Agent - Custom Exception Classes

This module provides a comprehensive hierarchy of custom exception classes
for the CloudWatch Logs AI Agent MCP Server.

Author: CloudWatch Logs AI Agent Team
License: MIT
"""

from .base import (
    AgentError,
    AgentConfigurationError,
    AgentValidationError,
    AgentTimeoutError,
    AgentResourceError,
)

from .aws import (
    AWSError,
    CloudWatchError,
    CloudWatchLogsError,
    CredentialsError,
    RegionError,
    ResourceNotFoundError,
)

from .mcp import (
    MCPError,
    MCPServerError,
    MCPClientError,
    MCPConnectionError,
    MCPProtocolError,
    # Security-related errors removed as per task 23.8
)

from .tools import (
    ToolError,
    ToolExecutionError,
    ToolValidationError,
    ToolTimeoutError,
    ToolDependencyError,
)

from .agents import (
    AgentTeamError,
    AgentModelError,
    AgentOrchestratorError,
    AgentCommunicationError,
)

# Cache-related imports removed

__all__ = [
    # Base exceptions
    "AgentError",
    "AgentConfigurationError",
    "AgentValidationError",
    "AgentTimeoutError",
    "AgentResourceError",
    # AWS exceptions
    "AWSError",
    "CloudWatchError",
    "CloudWatchLogsError",
    "CredentialsError",
    "RegionError",
    "ResourceNotFoundError",
    # MCP exceptions
    "MCPError",
    "MCPServerError",
    "MCPClientError",
    "MCPConnectionError",
    "MCPProtocolError",
    # Tool exceptions
    "ToolError",
    "ToolExecutionError",
    "ToolValidationError",
    "ToolTimeoutError",
    "ToolDependencyError",
    # Agent exceptions
    "AgentTeamError",
    "AgentModelError",
    "AgentOrchestratorError",
    "AgentCommunicationError",
    # Cache exceptions removed
]
