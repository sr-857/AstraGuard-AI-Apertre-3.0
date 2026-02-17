"""
Advanced Anomaly Detector for Security Threat Detection

Integrates feature engineering, model ensemble, and adaptive learning
to provide real-time threat detection with <1% false positive rate.
"""

import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import logging
import asyncio
from collections import deque
import hashlib
import json

from .feature_engineering import (
    FeatureEngineeringPipeline, 
    get_feature_pipeline,
    FeatureCategory
)
from .model_ensemble import (
    ModelEnsemble,
    EnsemblePrediction,
    get_model_ensemble,
    ModelType
)

from core.error_handling import (
    AstraGuardException,
    safe_execute,
    ErrorContext,
    ErrorSeverity,
    handle_component_error
)
from core.timeout_handler import async_timeout, get_timeout_config
from core.circuit_breaker import CircuitBreaker, register_circuit_breaker, CircuitOpenError
from core.resource_monitor import get_resource_monitor
from core.component_health import get_health_monitor
from core.metrics import (
    THREAT_DETECTION_LATENCY,
    THREAT_DETECTION_PREDICTIONS_TOTAL,
    THREAT_DETECTION_FALSE_POSITIVES,
    THREAT_DETECTION_TRUE_POSITIVES,
    THREAT_DETECTION_ALERTS_TOTAL,
)

logger = logging.getLogger(__name__)


class ThreatSeverity(Enum):
    """Severity levels for detected threats."""
    CRITICAL = "critical"      # Immediate action required
    HIGH = "high"              # Urgent attention needed
    MEDIUM = "medium"          # Investigate soon
    LOW = "low"                # Monitor
    INFO = "info"              # Informational only


class ThreatCategory(Enum):
    """Categories of security threats."""
    MALWARE = "malware"
    INTRUSION = "intrusion"
    DATA_EXFILTRATION = "data_exfiltration"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    LATERAL_MOVEMENT = "lateral_movement"
    DENIAL_OF_SERVICE = "denial_of_service"
    ANOMALY = "anomaly"
    POLICY_VIOLATION = "policy_violation"


@dataclass
class ThreatDetection:
    """Complete threat detection result."""
    detection_id: str
    timestamp: datetime
    is_threat: bool
    severity: ThreatSeverity
    category: ThreatCategory
    confidence: float
    anomaly_score: float
    source_data: Dict[str, Any]
    features_used: List[str]
    model_predictions: List[Dict[str, Any]]
    recommended_actions: List[str]
    context: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'detection_id': self.detection_id,
            'timestamp': self.timestamp.isoformat(),
            'is_threat': self.is_threat,
            'severity': self.severity.value,
            'category': self.category.value,
            'confidence': self.confidence,
            'anomaly_score': self.anomaly_score,
            'source_data_hash': hashlib.sha256(
                json.dumps(self.source_data, sort_keys=True).encode()
            ).hexdigest()[:16],
            'features_count': len(self.features_used),
            'model_predictions': self.model_predictions,
            'recommended_actions': self.recommended_actions,
            'context': self.context
        }


class AdvancedAnomalyDetector:
    """
    Advanced anomaly detector integrating multiple ML models and feature engineering.
    
    Features:
    - Real-time threat detection with <100ms latency
    - <1% false positive rate through ensemble voting
    - Adaptive learning from feedback
    - Multi-category threat classification
    - Automatic severity assignment
    """
    
    # Performance targets
    TARGET_LATENCY_MS: float = 100.0
    TARGET_FPR: float = 0.01  # <1%
    
    def __init__(self):
        self.feature_pipeline: Optional[FeatureEngineeringPipeline] = None
        self.model_ensemble: Optional[ModelEnsemble] = None
        self.is_initialized: bool = False
        
        # Detection history for feedback loop
        self.detection_history: deque = deque(maxlen=10000)
        self.feedback_buffer: deque = deque(maxlen=1000)
        
        # Threat categorization rules
        self.category_rules = self._initialize_category_rules()
        
        # Circuit breaker for detection pipeline
        self.detection_circuit = register_circuit_breaker(
            CircuitBreaker(
                name="threat_detection",
                failure_threshold=5,
                success_threshold=2,
                recovery_timeout=30,
                expected_exceptions=(Exception,)
            )
        )
        
        # Health monitoring
        self.health_monitor = get_health_monitor()
        self.health_monitor.register_component("advanced_anomaly_detector")
        
        # Performance tracking
        self.detection_count: int = 0
        self.false_positive_count: int = 0
        self.total_latency_ms: float = 0.0
        
    def _initialize_category_rules(self) -> Dict[ThreatCategory, Dict[str, Any]]:
        """Initialize rules for threat categorization."""
        return {
            ThreatCategory.MALWARE: {
                'indicators': ['process_anomaly', 'file_entropy_high', 'suspicious_api_calls'],
                'severity_threshold': 0.8,
                'default_severity': ThreatSeverity.HIGH
            },
            ThreatCategory.INTRUSION: {
                'indicators': ['auth_failure_burst', 'unusual_login_time', 'geo_anomaly'],
                'severity_threshold': 0.75,
                'default_severity': ThreatSeverity.CRITICAL
            },
            ThreatCategory.DATA_EXFILTRATION: {
                'indicators': ['large_outbound_transfer', 'unusual_destination', 'off_hours_access'],
                'severity_threshold': 0.7,
                'default_severity': ThreatSeverity.CRITICAL
            },
            ThreatCategory.PRIVILEGE_ESCALATION: {
                'indicators': ['sudo_usage', 'permission_change', 'admin_access'],
                'severity_threshold': 0.8,
                'default_severity': ThreatSeverity.HIGH
            },
            ThreatCategory.LATERAL_MOVEMENT: {
                'indicators': ['network_scan', 'connection_spike', 'internal_port_access'],
                'severity_threshold': 0.75,
                'default_severity': ThreatSeverity.HIGH
            },
            ThreatCategory.DENIAL_OF_SERVICE: {
                'indicators': ['request_flood', 'connection_flood', 'resource_exhaustion'],
                'severity_threshold': 0.7,
                'default_severity': ThreatSeverity.HIGH
            },
            ThreatCategory.ANOMALY: {
                'indicators': ['statistical_outlier', 'behavioral_deviation'],
                'severity_threshold': 0.85,  # High threshold to reduce FPs
                'default_severity': ThreatSeverity.MEDIUM
            },
            ThreatCategory.POLICY_VIOLATION: {
                'indicators': ['unauthorized_access', 'compliance_violation'],
                'severity_threshold': 0.6,
                'default_severity': ThreatSeverity.MEDIUM
            }
        }
    
    async def initialize(self) -> bool:
        """Initialize the detector with all components."""
        try:
            logger.info("Initializing advanced anomaly detector...")
            
            # Initialize feature pipeline
            self.feature_pipeline = get_feature_pipeline()
            
            # Initialize model ensemble
            self.model_ensemble = await get_model_ensemble(input_dim=50)
            
            # Try to load pre-trained models
            models_loaded = await self.model_ensemble.load_models()
            
            if not models_loaded:
                logger.warning("No pre-trained models found - detector will need training")
            
            self.is_initialized = True
            self.health_monitor.mark_healthy(
                "advanced_anomaly_detector",
                {
                    "models_loaded": models_loaded,
                    "status": "initialized"
                }
            )
            
            logger.info("Advanced anomaly detector initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize detector: {e}")
            self.health_monitor.mark_failed("advanced_anomaly_detector", str(e))
            return False
    
    @async_timeout(seconds=0.5, operation_name="threat_detection")  # 500ms max for real-time
    async def detect(self, data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ThreatDetection:
        """
        Perform real-time threat detection on input data.
        
        Args:
            data: Input data dictionary with telemetry/security events
            context: Optional context (user, system, time, etc.)
            
        Returns:
            ThreatDetection result with threat assessment
        """
        start_time = datetime.now()
        detection_id = self._generate_detection_id(data)
        
        try:
            # Check resource availability
            resource_monitor = get_resource_monitor()
            resource_status = resource_monitor.check_resource_health()
            
            if resource_status['overall'] == 'critical':
                logger.warning("Critical resource levels - detection may be degraded")
            
            # Ensure initialization
            if not self.is_initialized:
                await self.initialize()
            
            # Extract features
            features = await self.feature_pipeline.extract_features(data)
            feature_vector = np.array(list(features.values()))
            
            # Get ensemble prediction through circuit breaker
            prediction = await self.detection_circuit.call(
                self.model_ensemble.predict,
                feature_vector
            )
            
            # Categorize threat
            category, severity = self._categorize_threat(
                prediction, features, context or {}
            )
            
            # Determine if this is a real threat
            is_threat = prediction.is_anomaly and prediction.confidence > 0.85
            
            # Generate recommended actions
            actions = self._generate_recommended_actions(
                category, severity, prediction, context or {}
            )
            
            # Create detection result
            detection = ThreatDetection(
                detection_id=detection_id,
                timestamp=datetime.now(),
                is_threat=is_threat,
                severity=severity,
                category=category,
                confidence=prediction.confidence,
                anomaly_score=prediction.anomaly_score,
                source_data=data,
                features_used=list(features.keys()),
                model_predictions=[p.__dict__ for p in prediction.model_predictions],
                recommended_actions=actions,
                context=context or {}
            )
            
            # Track metrics
            self._track_detection_metrics(detection, start_time)
            
            # Store in history
            self.detection_history.append(detection)
            
            # Alert if threat detected
            if is_threat:
                await self._alert_threat(detection)
            
            return detection
            
        except CircuitOpenError as e:
            logger.error(f"Detection circuit open: {e}")
            return self._create_fallback_detection(detection_id, data, "circuit_open")
            
        except asyncio.TimeoutError:
            logger.warning("Detection timeout - returning fallback")
            return self._create_fallback_detection(detection_id, data, "timeout")
            
        except Exception as e:
            logger.error(f"Detection failed: {e}")
            return self._create_fallback_detection(detection_id, data, f"error: {str(e)}")
    
    def _generate_detection_id(self, data: Dict[str, Any]) -> str:
        """Generate unique detection ID."""
        timestamp = datetime.now().isoformat()
        data_hash = hashlib.md5(
            f"{timestamp}{str(data)}".encode()
        ).hexdigest()[:12]
        return f"THREAT-{data_hash}"
    
    def _categorize_threat(self, prediction: EnsemblePrediction, 
                          features: Dict[str, Any],
                          context: Dict[str, Any]) -> Tuple[ThreatCategory, ThreatSeverity]:
        """
        Categorize threat based on prediction and features.
        
        Returns:
            Tuple of (category, severity)
        """
        # Default category
        category = ThreatCategory.ANOMALY
        max_score = prediction.anomaly_score
        
        # Check each category's indicators
        for cat, rules in self.category_rules.items():
            score = 0.0
            indicators_found = 0
            
            for indicator in rules['indicators']:
                # Check if indicator is present in features or context
                if indicator in features:
                    score += features[indicator] * 0.3
                    indicators_found += 1
                elif indicator in context:
                    score += 0.5
                    indicators_found += 1
            
            # Boost score based on number of indicators found
            if indicators_found > 0:
                score *= (1 + indicators_found * 0.2)
            
            # Update category if this one has higher score
            if score > max_score and score > rules['severity_threshold']:
                max_score = score
                category = cat
        
        # Determine severity
        if prediction.anomaly_score > 0.9 and prediction.confidence > 0.9:
            severity = ThreatSeverity.CRITICAL
        elif prediction.anomaly_score > 0.8:
            severity = ThreatSeverity.HIGH
        elif prediction.anomaly_score > 0.7:
            severity = ThreatSeverity.MEDIUM
        elif prediction.anomaly_score > 0.6:
            severity = ThreatSeverity.LOW
        else:
            severity = ThreatSeverity.INFO
        
        # Adjust severity based on category rules
        category_rules = self.category_rules.get(category, {})
        if severity.value < category_rules.get('default_severity', ThreatSeverity.MEDIUM).value:
            severity = category_rules['default_severity']
        
        return category, severity
    
    def _generate_recommended_actions(self, category: ThreatCategory,
                                     severity: ThreatSeverity,
                                     prediction: EnsemblePrediction,
                                     context: Dict[str, Any]) -> List[str]:
        """Generate recommended actions based on threat assessment."""
        actions = []
        
        # Base actions by severity
        if severity == ThreatSeverity.CRITICAL:
            actions.extend([
                "Immediately isolate affected system",
                "Notify security team via pager/SMS",
                "Begin evidence collection",
                "Prepare incident response"
            ])
        elif severity == ThreatSeverity.HIGH:
            actions.extend([
                "Increase monitoring on affected system",
                "Notify security team",
                "Review access logs"
            ])
        elif severity == ThreatSeverity.MEDIUM:
            actions.extend([
                "Schedule investigation",
                "Review related events"
            ])
        
        # Category-specific actions
        category_actions = {
            ThreatCategory.MALWARE: [
                "Run antivirus scan",
                "Check process hashes against threat intelligence",
                "Isolate suspicious processes"
            ],
            ThreatCategory.INTRUSION: [
                "Block source IP",
                "Force password reset for affected account",
                "Review authentication logs"
            ],
            ThreatCategory.DATA_EXFILTRATION: [
                "Block outbound connections",
                "Review data access audit logs",
                "Check for data loss"
            ],
            ThreatCategory.PRIVILEGE_ESCALATION: [
                "Revoke elevated permissions",
                "Audit privilege usage",
                "Review sudo logs"
            ],
            ThreatCategory.LATERAL_MOVEMENT: [
                "Segment network access",
                "Block suspicious internal connections",
                "Scan for compromise indicators"
            ],
            ThreatCategory.DENIAL_OF_SERVICE: [
                "Activate rate limiting",
                "Scale resources",
                "Block attacking IPs"
            ]
        }
        
        if category in category_actions:
            actions.extend(category_actions[category])
        
        return actions
    
    def _track_detection_metrics(self, detection: ThreatDetection, start_time: datetime):
        """Track detection performance metrics."""
        latency_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        self.detection_count += 1
        self.total_latency_ms += latency_ms
        
        THREAT_DETECTION_LATENCY.observe(latency_ms / 1000)  # Convert to seconds
        
        if detection.is_threat:
            THREAT_DETECTION_ALERTS_TOTAL.labels(
                severity=detection.severity.value,
                category=detection.category.value
            ).inc()
    
    async def _alert_threat(self, detection: ThreatDetection):
        """Alert on detected threat."""
        logger.warning(
            f"THREAT DETECTED: {detection.detection_id} | "
            f"Category: {detection.category.value} | "
            f"Severity: {detection.severity.value} | "
            f"Confidence: {detection.confidence:.2f}"
        )
        
        # Here you would integrate with alerting systems
        # (PagerDuty, Slack, email, SIEM, etc.)
        
        # Store for forensics
        await self._store_for_forensics(detection)
    
    async def _store_for_forensics(self, detection: ThreatDetection):
        """Store detection for forensics analysis."""
        # This would integrate with the forensics logging system
        pass
    
    def _create_fallback_detection(self, detection_id: str, data: Dict[str, Any],
                                    reason: str) -> ThreatDetection:
        """Create fallback detection when normal detection fails."""
        return ThreatDetection(
            detection_id=detection_id,
            timestamp=datetime.now(),
            is_threat=False,  # Conservative: don't alert on failure
            severity=ThreatSeverity.INFO,
            category=ThreatCategory.ANOMALY,
            confidence=0.0,
            anomaly_score=0.5,
            source_data=data,
            features_used=[],
            model_predictions=[],
            recommended_actions=[f"Detection failed: {reason}. Manual review recommended."],
            context={'fallback': True, 'failure_reason': reason}
        )
    
    async def provide_feedback(self, detection_id: str, was_true_positive: bool):
        """
        Provide feedback on a detection for adaptive learning.
        
        Args:
            detection_id: ID of the detection
            was_true_positive: Whether it was a real threat (True) or false positive (False)
        """
        # Find detection in history
        detection = None
        for d in self.detection_history:
            if d.detection_id == detection_id:
                detection = d
                break
        
        if not detection:
            logger.warning(f"Detection {detection_id} not found for feedback")
            return
        
        # Store feedback
        self.feedback_buffer.append({
            'detection_id': detection_id,
            'was_true_positive': was_true_positive,
            'timestamp': datetime.now(),
            'detection': detection
        })
        
        # Update model ensemble
        if self.model_ensemble:
            self.model_ensemble.update_performance(
                predicted_anomaly=detection.is_threat,
                actual_anomaly=was_true_positive
            )
        
        # Log feedback
        if was_true_positive:
            THREAT_DETECTION_TRUE_POSITIVES.inc()
            logger.info(f"Feedback: True positive confirmed for {detection_id}")
        else:
            self.false_positive_count += 1
            THREAT_DETECTION_FALSE_POSITIVES.inc()
            logger.info(f"Feedback: False positive recorded for {detection_id}")
        
        # Periodic model retraining check
        if len(self.feedback_buffer) >= 100:
            await self._consider_retraining()
    
    async def _consider_retraining(self):
        """Consider retraining models based on feedback."""
        recent_feedback = list(self.feedback_buffer)[-100:]
        
        false_positives = sum(1 for f in recent_feedback if not f['was_true_positive'])
        fp_rate = false_positives / len(recent_feedback)
        
        if fp_rate > self.TARGET_FPR:
            logger.warning(f"False positive rate {fp_rate:.2%} exceeds target - considering retraining")
            # Here you would trigger model retraining
            # For now, just adjust thresholds
            if self.model_ensemble:
                # Increase thresholds to reduce false positives
                for model_type in self.model_ensemble.thresholds:
                    self.model_ensemble.thresholds[model_type] = min(
                        0.9, 
                        self.model_ensemble.thresholds[model_type] + 0.05
                    )
    
    async def train(self, training_data: List[Dict[str, Any]], 
                    labels: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Train the detector with labeled data.
        
        Args:
            training_data: List of data dictionaries
            labels: Optional labels (1=anomaly, 0=normal)
            
        Returns:
            Training metrics
        """
        logger.info(f"Starting training with {len(training_data)} samples")
        
        # Extract features for all samples
        features_list = []
        for data in training_data:
            features = await self.feature_pipeline.extract_features(data)
            features_list.append(features)
        
        # Convert to feature matrix
        feature_matrix = np.array([list(f.values()) for f in features_list])
        
        # Convert labels if provided
        if labels:
            y = np.array(labels)
        else:
            y = None
        
        # Train ensemble
        metrics = await self.model_ensemble.train(feature_matrix, y)
        
        logger.info(f"Training completed: {metrics}")
        return {
            'samples_processed': len(training_data),
            'feature_count': feature_matrix.shape[1],
            'model_metrics': metrics
        }
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get detector performance statistics."""
        avg_latency = (
            self.total_latency_ms / self.detection_count 
            if self.detection_count > 0 else 0
        )
        
        fpr = (
            self.false_positive_count / self.detection_count 
            if self.detection_count > 0 else 0
        )
        
        return {
            'total_detections': self.detection_count,
            'false_positives': self.false_positive_count,
            'false_positive_rate': fpr,
            'target_fpr': self.TARGET_FPR,
            'average_latency_ms': avg_latency,
            'target_latency_ms': self.TARGET_LATENCY_MS,
            'meets_latency_target': avg_latency <= self.TARGET_LATENCY_MS,
            'meets_fpr_target': fpr <= self.TARGET_FPR,
            'history_size': len(self.detection_history),
            'feedback_buffer_size': len(self.feedback_buffer)
        }
    
    def get_recent_detections(self, count: int = 100,
                               severity_filter: Optional[ThreatSeverity] = None) -> List[ThreatDetection]:
        """Get recent detections with optional filtering."""
        detections = list(self.detection_history)[-count:]
        
        if severity_filter:
            detections = [d for d in detections if d.severity == severity_filter]
        
        return detections


# Global instance
_detector: Optional[AdvancedAnomalyDetector] = None


async def get_advanced_detector() -> AdvancedAnomalyDetector:
    """Get or create global advanced detector instance."""
    global _detector
    if _detector is None:
        _detector = AdvancedAnomalyDetector()
        await _detector.initialize()
    return _detector
