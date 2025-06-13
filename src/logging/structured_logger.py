"""Structured Logger Implementation

Provides enhanced logging with contextual information, metrics integration,
and Japanese language support for the CloudWatch Logs AI Agent.

Author: CloudWatch Logs AI Agent Team
License: MIT
"""

import logging
import threading
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, Union, List
import json
import uuid

# Context variable for request tracking
_request_context: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    "request_context", default=None
)


class LogLevel(Enum):
    """Enhanced log levels with Japanese descriptions"""

    DEBUG = ("DEBUG", "デバッグ", 10)
    INFO = ("INFO", "情報", 20)
    WARNING = ("WARNING", "警告", 30)
    ERROR = ("ERROR", "エラー", 40)
    CRITICAL = ("CRITICAL", "重要", 50)

    def __init__(self, name: str, japanese_name: str, level: int):
        self.level_name = name
        self.japanese_name = japanese_name
        self.level = level


@dataclass
class LogContext:
    """Structured log context information"""

    request_id: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    client_ip: Optional[str] = None
    component: Optional[str] = None
    operation: Optional[str] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.utcnow())
    extra_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary"""
        return {
            "request_id": self.request_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "client_ip": self.client_ip,
            "component": self.component,
            "operation": self.operation,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "timestamp": self.timestamp.isoformat(),
            **self.extra_data,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LogContext":
        """Create context from dictionary"""
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        elif timestamp is None:
            timestamp = datetime.utcnow()

        extra_data = {
            k: v
            for k, v in data.items()
            if k
            not in {
                "request_id",
                "session_id",
                "user_id",
                "client_ip",
                "component",
                "operation",
                "trace_id",
                "span_id",
                "timestamp",
            }
        }

        return cls(
            request_id=data.get("request_id"),
            session_id=data.get("session_id"),
            user_id=data.get("user_id"),
            client_ip=data.get("client_ip"),
            component=data.get("component"),
            operation=data.get("operation"),
            trace_id=data.get("trace_id"),
            span_id=data.get("span_id"),
            timestamp=timestamp,
            extra_data=extra_data,
        )

    def copy(self, **updates) -> "LogContext":
        """Create a copy with updates"""
        data = self.to_dict()
        data.update(updates)
        return self.from_dict(data)


class StructuredLogger:
    """Enhanced logger with structured logging and context support"""

    def __init__(
        self,
        name: str,
        logger: Optional[logging.Logger] = None,
        default_context: Optional[LogContext] = None,
    ):
        self.name = name
        self.logger = logger or logging.getLogger(name)
        self.default_context = default_context or LogContext(component=name)
        self.metrics = {
            "total_logs": 0,
            "logs_by_level": {level.level_name: 0 for level in LogLevel},
            "logs_by_component": {},
            "error_count": 0,
            "warning_count": 0,
        }
        self._lock = threading.Lock()

    def _update_metrics(self, level: LogLevel, context: LogContext):
        """Update logging metrics"""
        with self._lock:
            self.metrics["total_logs"] += 1
            self.metrics["logs_by_level"][level.level_name] += 1

            component = context.component or "unknown"
            self.metrics["logs_by_component"][component] = (
                self.metrics["logs_by_component"].get(component, 0) + 1
            )

            if level in [LogLevel.ERROR, LogLevel.CRITICAL]:
                self.metrics["error_count"] += 1
            elif level == LogLevel.WARNING:
                self.metrics["warning_count"] += 1

    def _get_effective_context(
        self, context: Optional[LogContext] = None
    ) -> LogContext:
        """Get effective context by merging defaults, request context, and provided context"""
        # Start with default context
        effective = self.default_context.copy()

        # Merge request context if available
        request_ctx = _request_context.get()
        if request_ctx:
            effective = effective.copy(**request_ctx)

        # Merge provided context
        if context:
            effective = effective.copy(**context.to_dict())

        return effective

    def _log(
        self,
        level: LogLevel,
        message: str,
        context: Optional[LogContext] = None,
        japanese_message: Optional[str] = None,
        exc_info: bool = False,
        **kwargs,
    ):
        """Internal logging method"""
        effective_context = self._get_effective_context(context)

        # Update metrics
        self._update_metrics(level, effective_context)

        # Prepare extra data for logger
        extra_data = {
            "level_japanese": level.japanese_name,
            "japanese_message": japanese_message,
            **effective_context.to_dict(),
            **kwargs,
        }

        # Remove None values
        extra_data = {k: v for k, v in extra_data.items() if v is not None}

        # Log the message
        self.logger.log(level.level, message, exc_info=exc_info, extra=extra_data)

    def debug(
        self,
        message: str,
        context: Optional[LogContext] = None,
        japanese_message: Optional[str] = None,
        **kwargs,
    ):
        """Log debug message"""
        self._log(LogLevel.DEBUG, message, context, japanese_message, **kwargs)

    def info(
        self,
        message: str,
        context: Optional[LogContext] = None,
        japanese_message: Optional[str] = None,
        **kwargs,
    ):
        """Log info message"""
        self._log(LogLevel.INFO, message, context, japanese_message, **kwargs)

    def warning(
        self,
        message: str,
        context: Optional[LogContext] = None,
        japanese_message: Optional[str] = None,
        **kwargs,
    ):
        """Log warning message"""
        self._log(LogLevel.WARNING, message, context, japanese_message, **kwargs)

    def error(
        self,
        message: str,
        context: Optional[LogContext] = None,
        japanese_message: Optional[str] = None,
        exc_info: bool = True,
        **kwargs,
    ):
        """Log error message"""
        self._log(
            LogLevel.ERROR, message, context, japanese_message, exc_info, **kwargs
        )

    def critical(
        self,
        message: str,
        context: Optional[LogContext] = None,
        japanese_message: Optional[str] = None,
        exc_info: bool = True,
        **kwargs,
    ):
        """Log critical message"""
        self._log(
            LogLevel.CRITICAL, message, context, japanese_message, exc_info, **kwargs
        )

    def exception(
        self,
        message: str,
        context: Optional[LogContext] = None,
        japanese_message: Optional[str] = None,
        **kwargs,
    ):
        """Log exception with traceback"""
        self._log(LogLevel.ERROR, message, context, japanese_message, True, **kwargs)

    def log_operation_start(
        self, operation: str, context: Optional[LogContext] = None, **kwargs
    ):
        """Log operation start"""
        ctx = context or LogContext()
        ctx.operation = operation

        self.info(
            f"Operation started: {operation}",
            context=ctx,
            japanese_message=f"操作開始: {operation}",
            operation_status="started",
            **kwargs,
        )

    def log_operation_success(
        self,
        operation: str,
        duration_ms: Optional[float] = None,
        context: Optional[LogContext] = None,
        **kwargs,
    ):
        """Log operation success"""
        ctx = context or LogContext()
        ctx.operation = operation

        extra = {"operation_status": "success"}
        if duration_ms is not None:
            extra["duration_ms"] = duration_ms

        self.info(
            f"Operation completed successfully: {operation}",
            context=ctx,
            japanese_message=f"操作正常完了: {operation}",
            **extra,
            **kwargs,
        )

    def log_operation_failure(
        self,
        operation: str,
        error: str,
        duration_ms: Optional[float] = None,
        context: Optional[LogContext] = None,
        **kwargs,
    ):
        """Log operation failure"""
        ctx = context or LogContext()
        ctx.operation = operation

        extra = {"operation_status": "failed", "error_message": error}
        if duration_ms is not None:
            extra["duration_ms"] = duration_ms

        self.error(
            f"Operation failed: {operation} - {error}",
            context=ctx,
            japanese_message=f"操作失敗: {operation} - {error}",
            **extra,
            **kwargs,
        )

    def get_metrics(self) -> Dict[str, Any]:
        """Get logging metrics"""
        with self._lock:
            return self.metrics.copy()

    def reset_metrics(self):
        """Reset logging metrics"""
        with self._lock:
            self.metrics = {
                "total_logs": 0,
                "logs_by_level": {level.level_name: 0 for level in LogLevel},
                "logs_by_component": {},
                "error_count": 0,
                "warning_count": 0,
            }


# Global logger registry
_loggers: Dict[str, StructuredLogger] = {}
_lock = threading.Lock()


def create_logger(
    name: str,
    level: Union[str, int, LogLevel] = LogLevel.INFO,
    context: Optional[LogContext] = None,
) -> StructuredLogger:
    """Create a new structured logger"""

    # Convert level to LogLevel if needed
    if isinstance(level, str):
        level = LogLevel[level.upper()]
    elif isinstance(level, int):
        for log_level in LogLevel:
            if log_level.level == level:
                level = log_level
                break
        else:
            level = LogLevel.INFO

    # Create underlying logger
    logger = logging.getLogger(name)
    logger.setLevel(level.level)

    # Create structured logger
    structured_logger = StructuredLogger(name, logger, context)

    # Register logger
    with _lock:
        _loggers[name] = structured_logger

    return structured_logger


def get_logger(name: str) -> StructuredLogger:
    """Get or create a structured logger"""
    with _lock:
        if name not in _loggers:
            return create_logger(name)
        return _loggers[name]


def setup_logging(
    level: Union[str, LogLevel] = LogLevel.INFO,
    log_file: Optional[str] = None,
    json_format: bool = False,
    include_context: bool = True,
):
    """Setup enhanced logging configuration"""

    # Import here to avoid circular imports
    from .formatters import JSONFormatter, ConsoleFormatter
    from .handlers import RotatingFileHandlerWithContext

    # Convert level
    if isinstance(level, str):
        level = LogLevel[level.upper()]

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level.level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler()
    if json_format:
        console_formatter = JSONFormatter(include_context=include_context)
    else:
        console_formatter = ConsoleFormatter(include_context=include_context)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File handler if specified
    if log_file:
        file_handler = RotatingFileHandlerWithContext(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=5  # 10MB
        )
        file_formatter = JSONFormatter(include_context=include_context)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    return root_logger


def set_request_context(**context):
    """Set request context for current execution"""
    current = _request_context.get() or {}
    current.update(context)
    _request_context.set(current)


def get_request_context() -> Optional[Dict[str, Any]]:
    """Get current request context"""
    return _request_context.get()


def clear_request_context():
    """Clear request context"""
    _request_context.set(None)
