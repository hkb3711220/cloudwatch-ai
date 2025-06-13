"""MCP-related Exception Classes

Provides exception classes for Model Context Protocol (MCP) specific errors
including server, client, protocol, and security related exceptions.

Author: CloudWatch Logs AI Agent Team
License: MIT
"""

from typing import Optional, Dict, Any
from .base import AgentError, ErrorContext


class MCPError(AgentError):
    """Base exception class for MCP-related errors"""

    def __init__(
        self,
        message: str,
        mcp_method: Optional[str] = None,
        mcp_request_id: Optional[str] = None,
        **kwargs
    ):
        """Initialize MCP error

        Args:
            message: Error message
            mcp_method: MCP method that caused the error
            mcp_request_id: MCP request ID for tracking
            **kwargs: Additional AgentError arguments
        """
        super().__init__(message, **kwargs)
        self.mcp_method = mcp_method
        self.mcp_request_id = mcp_request_id

    def _get_default_japanese_message(self) -> str:
        return "MCPプロトコルでエラーが発生しました"

    def _get_default_error_code(self) -> str:
        return "MCP_ERROR"

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary with MCP-specific fields"""
        result = super().to_dict()
        result.update(
            {"mcp_method": self.mcp_method, "mcp_request_id": self.mcp_request_id}
        )
        return result


class MCPServerError(MCPError):
    """Exception class for MCP server errors"""

    def __init__(
        self,
        message: str,
        server_component: Optional[str] = None,
        port: Optional[int] = None,
        **kwargs
    ):
        """Initialize MCP server error

        Args:
            message: Error message
            server_component: Server component that failed (e.g., 'request_handler', 'security')
            port: Server port number
            **kwargs: Additional MCPError arguments
        """
        super().__init__(message, **kwargs)
        self.server_component = server_component
        self.port = port

    def _get_default_japanese_message(self) -> str:
        return "MCPサーバーでエラーが発生しました"

    def _get_default_error_code(self) -> str:
        return "MCP_SERVER_ERROR"

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary with server-specific fields"""
        result = super().to_dict()
        result.update({"server_component": self.server_component, "port": self.port})
        return result


class MCPClientError(MCPError):
    """Exception class for MCP client errors"""

    def __init__(
        self,
        message: str,
        client_type: Optional[str] = None,
        server_url: Optional[str] = None,
        **kwargs
    ):
        """Initialize MCP client error

        Args:
            message: Error message
            client_type: Type of client (e.g., 'http', 'stdio')
            server_url: Server URL that the client was trying to connect to
            **kwargs: Additional MCPError arguments
        """
        super().__init__(message, **kwargs)
        self.client_type = client_type
        self.server_url = server_url

    def _get_default_japanese_message(self) -> str:
        return "MCPクライアントでエラーが発生しました"

    def _get_default_error_code(self) -> str:
        return "MCP_CLIENT_ERROR"

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary with client-specific fields"""
        result = super().to_dict()
        result.update({"client_type": self.client_type, "server_url": self.server_url})
        return result


class MCPConnectionError(MCPError):
    """Exception class for MCP connection errors"""

    def __init__(
        self,
        message: str,
        connection_type: Optional[str] = None,
        endpoint: Optional[str] = None,
        retry_count: Optional[int] = None,
        **kwargs
    ):
        """Initialize MCP connection error

        Args:
            message: Error message
            connection_type: Type of connection (e.g., 'http', 'websocket', 'stdio')
            endpoint: Connection endpoint
            retry_count: Number of retries attempted
            **kwargs: Additional MCPError arguments
        """
        super().__init__(message, **kwargs)
        self.connection_type = connection_type
        self.endpoint = endpoint
        self.retry_count = retry_count

    def _get_default_japanese_message(self) -> str:
        return "MCP接続でエラーが発生しました"

    def _get_default_error_code(self) -> str:
        return "MCP_CONNECTION_ERROR"

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary with connection-specific fields"""
        result = super().to_dict()
        result.update(
            {
                "connection_type": self.connection_type,
                "endpoint": self.endpoint,
                "retry_count": self.retry_count,
            }
        )
        return result


class MCPProtocolError(MCPError):
    """Exception class for MCP protocol violations and invalid requests"""

    def __init__(
        self,
        message: str,
        protocol_version: Optional[str] = None,
        invalid_field: Optional[str] = None,
        **kwargs
    ):
        """Initialize MCP protocol error

        Args:
            message: Error message
            protocol_version: MCP protocol version that was violated
            invalid_field: Field that contains invalid data
            **kwargs: Additional MCPError arguments
        """
        super().__init__(message, **kwargs)
        self.protocol_version = protocol_version
        self.invalid_field = invalid_field

    def _get_default_japanese_message(self) -> str:
        return "MCPプロトコルエラーが発生しました"

    def _get_default_error_code(self) -> str:
        return "MCP_PROTOCOL_ERROR"

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary with protocol-specific fields"""
        result = super().to_dict()
        result.update(
            {
                "protocol_version": self.protocol_version,
                "invalid_field": self.invalid_field,
            }
        )
        return result
