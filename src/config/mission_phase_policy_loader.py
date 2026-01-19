"""
Mission Phase Policy Loader

Loads and validates mission phase response policies from YAML/JSON configuration files.

Features:
- Load policy from file with fallback to defaults
- Validate policy structure
- Provide fallback defaults for missing configurations
- Graceful error handling
"""

import os
import logging
import yaml
import json
from typing import Dict, Any, Optional
from pathlib import Path
from .config_loader import load_config_file, find_config_file

logger = logging.getLogger(__name__)


class MissionPhasePolicyLoader:
    """
    Loads and validates mission phase policies from configuration files.
    
    Policy files can be in YAML or JSON format. If a file is not found,
    sensible defaults are provided to prevent system breakage.
    """
    
    DEFAULT_POLICY = {
        "phases": {
            "LAUNCH": {
                "description": "Rocket ascent and orbital insertion phase.",
                "allowed_actions": ["LOG_EVENT", "MONITOR", "ALERT_ONLY"],
                "forbidden_actions": ["RESTART_SERVICE", "FIRE_THRUSTERS", "DEPLOY_SOLAR_PANELS"],
                "threshold_multiplier": 2.0,
                "severity_thresholds": {
                    "CRITICAL": "ESCALATE_SAFE_MODE",
                    "HIGH": "ALERT_OPERATORS",
                    "MEDIUM": "LOG_ONLY",
                    "LOW": "LOG_ONLY"
                }
            },
            "DEPLOYMENT": {
                "description": "Initial system startup and stabilization.",
                "allowed_actions": ["LOG_EVENT", "MONITOR", "ALERT_ONLY", "PING_GROUND"],
                "forbidden_actions": ["FIRE_THRUSTERS", "PAYLOAD_OPERATIONS"],
                "threshold_multiplier": 1.5,
                "severity_thresholds": {
                    "CRITICAL": "ESCALATE_SAFE_MODE",
                    "HIGH": "ALERT_OPERATORS",
                    "MEDIUM": "LOG_ONLY",
                    "LOW": "LOG_ONLY"
                }
            },
            "NOMINAL_OPS": {
                "description": "Standard mission operations.",
                "allowed_actions": [
                    "LOG_EVENT", "MONITOR", "ALERT_ONLY", "RESTART_SERVICE",
                    "THERMAL_REGULATION", "POWER_LOAD_BALANCING", "STABILIZATION",
                    "PING_GROUND", "ISOLATE_SUBSYSTEM"
                ],
                "forbidden_actions": [],
                "threshold_multiplier": 1.0,
                "severity_thresholds": {
                    "CRITICAL": "ESCALATE_SAFE_MODE",
                    "HIGH": "CONTROLLED_ACTION",
                    "MEDIUM": "CONTROLLED_ACTION",
                    "LOW": "LOG_ONLY"
                }
            },
            "PAYLOAD_OPS": {
                "description": "Specialized payload mission operations.",
                "allowed_actions": [
                    "LOG_EVENT", "MONITOR", "ALERT_ONLY", "RESTART_SERVICE",
                    "THERMAL_REGULATION", "POWER_LOAD_BALANCING",
                    "PAYLOAD_OPERATIONS", "HIGH_POWER_TRANSMISSION", "PING_GROUND"
                ],
                "forbidden_actions": ["FIRE_THRUSTERS", "STABILIZATION"],
                "threshold_multiplier": 1.0,
                "severity_thresholds": {
                    "CRITICAL": "ESCALATE_SAFE_MODE",
                    "HIGH": "CONTROLLED_ACTION",
                    "MEDIUM": "CONTROLLED_ACTION",
                    "LOW": "LOG_ONLY"
                }
            },
            "SAFE_MODE": {
                "description": "Minimal power state for survival.",
                "allowed_actions": ["LOG_EVENT", "MONITOR", "ALERT_ONLY", "PING_GROUND"],
                "forbidden_actions": [
                    "RESTART_SERVICE", "FIRE_THRUSTERS", "THERMAL_REGULATION",
                    "PAYLOAD_OPERATIONS", "HIGH_POWER_TRANSMISSION"
                ],
                "threshold_multiplier": 0.8,
                "severity_thresholds": {
                    "CRITICAL": "LOG_ONLY",
                    "HIGH": "LOG_ONLY",
                    "MEDIUM": "LOG_ONLY",
                    "LOW": "LOG_ONLY"
                }
            }
        },
        "global": {
            "default_action": "LOG_ONLY",
            "min_confidence_for_action": 0.7,
            "min_confidence_for_escalation": 0.8,
            "recurrence_window_seconds": 3600,
            "recurrence_threshold": 2,
            "log_all_decisions": True,
            "enable_simulation_mode": True
        }
    }
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the policy loader.
        
        Args:
            config_path: Path to policy config file (YAML or JSON).
                        If None, looks for default locations.
                        If not found, uses built-in defaults.
        """
        self.config_path = config_path or self._find_default_config_path()
        self.policy: Dict[str, Any] = {}
        self._load()
    
    def _find_default_config_path(self) -> Optional[str]:
        """
        Try to find policy config in default locations.
        
        Default search paths (in order):
        1. config/mission_phase_response_policy
        2. config/mission_policies
        3. ../config/mission_phase_response_policy (relative to this file)
        """
        search_paths = ["config", str(Path(__file__).parent.parent / "config")]
        
        # Try mission_phase_response_policy first
        config_path = find_config_file("mission_phase_response_policy", search_paths)
        if config_path:
            return config_path
            
        # Fallback to mission_policies
        config_path = find_config_file("mission_policies", search_paths)
        if config_path:
            return config_path
            
        return None
    
    def _load(self):
        """Load policy from file or use defaults."""
        if self.config_path and os.path.exists(self.config_path):
            try:
                self.policy = self._load_file(self.config_path)
                logger.info(f"Loaded mission phase policy from {self.config_path}")
                
                # Validate loaded policy
                self._validate_policy()
                
                # Merge with defaults for missing keys
                self.policy = self._merge_with_defaults(self.policy)
                logger.info("Policy validated and merged with defaults")
                
            except Exception as e:
                logger.error(f"Failed to load policy from {self.config_path}: {e}")
                logger.warning("Falling back to default policy")
                self.policy = self.DEFAULT_POLICY.copy()
        else:
            if self.config_path:
                logger.warning(f"Policy config not found at {self.config_path}")
            logger.info("Using default mission phase policy")
            self.policy = self.DEFAULT_POLICY.copy()
    
    def _load_file(self, path: str) -> Dict[str, Any]:
        """Load policy from YAML or JSON file with environment variable substitution."""
        from .config_utils import load_config_with_env_vars
        return load_config_with_env_vars(path)
    
    def _validate_policy(self):
        """Validate policy structure."""
        if not isinstance(self.policy, dict):
            raise ValueError("Policy must be a dictionary at root level")
        
        if 'phases' not in self.policy:
            raise ValueError("Policy must contain 'phases' key")
        
        phases = self.policy['phases']
        if not isinstance(phases, dict):
            raise ValueError("Phases must be a dictionary")
        
        if not phases:
            raise ValueError("At least one phase must be defined")
        
        # Check minimum required phases
        expected_phases = {"LAUNCH", "DEPLOYMENT", "NOMINAL_OPS", "SAFE_MODE"}
        configured_phases = set(phases.keys())
        missing = expected_phases - configured_phases
        
        if missing:
            logger.warning(f"Policy missing expected phases: {missing}")
        
        # Validate each phase
        for phase_name, phase_config in phases.items():
            if not isinstance(phase_config, dict):
                raise ValueError(f"Phase '{phase_name}' config must be a dictionary")
            
            if 'description' not in phase_config:
                logger.warning(f"Phase '{phase_name}' missing description")
            
            if 'allowed_actions' not in phase_config:
                logger.warning(f"Phase '{phase_name}' missing allowed_actions")
    
    def _merge_with_defaults(self, loaded_policy: Dict) -> Dict:
        """Merge loaded policy with defaults for missing fields."""
        result = {
            "phases": {},
            "global": self.DEFAULT_POLICY.get("global", {}).copy()
        }
        
        # Update global config if provided
        if "global" in loaded_policy:
            result["global"].update(loaded_policy["global"])
        
        # Merge phases
        default_phases = self.DEFAULT_POLICY.get("phases", {})
        loaded_phases = loaded_policy.get("phases", {})
        
        # Keep all default phases
        for phase_name, default_config in default_phases.items():
            result["phases"][phase_name] = default_config.copy()
        
        # Override with loaded phases
        for phase_name, loaded_config in loaded_phases.items():
            if phase_name in result["phases"]:
                result["phases"][phase_name].update(loaded_config)
            else:
                result["phases"][phase_name] = loaded_config
        
        return result
    
    def get_policy(self) -> Dict[str, Any]:
        """Get the loaded and validated policy."""
        return self.policy
    
    def get_phase_policy(self, phase_name: str) -> Optional[Dict[str, Any]]:
        """Get policy for a specific phase."""
        return self.policy.get("phases", {}).get(phase_name)
    
    def get_global_config(self) -> Dict[str, Any]:
        """Get global configuration."""
        return self.policy.get("global", {})
    
    def reload(self, new_config_path: Optional[str] = None):
        """Reload policy from file."""
        if new_config_path:
            self.config_path = new_config_path
        self._load()
        logger.info("Policy reloaded")
    
    def to_dict(self) -> Dict[str, Any]:
        """Export policy as dictionary."""
        return self.policy.copy()
