"""
Mitigation Engine for Threat Response

Executes mitigation actions to contain and remediate threats.
Provides rollback capabilities and effectiveness tracking.
"""

import asyncio
from typing import Dict, List, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
from collections import deque
import uuid

from core.error_handling import safe_execute, AstraGuardException
from core.timeout_handler import async_timeout

logger = logging.getLogger(__name__)


class MitigationStatus(Enum):
    """Status of a mitigation action."""
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class MitigationType(Enum):
    """Types of mitigation actions."""
    CONTAINMENT = "containment"       # Isolate/limit spread
    ERADICATION = "eradication"      # Remove threat
    RECOVERY = "recovery"             # Restore normal operation
    PREVENTION = "prevention"         # Prevent recurrence


@dataclass
class MitigationAction:
    """Definition of a mitigation action."""
    action_id: str
    name: str
    description: str
    mitigation_type: MitigationType
    action_func: Callable[[Dict[str, Any]], Awaitable[bool]]
    rollback_func: Optional[Callable[[Dict[str, Any]], Awaitable[bool]]] = None
    max_duration: int = 300  # seconds
    requires_approval: bool = False
    
    async def execute(self, context: Dict[str, Any]) -> bool:
        """Execute the mitigation action."""
        return await self.action_func(context)
    
    async def rollback(self, context: Dict[str, Any]) -> bool:
        """Rollback the mitigation action."""
        if self.rollback_func:
            return await self.rollback_func(context)
        return False


@dataclass
class MitigationResult:
    """Result of a mitigation execution."""
    mitigation_id: str
    threat_id: str
    action_id: str
    status: MitigationStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    success: bool = False
    message: str = ""
    rollback_available: bool = False
    rollback_performed: bool = False
    effectiveness_score: float = 0.0  # 0-1 scale
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "mitigation_id": self.mitigation_id,
            "threat_id": self.threat_id,
            "action_id": self.action_id,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "success": self.success,
            "message": self.message,
            "rollback_available": self.rollback_available,
            "rollback_performed": self.rollback_performed,
            "effectiveness_score": self.effectiveness_score,
            "details": self.details
        }


class MitigationEngine:
    """
    Mitigation engine for executing threat containment and remediation.
    
    Manages mitigation actions, tracks effectiveness, and provides
    rollback capabilities for failed mitigations.
    """
    
    def __init__(self):
        self.actions: Dict[str, MitigationAction] = {}
        self.active_mitigations: Dict[str, MitigationResult] = {}
        self.mitigation_history: deque = deque(maxlen=10000)
        
        # Effectiveness tracking
        self.effectiveness_scores: Dict[str, List[float]] = {}
        
        # Statistics
        self.total_executed = 0
        self.successful = 0
        self.failed = 0
        self.rolled_back = 0
        
    def register_action(self, action: MitigationAction):
        """Register a mitigation action."""
        self.actions[action.action_id] = action
        logger.info(f"Registered mitigation action: {action.action_id}")
    
    async def execute_mitigation(self,
                               threat_id: str,
                               action_id: str,
                               context: Dict[str, Any],
                               approve: bool = False) -> MitigationResult:
        """
        Execute a mitigation action for a threat.
        
        Args:
            threat_id: ID of the threat to mitigate
            action_id: ID of the mitigation action
            context: Execution context
            approve: Whether to auto-approve if approval required
            
        Returns:
            MitigationResult
        """
        action = self.actions.get(action_id)
        if not action:
            raise AstraGuardException(
                f"Mitigation action not found: {action_id}",
                component="mitigation_engine"
            )
        
        # Check approval
        if action.requires_approval and not approve:
            result = MitigationResult(
                mitigation_id=str(uuid.uuid4()),
                threat_id=threat_id,
                action_id=action_id,
                status=MitigationStatus.PLANNED,
                started_at=datetime.now(),
                message="Awaiting approval",
                rollback_available=action.rollback_func is not None
            )
            self.active_mitigations[result.mitigation_id] = result
            return result
        
        # Execute
        return await self._run_mitigation(threat_id, action, context)
    
    async def _run_mitigation(self,
                             threat_id: str,
                             action: MitigationAction,
                             context: Dict[str, Any]) -> MitigationResult:
        """Run a mitigation action."""
        mitigation_id = str(uuid.uuid4())
        
        result = MitigationResult(
            mitigation_id=mitigation_id,
            threat_id=threat_id,
            action_id=action.action_id,
            status=MitigationStatus.IN_PROGRESS,
            started_at=datetime.now(),
            rollback_available=action.rollback_func is not None
        )
        
        self.active_mitigations[mitigation_id] = result
        
        try:
            # Execute with timeout
            success = await asyncio.wait_for(
                action.execute(context),
                timeout=action.max_duration
            )
            
            result.success = success
            result.status = MitigationStatus.SUCCESS if success else MitigationStatus.FAILED
            result.message = "Mitigation executed successfully" if success else "Mitigation failed"
            result.completed_at = datetime.now()
            
            if success:
                self.successful += 1
            else:
                self.failed += 1
            
            # Calculate initial effectiveness
            result.effectiveness_score = 1.0 if success else 0.0
            
        except asyncio.TimeoutError:
            result.status = MitigationStatus.FAILED
            result.success = False
            result.message = f"Mitigation timed out after {action.max_duration}s"
            result.completed_at = datetime.now()
            self.failed += 1
            
        except Exception as e:
            result.status = MitigationStatus.FAILED
            result.success = False
            result.message = f"Mitigation error: {str(e)}"
            result.completed_at = datetime.now()
            self.failed += 1
            logger.error(f"Mitigation {mitigation_id} failed: {e}")
        
        finally:
            self.total_executed += 1
            self.mitigation_history.append(result)
            
            # Track effectiveness
            if action.action_id not in self.effectiveness_scores:
                self.effectiveness_scores[action.action_id] = []
            self.effectiveness_scores[action.action_id].append(result.effectiveness_score)
        
        return result
    
    async def rollback_mitigation(self, mitigation_id: str) -> bool:
        """
        Rollback a mitigation action.
        
        Args:
            mitigation_id: ID of the mitigation to rollback
            
        Returns:
            True if rollback successful
        """
        result = self.active_mitigations.get(mitigation_id)
        if not result:
            logger.error(f"Mitigation not found: {mitigation_id}")
            return False
        
        if not result.rollback_available:
            logger.error(f"Rollback not available for mitigation: {mitigation_id}")
            return False
        
        action = self.actions.get(result.action_id)
        if not action or not action.rollback_func:
            return False
        
        try:
            context = result.details.get("context", {})
            success = await action.rollback(context)
            
            if success:
                result.rollback_performed = True
                result.status = MitigationStatus.ROLLED_BACK
                result.message = "Mitigation rolled back"
                self.rolled_back += 1
                logger.info(f"Mitigation {mitigation_id} rolled back successfully")
            else:
                logger.error(f"Rollback failed for mitigation: {mitigation_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Rollback error for {mitigation_id}: {e}")
            return False
    
    def update_effectiveness(self, mitigation_id: str, score: float):
        """
        Update effectiveness score for a mitigation.
        
        Args:
            mitigation_id: ID of the mitigation
            score: Effectiveness score (0-1)
        """
        result = self.active_mitigations.get(mitigation_id)
        if result:
            result.effectiveness_score = max(0.0, min(1.0, score))
            
            # Update tracking
            action_scores = self.effectiveness_scores.get(result.action_id, [])
            if action_scores:
                action_scores[-1] = result.effectiveness_score
    
    def get_action_effectiveness(self, action_id: str) -> float:
        """Get average effectiveness for an action."""
        scores = self.effectiveness_scores.get(action_id, [])
        if not scores:
            return 0.5  # Default neutral score
        
        return sum(scores) / len(scores)
    
    def get_best_actions(self, 
                        mitigation_type: Optional[MitigationType] = None,
                        count: int = 5) -> List[str]:
        """
        Get best performing mitigation actions.
        
        Returns:
            List of action IDs sorted by effectiveness
        """
        action_scores = []
        
        for action_id, action in self.actions.items():
            if mitigation_type and action.mitigation_type != mitigation_type:
                continue
            
            effectiveness = self.get_action_effectiveness(action_id)
            action_scores.append((action_id, effectiveness))
        
        # Sort by effectiveness descending
        action_scores.sort(key=lambda x: x[1], reverse=True)
        
        return [action_id for action_id, _ in action_scores[:count]]
    
    def get_active_mitigations(self, 
                              threat_id: Optional[str] = None) -> List[MitigationResult]:
        """Get active mitigations with optional filtering."""
        mitigations = list(self.active_mitigations.values())
        
        if threat_id:
            mitigations = [m for m in mitigations if m.threat_id == threat_id]
        
        return [m for m in mitigations if m.status == MitigationStatus.IN_PROGRESS]
    
    def get_mitigation_history(self,
                              threat_id: Optional[str] = None,
                              limit: int = 100) -> List[MitigationResult]:
        """Get mitigation history with optional filtering."""
        history = list(self.mitigation_history)
        
        if threat_id:
            history = [m for m in history if m.threat_id == threat_id]
        
        # Sort by started_at descending
        history.sort(key=lambda m: m.started_at, reverse=True)
        
        return history[:limit]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get mitigation engine statistics."""
        by_type = {}
        for result in self.mitigation_history:
            action = self.actions.get(result.action_id)
            if action:
                mtype = action.mitigation_type.value
                if mtype not in by_type:
                    by_type[mtype] = {"total": 0, "success": 0}
                by_type[mtype]["total"] += 1
                if result.success:
                    by_type[mtype]["success"] += 1
        
        # Calculate success rates by type
        for mtype in by_type:
            total = by_type[mtype]["total"]
            success = by_type[mtype]["success"]
            by_type[mtype]["success_rate"] = success / total if total > 0 else 0
        
        return {
            "total_executed": self.total_executed,
            "successful": self.successful,
            "failed": self.failed,
            "rolled_back": self.rolled_back,
            "success_rate": self.successful / max(1, self.total_executed),
            "active_mitigations": len(self.get_active_mitigations()),
            "by_type": by_type,
            "action_effectiveness": {
                action_id: self.get_action_effectiveness(action_id)
                for action_id in self.actions.keys()
            }
        }


# Standard mitigation actions
async def mitigate_isolate_network(context: Dict[str, Any]) -> bool:
    """Mitigation: Isolate system from network."""
    try:
        system_id = context.get("system_id")
        logger.warning(f"Isolating system from network: {system_id}")
        # Production: Implement actual network isolation
        return True
    except Exception as e:
        logger.error(f"Network isolation failed: {e}")
        return False


async def rollback_isolate_network(context: Dict[str, Any]) -> bool:
    """Rollback: Restore network connectivity."""
    try:
        system_id = context.get("system_id")
        logger.info(f"Restoring network connectivity: {system_id}")
        # Production: Implement actual network restoration
        return True
    except Exception as e:
        logger.error(f"Network restoration failed: {e}")
        return False


async def mitigate_kill_malware(context: Dict[str, Any]) -> bool:
    """Mitigation: Kill malware processes."""
    try:
        process_ids = context.get("process_ids", [])
        logger.warning(f"Killing malware processes: {process_ids}")
        # Production: Implement actual process termination
        return True
    except Exception as e:
        logger.error(f"Malware process termination failed: {e}")
        return False


async def mitigate_block_attacker(context: Dict[str, Any]) -> bool:
    """Mitigation: Block attacker IP/connection."""
    try:
        attacker_ip = context.get("attacker_ip")
        logger.warning(f"Blocking attacker: {attacker_ip}")
        # Production: Implement actual IP blocking
        return True
    except Exception as e:
        logger.error(f"Attacker blocking failed: {e}")
        return False


async def rollback_block_attacker(context: Dict[str, Any]) -> bool:
    """Rollback: Unblock IP."""
    try:
        attacker_ip = context.get("attacker_ip")
        logger.info(f"Unblocking IP: {attacker_ip}")
        # Production: Implement actual IP unblock
        return True
    except Exception as e:
        logger.error(f"IP unblock failed: {e}")
        return False


async def mitigate_disable_compromised_account(context: Dict[str, Any]) -> bool:
    """Mitigation: Disable compromised account."""
    try:
        account = context.get("account")
        logger.warning(f"Disabling compromised account: {account}")
        # Production: Implement actual account disable
        return True
    except Exception as e:
        logger.error(f"Account disable failed: {e}")
        return False


async def rollback_disable_account(context: Dict[str, Any]) -> bool:
    """Rollback: Re-enable account."""
    try:
        account = context.get("account")
        logger.info(f"Re-enabling account: {account}")
        # Production: Implement actual account re-enable
        return True
    except Exception as e:
        logger.error(f"Account re-enable failed: {e}")
        return False


async def mitigate_restore_from_backup(context: Dict[str, Any]) -> bool:
    """Mitigation: Restore from backup."""
    try:
        system_id = context.get("system_id")
        backup_point = context.get("backup_point")
        logger.warning(f"Restoring {system_id} from backup: {backup_point}")
        # Production: Implement actual backup restoration
        return True
    except Exception as e:
        logger.error(f"Backup restoration failed: {e}")
        return False


# Standard action definitions
STANDARD_MITIGATION_ACTIONS = {
    "isolate_network": MitigationAction(
        action_id="isolate_network",
        name="Isolate Network",
        description="Isolate affected system from network",
        mitigation_type=MitigationType.CONTAINMENT,
        action_func=mitigate_isolate_network,
        rollback_func=rollback_isolate_network,
        max_duration=30,
        requires_approval=True
    ),
    
    "kill_malware": MitigationAction(
        action_id="kill_malware",
        name="Kill Malware Processes",
        description="Terminate identified malware processes",
        mitigation_type=MitigationType.ERADICATION,
        action_func=mitigate_kill_malware,
        max_duration=10,
        requires_approval=False
    ),
    
    "block_attacker": MitigationAction(
        action_id="block_attacker",
        name="Block Attacker",
        description="Block attacker IP address or connection",
        mitigation_type=MitigationType.CONTAINMENT,
        action_func=mitigate_block_attacker,
        rollback_func=rollback_block_attacker,
        max_duration=15,
        requires_approval=False
    ),
    
    "disable_compromised_account": MitigationAction(
        action_id="disable_compromised_account",
        name="Disable Compromised Account",
        description="Disable compromised user account",
        mitigation_type=MitigationType.CONTAINMENT,
        action_func=mitigate_disable_compromised_account,
        rollback_func=rollback_disable_account,
        max_duration=10,
        requires_approval=True
    ),
    
    "restore_from_backup": MitigationAction(
        action_id="restore_from_backup",
        name="Restore from Backup",
        description="Restore system from clean backup",
        mitigation_type=MitigationType.RECOVERY,
        action_func=mitigate_restore_from_backup,
        max_duration=600,
        requires_approval=True
    )
}


def register_standard_mitigations(engine: MitigationEngine):
    """Register standard mitigation actions."""
    for action in STANDARD_MITIGATION_ACTIONS.values():
        engine.register_action(action)
        logger.info(f"Registered mitigation: {action.action_id}")
    
    logger.info("All standard mitigations registered")


# Global instance
_mitigation_engine: Optional[MitigationEngine] = None


def get_mitigation_engine() -> MitigationEngine:
    """Get global mitigation engine instance."""
    global _mitigation_engine
    if _mitigation_engine is None:
        _mitigation_engine = MitigationEngine()
    return _mitigation_engine
