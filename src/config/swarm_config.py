"""
Configuration management with feature flag support.

Provides centralized configuration access including SWARM_MODE_ENABLED
for Issue #397 multi-agent swarm intelligence.
"""

import os
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SwarmFeatureConfig:
    """Configuration for swarm intelligence features."""
    enabled: bool = False
    validate_schemas: bool = True
    compression_enabled: bool = True
    max_payload_bytes: int = 1024


class Config:
    """
    Global configuration manager with feature flags.
    
    Environment Variables:
        SWARM_MODE_ENABLED: Enable multi-agent swarm intelligence (default: False)
        SWARM_SCHEMA_VALIDATION: Enable JSONSchema validation (default: True)
        SWARM_COMPRESSION: Enable LZ4 compression (default: True)
        SWARM_MAX_PAYLOAD: Max HealthSummary payload size (default: 1024)
    """

    # Feature flags
    SWARM_MODE_ENABLED = os.getenv("SWARM_MODE_ENABLED", "false").lower() == "true"
    SWARM_SCHEMA_VALIDATION = os.getenv("SWARM_SCHEMA_VALIDATION", "true").lower() == "true"
    SWARM_COMPRESSION = os.getenv("SWARM_COMPRESSION", "true").lower() == "true"
    SWARM_MAX_PAYLOAD = int(os.getenv("SWARM_MAX_PAYLOAD", "1024"))

    # Swarm feature configuration object
    SWARM_CONFIG = SwarmFeatureConfig(
        enabled=SWARM_MODE_ENABLED,
        validate_schemas=SWARM_SCHEMA_VALIDATION,
        compression_enabled=SWARM_COMPRESSION,
        max_payload_bytes=SWARM_MAX_PAYLOAD,
    )

    @classmethod
    def load_swarm_config(cls) -> SwarmFeatureConfig:
        """
        Load swarm configuration from environment variables.
        
        Returns:
            SwarmFeatureConfig instance with current settings
        """
        return cls.SWARM_CONFIG

    @classmethod
    def enable_swarm_mode(cls) -> None:
        """Enable swarm mode at runtime."""
        cls.SWARM_MODE_ENABLED = True
        cls.SWARM_CONFIG.enabled = True
        logger.info("Swarm mode enabled")

    @classmethod
    def disable_swarm_mode(cls) -> None:
        """Disable swarm mode at runtime."""
        cls.SWARM_MODE_ENABLED = False
        cls.SWARM_CONFIG.enabled = False
        logger.info("Swarm mode disabled")

    @classmethod
    def is_swarm_enabled(cls) -> bool:
        """Check if swarm mode is enabled."""
        return cls.SWARM_MODE_ENABLED

    @classmethod
    def get_swarm_config(cls) -> SwarmFeatureConfig:
        """Get current swarm configuration."""
        return cls.SWARM_CONFIG

    @classmethod
    def dump_config(cls) -> Dict[str, Any]:
        """Dump current configuration as dictionary."""
        return {
            "SWARM_MODE_ENABLED": cls.SWARM_MODE_ENABLED,
            "SWARM_SCHEMA_VALIDATION": cls.SWARM_SCHEMA_VALIDATION,
            "SWARM_COMPRESSION": cls.SWARM_COMPRESSION,
            "SWARM_MAX_PAYLOAD": cls.SWARM_MAX_PAYLOAD,
        }


# Create global config instance
config = Config()
