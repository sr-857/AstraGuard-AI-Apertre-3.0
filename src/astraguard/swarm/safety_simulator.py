"""
Swarm Impact Pre-Execution Simulation for Safety Validation

Issue #413: Safety simulation layer for CONSTELLATION actions
- Pre-validates actions before consensus (#406) and propagation (#408)
- Simulates: attitude cascade, power budget, thermal effects
- Blocks actions with >10% constellation risk increase
- <100ms simulation latency guarantee
- Prevents 10x slower post-facto recovery

Integration:
  ResponseOrchestrator (#412)
  → SafetySimulator (#413)
  → ConsensusEngine (#406) for approval
  → ActionPropagator (#408) for execution

Simulation Models:
  1. ATTITUDE CASCADE: neighbor coverage ripple effect
  2. POWER BUDGET: constellation power headroom validation
  3. THERMAL CASCADE: temperature propagation to neighbors

Risk Aggregation:
  - Base risk: direct action impact
  - Cascade risk: neighbor propagation
  - Total risk = base + cascade (block if >10%)

Dependencies:
  - SwarmRegistry (#400): peer health tracking
  - SwarmConfig (#397): risk thresholds, constellation params
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, List, Any
import time

logger = logging.getLogger(__name__)


class ActionType(Enum):
    """Types of actions that can be simulated."""
    ATTITUDE_ADJUST = "attitude_adjust"          # Coverage ripple effect
    LOAD_SHED = "load_shed"                      # Power budget impact
    THERMAL_MANEUVER = "thermal_maneuver"        # Thermal cascade
    SAFE_MODE = "safe_mode"                      # Safe transition (0% risk)
    ROLE_REASSIGNMENT = "role_reassignment"      # Role change (low risk)


@dataclass
class SimulationResult:
    """Result of swarm impact simulation."""
    is_safe: bool                      # True if risk <= threshold
    base_risk: float                   # Direct action risk (0.0-1.0)
    cascade_risk: float                # Propagated neighbor risk
    total_risk: float                  # base_risk + cascade_risk
    affected_agents: List[str]         # Serial numbers of affected agents
    risk_details: Dict[str, Any] = field(default_factory=dict)
    simulation_latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Export to dictionary."""
        return {
            "is_safe": self.is_safe,
            "base_risk": self.base_risk,
            "cascade_risk": self.cascade_risk,
            "total_risk": self.total_risk,
            "affected_agents_count": len(self.affected_agents),
            "risk_details": self.risk_details,
            "simulation_latency_ms": self.simulation_latency_ms,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class SafetyMetrics:
    """Metrics for safety simulator."""
    simulations_run: int = 0
    simulations_safe: int = 0
    simulations_blocked: int = 0
    total_blocked_risk: float = 0.0
    cascade_prevention_count: int = 0
    avg_simulation_latency_ms: float = 0.0
    p95_simulation_latency_ms: float = 0.0
    max_simulation_latency_ms: float = 0.0

    @property
    def safety_block_rate(self) -> float:
        """Percentage of simulations blocked (0.0-1.0)."""
        if self.simulations_run == 0:
            return 0.0
        return self.simulations_blocked / self.simulations_run

    def to_dict(self) -> dict:
        """Export metrics for Prometheus."""
        return {
            "safety_simulations_run": self.simulations_run,
            "safety_simulations_safe": self.simulations_safe,
            "safety_simulations_blocked": self.simulations_blocked,
            "safety_block_rate": self.safety_block_rate,
            "cascade_prevention_count": self.cascade_prevention_count,
            "simulation_latency_ms_avg": self.avg_simulation_latency_ms,
            "simulation_latency_ms_p95": self.p95_simulation_latency_ms,
            "simulation_latency_ms_max": self.max_simulation_latency_ms,
        }


class SwarmImpactSimulator:
    """
    Simulates constellation-wide impact of actions before execution.

    Three simulation models:
    1. ATTITUDE CASCADE: Attitude adjustments ripple to neighbors
    2. POWER BUDGET: Load shedding impacts constellation power headroom
    3. THERMAL CASCADE: Maneuvers cause thermal propagation

    Risk calculation:
    - Base risk: Direct action impact
    - Cascade risk: Neighbor propagation (weighted by coverage impact)
    - Total risk = base_risk + cascade_risk
    - BLOCK if total_risk > risk_threshold (default 10%)

    Integration point:
    - ResponseOrchestrator (#412) calls validate_action()
    - SafetySimulator blocks unsafe CONSTELLATION actions
    - Safe actions proceed to ConsensusEngine (#406) voting
    """

    # Risk thresholds (configurable via SwarmConfig)
    DEFAULT_RISK_THRESHOLD = 0.10  # 10% maximum risk increase
    ATTITUDE_CASCADE_MULTIPLIER = 0.30  # 10° attitude → 30% coverage loss
    POWER_BUDGET_MARGIN = 0.15  # 15% power margin required
    THERMAL_LIMIT_CELSIUS = 5.0  # <5°C temperature change limit

    # Simulation model weights
    ATTITUDE_BASE_WEIGHT = 0.40
    POWER_BASE_WEIGHT = 0.30
    THERMAL_BASE_WEIGHT = 0.30

    def __init__(
        self,
        registry: Optional[Any] = None,  # SwarmRegistry (#400)
        config: Optional[Any] = None,    # SwarmConfig (#397)
        risk_threshold: Optional[float] = None,
        swarm_mode_enabled: bool = True,
    ):
        """
        Initialize safety simulator.

        Args:
            registry: SwarmRegistry for peer health tracking
            config: SwarmConfig with risk thresholds
            risk_threshold: Custom risk threshold (default 10%)
            swarm_mode_enabled: Feature flag for swarm coordination
        """
        self.registry = registry
        self.config = config
        self.risk_threshold = risk_threshold or self.DEFAULT_RISK_THRESHOLD
        self.swarm_mode_enabled = swarm_mode_enabled

        # Metrics tracking
        self.metrics = SafetyMetrics()
        self.latency_samples: List[float] = []

        logger.info(
            f"SwarmImpactSimulator initialized "
            f"(risk_threshold={self.risk_threshold:.1%}, "
            f"swarm_mode={swarm_mode_enabled})"
        )

    async def validate_action(
        self,
        action: str,
        params: Dict[str, Any],
        decision_id: str = "",
        scope: str = "constellation",
    ) -> bool:
        """
        Validate action against constellation safety constraints.

        Algorithm:
        1. Classify action type
        2. Calculate base risk
        3. Simulate cascade effects (neighbor propagation)
        4. Aggregate total risk
        5. Block if risk > threshold

        Args:
            action: Action name (e.g., "attitude_adjust")
            params: Action parameters (e.g., {"angle_degrees": 10})
            decision_id: Optional decision identifier for logging
            scope: Action scope ("local", "swarm", "constellation")

        Returns:
            bool: True if safe, False if blocked
        """
        import time
        start_time = time.time()

        try:
            # Only validate CONSTELLATION actions
            if scope != "constellation":
                logger.debug(
                    f"Skipping safety validation for non-constellation scope: {scope}"
                )
                return True

            # Feature flag check
            if not self.swarm_mode_enabled:
                logger.debug("Safety validation disabled: SWARM_MODE_ENABLED=False")
                return True

            # Classify and simulate action
            action_type = self._classify_action(action)
            result = await self._simulate_action(action_type, params)

            # Track metrics
            self.metrics.simulations_run += 1
            elapsed_ms = (time.time() - start_time) * 1000
            self.latency_samples.append(elapsed_ms)
            self._update_latency_metrics(elapsed_ms)

            if result.is_safe:
                self.metrics.simulations_safe += 1
                logger.info(
                    f"Action APPROVED by safety check: {action} "
                    f"(risk={result.total_risk:.1%}, {decision_id})"
                )
            else:
                self.metrics.simulations_blocked += 1
                self.metrics.cascade_prevention_count += 1
                self.metrics.total_blocked_risk += result.total_risk
                logger.warning(
                    f"Action BLOCKED by safety check: {action} "
                    f"(risk={result.total_risk:.1%} > {self.risk_threshold:.1%}, "
                    f"{decision_id})"
                )

            return result.is_safe

        except Exception as e:
            logger.error(
                f"Error in safety validation: {e}",
                exc_info=True,
            )
            # Safe default: block on error
            self.metrics.simulations_blocked += 1
            return False

    def _classify_action(self, action: str) -> ActionType:
        """Classify action for simulation model selection."""
        action_lower = action.lower()

        if "attitude" in action_lower:
            return ActionType.ATTITUDE_ADJUST
        elif "load" in action_lower or "power" in action_lower:
            return ActionType.LOAD_SHED
        elif "thermal" in action_lower or "maneuver" in action_lower:
            return ActionType.THERMAL_MANEUVER
        elif "safe" in action_lower:
            return ActionType.SAFE_MODE
        elif "role" in action_lower:
            return ActionType.ROLE_REASSIGNMENT
        else:
            # Default to low-risk action
            logger.warning(f"Unknown action type: {action}, defaulting to low-risk")
            return ActionType.ROLE_REASSIGNMENT

    async def _simulate_action(
        self,
        action_type: ActionType,
        params: Dict[str, Any],
    ) -> SimulationResult:
        """Simulate constellation impact of action."""

        affected_agents = []

        # Route to appropriate simulation model
        if action_type == ActionType.ATTITUDE_ADJUST:
            base_risk = await self._simulate_attitude_cascade(params)
            affected_agents = await self._get_coverage_neighbors()

        elif action_type == ActionType.LOAD_SHED:
            base_risk = await self._simulate_power_budget(params)
            affected_agents = await self._get_all_agents()

        elif action_type == ActionType.THERMAL_MANEUVER:
            base_risk = await self._simulate_thermal_cascade(params)
            affected_agents = await self._get_thermal_neighbors()

        elif action_type == ActionType.SAFE_MODE:
            # Safe mode transition has minimal risk
            base_risk = 0.0
            affected_agents = []

        else:  # ROLE_REASSIGNMENT
            # Role change has low risk
            base_risk = 0.05  # 5% base risk
            affected_agents = []

        # Simulate cascade effects
        cascade_risk = await self._propagate_to_neighbors(base_risk, affected_agents)
        total_risk = base_risk + cascade_risk

        # Determine safety
        is_safe = total_risk <= self.risk_threshold

        return SimulationResult(
            is_safe=is_safe,
            base_risk=base_risk,
            cascade_risk=cascade_risk,
            total_risk=total_risk,
            affected_agents=affected_agents,
            risk_details={
                "action_type": action_type.value,
                "threshold": self.risk_threshold,
                "neighbor_count": len(affected_agents),
            },
        )

    async def _simulate_attitude_cascade(self, params: Dict[str, Any]) -> float:
        """
        Simulate attitude adjustment cascade effect.

        Model:
        - 10° attitude change → 3% coverage loss per neighbor
        - 10 neighbors × 3% = 30% constellation coverage loss
        - Base risk = (attitude_change_degrees / 10) × CASCADE_MULTIPLIER

        Args:
            params: {"angle_degrees": float}

        Returns:
            float: Base risk (0.0-1.0)
        """
        angle = params.get("angle_degrees", 0.0)

        # Risk scales with attitude change
        # 10° = 40% risk, 5° = 20% risk, 1° = 4% risk
        base_risk = (angle / 10.0) * self.ATTITUDE_CASCADE_MULTIPLIER

        # Cap at 1.0
        return min(1.0, base_risk)

    async def _simulate_power_budget(self, params: Dict[str, Any]) -> float:
        """
        Simulate power budget impact of load shedding.

        Model:
        - Current constellation power consumption
        - Load shedding amount
        - If (current_power + load_shed) > constellation_max: high risk
        - Risk = (power_after / power_max) - POWER_BUDGET_MARGIN

        Args:
            params: {"shed_percent": float}

        Returns:
            float: Base risk (0.0-1.0)
        """
        shed_percent = params.get("shed_percent", 0.0)

        # Shedding increases risk only if margin becomes critical
        # Normal: 80% utilization, 20% margin
        # After shed: 95% utilization, 5% margin → higher risk
        # Risk = max(0, (utilization - (1 - margin)) / margin)

        if shed_percent <= self.POWER_BUDGET_MARGIN * 100:
            # Safe shedding amount
            return 0.0
        else:
            # Risky shedding
            excess = shed_percent - (self.POWER_BUDGET_MARGIN * 100)
            base_risk = excess / 100.0  # Scale to risk

        return min(1.0, base_risk)

    async def _simulate_thermal_cascade(self, params: Dict[str, Any]) -> float:
        """
        Simulate thermal cascade from maneuver.

        Model:
        - Maneuver creates heat
        - Propagates to neighbors
        - ΔTemperature < 5°C is safe
        - Risk = (delta_temp / thermal_limit)

        Args:
            params: {"delta_temperature": float}

        Returns:
            float: Base risk (0.0-1.0)
        """
        delta_temp = params.get("delta_temperature", 0.0)

        if delta_temp <= self.THERMAL_LIMIT_CELSIUS:
            # Safe temperature change
            return 0.0
        else:
            # Risky thermal change
            base_risk = delta_temp / (self.THERMAL_LIMIT_CELSIUS * 10)

        return min(1.0, base_risk)

    async def _propagate_to_neighbors(
        self,
        base_risk: float,
        affected_agents: List[str],
    ) -> float:
        """
        Propagate base risk to neighbors (cascade effect).

        Algorithm:
        - For each affected agent, propagate risk to neighbors
        - Each neighbor receives: base_risk × propagation_factor
        - Propagation stops after 1 hop (immediate neighbors only)
        - Total cascade_risk = sum(neighbor_risks) / neighbor_count

        Args:
            base_risk: Direct action risk
            affected_agents: List of agent serials directly affected

        Returns:
            float: Cascaded risk (0.0-1.0)
        """
        if not affected_agents or base_risk == 0:
            return 0.0

        # Propagation factor: neighbors inherit fraction of base risk
        propagation_factor = 0.15  # 15% of base risk propagates to neighbors

        total_cascade_risk = 0.0

        for agent_serial in affected_agents:
            # Get neighbors of this affected agent
            neighbor_serials = await self._get_agent_neighbors(agent_serial)

            # Each neighbor receives propagated risk
            for _ in neighbor_serials:
                neighbor_risk = base_risk * propagation_factor
                total_cascade_risk += neighbor_risk

        # Normalize by number of affected agents
        if affected_agents:
            cascade_risk = total_cascade_risk / len(affected_agents)
        else:
            cascade_risk = 0.0

        return min(1.0, cascade_risk)

    async def _get_coverage_neighbors(self) -> List[str]:
        """Get agents affected by coverage changes (attitude adjustment)."""
        if not self.registry:
            return []

        peers = self.registry.get_alive_peers()
        # Return serial numbers (typically first 5-10 neighbors)
        return [peer.satellite_serial for peer in peers[:10]]

    async def _get_thermal_neighbors(self) -> List[str]:
        """Get agents affected by thermal changes (nearby orbit)."""
        if not self.registry:
            return []

        peers = self.registry.get_alive_peers()
        # Return serial numbers (typically 3-5 nearest neighbors)
        return [peer.satellite_serial for peer in peers[:5]]

    async def _get_all_agents(self) -> List[str]:
        """Get all constellation agents (for power budget impacts)."""
        if not self.registry:
            return []

        peers = self.registry.get_alive_peers()
        return [peer.satellite_serial for peer in peers]

    async def _get_agent_neighbors(self, agent_serial: str) -> List[str]:
        """Get neighbors of a specific agent."""
        if not self.registry:
            return []

        # Simplified: return all other agents
        peers = self.registry.get_alive_peers()
        neighbors = [
            p.satellite_serial for p in peers
            if p.satellite_serial != agent_serial
        ]
        return neighbors

    def _update_latency_metrics(self, latency_ms: float) -> None:
        """Update latency metrics with new sample."""
        # Update average
        total = sum(self.latency_samples)
        self.metrics.avg_simulation_latency_ms = total / len(self.latency_samples)

        # Update P95
        if len(self.latency_samples) >= 20:
            sorted_samples = sorted(self.latency_samples)
            p95_index = int(len(sorted_samples) * 0.95)
            self.metrics.p95_simulation_latency_ms = sorted_samples[p95_index]

        # Update max
        self.metrics.max_simulation_latency_ms = max(self.latency_samples)

    def get_metrics(self) -> SafetyMetrics:
        """Get current metrics snapshot."""
        return self.metrics

    def reset_metrics(self) -> None:
        """Reset all metrics."""
        self.metrics = SafetyMetrics()
        self.latency_samples = []
