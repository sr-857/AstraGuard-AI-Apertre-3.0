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
from typing import Dict, Any, Optional, Tuple
from dataclasses import asdict
from datetime import datetime, timedelta
import json
from pathlib import Path
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


logger = logging.getLogger(__name__)


class PhaseAwareAnomalyHandler:
    """
    Handles anomalies with awareness of mission phase constraints.
    
    Responsibilities:
    1. Receive anomaly detection results (type, severity, confidence)
    2. Query current mission phase from state machine
    3. Evaluate against phase-specific policies
    4. Generate phase-aware response decision
    5. Log all decisions for audit and learning
    
    The handler is designed to be called from the anomaly detection pipeline.
    """
    
    def __init__(
        self,
        state_machine: StateMachine,
        policy_loader: Optional[MissionPhasePolicyLoader] = None,
        enable_recurrence_tracking: bool = True
    ):
        """
        Initialize the phase-aware anomaly handler.
        
        Args:
            state_machine: StateMachine instance to query mission phase
            policy_loader: MissionPhasePolicyLoader instance
                          If None, creates a new one with defaults
            enable_recurrence_tracking: Track anomaly recurrence patterns
        """
        self.state_machine = state_machine
        self.policy_loader = policy_loader or MissionPhasePolicyLoader()
        self.policy_engine = MissionPhasePolicyEngine(self.policy_loader.get_policy())
        
        # Recurrence tracking
        self.enable_recurrence_tracking = enable_recurrence_tracking
        self.anomaly_history = []  # List of (anomaly_type, timestamp) tuples
        self.recurrence_window = timedelta(seconds=3600)  # 1 hour default
        
        logger.info("Phase-aware anomaly handler initialized")
    
    def handle_anomaly(
        self,
        anomaly_type: str,
        severity_score: float,
        confidence: float,
        anomaly_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process an anomaly with phase awareness.
        
        Args:
            anomaly_type: Type of anomaly (e.g., 'power_fault', 'thermal_fault')
            severity_score: Numeric severity from 0-1
            confidence: Detection confidence from 0-1
            anomaly_metadata: Optional additional info (fault_class, subsystem, etc.)
        
        Returns:
            Decision dict with:
            {
                'success': bool,
                'anomaly_type': str,
                'mission_phase': str,
                'policy_decision': PolicyDecision (as dict),
                'recommended_action': str,
                'should_escalate_to_safe_mode': bool,
                'reasoning': str,
                'timestamp': datetime,
                'decision_id': str (unique identifier)
            }
        """
        if anomaly_metadata is None:
            anomaly_metadata = {}
        
        # Get current mission phase
        current_phase = self.state_machine.get_current_phase()
        
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
        except Exception as e:
            logger.warning(f"Failed to update metrics: {e}")
        
        # Log the decision
        self._log_decision(decision)
        
        # Record anomaly for reporting
        self._record_anomaly_for_reporting(decision, anomaly_metadata)
        
        # If escalation is needed, trigger it
        if should_escalate:
            self._execute_escalation(decision)

        # Record for feedback loop
        self._record_anomaly_for_reporting(decision, anomaly_metadata)
        
        return decision
    
    def _update_recurrence_tracking(self, anomaly_type: str) -> Dict[str, Any]:
        """
        Track recurrence of anomalies within a time window.
        
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
        
        # Add current occurrence
        if self.enable_recurrence_tracking:
            self.anomaly_history.append((anomaly_type, now))
        
        # Count total occurrences of this type
        total_count = sum(1 for a_type, _ in self.anomaly_history if a_type == anomaly_type)
        
        # Find occurrences within time window
        window_start = now - self.recurrence_window
        recent_occurrences = [
            (a_type, timestamp) for a_type, timestamp in self.anomaly_history
            if a_type == anomaly_type and timestamp >= window_start
        ]
        
        # Find last occurrence
        same_type_history = [
            (a_type, timestamp) for a_type, timestamp in self.anomaly_history
            if a_type == anomaly_type
        ]
        
        if len(same_type_history) > 1:
            # Get second-to-last (last one is the current)
            last_occurrence = same_type_history[-2][1]
            time_since_last = (now - last_occurrence).total_seconds()
        else:
            last_occurrence = None
            time_since_last = None
        
        # Clean up old entries (keep last 1000 or entries within 24 hours)
        if len(self.anomaly_history) > 1000:
            cutoff = now - timedelta(hours=24)
            self.anomaly_history = [
                (a_type, ts) for a_type, ts in self.anomaly_history
                if ts >= cutoff
            ]
        
        return {
            'count': total_count,
            'total_in_window': len(recent_occurrences),
            'last_occurrence': last_occurrence.isoformat() if last_occurrence else None,
            'time_since_last_seconds': time_since_last
        }
    
    def _execute_escalation(self, decision: Dict[str, Any]):
        """
        Execute escalation to SAFE_MODE.
        
        This is called when the policy engine determines that escalation is needed.
        """
        try:
            logger.warning(
                f"Escalating to SAFE_MODE due to {decision['anomaly_type']} "
                f"(severity: {decision['severity_score']:.2f}, "
                f"phase: {decision['mission_phase']})"
            )
            
            # Force transition to SAFE_MODE
            escalation_result = self.state_machine.force_safe_mode()
            
            logger.info(f"Escalation executed: {escalation_result['message']}")
            
        except Exception as e:
            logger.error(f"Failed to execute escalation: {e}", exc_info=True)

    def _record_anomaly_for_reporting(
        self, 
        decision: Dict[str, Any], 
        anomaly_metadata: Dict[str, Any]
    ):
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
                # label is None by default for pending events
            )
            
            pending_file = Path("feedback_pending.json")
            events = []
            
            if pending_file.exists():
                try:
                    content = pending_file.read_text()
                    if content.strip():
                        # Load existing events
                        raw_events = json.loads(content)
                        # We don't need to validate all existing ones strictly here, just append
                        events = raw_events
                except json.JSONDecodeError:
                    logger.warning("Corrupt pending feedback file, starting fresh.")
            
            # Append new event
            events.append(event.model_dump(mode='json'))
            
            # Write back
            pending_file.write_text(json.dumps(events, indent=2))
            
        except Exception as e:
            logger.error(f"Failed to record anomaly for reporting: {e}")
    
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
    
    def _record_anomaly_for_reporting(self, decision: Dict[str, Any], anomaly_metadata: Dict[str, Any]):
        """Record anomaly for reporting and analytics purposes."""
        # This method could store anomalies in a database, send to monitoring systems, etc.
        # For now, we'll just log that recording occurred
        logger.debug(f"Recorded anomaly for reporting: {decision['decision_id']}")
    
    def _generate_decision_id(self) -> str:
        """Generate a unique decision identifier."""
        import time
        import random
        timestamp = int(time.time() * 1000)
        random_part = random.randint(0, 99999)
        return f"DECISION_{timestamp}_{random_part:05d}"
    
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
        
        return self.policy_engine.get_phase_constraints(phase)
    
    def get_anomaly_history(self, anomaly_type: Optional[str] = None) -> list:
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
    
    def clear_anomaly_history(self):
        """Clear the anomaly history (e.g., for testing or reset)."""
        self.anomaly_history.clear()
        logger.info("Anomaly history cleared")
    
    def reload_policies(self, new_config_path: Optional[str] = None):
        """
        Reload policies from file.
        
        Useful for hot-reloading policy updates without restarting.
        """
        try:
            self.policy_loader.reload(new_config_path)
            self.policy_engine = MissionPhasePolicyEngine(
                self.policy_loader.get_policy()
            )
            logger.info("Policies reloaded successfully")
        except Exception as e:
            logger.error(f"Failed to reload policies: {e}", exc_info=True)


class DecisionTracer:
    """
    Utility to trace and explain decision-making for debugging and learning.
    
    Collects decisions for a period and provides analysis.
    """
    
    def __init__(self, max_decisions: int = 1000):
        """Initialize the decision tracer."""
        self.max_decisions = max_decisions
        self.decisions = []
    
    def add_decision(self, decision: Dict[str, Any]):
        """Record a decision."""
        self.decisions.append(decision)
        if len(self.decisions) > self.max_decisions:
            self.decisions.pop(0)
    
    def get_decisions_for_phase(self, phase: str) -> list:
        """Get all recorded decisions for a specific phase."""
        return [d for d in self.decisions if d.get('mission_phase') == phase]
    
    def get_decisions_for_anomaly_type(self, anomaly_type: str) -> list:
        """Get all recorded decisions for a specific anomaly type."""
        return [d for d in self.decisions if d.get('anomaly_type') == anomaly_type]
    
    def get_escalations(self) -> list:
        """Get all decisions that resulted in escalation."""
        return [d for d in self.decisions if d.get('should_escalate_to_safe_mode')]
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics on recorded decisions."""
        if not self.decisions:
            return {"total_decisions": 0}
        
        escalations = self.get_escalations()
        
        phases = {}
        for d in self.decisions:
            phase = d.get('mission_phase')
            if phase:
                phases[phase] = phases.get(phase, 0) + 1
        
        anomaly_types = {}
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
            
            # Prepare telemetry data (use metadata or create minimal data)
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
            
        except Exception as e:
            logger.warning(f"Failed to record anomaly for reporting: {e}")
