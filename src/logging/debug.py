"""Debug Logging Support

Provides advanced debugging capabilities for development including
detailed tracing, performance measurement, and interactive debugging.

Author: CloudWatch Logs AI Agent Team
License: MIT
"""

import functools
import inspect
import logging
import time
import traceback
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable, Union
import threading
import sys
import os
from dataclasses import dataclass, field

from .structured_logger import StructuredLogger, LogContext, LogLevel, get_logger
from .context import LoggingContext, operation_context


@dataclass
class PerformanceMetrics:
    """Performance metrics for operations"""

    operation: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    memory_usage_mb: Optional[float] = None
    cpu_percent: Optional[float] = None
    peak_memory_mb: Optional[float] = None
    extra_metrics: Dict[str, Any] = field(default_factory=dict)

    def mark_end(self):
        """Mark the end of the operation"""
        self.end_time = datetime.utcnow()
        if self.start_time:
            self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "operation": self.operation,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "memory_usage_mb": self.memory_usage_mb,
            "cpu_percent": self.cpu_percent,
            "peak_memory_mb": self.peak_memory_mb,
            **self.extra_metrics,
        }


class DebugLogger:
    """Enhanced debug logger with advanced debugging features"""

    def __init__(
        self,
        name: str = "debug",
        enable_tracing: bool = True,
        enable_performance: bool = True,
        max_trace_depth: int = 10,
        performance_threshold_ms: float = 100.0,
    ):
        self.logger = get_logger(f"debug.{name}")
        self.enable_tracing = enable_tracing
        self.enable_performance = enable_performance
        self.max_trace_depth = max_trace_depth
        self.performance_threshold_ms = performance_threshold_ms

        # Performance tracking
        self.active_operations = {}
        self.performance_history = []
        self._lock = threading.Lock()

        # Call stack tracking
        self.call_stack = []
        self.trace_depth = 0

    def trace(
        self,
        message: str,
        context: Optional[LogContext] = None,
        extra: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """Log trace message with call stack information"""
        if not self.enable_tracing:
            return

        # Get caller information
        frame = inspect.currentframe().f_back
        caller_info = {
            "filename": os.path.basename(frame.f_code.co_filename),
            "function": frame.f_code.co_name,
            "line_number": frame.f_lineno,
            "trace_depth": self.trace_depth,
        }

        # Add local variables if requested
        if extra and extra.get("include_locals", False):
            caller_info["local_vars"] = {
                k: str(v)[:100]
                for k, v in frame.f_locals.items()
                if not k.startswith("_") and k != "self"
            }

        # Create debug context
        debug_context = context or LogContext()
        debug_context.extra_data.update(caller_info)
        if extra:
            debug_context.extra_data.update(extra)

        self.logger.debug(
            f"TRACE: {message}",
            context=debug_context,
            japanese_message=f"トレース: {message}",
            **kwargs,
        )

    def trace_function_call(
        self,
        func_name: str,
        args: tuple,
        kwargs: dict,
        context: Optional[LogContext] = None,
    ):
        """Trace function call with arguments"""
        if not self.enable_tracing or self.trace_depth >= self.max_trace_depth:
            return

        # Format arguments for logging
        args_str = ", ".join(
            [str(arg)[:50] for arg in args[:5]]
        )  # Limit to first 5 args
        kwargs_str = ", ".join(
            [f"{k}={str(v)[:50]}" for k, v in list(kwargs.items())[:5]]
        )

        debug_context = context or LogContext()
        debug_context.extra_data.update(
            {
                "function_name": func_name,
                "args_count": len(args),
                "kwargs_count": len(kwargs),
                "args_preview": args_str,
                "kwargs_preview": kwargs_str,
            }
        )

        self.logger.debug(
            f"CALL: {func_name}({args_str}{', ' + kwargs_str if kwargs_str else ''})",
            context=debug_context,
            japanese_message=f"関数呼び出し: {func_name}",
        )

    def trace_function_return(
        self,
        func_name: str,
        result: Any,
        duration_ms: float,
        context: Optional[LogContext] = None,
    ):
        """Trace function return with result and duration"""
        if not self.enable_tracing:
            return

        result_preview = str(result)[:100] if result is not None else "None"

        debug_context = context or LogContext()
        debug_context.extra_data.update(
            {
                "function_name": func_name,
                "duration_ms": duration_ms,
                "result_type": type(result).__name__,
                "result_preview": result_preview,
                "performance_flag": duration_ms > self.performance_threshold_ms,
            }
        )

        level = (
            LogLevel.WARNING
            if duration_ms > self.performance_threshold_ms
            else LogLevel.DEBUG
        )

        self.logger._log(
            level,
            f"RETURN: {func_name} -> {result_preview} ({duration_ms:.2f}ms)",
            context=debug_context,
            japanese_message=f"関数戻り: {func_name} ({duration_ms:.2f}ms)",
        )

    def trace_exception(
        self, func_name: str, exception: Exception, context: Optional[LogContext] = None
    ):
        """Trace function exception"""
        debug_context = context or LogContext()
        debug_context.extra_data.update(
            {
                "function_name": func_name,
                "exception_type": type(exception).__name__,
                "exception_message": str(exception),
                "traceback": traceback.format_exc(),
            }
        )

        self.logger.error(
            f"EXCEPTION: {func_name} raised {type(exception).__name__}: {exception}",
            context=debug_context,
            japanese_message=f"例外発生: {func_name}で{type(exception).__name__}",
            exc_info=True,
        )

    def start_performance_tracking(
        self, operation: str, context: Optional[LogContext] = None
    ) -> str:
        """Start tracking performance for an operation"""
        if not self.enable_performance:
            return operation

        # Try to get memory usage
        memory_usage = None
        try:
            import psutil

            process = psutil.Process()
            memory_usage = process.memory_info().rss / 1024 / 1024  # MB
        except ImportError:
            pass

        metrics = PerformanceMetrics(
            operation=operation,
            start_time=datetime.utcnow(),
            memory_usage_mb=memory_usage,
        )

        operation_id = f"{operation}_{id(metrics)}"

        with self._lock:
            self.active_operations[operation_id] = metrics

        debug_context = context or LogContext()
        debug_context.extra_data.update(
            {"operation_id": operation_id, "start_memory_mb": memory_usage}
        )

        self.logger.debug(
            f"PERF_START: {operation}",
            context=debug_context,
            japanese_message=f"パフォーマンス追跡開始: {operation}",
        )

        return operation_id

    def end_performance_tracking(
        self,
        operation_id: str,
        context: Optional[LogContext] = None,
        extra_metrics: Optional[Dict[str, Any]] = None,
    ):
        """End performance tracking for an operation"""
        if not self.enable_performance:
            return

        with self._lock:
            metrics = self.active_operations.pop(operation_id, None)

        if not metrics:
            self.logger.warning(f"No active performance tracking for {operation_id}")
            return

        metrics.mark_end()

        # Try to get final memory usage
        try:
            import psutil

            process = psutil.Process()
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            if metrics.memory_usage_mb:
                metrics.peak_memory_mb = max(metrics.memory_usage_mb, final_memory)
        except ImportError:
            pass

        # Add extra metrics
        if extra_metrics:
            metrics.extra_metrics.update(extra_metrics)

        # Add to history
        with self._lock:
            self.performance_history.append(metrics)
            # Keep only last 1000 entries
            if len(self.performance_history) > 1000:
                self.performance_history = self.performance_history[-1000:]

        # Log performance result
        debug_context = context or LogContext()
        debug_context.extra_data.update(metrics.to_dict())

        level = (
            LogLevel.WARNING
            if metrics.duration_ms
            and metrics.duration_ms > self.performance_threshold_ms
            else LogLevel.DEBUG
        )

        self.logger._log(
            level,
            f"PERF_END: {metrics.operation} completed in {metrics.duration_ms:.2f}ms",
            context=debug_context,
            japanese_message=f"パフォーマンス追跡終了: {metrics.operation} ({metrics.duration_ms:.2f}ms)",
        )

    def log_variable_state(
        self,
        variables: Dict[str, Any],
        context: Optional[LogContext] = None,
        message: str = "Variable state",
    ):
        """Log current state of variables for debugging"""
        debug_context = context or LogContext()

        # Format variables for logging
        var_info = {}
        for name, value in variables.items():
            var_info[name] = {
                "type": type(value).__name__,
                "value": str(value)[:200],  # Truncate long values
                "size": len(str(value)) if hasattr(value, "__len__") else None,
            }

        debug_context.extra_data.update(
            {"variable_count": len(variables), "variables": var_info}
        )

        self.logger.debug(
            f"VARS: {message}",
            context=debug_context,
            japanese_message=f"変数状態: {message}",
        )

    def log_data_structure(
        self,
        data: Any,
        name: str = "data",
        max_depth: int = 3,
        context: Optional[LogContext] = None,
    ):
        """Log detailed information about a data structure"""

        def analyze_structure(obj, depth=0, max_depth=3):
            if depth > max_depth:
                return {"truncated": True, "reason": "max_depth_exceeded"}

            if obj is None:
                return {"type": "NoneType", "value": None}
            elif isinstance(obj, (str, int, float, bool)):
                return {
                    "type": type(obj).__name__,
                    "value": str(obj)[:100],
                    "length": len(str(obj)),
                }
            elif isinstance(obj, (list, tuple)):
                return {
                    "type": type(obj).__name__,
                    "length": len(obj),
                    "items": [
                        analyze_structure(item, depth + 1, max_depth)
                        for item in obj[:5]
                    ],
                }
            elif isinstance(obj, dict):
                return {
                    "type": "dict",
                    "length": len(obj),
                    "keys": list(obj.keys())[:10],
                    "items": {
                        k: analyze_structure(v, depth + 1, max_depth)
                        for k, v in list(obj.items())[:5]
                    },
                }
            else:
                return {
                    "type": type(obj).__name__,
                    "string_repr": str(obj)[:100],
                    "attributes": [
                        attr for attr in dir(obj) if not attr.startswith("_")
                    ][:10],
                }

        structure_info = analyze_structure(data, max_depth=max_depth)

        debug_context = context or LogContext()
        debug_context.extra_data.update(
            {"data_name": name, "structure": structure_info}
        )

        self.logger.debug(
            f"STRUCT: {name} -> {structure_info.get('type', 'unknown')}",
            context=debug_context,
            japanese_message=f"データ構造: {name}",
        )

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary statistics"""
        with self._lock:
            if not self.performance_history:
                return {"message": "No performance data available"}

            durations = [
                m.duration_ms for m in self.performance_history if m.duration_ms
            ]
            memory_usage = [
                m.memory_usage_mb for m in self.performance_history if m.memory_usage_mb
            ]

            summary = {
                "total_operations": len(self.performance_history),
                "active_operations": len(self.active_operations),
                "avg_duration_ms": sum(durations) / len(durations) if durations else 0,
                "max_duration_ms": max(durations) if durations else 0,
                "min_duration_ms": min(durations) if durations else 0,
                "slow_operations": len(
                    [d for d in durations if d > self.performance_threshold_ms]
                ),
                "avg_memory_mb": (
                    sum(memory_usage) / len(memory_usage) if memory_usage else 0
                ),
                "max_memory_mb": max(memory_usage) if memory_usage else 0,
            }

            return summary


# Global debug logger instance
_debug_logger = DebugLogger()


def debug_trace(message: str, **kwargs):
    """Quick debug trace function"""
    _debug_logger.trace(message, **kwargs)


def debug_vars(**variables):
    """Quick function to log variable states"""
    _debug_logger.log_variable_state(variables)


def debug_data(data: Any, name: str = "data", **kwargs):
    """Quick function to log data structure"""
    _debug_logger.log_data_structure(data, name, **kwargs)


def trace_calls(
    enable_performance: bool = True, enable_tracing: bool = True, max_depth: int = 5
):
    """Decorator to trace function calls and performance"""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            func_name = f"{func.__module__}.{func.__qualname__}"

            # Start tracing
            if enable_tracing:
                _debug_logger.trace_function_call(func_name, args, kwargs)
                _debug_logger.trace_depth += 1

            # Start performance tracking
            operation_id = None
            if enable_performance:
                operation_id = _debug_logger.start_performance_tracking(func_name)

            try:
                start_time = time.time()
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000

                # Log return
                if enable_tracing:
                    _debug_logger.trace_function_return(func_name, result, duration_ms)

                return result

            except Exception as e:
                duration_ms = (
                    (time.time() - start_time) * 1000 if "start_time" in locals() else 0
                )

                # Log exception
                if enable_tracing:
                    _debug_logger.trace_exception(func_name, e)

                raise

            finally:
                # End performance tracking
                if enable_performance and operation_id:
                    _debug_logger.end_performance_tracking(operation_id)

                # Decrease trace depth
                if enable_tracing:
                    _debug_logger.trace_depth = max(0, _debug_logger.trace_depth - 1)

        return wrapper

    return decorator


@contextmanager
def debug_context(operation_name: str, **context_data):
    """Context manager for debugging operations"""
    operation_id = _debug_logger.start_performance_tracking(operation_name)

    debug_context = LogContext(operation=operation_name, extra_data=context_data)

    with operation_context(operation_name):
        try:
            _debug_logger.trace(
                f"Starting operation: {operation_name}", context=debug_context
            )
            yield _debug_logger
            _debug_logger.trace(
                f"Completed operation: {operation_name}", context=debug_context
            )

        except Exception as e:
            _debug_logger.trace_exception(operation_name, e, context=debug_context)
            raise

        finally:
            _debug_logger.end_performance_tracking(operation_id, context=debug_context)


def get_debug_logger(name: str = "main") -> DebugLogger:
    """Get a debug logger instance"""
    return DebugLogger(name)


def get_performance_summary() -> Dict[str, Any]:
    """Get global performance summary"""
    return _debug_logger.get_performance_summary()
