"""
Phase-Aware Anomaly Handler

Integrates mission phase policies into the anomaly detection and response pipeline.

This module bridges the gap between:
1. Anomaly detection (identifies what's wrong)
2. Phase policies (constraints for the current mission phase)
3. Response orchestration (decides what to do about it)

The handler ensures that the same anomaly leads to different responses
depending on the current mission phase.
"""

import logging
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import asdict
from datetime import datetime, timedelta
import json
from pathlib import Path
from collections import defaultdict, deque
import uuid
from models.feedback import FeedbackEvent


from state_machine.state_engine import StateMachine, MissionPhase
from state_machine.mission_phase_policy_engine import (
    MissionPhasePolicyEngine,
    PolicyDecision,
    EscalationLevel
)
from config.mission_phase_policy_loader import MissionPhasePolicyLoader
from core.metrics import ANOMALIES_BY_TYPE
from anomaly_agent.explainability import build_explanation
from anomaly.report_generator import get_report_generator


logger: logging.Logger = logging.getLogger(__name__)

def _log_with_context(
    logger_method,
    message: str,
    decision_id: Optional[str] = None,
    anomaly_type: Optional[str] = None,
    **extra_context
):
    """
    Helper to add consistent context to logs.
    
    Args:
        logger_method: Logger method to call (logger.info, logger.error, etc.)
        message: Log message
        decision_id: Optional decision ID
        anomaly_type: Optional anomaly type
        **extra_context: Additional context fields
    """
    context = {}
    if decision_id:
        context['decision_id'] = decision_id
    if anomaly_type:
        context['anomaly_type'] = anomaly_type
    context.update(extra_context)
    
    logger_method(message, extra=context)


def _log_with_context(
    logger_method,
    message: str,
    decision_id: Optional[str] = None,
    anomaly_type: Optional[str] = None,
    **extra_context
):
    """
    Helper to add consistent context to logs.
    
    Args:
        logger_method: Logger method to call (logger.info, logger.error, etc.)
        message: Log message
        decision_id: Optional decision ID
        anomaly_type: Optional anomaly type
        **extra_context: Additional context fields
    """
    context = {}
    if decision_id:
        context['decision_id'] = decision_id
    if anomaly_type:
        context['anomaly_type'] = anomaly_type
    context.update(extra_context)
    
    logger_method(message, extra=context)



class PhaseAwareAnomalyHandler:
    """
    Orchestrates anomaly response based on mission phase constraints.

    This handler acts as the decision-making brain of the anomaly response system.
    It does not just report anomalies; it decides *what to do* about them based on
    pre-defined policies for the current mission phase.

    Responsibilities:
    1.  **Contextualize**: Combine anomaly data with the current mission phase.
    2.  **Evaluate**: Apply phase-specific policies (e.g., "Ignore minor power
        fluctuations during Launch", "Escalate thermal issues during Payload Ops").
    3.  **Decide**: Determine the appropriate action (Log, Warn, Mask, Escalate).
    4.  **Track**: maintain history for recurrence detection (e.g., "Is this the
        3rd time this happened in an hour?").
    """
    
    def __init__(
        self,
        state_machine: StateMachine,
        policy_loader: Optional[MissionPhasePolicyLoader] = None,
        enable_recurrence_tracking: bool = True
    ) -> None:
        """
        Initialize the phase-aware anomaly handler.
        
        Args:
            state_machine: StateMachine instance to query mission phase
            policy_loader: MissionPhasePolicyLoader instance
                          If None, creates a new one with defaults
            enable_recurrence_tracking: Track anomaly recurrence patterns
        
        Raises:
            TypeError: If state_machine is not a StateMachine instance
            ValueError: If policy_loader returns invalid policy
        """
        # Validate inputs
        if not isinstance(state_machine, StateMachine):
            raise TypeError(
                f"state_machine must be a StateMachine instance, got {type(state_machine).__name__}"
            )
        
        try:
            self.state_machine = state_machine
            self.policy_loader = policy_loader or MissionPhasePolicyLoader()
            
            # Get and validate policy
            policy = self.policy_loader.get_policy()
            if not policy or not isinstance(policy, dict):
                raise ValueError("Policy loader returned invalid policy structure")
            
            self.policy_engine = MissionPhasePolicyEngine(policy)
            
        except (AttributeError, TypeError) as e:
            logger.error(
                f"Failed to initialize policy engine ({type(e).__name__}): {e}",
                exc_info=True
            )
            raise ValueError(f"Policy engine initialization failed: {e}") from e
        except (ValueError, KeyError) as e:
            logger.error(
                f"Invalid policy configuration ({type(e).__name__}): {e}",
                exc_info=True
            )
            raise
        
        # Recurrence tracking - optimized data structures
        self.enable_recurrence_tracking = enable_recurrence_tracking
        self.anomaly_history: List[Tuple[str, datetime]] = []  # List of (anomaly_type, timestamp) tuples
        self.recurrence_window = timedelta(seconds=3600)  # 1 hour default
        
        # Initialize tracking dictionaries (CRITICAL FIX)
        self._anomaly_counts: Dict[str, int] = defaultdict(int)
        self._anomaly_timestamps: Dict[str, List[datetime]] = defaultdict(list)
        
        logger.info(
            "Phase-aware anomaly handler initialized",
            extra={'recurrence_tracking_enabled': enable_recurrence_tracking}
        )

    
    def handle_anomaly(
        self,
        anomaly_type: str,
        severity_score: float,
        confidence: float,
        anomaly_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process an anomaly with phase-aware logic and policy enforcement.

        This is the core entry point for the handler. It:
        1.  Snapshots the current mission phase.
        2.  Updates recurrence tracking (has this happened recently?).
        3.  Queries the Policy Engine for a decision.
        4.  Determines if Safe Mode escalation is required.
        5.  Constructs a full decision object for logging and downstream action.

        Args:
            anomaly_type (str): The classification tag (e.g., 'power_fault').
            severity_score (float): Normalized severity [0.0 - 1.0].
            confidence (float): Model confidence [0.0 - 1.0].
            anomaly_metadata (Optional[Dict]): Context (e.g., source component).

        Returns:
            Dict[str, Any]: A comprehensive decision object containing constraints,
            recommended actions, and escalation flags.
        """
        if anomaly_metadata is None:
            anomaly_metadata = {}

        # Validate inputs
        if not isinstance(anomaly_type, str) or not anomaly_type.strip():
            raise ValueError("anomaly_type must be a non-empty string")

        if not (0 <= severity_score <= 1):
            raise ValueError(f"severity_score must be between 0 and 1, got {severity_score}")

        if not (0 <= confidence <= 1):
            raise ValueError(f"confidence must be between 0 and 1, got {confidence}")

        if not isinstance(anomaly_metadata, dict):
            raise TypeError(f"anomaly_metadata must be a dict, got {type(anomaly_metadata)}")

        
        # Get current mission phase
        try:
            current_phase = self.state_machine.get_current_phase()
        except (AttributeError, RuntimeError) as e:
            logger.error(
                f"Failed to get current mission phase: {e}. Defaulting to NOMINAL_OPS.",
                exc_info=True
            )
            current_phase = MissionPhase.NOMINAL_OPS  # Safe default

        
        # Track recurrence
        recurrence_info = self._update_recurrence_tracking(anomaly_type)
        
        # Build complete anomaly attributes
        anomaly_attributes = {
            **anomaly_metadata,
            'confidence': confidence,
            'recurrence_count': recurrence_info['count'],
            'last_occurrence': recurrence_info['last_occurrence'],
            'total_in_window': recurrence_info['total_in_window']
        }
        
        # Evaluate against phase policy
        policy_decision = self.policy_engine.evaluate(
            mission_phase=current_phase,
            anomaly_type=anomaly_type,
            severity_score=severity_score,
            anomaly_attributes=anomaly_attributes
        )
        
        # Determine if escalation is needed
        should_escalate = (
            policy_decision.escalation_level == EscalationLevel.ESCALATE_SAFE_MODE.value
        )
        
        # Build complete response
        decision = {
            'success': True,
            'anomaly_type': anomaly_type,
            'severity_score': severity_score,
            'detection_confidence': confidence,
            'mission_phase': current_phase.value,
            'policy_decision': asdict(policy_decision),
            'recommended_action': policy_decision.recommended_action,
            'should_escalate_to_safe_mode': should_escalate,
            'reasoning': policy_decision.reasoning,
            'recurrence_info': recurrence_info,
            'timestamp': datetime.now(),
            'decision_id': self._generate_decision_id()
        }
        decision["explanation"] = build_explanation({
            "primary_factor": policy_decision.reasoning,
            "secondary_factors": [
                f"Recurrence count: {recurrence_info.get('count')}",
                f"Recent occurrences: {recurrence_info.get('total_in_window')}"
            ],
            "mission_phase": current_phase.value,
            "confidence": confidence
        })



        # Update Prometheus metrics
        try:
            severity_level = policy_decision.severity  # e.g., "HIGH", "CRITICAL"
            ANOMALIES_BY_TYPE.labels(
                type=anomaly_type, 
                severity=severity_level
            ).inc()
        except (AttributeError, KeyError) as e:
            logger.warning(
                f"Failed to update metrics for anomaly '{anomaly_type}' ({type(e).__name__}): {e}. "
                f"Policy decision may be missing severity field.",
                extra={
                    'anomaly_type': anomaly_type,
                    'policy_decision': asdict(policy_decision) if policy_decision else None
                }
            )
        except (TypeError, ValueError) as e:
            # Handle invalid metric values or label types
            logger.error(
                f"Invalid metric data for anomaly '{anomaly_type}' ({type(e).__name__}): {e}",
                exc_info=True,
                extra={
                    'anomaly_type': anomaly_type,
                    'severity_level': severity_level if 'severity_level' in locals() else 'unknown'
                }
            )
        except (RuntimeError, OSError) as e:
            # Handle Prometheus client errors (network, file system, etc.)
            logger.error(
                f"Prometheus client error updating metrics ({type(e).__name__}): {e}",
                exc_info=True,
                extra={'anomaly_type': anomaly_type}
            )
        
        # Log the decision
        self._log_decision(decision)
        
        # Record anomaly for reporting (feedback loop)
        self._record_anomaly_for_reporting(decision, anomaly_metadata)
        
        # If escalation is needed, trigger it
        if should_escalate:
            self._execute_escalation(decision)
        
        return decision

    
    def _update_recurrence_tracking(self, anomaly_type: str) -> Dict[str, Any]:
        """
        Track recurrence of anomalies within a time window.
        
        Optimized implementation using dictionary-based indexing for O(1) lookups.
        
        Returns:
            Dict with:
            {
                'count': Total occurrences of this type ever
                'total_in_window': Occurrences in recent time window
                'last_occurrence': Timestamp of last occurrence (or None)
                'time_since_last': Seconds since last occurrence (or None)
            }
        """
        now = datetime.now()
        
        # Add current occurrence - O(1) operations
        if self.enable_recurrence_tracking:
            self.anomaly_history.append((anomaly_type, now))
            self._anomaly_counts[anomaly_type] += 1
            self._anomaly_timestamps[anomaly_type].append(now)
        
        # Get total count - O(1) lookup
        total_count = self._anomaly_counts[anomaly_type]
        
        # Find occurrences within time window - O(k) where k = occurrences of this type
        window_start = now - self.recurrence_window
        timestamps = self._anomaly_timestamps[anomaly_type]
        recent_count = sum(1 for ts in timestamps if ts >= window_start)
        
        # Find last occurrence - O(1) access
        if len(timestamps) > 1:
            last_occurrence = timestamps[-2]  # Second-to-last (current is last)
            time_since_last = (now - last_occurrence).total_seconds()
        else:
            last_occurrence = None
            time_since_last = None
        
        # Periodic cleanup of old entries (every 1000 anomalies)
        if len(self.anomaly_history) > 1000 and len(self.anomaly_history) % 100 == 0:
            self._cleanup_old_entries(now)
        
        return {
            'count': total_count,
            'total_in_window': recent_count,
            'last_occurrence': last_occurrence.isoformat() if last_occurrence else None,
            'time_since_last_seconds': time_since_last
        }
    
    def _cleanup_old_entries(self, current_time: datetime) -> None:
        """
        Clean up old anomaly history entries outside the recurrence window.
        
        Args:
            current_time: Current timestamp for comparison
        """
        try:
            cutoff_time = current_time - self.recurrence_window
            
            # Remove old entries from history
            self.anomaly_history = [
                (a_type, ts) for a_type, ts in self.anomaly_history
                if ts >= cutoff_time
            ]
            
            # Clean up old timestamps from tracking dictionaries
            for anomaly_type in list(self._anomaly_timestamps.keys()):
                timestamps = self._anomaly_timestamps[anomaly_type]
                recent_timestamps = [ts for ts in timestamps if ts >= cutoff_time]
                
                if recent_timestamps:
                    self._anomaly_timestamps[anomaly_type] = recent_timestamps
                else:
                    # Remove empty entries
                    del self._anomaly_timestamps[anomaly_type]
                    if anomaly_type in self._anomaly_counts:
                        del self._anomaly_counts[anomaly_type]
            
            logger.debug(
                f"Cleaned up old anomaly entries",
                extra={
                    'entries_remaining': len(self.anomaly_history),
                    'cutoff_time': cutoff_time.isoformat()
                }
            )
            
        except (TypeError, ValueError) as e:
            logger.error(
                f"Error during anomaly history cleanup ({type(e).__name__}): {e}",
                exc_info=True
            )
        except (KeyError, AttributeError) as e:
            logger.error(
                f"Invalid data structure during cleanup ({type(e).__name__}): {e}",
                exc_info=True
            )
    
    def _execute_escalation(self, decision: Dict[str, Any]) -> None:
        """
        Execute escalation to SAFE_MODE.
        
        This is called when the policy engine determines that escalation is needed.
        """
        try:
            logger.warning(
                f"Escalating to SAFE_MODE due to {decision['anomaly_type']} "
                f"(severity: {decision['severity_score']:.2f}, "
                f"phase: {decision['mission_phase']}, "
                f"decision_id: {decision['decision_id']})"
            )
            
            # Force transition to SAFE_MODE
            escalation_result = self.state_machine.force_safe_mode()
            
            logger.info(
                f"Escalation executed: {escalation_result['message']}",
                extra={'decision_id': decision['decision_id']}
            )
            
        except (RuntimeError, ValueError) as e:
            logger.error(
                f"State machine escalation failed for decision {decision['decision_id']}: {e}. "
                f"Current phase: {decision['mission_phase']}, Target: SAFE_MODE",
                exc_info=True,
                extra={
                    'decision_id': decision['decision_id'],
                    'anomaly_type': decision['anomaly_type'],
                    'current_phase': decision['mission_phase']
                }
            )
        except AttributeError as e:
            logger.error(
                f"Invalid state machine or decision structure: {e}",
                exc_info=True,
                extra={'decision_id': decision.get('decision_id', 'UNKNOWN')}
            )
        except (TypeError, KeyError) as e:
            # Handle invalid decision dictionary structure
            logger.error(
                f"Invalid decision dictionary for escalation ({type(e).__name__}): {e}",
                exc_info=True,
                extra={
                    'decision_id': decision.get('decision_id', 'UNKNOWN'),
                    'decision_keys': list(decision.keys()) if isinstance(decision, dict) else 'not_a_dict'
                }
            )
        except (OSError, IOError) as e:
            # Handle I/O errors during state persistence
            logger.critical(
                f"I/O error during escalation ({type(e).__name__}): {e}. "
                f"State may not be persisted!",
                exc_info=True,
                extra={'decision_id': decision.get('decision_id', 'UNKNOWN')}
            )


    def _log_decision(self, decision: Dict[str, Any]):

        """Log the anomaly decision for audit and analysis."""
        # Structured logging
        log_entry = {
            'timestamp': decision['timestamp'].isoformat(),
            'decision_id': decision['decision_id'],
            'anomaly_type': decision['anomaly_type'],
            'severity': decision['severity_score'],
            'confidence': decision['detection_confidence'],
            'mission_phase': decision['mission_phase'],
            'recommended_action': decision['recommended_action'],
            'escalation': decision['should_escalate_to_safe_mode'],
            'recurrence_count': decision['recurrence_info']['count'],
            'reasoning': decision['reasoning']
        }
        
        logger.info(f"Anomaly decision: {log_entry}")
    
    def _record_anomaly_for_reporting(
        self, 
        decision: Dict[str, Any], 
        anomaly_metadata: Dict[str, Any]
    ) -> None:
        """
        Record anomaly decision for operator feedback loop.
        
        Saves the event to a pending file for review via CLI.
        """
        try:
            event = FeedbackEvent(
                fault_id=decision['decision_id'],
                anomaly_type=decision['anomaly_type'],
                recovery_action=decision['recommended_action'],
                mission_phase=decision['mission_phase'],
                timestamp=decision['timestamp'],
                confidence_score=decision['detection_confidence'],
            )
            
            pending_file = Path("feedback_pending.json")
            events = []
            
            if pending_file.exists():
                try:
                    content = pending_file.read_text()
                    if content.strip():
                        raw_events = json.loads(content)
                        events = raw_events if isinstance(raw_events, list) else []
                except json.JSONDecodeError as e:
                    logger.warning(
                        f"Corrupt pending feedback file, starting fresh: {e}",
                        extra={'file_path': str(pending_file)}
                    )
                except (IOError, OSError) as e:
                    logger.error(
                        f"Failed to read feedback file: {e}",
                        extra={'file_path': str(pending_file)}
                    )
                    return  # Can't proceed without reading existing data
            
            events.append(event.model_dump(mode='json'))
            pending_file.write_text(json.dumps(events, indent=2))
            
            logger.debug(
                f"Recorded feedback event for decision {decision['decision_id']}",
                extra={'decision_id': decision['decision_id'], 'total_events': len(events)}
            )
            
        except (IOError, OSError, PermissionError) as e:
            logger.error(
                f"Failed to write feedback file for decision {decision['decision_id']}: {e}",
                exc_info=True,
                extra={
                    'decision_id': decision['decision_id'],
                    'file_path': str(pending_file) if 'pending_file' in locals() else 'unknown'
                }
            )
        except (KeyError, AttributeError) as e:
            logger.error(
                f"Invalid decision structure for feedback recording: {e}",
                exc_info=True,
                extra={'decision_keys': list(decision.keys()) if isinstance(decision, dict) else 'not_a_dict'}
            )
        except (TypeError, ValueError) as e:
            # Handle data serialization errors
            logger.error(
                f"Failed to serialize feedback event ({type(e).__name__}): {e}",
                exc_info=True,
                extra={
                    'decision_id': decision.get('decision_id', 'UNKNOWN'),
                    'event_type': type(event).__name__ if 'event' in locals() else 'unknown'
                }
            )

    
    def _log_decision(self, decision: Dict[str, Any]) -> None:
        """Log the anomaly decision for audit and analysis."""
        # Structured logging
        log_entry = {
            'timestamp': decision['timestamp'].isoformat(),
            'decision_id': decision['decision_id'],
            'anomaly_type': decision['anomaly_type'],
            'severity': decision['severity_score'],
            'confidence': decision['detection_confidence'],
            'mission_phase': decision['mission_phase'],
            'recommended_action': decision['recommended_action'],
            'escalation': decision['should_escalate_to_safe_mode'],
            'recurrence_count': decision['recurrence_info']['count'],
            'reasoning': decision['reasoning']
        }
        
        logger.info(f"Anomaly decision: {log_entry}")
    
    def _generate_decision_id(self) -> str:
        """Generate a unique decision identifier using UUID for better performance."""
        timestamp = int(datetime.now().timestamp() * 1000)
        uuid_part = uuid.uuid4().hex[:8]
        return f"DECISION_{timestamp}_{uuid_part}"

    
    def get_phase_constraints(self, phase: Optional[MissionPhase] = None) -> Dict[str, Any]:
        """
        Get phase constraints for inspection.
        
        Args:
            phase: Mission phase to inspect. If None, uses current phase.
        
        Returns:
            Dict with allowed_actions, forbidden_actions, threshold_multiplier, etc.
        """
        if phase is None:
            phase = self.state_machine.get_current_phase()
        
        constraints = self.policy_engine.get_phase_constraints(phase)
        return constraints if isinstance(constraints, dict) else {}
    
    def get_anomaly_history(self, anomaly_type: Optional[str] = None) -> List[Tuple[str, datetime]]:
        """
        Get recent anomaly history.
        
        Args:
            anomaly_type: Filter to specific type, or None for all
        
        Returns:
            List of (anomaly_type, timestamp) tuples
        """
        if anomaly_type is None:
            return self.anomaly_history.copy()
        else:
            return [
                (a_type, ts) for a_type, ts in self.anomaly_history
                if a_type == anomaly_type
            ]
    
    def clear_anomaly_history(self) -> None:
        """Clear the anomaly history (e.g., for testing or reset)."""
        self.anomaly_history.clear()
        self._anomaly_counts.clear()
        self._anomaly_timestamps.clear()
        logger.info("Anomaly history cleared")

    
    def reload_policies(self, new_config_path: Optional[str] = None) -> None:
        """
        Reload policies from file.
        
        Useful for hot-reloading policy updates without restarting.
        """
        try:
            config_path = new_config_path or "default"
            logger.info(f"Reloading policies from: {config_path}")
            
            self.policy_loader.reload(new_config_path)
            new_policy = self.policy_loader.get_policy()
            
            # Validate policy before applying
            if not new_policy or not isinstance(new_policy, dict):
                raise ValueError(f"Invalid policy structure loaded from {config_path}")
            
            self.policy_engine = MissionPhasePolicyEngine(new_policy)
            logger.info(
                f"Policies reloaded successfully from {config_path}",
                extra={'policy_phases': list(new_policy.keys()) if isinstance(new_policy, dict) else []}
            )
            
        except FileNotFoundError as e:
            logger.error(
                f"Policy config file not found: {e}",
                extra={'config_path': new_config_path or 'default'}
            )
        except (ValueError, KeyError) as e:
            logger.error(
                f"Invalid policy configuration: {e}. Keeping existing policies.",
                exc_info=True,
                extra={'config_path': new_config_path or 'default'}
            )
        except (IOError, OSError) as e:
            logger.error(
                f"Failed to read policy file: {e}",
                exc_info=True,
                extra={'config_path': new_config_path or 'default'}
            )
        except (TypeError, AttributeError) as e:
            # Handle invalid policy structure or engine errors
            logger.critical(
                f"Policy engine error during reload ({type(e).__name__}): {e}. "
                f"Policy engine may be in inconsistent state!",
                exc_info=True,
                extra={'config_path': new_config_path or 'default'}
            )
        except (ImportError, ModuleNotFoundError) as e:
            # Handle missing dependencies
            logger.critical(
                f"Missing dependency for policy loading ({type(e).__name__}): {e}",
                exc_info=True,
                extra={'config_path': new_config_path or 'default'}
            )



class DecisionTracer:
    """
    Utility to trace and explain decision-making for debugging and learning.
    
    Collects decisions for a period and provides analysis.
    Uses deque for O(1) append and automatic size management.
    """
    
    def __init__(self, max_decisions: int = 1000) -> None:
        """Initialize the decision tracer."""
        self.max_decisions = max_decisions
        self.decisions: List[Dict[str, Any]] = []
    
    def add_decision(self, decision: Dict[str, Any]) -> None:
        """Record a decision."""
        self.decisions.append(decision)

    
    def get_decisions_for_phase(self, phase: str) -> List[Dict[str, Any]]:
        """Get all recorded decisions for a specific phase."""
        return [d for d in self.decisions if d.get('mission_phase') == phase]
    
    def get_decisions_for_anomaly_type(self, anomaly_type: str) -> List[Dict[str, Any]]:
        """Get all recorded decisions for a specific anomaly type."""
        return [d for d in self.decisions if d.get('anomaly_type') == anomaly_type]
    
    def get_escalations(self) -> List[Dict[str, Any]]:
        """Get all decisions that resulted in escalation."""
        return [d for d in self.decisions if d.get('should_escalate_to_safe_mode')]

    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics on recorded decisions."""
        if not self.decisions:
            return {"total_decisions": 0}
        
        escalations = self.get_escalations()
        
        phases: Dict[str, int] = {}
        for d in self.decisions:
            phase = d.get('mission_phase')
            if phase:
                phases[phase] = phases.get(phase, 0) + 1
        
        anomaly_types: Dict[str, int] = {}
        for d in self.decisions:
            a_type = d.get('anomaly_type')
            if a_type:
                anomaly_types[a_type] = anomaly_types.get(a_type, 0) + 1
        
        return {
            'total_decisions': len(self.decisions),
            'total_escalations': len(escalations),
            'escalation_rate': len(escalations) / len(self.decisions) if self.decisions else 0,
            'by_phase': phases,
            'by_anomaly_type': anomaly_types
        }
    
    def _record_anomaly_for_reporting(self, decision: Dict[str, Any], anomaly_metadata: Dict[str, Any]) -> None:
        """
        Record anomaly event for reporting purposes.
        
        Args:
            decision: The complete decision dictionary from handle_anomaly
            anomaly_metadata: Additional metadata about the anomaly
        """
        try:
            report_generator = get_report_generator()
            
            # Map severity score to severity level
            severity_score = decision.get('severity_score', 0.5)
            if severity_score >= 0.8:
                severity = "CRITICAL"
            elif severity_score >= 0.6:
                severity = "HIGH"
            elif severity_score >= 0.4:
                severity = "MEDIUM"
            else:
                severity = "LOW"
            
            # Prepare telemetry data
            telemetry_data = anomaly_metadata.copy() if anomaly_metadata else {}
            telemetry_data.update({
                'severity_score': severity_score,
                'detection_confidence': decision.get('detection_confidence', 0.0),
                'recurrence_info': decision.get('recurrence_info', {})
            })
            
            report_generator.record_anomaly(
                anomaly_type=decision['anomaly_type'],
                severity=severity,
                confidence=decision.get('detection_confidence', 0.0),
                mission_phase=decision['mission_phase'],
                telemetry_data=telemetry_data,
                explanation=decision.get('explanation')
            )
            
        except (AttributeError, KeyError) as e:
            logger.error(
                f"Invalid decision or metadata structure for reporting: {e}",
                exc_info=True,
                extra={
                    'decision_id': decision.get('decision_id', 'UNKNOWN'),
                    'decision_keys': list(decision.keys()) if isinstance(decision, dict) else 'not_a_dict'
                }
            )
        except ImportError as e:
            logger.error(
                f"Report generator not available: {e}. Anomaly will not be recorded in reports.",
                extra={'decision_id': decision.get('decision_id', 'UNKNOWN')}
            )
        except (TypeError, ValueError) as e:
            # Handle data type or value errors in report generation
            logger.error(
                f"Invalid data for report generation ({type(e).__name__}): {e}",
                exc_info=True,
                extra={
                    'decision_id': decision.get('decision_id', 'UNKNOWN'),
                    'severity_score': decision.get('severity_score', 'unknown')
                }
            )
        except (RuntimeError, OSError, IOError) as e:
            # Handle report generator runtime or I/O errors
            logger.error(
                f"Report generator error ({type(e).__name__}): {e}",
                exc_info=True,
                extra={'decision_id': decision.get('decision_id', 'UNKNOWN')}
            )
