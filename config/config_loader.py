"""
Configuration File Loader Utility

Provides unified loading for YAML and JSON configuration files with automatic format detection.

Features:
- Automatic format detection based on file extension or content
- Support for both YAML and JSON formats
- Graceful error handling
- Type-safe loading with validation
- Secret reference resolution (secrets://secret_name)
"""

import os
import re
import json
import yaml
import logging
from typing import Dict, Any, Optional, Union
from pathlib import Path

logger = logging.getLogger(__name__)

# Secret reference pattern: secrets://secret_name or secrets://path/to/secret
SECRET_REFERENCE_PATTERN = re.compile(r'^secrets://(.+)$')



def load_config_file(file_path: str) -> Dict[str, Any]:
    """
    Load configuration from YAML or JSON file with automatic format detection.

    Args:
        file_path: Path to the configuration file

    Returns:
        Dict containing the loaded configuration

    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If the file format is unsupported or content is invalid
        Exception: For other parsing errors
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Configuration file not found: {file_path}")

    file_extension = Path(file_path).suffix.lower()

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            if file_extension == '.json':
                return json.load(f)
            elif file_extension in ['.yaml', '.yml']:
                data = yaml.safe_load(f)
                if data is None:
                    raise ValueError("Configuration file is empty")
                return data
            else:
                # Try to detect format from content
                content = f.read()
                f.seek(0)  # Reset file pointer

                # Try JSON first
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    pass

                # Try YAML
                try:
                    data = yaml.safe_load(content)
                    if data is None:
                        raise ValueError("Configuration file is empty")
                    return data
                except yaml.YAMLError:
                    pass

                raise ValueError(f"Unsupported configuration file format: {file_path}")

    except Exception as e:
        logger.error(f"Failed to load configuration file {file_path}: {e}")
        raise


def find_config_file(base_name: str, search_paths: Optional[list] = None) -> Optional[str]:
    """
    Find a configuration file by trying different extensions and locations.

    Args:
        base_name: Base name of the config file (without extension)
        search_paths: List of directories to search in. If None, uses default paths.

    Returns:
        Path to the found config file, or None if not found
    """
    if search_paths is None:
        search_paths = ['config', '']

    extensions = ['.yaml', '.yml', '.json']

    for search_path in search_paths:
        for ext in extensions:
            candidate = os.path.join(search_path, f"{base_name}{ext}")
            if os.path.exists(candidate):
                logger.info(f"Found configuration file: {candidate}")
                return candidate

    return None


def save_config_file(file_path: str, config: Dict[str, Any], format: Optional[str] = None) -> None:
    """
    Save configuration to a file in YAML or JSON format.

    Args:
        file_path: Path where to save the configuration
        config: Configuration dictionary to save
        format: Format to use ('yaml', 'json', or None for auto-detection from extension)
    """
    if format is None:
        ext = Path(file_path).suffix.lower()
        if ext == '.json':
            format = 'json'
        else:
            format = 'yaml'

    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, 'w', encoding='utf-8') as f:
        if format == 'json':
            json.dump(config, f, indent=2, ensure_ascii=False)
        elif format == 'yaml':
            yaml.safe_dump(config, f, default_flow_style=False, allow_unicode=True)
        else:
            raise ValueError(f"Unsupported format: {format}")

    logger.info(f"Saved configuration to {file_path}")


def _is_secret_reference(value: Any) -> bool:
    """Check if a value is a secrets:// reference."""
    if not isinstance(value, str):
        return False
    return SECRET_REFERENCE_PATTERN.match(value) is not None


def _resolve_single_secret(value: str, adapter: Any = None) -> str:
    """
    Resolve a single secrets:// reference to its actual value.
    
    Args:
        value: The secrets:// reference string
        adapter: Optional SecretsAdapter instance
        
    Returns:
        The resolved secret value
        
    Raises:
        ValueError: If secret cannot be resolved
    """
    match = SECRET_REFERENCE_PATTERN.match(value)
    if not match:
        return value
    
    secret_name = match.group(1)
    
    # Get adapter if not provided
    if adapter is None:
        try:
            from security.secrets_adapter import get_adapter
            adapter = get_adapter()
        except ImportError:
            # Fallback to os.environ if security module not available
            logger.warning("security.secrets_adapter not available, using os.environ")
            resolved = os.environ.get(secret_name)
            if resolved is None:
                raise ValueError(f"Secret '{secret_name}' not found in environment")
            return resolved
    
    resolved = adapter.get_secret(secret_name)
    if resolved is None:
        raise ValueError(f"Secret '{secret_name}' not found")
    
    return resolved


def resolve_secret_references(
    config: Dict[str, Any],
    adapter: Any = None,
    raise_on_missing: bool = True
) -> Dict[str, Any]:
    """
    Recursively resolve all secrets:// references in a configuration dictionary.
    
    Args:
        config: Configuration dictionary potentially containing secrets:// references
        adapter: Optional SecretsAdapter instance to use for resolution
        raise_on_missing: If True, raise ValueError for missing secrets.
                         If False, leave unresolved references as-is.
        
    Returns:
        Configuration dictionary with secrets resolved
        
    Example:
        config = {
            "database": {
                "password": "secrets://db_password"
            },
            "api_key": "secrets://api_key"
        }
        resolved = resolve_secret_references(config)
        # Returns:
        # {
        #     "database": {"password": "actual_password"},
        #     "api_key": "actual_api_key"
        # }
    """
    def _resolve_value(value: Any) -> Any:
        if isinstance(value, str) and _is_secret_reference(value):
            try:
                return _resolve_single_secret(value, adapter)
            except ValueError as e:
                if raise_on_missing:
                    raise
                logger.warning(f"Could not resolve secret reference: {e}")
                return value
        elif isinstance(value, dict):
            return {k: _resolve_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [_resolve_value(item) for item in value]
        else:
            return value
    
    return _resolve_value(config)


def load_config_with_secrets(
    file_path: str,
    adapter: Any = None,
    raise_on_missing: bool = True
) -> Dict[str, Any]:
    """
    Load configuration from file and resolve all secrets:// references.
    
    This is a convenience function that combines load_config_file() and
    resolve_secret_references().
    
    Args:
        file_path: Path to the configuration file
        adapter: Optional SecretsAdapter instance
        raise_on_missing: If True, raise ValueError for missing secrets
        
    Returns:
        Configuration dictionary with secrets resolved
        
    Example:
        # config.yaml:
        # api:
        #   key: secrets://API_KEY
        #   url: https://api.example.com
        
        config = load_config_with_secrets("config.yaml")
        print(config["api"]["key"])  # Prints the actual API key
    """
    config = load_config_file(file_path)
    return resolve_secret_references(config, adapter, raise_on_missing)
