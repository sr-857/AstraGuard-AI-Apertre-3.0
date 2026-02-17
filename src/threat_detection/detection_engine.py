"""
Detection Engine - Main Orchestration for Threat Detection

Central orchestration system that coordinates all threat detection
components including anomaly detection, behavioral analysis,
threat intelligence, and automated response.
"""

import asyncio
from typing import Dict, List, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
from collections import deque
import uuid

from .advanced_anomaly_detector import (
    AdvancedAnomalyDetector, ThreatDetection, ThreatSeverity, 
    ThreatCategory, get_advanced_detector
)
from .behavioral_analyzer import (
    BehavioralAnalyzer, BehavioralAnalysisResult, 
    get_behavioral_analyzer
)
from .threat_intelligence import (
    ThreatIntelligenceManager, get_threat_intelligence
)
from .automated_response import (
    AutomatedResponseSystem, get_automated_response
)
from .forensics_logger import (
    ForensicsLogger, ForensicsEventType, ForensicsSeverity,
    get_forensics_logger
)
from .ioc_manager import IoCManager, get_ioc_manager
from core.error_handling import safe_execute, AstraGuardException
from core.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class DetectionMode(Enum):
    """Detection operation modes."""
    PASSIVE = "passive"           # Detection only
    ACTIVE = "active"             # Detection with alerting
    AUTONOMOUS = "autonomous"     # Detection with automated response


class EngineStatus(Enum):
    """Engine operational status."""
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


@dataclass
class DetectionContext:
    """Context for detection operations."""
    source: str
    timestamp: datetime
    entity_id: Optional[str] = None
    entity_type: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    priority: int = 5  # 1-10, lower is higher priority


@dataclass
class DetectionResult:
    """Result of a detection operation."""
    detection_id: str
    timestamp: datetime
    detections: List[ThreatDetection]
    behavioral_analysis: Optional[BehavioralAnalysisResult] = None
    ioc_matches: List[Dict[str, Any]] = field(default_factory=list)
    response_triggered: bool = False
    response_actions: List[str] = field(default_factory=list)
    forensics_event_id: Optional[str] = None
    processing_time_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "detection_id": self.detection_id,
            "timestamp": self.timestamp.isoformat(),
            "detections": [d.to_dict() for d in self.detections],
            "behavioral_analysis": self.behavioral_analysis.to_dict() if self.behavioral_analysis else None,
            "ioc_matches": self.ioc_matches,
            "response_triggered": self.response_triggered,
            "response_actions": self.response_actions,
            "forensics_event_id": self.forensics_event_id,
            "processing_time_ms": self.processing_time_ms
        }


class ThreatDetectionEngine:
    """
    Main threat detection orchestration engine.
    
    Coordinates all detection components and manages the complete
    threat detection pipeline from data ingestion to response.
    """
    
    def __init__(self, mode: DetectionMode = DetectionMode.ACTIVE):
        self.mode = mode
        self.status = EngineStatus.INITIALIZING
        
        # Component references
        self.anomaly_detector: Optional[AdvancedAnomalyDetector] = None
        self.behavioral_analyzer: Optional[BehavioralAnalyzer] = None
        self.threat_intel: Optional[ThreatIntelligenceManager] = None
        self.response_system: Optional[AutomatedResponseSystem] = None
        self.forensics_logger: Optional[ForensicsLogger] = None
        self.ioc_manager: Optional[IoCManager] = None
        
        # Detection pipeline
        self.detection_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self.processing_tasks: List[asyncio.Task] = []
        self.max_workers = 5
        
        # Circuit breakers for components
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Statistics
        self.total_processed = 0
        self.total_detections = 0
        self.total_responses = 0
        self.processing_times: deque = deque(maxlen=1000)
        
        # Detection history
        self.detection_history: deque = deque(maxlen=10000)
        
        # Callbacks
        self.detection_callbacks: List[Callable[[DetectionResult], Awaitable[None]]] = []
        
        logger.info("ThreatDetectionEngine initialized")
    
    async def initialize(self):
        """Initialize all detection components."""
        try:
            # Initialize components
            self.anomaly_detector = get_advanced_detector()
            self.behavioral_analyzer = get_behavioral_analyzer()
            self.threat_intel = get_threat_intelligence()
            self.response_system = get_automated_response()
            self.forensics_logger = get_forensics_logger()
            self.ioc_manager = get_ioc_manager()
            
            # Setup circuit breakers
            self.circuit_breakers = {
                "anomaly_detector": CircuitBreaker("anomaly_detector", failure_threshold=5),
                "behavioral_analyzer": CircuitBreaker("behavioral_analyzer", failure_threshold=5),
                "threat_intel": CircuitBreaker("threat_intel", failure_threshold=5),
                "response_system": CircuitBreaker("response_system", failure_threshold=3)
            }
            
            self.status = EngineStatus.READY
            logger.info("ThreatDetectionEngine ready")
            
        except Exception as e:
            self.status = EngineStatus.ERROR
            logger.error(f"Engine initialization failed: {e}")
            raise
    
    async def start(self):
        """Start the detection engine."""
        if self.status != EngineStatus.READY:
            raise AstraGuardException(
                "Engine not ready. Call initialize() first.",
                component="detection_engine"
            )
        
        self.status = EngineStatus.RUNNING
        
        # Start worker tasks
        for i in range(self.max_workers):
            task = asyncio.create_task(self._detection_worker(f"worker-{i}"))
            self.processing_tasks.append(task)
        
        logger.info(f"Detection engine started with {self.max_workers} workers")
    
    async def stop(self):
        """Stop the detection engine."""
        self.status = EngineStatus.PAUSED
        
        # Cancel worker tasks
        for task in self.processing_tasks:
            task.cancel()
        
        self.processing_tasks.clear()
        
        logger.info("Detection engine stopped")
    
    async def _detection_worker(self, worker_id: str):
        """Detection worker task."""
        logger.info(f"Detection worker {worker_id} started")
        
        while self.status == EngineStatus.RUNNING:
            try:
                # Get item from queue with timeout
                context, data = await asyncio.wait_for(
                    self.detection_queue.get(),
                    timeout=1.0
                )
                
                # Process detection
                await self._process_detection(context, data)
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
    
    async def submit_for_detection(self,
                                   data: Dict[str, Any],
                                   context: Optional[DetectionContext] = None) -> str:
        """
        Submit data for threat detection.
        
        Args:
            data: Data to analyze
            context: Optional detection context
            
        Returns:
            Submission ID
        """
        if not context:
            context = DetectionContext(
                source="api",
                timestamp=datetime.now()
            )
        
        submission_id = f"SUB-{datetime.now().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8]}"
        
        # Add to queue
        try:
            self.detection_queue.put_nowait((context, data))
            logger.debug(f"Submitted for detection: {submission_id}")
            return submission_id
        except asyncio.QueueFull:
            raise AstraGuardException(
                "Detection queue full",
                component="detection_engine"
            )
    
    async def _process_detection(self,
                                  context: DetectionContext,
                                  data: Dict[str, Any]) -> DetectionResult:
        """Process a single detection."""
        start_time = datetime.now()
        detection_id = f"DET-{start_time.strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8]}"
        
        detections = []
        behavioral_result = None
        ioc_matches = []
        response_triggered = False
        response_actions = []
        forensics_event_id = None
        
        try:
            # Step 1: Anomaly Detection
            if self.circuit_breakers["anomaly_detector"].can_execute():
                try:
                    anomaly_results = await self.anomaly_detector.analyze(data)
                    detections.extend(anomaly_results)
                except Exception as e:
                    self.circuit_breakers["anomaly_detector"].record_failure()
                    logger.warning(f"Anomaly detection failed: {e}")
            
            # Step 2: Behavioral Analysis
            if context.entity_id and self.circuit_breakers["behavioral_analyzer"].can_execute():
                try:
                    behavioral_result = await self.behavioral_analyzer.analyze_entity(
                        entity_id=context.entity_id,
                        entity_type=context.entity_type or "unknown",
                        current_data=data
                    )
                    
                    # Convert behavioral anomalies to detections
                    if behavioral_result.result_type.value in ["suspicious", "anomalous"]:
                        detection = ThreatDetection(
                            detection_id=f"BEH-{detection_id}",
                            threat_type=f"behavioral_{behavioral_result.result_type.value}",
                            category=ThreatCategory.BEHAVIORAL_ANOMALY,
                            severity=self._risk_to_severity(behavioral_result.risk_score),
                            confidence=behavioral_result.risk_score,
                            description=f"Behavioral {behavioral_result.result_type.value}: {behavioral_result.reasoning}",
                            affected_entities=[context.entity_id],
                            source_data={"behavioral_analysis": behavioral_result.to_dict()},
                            timestamp=datetime.now()
                        )
                        detections.append(detection)
                        
                except Exception as e:
                    self.circuit_breakers["behavioral_analyzer"].record_failure()
                    logger.warning(f"Behavioral analysis failed: {e}")
            
            # Step 3: IoC Matching
            ioc_matches = self._check_iocs(data, context)
            
            # Step 4: Log to forensics
            if detections or ioc_matches:
                forensics_event = self.forensics_logger.log_threat_detection(
                    detection_id=detection_id,
                    threat_type="multiple" if len(detections) > 1 else (detections[0].threat_type if detections else "ioc_match"),
                    severity="critical" if any(d.severity == ThreatSeverity.CRITICAL for d in detections) else "high",
                    description=f"Detected {len(detections)} threats and {len(ioc_matches)} IoC matches",
                    source_data={
                        "detections": [d.to_dict() for d in detections],
                        "ioc_matches": ioc_matches,
                        "context": context.__dict__
                    },
                    entity_id=context.entity_id
                )
                forensics_event_id = forensics_event.event_id
            
            # Step 5: Automated Response (if enabled)
            if self.mode == DetectionMode.AUTONOMOUS and detections:
                if self.circuit_breakers["response_system"].can_execute():
                    try:
                        for detection in detections:
                            if detection.severity in [ThreatSeverity.CRITICAL, ThreatSeverity.HIGH]:
                                response_result = await self.response_system.execute_response(
                                    detection=detection,
                                    auto_approve=True
                                )
                                response_triggered = True
                                response_actions.append(response_result.response_id)
                                
                    except Exception as e:
                        self.circuit_breakers["response_system"].record_failure()
                        logger.warning(f"Automated response failed: {e}")
            
            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            # Create result
            result = DetectionResult(
                detection_id=detection_id,
                timestamp=start_time,
                detections=detections,
                behavioral_analysis=behavioral_result,
                ioc_matches=ioc_matches,
                response_triggered=response_triggered,
                response_actions=response_actions,
                forensics_event_id=forensics_event_id,
                processing_time_ms=processing_time
            )
            
            # Update statistics
            self.total_processed += 1
            self.total_detections += len(detections)
            if response_triggered:
                self.total_responses += 1
            self.processing_times.append(processing_time)
            self.detection_history.append(result)
            
            # Notify callbacks
            for callback in self.detection_callbacks:
                try:
                    await callback(result)
                except Exception as e:
                    logger.warning(f"Detection callback failed: {e}")
            
            return result
            
        except Exception as e:
            logger.error(f"Detection processing failed: {e}")
            raise
    
    def _check_iocs(self,
                   data: Dict[str, Any],
                   context: DetectionContext) -> List[Dict[str, Any]]:
        """Check for IoC matches in data."""
        matches = []
        
        # Extract potential IoC values from data
        ioc_values = self._extract_ioc_values(data)
        
        for ioc_type, value in ioc_values:
            ioc = self.ioc_manager.find_ioc(ioc_type, value)
            if ioc:
                matches.append({
                    "ioc_id": ioc.ioc_id,
                    "ioc_type": ioc_type,
                    "value": value,
                    "severity": ioc.severity.value,
                    "context": context.source
                })
        
        return matches
    
    def _extract_ioc_values(self, data: Dict[str, Any]) -> List[tuple]:
        """Extract potential IoC values from data."""
        values = []
        
        # Common field names that might contain IoCs
        ioc_fields = {
            "ip_address": ["ip", "source_ip", "destination_ip", "client_ip"],
            "domain": ["domain", "hostname", "url"],
            "file_hash": ["hash", "md5", "sha256", "file_hash"],
            "email_address": ["email", "sender", "recipient"]
        }
        
        for ioc_type, fields in ioc_fields.items():
            for field in fields:
                if field in data:
                    values.append((ioc_type, data[field]))
        
        return values
    
    def _risk_to_severity(self, risk_score: float) -> ThreatSeverity:
        """Convert risk score to threat severity."""
        if risk_score >= 0.9:
            return ThreatSeverity.CRITICAL
        elif risk_score >= 0.7:
            return ThreatSeverity.HIGH
        elif risk_score >= 0.5:
            return ThreatSeverity.MEDIUM
        else:
            return ThreatSeverity.LOW
    
    def register_detection_callback(self, 
                                   callback: Callable[[DetectionResult], Awaitable[None]]):
        """Register a callback for detection results."""
        self.detection_callbacks.append(callback)
        logger.info(f"Registered detection callback: {callback.__name__}")
    
    def get_detection(self, detection_id: str) -> Optional[DetectionResult]:
        """Get detection result by ID."""
        for result in self.detection_history:
            if result.detection_id == detection_id:
                return result
        return None
    
    def get_recent_detections(self,
                              severity: Optional[ThreatSeverity] = None,
                              category: Optional[ThreatCategory] = None,
                              limit: int = 100) -> List[DetectionResult]:
        """Get recent detections with optional filtering."""
        results = list(self.detection_history)
        
        if severity:
            results = [
                r for r in results
                if any(d.severity == severity for d in r.detections)
            ]
        
        if category:
            results = [
                r for r in results
                if any(d.category == category for d in r.detections)
            ]
        
        # Sort by timestamp descending
        results.sort(key=lambda r: r.timestamp, reverse=True)
        
        return results[:limit]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get engine statistics."""
        avg_processing_time = (
            sum(self.processing_times) / len(self.processing_times)
            if self.processing_times else 0
        )
        
        by_severity = {}
        for result in self.detection_history:
            for detection in result.detections:
                sev = detection.severity.value
                by_severity[sev] = by_severity.get(sev, 0) + 1
        
        return {
            "status": self.status.value,
            "mode": self.mode.value,
            "total_processed": self.total_processed,
            "total_detections": self.total_detections,
            "total_responses": self.total_responses,
            "detection_rate": self.total_detections / max(1, self.total_processed),
            "avg_processing_time_ms": avg_processing_time,
            "queue_size": self.detection_queue.qsize(),
            "active_workers": len(self.processing_tasks),
            "by_severity": by_severity,
            "circuit_breaker_status": {
                name: cb.is_open for name, cb in self.circuit_breakers.items()
            }
        }


# Global instance
_detection_engine: Optional[ThreatDetectionEngine] = None


async def get_detection_engine(mode: DetectionMode = DetectionMode.ACTIVE) -> ThreatDetectionEngine:
    """Get global detection engine instance."""
    global _detection_engine
    if _detection_engine is None:
        _detection_engine = ThreatDetectionEngine(mode=mode)
        await _detection_engine.initialize()
    return _detection_engine
