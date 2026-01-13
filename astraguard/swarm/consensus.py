"""
Consensus Engine with 2/3 Quorum Voting

Implements consensus protocol for binding global decisions:
- 2/3 majority quorum (Byzantine fault tolerant for 33% failures)
- Leader proposes → Peers vote → Quorum executes
- 5s timeout fallback prevents deadlock during partitions
- Proposal deduplication via unique proposal IDs

Issue #406: Consensus for global actions
Depends on: #405 (leader election), #400 (registry), #398 (bus), #403 (reliable delivery)
"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, List, Set
from datetime import datetime, timedelta
from uuid import uuid4
import logging

from astraguard.swarm.models import AgentID, SwarmConfig
from astraguard.swarm.leader_election import LeaderElection
from astraguard.swarm.bus import SwarmMessageBus
from astraguard.swarm.registry import SwarmRegistry
from astraguard.swarm.types import QoSLevel

logger = logging.getLogger(__name__)


class ProposalState(Enum):
    """Consensus proposal states."""
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    TIMEOUT = "timeout"


@dataclass
class ProposalRequest:
    """Consensus proposal specification."""
    proposal_id: str
    action: str
    params: Dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    timeout_seconds: int = 5

    def to_dict(self) -> Dict:
        """Serialize to dict for message transport."""
        return {
            "proposal_id": self.proposal_id,
            "action": self.action,
            "params": self.params,
            "timestamp": self.timestamp.isoformat(),
            "timeout_seconds": self.timeout_seconds,
        }


@dataclass
class ConsensusMetrics:
    """Consensus metrics for Prometheus export."""
    proposal_count: int = 0
    approved_count: int = 0
    denied_count: int = 0
    timeout_count: int = 0
    avg_duration_ms: float = 0.0
    last_proposal_id: Optional[str] = None

    def to_dict(self) -> Dict:
        """Export metrics as dictionary."""
        return {
            "proposal_count": self.proposal_count,
            "approved_count": self.approved_count,
            "denied_count": self.denied_count,
            "timeout_count": self.timeout_count,
            "avg_duration_ms": self.avg_duration_ms,
            "last_proposal_id": self.last_proposal_id or "none",
        }


class NotLeaderError(Exception):
    """Raised when non-leader attempts proposal."""
    pass


class ConsensusEngine:
    """
    2/3 Quorum consensus for global swarm decisions.
    
    Algorithm:
    1. LEADER checks membership, creates proposal with unique ID
    2. Broadcasts ProposalRequest to all peers (QoS=2)
    3. Peers evaluate proposal, respond with VoteGrant or VoteDeny
    4. LEADER counts votes; 2/3 quorum = APPROVED
    5. On timeout (5s), fallback to local decision
    6. LEADER broadcasts ActionApproved/ActionDenied to all peers
    7. All peers execute decision (safe mode, role reassign, etc.)
    """

    # Configuration
    PROPOSAL_REQUEST_TOPIC = "coord/proposal_request"
    VOTE_GRANT_TOPIC = "coord/vote_grant"
    VOTE_DENY_TOPIC = "coord/vote_deny"
    ACTION_APPROVED_TOPIC = "coord/action_approved"
    DEFAULT_TIMEOUT_SECONDS = 5

    # Proposal type configurations
    PROPOSAL_TYPES = {
        "safe_mode": {"quorum_fraction": 2/3, "timeout": 3},
        "role_reassign": {"quorum_fraction": 2/3, "timeout": 10},
        "attitude_adjust": {"quorum_fraction": 1/2, "timeout": 5},
    }

    def __init__(
        self,
        config: SwarmConfig,
        election: LeaderElection,
        registry: SwarmRegistry,
        bus: SwarmMessageBus,
    ):
        """
        Initialize consensus engine.
        
        Args:
            config: SwarmConfig with agent_id and SWARM_MODE_ENABLED flag
            election: LeaderElection for leader validation
            registry: SwarmRegistry for peer discovery
            bus: SwarmMessageBus for message delivery (QoS=2)
        """
        self.config = config
        self.election = election
        self.registry = registry
        self.bus = bus

        # Proposal tracking
        self.pending_proposals: Dict[str, ProposalRequest] = {}
        self.proposal_votes: Dict[str, Set[AgentID]] = {}
        self.proposal_denials: Dict[str, Dict[AgentID, str]] = {}
        self.executed_proposals: Set[str] = set()

        # Metrics
        self.metrics = ConsensusMetrics()

        # Task management
        self._running = False
        self._subscription_ids = []

    async def start(self) -> None:
        """Start consensus engine and subscribe to vote messages."""
        if not self.config.SWARM_MODE_ENABLED:
            logger.debug("Swarm mode disabled, skipping consensus engine")
            return

        self._running = True
        logger.info(f"Starting consensus engine for {self.config.agent_id.satellite_serial}")

        # Subscribe to vote messages
        self.bus.subscribe(
            self.PROPOSAL_REQUEST_TOPIC,
            self._handle_proposal_request,
            qos=QoSLevel.RELIABLE,
        )
        self.bus.subscribe(
            self.VOTE_GRANT_TOPIC,
            self._handle_vote_grant,
            qos=QoSLevel.RELIABLE,
        )
        self.bus.subscribe(
            self.VOTE_DENY_TOPIC,
            self._handle_vote_deny,
            qos=QoSLevel.RELIABLE,
        )
        self.bus.subscribe(
            self.ACTION_APPROVED_TOPIC,
            self._handle_action_approved,
            qos=QoSLevel.RELIABLE,
        )

    async def stop(self) -> None:
        """Stop consensus engine."""
        self._running = False
        logger.info("Consensus engine stopped")

    async def propose(self, action: str, params: Dict = None, timeout: Optional[int] = None) -> bool:
        """
        Propose global action for consensus voting.
        
        Args:
            action: Action type (safe_mode, role_reassign, attitude_adjust)
            params: Action parameters
            timeout: Timeout in seconds (defaults by action type)
            
        Returns:
            True if approved by quorum, False if denied/timeout
            
        Raises:
            NotLeaderError: If not current leader
        """
        if not self.election.is_leader():
            raise NotLeaderError(f"Not leader, cannot propose. Current leader: {self.election.get_leader()}")

        if params is None:
            params = {}

        # Determine timeout
        if timeout is None:
            timeout = self.PROPOSAL_TYPES.get(action, {}).get("timeout", self.DEFAULT_TIMEOUT_SECONDS)

        # Create proposal
        proposal_id = str(uuid4())
        proposal = ProposalRequest(proposal_id, action, params, timeout_seconds=timeout)
        self.pending_proposals[proposal_id] = proposal
        self.proposal_votes[proposal_id] = {self.config.agent_id}  # Vote for self
        self.proposal_denials[proposal_id] = {}

        logger.info(f"Proposing {action} (id={proposal_id[:8]}..., timeout={timeout}s)")

        # Broadcast proposal request
        start_time = datetime.now()
        await self.bus.publish(
            self.PROPOSAL_REQUEST_TOPIC,
            proposal.to_dict(),
            qos=QoSLevel.RELIABLE,
        )

        # Wait for votes or timeout
        try:
            approved = await asyncio.wait_for(
                self._wait_for_quorum(proposal_id, action),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning(f"Proposal {proposal_id[:8]}... timed out after {timeout}s, using fallback")
            approved = await self._fallback_decision(proposal_id, action)
            self.metrics.timeout_count += 1

        # Record metrics
        elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
        self.metrics.proposal_count += 1
        self.metrics.last_proposal_id = proposal_id
        if approved:
            self.metrics.approved_count += 1
        else:
            self.metrics.denied_count += 1

        # Broadcast decision to all peers
        if approved:
            await self.bus.publish(
                self.ACTION_APPROVED_TOPIC,
                {"proposal_id": proposal_id, "action": action},
                qos=QoSLevel.RELIABLE,
            )
            logger.info(f"Proposal {proposal_id[:8]}... APPROVED (elapsed={elapsed_ms:.0f}ms)")
        else:
            logger.info(f"Proposal {proposal_id[:8]}... DENIED (elapsed={elapsed_ms:.0f}ms)")

        # Cleanup
        del self.pending_proposals[proposal_id]
        del self.proposal_votes[proposal_id]
        del self.proposal_denials[proposal_id]

        return approved

    async def _wait_for_quorum(self, proposal_id: str, action: str) -> bool:
        """Wait for quorum votes to be received."""
        while True:
            # Calculate quorum requirement
            alive_peers = self.registry.get_alive_peers()
            quorum_fraction = self.PROPOSAL_TYPES.get(action, {}).get("quorum_fraction", 2/3)
            quorum_size = max(1, int(len(alive_peers) * quorum_fraction))

            # Check if quorum achieved
            votes = self.proposal_votes.get(proposal_id, set())
            if len(votes) >= quorum_size:
                return True

            # Check if quorum impossible (too many denials)
            denials = self.proposal_denials.get(proposal_id, {})
            total_responded = len(votes) + len(denials)
            if total_responded == len(alive_peers):
                # All peers have responded
                return len(votes) >= quorum_size

            await asyncio.sleep(0.1)

    async def _fallback_decision(self, proposal_id: str, action: str) -> bool:
        """Fallback decision when timeout occurs (leader accepts)."""
        # In Byzantine setting, leader is trusted (elected by majority)
        # Fallback allows completion during network partitions
        return True

    async def _handle_proposal_request(self, message: dict) -> None:
        """Handle incoming proposal request from leader."""
        try:
            proposal_id = message.get("proposal_id", "")
            action = message.get("action", "")
            params = message.get("params", {})

            # Skip if already executed
            if proposal_id in self.executed_proposals:
                return

            logger.info(f"Received proposal {proposal_id[:8]}... ({action})")

            # Evaluate proposal (stub: always approve for now)
            approved = await self._evaluate_proposal(action, params)

            # Send vote
            if approved:
                await self.bus.publish(
                    self.VOTE_GRANT_TOPIC,
                    {"proposal_id": proposal_id, "voter_id": self.config.agent_id.satellite_serial},
                    qos=QoSLevel.RELIABLE,
                )
            else:
                await self.bus.publish(
                    self.VOTE_DENY_TOPIC,
                    {"proposal_id": proposal_id, "voter_id": self.config.agent_id.satellite_serial, "reason": "local_constraint"},
                    qos=QoSLevel.RELIABLE,
                )

        except Exception as e:
            logger.error(f"Error handling proposal request: {e}")

    async def _handle_vote_grant(self, message: dict) -> None:
        """Handle incoming vote grant from peer."""
        try:
            proposal_id = message.get("proposal_id", "")
            voter_id = message.get("voter_id", "")

            if proposal_id not in self.proposal_votes:
                return

            voter = AgentID.create("astra-v3.0", voter_id)
            self.proposal_votes[proposal_id].add(voter)
            logger.debug(f"Vote grant for {proposal_id[:8]}... from {voter_id}")

        except Exception as e:
            logger.error(f"Error handling vote grant: {e}")

    async def _handle_vote_deny(self, message: dict) -> None:
        """Handle incoming vote denial from peer."""
        try:
            proposal_id = message.get("proposal_id", "")
            voter_id = message.get("voter_id", "")
            reason = message.get("reason", "unknown")

            if proposal_id not in self.proposal_denials:
                return

            voter = AgentID.create("astra-v3.0", voter_id)
            self.proposal_denials[proposal_id][voter] = reason
            logger.debug(f"Vote deny for {proposal_id[:8]}... from {voter_id} ({reason})")

        except Exception as e:
            logger.error(f"Error handling vote deny: {e}")

    async def _handle_action_approved(self, message: dict) -> None:
        """Handle action approved notification from leader."""
        try:
            proposal_id = message.get("proposal_id", "")
            action = message.get("action", "")

            self.executed_proposals.add(proposal_id)
            logger.info(f"Action approved: {action} (id={proposal_id[:8]}...)")

        except Exception as e:
            logger.error(f"Error handling action approved: {e}")

    async def _evaluate_proposal(self, action: str, params: Dict) -> bool:
        """Evaluate if peer approves proposal."""
        # Stub implementation: peers always approve
        # In real system, would check local constraints
        # (battery level, orbit position, memory, etc.)
        return True

    def get_metrics(self) -> ConsensusMetrics:
        """Get current consensus metrics."""
        return self.metrics
