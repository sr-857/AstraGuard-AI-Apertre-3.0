"""
Mission Phase Policy Engine

Evaluates anomalies against mission-phase-specific policies to determine
appropriate fault response actions.

The policy engine implements a decision tree:
1. Lookup phase configuration from loaded policy
2. Check anomaly severity against phase-specific thresholds
3. Evaluate allowed vs. forbidden actions
4. Determine escalation level (e.g., to SAFE_MODE)
5. Return structured decision with reasoning
"""

import logging
from typing import Dict, List, Any, Optional
from enum import Enum
from dataclasses import dataclass
from state_machine.state_engine import MissionPhase

# Import error handling
from core.error_handling import PolicyEvaluationError
from core.component_health import get_health_monitor
# Import input validation
from core.input_validation import PolicyDecision as CorePolicyDecision, ValidationError

logger = logging.getLogger(__name__)


class SeverityLevel(Enum):
    """Severity levels for anomalies."""

    CRITICAL = "CRITICAL"  # >= 0.9
    HIGH = "HIGH"  # 0.7 - 0.89
    MEDIUM = "MEDIUM"  # 0.4 - 0.69
    LOW = "LOW"  # < 0.4


class EscalationLevel(Enum):
    """Escalation decision for response."""

    NO_ACTION = "NO_ACTION"  # System OK, no action needed
    LOG_ONLY = "LOG_ONLY"  # Log the event, no automated action
    ALERT_OPERATORS = "ALERT_OPERATORS"  # Alert humans but no automated actions
    CONTROLLED_ACTION = "CONTROLLED_ACTION"  # Limited automated response
    ESCALATE_SAFE_MODE = "ESCALATE_SAFE_MODE"  # Escalate to SAFE_MODE


@dataclass
class PolicyDecision:
    """
    Result of policy evaluation for an anomaly.

    Attributes:
        mission_phase: Current mission phase
        anomaly_type: Type/class of anomaly detected
        severity: Calculated severity level
        severity_score: Numeric severity (0-1)
        is_allowed: Whether response is allowed in this phase
        allowed_actions: List of actions allowed in this phase
        recommended_action: Primary recommended action
        escalation_level: Whether to escalate to SAFE_MODE
        confidence: Confidence in the decision (0-1)
        reasoning: Human-readable explanation of decision
    """

    mission_phase: str
    anomaly_type: str
    severity: str
    severity_score: float
    is_allowed: bool
    allowed_actions: List[str]
    recommended_action: str
    escalation_level: str
    confidence: float
    reasoning: str


class MissionPhasePolicyEngine:
    """
    Evaluates anomalies against mission-phase-specific policies.

    This engine loads a policy configuration (typically from YAML) that defines:
    - Which actions are allowed/forbidden in each phase
    - Severity thresholds that trigger specific responses
    - Escalation rules (when to go to SAFE_MODE)

    The engine is stateless and pure - no side effects.
    """

    def __init__(self, policy_config: Dict[str, Any]):
        """
        Initialize the policy engine with error handling.

        Args:
            policy_config: Dictionary with 'phases' key containing phase policies
                          Typically loaded from YAML by MissionPhasePolicyLoader

        Raises:
            PolicyEvaluationError: If policy config is invalid
        """
        health_monitor = get_health_monitor()
        health_monitor.register_component("policy_engine")

        try:
            self.policy_config = policy_config
            self._validate_config()
            health_monitor.mark_healthy(
                "policy_engine", {"phases_loaded": len(policy_config.get("phases", {}))}
            )
            logger.info(
                f"Policy engine initialized with {len(policy_config.get('phases', {}))} phases"
            )
        except Exception as e:
            raise PolicyEvaluationError(
                f"Failed to initialize policy engine: {str(e)}",
                component="policy_engine",
                context={"error": str(e)},
            )

    def _validate_config(self):
        """Validate that the policy config has required structure."""
        if not isinstance(self.policy_config, dict):
            raise PolicyEvaluationError(
                "Policy config must be a dictionary",
                component="policy_engine",
                context={"config_type": str(type(self.policy_config))},
            )

        if "phases" not in self.policy_config:
            raise PolicyEvaluationError(
                "Policy config must have 'phases' key", component="policy_engine"
            )

        phases = self.policy_config["phases"]
        if not isinstance(phases, dict):
            raise PolicyEvaluationError(
                "Phases must be a dictionary",
                component="policy_engine",
                context={"phases_type": str(type(phases))},
            )

        # Log a warning if expected phases are missing
        expected_phases = {p.value for p in MissionPhase}
        configured_phases = set(phases.keys())
        missing = expected_phases - configured_phases
        if missing:
            logger.warning(f"Policy config missing phases: {missing}")

    def evaluate(
        self,
        mission_phase: MissionPhase,
        anomaly_type: str,
        severity_score: float,
        anomaly_attributes: Optional[Dict[str, Any]] = None,
    ) -> PolicyDecision:
        """
        Evaluate an anomaly against the current mission phase policy.

        Args:
            mission_phase: Current MissionPhase enum value
            anomaly_type: Type of anomaly (e.g., 'power_fault', 'thermal_fault')
            severity_score: Numeric severity from 0-1
            anomaly_attributes: Optional dict with additional anomaly info
                               (e.g., fault_class, confidence, recurrence_count)

        Returns:
            PolicyDecision object with evaluation results
        """
        if anomaly_attributes is None:
            anomaly_attributes = {}

        # Get phase configuration
        phase_config = self._get_phase_config(mission_phase)
        if not phase_config:
            # No specific config for this phase - use conservative defaults
            return self._make_default_decision(
                mission_phase, anomaly_type, severity_score
            )

        # Classify severity
        severity_level = self._classify_severity(severity_score)

        # Determine allowed actions for this phase
        allowed_actions = phase_config.get("allowed_actions", [])
        forbidden_actions = phase_config.get("forbidden_actions", [])

        # Evaluate against severity thresholds
        severity_thresholds = phase_config.get("severity_thresholds", {})

        # Determine if response is appropriate for this phase
        is_allowed = self._is_response_allowed(
            mission_phase,
            phase_config,
            severity_level,
            anomaly_attributes,
            severity_thresholds,
            severity_score,
        )

        # Determine escalation
        escalation_level = self._determine_escalation(
            mission_phase,
            phase_config,
            severity_level,
            severity_score,
            is_allowed,
            anomaly_attributes,
        )

        # Select recommended action
        recommended_action = self._select_action(
            phase_config, escalation_level, allowed_actions, forbidden_actions, anomaly_type
        )

        # Build reasoning
        reasoning = self._build_reasoning(
            mission_phase,
            anomaly_type,
            severity_level,
            is_allowed,
            escalation_level,
            allowed_actions,
        )

        # Confidence in decision (higher if phase has specific rules)
        confidence = 0.9 if allowed_actions else 0.7

        decision = PolicyDecision(
            mission_phase=mission_phase.value,
            anomaly_type=anomaly_type,
            severity=severity_level.value,
            severity_score=severity_score,
            is_allowed=is_allowed,
            allowed_actions=allowed_actions,
            recommended_action=recommended_action,
            escalation_level=escalation_level.value,
            confidence=confidence,
            reasoning=reasoning,
        )

        # Validate the decision using core input validation
        try:
            # Map local fields to core PolicyDecision fields
            core_decision_dict = {
                'mission_phase': decision.mission_phase,
                'anomaly_type': decision.anomaly_type,
                'severity': decision.severity,
                'recommended_action': decision.recommended_action,
                'detection_confidence': decision.confidence,  # Map confidence to detection_confidence
                'timestamp': '',  # Add empty timestamp as it's not available
                'reasoning': decision.reasoning,
            }
            CorePolicyDecision.validate(core_decision_dict)
        except ValidationError as e:
            logger.warning(f"Policy decision validation failed: {e}")
            # Continue with the decision but log the issue

        return decision

    def _get_phase_config(self, mission_phase: MissionPhase) -> Optional[Dict]:
        """Get configuration for a specific mission phase."""
        phases = self.policy_config.get("phases", {})
        return phases.get(mission_phase.value)

    def _classify_severity(self, score: float) -> SeverityLevel:
        """Classify numeric severity score into levels."""
        # Handle None/null score with safe default
        if score is None:
            return SeverityLevel.LOW

        # Convert to float, default to 0 if conversion fails
        try:
            score_value = float(score)
        except (TypeError, ValueError):
            logger.warning(f"Invalid severity score {score}, defaulting to LOW")
            return SeverityLevel.LOW

        # Classify based on thresholds
        if score_value >= 0.9:
            return SeverityLevel.CRITICAL
        elif score_value >= 0.7:
            return SeverityLevel.HIGH
        elif score_value >= 0.4:
            return SeverityLevel.MEDIUM
        else:
            return SeverityLevel.LOW

    def _is_response_allowed(
        self,
        mission_phase: MissionPhase,
        phase_config: Dict,
        severity_level: SeverityLevel,
        anomaly_attributes: Dict,
        severity_thresholds: Dict = None,
        severity_score: float = 0.0,
    ) -> bool:
        """
        Determine if automated response is allowed in this phase.

        Rules:
        - LAUNCH/DEPLOYMENT: Only allow critical responses
        - NOMINAL_OPS/PAYLOAD_OPS: Allow all appropriate responses
        - SAFE_MODE: Only allow logging/monitoring
        
        Also checks against phase-specific severity thresholds if configured.
        """
        if severity_thresholds is None:
            severity_thresholds = {}
        
        # Check severity against configured thresholds (skip if severity_score is None)
        if severity_score is not None:
            min_threshold = severity_thresholds.get("min_threshold", 0.0)
            max_threshold = severity_thresholds.get("max_threshold", 1.0)
            if not (min_threshold <= severity_score <= max_threshold):
                # Severity outside configured threshold range
                return False
        if mission_phase == MissionPhase.LAUNCH:
            # Launch: only respond to critical anomalies
            return severity_level == SeverityLevel.CRITICAL
        elif mission_phase == MissionPhase.DEPLOYMENT:
            # Deployment: respond to high/critical
            return severity_level in [SeverityLevel.CRITICAL, SeverityLevel.HIGH]
        elif mission_phase == MissionPhase.SAFE_MODE:
            # Safe mode: only log, no automated actions
            return False
        else:
            # Nominal/Payload ops: respond to medium and above
            return severity_level in [
                SeverityLevel.CRITICAL,
                SeverityLevel.HIGH,
                SeverityLevel.MEDIUM,
            ]

    def _determine_escalation(
        self,
        mission_phase: MissionPhase,
        phase_config: Dict,
        severity_level: SeverityLevel,
        severity_score: float,
        is_allowed: bool,
        anomaly_attributes: Dict,
    ) -> EscalationLevel:
        """
        Determine if escalation to SAFE_MODE is needed.

        Logic:
        - CRITICAL severity: escalate unless in SAFE_MODE
        - Recurrent fault: escalate
        - Multiple system failures: escalate
        """
        # Already in safe mode
        if mission_phase == MissionPhase.SAFE_MODE:
            return EscalationLevel.LOG_ONLY

        # No automated response allowed
        if not is_allowed:
            if severity_level == SeverityLevel.CRITICAL:
                return EscalationLevel.ESCALATE_SAFE_MODE
            else:
                return EscalationLevel.ALERT_OPERATORS

        # Critical always escalates
        if severity_level == SeverityLevel.CRITICAL:
            return EscalationLevel.ESCALATE_SAFE_MODE

        # Recurrent fault escalates
        recurrence_count = anomaly_attributes.get("recurrence_count", 0)
        if recurrence_count >= 3:
            return EscalationLevel.ESCALATE_SAFE_MODE

        # High severity might escalate
        if severity_level == SeverityLevel.HIGH:
            if mission_phase == MissionPhase.LAUNCH:
                return EscalationLevel.ALERT_OPERATORS
            else:
                return EscalationLevel.CONTROLLED_ACTION

        # Medium/Low severity
        if severity_level == SeverityLevel.MEDIUM:
            return EscalationLevel.CONTROLLED_ACTION
        else:
            return EscalationLevel.LOG_ONLY

    def _select_action(
        self,
        phase_config: Dict,
        escalation_level: EscalationLevel,
        allowed_actions: List[str],
        forbidden_actions: List[str],
        anomaly_type: str,
    ) -> str:
        """
        Select the recommended action based on escalation level and allowed actions.
        
        Enforces forbidden actions by filtering them out from allowed actions.
        """
        if escalation_level == EscalationLevel.ESCALATE_SAFE_MODE:
            return "ENTER_SAFE_MODE"
        elif escalation_level == EscalationLevel.ALERT_OPERATORS:
            return "ALERT_ONLY"
        elif escalation_level == EscalationLevel.LOG_ONLY:
            return "LOG_ONLY"
        elif escalation_level == EscalationLevel.NO_ACTION:
            return "NO_ACTION"
        else:  # CONTROLLED_ACTION
            # Filter out forbidden actions from allowed actions
            safe_actions = [
                action
                for action in allowed_actions
                if action not in forbidden_actions
            ]
            # Return first safe action, or log if none
            if safe_actions:
                return safe_actions[0]
            return "LOG_ONLY"

    def _build_reasoning(
        self,
        mission_phase: MissionPhase,
        anomaly_type: str,
        severity_level: SeverityLevel,
        is_allowed: bool,
        escalation_level: EscalationLevel,
        allowed_actions: List[str],
    ) -> str:
        """Build a human-readable reasoning string."""
        parts = [
            f"Anomaly type: {anomaly_type}",
            f"Severity: {severity_level.value}",
            f"Mission phase: {mission_phase.value}",
        ]

        if not is_allowed:
            parts.append("Automated response blocked by phase policy")
        elif allowed_actions:
            parts.append(f"Allowed actions: {', '.join(allowed_actions)}")

        if escalation_level == EscalationLevel.ESCALATE_SAFE_MODE:
            parts.append("Decision: Escalate to SAFE_MODE")
        elif escalation_level == EscalationLevel.ALERT_OPERATORS:
            parts.append("Decision: Alert operators only")
        elif escalation_level == EscalationLevel.LOG_ONLY:
            parts.append("Decision: Log event only")
        elif escalation_level == EscalationLevel.CONTROLLED_ACTION:
            parts.append("Decision: Execute allowed response action")

        return " | ".join(parts)

    def _make_default_decision(
        self, mission_phase: MissionPhase, anomaly_type: str, severity_score: float
    ) -> PolicyDecision:
        """Make a conservative default decision when no policy is configured."""
        severity_level = self._classify_severity(severity_score)

        logger.warning(
            f"No policy found for phase {mission_phase.value}. "
            f"Using conservative default for {anomaly_type}."
        )

        # Conservative defaults: always alert and log
        if severity_score >= 0.9:
            escalation = EscalationLevel.ESCALATE_SAFE_MODE
            action = "ENTER_SAFE_MODE"
        else:
            escalation = EscalationLevel.ALERT_OPERATORS
            action = "ALERT_ONLY"

        return PolicyDecision(
            mission_phase=mission_phase.value,
            anomaly_type=anomaly_type,
            severity=severity_level.value,
            severity_score=severity_score,
            is_allowed=False,
            allowed_actions=[],
            recommended_action=action,
            escalation_level=escalation.value,
            confidence=0.5,
            reasoning="No phase policy configured. Using conservative defaults.",
        )

    def get_phase_constraints(self, mission_phase: MissionPhase) -> Dict[str, Any]:
        """Get all constraints for a specific mission phase."""
        config = self._get_phase_config(mission_phase)
        if not config:
            return {
                "phase": mission_phase.value,
                "description": "No configuration",
                "allowed_actions": [],
                "forbidden_actions": [],
                "threshold_multiplier": 1.0,
            }

        return {
            "phase": mission_phase.value,
            "description": config.get("description", ""),
            "allowed_actions": config.get("allowed_actions", []),
            "forbidden_actions": config.get("forbidden_actions", []),
            "threshold_multiplier": config.get("threshold_multiplier", 1.0),
            "severity_thresholds": config.get("severity_thresholds", {}),
        }
