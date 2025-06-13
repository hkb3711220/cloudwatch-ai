"""Base Exception Classes

Provides base exception classes for the CloudWatch Logs AI Agent
with support for Japanese error messages and contextual information.

Author: CloudWatch Logs AI Agent Team
License: MIT
"""

import traceback
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field


@dataclass
class ErrorContext:
    """Error context information for debugging and monitoring"""

    timestamp: datetime = field(default_factory=lambda: datetime.utcnow())
    component: Optional[str] = None
    operation: Optional[str] = None
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    additional_data: Dict[str, Any] = field(default_factory=dict)
    stack_trace: Optional[str] = None


class AgentError(Exception):
    """Base exception class for CloudWatch Logs AI Agent

    This is the root exception class for all custom exceptions in the agent.
    Provides support for:
    - Japanese error messages
    - Error context information
    - Error categorization
    - Debug information
    """

    def __init__(
        self,
        message: str,
        japanese_message: Optional[str] = None,
        error_code: Optional[str] = None,
        context: Optional[ErrorContext] = None,
        cause: Optional[Exception] = None,
        recoverable: bool = False,
    ):
        """Initialize agent error

        Args:
            message: English error message
            japanese_message: Japanese error message for user display
            error_code: Unique error code for categorization
            context: Error context information
            cause: Original exception that caused this error
            recoverable: Whether this error is recoverable
        """
        super().__init__(message)
        self.message = message
        self.japanese_message = japanese_message or self._get_default_japanese_message()
        self.error_code = error_code or self._get_default_error_code()
        self.context = context or ErrorContext()
        self.cause = cause
        self.recoverable = recoverable

        # Capture stack trace if not already provided
        if not self.context.stack_trace:
            self.context.stack_trace = traceback.format_exc()

    def _get_default_japanese_message(self) -> str:
        """Get default Japanese message for this error type"""
        return "予期しないエラーが発生しました"

    def _get_default_error_code(self) -> str:
        """Get default error code for this error type"""
        return "AGENT_ERROR"

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for serialization"""
        return {
            "error_type": self.__class__.__name__,
            "error_code": self.error_code,
            "message": self.message,
            "japanese_message": self.japanese_message,
            "recoverable": self.recoverable,
            "timestamp": self.context.timestamp.isoformat(),
            "component": self.context.component,
            "operation": self.context.operation,
            "request_id": self.context.request_id,
            "user_id": self.context.user_id,
            "session_id": self.context.session_id,
            "additional_data": self.context.additional_data,
            "stack_trace": self.context.stack_trace,
            "cause": str(self.cause) if self.cause else None,
        }

    def get_user_message(self) -> str:
        """Get user-friendly message for display"""
        return self.japanese_message

    def get_detailed_message(self) -> str:
        """Get detailed message including context for logging"""
        details = [f"Error: {self.message}"]
        if self.error_code:
            details.append(f"Code: {self.error_code}")
        if self.context.component:
            details.append(f"Component: {self.context.component}")
        if self.context.operation:
            details.append(f"Operation: {self.context.operation}")
        if self.context.request_id:
            details.append(f"Request ID: {self.context.request_id}")
        if self.cause:
            details.append(f"Caused by: {self.cause}")
        return " | ".join(details)


class AgentConfigurationError(AgentError):
    """Exception raised for configuration-related errors"""

    def _get_default_japanese_message(self) -> str:
        return "設定エラーが発生しました"

    def _get_default_error_code(self) -> str:
        return "CONFIGURATION_ERROR"


class AgentValidationError(AgentError):
    """Exception raised for validation errors"""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        validation_errors: Optional[List[str]] = None,
        **kwargs,
    ):
        """Initialize validation error

        Args:
            message: Error message
            field: Field name that failed validation
            value: Value that failed validation
            validation_errors: List of specific validation errors
            **kwargs: Additional AgentError arguments
        """
        super().__init__(message, **kwargs)
        self.field = field
        self.value = value
        self.validation_errors = validation_errors or []

    def _get_default_japanese_message(self) -> str:
        return "入力パラメータの検証エラーが発生しました"

    def _get_default_error_code(self) -> str:
        return "VALIDATION_ERROR"

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary with validation-specific fields"""
        result = super().to_dict()
        result.update(
            {
                "field": self.field,
                "value": str(self.value) if self.value is not None else None,
                "validation_errors": self.validation_errors,
            }
        )
        return result


class AgentTimeoutError(AgentError):
    """Exception raised for timeout-related errors"""

    def __init__(self, message: str, timeout_seconds: Optional[float] = None, **kwargs):
        """Initialize timeout error

        Args:
            message: Error message
            timeout_seconds: Timeout value that was exceeded
            **kwargs: Additional AgentError arguments
        """
        super().__init__(message, **kwargs)
        self.timeout_seconds = timeout_seconds

    def _get_default_japanese_message(self) -> str:
        return "処理がタイムアウトしました"

    def _get_default_error_code(self) -> str:
        return "TIMEOUT_ERROR"

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary with timeout-specific fields"""
        result = super().to_dict()
        result["timeout_seconds"] = self.timeout_seconds
        return result


class AgentResourceError(AgentError):
    """Exception raised for resource-related errors"""

    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        **kwargs,
    ):
        """Initialize resource error

        Args:
            message: Error message
            resource_type: Type of resource that caused the error
            resource_id: ID of the resource that caused the error
            **kwargs: Additional AgentError arguments
        """
        super().__init__(message, **kwargs)
        self.resource_type = resource_type
        self.resource_id = resource_id

    def _get_default_japanese_message(self) -> str:
        return "リソースエラーが発生しました"

    def _get_default_error_code(self) -> str:
        return "RESOURCE_ERROR"

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary with resource-specific fields"""
        result = super().to_dict()
        result.update(
            {"resource_type": self.resource_type, "resource_id": self.resource_id}
        )
        return result
