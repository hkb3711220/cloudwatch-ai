"""
Configuration settings for the CloudWatch Logs AI Agent.

This module manages configuration settings including AWS credentials,
region settings, and investigation parameters using environment variables.
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional

# Import environment loader to ensure .env files are loaded
try:
    from .env_loader import load_environment, validate_environment
except ImportError:
    try:
        from src.config.env_loader import load_environment, validate_environment
    except ImportError:
        print("Warning: Could not import env_loader. Using minimal configuration.")

        def load_environment(profile="default"):
            pass

        def validate_environment():
            return {}


@dataclass
class AWSConfig:
    """AWS configuration settings."""

    region_name: Optional[str] = None
    profile_name: Optional[str] = None
    access_key_id: Optional[str] = None
    secret_access_key: Optional[str] = None

    @classmethod
    def from_environment(cls) -> "AWSConfig":
        """Create AWS config from environment variables."""
        return cls(
            region_name=os.getenv("AWS_DEFAULT_REGION", os.getenv("AWS_REGION")),
            profile_name=os.getenv("AWS_PROFILE"),
            access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        )


@dataclass
class LoggingConfig:
    """Logging configuration for the application."""

    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    @classmethod
    def from_environment(cls) -> "LoggingConfig":
        """Create logging config from environment variables."""
        return cls(
            level=os.getenv("LOG_LEVEL", "INFO").upper(),
            format=os.getenv(
                "LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            ),
        )


class Settings:
    """Main settings class that aggregates all configuration."""

    def __init__(self, env_profile: str = "default"):
        # Ensure environment variables are loaded
        load_environment(env_profile)

        self.aws = AWSConfig.from_environment()
        self.logging = LoggingConfig.from_environment()

        # Initialize logging
        self._setup_logging()

    def _setup_logging(self):
        """Setup logging configuration."""
        logging.basicConfig(
            level=getattr(logging, self.logging.level), format=self.logging.format
        )

        # Reduce boto3/botocore log level to WARNING to avoid spam
        logging.getLogger("boto3").setLevel(logging.WARNING)
        logging.getLogger("botocore").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)

    def validate_aws_config(self) -> bool:
        """
        Validate AWS configuration.

        Returns:
            True if AWS configuration is valid, False otherwise
        """
        # Check if we have either profile or access keys
        has_profile = bool(self.aws.profile_name)
        has_keys = bool(self.aws.access_key_id and self.aws.secret_access_key)

        if not (has_profile or has_keys):
            logging.warning(
                "No AWS credentials found. Please set AWS_PROFILE or "
                "AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY environment variables, "
                "or configure AWS CLI."
            )
            return False

        if not self.aws.region_name:
            logging.warning(
                "No AWS region specified. Please set AWS_DEFAULT_REGION or "
                "AWS_REGION environment variable."
            )
            return False

        return True

    def reload(self, env_profile: str = "default"):
        """
        Reload all configuration from environment variables.

        Args:
            env_profile: Environment profile to reload
        """
        from .env_loader import reload_environment

        # Reload environment files
        reload_environment()

        # Reload configuration objects
        self.aws = AWSConfig.from_environment()
        self.logging = LoggingConfig.from_environment()
        self._setup_logging()

    def validate(self) -> dict:
        """
        Validate the current configuration.

        Returns:
            Dictionary with validation results
        """
        validation_results = validate_environment()

        # Additional validation
        validation_results["aws_credentials"] = bool(
            self.aws.access_key_id
            or os.getenv("AWS_PROFILE")
            or os.getenv("AWS_ROLE_ARN")
        )

        validation_results["aws_region"] = bool(self.aws.region_name)

        return validation_results


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get the global settings instance."""
    return settings


def reload_settings(env_profile: str = "default") -> Settings:
    """
    Reload settings from environment variables.

    Args:
        env_profile: Environment profile to reload

    Returns:
        Updated global settings instance
    """
    global settings
    # Create a new settings instance to ensure fresh configuration
    settings = Settings(env_profile)
    return settings


def validate_settings() -> dict:
    """
    Validate the current settings configuration.

    Returns:
        Dictionary with validation results
    """
    return settings.validate()
