"""
AstraGuard Anomaly Agent

Real-time decision loop: detect → recall → reason → act → learn
"""

__version__ = "2.0.0"

# Import available components
try:
    from .phase_aware_handler import PhaseAwareAnomalyHandler, DecisionTracer
    __all__ = ["PhaseAwareAnomalyHandler", "DecisionTracer"]
except (ImportError, ModuleNotFoundError):
    __all__ = []

# Legacy imports for compatibility (these modules may not exist)
try:
    from .decision_loop import DecisionLoop
    __all__.append("DecisionLoop")
except (ImportError, ModuleNotFoundError):
    pass

try:
    from .reasoning_engine import ReasoningEngine
    __all__.append("ReasoningEngine")
except (ImportError, ModuleNotFoundError):
    pass

try:
    from .confidence_scorer import ConfidenceScorer
    __all__.append("ConfidenceScorer")
except (ImportError, ModuleNotFoundError):
    pass

