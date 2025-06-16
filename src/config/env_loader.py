"""
Environment variable loader for CloudWatch Log Agent.

This module provides utilities to load environment variables from .env files
and support different environment profiles (dev, test, prod).

Environment Variable Priority (highest to lowest):
1. External environment variables (e.g., from MCP server env section)
2. .env.{profile} files (profile-specific settings)
3. .env files (local overrides)
4. .env.cloudwatch files (base configuration)

External environment variables are never overridden by .env files.
"""

import os
import logging
from pathlib import Path
from typing import Dict, Optional, List, Union

logger = logging.getLogger(__name__)


class EnvLoader:
    """
    Environment variable loader with support for .env files and profiles.
    """

    def __init__(self, project_root: Optional[Union[str, Path]] = None):
        """
        Initialize the environment loader.

        Args:
            project_root: Root directory of the project. If None, auto-detect.
        """
        if project_root is None:
            # Auto-detect project root by looking for common files
            current_dir = Path(__file__).parent
            while current_dir != current_dir.parent:
                if (current_dir / ".env.cloudwatch").exists() or (
                    current_dir / "requirements.txt"
                ).exists():
                    project_root = current_dir
                    break
                current_dir = current_dir.parent
            else:
                project_root = Path.cwd()

        self.project_root = Path(project_root)
        self.loaded_files: List[Path] = []
        self.env_vars: Dict[str, str] = {}

    def load_env_file(self, file_path: Union[str, Path], override: bool = True) -> bool:
        """
        Load environment variables from a .env file.

        Args:
            file_path: Path to the .env file
            override: Whether to override existing environment variables

        Returns:
            True if file was loaded successfully, False otherwise
        """
        file_path = Path(file_path)

        # Make path relative to project root if it's not absolute
        if not file_path.is_absolute():
            file_path = self.project_root / file_path

        if not file_path.exists():
            logger.warning(f"Environment file not found: {file_path}")
            return False

        try:
            loaded_count = 0
            with open(file_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()

                    # Skip empty lines and comments
                    if not line or line.startswith("#"):
                        continue

                    # Parse key=value pairs
                    if "=" not in line:
                        logger.warning(
                            f"Invalid line {line_num} in {file_path}: {line}"
                        )
                        continue

                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()

                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]

                    # Set environment variable
                    if override or key not in os.environ:
                        os.environ[key] = value
                        self.env_vars[key] = value
                        loaded_count += 1

            self.loaded_files.append(file_path)
            logger.info(f"Loaded {loaded_count} environment variables from {file_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to load environment file {file_path}: {e}")
            return False

    def load_profile_env(self, profile: str = "default") -> bool:
        """
        Load environment variables for a specific profile.

        Profiles are loaded in this order (with proper priority):
        1. .env.cloudwatch (base configuration) - lowest priority
        2. .env (local overrides) - medium priority
        3. .env.{profile} (profile-specific settings) - higher priority
        4. External environment variables (e.g., from MCP) - highest priority (never overridden)

        Args:
            profile: Environment profile name (dev, test, prod, etc.)

        Returns:
            True if at least one file was loaded successfully
        """
        files_to_load = [
            ".env.cloudwatch",  # Base configuration
            ".env",  # Local overrides
        ]

        # Add profile-specific file if not default
        if profile != "default":
            files_to_load.append(f".env.{profile}")

        loaded_any = False
        for env_file in files_to_load:
            # Use override=False to respect external environment variables
            if self.load_env_file(env_file, override=False):
                loaded_any = True

        if loaded_any:
            logger.info(f"Environment profile '{profile}' loaded successfully")
        else:
            logger.warning(f"No environment files found for profile '{profile}'")

        return loaded_any

    def reload(self) -> bool:
        """
        Reload all previously loaded environment files.

        Returns:
            True if all files were reloaded successfully
        """
        if not self.loaded_files:
            logger.warning("No environment files to reload")
            return False

        files_to_reload = self.loaded_files.copy()
        self.loaded_files.clear()
        self.env_vars.clear()

        success = True
        for file_path in files_to_reload:
            if not self.load_env_file(file_path):
                success = False

        if success:
            logger.info("All environment files reloaded successfully")
        else:
            logger.warning("Some environment files failed to reload")

        return success

    def get_loaded_variables(self) -> Dict[str, str]:
        """
        Get all environment variables loaded by this loader.

        Returns:
            Dictionary of loaded environment variables
        """
        return self.env_vars.copy()

    def validate_required_vars(self, required_vars: List[str]) -> Dict[str, bool]:
        """
        Validate that required environment variables are set.

        Args:
            required_vars: List of required environment variable names

        Returns:
            Dictionary mapping variable names to whether they are set
        """
        validation_results = {}
        missing_vars = []

        for var in required_vars:
            is_set = bool(os.getenv(var))
            validation_results[var] = is_set
            if not is_set:
                missing_vars.append(var)

        if missing_vars:
            logger.warning(
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )
        else:
            logger.info(
                f"All required environment variables are set: {', '.join(required_vars)}"
            )

        return validation_results

    def export_current_env(
        self, output_file: Union[str, Path], include_system_vars: bool = False
    ) -> bool:
        """
        Export current environment variables to a .env file.

        Args:
            output_file: Path to output .env file
            include_system_vars: Whether to include system environment variables

        Returns:
            True if export was successful
        """
        output_file = Path(output_file)

        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write("# CloudWatch Log Agent Environment Variables\n")
                f.write(f"# Generated automatically\n\n")

                # Write loaded variables
                if self.env_vars:
                    f.write("# Variables loaded from .env files\n")
                    for key, value in sorted(self.env_vars.items()):
                        # Quote values with spaces
                        if " " in value:
                            value = f'"{value}"'
                        f.write(f"{key}={value}\n")
                    f.write("\n")

                # Write system variables if requested
                if include_system_vars:
                    f.write("# System environment variables\n")
                    for key, value in sorted(os.environ.items()):
                        if key not in self.env_vars:
                            # Only include relevant variables
                            if any(
                                prefix in key
                                for prefix in ["AWS_", "OPENAI_", "ANTHROPIC_", "LOG_"]
                            ):
                                if " " in value:
                                    value = f'"{value}"'
                                f.write(f"{key}={value}\n")

            logger.info(f"Environment variables exported to {output_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to export environment variables: {e}")
            return False


# Global loader instance
_global_loader: Optional[EnvLoader] = None


def get_env_loader() -> EnvLoader:
    """
    Get the global environment loader instance.

    Returns:
        Global EnvLoader instance
    """
    global _global_loader
    if _global_loader is None:
        _global_loader = EnvLoader()
    return _global_loader


def load_environment(
    profile: str = "default", project_root: Optional[str] = None
) -> bool:
    """
    Convenience function to load environment variables.

    Args:
        profile: Environment profile to load
        project_root: Project root directory

    Returns:
        True if environment was loaded successfully
    """
    global _global_loader
    _global_loader = EnvLoader(project_root)
    return _global_loader.load_profile_env(profile)


def reload_environment() -> bool:
    """
    Reload environment variables from previously loaded files.

    Returns:
        True if reload was successful
    """
    loader = get_env_loader()
    return loader.reload()


def validate_environment(required_vars: Optional[List[str]] = None) -> Dict[str, bool]:
    """
    Validate the current environment configuration.

    Args:
        required_vars: List of required variables. If None, use default set.

    Returns:
        Dictionary mapping variable names to whether they are set
    """
    if required_vars is None:
        # Default required variables for CloudWatch Log Agent
        required_vars = [
            "AWS_DEFAULT_REGION",  # or AWS_REGION
            # At least one AI API key
        ]

        # Check if AWS region is set (either variable)
        aws_region_set = bool(
            os.getenv("AWS_DEFAULT_REGION") or os.getenv("AWS_REGION")
        )

        # Check if at least one AI API key is set
        ai_keys = [
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "AZURE_OPENAI_API_KEY",
            "GOOGLE_API_KEY",
        ]
        ai_key_set = any(os.getenv(key) for key in ai_keys)

        results = {"AWS_REGION": aws_region_set, "AI_API_KEY": ai_key_set}

        return results

    loader = get_env_loader()
    return loader.validate_required_vars(required_vars)


# Auto-load environment on module import
def _auto_load_environment():
    """Automatically load environment variables when module is imported."""
    try:
        load_environment()
    except Exception as e:
        logger.debug(
            f"Auto-load of environment failed (this is normal if no .env files exist): {e}"
        )


# Auto-load when module is imported
_auto_load_environment()
