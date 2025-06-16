"""Simplified MCP Server Configuration Management

Direct CloudWatch integration configuration without AI Agent complexity.
"""

import logging
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, Union, List
from enum import Enum

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    # Pydantic v2
    from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator
    from pydantic_settings import BaseSettings, SettingsConfigDict

    PYDANTIC_V2 = True
except ImportError:
    # Pydantic v1 (fallback)
    from pydantic import (
        BaseSettings,
        BaseModel,
        Field,
        validator,
        SecretStr,
        root_validator,
    )

    PYDANTIC_V2 = False

# Try to import existing settings with fallback
try:
    from ..config.settings import Settings

    LEGACY_SETTINGS_AVAILABLE = True
except ImportError:
    LEGACY_SETTINGS_AVAILABLE = False

logger = logging.getLogger(__name__)


class LogLevel(str, Enum):
    """Supported logging levels"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class TransportType(str, Enum):
    """MCP transport types"""

    STDIO = "stdio"
    SSE = "sse"
    HTTP = "streamable-http"


class AWSCredentialsConfig(BaseModel):
    """AWS credentials and configuration"""

    region: str = Field(default="us-east-1", description="AWS region")
    profile: Optional[str] = Field(
        default=None, description="AWS profile name")
    access_key_id: Optional[SecretStr] = Field(
        default=None, description="AWS access key ID"
    )
    secret_access_key: Optional[SecretStr] = Field(
        default=None, description="AWS secret access key"
    )
    session_token: Optional[SecretStr] = Field(
        default=None, description="AWS session token"
    )

    @classmethod
    def from_environment(cls) -> "AWSCredentialsConfig":
        """Create AWS config from environment variables

        Reads from standard AWS environment variables:
        - AWS_PROFILE
        - AWS_REGION / AWS_DEFAULT_REGION
        - AWS_ACCESS_KEY_ID
        - AWS_SECRET_ACCESS_KEY
        - AWS_SESSION_TOKEN
        """
        import os

        # Read environment variables
        profile = os.getenv("AWS_PROFILE")
        region = (
            os.getenv("AWS_REGION") or os.getenv(
                "AWS_DEFAULT_REGION") or "us-east-1"
        )
        access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        session_token = os.getenv("AWS_SESSION_TOKEN")

        # Log what we found (without secrets)
        logger.debug(f"Environment AWS_PROFILE: {profile or 'not set'}")
        logger.debug(f"Environment AWS_REGION: {region}")
        logger.debug(
            f"Environment AWS_ACCESS_KEY_ID: {'set' if access_key_id else 'not set'}"
        )
        logger.debug(
            f"Environment AWS_SECRET_ACCESS_KEY: {'set' if secret_access_key else 'not set'}"
        )
        logger.debug(
            f"Environment AWS_SESSION_TOKEN: {'set' if session_token else 'not set'}"
        )

        return cls(
            region=region,
            profile=profile,
            access_key_id=SecretStr(access_key_id) if access_key_id else None,
            secret_access_key=(
                SecretStr(secret_access_key) if secret_access_key else None
            ),
            session_token=SecretStr(session_token) if session_token else None,
        )

    if PYDANTIC_V2:

        @field_validator("region")
        @classmethod
        def validate_region(cls, v):
            """Validate AWS region format"""
            if not isinstance(v, str) or len(v) < 3:
                raise ValueError("Invalid AWS region format")
            # Basic AWS region validation
            import re

            if not re.match(r"^[a-z]{2}-[a-z]+-\d+$", v):
                raise ValueError("Invalid AWS region format")
            return v

    else:

        @validator("region")
        def validate_region(cls, v):
            """Validate AWS region format"""
            if not isinstance(v, str) or len(v) < 3:
                raise ValueError("Invalid AWS region format")
            import re

            if not re.match(r"^[a-z]{2}-[a-z]+-\d+$", v):
                raise ValueError("Invalid AWS region format")
            return v

    def is_configured(self) -> bool:
        """Check if AWS credentials are configured"""
        return self.profile is not None or (
            self.access_key_id is not None and self.secret_access_key is not None
        )


class ServerConfig(BaseModel):
    """MCP server configuration"""

    name: str = Field(default="CloudWatch Logs MCP Server",
                      description="Server name")
    version: str = Field(default="0.3.0", description="Server version")
    transport: TransportType = Field(
        default=TransportType.STDIO, description="Transport protocol"
    )
    host: str = Field(default="localhost", description="Server host")
    port: int = Field(default=8000, description="Server port")

    # Note: Performance and development settings removed as they were not used in the codebase

    if PYDANTIC_V2:

        @field_validator("port")
        @classmethod
        def validate_port(cls, v):
            """Validate port range"""
            if not 1 <= v <= 65535:
                raise ValueError("Port must be between 1 and 65535")
            return v

    else:

        @validator("port")
        def validate_port(cls, v):
            """Validate port range"""
            if not 1 <= v <= 65535:
                raise ValueError("Port must be between 1 and 65535")
            return v


class MCPConfig(BaseSettings):
    """Main MCP configuration class for direct CloudWatch integration"""

    # Logging configuration
    log_level: LogLevel = Field(
        default=LogLevel.INFO, description="Logging level")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format string",
    )

    # Configuration sections
    server: ServerConfig = Field(default_factory=ServerConfig)
    aws: AWSCredentialsConfig = Field(default_factory=AWSCredentialsConfig)

    if PYDANTIC_V2:
        model_config = SettingsConfigDict(
            env_prefix="MCP_",
            case_sensitive=False,
            env_nested_delimiter="__",
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore",
        )
    else:

        class Config:
            env_prefix = "MCP_"
            case_sensitive = False
            env_nested_delimiter = "__"
            env_file = ".env"
            env_file_encoding = "utf-8"
            extra = "ignore"

    def validate_configuration(self) -> List[str]:
        """Validate configuration and return list of issues"""
        issues = []

        # Check AWS configuration
        if not self.aws.is_configured():
            issues.append(
                "AWS credentials not configured (profile or access keys required)"
            )

        # Check server configuration
        if not self.server.name:
            issues.append("Server name cannot be empty")

        # Check logging configuration
        if not self.log_format:
            issues.append("Log format cannot be empty")

        return issues

    def setup_logging(self) -> None:
        """Setup logging based on configuration"""
        logging.basicConfig(
            level=getattr(logging, self.log_level.value),
            format=self.log_format,
            force=True,
        )

        # Set specific loggers
        logging.getLogger("boto3").setLevel(logging.WARNING)
        logging.getLogger("botocore").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)

        logger.info(f"Logging configured: {self.log_level.value}")

    def to_dict(self, include_secrets: bool = False) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        if PYDANTIC_V2:
            config_dict = self.model_dump()
        else:
            config_dict = self.dict()

        if not include_secrets:
            # Remove secrets from AWS config
            if "aws" in config_dict:
                for key in ["access_key_id", "secret_access_key", "session_token"]:
                    if key in config_dict["aws"]:
                        config_dict["aws"][key] = (
                            "***" if config_dict["aws"][key] else None
                        )

        return config_dict

    def save_to_file(self, filepath: str) -> None:
        """Save configuration to file"""
        config_dict = self.to_dict(include_secrets=False)

        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)

        logger.info(f"Configuration saved to {filepath}")


def load_config(
    config_file: Optional[str] = None, env_file: Optional[str] = None
) -> MCPConfig:
    """Load configuration from environment and files

    Priority order:
    1. Environment variables
    2. .env file (if exists)
    3. Config file (if provided)
    4. Defaults

    Args:
        config_file: Path to JSON config file (optional)
        env_file: Path to .env file (optional, defaults to .env)

    Returns:
        MCPConfig instance
    """

    logger.debug("Loading MCP configuration")

    # Load .env file if available
    if load_dotenv is not None:
        env_path = env_file or ".env"
        if Path(env_path).exists():
            load_dotenv(env_path, override=False)
            logger.debug(f"Loaded environment from {env_path}")

    # Create base config from environment variables
    config = MCPConfig()

    # Load AWS configuration from environment
    aws_config = AWSCredentialsConfig.from_environment()
    config.aws = aws_config

    # Override with config file if provided
    if config_file and Path(config_file).exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                file_config = json.load(f)

            # Update config with file values
            if PYDANTIC_V2:
                config = MCPConfig.model_validate(
                    {**config.model_dump(), **file_config}
                )
            else:
                config = MCPConfig.parse_obj({**config.dict(), **file_config})

            logger.debug(f"Configuration loaded from {config_file}")

        except Exception as e:
            logger.warning(f"Failed to load config file {config_file}: {e}")

    # Validate configuration
    issues = config.validate_configuration()
    if issues:
        logger.warning(f"Configuration issues found: {', '.join(issues)}")

    logger.info("MCP configuration loaded successfully")
    logger.debug(f"AWS Region: {config.aws.region}")
    logger.debug(f"AWS Profile: {config.aws.profile}")

    return config


def create_default_config_file(filepath: str) -> None:
    """Create a default configuration file"""

    default_config = MCPConfig()
    default_config.save_to_file(filepath)

    logger.info(f"Default configuration file created: {filepath}")


# Global config instance
_global_config: Optional[MCPConfig] = None


def get_config() -> MCPConfig:
    """Get global configuration instance"""
    global _global_config

    if _global_config is None:
        _global_config = load_config()

    return _global_config
