"""
Configuration Utilities with Environment Variable Support

Provides utilities for loading and processing configuration files with environment
variable substitution. Supports placeholders like ${VAR_NAME} in YAML/JSON configs.

Features:
- Load YAML/JSON configuration files
- Substitute environment variables in config values
- Support for default values: ${VAR_NAME:default_value}
- Type conversion for numeric and boolean values
- Recursive processing of nested dictionaries and lists
"""

import os
import re
import logging
import yaml
import json
from typing import Dict, Any, Optional, Union
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigLoader:
    """
    Loads and processes configuration files with environment variable substitution.

    Supports placeholders in the format ${VAR_NAME} or ${VAR_NAME:default_value}.
    """

    # Regex pattern to match environment variable placeholders
    ENV_VAR_PATTERN = re.compile(r'\$\{([^}]+)\}')

    @classmethod
    def load_yaml(cls, path: Union[str, Path]) -> Dict[str, Any]:
        """
        Load YAML configuration file with environment variable substitution.

        Args:
            path: Path to YAML file

        Returns:
            Processed configuration dictionary

        Raises:
            FileNotFoundError: If file doesn't exist
            yaml.YAMLError: If YAML parsing fails
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        if data is None:
            raise ValueError(f"Configuration file is empty: {path}")

        return cls._process_env_vars(data)

    @classmethod
    def load_json(cls, path: Union[str, Path]) -> Dict[str, Any]:
        """
        Load JSON configuration file with environment variable substitution.

        Args:
            path: Path to JSON file

        Returns:
            Processed configuration dictionary

        Raises:
            FileNotFoundError: If file doesn't exist
            json.JSONDecodeError: If JSON parsing fails
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return cls._process_env_vars(data)

    @classmethod
    def load_config(cls, path: Union[str, Path]) -> Dict[str, Any]:
        """
        Load configuration file (YAML or JSON) with environment variable substitution.

        Auto-detects format based on file extension.

        Args:
            path: Path to configuration file

        Returns:
            Processed configuration dictionary

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is unsupported
        """
        path = Path(path)

        if path.suffix.lower() in ['.yaml', '.yml']:
            return cls.load_yaml(path)
        elif path.suffix.lower() == '.json':
            return cls.load_json(path)
        else:
            raise ValueError(f"Unsupported configuration file format: {path.suffix}")

    @classmethod
    def _process_env_vars(cls, data: Any) -> Any:
        """
        Recursively process data structure and substitute environment variables.

        Args:
            data: Data structure to process (dict, list, str, etc.)

        Returns:
            Processed data with environment variables substituted
        """
        if isinstance(data, dict):
            return {key: cls._process_env_vars(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [cls._process_env_vars(item) for item in data]
        elif isinstance(data, str):
            return cls._substitute_env_var(data)
        else:
            # Return other types (int, float, bool, None) as-is
            return data

    @classmethod
    def _substitute_env_var(cls, value: str) -> Union[str, int, float, bool]:
        """
        Substitute environment variable placeholders in a string value.

        Supports formats:
        - ${VAR_NAME} - Required variable
        - ${VAR_NAME:default} - Variable with default value

        Also supports type conversion for numeric and boolean values.

        Args:
            value: String value that may contain environment variable placeholders

        Returns:
            Processed value with substitutions applied

        Raises:
            ValueError: If required environment variable is not set
        """
        def replace_match(match):
            var_expr = match.group(1)

            # Check for default value syntax: VAR_NAME:default_value
            if ':' in var_expr:
                var_name, default_value = var_expr.split(':', 1)
                var_name = var_name.strip()
                default_value = default_value.strip()
            else:
                var_name = var_expr.strip()
                default_value = None

            # Get environment variable value
            env_value = os.getenv(var_name)

            if env_value is None:
                if default_value is None:
                    raise ValueError(f"Required environment variable not set: {var_name}")
                env_value = default_value

            # Type conversion for common types
            converted_value = cls._convert_value(env_value)

            # For string interpolation, we need to convert back to string
            # Only return the converted type if this is a standalone variable
            return str(converted_value)

        # Apply all substitutions (all converted to strings for interpolation)
        result = cls.ENV_VAR_PATTERN.sub(replace_match, value)

        # If the entire original value was just a single variable substitution,
        # return the converted type. Otherwise, return the interpolated string.
        if cls.ENV_VAR_PATTERN.fullmatch(value):
            # The result is a string representation of the converted value
            return cls._convert_value(result)
        else:
            # This was a complex string with substitutions, return as string
            return result

    @classmethod
    def _convert_value(cls, value: str) -> Union[str, int, float, bool]:
        """
        Convert string value to appropriate type.

        Attempts to convert to int, float, or bool based on value format.

        Args:
            value: String value to convert

        Returns:
            Converted value (int, float, bool, or str)
        """
        # Try boolean conversion first
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'

        # Try integer conversion
        try:
            # Check if it's a valid integer (not float)
            if '.' not in value and 'e' not in value.lower():
                return int(value)
        except ValueError:
            pass

        # Try float conversion
        try:
            return float(value)
        except ValueError:
            pass

        # Return as string if no conversion possible
        return value


def load_config_with_env_vars(path: Union[str, Path],
                             fallback_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Load configuration file with environment variable substitution and fallback.

    Args:
        path: Path to configuration file
        fallback_data: Fallback data to use if file doesn't exist

    Returns:
        Processed configuration dictionary

    Raises:
        FileNotFoundError: If file doesn't exist and no fallback provided
    """
    try:
        return ConfigLoader.load_config(path)
    except FileNotFoundError:
        if fallback_data is not None:
            logger.warning(f"Configuration file not found: {path}, using fallback data")
            return ConfigLoader._process_env_vars(fallback_data)
        else:
            raise


# Convenience functions for backward compatibility
def load_yaml_config(path: Union[str, Path]) -> Dict[str, Any]:
    """Load YAML configuration with environment variable support."""
    return ConfigLoader.load_yaml(path)


def load_json_config(path: Union[str, Path]) -> Dict[str, Any]:
    """Load JSON configuration with environment variable support."""
    return ConfigLoader.load_json(path)