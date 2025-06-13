"""Custom Log Formatters

Provides specialized formatters for different output targets with
structured logging and Japanese language support.

Author: CloudWatch Logs AI Agent Team
License: MIT
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional
import traceback


class StructuredFormatter(logging.Formatter):
    """Base structured formatter with context support"""

    def __init__(
        self,
        include_context: bool = True,
        include_japanese: bool = True,
        extra_fields: Optional[list] = None,
    ):
        super().__init__()
        self.include_context = include_context
        self.include_japanese = include_japanese
        self.extra_fields = extra_fields or []

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with structured data"""

        # Build base log data
        log_data = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add Japanese level if available
        if self.include_japanese and hasattr(record, "level_japanese"):
            log_data["level_japanese"] = record.level_japanese

        # Add Japanese message if available
        if self.include_japanese and hasattr(record, "japanese_message"):
            log_data["japanese_message"] = record.japanese_message

        # Add context information if enabled
        if self.include_context:
            context_fields = [
                "request_id",
                "session_id",
                "user_id",
                "client_ip",
                "component",
                "operation",
                "trace_id",
                "span_id",
            ]

            for field in context_fields:
                if hasattr(record, field) and getattr(record, field) is not None:
                    log_data[field] = getattr(record, field)

        # Add extra fields
        for field in self.extra_fields:
            if hasattr(record, field):
                log_data[field] = getattr(record, field)

        # Add exception information if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info),
            }

        # Add any additional attributes from the record
        for key, value in record.__dict__.items():
            if (
                key not in log_data
                and not key.startswith("_")
                and key
                not in [
                    "name",
                    "msg",
                    "args",
                    "levelname",
                    "levelno",
                    "pathname",
                    "filename",
                    "module",
                    "lineno",
                    "funcName",
                    "created",
                    "msecs",
                    "relativeCreated",
                    "thread",
                    "threadName",
                    "processName",
                    "process",
                    "getMessage",
                    "exc_info",
                    "exc_text",
                    "stack_info",
                ]
            ):
                try:
                    # Only include JSON-serializable values
                    json.dumps(value)
                    log_data[key] = value
                except (TypeError, ValueError):
                    log_data[key] = str(value)

        return self._format_output(log_data)

    def _format_output(self, log_data: Dict[str, Any]) -> str:
        """Format the output - to be overridden by subclasses"""
        return str(log_data)


class JSONFormatter(StructuredFormatter):
    """JSON formatter for structured logging"""

    def __init__(
        self,
        include_context: bool = True,
        include_japanese: bool = True,
        extra_fields: Optional[list] = None,
        indent: Optional[int] = None,
        ensure_ascii: bool = False,
    ):
        super().__init__(include_context, include_japanese, extra_fields)
        self.indent = indent
        self.ensure_ascii = ensure_ascii

    def _format_output(self, log_data: Dict[str, Any]) -> str:
        """Format as JSON"""
        return json.dumps(
            log_data,
            indent=self.indent,
            ensure_ascii=self.ensure_ascii,
            default=str,
            separators=(",", ":") if self.indent is None else (",", ": "),
        )


class ConsoleFormatter(StructuredFormatter):
    """Human-readable console formatter"""

    def __init__(
        self,
        include_context: bool = True,
        include_japanese: bool = False,
        extra_fields: Optional[list] = None,
        use_colors: bool = True,
        compact: bool = False,
    ):
        super().__init__(include_context, include_japanese, extra_fields)
        self.use_colors = use_colors
        self.compact = compact

        # ANSI color codes
        self.colors = (
            {
                "DEBUG": "\033[36m",  # Cyan
                "INFO": "\033[32m",  # Green
                "WARNING": "\033[33m",  # Yellow
                "ERROR": "\033[31m",  # Red
                "CRITICAL": "\033[35m",  # Magenta
                "RESET": "\033[0m",  # Reset
            }
            if use_colors
            else {}
        )

    def _format_output(self, log_data: Dict[str, Any]) -> str:
        """Format for console output"""

        # Base format
        timestamp = log_data.get("timestamp", "")
        level = log_data.get("level", "INFO")
        logger_name = log_data.get("logger", "")
        message = log_data.get("message", "")

        # Apply colors
        if self.use_colors and level in self.colors:
            level_colored = f"{self.colors[level]}{level}{self.colors['RESET']}"
        else:
            level_colored = level

        if self.compact:
            # Compact format
            parts = [f"{timestamp[:19]}", level_colored, message]
        else:
            # Full format
            parts = [f"{timestamp}", f"[{level_colored}]", f"{logger_name}:", message]

        base_line = " ".join(filter(None, parts))

        # Add context information
        context_parts = []
        if self.include_context:
            context_fields = ["request_id", "component", "operation"]
            for field in context_fields:
                if field in log_data and log_data[field]:
                    context_parts.append(f"{field}={log_data[field]}")

        # Add Japanese message if available
        if self.include_japanese and "japanese_message" in log_data:
            context_parts.append(f"ja='{log_data['japanese_message']}'")

        # Add extra fields
        for field in self.extra_fields:
            if field in log_data and field not in [
                "timestamp",
                "level",
                "logger",
                "message",
            ]:
                context_parts.append(f"{field}={log_data[field]}")

        if context_parts:
            if self.compact:
                base_line += f" [{', '.join(context_parts)}]"
            else:
                base_line += f"\n  Context: {', '.join(context_parts)}"

        # Add exception information
        if "exception" in log_data:
            exc_info = log_data["exception"]
            if self.compact:
                base_line += f" [Exception: {exc_info.get('type', 'Unknown')}: {exc_info.get('message', '')}]"
            else:
                base_line += f"\n  Exception: {exc_info.get('type', 'Unknown')}: {exc_info.get('message', '')}"
                if exc_info.get("traceback"):
                    base_line += (
                        f"\n  Traceback:\n    {'    '.join(exc_info['traceback'])}"
                    )

        return base_line


class FileFormatter(JSONFormatter):
    """File formatter optimized for log files"""

    def __init__(
        self,
        include_context: bool = True,
        include_japanese: bool = True,
        extra_fields: Optional[list] = None,
        compress_fields: bool = True,
    ):
        super().__init__(include_context, include_japanese, extra_fields)
        self.compress_fields = compress_fields

    def _format_output(self, log_data: Dict[str, Any]) -> str:
        """Format optimized for file storage"""

        if self.compress_fields:
            # Remove None values and empty strings to save space
            compressed_data = {
                k: v for k, v in log_data.items() if v is not None and v != ""
            }

            # Compress timestamp to shorter format if possible
            if "timestamp" in compressed_data:
                timestamp = compressed_data["timestamp"]
                if timestamp.endswith("Z"):
                    # Remove milliseconds for file logs to save space
                    compressed_data["timestamp"] = timestamp[:19] + "Z"

            log_data = compressed_data

        return super()._format_output(log_data)
