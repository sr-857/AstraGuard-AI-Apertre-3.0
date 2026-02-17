"""
Advanced Security Threat Detection System for AstraGuard

This module provides ML-based security threat detection capabilities including:
- Advanced anomaly detection with ensemble models
- Behavioral analysis and profiling
- Threat intelligence integration
- Automated response and mitigation
- Forensics logging and evidence collection
- Threat hunting tools

All components are designed for <1% false positive rate and real-time detection.
"""

from .advanced_anomaly_detector import AdvancedAnomalyDetector, get_advanced_detector
from .detection_engine import ThreatDetectionEngine, get_detection_engine
from .threat_intelligence import ThreatIntelligenceManager, get_threat_intelligence

__all__ = [
    "AdvancedAnomalyDetector",
    "get_advanced_detector",
    "ThreatDetectionEngine", 
    "get_detection_engine",
    "ThreatIntelligenceManager",
    "get_threat_intelligence",
]
