"""
Automated Response System for Threat Detection

Orchestrates automated responses to detected threats including
alerting, containment, and mitigation actions.
"""

import asyncio
from typing import Dict, List, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
from collections import deque
import uuid

from .advanced_anomaly_detector import ThreatDetection, ThreatSeverity, ThreatCategory
from core.error_handling import safe_execute, AstraGuardException, async_retry
from core.timeout_handler import async_timeout
from core.circuit_breaker import CircuitBreaker, register_circuit_breaker

logger = logging.getLogger(__name__)


class ResponseStatus(Enum):
    """Status of a response action."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ResponsePriority(Enum):
    """Priority levels for response actions."""
    CRITICAL = 1  # Immediate response required
    HIGH = 2      # Response within 1 minute
    MEDIUM = 3    # Response within 5 minutes
    LOW = 4       # Response within 15 minutes


@dataclass
class ResponseAction:
    """Definition of a response action."""
    action_id: str
    name: str
    description: str
    priority: ResponsePriority
    max_execution_time: int  # seconds
    requires_approval: bool
    auto_execute_severity: List[ThreatSeverity] = field(default_factory=list)
    action_func: Optional[Callable[..., Awaitable[bool]]] = None
    
    async def execute(self, context: Dict[str, Any]) -> bool:
        """Execute the response action."""
        if self.action_func:
            return await self.action_func(context)
        return False


@dataclass
class ResponseResult:
    """Result of a response execution."""
    response_id: str
    detection_id: str
    action_id: str
    status: ResponseStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    success: bool = False
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "response_id": self.response_id,
            "detection_id": self.detection_id,
            "action_id": self.action_id,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "success": self.success,
            "message": self.message,
            "details": self.details
        }


@dataclass
class ResponsePlaybook:
    """Playbook defining responses for a threat type."""
    playbook_id: str
    name: str
    description: str
    threat_categories: List[ThreatCategory]
    severity_levels: List[ThreatSeverity]
    actions: List[str]  # List of action_ids
    execution_mode: str = "sequential"  # or "parallel"
    enabled: bool = True
    
    def matches(self, detection: ThreatDetection) -> bool:
        """Check if playbook matches a detection."""
        category_match = detection.category in self.threat_categories
        severity_match = detection.severity in self.severity_levels
        return category_match and severity_match and self.enabled


class AutomatedResponseSystem:
    """
    Automated response system for threat detection.
    
    Orchestrates response actions based on detected threats,
    with support for playbooks, approval workflows, and
    execution tracking.
    """
    
    # Response time targets by priority (seconds)
    RESPONSE_TARGETS = {
        ResponsePriority.CRITICAL: 5,
        ResponsePriority.HIGH: 60,
        ResponsePriority.MEDIUM: 300,
        ResponsePriority.LOW: 900
    }
    
    def __init__(self):
        self.actions: Dict[str, ResponseAction] = {}
        self.playbooks: Dict[str, ResponsePlaybook] = {}
        self.response_history: deque = deque(maxlen=10000)
        self.pending_approvals: Dict[str, ResponseResult] = {}
        
        # Execution tracking
        self.execution_count = 0
        self.success_count = 0
        self.failure_count = 0
        
        # Circuit breaker for response execution
        self.response_circuit = register_circuit_breaker(
            CircuitBreaker(
                name="automated_response",
                failure_threshold=5,
                success_threshold=2,
                recovery_timeout=60,
                expected_exceptions=(Exception,)
            )
        )
        
        # Approval callback (set externally)
        self.approval_callback: Optional[Callable[[ResponseResult], Awaitable[bool]]] = None
        
    def register_action(self, action: ResponseAction):
        """Register a response action."""
        self.actions[action.action_id] = action
        logger.info(f"Registered response action: {action.action_id}")
    
    def register_playbook(self, playbook: ResponsePlaybook):
        """Register a response playbook."""
        self.playbooks[playbook.playbook_id] = playbook
        logger.info(f"Registered response playbook: {playbook.playbook_id}")
    
    async def process_detection(self, detection: ThreatDetection) -> List[ResponseResult]:
        """
        Process a threat detection and execute appropriate responses.
        
        Args:
            detection: Threat detection result
            
        Returns:
            List of response results
        """
        logger.info(
            f"Processing detection {detection.detection_id} - "
            f"Category: {detection.category.value}, "
            f"Severity: {detection.severity.value}"
        )
        
        results = []
        
        # Find matching playbooks
        matching_playbooks = [
            pb for pb in self.playbooks.values()
            if pb.matches(detection)
        ]
        
        if not matching_playbooks:
            logger.info(f"No matching playbooks for detection {detection.detection_id}")
            return results
        
        # Execute playbooks
        for playbook in matching_playbooks:
            playbook_results = await self._execute_playbook(playbook, detection)
            results.extend(playbook_results)
        
        return results
    
    async def _execute_playbook(self, 
                                 playbook: ResponsePlaybook,
                                 detection: ThreatDetection) -> List[ResponseResult]:
        """Execute a response playbook."""
        logger.info(f"Executing playbook {playbook.playbook_id} for {detection.detection_id}")
        
        results = []
        
        # Get actions
        actions = [
            self.actions.get(action_id)
            for action_id in playbook.actions
            if action_id in self.actions
        ]
        
        # Sort by priority
        actions.sort(key=lambda a: a.priority.value)
        
        if playbook.execution_mode == "sequential":
            # Execute sequentially
            for action in actions:
                result = await self._execute_action(action, detection)
                results.append(result)
                
                # Stop on failure for critical actions
                if not result.success and action.priority == ResponsePriority.CRITICAL:
                    logger.warning(f"Critical action failed, stopping playbook execution")
                    break
        
        else:  # parallel
            # Execute in parallel
            tasks = [
                self._execute_action(action, detection)
                for action in actions
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out exceptions
            results = [
                r for r in results 
                if isinstance(r, ResponseResult)
            ]
        
        return results
    
    async def _execute_action(self,
                             action: ResponseAction,
                             detection: ThreatDetection) -> ResponseResult:
        """Execute a single response action."""
        response_id = str(uuid.uuid4())
        
        result = ResponseResult(
            response_id=response_id,
            detection_id=detection.detection_id,
            action_id=action.action_id,
            status=ResponseStatus.PENDING,
            started_at=datetime.now()
        )
        
        # Check if approval required
        if action.requires_approval and detection.severity not in action.auto_execute_severity:
            result.status = ResponseStatus.PENDING
            self.pending_approvals[response_id] = result
            
            logger.info(f"Action {action.action_id} requires approval for {detection.detection_id}")
            
            # Request approval
            if self.approval_callback:
                approved = await self.approval_callback(result)
                if not approved:
                    result.status = ResponseStatus.CANCELLED
                    result.message = "Cancelled - approval denied"
                    self.response_history.append(result)
                    return result
            
            result.status = ResponseStatus.IN_PROGRESS
        
        # Execute action
        result.status = ResponseStatus.IN_PROGRESS
        
        try:
            # Execute with timeout and circuit breaker
            success = await self.response_circuit.call(
                self._execute_with_timeout,
                action,
                detection,
                result
            )
            
            result.success = success
            result.status = ResponseStatus.SUCCESS if success else ResponseStatus.FAILED
            result.message = "Action executed successfully" if success else "Action execution failed"
            
            if success:
                self.success_count += 1
            else:
                self.failure_count += 1
                
        except asyncio.TimeoutError:
            result.status = ResponseStatus.FAILED
            result.success = False
            result.message = f"Action timed out after {action.max_execution_time}s"
            self.failure_count += 1
            
        except Exception as e:
            result.status = ResponseStatus.FAILED
            result.success = False
            result.message = f"Action failed: {str(e)}"
            self.failure_count += 1
            logger.error(f"Action {action.action_id} failed: {e}")
        
        finally:
            result.completed_at = datetime.now()
            self.execution_count += 1
            self.response_history.append(result)
        
        return result
    
    async def _execute_with_timeout(self,
                                   action: ResponseAction,
                                   detection: ThreatDetection,
                                   result: ResponseResult) -> bool:
        """Execute action with timeout."""
        # Create context for action
        context = {
            "detection": detection.to_dict(),
            "response_id": result.response_id,
            "timestamp": datetime.now().isoformat()
        }
        
        # Execute with timeout
        return await asyncio.wait_for(
            action.execute(context),
            timeout=action.max_execution_time
        )
    
    def approve_response(self, response_id: str, approved: bool = True) -> bool:
        """Approve or reject a pending response."""
        if response_id not in self.pending_approvals:
            return False
        
        result = self.pending_approvals[response_id]
        
        if approved:
            result.status = ResponseStatus.IN_PROGRESS
            logger.info(f"Response {response_id} approved")
        else:
            result.status = ResponseStatus.CANCELLED
            result.message = "Cancelled by operator"
            self.response_history.append(result)
            logger.info(f"Response {response_id} rejected")
        
        del self.pending_approvals[response_id]
        return True
    
    def get_pending_approvals(self) -> List[ResponseResult]:
        """Get all pending approval requests."""
        return list(self.pending_approvals.values())
    
    def get_response_history(self,
                            detection_id: Optional[str] = None,
                            limit: int = 100) -> List[ResponseResult]:
        """Get response history with optional filtering."""
        history = list(self.response_history)
        
        if detection_id:
            history = [r for r in history if r.detection_id == detection_id]
        
        # Sort by started_at descending
        history.sort(key=lambda r: r.started_at, reverse=True)
        
        return history[:limit]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get response system statistics."""
        recent_history = list(self.response_history)[-1000:]
        
        by_status = {}
        for result in recent_history:
            status = result.status.value
            by_status[status] = by_status.get(status, 0) + 1
        
        avg_response_time = 0.0
        response_times = []
        for result in recent_history:
            if result.completed_at and result.started_at:
                response_time = (result.completed_at - result.started_at).total_seconds()
                response_times.append(response_time)
        
        if response_times:
            avg_response_time = sum(response_times) / len(response_times)
        
        return {
            "total_executions": self.execution_count,
            "successful": self.success_count,
            "failed": self.failure_count,
            "success_rate": self.success_count / max(1, self.execution_count),
            "pending_approvals": len(self.pending_approvals),
            "by_status": by_status,
            "average_response_time_seconds": avg_response_time,
            "actions_registered": len(self.actions),
            "playbooks_registered": len(self.playbooks)
        }


# Global instance
_response_system: Optional[AutomatedResponseSystem] = None


def get_automated_response_system() -> AutomatedResponseSystem:
    """Get global automated response system instance."""
    global _response_system
    if _response_system is None:
        _response_system = AutomatedResponseSystem()
    return _response_system
