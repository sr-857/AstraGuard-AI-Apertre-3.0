"""
DDoS Protection Configuration Loader

Loads and manages DDoS protection configuration from YAML files
and environment variables.
"""

import os
import yaml
from typing import Dict, Any, Optional, Set
from pathlib import Path
from security.ddos_protection import DDoSConfig


class DDoSConfigLoader:
    """Loads DDoS protection configuration from YAML files."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration loader.
        
        Args:
            config_path: Path to DDoS configuration YAML file
        """
        if config_path is None:
            # Try to find config file in common locations
            possible_paths = [
                "config/ddos_protection.yaml",
                "src/config/ddos_protection.yaml",
                "../config/ddos_protection.yaml",
                os.path.join(os.path.dirname(__file__), "../../config/ddos_protection.yaml")
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    config_path = path
                    break
        
        self.config_path = config_path
        self._config_data: Optional[Dict[str, Any]] = None
    
    def load_config(self) -> DDoSConfig:
        """
        Load DDoS configuration from YAML file and environment variables.
        
        Returns:
            DDoSConfig instance with loaded settings
        """
        # Load from YAML
        if self.config_path and os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    self._config_data = yaml.safe_load(f)
            except Exception as e:
                print(f"Warning: Failed to load DDoS config from {self.config_path}: {e}")
                self._config_data = {}
        else:
            print(f"Warning: DDoS config file not found at {self.config_path}, using defaults")
            self._config_data = {}
        
        # Get environment-specific config
        env = os.getenv("ENVIRONMENT", "development").lower()
        base_config = self._config_data.get("ddos_protection", {})
        env_overrides = self._config_data.get("environments", {}).get(env, {}).get("ddos_protection", {})
        
        # Merge configs (environment overrides base)
        config = self._merge_configs(base_config, env_overrides)
        
        # Apply environment variable overrides
        config = self._apply_env_overrides(config)
        
        # Build DDoSConfig object
        return self._build_ddos_config(config)
    
    def _merge_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge two config dictionaries."""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _apply_env_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides to config."""
        # Check for common environment variable overrides
        env_mappings = {
            "DDOS_ENABLED": ("enabled", lambda x: x.lower() == "true"),
            "DDOS_MAX_REQUESTS_PER_SECOND": ("rate_limiting.max_requests_per_second", int),
            "DDOS_MAX_REQUESTS_PER_MINUTE": ("rate_limiting.max_requests_per_minute", int),
            "DDOS_MAX_CONNECTIONS_PER_IP": ("connection_limits.max_concurrent_per_ip", int),
            "DDOS_AUTO_BLOCK_THRESHOLD": ("ip_blocking.auto_block_threshold", float),
            "DDOS_BLOCK_DURATION": ("ip_blocking.block_duration_seconds", int),
        }
        
        for env_var, (config_path, converter) in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                try:
                    converted_value = converter(value)
                    self._set_nested_value(config, config_path, converted_value)
                except (ValueError, TypeError) as e:
                    print(f"Warning: Invalid value for {env_var}: {value} ({e})")
        
        return config
    
    def _set_nested_value(self, config: Dict[str, Any], path: str, value: Any) -> None:
        """Set a nested dictionary value using dot notation path."""
        keys = path.split('.')
        current = config
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value
    
    def _get_nested_value(self, config: Dict[str, Any], path: str, default: Any = None) -> Any:
        """Get a nested dictionary value using dot notation path."""
        keys = path.split('.')
        current = config
        
        for key in keys:
            if not isinstance(current, dict) or key not in current:
                return default
            current = current[key]
        
        return current
    
    def _build_ddos_config(self, config: Dict[str, Any]) -> DDoSConfig:
        """Build DDoSConfig object from config dictionary."""
        # Check if DDoS protection is enabled
        if not config.get("enabled", True):
            # Return minimal config if disabled
            return DDoSConfig(
                max_requests_per_minute=999999,
                max_requests_per_second=999999,
                max_concurrent_connections_per_ip=999999,
                auto_block_threshold=999.0  # Effectively disabled
            )
        
        # Extract configuration values
        rate_limiting = config.get("rate_limiting", {})
        connection_limits = config.get("connection_limits", {})
        pattern_detection = config.get("pattern_detection", {})
        ip_blocking = config.get("ip_blocking", {})
        whitelist_config = config.get("whitelist", {})
        geo_filtering = config.get("geo_filtering", {})
        
        # Build whitelist sets
        whitelist_ips = set(whitelist_config.get("ips", []))
        whitelist_user_agents = set(whitelist_config.get("user_agents", []))
        
        # Build geo filtering sets
        blocked_countries = set(geo_filtering.get("blocked_countries", []))
        allowed_countries_list = geo_filtering.get("allowed_countries", [])
        allowed_countries = set(allowed_countries_list) if allowed_countries_list else None
        
        # Create DDoSConfig instance
        ddos_config = DDoSConfig(
            # Rate limiting
            max_requests_per_minute=rate_limiting.get("max_requests_per_minute", 60),
            max_requests_per_second=rate_limiting.get("max_requests_per_second", 10),
            
            # Connection limits
            max_concurrent_connections_per_ip=connection_limits.get("max_concurrent_per_ip", 10),
            max_total_concurrent_connections=connection_limits.get("max_total_concurrent", 1000),
            
            # Request patterns
            suspicious_pattern_threshold=pattern_detection.get("suspicious_pattern_threshold", 5),
            request_window_seconds=pattern_detection.get("request_window_seconds", 60),
            
            # IP blocking
            auto_block_threshold=ip_blocking.get("auto_block_threshold", 80.0),
            block_duration_seconds=ip_blocking.get("block_duration_seconds", 3600),
            permanent_block_threshold=ip_blocking.get("permanent_block_threshold", 5),
            
            # Attack detection
            slowloris_timeout_seconds=connection_limits.get("connection_timeout_seconds", 30),
            http_flood_threshold=self._get_nested_value(
                config, "attack_detection.http_flood_threshold", 100
            ),
            
            # Whitelisting
            whitelist_ips=whitelist_ips,
            whitelist_user_agents=whitelist_user_agents,
            
            # Geographic filtering
            blocked_countries=blocked_countries,
            allowed_countries=allowed_countries
        )
        
        return ddos_config
    
    def is_enabled(self) -> bool:
        """Check if DDoS protection is enabled in config."""
        if self._config_data is None:
            self.load_config()
        
        env = os.getenv("ENVIRONMENT", "development").lower()
        base_config = self._config_data.get("ddos_protection", {})
        env_overrides = self._config_data.get("environments", {}).get(env, {}).get("ddos_protection", {})
        
        config = self._merge_configs(base_config, env_overrides)
        
        # Check environment variable override
        env_enabled = os.getenv("DDOS_ENABLED")
        if env_enabled is not None:
            return env_enabled.lower() == "true"
        
        return config.get("enabled", True)


def load_ddos_config(config_path: Optional[str] = None) -> DDoSConfig:
    """
    Load DDoS configuration.
    
    Args:
        config_path: Optional path to config file
        
    Returns:
        DDoSConfig instance
    """
    loader = DDoSConfigLoader(config_path)
    return loader.load_config()


def is_ddos_protection_enabled(config_path: Optional[str] = None) -> bool:
    """
    Check if DDoS protection is enabled.
    
    Args:
        config_path: Optional path to config file
        
    Returns:
        True if enabled, False otherwise
    """
    loader = DDoSConfigLoader(config_path)
    return loader.is_enabled()
