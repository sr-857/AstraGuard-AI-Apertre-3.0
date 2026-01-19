"""
Leader Election Engine with Raft-Inspired Timeouts

Implements Raft-inspired leader election protocol with:
- Randomized election timeouts (150-300ms)
- AgentID lexicographic tiebreaker
- 10-second heartbeat lease for split-brain protection
- Quorum-based voting (N/2 + 1)
- State machine: FOLLOWER → CANDIDATE → LEADER

Issue #405: Coordination layer leader election
Depends on: #397 (models), #398 (bus), #400 (registry), #403 (reliable delivery)
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Optional, Set
from random import randint
import logging

from astraguard.swarm.models import AgentID, SwarmConfig
from astraguard.swarm.bus import SwarmMessageBus
from astraguard.swarm.registry import SwarmRegistry
from astraguard.swarm.types import QoSLevel

logger = logging.getLogger(__name__)


class ElectionState(Enum):
    """Raft-inspired election state machine."""
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"


@dataclass
class ElectionMetrics:
    """Election metrics for Prometheus export."""
    election_count: int = 0
    convergence_time_ms: Optional[float] = None
    current_state: str = ElectionState.FOLLOWER.value
    last_leader_id: Optional[str] = None
    lease_remaining_ms: float = 0.0

    def to_dict(self) -> Dict[str, any]:
        """Export metrics as dictionary."""
        return {
            "election_count": self.election_count,
            "convergence_time_ms": self.convergence_time_ms or 0.0,
            "current_state": self.current_state,
            "last_leader_id": self.last_leader_id or "none",
            "lease_remaining_ms": self.lease_remaining_ms,
        }


class LeaderElection:
    """
    Raft-inspired leader election with randomized timeouts.
    
    Algorithm:
    1. FOLLOWER waits for heartbeat (10s lease)
    2. On timeout, becomes CANDIDATE with random(150-300ms) election delay
    3. Candidate broadcasts RequestVote to alive peers
    4. Voters grant vote if candidate has higher AgentID or same ID with higher uptime
    5. On quorum (N/2 + 1), candidate becomes LEADER
    6. LEADER sends AppendEntries heartbeat every 1s to maintain lease
    7. Split-brain prevented via lease expiry + deterministic tiebreaker
    """

    # Configuration constants
    ELECTION_TIMEOUT_MIN_MS = 150
    ELECTION_TIMEOUT_MAX_MS = 300
    HEARTBEAT_INTERVAL_MS = 1000
    LEASE_VALIDITY_SECONDS = 10
    HEARTBEAT_TOPIC = "coord/heartbeat"
    VOTE_REQUEST_TOPIC = "coord/vote_request"
    VOTE_GRANT_TOPIC = "coord/vote_grant"

    def __init__(
        self,
        config: SwarmConfig,
        registry: SwarmRegistry,
        bus: SwarmMessageBus,
    ):
        """
        Initialize leader election engine.
        
        Args:
            config: SwarmConfig with agent_id and SWARM_MODE_ENABLED flag
            registry: SwarmRegistry for peer discovery and health tracking
            bus: SwarmMessageBus for reliable message delivery (QoS=2)
        """
        self.config = config
        self.registry = registry
        self.bus = bus

        # State machine
        self.state = ElectionState.FOLLOWER
        self.current_leader: Optional[AgentID] = None
        self.voted_for: Optional[AgentID] = None
        self.lease_expiry: datetime = datetime.now()

        # Election tracking
        self.current_term: int = 0
        self.votes_received: Set[AgentID] = set()
        self.election_start_time: Optional[datetime] = None

        # Metrics
        self.metrics = ElectionMetrics()

        # Task management
        self._election_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = False

    def is_leader(self) -> bool:
        """Check if this agent is current leader with valid lease."""
        return (
            self.state == ElectionState.LEADER
            and self.current_leader == self.config.agent_id
            and self.lease_expiry > datetime.now()
        )

    def get_leader(self) -> Optional[AgentID]:
        """Get current leader if lease is valid."""
        if self.lease_expiry > datetime.now():
            return self.current_leader
        return None

    def get_state(self) -> ElectionState:
        """Get current election state."""
        return self.state

    async def start(self) -> None:
        """Start background election and heartbeat tasks."""
        if not self.config.SWARM_MODE_ENABLED:
            logger.debug("Swarm mode disabled, skipping leader election")
            return

        self._running = True
        logger.info(f"Starting leader election engine for {self.config.agent_id.satellite_serial}")

        # Start election loop
        self._election_task = asyncio.create_task(self._election_loop())

        # Start heartbeat loop (for leader)
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        # Subscribe to vote and heartbeat messages
        self.bus.subscribe(
            self.VOTE_REQUEST_TOPIC,
            self._handle_vote_request,
            qos=QoSLevel.RELIABLE,
        )
        self.bus.subscribe(
            self.VOTE_GRANT_TOPIC,
            self._handle_vote_grant,
            qos=QoSLevel.RELIABLE,
        )
        self.bus.subscribe(
            self.HEARTBEAT_TOPIC,
            self._handle_heartbeat,
            qos=QoSLevel.RELIABLE,
        )

    async def stop(self) -> None:
        """Stop leader election tasks."""
        self._running = False
        if self._election_task:
            self._election_task.cancel()
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        logger.info("Leader election engine stopped")

    def get_metrics(self) -> ElectionMetrics:
        """Get current election metrics."""
        self.metrics.current_state = self.state.value
        if self.current_leader:
            self.metrics.last_leader_id = self.current_leader.satellite_serial
        lease_remaining = (self.lease_expiry - datetime.now()).total_seconds() * 1000
        self.metrics.lease_remaining_ms = max(0, lease_remaining)
        return self.metrics

    async def _election_loop(self) -> None:
        """Main election loop: Monitor lease expiry and trigger elections."""
        while self._running:
            try:
                if self.state == ElectionState.FOLLOWER:
                    await self._follower_loop()
                elif self.state == ElectionState.CANDIDATE:
                    await self._candidate_loop()
                else:  # LEADER
                    await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Election loop error: {e}", exc_info=True)
                await asyncio.sleep(0.1)

    async def _follower_loop(self) -> None:
        """Follower state: Wait for heartbeat or election timeout."""
        time_until_timeout = (self.lease_expiry - datetime.now()).total_seconds()
        if time_until_timeout <= 0:
            logger.info(f"{self.config.agent_id.satellite_serial} election timeout, becoming candidate")
            await self._become_candidate()
        else:
            await asyncio.sleep(min(time_until_timeout, 0.05))

    async def _candidate_loop(self) -> None:
        """Candidate state: Send vote requests and wait for quorum."""
        if not self.election_start_time:
            self.election_start_time = datetime.now()
            self.current_term += 1
            self.voted_for = self.config.agent_id
            self.votes_received = {self.config.agent_id}
            alive_peers = self.registry.get_alive_peers()
            logger.info(f"{self.config.agent_id.satellite_serial} requesting votes from {len(alive_peers)} peers")
            for peer in alive_peers:
                if peer != self.config.agent_id:
                    await self.bus.publish(
                        self.VOTE_REQUEST_TOPIC,
                        {"term": self.current_term, "candidate_id": self.config.agent_id.satellite_serial, "candidate_uptime": self._get_uptime_seconds()},
                        qos=QoSLevel.RELIABLE,
                    )
        quorum_size = self._calculate_quorum_size()
        if len(self.votes_received) >= quorum_size:
            logger.info(f"{self.config.agent_id.satellite_serial} achieved quorum ({len(self.votes_received)}/{quorum_size}), becoming leader")
            elapsed_ms = (datetime.now() - self.election_start_time).total_seconds() * 1000
            self.metrics.convergence_time_ms = elapsed_ms
            self.metrics.election_count += 1
            await self._become_leader()
            return
        if self.election_start_time:
            election_duration = (datetime.now() - self.election_start_time).total_seconds() * 1000
            if election_duration > randint(self.ELECTION_TIMEOUT_MIN_MS, self.ELECTION_TIMEOUT_MAX_MS):
                logger.warning(f"{self.config.agent_id.satellite_serial} election timeout, restarting")
                self.election_start_time = None
                self.votes_received = set()
        await asyncio.sleep(0.01)

    async def _heartbeat_loop(self) -> None:
        """Heartbeat sender: LEADER sends periodic heartbeats to maintain lease."""
        while self._running:
            try:
                if self.state == ElectionState.LEADER:
                    await self.bus.publish(self.HEARTBEAT_TOPIC, {"leader_id": self.config.agent_id.satellite_serial, "term": self.current_term, "timestamp": datetime.now().isoformat()}, qos=QoSLevel.RELIABLE)
                    logger.debug(f"{self.config.agent_id.satellite_serial} sent heartbeat (term={self.current_term})")
                await asyncio.sleep(self.HEARTBEAT_INTERVAL_MS / 1000)
            except Exception as e:
                logger.error(f"Heartbeat loop error: {e}")
                await asyncio.sleep(0.1)

    async def _become_candidate(self) -> None:
        """Transition from FOLLOWER to CANDIDATE state."""
        self.state = ElectionState.CANDIDATE
        self.election_start_time = None
        self.votes_received = set()
        self.current_term += 1
        logger.info(f"{self.config.agent_id.satellite_serial} became CANDIDATE (term={self.current_term})")

    async def _become_leader(self) -> None:
        """Transition to LEADER state and send initial heartbeat."""
        self.state = ElectionState.LEADER
        self.current_leader = self.config.agent_id
        self.lease_expiry = datetime.now() + timedelta(seconds=self.LEASE_VALIDITY_SECONDS)
        self.election_start_time = None
        logger.info(f"{self.config.agent_id.satellite_serial} became LEADER (term={self.current_term}, lease until {self.lease_expiry.isoformat()})")
        await self.bus.publish(self.HEARTBEAT_TOPIC, {"leader_id": self.config.agent_id.satellite_serial, "term": self.current_term, "timestamp": datetime.now().isoformat()}, qos=QoSLevel.RELIABLE)

    async def _handle_vote_request(self, message: dict) -> None:
        """Handle incoming vote request from candidate."""
        try:
            term = message.get("term", 0)
            candidate_id = message.get("candidate_id", "")
            candidate_uptime = message.get("candidate_uptime", 0)
            if term > self.current_term:
                self.current_term = term
                self.state = ElectionState.FOLLOWER
                self.voted_for = None
            if term < self.current_term:
                return
            if self.voted_for is None or self._should_vote_for(candidate_id, candidate_uptime):
                self.voted_for = AgentID.create("astra-v3.0", candidate_id)
                await self.bus.publish(self.VOTE_GRANT_TOPIC, {"term": self.current_term, "voter_id": self.config.agent_id.satellite_serial}, qos=QoSLevel.RELIABLE)
                logger.info(f"Granted vote to {candidate_id} (term={term})")
        except Exception as e:
            logger.error(f"Error handling vote request: {e}")

    async def _handle_vote_grant(self, message: dict) -> None:
        """Handle incoming vote grant from peer."""
        try:
            term = message.get("term", 0)
            voter_id = message.get("voter_id", "")
            if self.state != ElectionState.CANDIDATE or term != self.current_term:
                return
            voter = AgentID.create("astra-v3.0", voter_id)
            self.votes_received.add(voter)
            logger.debug(f"Received vote from {voter_id} ({len(self.votes_received)} total)")
        except Exception as e:
            logger.error(f"Error handling vote grant: {e}")

    async def _handle_heartbeat(self, message: dict) -> None:
        """Handle incoming heartbeat from leader."""
        try:
            term = message.get("term", 0)
            leader_id = message.get("leader_id", "")
            if term < self.current_term:
                return
            if term > self.current_term:
                self.current_term = term
                if self.state != ElectionState.FOLLOWER:
                    self.state = ElectionState.FOLLOWER
                    self.election_start_time = None
            self.current_leader = AgentID.create("astra-v3.0", leader_id)
            self.lease_expiry = datetime.now() + timedelta(seconds=self.LEASE_VALIDITY_SECONDS)
            if self.state == ElectionState.CANDIDATE:
                logger.info(f"{self.config.agent_id.satellite_serial} received heartbeat, becoming follower")
                self.state = ElectionState.FOLLOWER
                self.election_start_time = None
            logger.debug(f"Heartbeat from {leader_id} (term={term}, lease until {self.lease_expiry.isoformat()})")
        except Exception as e:
            logger.error(f"Error handling heartbeat: {e}")

    def _should_vote_for(self, candidate_id: str, candidate_uptime: float) -> bool:
        """Determine if we should vote for candidate based on AgentID and uptime."""
        if self.voted_for is None:
            return True
        if candidate_id > self.voted_for.satellite_serial:
            return True
        if candidate_id == self.voted_for.satellite_serial:
            return candidate_uptime > self._get_uptime_seconds()
        return False

    def _calculate_quorum_size(self) -> int:
        """Calculate quorum size as N/2 + 1."""
        alive_peers = self.registry.get_alive_peers()
        return len(alive_peers) // 2 + 1

    def _get_uptime_seconds(self) -> float:
        """Get agent uptime in seconds (placeholder)."""
        # In production, this would track actual uptime
        # For now, return current time for deterministic ordering
        return datetime.now().timestamp()
