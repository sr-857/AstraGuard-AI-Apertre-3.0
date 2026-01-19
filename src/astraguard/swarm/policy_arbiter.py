"""
Policy Arbitration for local vs global conflict resolution.

Issue #407: Coordination Core - Local vs global policy arbitration for AstraGuard v3.0
- Resolves conflicts between local (device-initiated) and global (consensus) policies
- Weighted scoring: safety (0.7) > performance (0.2) > availability (0.1)
- Byzantine fault tolerance through multi-agent conflict detection
- Supports configurable weights via SwarmConfig

Algorithm:
1. Score each policy: base_score * weight[priority]
2. Compare weighted scores: higher wins
3. Tiebreaker: newer timestamp wins
4. Multi-agent: sum scores across quorum for global optimum

Example:
  local_safe_mode.score = 0.9 * 0.7 = 0.63  (priority=SAFETY)
  global_attitude.score = 0.8 * 0.2 = 0.16  (priority=PERFORMANCE)
  → local_safe_mode wins (0.63 > 0.16)
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum

from astraguard.swarm.types import Policy, ActionScope, PriorityEnum
from astraguard.swarm.models import AgentID


class ConflictResolution(str, Enum):
    """Policy arbitration decision."""
    LOCAL_WINS = "LOCAL_WINS"
    GLOBAL_WINS = "GLOBAL_WINS"
    MERGED = "MERGED"
    ABSTAIN = "ABSTAIN"


@dataclass
class PolicyArbiterMetrics:
    """Metrics for policy arbitration."""
    arbitration_conflicts_resolved: int = 0
    local_overrides_global_count: int = 0
    safety_violations_blocked: int = 0
    policy_convergence_time_ms: float = 0.0

    def to_dict(self) -> dict:
        """Serialize to dict for Prometheus export."""
        return {
            "arbitration_conflicts_resolved": self.arbitration_conflicts_resolved,
            "local_overrides_global_count": self.local_overrides_global_count,
            "safety_violations_blocked": self.safety_violations_blocked,
            "policy_convergence_time_ms": self.policy_convergence_time_ms,
        }


class PolicyArbiter:
    """Arbitrates conflicts between local and global policies.
    
    Weighted scoring model enables intelligent tradeoff resolution:
    - Safety (0.7): Emergency conditions override performance
    - Performance (0.2): Normal optimization within safety bounds
    - Availability (0.1): Load balancing and role changes
    
    Attributes:
        weights: Priority weight mapping (safety, performance, availability)
        metrics: Arbitration metrics for monitoring
    """

    # Default weights: safety > performance > availability
    DEFAULT_WEIGHTS = {
        "SAFETY": 0.7,
        "PERFORMANCE": 0.2,
        "AVAILABILITY": 0.1,
    }

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        """Initialize PolicyArbiter.
        
        Args:
            weights: Custom weight mapping. Must sum to 1.0.
                    Default: {SAFETY: 0.7, PERFORMANCE: 0.2, AVAILABILITY: 0.1}
        
        Raises:
            ValueError: If weights don't sum to 1.0 or are invalid
        """
        self.weights = weights or self.DEFAULT_WEIGHTS
        self._validate_weights()
        self.metrics = PolicyArbiterMetrics()

    def _validate_weights(self):
        """Validate weights sum to 1.0 and all are non-negative."""
        weight_sum = sum(self.weights.values())
        if not abs(weight_sum - 1.0) < 0.001:  # Allow floating point tolerance
            raise ValueError(
                f"Weights must sum to 1.0, got {weight_sum}. "
                f"Weights: {self.weights}"
            )
        
        for name, weight in self.weights.items():
            if weight < 0 or weight > 1.0:
                raise ValueError(
                    f"Weight '{name}' must be between 0.0 and 1.0, got {weight}"
                )

    def arbitrate(
        self, local_policy: Policy, global_policy: Policy
    ) -> Policy:
        """Arbitrate between local and global policies.
        
        Decision logic:
        1. Apply weighted scoring based on priority
        2. SAFETY priority override: if either is SAFETY, use that
        3. Compare weighted scores: higher wins
        4. Tiebreaker: newer timestamp wins
        
        Args:
            local_policy: Device-initiated policy
            global_policy: Consensus-approved policy
        
        Returns:
            Policy: Winning policy (local or global)
        """
        # Safety override: SAFETY priority always wins
        if local_policy.priority == PriorityEnum.SAFETY:
            if global_policy.priority != PriorityEnum.SAFETY:
                self.metrics.local_overrides_global_count += 1
                self.metrics.safety_violations_blocked += 1
                return local_policy
        
        if global_policy.priority == PriorityEnum.SAFETY:
            if local_policy.priority != PriorityEnum.SAFETY:
                self.metrics.safety_violations_blocked += 1
                return global_policy
        
        # Weighted scoring
        local_weighted = self._apply_weights(local_policy)
        global_weighted = self._apply_weights(global_policy)
        
        # Compare with small tolerance for floating point
        if local_weighted > global_weighted + 0.001:
            self.metrics.local_overrides_global_count += 1
            self.metrics.arbitration_conflicts_resolved += 1
            return local_policy
        
        if global_weighted > local_weighted + 0.001:
            self.metrics.arbitration_conflicts_resolved += 1
            return global_policy
        
        # Tiebreaker: newer timestamp wins, local wins on exact tie
        if local_policy.timestamp >= global_policy.timestamp:
            self.metrics.local_overrides_global_count += 1
            return local_policy
        
        return global_policy

    def _apply_weights(self, policy: Policy) -> float:
        """Apply weights to policy score based on priority.
        
        Weighted Score = base_score * weight[priority]
        
        Args:
            policy: Policy to score
        
        Returns:
            float: Weighted score (0.0-1.0)
        """
        priority_name = policy.priority.name  # e.g., "SAFETY"
        weight = self.weights.get(priority_name, 0.0)
        return policy.score * weight

    def get_conflict_score(self, policies: List[Policy]) -> float:
        """Detect multi-agent conflicts and return conflict severity.
        
        Conflict Detection:
        - Count policies with same action → high consensus
        - Count conflicting actions → low consensus
        - Return: conflicting_count / total_count (0.0 = consensus, 1.0 = total conflict)
        
        Example:
          5 agents: 4 propose safe_mode, 1 proposes attitude_adjust
          → conflict_score = 1 / 5 = 0.2 (low conflict, proceed with majority)
        
        Args:
            policies: List of policies from multiple agents
        
        Returns:
            float: Conflict severity (0.0 = all agree, 1.0 = all disagree)
        """
        if not policies:
            return 0.0
        
        if len(policies) == 1:
            return 0.0
        
        # Count action frequencies
        action_counts: Dict[str, int] = {}
        for policy in policies:
            action_counts[policy.action] = action_counts.get(policy.action, 0) + 1
        
        # If all same action, no conflict
        if len(action_counts) == 1:
            return 0.0
        
        # Conflict count = all policies except the most common action
        most_common_count = max(action_counts.values())
        conflict_count = len(policies) - most_common_count
        
        return conflict_count / len(policies)

    def resolve_multi_agent(self, policies: List[Policy]) -> Policy:
        """Resolve policies from multiple agents using weighted quorum.
        
        Algorithm:
        1. Group policies by action
        2. For each group, sum weighted scores
        3. Return action with highest total weighted score
        
        Example (5 agents, 2/3 quorum = 4):
          Group A (safe_mode): sum([0.63, 0.63, 0.56, 0.49]) = 2.31
          Group B (attitude): sum([0.16, 0.16, 0.16]) = 0.48
          → safe_mode wins (2.31 > 0.48)
        
        Args:
            policies: Policies from quorum members
        
        Returns:
            Policy: Winning policy with highest weighted sum
        
        Raises:
            ValueError: If policies list is empty
        """
        if not policies:
            raise ValueError("Cannot resolve empty policy list")
        
        # Group policies by action
        action_groups: Dict[str, List[Policy]] = {}
        for policy in policies:
            if policy.action not in action_groups:
                action_groups[policy.action] = []
            action_groups[policy.action].append(policy)
        
        # Calculate total weighted score for each action
        action_scores: Dict[str, tuple[float, Policy]] = {}
        for action, group in action_groups.items():
            total_weighted = sum(self._apply_weights(p) for p in group)
            # Return policy: use first one as representative, but with summed score
            representative = group[0]
            action_scores[action] = (total_weighted, representative)
        
        # Return action with highest total weighted score
        winning_action = max(action_scores.keys(), key=lambda a: action_scores[a][0])
        _, winning_policy = action_scores[winning_action]
        
        self.metrics.arbitration_conflicts_resolved += 1
        return winning_policy

    def update_weights(self, weights: Dict[str, float]):
        """Update arbitration weights at runtime.
        
        Args:
            weights: New weight mapping
        
        Raises:
            ValueError: If weights don't sum to 1.0
        """
        self.weights = weights
        self._validate_weights()

    def check_safety_compliance(self, policy: Policy) -> bool:
        """Check if policy violates safety constraints.
        
        Safety rules:
        - SAFETY priority policies always allowed
        - Other priorities cannot override SAFETY constraint
        - Local battery critical (<10%) blocks non-SAFETY actions
        
        Args:
            policy: Policy to check
        
        Returns:
            bool: True if policy is safe, False if it violates safety
        """
        # Check for critical battery constraint
        critical_battery = policy.parameters.get("battery_critical", False)
        if critical_battery and policy.priority != PriorityEnum.SAFETY:
            self.metrics.safety_violations_blocked += 1
            return False
        
        return True

    def merge_policies(
        self, local: Policy, global_policy: Policy
    ) -> Optional[Policy]:
        """Attempt to merge compatible policies (stub for future).
        
        Currently returns None (no merge possible).
        Future: Could merge attitude_adjust + load_shed into single action.
        
        Args:
            local: Local policy
            global_policy: Global policy
        
        Returns:
            Policy: Merged policy, or None if merge not possible
        """
        # Stub: policies are generally incompatible, prefer arbitration
        return None
