"""
Configuration management for database connection pooling.
"""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PoolConfig:
    """Connection pool configuration parameters."""
    
    max_size: int = 10
    min_size: int = 2
    connection_timeout: float = 30.0
    idle_timeout: float = 300.0
    max_retries: int = 3
    retry_backoff: float = 0.5
    enable_pool: bool = True
    db_path: str = "data/contact_submissions.db"
    
    @classmethod
    def from_file(cls, path: str = "config/database.json") -> "PoolConfig":
        """
        Load configuration from JSON file.
        Falls back to defaults if file missing or invalid.
        
        Args:
            path: Path to configuration file
            
        Returns:
            PoolConfig instance with loaded or default values
        """
        config_path = Path(path)
        
        # Try to load from file
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    data = json.load(f)
                    pool_config = data.get("connection_pool", {})
                    
                    # Create config with file values
                    config = cls(
                        max_size=pool_config.get("max_size", cls.max_size),
                        min_size=pool_config.get("min_size", cls.min_size),
                        connection_timeout=pool_config.get("connection_timeout", cls.connection_timeout),
                        idle_timeout=pool_config.get("idle_timeout", cls.idle_timeout),
                        max_retries=pool_config.get("max_retries", cls.max_retries),
                        retry_backoff=pool_config.get("retry_backoff", cls.retry_backoff),
                        enable_pool=pool_config.get("enable_pool", cls.enable_pool),
                        db_path=data.get("db_path", cls.db_path),
                    )
                    
                    logger.info(f"Loaded pool configuration from {path}")
                    return config
                    
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.error(
                    f"Failed to load configuration from {path}: {e}. Using defaults.",
                    exc_info=True
                )
        else:
            logger.info(f"Configuration file {path} not found. Using defaults.")
        
        # Apply environment variable overrides
        config = cls()
        config._apply_env_overrides()
        return config
    
    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides to configuration."""
        if os.getenv("DB_POOL_MAX_SIZE"):
            try:
                self.max_size = int(os.getenv("DB_POOL_MAX_SIZE"))
            except ValueError:
                logger.warning("Invalid DB_POOL_MAX_SIZE environment variable")
        
        if os.getenv("DB_POOL_MIN_SIZE"):
            try:
                self.min_size = int(os.getenv("DB_POOL_MIN_SIZE"))
            except ValueError:
                logger.warning("Invalid DB_POOL_MIN_SIZE environment variable")
        
        if os.getenv("DB_POOL_CONNECTION_TIMEOUT"):
            try:
                self.connection_timeout = float(os.getenv("DB_POOL_CONNECTION_TIMEOUT"))
            except ValueError:
                logger.warning("Invalid DB_POOL_CONNECTION_TIMEOUT environment variable")
        
        if os.getenv("DB_POOL_IDLE_TIMEOUT"):
            try:
                self.idle_timeout = float(os.getenv("DB_POOL_IDLE_TIMEOUT"))
            except ValueError:
                logger.warning("Invalid DB_POOL_IDLE_TIMEOUT environment variable")
        
        if os.getenv("DB_POOL_ENABLED"):
            self.enable_pool = os.getenv("DB_POOL_ENABLED").lower() in ("true", "1", "yes")
    
    def validate(self) -> None:
        """
        Validate configuration parameters.
        
        Raises:
            ValueError: If parameters are invalid
        """
        errors = []
        
        if self.max_size <= 0:
            errors.append("max_size must be positive")
        
        if self.min_size < 0:
            errors.append("min_size must be non-negative")
        
        if self.min_size > self.max_size:
            errors.append("min_size cannot exceed max_size")
        
        if self.connection_timeout <= 0:
            errors.append("connection_timeout must be positive")
        
        if self.idle_timeout <= 0:
            errors.append("idle_timeout must be positive")
        
        if self.max_retries < 0:
            errors.append("max_retries must be non-negative")
        
        if self.retry_backoff < 0:
            errors.append("retry_backoff must be non-negative")
        
        if errors:
            error_msg = "; ".join(errors)
            logger.error(f"Invalid pool configuration: {error_msg}")
            raise ValueError(f"Invalid pool configuration: {error_msg}")
