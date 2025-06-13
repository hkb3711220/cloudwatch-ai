"""Logging System Setup and Configuration

Provides easy setup and configuration utilities for the entire logging system
with sensible defaults for different environments (development, production, testing).

Author: CloudWatch Logs AI Agent Team
License: MIT
"""

import logging
import os
from datetime import timedelta
from pathlib import Path
from typing import Dict, List, Optional, Union

from .structured_logger import StructuredLogger, LogLevel, setup_logging
from .formatters import JSONFormatter, ConsoleFormatter, FileFormatter
from .handlers import (
    RotatingFileHandlerWithContext,
    AsyncFileHandler,
    MetricsHandler,
    CallbackHandler,
)
from .rotation import LogRotationConfig, RotationPolicy, CompressionType, ArchivePolicy
from .debug import get_debug_logger
from .context import LoggingContext


class LoggingEnvironment:
    """Predefined logging environments"""

    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"
    DEBUG = "debug"


class LoggingSetup:
    """Main class for setting up the logging system"""

    def __init__(self, environment: str = LoggingEnvironment.DEVELOPMENT):
        self.environment = environment
        self.loggers = {}
        self.handlers = {}
        self.config = self._get_default_config()

    def _get_default_config(self) -> Dict:
        """Get default configuration based on environment"""
        base_config = {
            "log_dir": "logs",
            "log_filename": "cloudwatch_agent.log",
            "enable_console": True,
            "enable_file": True,
            "enable_metrics": True,
            "enable_rotation": True,
            "enable_debug": False,
            "console_level": LogLevel.INFO,
            "file_level": LogLevel.DEBUG,
            "include_japanese": True,
            "max_file_size": 10 * 1024 * 1024,  # 10MB
            "backup_count": 30,
            "rotation_policy": RotationPolicy.COMBINED,
            "compression_type": CompressionType.GZIP,
            "archive_policy": ArchivePolicy.COMPRESS,
            "delete_after_days": 90,
        }

        if self.environment == LoggingEnvironment.DEVELOPMENT:
            base_config.update(
                {
                    "console_level": LogLevel.DEBUG,
                    "enable_debug": True,
                    "include_japanese": True,
                    "max_file_size": 5 * 1024 * 1024,  # 5MB
                    "backup_count": 10,
                }
            )
        elif self.environment == LoggingEnvironment.PRODUCTION:
            base_config.update(
                {
                    "console_level": LogLevel.WARNING,
                    "file_level": LogLevel.INFO,
                    "enable_debug": False,
                    "max_file_size": 50 * 1024 * 1024,  # 50MB
                    "backup_count": 100,
                    "delete_after_days": 180,
                }
            )
        elif self.environment == LoggingEnvironment.TESTING:
            base_config.update(
                {
                    "console_level": LogLevel.ERROR,
                    "file_level": LogLevel.WARNING,
                    "enable_debug": False,
                    "enable_rotation": False,
                    "backup_count": 5,
                }
            )
        elif self.environment == LoggingEnvironment.DEBUG:
            base_config.update(
                {
                    "console_level": LogLevel.DEBUG,
                    "file_level": LogLevel.DEBUG,
                    "enable_debug": True,
                    "include_japanese": True,
                    "max_file_size": 1 * 1024 * 1024,  # 1MB
                    "backup_count": 5,
                }
            )

        return base_config

    def setup_basic_logging(
        self,
        log_dir: Optional[str] = None,
        log_filename: Optional[str] = None,
        console_level: Optional[LogLevel] = None,
        file_level: Optional[LogLevel] = None,
    ) -> StructuredLogger:
        """Setup basic logging with minimal configuration"""

        # Update config with provided values
        if log_dir:
            self.config["log_dir"] = log_dir
        if log_filename:
            self.config["log_filename"] = log_filename
        if console_level:
            self.config["console_level"] = console_level
        if file_level:
            self.config["file_level"] = file_level

        # Create log directory
        log_path = Path(self.config["log_dir"])
        log_path.mkdir(parents=True, exist_ok=True)

        # Setup structured logging
        setup_logging(
            level=self.config["file_level"],
            include_japanese=self.config["include_japanese"],
        )

        # Get main logger
        logger = StructuredLogger("cloudwatch.agent")

        # Clear existing handlers
        logger.logger.handlers.clear()

        # Add console handler
        if self.config["enable_console"]:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(self.config["console_level"].value[2])
            console_formatter = ConsoleFormatter(
                include_context=True,
                include_japanese=self.config["include_japanese"],
                use_colors=True,
            )
            console_handler.setFormatter(console_formatter)
            logger.logger.addHandler(console_handler)
            self.handlers["console"] = console_handler

        # Add file handler
        if self.config["enable_file"]:
            log_file_path = log_path / self.config["log_filename"]

            if self.config["enable_rotation"]:
                # Create rotation config
                rotation_config = LogRotationConfig(
                    rotation_policy=self.config["rotation_policy"],
                    max_file_size=self.config["max_file_size"],
                    rotation_interval=timedelta(days=1),
                    max_files=self.config["backup_count"],
                    compression_type=self.config["compression_type"],
                    archive_policy=self.config["archive_policy"],
                    delete_after_days=self.config["delete_after_days"],
                )

                file_handler = RotatingFileHandlerWithContext(
                    filename=str(log_file_path), config=rotation_config
                )
            else:
                file_handler = logging.FileHandler(str(log_file_path))

            file_handler.setLevel(self.config["file_level"].value[2])
            file_formatter = FileFormatter(
                include_context=True,
                include_japanese=self.config["include_japanese"],
                compress_data=True,
            )
            file_handler.setFormatter(file_formatter)
            logger.logger.addHandler(file_handler)
            self.handlers["file"] = file_handler

        # Add metrics handler
        if self.config["enable_metrics"]:
            metrics_handler = MetricsHandler(
                retention_period=timedelta(hours=24), bucket_size=timedelta(minutes=1)
            )
            metrics_handler.setLevel(logging.DEBUG)
            logger.logger.addHandler(metrics_handler)
            self.handlers["metrics"] = metrics_handler

        # Store main logger
        self.loggers["main"] = logger

        return logger

    def setup_component_logger(
        self,
        component: str,
        level: Optional[LogLevel] = None,
        separate_file: bool = False,
    ) -> StructuredLogger:
        """Setup logger for a specific component"""

        logger_name = f"cloudwatch.{component}"
        logger = StructuredLogger(logger_name)

        # Use main logger's handlers by default
        if not separate_file and "main" in self.loggers:
            logger.logger.handlers = self.loggers["main"].logger.handlers.copy()
        else:
            # Create separate file if requested
            if separate_file:
                log_path = Path(self.config["log_dir"])
                component_log_file = log_path / f"{component}.log"

                file_handler = RotatingFileHandlerWithContext(
                    filename=str(component_log_file),
                    config=LogRotationConfig(
                        max_file_size=self.config["max_file_size"] // 2,
                        max_files=self.config["backup_count"] // 2,
                    ),
                )

                file_formatter = FileFormatter(
                    include_context=True,
                    include_japanese=self.config["include_japanese"],
                )
                file_handler.setFormatter(file_formatter)
                logger.logger.addHandler(file_handler)

        # Set level
        if level:
            logger.logger.setLevel(level.value[2])

        self.loggers[component] = logger
        return logger

    def setup_debug_logging(self) -> Optional:
        """Setup debug logging if enabled"""
        if not self.config["enable_debug"]:
            return None

        debug_logger = get_debug_logger("main")
        self.loggers["debug"] = debug_logger
        return debug_logger

    def setup_mcp_logging(self) -> StructuredLogger:
        """Setup MCP-specific logging"""
        mcp_logger = self.setup_component_logger(
            "mcp",
            level=(
                LogLevel.DEBUG
                if self.environment == LoggingEnvironment.DEVELOPMENT
                else LogLevel.INFO
            ),
            separate_file=True,
        )

        # Add request tracking
        mcp_logger.enable_operation_tracking = True

        return mcp_logger

    def setup_aws_logging(self) -> StructuredLogger:
        """Setup AWS-specific logging"""
        aws_logger = self.setup_component_logger(
            "aws",
            level=LogLevel.INFO,
            separate_file=self.environment == LoggingEnvironment.DEVELOPMENT,
        )

        # Add AWS-specific context
        aws_logger.default_context = {"service": "cloudwatch-logs", "component": "aws"}

        return aws_logger

    def setup_tools_logging(self) -> StructuredLogger:
        """Setup tools-specific logging"""
        tools_logger = self.setup_component_logger(
            "tools",
            level=(
                LogLevel.DEBUG
                if self.environment == LoggingEnvironment.DEBUG
                else LogLevel.INFO
            ),
            separate_file=False,
        )

        return tools_logger

    def setup_complete_system(self) -> Dict[str, StructuredLogger]:
        """Setup the complete logging system"""
        loggers = {}

        # Main system logger
        loggers["main"] = self.setup_basic_logging()

        # Component loggers
        loggers["mcp"] = self.setup_mcp_logging()
        loggers["aws"] = self.setup_aws_logging()
        loggers["tools"] = self.setup_tools_logging()

        # Debug logger
        debug_logger = self.setup_debug_logging()
        if debug_logger:
            loggers["debug"] = debug_logger

        # Log setup completion
        loggers["main"].info(
            "Logging system setup completed",
            japanese_message="ログシステムのセットアップが完了しました",
            context_data={
                "environment": self.environment,
                "loggers_count": len(loggers),
                "handlers_count": len(self.handlers),
                "log_directory": self.config["log_dir"],
            },
        )

        return loggers

    def add_custom_handler(
        self,
        handler: logging.Handler,
        name: str,
        apply_to_loggers: Optional[List[str]] = None,
    ):
        """Add a custom handler to the system"""
        self.handlers[name] = handler

        # Apply to specified loggers or all
        target_loggers = apply_to_loggers or list(self.loggers.keys())

        for logger_name in target_loggers:
            if logger_name in self.loggers:
                logger = self.loggers[logger_name]
                if hasattr(logger, "logger"):  # StructuredLogger
                    logger.logger.addHandler(handler)
                else:  # Other logger types
                    logger.addHandler(handler)

    def get_logger(self, name: str) -> Optional[StructuredLogger]:
        """Get a logger by name"""
        return self.loggers.get(name)

    def get_handler(self, name: str) -> Optional[logging.Handler]:
        """Get a handler by name"""
        return self.handlers.get(name)

    def get_metrics(self) -> Optional[Dict]:
        """Get metrics from metrics handler"""
        metrics_handler = self.get_handler("metrics")
        if isinstance(metrics_handler, MetricsHandler):
            return metrics_handler.get_metrics()
        return None

    def shutdown(self):
        """Shutdown the logging system gracefully"""
        for logger in self.loggers.values():
            if hasattr(logger, "logger"):
                for handler in logger.logger.handlers:
                    handler.close()

        # Clear collections
        self.loggers.clear()
        self.handlers.clear()


# Convenience functions
def setup_development_logging(log_dir: str = "logs") -> Dict[str, StructuredLogger]:
    """Quick setup for development environment"""
    setup = LoggingSetup(LoggingEnvironment.DEVELOPMENT)
    return setup.setup_complete_system()


def setup_production_logging(
    log_dir: str = "/var/log/cloudwatch-agent",
) -> Dict[str, StructuredLogger]:
    """Quick setup for production environment"""
    setup = LoggingSetup(LoggingEnvironment.PRODUCTION)
    setup.config["log_dir"] = log_dir
    return setup.setup_complete_system()


def setup_testing_logging() -> Dict[str, StructuredLogger]:
    """Quick setup for testing environment"""
    setup = LoggingSetup(LoggingEnvironment.TESTING)
    setup.config["log_dir"] = "test_logs"
    return setup.setup_complete_system()


def setup_custom_logging(
    environment: str = LoggingEnvironment.DEVELOPMENT, **config_overrides
) -> LoggingSetup:
    """Setup custom logging configuration"""
    setup = LoggingSetup(environment)
    setup.config.update(config_overrides)
    return setup
