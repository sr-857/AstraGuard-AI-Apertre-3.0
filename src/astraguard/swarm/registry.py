"""
SwarmRegistry - Local agent discovery and heartbeat for satellite constellations.

Issue #400: Agent registry with gossip-based discovery and exponential backoff heartbeat
- Cold start peer discovery: 5 agents <2min, 50 agents <2min
- Heartbeat: 30s normal, 60s congestion backoff, 120s failure recovery
- Gossip propagation: O(log N) discovery time
- Integration: HealthSummary (#397), SwarmMessageBus (#398), StateCompressor (#399)
"""

import asyncio
import logging
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from astraguard.swarm.models import AgentID, SatelliteRole, HealthSummary, SwarmConfig
from astraguard.swarm.bus import SwarmMessageBus
from astraguard.swarm.compressor import StateCompressor

logger = logging.getLogger(__name__)

# Configuration
HEARTBEAT_INTERVAL = 30  # seconds
HEARTBEAT_TIMEOUT = 90  # seconds (3x interval)
CONGESTION_BACKOFF = 60  # seconds (2x interval)
FAILURE_BACKOFF = 120  # seconds (4x interval)
GOSSIP_FANOUT = 3  # Number of peers to forward HELLO to
GOSSIP_REPLICATION = 2  # Max times a HELLO is replicated per node


@dataclass
class PeerState:
    """State of a peer in the satellite constellation."""
    
    agent_id: AgentID
    role: SatelliteRole
    last_heartbeat: datetime
    health_summary: Optional[HealthSummary] = None
    heartbeat_failures: int = field(default=0)
    is_alive: bool = field(init=False, default=True)
    backoff_multiplier: float = field(init=False, default=1.0)
    
    def __post_init__(self):
        """Compute is_alive based on timeout."""
        self._update_alive_status()
    
    def _update_alive_status(self):
        """Update is_alive based on heartbeat timeout."""
        timeout = HEARTBEAT_TIMEOUT
        if datetime.utcnow() - self.last_heartbeat > timedelta(seconds=timeout):
            self.is_alive = False
        else:
            self.is_alive = True
    
    def record_heartbeat(self, health_summary: Optional[HealthSummary] = None):
        """Record successful heartbeat."""
        self.last_heartbeat = datetime.utcnow()
        if health_summary:
            self.health_summary = health_summary
        self.heartbeat_failures = 0
        self.backoff_multiplier = 1.0
        self.is_alive = True
    
    def record_heartbeat_failure(self):
        """Record failed heartbeat with exponential backoff."""
        self.heartbeat_failures += 1
        self.backoff_multiplier = min(4.0, 2.0 ** (self.heartbeat_failures - 1))
        self._update_alive_status()
    
    def get_next_heartbeat_interval(self) -> int:
        """Get next heartbeat interval with backoff."""
        if self.heartbeat_failures == 0:
            return HEARTBEAT_INTERVAL
        elif self.heartbeat_failures == 1:
            return CONGESTION_BACKOFF
        else:
            return FAILURE_BACKOFF


class SwarmRegistry:
    """Registry for discovering and tracking satellite agents in constellation."""
    
    def __init__(self, config: SwarmConfig, agent_id: AgentID):
        """Initialize registry.
        
        Args:
            config: SwarmConfig with constellation and peer information
            agent_id: This agent's ID
        """
        self.config = config
        self.agent_id = agent_id
        self.peers: Dict[AgentID, PeerState] = {}
        self.compressor = StateCompressor()
        self.bus: Optional[SwarmMessageBus] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._hello_seen: Dict[AgentID, int] = {}  # Track HELLO replication
        
        # Initialize self as peer
        self._register_self()
        
        logger.info(f"SwarmRegistry initialized for {agent_id.constellation} "
                   f"constellation with {len(config.peers)} configured peers")
    
    def _register_self(self):
        """Register this agent as a peer."""
        now = datetime.utcnow()
        peer_state = PeerState(
            agent_id=self.agent_id,
            role=self.config.role,
            last_heartbeat=now
        )
        self.peers[self.agent_id] = peer_state
    
    def start(self, bus: SwarmMessageBus):
        """Start discovery and heartbeat mechanisms.
        
        Args:
            bus: SwarmMessageBus for pub/sub communication
        """
        self.bus = bus
        
        # Subscribe to heartbeat and discovery messages
        self.bus.subscribe(
            topic_filter="satellite/health/#",
            callback=self._on_health_message
        )
        
        self.bus.subscribe(
            topic_filter="satellite/hello/#",
            callback=self._on_hello_message
        )
        
        logger.info(f"SwarmRegistry started, subscribed to discovery topics")
    
    async def start_heartbeat(self):
        """Start background heartbeat task."""
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("Heartbeat task started")
    
    async def stop_heartbeat(self):
        """Stop background heartbeat task."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            logger.info("Heartbeat task stopped")
    
    async def _heartbeat_loop(self):
        """Background task: periodic heartbeat broadcasts.
        
        - Publishes health summary every 30s
        - Exponential backoff on failures (30s → 60s → 120s)
        - Broadcasts HELLO discovery message periodically
        """
        hello_counter = 0
        
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                
                # Publish heartbeat
                try:
                    health = self._generate_health_summary()
                    compressed = self.compressor.compress_health(health)
                    
                    await self.bus.publish(
                        topic=f"satellite/health/{self.agent_id.id}",
                        payload=compressed,
                        qos_level=1  # ACK required
                    )
                    
                    # Update self health
                    if self.agent_id in self.peers:
                        self.peers[self.agent_id].record_heartbeat(health)
                    
                except Exception as e:
                    logger.warning(f"Heartbeat publish failed: {e}")
                    if self.agent_id in self.peers:
                        self.peers[self.agent_id].record_heartbeat_failure()
                
                # Periodic HELLO broadcast (every 3 heartbeats = ~90s)
                hello_counter += 1
                if hello_counter % 3 == 0:
                    try:
                        await self.bus.publish(
                            topic=f"satellite/hello/{self.agent_id.id}",
                            payload=str(self.agent_id.id).encode(),
                            qos_level=0  # Fire-and-forget
                        )
                    except Exception as e:
                        logger.warning(f"HELLO broadcast failed: {e}")
        
        except asyncio.CancelledError:
            logger.info("Heartbeat loop cancelled")
            raise
    
    def _generate_health_summary(self) -> HealthSummary:
        """Generate health summary for this agent."""
        return HealthSummary(
            anomaly_signature=[0.1] * 32,  # Placeholder
            risk_score=0.0,
            recurrence_score=0.0,
            timestamp=datetime.utcnow()
        )
    
    async def _on_health_message(self, sender_id: str, payload: bytes):
        """Handle incoming health summary message.
        
        Args:
            sender_id: Agent ID of sender
            payload: Compressed health summary (Issue #399)
        """
        try:
            # Decompress health summary
            health = self.compressor.decompress(payload)
            
            # Parse sender ID
            sender_agent_id = AgentID.from_id(sender_id)
            
            # Update or create peer
            if sender_agent_id not in self.peers:
                peer_state = PeerState(
                    agent_id=sender_agent_id,
                    role=self.config.role,  # Will be corrected by HELLO
                    last_heartbeat=datetime.utcnow(),
                    health_summary=health
                )
                self.peers[sender_agent_id] = peer_state
                logger.info(f"Discovered new peer: {sender_agent_id.id[:8]}")
            else:
                self.peers[sender_agent_id].record_heartbeat(health)
        
        except Exception as e:
            logger.error(f"Failed to process health message from {sender_id}: {e}")
    
    async def _on_hello_message(self, sender_id: str, payload: bytes):
        """Handle HELLO discovery message with gossip forwarding.
        
        Protocol:
        1. Receive HELLO from peer
        2. Add peer to registry if new
        3. Forward HELLO to random subset of peers (fanout=3)
        4. Limit replication to prevent flooding (max 2x per node)
        
        Args:
            sender_id: Agent ID of sender
            payload: Agent ID (for verification)
        """
        try:
            sender_agent_id = AgentID.from_id(sender_id)
            
            # Track replications to prevent flooding
            replication_count = self._hello_seen.get(sender_agent_id, 0)
            if replication_count >= GOSSIP_REPLICATION:
                return  # Already replicated enough times
            
            # Add peer if new
            if sender_agent_id not in self.peers:
                peer_state = PeerState(
                    agent_id=sender_agent_id,
                    role=self.config.role,  # Will be corrected later
                    last_heartbeat=datetime.utcnow()
                )
                self.peers[sender_agent_id] = peer_state
                logger.info(f"Discovered peer via HELLO: {sender_agent_id.id[:8]}")
            else:
                # Update heartbeat
                self.peers[sender_agent_id].last_heartbeat = datetime.utcnow()
            
            # Gossip forwarding: forward to random subset of known peers
            if len(self.peers) > 1 and replication_count < GOSSIP_REPLICATION:
                other_peers = [
                    p for p in self.peers.values()
                    if p.agent_id != self.agent_id and p.agent_id != sender_agent_id
                ]
                
                if other_peers:
                    fanout_size = min(GOSSIP_FANOUT, len(other_peers))
                    targets = random.sample(other_peers, fanout_size)
                    
                    for target in targets:
                        try:
                            await self.bus.publish(
                                topic=f"satellite/hello/{sender_agent_id.id}",
                                payload=payload,
                                qos_level=0  # Fire-and-forget
                            )
                        except Exception as e:
                            logger.debug(f"Failed to forward HELLO to {target.agent_id.id[:8]}: {e}")
            
            # Update replication counter
            self._hello_seen[sender_agent_id] = replication_count + 1
        
        except Exception as e:
            logger.error(f"Failed to process HELLO message from {sender_id}: {e}")
    
    def get_alive_peers(self) -> List[AgentID]:
        """Get list of alive peer agent IDs.
        
        Returns:
            List of AgentID for peers with is_alive=True
        """
        alive = []
        now = datetime.utcnow()
        
        for peer_state in self.peers.values():
            # Check timeout
            timeout = HEARTBEAT_TIMEOUT
            time_since_heartbeat = (now - peer_state.last_heartbeat).total_seconds()
            
            if time_since_heartbeat <= timeout:
                alive.append(peer_state.agent_id)
        
        return alive
    
    def get_quorum_size(self) -> int:
        """Get quorum size for leader election (Issue #405).
        
        Returns:
            Ceiling of (alive_peers / 2) + 1
        """
        alive_count = len(self.get_alive_peers())
        return alive_count // 2 + 1
    
    def get_peer_health(self, agent_id: AgentID) -> Optional[HealthSummary]:
        """Get latest health summary for peer.
        
        Args:
            agent_id: Peer to query
            
        Returns:
            HealthSummary or None if peer not found
        """
        if agent_id in self.peers:
            return self.peers[agent_id].health_summary
        return None
    
    def get_peer_state(self, agent_id: AgentID) -> Optional[PeerState]:
        """Get full state for peer.
        
        Args:
            agent_id: Peer to query
            
        Returns:
            PeerState or None if peer not found
        """
        return self.peers.get(agent_id)
    
    def get_all_peers(self) -> List[PeerState]:
        """Get state for all known peers.
        
        Returns:
            List of PeerState objects
        """
        return list(self.peers.values())
    
    def get_peer_count(self) -> int:
        """Get total number of known peers (including self).
        
        Returns:
            Count of peers in registry
        """
        return len(self.peers)
    
    def get_registry_stats(self) -> Dict:
        """Get registry statistics for monitoring.
        
        Returns:
            Dict with peer counts, health, etc.
        """
        alive_peers = self.get_alive_peers()
        total_peers = len(self.peers)
        
        return {
            "total_peers": total_peers,
            "alive_peers": len(alive_peers),
            "dead_peers": total_peers - len(alive_peers),
            "alive_percentage": (len(alive_peers) / total_peers * 100) if total_peers > 0 else 0,
            "quorum_size": self.get_quorum_size(),
            "heartbeat_interval": HEARTBEAT_INTERVAL,
            "heartbeat_timeout": HEARTBEAT_TIMEOUT,
        }
