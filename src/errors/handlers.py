"""Centralized Error Handling Mechanism

Provides decorators, context managers, and utilities for centralized
error handling throughout the CloudWatch Logs AI Agent.

Author: CloudWatch Logs AI Agent Team
License: MIT
"""

import asyncio
import functools
import logging
import traceback
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Type,
    Union,
    TypeVar,
    Awaitable,
    AsyncGenerator,
    Generator,
)

from .base import AgentError, ErrorContext
from .aws import AWSError, CloudWatchLogsError, CredentialsError
from .mcp import MCPError, MCPServerError
from .tools import ToolError, ToolExecutionError, ToolTimeoutError

# Type variables for generic decorators
F = TypeVar("F", bound=Callable[..., Any])
AsyncF = TypeVar("AsyncF", bound=Callable[..., Awaitable[Any]])

logger = logging.getLogger(__name__)


class ErrorRecoveryConfig:
    """Configuration for error recovery strategies"""

    def __init__(
        self,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        backoff_multiplier: float = 2.0,
        recoverable_errors: Optional[List[Type[Exception]]] = None,
        fatal_errors: Optional[List[Type[Exception]]] = None,
    ):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.backoff_multiplier = backoff_multiplier
        self.recoverable_errors = recoverable_errors or [
            ConnectionError,
            TimeoutError,
            ToolTimeoutError,
        ]
        self.fatal_errors = fatal_errors or [CredentialsError]


class ErrorHandler:
    """Centralized error handler with recovery strategies"""

    def __init__(self, component: str = "unknown"):
        self.component = component
        self.error_history: List[Dict[str, Any]] = []
        self.metrics = {
            "total_errors": 0,
            "recoverable_errors": 0,
            "fatal_errors": 0,
            "errors_by_type": {},
        }

    def handle_error(
        self,
        error: Exception,
        context: Optional[ErrorContext] = None,
        operation: Optional[str] = None,
        recoverable: bool = True,
    ) -> AgentError:
        """Handle and convert exceptions to AgentError instances"""

        # Create context if not provided
        if context is None:
            context = ErrorContext(component=self.component, operation=operation)
        else:
            context.component = context.component or self.component
            context.operation = context.operation or operation

        # Convert to AgentError if needed
        if isinstance(error, AgentError):
            agent_error = error
            agent_error.context = context
        else:
            agent_error = self._convert_to_agent_error(error, context, recoverable)

        # Update metrics
        self._update_metrics(agent_error)

        # Record error history
        self._record_error(agent_error)

        # Log error
        self._log_error(agent_error)

        return agent_error

    def _convert_to_agent_error(
        self, error: Exception, context: ErrorContext, recoverable: bool
    ) -> AgentError:
        """Convert standard exceptions to AgentError instances"""

        error_message = str(error)

        # AWS/Boto3 errors
        if hasattr(error, "response") and "Error" in getattr(error, "response", {}):
            aws_error = error.response["Error"]
            return AWSError(
                message=error_message,
                aws_error_code=aws_error.get("Code"),
                aws_error_message=aws_error.get("Message"),
                context=context,
                cause=error,
                recoverable=recoverable,
            )

        # Timeout errors
        if isinstance(error, (asyncio.TimeoutError, TimeoutError)):
            return ToolTimeoutError(
                message=f"Operation timed out: {error_message}",
                context=context,
                cause=error,
                recoverable=True,
            )

        # Connection errors
        if isinstance(error, ConnectionError):
            return MCPError(
                message=f"Connection error: {error_message}",
                context=context,
                cause=error,
                recoverable=True,
            )

        # Generic error
        return AgentError(
            message=error_message, context=context, cause=error, recoverable=recoverable
        )

    def _update_metrics(self, error: AgentError):
        """Update error metrics"""
        self.metrics["total_errors"] += 1

        if error.recoverable:
            self.metrics["recoverable_errors"] += 1
        else:
            self.metrics["fatal_errors"] += 1

        error_type = type(error).__name__
        self.metrics["errors_by_type"][error_type] = (
            self.metrics["errors_by_type"].get(error_type, 0) + 1
        )

    def _record_error(self, error: AgentError):
        """Record error in history"""
        self.error_history.append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "error_type": type(error).__name__,
                "error_code": error.error_code,
                "message": error.message,
                "component": error.context.component,
                "operation": error.context.operation,
                "recoverable": error.recoverable,
            }
        )

        # Keep only last 100 errors
        if len(self.error_history) > 100:
            self.error_history = self.error_history[-100:]

    def _log_error(self, error: AgentError):
        """Log error with appropriate level"""
        level = logging.WARNING if error.recoverable else logging.ERROR

        logger.log(
            level,
            f"[{self.component}] {error.get_detailed_message()}",
            extra={
                "error_code": error.error_code,
                "error_type": type(error).__name__,
                "component": error.context.component,
                "operation": error.context.operation,
                "recoverable": error.recoverable,
                "japanese_message": error.japanese_message,
            },
        )

    def get_metrics(self) -> Dict[str, Any]:
        """Get error metrics"""
        return self.metrics.copy()

    def get_recent_errors(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent errors"""
        return self.error_history[-limit:]


# Global error handler instance
_global_error_handler = ErrorHandler("global")


def handle_errors(
    component: Optional[str] = None,
    operation: Optional[str] = None,
    recovery_config: Optional[ErrorRecoveryConfig] = None,
    return_on_error: Any = None,
    reraise: bool = False,
):
    """Decorator for handling errors in functions and methods"""

    def decorator(func: F) -> F:
        if asyncio.iscoroutinefunction(func):
            return _async_error_handler(
                func, component, operation, recovery_config, return_on_error, reraise
            )
        else:
            return _sync_error_handler(
                func, component, operation, recovery_config, return_on_error, reraise
            )

    return decorator


def _async_error_handler(
    func: AsyncF,
    component: Optional[str],
    operation: Optional[str],
    recovery_config: Optional[ErrorRecoveryConfig],
    return_on_error: Any,
    reraise: bool,
) -> AsyncF:
    """Async error handler decorator"""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        error_handler = ErrorHandler(component or func.__module__)
        config = recovery_config or ErrorRecoveryConfig()

        last_error = None
        delay = config.retry_delay

        for attempt in range(config.max_retries + 1):
            try:
                return await func(*args, **kwargs)

            except Exception as e:
                context = ErrorContext(
                    component=component or func.__module__,
                    operation=operation or func.__name__,
                    additional_data={
                        "attempt": attempt + 1,
                        "max_retries": config.max_retries,
                        "function": func.__name__,
                        "args_count": len(args),
                        "kwargs_keys": list(kwargs.keys()),
                    },
                )

                agent_error = error_handler.handle_error(e, context, operation)
                last_error = agent_error

                # Check if error is fatal
                if any(isinstance(e, fatal_type) for fatal_type in config.fatal_errors):
                    if reraise:
                        raise agent_error
                    return return_on_error

                # Check if we should retry
                if attempt < config.max_retries and any(
                    isinstance(e, recoverable_type)
                    for recoverable_type in config.recoverable_errors
                ):
                    await asyncio.sleep(delay)
                    delay *= config.backoff_multiplier
                    continue

                # No more retries or non-recoverable error
                if reraise:
                    raise agent_error
                return return_on_error

        # All retries exhausted
        if reraise and last_error:
            raise last_error
        return return_on_error

    return wrapper


def _sync_error_handler(
    func: F,
    component: Optional[str],
    operation: Optional[str],
    recovery_config: Optional[ErrorRecoveryConfig],
    return_on_error: Any,
    reraise: bool,
) -> F:
    """Sync error handler decorator"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        error_handler = ErrorHandler(component or func.__module__)
        config = recovery_config or ErrorRecoveryConfig()

        last_error = None
        delay = config.retry_delay

        for attempt in range(config.max_retries + 1):
            try:
                return func(*args, **kwargs)

            except Exception as e:
                context = ErrorContext(
                    component=component or func.__module__,
                    operation=operation or func.__name__,
                    additional_data={
                        "attempt": attempt + 1,
                        "max_retries": config.max_retries,
                        "function": func.__name__,
                        "args_count": len(args),
                        "kwargs_keys": list(kwargs.keys()),
                    },
                )

                agent_error = error_handler.handle_error(e, context, operation)
                last_error = agent_error

                # Check if error is fatal
                if any(isinstance(e, fatal_type) for fatal_type in config.fatal_errors):
                    if reraise:
                        raise agent_error
                    return return_on_error

                # Check if we should retry
                if attempt < config.max_retries and any(
                    isinstance(e, recoverable_type)
                    for recoverable_type in config.recoverable_errors
                ):
                    import time

                    time.sleep(delay)
                    delay *= config.backoff_multiplier
                    continue

                # No more retries or non-recoverable error
                if reraise:
                    raise agent_error
                return return_on_error

        # All retries exhausted
        if reraise and last_error:
            raise last_error
        return return_on_error

    return wrapper


@contextmanager
def error_context(
    component: str, operation: str, reraise: bool = True, return_on_error: Any = None
) -> Generator[ErrorHandler, None, None]:
    """Context manager for error handling"""

    error_handler = ErrorHandler(component)

    try:
        yield error_handler
    except Exception as e:
        context = ErrorContext(component=component, operation=operation)

        agent_error = error_handler.handle_error(e, context, operation)

        if reraise:
            raise agent_error

        return return_on_error


@asynccontextmanager
async def async_error_context(
    component: str, operation: str, reraise: bool = True, return_on_error: Any = None
) -> AsyncGenerator[ErrorHandler, None]:
    """Async context manager for error handling"""

    error_handler = ErrorHandler(component)

    try:
        yield error_handler
    except Exception as e:
        context = ErrorContext(component=component, operation=operation)

        agent_error = error_handler.handle_error(e, context, operation)

        if reraise:
            raise agent_error

        return return_on_error


def get_global_error_metrics() -> Dict[str, Any]:
    """Get global error metrics"""
    return _global_error_handler.get_metrics()


def get_recent_global_errors(limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent global errors"""
    return _global_error_handler.get_recent_errors(limit)


def handle_exception(
    exception: Exception, component: str = "unknown", operation: str = "unknown"
) -> AgentError:
    """Handle any exception and convert to AgentError"""
    context = ErrorContext(component=component, operation=operation)
    return _global_error_handler.handle_error(exception, context, operation)


def handle_specific_exceptions(
    error: Exception,
    exception_handlers: List[
        Tuple[Type[Exception], Callable[[Exception, ErrorContext], AgentError]]
    ],
    error_context: ErrorContext,
) -> AgentError:
    for exception_type, handler in exception_handlers:
        if isinstance(error, exception_type):
            return handler(error, error_context)

    return _global_error_handler.handle_error(error, error_context)


def handle_tool_error(error: Exception, context: ErrorContext) -> AgentError:
    # Implementation of handle_tool_error
    pass


def handle_aws_error(error: Exception, context: ErrorContext) -> AgentError:
    # Implementation of handle_aws_error
    pass


def handle_mcp_error(error: Exception, context: ErrorContext) -> AgentError:
    # Implementation of handle_mcp_error
    pass


def handle_validation_error(error: Exception, context: ErrorContext) -> AgentError:
    # Implementation of handle_validation_error
    pass


def handle_connection_error(error: Exception, context: ErrorContext) -> AgentError:
    # Implementation of handle_connection_error
    pass


def handle_timeout_error(error: Exception, context: ErrorContext) -> AgentError:
    # Implementation of handle_timeout_error
    pass


def handle_permission_error(error: Exception, context: ErrorContext) -> AgentError:
    # Implementation of handle_permission_error
    pass


def handle_file_not_found_error(error: Exception, context: ErrorContext) -> AgentError:
    # Implementation of handle_file_not_found_error
    pass


def handle_key_error(error: Exception, context: ErrorContext) -> AgentError:
    # Implementation of handle_key_error
    pass


def handle_value_error(error: Exception, context: ErrorContext) -> AgentError:
    # Implementation of handle_value_error
    pass
