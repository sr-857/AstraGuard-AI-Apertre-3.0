"""
Chaos Engineering Framework for AstraGuard AI

Provides automated chaos testing capabilities for backend resilience validation.
Integrates with Chaos Toolkit for standardized experiment definitions.

Modules:
    experiments: YAML-based chaos experiment definitions
    actions: Custom chaos actions for AstraGuard-specific failures
    probes: Health and recovery validation probes
    validation: Recovery and SLO validation utilities
"""

__version__ = "1.0.0"
__all__ = [
    "run_experiment",
    "validate_recovery",
    "report_incident",
]

from chaos.experiments.runner import run_experiment
from chaos.validation.recovery_validator import validate_recovery
from chaos.validation.incident_reporter import report_incident
