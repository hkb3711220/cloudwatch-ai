"""Custom Log Handlers

Provides enhanced log handlers with context support, rotation,
async capabilities, and metrics integration.

Author: CloudWatch Logs AI Agent Team
License: MIT
"""

import asyncio
import logging
import logging.handlers
import os
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, List, Callable
import json


class RotatingFileHandlerWithContext(logging.handlers.RotatingFileHandler):
    """Enhanced rotating file handler with context preservation"""

    def __init__(
        self,
        filename: str,
        mode: str = "a",
        maxBytes: int = 0,
        backupCount: int = 0,
        encoding: Optional[str] = None,
        delay: bool = False,
        preserve_context: bool = True,
    ):
        super().__init__(filename, mode, maxBytes, backupCount, encoding, delay)
        self.preserve_context = preserve_context

        # Ensure log directory exists
        log_dir = os.path.dirname(filename)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

    def emit(self, record: logging.LogRecord):
        """Emit a record with context preservation"""
        try:
            if self.preserve_context:
                # Add file-specific context
                if not hasattr(record, "file_handler"):
                    record.file_handler = True
                    record.file_path = self.baseFilename

            super().emit(record)
        except Exception:
            self.handleError(record)

    def doRollover(self):
        """Override rollover to add metadata"""
        super().doRollover()

        # Add metadata to new log file
        if self.stream:
            metadata = {
                "log_rotation": {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "previous_file": f"{self.baseFilename}.1",
                    "reason": "size_limit_exceeded",
                }
            }

            self.stream.write(f"# Log rotation metadata: {json.dumps(metadata)}\n")
            self.stream.flush()


class AsyncFileHandler(logging.Handler):
    """Asynchronous file handler for high-performance logging"""

    def __init__(
        self,
        filename: str,
        maxsize: int = 1000,
        flush_interval: float = 5.0,
        encoding: str = "utf-8",
    ):
        super().__init__()
        self.filename = filename
        self.maxsize = maxsize
        self.flush_interval = flush_interval
        self.encoding = encoding

        # Create log directory if needed
        log_dir = os.path.dirname(filename)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        # Buffer for log records
        self._buffer = deque(maxlen=maxsize)
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

        # Start background writer thread
        self._writer_thread = threading.Thread(target=self._writer_loop, daemon=True)
        self._writer_thread.start()

    def emit(self, record: logging.LogRecord):
        """Add record to buffer"""
        try:
            msg = self.format(record)
            with self._lock:
                self._buffer.append(f"{msg}\n")
        except Exception:
            self.handleError(record)

    def _writer_loop(self):
        """Background writer loop"""
        while not self._stop_event.is_set():
            self._flush_buffer()
            time.sleep(self.flush_interval)

        # Final flush on shutdown
        self._flush_buffer()

    def _flush_buffer(self):
        """Flush buffer to file"""
        if not self._buffer:
            return

        with self._lock:
            records = list(self._buffer)
            self._buffer.clear()

        try:
            with open(self.filename, "a", encoding=self.encoding) as f:
                f.writelines(records)
                f.flush()
        except Exception as e:
            # Re-add records to buffer if write failed
            with self._lock:
                self._buffer.extendleft(reversed(records))
            print(f"AsyncFileHandler write error: {e}")

    def close(self):
        """Close handler and stop background thread"""
        self._stop_event.set()
        if self._writer_thread.is_alive():
            self._writer_thread.join(timeout=self.flush_interval * 2)
        self._flush_buffer()
        super().close()


class MetricsHandler(logging.Handler):
    """Handler for collecting logging metrics and statistics"""

    def __init__(
        self,
        retention_period: timedelta = timedelta(hours=24),
        bucket_size: timedelta = timedelta(minutes=1),
    ):
        super().__init__()
        self.retention_period = retention_period
        self.bucket_size = bucket_size

        # Metrics storage
        self.metrics = {
            "total_logs": 0,
            "logs_by_level": defaultdict(int),
            "logs_by_component": defaultdict(int),
            "logs_by_logger": defaultdict(int),
            "error_count": 0,
            "warning_count": 0,
            "logs_per_minute": defaultdict(int),
            "average_log_size": 0,
            "peak_logs_per_minute": 0,
            "first_log_time": None,
            "last_log_time": None,
        }

        # Time-series data for analysis
        self.time_series = deque()
        self._lock = threading.Lock()

        # Start cleanup thread
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()

    def emit(self, record: logging.LogRecord):
        """Collect metrics from log record"""
        try:
            with self._lock:
                current_time = datetime.utcnow()

                # Update basic metrics
                self.metrics["total_logs"] += 1
                self.metrics["logs_by_level"][record.levelname] += 1
                self.metrics["logs_by_logger"][record.name] += 1

                # Update component metrics if available
                if hasattr(record, "component") and record.component:
                    self.metrics["logs_by_component"][record.component] += 1

                # Update error/warning counts
                if record.levelno >= logging.ERROR:
                    self.metrics["error_count"] += 1
                elif record.levelno >= logging.WARNING:
                    self.metrics["warning_count"] += 1

                # Update timing metrics
                if self.metrics["first_log_time"] is None:
                    self.metrics["first_log_time"] = current_time
                self.metrics["last_log_time"] = current_time

                # Calculate time bucket for per-minute metrics
                time_bucket = current_time.replace(second=0, microsecond=0)
                self.metrics["logs_per_minute"][time_bucket] += 1

                # Update peak logs per minute
                current_minute_count = self.metrics["logs_per_minute"][time_bucket]
                if current_minute_count > self.metrics["peak_logs_per_minute"]:
                    self.metrics["peak_logs_per_minute"] = current_minute_count

                # Update average log size
                message = self.format(record)
                log_size = len(message.encode("utf-8"))
                total_logs = self.metrics["total_logs"]
                current_avg = self.metrics["average_log_size"]
                self.metrics["average_log_size"] = (
                    current_avg * (total_logs - 1) + log_size
                ) / total_logs

                # Add to time series
                self.time_series.append(
                    {
                        "timestamp": current_time,
                        "level": record.levelname,
                        "logger": record.name,
                        "component": getattr(record, "component", None),
                        "size": log_size,
                        "has_exception": record.exc_info is not None,
                    }
                )

        except Exception:
            self.handleError(record)

    def _cleanup_loop(self):
        """Background cleanup of old metrics"""
        while True:
            try:
                current_time = datetime.utcnow()
                cutoff_time = current_time - self.retention_period

                with self._lock:
                    # Clean up per-minute metrics
                    expired_buckets = [
                        bucket
                        for bucket in self.metrics["logs_per_minute"]
                        if bucket < cutoff_time
                    ]
                    for bucket in expired_buckets:
                        del self.metrics["logs_per_minute"][bucket]

                    # Clean up time series data
                    while (
                        self.time_series
                        and self.time_series[0]["timestamp"] < cutoff_time
                    ):
                        self.time_series.popleft()

                # Sleep for cleanup interval (10% of retention period)
                cleanup_interval = self.retention_period.total_seconds() * 0.1
                time.sleep(max(60, cleanup_interval))  # At least 1 minute

            except Exception as e:
                print(f"MetricsHandler cleanup error: {e}")
                time.sleep(300)  # 5 minutes on error

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics snapshot"""
        with self._lock:
            # Convert defaultdict to regular dict for JSON serialization
            metrics_copy = {}
            for key, value in self.metrics.items():
                if isinstance(value, defaultdict):
                    metrics_copy[key] = dict(value)
                elif isinstance(value, datetime):
                    metrics_copy[key] = value.isoformat() + "Z"
                else:
                    metrics_copy[key] = value

            return metrics_copy

    def get_time_series(
        self, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get time series data for analysis"""
        with self._lock:
            filtered_data = []

            for entry in self.time_series:
                timestamp = entry["timestamp"]

                if start_time and timestamp < start_time:
                    continue
                if end_time and timestamp > end_time:
                    continue

                # Convert datetime to string for JSON serialization
                entry_copy = entry.copy()
                entry_copy["timestamp"] = timestamp.isoformat() + "Z"
                filtered_data.append(entry_copy)

            return filtered_data

    def reset_metrics(self):
        """Reset all metrics"""
        with self._lock:
            self.metrics = {
                "total_logs": 0,
                "logs_by_level": defaultdict(int),
                "logs_by_component": defaultdict(int),
                "logs_by_logger": defaultdict(int),
                "error_count": 0,
                "warning_count": 0,
                "logs_per_minute": defaultdict(int),
                "average_log_size": 0,
                "peak_logs_per_minute": 0,
                "first_log_time": None,
                "last_log_time": None,
            }
            self.time_series.clear()


class CallbackHandler(logging.Handler):
    """Handler that calls custom callbacks for log processing"""

    def __init__(
        self, callbacks: Optional[List[Callable[[logging.LogRecord], None]]] = None
    ):
        super().__init__()
        self.callbacks = callbacks or []
        self._lock = threading.Lock()

    def add_callback(self, callback: Callable[[logging.LogRecord], None]):
        """Add a callback function"""
        with self._lock:
            self.callbacks.append(callback)

    def remove_callback(self, callback: Callable[[logging.LogRecord], None]):
        """Remove a callback function"""
        with self._lock:
            if callback in self.callbacks:
                self.callbacks.remove(callback)

    def emit(self, record: logging.LogRecord):
        """Call all registered callbacks"""
        try:
            with self._lock:
                callbacks = self.callbacks.copy()

            for callback in callbacks:
                try:
                    callback(record)
                except Exception as e:
                    print(f"CallbackHandler callback error: {e}")

        except Exception:
            self.handleError(record)
