"""
Distributed Resilience Coordinator for cluster-wide consensus (Refactored for Issue #444)

Provides:
- Leader election coordination
- State publishing to cluster
- Vote collection and majority voting
- Quorum-based consensus decisions
- Multi-instance synchronization

Refactoring (Issue #444):
- Implements Coordinator interface
- Uses dependency injection for all external dependencies
- Pure consensus logic with side-effects through injected components
"""

import asyncio
import uuid
import logging
import math
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from collections import Counter

from backend.orchestration.coordinator import CoordinatorBase, ConsensusDecision, NodeInfo
from backend.redis_client import RedisClient

logger = logging.getLogger(__name__)


class DistributedResilienceCoordinator(CoordinatorBase):
    """Cluster-wide resilience state coordination via Redis.

    Responsibilities:
    - Lead cluster-wide state synchronization
    - Coordinate leader election
    - Collect votes from all instances
    - Apply majority voting for circuit/fallback decisions
    - Publish local state changes
    - Maintain quorum requirements
    
    Refactored (Issue #444):
    - Extends CoordinatorBase
    - All dependencies injected via constructor
    - Side-effects isolated to injected components (Redis, health monitor)
    """

    def __init__(
        self,
        redis_client: RedisClient,
        health_monitor,
        recovery_orchestrator=None,
        fallback_manager=None,
        instance_id: Optional[str] = None,
        quorum_threshold: float = 0.5,
    ):
        """Initialize distributed coordinator with dependency injection.

        Args:
            redis_client: RedisClient instance for communication
            health_monitor: HealthMonitor for local state
            recovery_orchestrator: Recovery orchestrator for actions (optional)
            fallback_manager: FallbackManager for mode changes (optional)
            instance_id: Unique instance identifier (auto-generated if None)
            quorum_threshold: Minimum fraction for quorum (default: >50%)
        """
        # Initialize base class
        super().__init__(instance_id=instance_id, quorum_threshold=quorum_threshold)
        
        # Injected dependencies
        self.redis = redis_client
        self.health = health_monitor
        self.recovery = recovery_orchestrator
        self.fallback = fallback_manager

        # Background tasks
        self._state_publisher_task = None
        self._leader_renewal_task = None
        self._vote_collector_task = None

        # Metrics
        self.election_wins = 0
        self.consensus_decisions = 0
        self.last_consensus_time = None

        logger.info(f"Initialized DistributedResilienceCoordinator: {self.instance_id}")

    async def startup(self):
        """Initialize distributed coordination.

        Attempts leader election and starts background tasks.
        """
        if not self.redis.connected:
            logger.error("Redis not connected, cannot start coordinator")
            return

        # Attempt leader election
        self.is_leader = await self.redis.leader_election(self.instance_id)
        if self.is_leader:
            self.election_wins += 1
            logger.info(f"Instance {self.instance_id} elected as LEADER")
        else:
            logger.info(f"Instance {self.instance_id} running as FOLLOWER")

        # Start background tasks
        self._running = True
        self._state_publisher_task = asyncio.create_task(self._state_publisher())
        self._leader_renewal_task = asyncio.create_task(self._leader_renewal())
        self._vote_collector_task = asyncio.create_task(self._vote_collector())

        logger.info("Distributed coordination started")

    async def shutdown(self):
        """Gracefully shutdown coordination."""
        self._running = False

        # Cancel and await background tasks with proper exception handling
        tasks_to_cancel = [
            ("state_publisher", self._state_publisher_task),
            ("leader_renewal", self._leader_renewal_task),
            ("vote_collector", self._vote_collector_task),
        ]

        for task_name, task in tasks_to_cancel:
            if task:
                try:
                    task.cancel()
                    await task
                except asyncio.CancelledError:
                    logger.debug(f"Task {task_name} cancelled successfully")
                except Exception as e:
                    logger.warning(f"Error during {task_name} shutdown: {e}")
                finally:
                    # Clear task reference
                    if task_name == "state_publisher":
                        self._state_publisher_task = None
                    elif task_name == "leader_renewal":
                        self._leader_renewal_task = None
                    elif task_name == "vote_collector":
                        self._vote_collector_task = None

        logger.info("Distributed coordination stopped")

    # ========== INTERFACE METHODS ==========

    async def elect_leader(self) -> bool:
        """
        Attempt to become cluster leader.
        
        Returns:
            True if this instance became leader, False otherwise
        """
        if not self.redis.connected:
            logger.error("Redis not connected, cannot elect leader")
            return False
        
        self.is_leader = await self.redis.leader_election(self.instance_id)
        if self.is_leader:
            self.election_wins += 1
            logger.info(f"Instance {self.instance_id} elected as LEADER")
        return self.is_leader

    async def assign_work(self, work_item: Dict[str, Any]) -> str:
        """
        Assign work to a cluster node.
        
        In this implementation, work is broadcast and nodes self-select.
        The leader node typically handles coordination.
        
        Args:
            work_item: Work to be assigned
            
        Returns:
            Instance ID that should handle the work (leader or self)
        """
        try:
            leader = await self.redis.get_leader()
            if leader:
                return leader
            return self.instance_id
        except Exception as e:
            logger.error(f"Failed to assign work: {e}")
            return self.instance_id

    async def heartbeat(self) -> None:
        """
        Send heartbeat to indicate this instance is alive.
        
        Updates vote registration with current timestamp.
        """
        try:
            # Get local state for voting (includes heartbeat)
            local_state = await self.health.get_comprehensive_state()
            
            circuit_state = local_state.get("circuit_breaker", {}).get("state", "UNKNOWN")
            fallback_mode = local_state.get("fallback", {}).get("mode", "PRIMARY")
            health_score = self._compute_health_score(local_state)
            
            vote = {
                "circuit_breaker_state": circuit_state,
                "fallback_mode": fallback_mode,
                "health_score": health_score,
                "timestamp": datetime.utcnow().isoformat(),
            }
            
            await self.redis.register_vote(self.instance_id, vote, ttl=30)
        except Exception as e:
            logger.error(f"Heartbeat failed: {e}")

    async def get_nodes(self) -> List[NodeInfo]:
        """
        Get list of all active nodes in cluster.
        
        Returns:
            List of NodeInfo for each active node
        """
        try:
            votes = await self.redis.get_cluster_votes()
            nodes = []
            
            leader = await self.redis.get_leader()
            
            for instance_id, vote in votes.items():
                try:
                    timestamp_str = vote.get("timestamp", "")
                    last_heartbeat = (
                        datetime.fromisoformat(timestamp_str)
                        if timestamp_str
                        else datetime.utcnow()
                    )
                    
                    node = NodeInfo(
                        instance_id=instance_id,
                        is_leader=(instance_id == leader),
                        health_score=vote.get("health_score", 0.5),
                        last_heartbeat=last_heartbeat,
                        state=vote,
                    )
                    nodes.append(node)
                except Exception as e:
                    logger.warning(f"Failed to parse node info for {instance_id}: {e}")
            
            return nodes
        except Exception as e:
            logger.error(f"Failed to get nodes: {e}")
            return []

    async def get_consensus(self) -> ConsensusDecision:
        """
        Get consensus decision from cluster quorum.
        
        Alias for get_cluster_consensus for interface compatibility.
        
        Returns:
            ConsensusDecision with cluster consensus
        """
        return await self.get_cluster_consensus()

    # ========== BACKGROUND TASKS ==========

    async def _state_publisher(self, interval: int = 5):
        """Continuously publish local state to cluster.

        Args:
            interval: Publication interval in seconds
        """
        while self._running:
            try:
                # Get local state
                local_state = await self.health.get_comprehensive_state()

                # Add instance metadata
                state_payload = {
                    "instance_id": self.instance_id,
                    "is_leader": self.is_leader,
                    "timestamp": datetime.utcnow().isoformat(),
                    "state": local_state,
                }

                # Publish to cluster
                await self.redis.publish_state("astra:resilience:state", state_payload)

                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"State publisher error: {e}")
                await asyncio.sleep(interval)

    async def _leader_renewal(self, interval: int = 15):
        """Renew leadership TTL if leader.

        Args:
            interval: Renewal interval in seconds
        """
        while self._running:
            try:
                if self.is_leader:
                    renewed = await self.redis.renew_leadership(
                        self.instance_id, ttl=30
                    )
                    if not renewed:
                        logger.warning(f"Lost leadership: {self.instance_id}")
                        self.is_leader = False
                    else:
                        logger.debug("Leadership renewed")
                else:
                    # Try to become leader if not already
                    self.is_leader = await self.redis.leader_election(
                        self.instance_id, ttl=30
                    )
                    if self.is_leader:
                        self.election_wins += 1
                        logger.info(f"Became leader: {self.instance_id}")

                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Leader renewal error: {e}")
                await asyncio.sleep(interval)

    def _compute_health_score(self, local_state: Dict[str, Any]) -> float:
        """Compute normalized health score (0.0-1.0) from component states.

        Combines weights from:
        - System health status (40% weight)
        - Circuit breaker state (35% weight)
        - Retry metrics state (25% weight)

        Args:
            local_state: Comprehensive state dict from get_comprehensive_state()

        Returns:
            Normalized health score between 0.0 (failed) and 1.0 (healthy)
        """
        # System health status mapping (40% weight)
        system_status = local_state.get("system", {}).get("status", "UNKNOWN")
        system_scores = {
            "HEALTHY": 1.0,
            "DEGRADED": 0.6,
            "FAILED": 0.0,
            "UNKNOWN": 0.5,
        }
        system_score = system_scores.get(system_status, 0.5) * 0.40

        # Circuit breaker state mapping (35% weight)
        cb_state = local_state.get("circuit_breaker", {}).get("state", "UNKNOWN")
        cb_scores = {
            "CLOSED": 1.0,
            "HALF_OPEN": 0.5,
            "OPEN": 0.0,
            "UNKNOWN": 0.5,
        }
        cb_score = cb_scores.get(cb_state, 0.5) * 0.35

        # Retry metrics state mapping (25% weight)
        retry_state = local_state.get("retry", {}).get("state", "UNKNOWN")
        retry_scores = {
            "STABLE": 1.0,
            "ELEVATED": 0.5,
            "CRITICAL": 0.0,
            "UNKNOWN": 0.5,
        }
        retry_score = retry_scores.get(retry_state, 0.5) * 0.25

        # Normalized health score
        health_score = system_score + cb_score + retry_score

        logger.debug(
            f"Computed health_score={health_score:.2f} "
            f"(system={system_score:.2f}, cb={cb_score:.2f}, retry={retry_score:.2f})"
        )

        return health_score

    async def _vote_collector(self, interval: int = 5):
        """Collect and register cluster votes.

        Args:
            interval: Collection interval in seconds
        """
        while self._running:
            try:
                # Get local state for voting
                local_state = await self.health.get_comprehensive_state()

                # Extract values from nested structure
                circuit_state = local_state.get("circuit_breaker", {}).get(
                    "state", "UNKNOWN"
                )
                fallback_mode = local_state.get("fallback", {}).get("mode", "PRIMARY")

                # Compute health_score from available component states
                health_score = self._compute_health_score(local_state)

                # Create vote
                vote = {
                    "circuit_breaker_state": circuit_state,
                    "fallback_mode": fallback_mode,
                    "health_score": health_score,
                    "timestamp": datetime.utcnow().isoformat(),
                }

                # Register vote
                await self.redis.register_vote(self.instance_id, vote, ttl=30)

                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Vote collector error: {e}")
                await asyncio.sleep(interval)

    async def get_cluster_consensus(self) -> ConsensusDecision:
        """Get quorum-based consensus decision from cluster.

        Collects votes from all instances and applies majority voting.
        Requires >50% quorum for valid consensus.

        Returns:
            ConsensusDecision with cluster consensus
        """
        try:
            # Get all votes
            votes = await self.redis.get_cluster_votes()

            if not votes:
                logger.warning("No votes available for consensus")
                return ConsensusDecision(
                    circuit_state="UNKNOWN",
                    fallback_mode="SAFE",
                    leader_instance="",
                    quorum_met=False,
                    voting_instances=0,
                    consensus_strength=0.0,
                )

            # Extract state values
            circuit_votes = [
                v.get("circuit_breaker_state", "UNKNOWN") for v in votes.values()
            ]
            fallback_votes = [v.get("fallback_mode", "PRIMARY") for v in votes.values()]

            # Majority voting
            circuit_consensus = self._majority_vote(circuit_votes)
            fallback_consensus = self._majority_vote(fallback_votes)

            # Get leader
            leader = await self.redis.get_leader()

            # Calculate quorum using configured threshold
            num_votes = len(votes)
            total_nodes = num_votes  # Use voting instances as cluster size

            # Validate quorum threshold is in valid range (0, 1]
            if not (0 < self.quorum_threshold <= 1):
                logger.warning(
                    f"Invalid quorum_threshold {self.quorum_threshold}, "
                    f"defaulting to 0.5 (majority)"
                )
                effective_threshold = 0.5
            else:
                effective_threshold = self.quorum_threshold

            # Calculate required votes for quorum
            required_votes = math.ceil(effective_threshold * total_nodes)
            quorum_met = num_votes >= required_votes

            # Calculate consensus strength
            if circuit_consensus != "SPLIT_BRAIN":
                circuit_strength = (
                    sum(1 for v in circuit_votes if v == circuit_consensus) / num_votes
                )
            else:
                circuit_strength = 0.0

            decision = ConsensusDecision(
                circuit_state=circuit_consensus,
                fallback_mode=fallback_consensus,
                leader_instance=leader or "NONE",
                quorum_met=quorum_met,
                voting_instances=num_votes,
                consensus_strength=circuit_strength,
            )

            self.consensus_decisions += 1
            self.last_consensus_time = datetime.utcnow()

            logger.debug(
                f"Consensus: circuit={circuit_consensus}, "
                f"fallback={fallback_consensus}, quorum={quorum_met}, "
                f"strength={circuit_strength:.2%}, votes={num_votes}"
            )

            return decision
        except Exception as e:
            logger.error(f"Failed to get cluster consensus: {e}")
            return ConsensusDecision(
                circuit_state="UNKNOWN",
                fallback_mode="SAFE",
                leader_instance="",
                quorum_met=False,
                voting_instances=0,
                consensus_strength=0.0,
            )

    def _majority_vote(self, votes: List[str]) -> str:
        """Apply majority voting to list of votes.

        Returns most common vote if it has >50% agreement.
        Otherwise returns "SPLIT_BRAIN" to indicate conflict.

        Args:
            votes: List of vote values

        Returns:
            Most common vote or "SPLIT_BRAIN"
        """
        if not votes:
            return "UNKNOWN"

        # Count votes
        counter = Counter(votes)
        most_common_vote, count = counter.most_common(1)[0]

        # Check for majority (>50%)
        majority_threshold = len(votes) / 2
        if count > majority_threshold:
            logger.debug(f"Majority vote: {most_common_vote} ({count}/{len(votes)})")
            return most_common_vote
        else:
            logger.warning(f"No majority consensus: {dict(counter)}")
            return "SPLIT_BRAIN"

    async def get_cluster_health(self) -> Dict[str, Any]:
        """Get aggregated health status of entire cluster.

        Returns:
            Dict with cluster health metrics
        """
        try:
            all_health = await self.redis.get_all_instance_health()
            if not all_health:
                return {"instances": 0, "healthy": 0, "degraded": 0, "failed": 0}

            # Categorize health
            healthy = sum(
                1 for h in all_health.values() if h.get("health_score", 0) >= 0.8
            )
            degraded = sum(
                1 for h in all_health.values() if 0.5 <= h.get("health_score", 0) < 0.8
            )
            failed = sum(
                1 for h in all_health.values() if h.get("health_score", 0) < 0.5
            )

            return {
                "instances": len(all_health),
                "healthy": healthy,
                "degraded": degraded,
                "failed": failed,
                "health_states": all_health,
            }
        except Exception as e:
            logger.error(f"Failed to get cluster health: {e}")
            return {"instances": 0, "healthy": 0, "degraded": 0, "failed": 0}

    async def get_metrics(self) -> Dict[str, Any]:
        """Get coordinator metrics.

        Returns:
            Dict with coordination metrics
        """
        return {
            "instance_id": self.instance_id,
            "is_leader": self.is_leader,
            "election_wins": self.election_wins,
            "consensus_decisions": self.consensus_decisions,
            "last_consensus_time": (
                self.last_consensus_time.isoformat()
                if self.last_consensus_time
                else None
            ),
            "running": self._running,
        }

    async def apply_consensus_decision(self, decision: ConsensusDecision) -> bool:
        """Apply consensus decision to local instance.

        Updates fallback mode based on consensus if quorum met.

        Args:
            decision: ConsensusDecision to apply

        Returns:
            True if applied, False otherwise
        """
        if not decision.quorum_met:
            logger.warning("Cannot apply decision: quorum not met")
            return False

        try:
            # Apply fallback mode change if different
            if self.fallback and decision.fallback_mode != "PRIMARY":
                logger.info(
                    f"Applying consensus fallback mode: {decision.fallback_mode}"
                )
                result = await self.fallback.set_mode(decision.fallback_mode)
                return result

            return True
        except Exception as e:
            logger.error(f"Failed to apply consensus decision: {e}")
            return False
