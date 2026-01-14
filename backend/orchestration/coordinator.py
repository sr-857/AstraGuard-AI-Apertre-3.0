"""
Coordinator Base Interface

Defines the protocol/interface for distributed coordinators.
Coordinators handle cluster-wide consensus, leader election, and state synchronization.
"""

import uuid
import logging
from typing import Protocol, Dict, Any, List, Optional, runtime_checkable
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ConsensusDecision:
    """Consensus decision from cluster quorum."""
    
    circuit_state: str  # e.g., "CLOSED", "OPEN", "HALF_OPEN"
    fallback_mode: str  # e.g., "PRIMARY", "HEURISTIC", "SAFE"
    leader_instance: str  # Instance ID of current leader
    quorum_met: bool  # Whether quorum threshold was met
    voting_instances: int  # Number of instances that voted
    consensus_strength: float  # Percentage agreement (0.0 - 1.0)
    
    def dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class NodeInfo:
    """Information about a cluster node."""
    
    instance_id: str
    is_leader: bool
    health_score: float
    last_heartbeat: datetime
    state: Dict[str, Any]


@runtime_checkable
class Coordinator(Protocol):
    """
    Protocol defining the interface for distributed coordinators.
    
    Coordinators manage cluster-wide state, leader election,
    and consensus decisions across distributed instances.
    """
    
    async def startup(self) -> None:
        """
        Initialize coordination and attempt leader election.
        
        Should connect to coordination backend (Redis, etcd, etc.)
        and start background tasks.
        """
        ...
    
    async def shutdown(self) -> None:
        """
        Gracefully shutdown coordination.
        
        Should stop background tasks and release resources.
        """
        ...
    
    async def elect_leader(self) -> bool:
        """
        Attempt to become cluster leader.
        
        Returns:
            True if this instance became leader, False otherwise
        """
        ...
    
    async def assign_work(self, work_item: Dict[str, Any]) -> str:
        """
        Assign work to a cluster node.
        
        Args:
            work_item: Work to be assigned
            
        Returns:
            Instance ID that accepted the work
        """
        ...
    
    async def heartbeat(self) -> None:
        """
        Send heartbeat to indicate this instance is alive.
        
        Should be called periodically to maintain cluster membership.
        """
        ...
    
    async def get_nodes(self) -> List[NodeInfo]:
        """
        Get list of all active nodes in cluster.
        
        Returns:
            List of NodeInfo for each active node
        """
        ...
    
    async def get_consensus(self) -> ConsensusDecision:
        """
        Get consensus decision from cluster quorum.
        
        Returns:
            ConsensusDecision with cluster consensus
        """
        ...


class CoordinatorBase(ABC):
    """
    Abstract base class for coordinators with common functionality.
    """
    
    def __init__(
        self,
        instance_id: Optional[str] = None,
        quorum_threshold: float = 0.5,
    ):
        """
        Initialize coordinator.
        
        Args:
            instance_id: Unique instance identifier (auto-generated if None)
            quorum_threshold: Minimum fraction for quorum (default: >50%)
        """
        self.instance_id = instance_id or f"astra-{uuid.uuid4().hex[:8]}"
        self.quorum_threshold = quorum_threshold
        self.is_leader = False
        self._running = False
        
        logger.info(f"Initialized coordinator: {self.instance_id}")
    
    @abstractmethod
    async def startup(self) -> None:
        """Initialize coordination."""
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown coordination."""
        pass
    
    @abstractmethod
    async def elect_leader(self) -> bool:
        """Attempt leader election."""
        pass
    
    @abstractmethod
    async def assign_work(self, work_item: Dict[str, Any]) -> str:
        """Assign work to a node."""
        pass
    
    @abstractmethod
    async def heartbeat(self) -> None:
        """Send heartbeat."""
        pass
    
    @abstractmethod
    async def get_nodes(self) -> List[NodeInfo]:
        """Get active nodes."""
        pass
    
    @abstractmethod
    async def get_consensus(self) -> ConsensusDecision:
        """Get cluster consensus."""
        pass
    
    def is_running(self) -> bool:
        """Check if coordinator is running."""
        return self._running


class LocalCoordinator(CoordinatorBase):
    """
    In-process coordinator for local development and testing.
    
    Provides a lightweight coordinator implementation that doesn't
    require external dependencies like Redis. Suitable for:
    - Local development
    - Unit testing
    - Single-instance deployments
    """
    
    def __init__(
        self,
        health_monitor=None,
        instance_id: Optional[str] = None,
        quorum_threshold: float = 0.5,
    ):
        """
        Initialize local coordinator.
        
        Args:
            health_monitor: Health monitor for local state
            instance_id: Unique instance identifier
            quorum_threshold: Minimum fraction for quorum
        """
        super().__init__(instance_id, quorum_threshold)
        self.health_monitor = health_monitor
        self._nodes: Dict[str, NodeInfo] = {}
        self._work_queue: List[Dict[str, Any]] = []
        
        logger.info("Initialized LocalCoordinator (single-instance mode)")
    
    async def startup(self) -> None:
        """Initialize coordination."""
        self._running = True
        # In local mode, always elect self as leader
        self.is_leader = True
        
        # Register self as only node
        self._nodes[self.instance_id] = NodeInfo(
            instance_id=self.instance_id,
            is_leader=True,
            health_score=1.0,
            last_heartbeat=datetime.utcnow(),
            state={},
        )
        
        logger.info(f"LocalCoordinator started: {self.instance_id} (leader)")
    
    async def shutdown(self) -> None:
        """Shutdown coordination."""
        self._running = False
        self._nodes.clear()
        self._work_queue.clear()
        logger.info("LocalCoordinator stopped")
    
    async def elect_leader(self) -> bool:
        """Attempt leader election (always succeeds in local mode)."""
        self.is_leader = True
        return True
    
    async def assign_work(self, work_item: Dict[str, Any]) -> str:
        """Assign work to self (only node)."""
        self._work_queue.append(work_item)
        return self.instance_id
    
    async def heartbeat(self) -> None:
        """Send heartbeat (update self)."""
        if self.instance_id in self._nodes:
            self._nodes[self.instance_id].last_heartbeat = datetime.utcnow()
            
            # Update health score if health monitor available
            if self.health_monitor:
                try:
                    state = await self.health_monitor.get_comprehensive_state()
                    system_status = state.get("system", {}).get("status", "UNKNOWN")
                    
                    # Simple health score mapping
                    health_map = {
                        "HEALTHY": 1.0,
                        "DEGRADED": 0.6,
                        "FAILED": 0.0,
                        "UNKNOWN": 0.5,
                    }
                    health_score = health_map.get(system_status, 0.5)
                    
                    self._nodes[self.instance_id].health_score = health_score
                    self._nodes[self.instance_id].state = state
                except Exception as e:
                    logger.error(f"Failed to update health in heartbeat: {e}")
    
    async def get_nodes(self) -> List[NodeInfo]:
        """Get active nodes (only self in local mode)."""
        return list(self._nodes.values())
    
    async def get_consensus(self) -> ConsensusDecision:
        """
        Get consensus decision (trivial in single-instance mode).
        
        Returns consensus based on local state since there's only one node.
        """
        if not self.health_monitor:
            return ConsensusDecision(
                circuit_state="UNKNOWN",
                fallback_mode="PRIMARY",
                leader_instance=self.instance_id,
                quorum_met=True,
                voting_instances=1,
                consensus_strength=1.0,
            )
        
        try:
            state = await self.health_monitor.get_comprehensive_state()
            
            circuit_state = state.get("circuit_breaker", {}).get("state", "UNKNOWN")
            fallback_mode = state.get("fallback", {}).get("mode", "PRIMARY")
            
            return ConsensusDecision(
                circuit_state=circuit_state,
                fallback_mode=fallback_mode,
                leader_instance=self.instance_id,
                quorum_met=True,
                voting_instances=1,
                consensus_strength=1.0,
            )
        except Exception as e:
            logger.error(f"Failed to get consensus: {e}")
            return ConsensusDecision(
                circuit_state="UNKNOWN",
                fallback_mode="SAFE",
                leader_instance=self.instance_id,
                quorum_met=True,
                voting_instances=1,
                consensus_strength=1.0,
            )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get coordinator metrics."""
        return {
            "instance_id": self.instance_id,
            "is_leader": self.is_leader,
            "running": self._running,
            "nodes": len(self._nodes),
            "pending_work": len(self._work_queue),
            "coordinator_type": "local",
        }
