"""Tool-related Exception Classes

Provides exception classes for MCP tool execution specific errors
including validation, timeout, and dependency related exceptions.

Author: CloudWatch Logs AI Agent Team
License: MIT
"""

from typing import Optional, Dict, Any, List
from .base import AgentError, ErrorContext


class ToolError(AgentError):
    """Base exception class for tool-related errors"""

    def __init__(
        self,
        message: str,
        tool_name: Optional[str] = None,
        tool_version: Optional[str] = None,
        **kwargs
    ):
        """Initialize tool error

        Args:
            message: Error message
            tool_name: Name of the tool that caused the error
            tool_version: Version of the tool
            **kwargs: Additional AgentError arguments
        """
        super().__init__(message, **kwargs)
        self.tool_name = tool_name
        self.tool_version = tool_version

    def _get_default_japanese_message(self) -> str:
        return "ツール実行中にエラーが発生しました"

    def _get_default_error_code(self) -> str:
        return "TOOL_ERROR"

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary with tool-specific fields"""
        result = super().to_dict()
        result.update({"tool_name": self.tool_name, "tool_version": self.tool_version})
        return result


class ToolExecutionError(ToolError):
    """Exception class for tool execution errors"""

    def __init__(
        self,
        message: str,
        execution_stage: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        output: Optional[str] = None,
        **kwargs
    ):
        """Initialize tool execution error

        Args:
            message: Error message
            execution_stage: Stage where execution failed (e.g., 'initialization', 'processing', 'cleanup')
            parameters: Parameters passed to the tool
            output: Partial output from the tool before failure
            **kwargs: Additional ToolError arguments
        """
        super().__init__(message, **kwargs)
        self.execution_stage = execution_stage
        self.parameters = parameters or {}
        self.output = output

    def _get_default_japanese_message(self) -> str:
        if self.tool_name == "investigate":
            return "調査ツールの実行中にエラーが発生しました"
        elif self.tool_name == "list_log_groups":
            return "ログ グループ一覧の取得中にエラーが発生しました"
        elif self.tool_name == "analyze_patterns":
            return "パターン分析中にエラーが発生しました"
        else:
            return "ツールの実行中にエラーが発生しました"

    def _get_default_error_code(self) -> str:
        return "TOOL_EXECUTION_ERROR"

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary with execution-specific fields"""
        result = super().to_dict()
        result.update(
            {
                "execution_stage": self.execution_stage,
                "parameters": self.parameters,
                "output": self.output,
            }
        )
        return result


class ToolValidationError(ToolError):
    """Exception class for tool parameter validation errors"""

    def __init__(
        self,
        message: str,
        invalid_parameters: Optional[List[str]] = None,
        validation_details: Optional[Dict[str, str]] = None,
        **kwargs
    ):
        """Initialize tool validation error

        Args:
            message: Error message
            invalid_parameters: List of parameter names that failed validation
            validation_details: Detailed validation error messages per parameter
            **kwargs: Additional ToolError arguments
        """
        super().__init__(message, **kwargs)
        self.invalid_parameters = invalid_parameters or []
        self.validation_details = validation_details or {}

    def _get_default_japanese_message(self) -> str:
        return "ツールパラメータの検証エラーが発生しました"

    def _get_default_error_code(self) -> str:
        return "TOOL_VALIDATION_ERROR"

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary with validation-specific fields"""
        result = super().to_dict()
        result.update(
            {
                "invalid_parameters": self.invalid_parameters,
                "validation_details": self.validation_details,
            }
        )
        return result


class ToolTimeoutError(ToolError):
    """Exception class for tool timeout errors"""

    def __init__(
        self,
        message: str,
        timeout_seconds: Optional[float] = None,
        elapsed_seconds: Optional[float] = None,
        **kwargs
    ):
        """Initialize tool timeout error

        Args:
            message: Error message
            timeout_seconds: Configured timeout value
            elapsed_seconds: Actual time elapsed before timeout
            **kwargs: Additional ToolError arguments
        """
        super().__init__(message, **kwargs)
        self.timeout_seconds = timeout_seconds
        self.elapsed_seconds = elapsed_seconds

    def _get_default_japanese_message(self) -> str:
        return "ツール実行がタイムアウトしました"

    def _get_default_error_code(self) -> str:
        return "TOOL_TIMEOUT_ERROR"

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary with timeout-specific fields"""
        result = super().to_dict()
        result.update(
            {
                "timeout_seconds": self.timeout_seconds,
                "elapsed_seconds": self.elapsed_seconds,
            }
        )
        return result


class ToolDependencyError(ToolError):
    """Exception class for tool dependency errors"""

    def __init__(
        self,
        message: str,
        missing_dependencies: Optional[List[str]] = None,
        dependency_type: Optional[str] = None,
        **kwargs
    ):
        """Initialize tool dependency error

        Args:
            message: Error message
            missing_dependencies: List of missing dependency names
            dependency_type: Type of dependency (e.g., 'aws_service', 'python_package', 'system_tool')
            **kwargs: Additional ToolError arguments
        """
        super().__init__(message, **kwargs)
        self.missing_dependencies = missing_dependencies or []
        self.dependency_type = dependency_type

    def _get_default_japanese_message(self) -> str:
        if self.dependency_type == "aws_service":
            return "必要なAWSサービスへのアクセスができません"
        elif self.dependency_type == "python_package":
            return "必要なPythonパッケージが見つかりません"
        elif self.dependency_type == "system_tool":
            return "必要なシステムツールが見つかりません"
        else:
            return "ツールの依存関係エラーが発生しました"

    def _get_default_error_code(self) -> str:
        return "TOOL_DEPENDENCY_ERROR"

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary with dependency-specific fields"""
        result = super().to_dict()
        result.update(
            {
                "missing_dependencies": self.missing_dependencies,
                "dependency_type": self.dependency_type,
            }
        )
        return result
