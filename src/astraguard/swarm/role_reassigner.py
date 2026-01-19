"""
Role Reassignment Engine for self-healing satellite constellation.

Issue #409: Dynamic role reassignment logic
Depends on: #397 (models), #400 (registry), #405 (leader election), #408 (action propagation)

Algorithm:
1. Leader evaluates health + compliance every 30s
2. PRIMARY health < 0.3 for 5min (3+ consecutive failures) → Quorum votes → BACKUP promoted
3. Compliance <90% → PRIMARY → STANDBY demotion
4. 2+ consecutive failures → SAFE_MODE isolation
5. STANDBY health > 0.8 → Eligible for reverse promotion (quorum approval)

Hysteresis: Prevents flapping during intermittent faults (20% packet loss tolerance)
Failover time: <5min p95
Metrics: role_changes_total, failover_time_seconds, flapping_events_blocked

Role Transition States:
  PRIMARY → BACKUP → STANDBY → SAFE_MODE (escalation)
  Recovery: SAFE_MODE → STANDBY → BACKUP → PRIMARY (with quorum approval)
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Set
from enum import Enum
from collections import deque

from astraguard.swarm.models import AgentID, SatelliteRole, HealthSummary, SwarmConfig
from astraguard.swarm.registry import SwarmRegistry
from astraguard.swarm.leader_election import LeaderElection
from astraguard.swarm.action_propagator import ActionPropagator
from astraguard.swarm.consensus import ConsensusEngine, NotLeaderError

logger = logging.getLogger(__name__)


class FailureMode(str, Enum):
    """Failure classification for escalation decisions."""
    HEALTHY = "healthy"
    INTERMITTENT = "intermittent"  # 1-2 failures in 5min
    DEGRADED = "degraded"  # 3+ consecutive failures
    CRITICAL = "critical"  # Multiple agents affected


@dataclass
class HealthHistory:
    """Track health measurements with timestamps for hysteresis logic."""
    agent_id: AgentID
    measurements: deque = field(default_factory=lambda: deque(maxlen=6))  # 5min window at 30s intervals
    last_update: datetime = field(default_factory=datetime.utcnow)
    failure_count: int = 0
    consecutive_below_threshold: int = 0

    def add_measurement(self, risk_score: float) -> None:
        """Record health measurement."""
        self.measurements.append((datetime.utcnow(), risk_score))
        self.last_update = datetime.utcnow()

        # Update consecutive failure count
        if risk_score > 0.3:  # Unhealthy threshold
            self.consecutive_below_threshold += 1
        else:
            self.consecutive_below_threshold = 0

    def get_failure_mode(self) -> FailureMode:
        """Classify failure severity based on recent history."""
        if len(self.measurements) == 0:
            return FailureMode.HEALTHY

        recent = [score for _, score in list(self.measurements)[-6:]]
        unhealthy_count = sum(1 for score in recent if score > 0.3)

        if unhealthy_count == 0:
            return FailureMode.HEALTHY
        elif unhealthy_count <= 2:
            return FailureMode.INTERMITTENT
        elif unhealthy_count >= 4:
            return FailureMode.CRITICAL
        else:
            return FailureMode.DEGRADED

    def is_healthy_for_promotion(self) -> bool:
        """Check if agent is healthy enough to be promoted."""
        if len(self.measurements) < 3:  # Need 90s of data
            return False
        recent = [score for _, score in list(self.measurements)[-6:]]
        # All recent measurements must be < 0.2 (healthy threshold for promotion)
        return all(score < 0.2 for score in recent)


@dataclass
class RoleReassignerMetrics:
    """Metrics for role reassignment and failover tracking."""
    role_changes_total: int = 0
    failover_time_seconds: Dict[str, float] = field(default_factory=dict)
    flapping_events_blocked: int = 0
    role_distribution: Dict[str, int] = field(
        default_factory=lambda: {
            "primary": 0,
            "backup": 0,
            "standby": 0,
            "safe_mode": 0,
        }
    )
    last_reassignment: Optional[datetime] = None
    failed_reassignments: int = 0

    def to_dict(self) -> dict:
        """Export metrics for Prometheus."""
        return {
            "role_changes_total": self.role_changes_total,
            "failover_time_p95": max(self.failover_time_seconds.values()) if self.failover_time_seconds else 0.0,
            "flapping_events_blocked": self.flapping_events_blocked,
            "role_distribution": self.role_distribution,
            "failed_reassignments": self.failed_reassignments,
        }


class RoleReassigner:
    """
    Leader-driven role reassignment for self-healing satellite constellation.

    Attributes:
        registry: SwarmRegistry for peer health tracking
        election: LeaderElection for leader verification
        propagator: ActionPropagator for role change execution
        consensus: ConsensusEngine for quorum validation
        health_threshold: Risk score trigger for demotion (0.3)
        promotion_threshold: Risk score for promotion eligibility (0.2)
        hysteresis_window: 5 minutes to prevent flapping
        health_histories: Dict mapping AgentID to HealthHistory
    """

    # Configuration
    HEALTH_THRESHOLD = 0.3  # Risk score trigger for PRIMARY failure
    PROMOTION_THRESHOLD = 0.2  # Health required for promotion
    HYSTERESIS_WINDOW = 300  # 5 minutes in seconds
    EVAL_INTERVAL = 30  # Evaluation every 30s (leader-only)
    COMPLIANCE_THRESHOLD = 0.90  # From ActionPropagator
    PROMOTION_QUORUM_REQUIRED = True

    def __init__(
        self,
        registry: SwarmRegistry,
        election: LeaderElection,
        propagator: ActionPropagator,
        consensus: ConsensusEngine,
        config: SwarmConfig,
    ):
        """Initialize role reassigner.

        Args:
            registry: SwarmRegistry for peer discovery
            election: LeaderElection for leader verification
            propagator: ActionPropagator for action broadcasting
            consensus: ConsensusEngine for quorum validation
            config: SwarmConfig for this agent
        """
        self.registry = registry
        self.election = election
        self.propagator = propagator
        self.consensus = consensus
        self.config = config

        # Health tracking
        self.health_histories: Dict[AgentID, HealthHistory] = {}
        self.role_change_timestamps: Dict[str, datetime] = {}  # Track failover timing
        self.metrics = RoleReassignerMetrics()

        # Task management
        self._eval_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        """Start role reassignment evaluation loop (leader-only)."""
        if not self.config.SWARM_MODE_ENABLED:
            logger.debug("Swarm mode disabled, skipping role reassignment")
            return

        self._running = True
        logger.info(f"Starting role reassigner for {self.config.agent_id.satellite_serial}")
        self._eval_task = asyncio.create_task(self._evaluation_loop())

    async def stop(self) -> None:
        """Stop role reassignment evaluation."""
        self._running = False
        if self._eval_task:
            self._eval_task.cancel()
        logger.info("Role reassigner stopped")

    async def _evaluation_loop(self) -> None:
        """Main loop: Leader evaluates roles every 30s."""
        while self._running:
            try:
                if self.election.is_leader():
                    await self.evaluate_roles()
                await asyncio.sleep(self.EVAL_INTERVAL)
            except Exception as e:
                logger.error(f"Role evaluation error: {e}", exc_info=True)
                await asyncio.sleep(self.EVAL_INTERVAL)

    async def evaluate_roles(self) -> None:
        """
        Leader-only: Check health + compliance → Propose reassignments.

        Algorithm:
        1. Collect health from all peers via registry
        2. Classify failures (healthy, intermittent, degraded, critical)
        3. Check compliance from action propagator
        4. Propose role changes via consensus
        5. Execute approved changes via action propagator
        """
        if not self.election.is_leader():
            return

        try:
            alive_peers = self.registry.get_alive_peers()
            logger.debug(f"Evaluating roles for {len(alive_peers)} alive peers")

            # Collect health measurements
            for peer in alive_peers:
                peer_state = self.registry.peers.get(peer)
                if peer_state and peer_state.health_summary:
                    if peer not in self.health_histories:
                        self.health_histories[peer] = HealthHistory(agent_id=peer)
                    self.health_histories[peer].add_measurement(
                        peer_state.health_summary.risk_score
                    )

            # Evaluate each peer for reassignment
            reassignments = []
            for peer, history in self.health_histories.items():
                failure_mode = history.get_failure_mode()
                peer_state = self.registry.peers.get(peer)
                if not peer_state:
                    continue

                current_role = peer_state.role

                # PRIMARY failure detection (3+ consecutive failures in 5min)
                if (
                    current_role == SatelliteRole.PRIMARY
                    and history.consecutive_below_threshold >= 3
                    and failure_mode in (FailureMode.DEGRADED, FailureMode.CRITICAL)
                ):
                    logger.warning(
                        f"PRIMARY {peer.satellite_serial} degraded "
                        f"({history.consecutive_below_threshold} failures), "
                        f"promoting BACKUP"
                    )
                    reassignments.append(self._propose_primary_failure_promotion(peer))

                # Compliance-based demotion (handled via action propagator escalation)
                elif (
                    current_role == SatelliteRole.PRIMARY
                    and self._is_compliance_failing(peer)
                ):
                    logger.warning(
                        f"PRIMARY {peer.satellite_serial} failing compliance, "
                        f"demoting to STANDBY"
                    )
                    reassignments.append(self._propose_compliance_demotion(peer))

                # STANDBY recovery path (health > 0.2)
                elif (
                    current_role in (SatelliteRole.STANDBY, SatelliteRole.SAFE_MODE)
                    and history.is_healthy_for_promotion()
                ):
                    target_role = SatelliteRole.BACKUP if current_role == SatelliteRole.STANDBY else SatelliteRole.STANDBY
                    logger.info(
                        f"{current_role.value.upper()} {peer.satellite_serial} "
                        f"recovered, promoting to {target_role.value}"
                    )
                    reassignments.append(self._propose_recovery_promotion(peer, target_role))

            # Execute approved reassignments
            if reassignments:
                await self._execute_reassignments(reassignments)

        except Exception as e:
            logger.error(f"Role evaluation failed: {e}", exc_info=True)

    def _propose_primary_failure_promotion(self, failed_primary: AgentID) -> Dict:
        """Propose PRIMARY failure → BACKUP promotion."""
        # Find available BACKUP
        backup_candidate = self._find_role_candidate(SatelliteRole.BACKUP)
        if not backup_candidate:
            # Fallback to STANDBY
            backup_candidate = self._find_role_candidate(SatelliteRole.STANDBY)

        if not backup_candidate:
            logger.warning(f"No BACKUP/STANDBY available to promote for {failed_primary.satellite_serial}")
            return None

        self.role_change_timestamps[failed_primary.satellite_serial] = datetime.utcnow()

        return {
            "action": "role_change",
            "target": failed_primary.satellite_serial,
            "from_role": SatelliteRole.PRIMARY.value,
            "to_role": SatelliteRole.BACKUP.value,
            "backup_promotion_target": backup_candidate.satellite_serial,
            "backup_promotion_to": SatelliteRole.PRIMARY.value,
            "reason": "primary_failure_hysteresis_exceeded",
        }

    def _propose_compliance_demotion(self, agent: AgentID) -> Dict:
        """Propose compliance failure → STANDBY demotion."""
        return {
            "action": "role_change",
            "target": agent.satellite_serial,
            "from_role": SatelliteRole.PRIMARY.value,
            "to_role": SatelliteRole.STANDBY.value,
            "reason": "compliance_failure",
        }

    def _propose_recovery_promotion(self, agent: AgentID, target_role: SatelliteRole) -> Dict:
        """Propose recovery-based promotion (STANDBY → BACKUP or SAFE_MODE → STANDBY)."""
        return {
            "action": "role_change",
            "target": agent.satellite_serial,
            "from_role": self.registry.peers[agent].role.value,
            "to_role": target_role.value,
            "reason": "health_recovery",
        }

    def _find_role_candidate(self, role: SatelliteRole) -> Optional[AgentID]:
        """Find healthy agent with specified role."""
        for agent, state in self.registry.peers.items():
            if state.role == role and state.is_alive:
                history = self.health_histories.get(agent)
                if history and history.get_failure_mode() == FailureMode.HEALTHY:
                    return agent
        return None

    def _is_compliance_failing(self, agent: AgentID) -> bool:
        """Check if agent is failing compliance from propagator."""
        # Access escalated agents from action propagator metrics
        for action in self.propagator.pending_actions.values():
            if agent.satellite_serial in action.escalated_agents:
                return True
        return False

    async def _execute_reassignments(self, reassignments: List[Dict]) -> None:
        """Execute role reassignments via consensus + action propagation."""
        for reassignment in reassignments:
            if not reassignment:
                continue

            try:
                # Use consensus for binding decisions
                approved = await self.consensus.propose(
                    action="role_reassign",
                    params=reassignment,
                    timeout=5,
                )

                if approved:
                    # Propagate role change via action propagator
                    target_agents = self.registry.get_alive_peers()
                    await self.propagator.propagate_action(
                        action="role_change",
                        parameters=reassignment,
                        target_agents=target_agents,
                        deadline_seconds=30,
                    )

                    self.metrics.role_changes_total += 1
                    self.metrics.last_reassignment = datetime.utcnow()

                    # Update local registry role
                    target_serial = reassignment["target"]
                    for agent in self.registry.peers:
                        if agent.satellite_serial == target_serial:
                            self.registry.peers[agent].role = SatelliteRole(reassignment["to_role"])
                            self.metrics.role_distribution[reassignment["to_role"]] += 1
                            break

                    # Track failover time if PRIMARY failure
                    if reassignment.get("reason") == "primary_failure_hysteresis_exceeded":
                        failover_start = self.role_change_timestamps.get(target_serial)
                        if failover_start:
                            elapsed = (datetime.utcnow() - failover_start).total_seconds()
                            self.metrics.failover_time_seconds[target_serial] = elapsed
                            logger.info(f"Failover completed for {target_serial} in {elapsed:.1f}s")

                else:
                    logger.warning(f"Consensus rejected role change for {reassignment['target']}")
                    self.metrics.failed_reassignments += 1

            except NotLeaderError:
                logger.debug("Lost leadership during reassignment execution")
                break
            except Exception as e:
                logger.error(f"Reassignment execution failed: {e}", exc_info=True)
                self.metrics.failed_reassignments += 1

    def get_metrics(self) -> RoleReassignerMetrics:
        """Export current metrics."""
        # Update role distribution from registry
        self.metrics.role_distribution = {
            "primary": 0,
            "backup": 0,
            "standby": 0,
            "safe_mode": 0,
        }
        for state in self.registry.peers.values():
            role_key = state.role.value
            if role_key in self.metrics.role_distribution:
                self.metrics.role_distribution[role_key] += 1

        return self.metrics

    def reset_metrics(self) -> None:
        """Reset metrics for testing."""
        self.metrics = RoleReassignerMetrics()
        self.health_histories.clear()
        self.role_change_timestamps.clear()
