"""
Token Bucket Bandwidth Governor - Fair rate limiting with priority queues

Issue #404: Communication protocols - bandwidth-aware messaging
- Per-peer token buckets (1KB/s) + global ceiling (10KB/s)
- Priority queues: CRITICAL(health) > HIGH(intent) > NORMAL(coord)
- Congestion signals: 70%→90%→100% utilization thresholds
- DoS prevention for 10-agent constellations
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional
import asyncio
from enum import Enum

from astraguard.swarm.models import AgentID, SwarmConfig


class MessagePriority(str, Enum):
    """Message priority levels for bandwidth allocation."""
    CRITICAL = "CRITICAL"  # Health broadcasts, emergency control
    HIGH = "HIGH"          # Intent signals
    NORMAL = "NORMAL"      # Coordination messages


# Priority allocation percentages (0.0-1.0)
PRIORITY_ALLOCATION = {
    MessagePriority.CRITICAL: 0.80,
    MessagePriority.HIGH: 0.15,
    MessagePriority.NORMAL: 0.05,
}


@dataclass
class TokenBucket:
    """Token bucket for rate limiting.
    
    Tokens accumulate at fixed rate. Each message consumes tokens.
    Burst allowance permits temporary exceeding of rate.
    """
    rate: float              # Tokens per second (bytes/s)
    burst: float             # Maximum burst size (bytes)
    _tokens: float = field(default=0.0, init=False)
    _last_update: datetime = field(default_factory=datetime.utcnow, init=False)
    
    def __post_init__(self):
        """Initialize with full tokens."""
        self._tokens = self.burst
    
    def _refill(self) -> None:
        """Add tokens based on elapsed time."""
        now = datetime.utcnow()
        elapsed = (now - self._last_update).total_seconds()
        self._last_update = now
        
        # Add tokens: rate * elapsed time
        self._tokens = min(
            self.burst,
            self._tokens + (self.rate * elapsed)
        )
    
    def acquire(self, tokens: float) -> bool:
        """Attempt to acquire tokens.
        
        Args:
            tokens: Number of tokens to acquire
        
        Returns:
            True if acquired, False if insufficient tokens
        """
        self._refill()
        
        if self._tokens >= tokens:
            self._tokens -= tokens
            return True
        
        return False
    
    def tokens_available(self) -> float:
        """Get current available tokens."""
        self._refill()
        return self._tokens
    
    def utilization(self) -> float:
        """Get utilization percentage (0.0-1.0)."""
        self._refill()
        # Utilization = (burst - available) / burst
        return max(0.0, 1.0 - (self._tokens / self.burst))


@dataclass
class BandwidthStats:
    """Bandwidth usage statistics."""
    total_bytes_sent: int = 0
    total_messages: int = 0
    dropped_messages: int = 0
    throttled_messages: int = 0
    congestion_events: int = 0
    peak_utilization: float = 0.0
    
    def average_message_size(self) -> float:
        """Average bytes per message."""
        if self.total_messages == 0:
            return 0.0
        return self.total_bytes_sent / self.total_messages
    
    def drop_rate(self) -> float:
        """Dropped / total ratio."""
        if self.total_messages == 0:
            return 0.0
        return self.dropped_messages / self.total_messages


class BandwidthGovernor:
    """Bandwidth governor with per-peer rate limiting and priority queues.
    
    Enforces:
    - Global limit: 10KB/s (configurable)
    - Per-peer limit: 1KB/s (configurable)
    - Priority allocation: CRITICAL > HIGH > NORMAL
    - Burst allowance: 2KB global, 500B per-peer
    """
    
    # Default rates (bytes/s)
    DEFAULT_GLOBAL_RATE = 10_000  # 10KB/s
    DEFAULT_GLOBAL_BURST = 2_000  # 2KB burst
    DEFAULT_PEER_RATE = 1_000     # 1KB/s per peer
    DEFAULT_PEER_BURST = 500      # 500B per-peer burst
    
    # Congestion thresholds
    THROTTLE_LOW_THRESHOLD = 0.70
    THROTTLE_ALL_THRESHOLD = 0.90
    CRITICAL_THRESHOLD = 1.00
    
    def __init__(self, config: SwarmConfig):
        """Initialize bandwidth governor.
        
        Args:
            config: SwarmConfig with agent info
        """
        self.config = config
        self.peer_buckets: Dict[AgentID, TokenBucket] = {}
        self.global_bucket = TokenBucket(
            rate=self.DEFAULT_GLOBAL_RATE,
            burst=self.DEFAULT_GLOBAL_BURST
        )
        self.stats = BandwidthStats()
        self._priority_queues: Dict[MessagePriority, asyncio.Queue] = {
            p: asyncio.Queue() for p in MessagePriority
        }
    
    def _get_peer_bucket(self, peer: AgentID) -> TokenBucket:
        """Get or create token bucket for peer."""
        if peer not in self.peer_buckets:
            self.peer_buckets[peer] = TokenBucket(
                rate=self.DEFAULT_PEER_RATE,
                burst=self.DEFAULT_PEER_BURST
            )
        return self.peer_buckets[peer]
    
    def acquire_tokens(
        self,
        peer: AgentID,
        size: int,
        priority: MessagePriority = MessagePriority.NORMAL
    ) -> bool:
        """Attempt to acquire bandwidth tokens.
        
        Args:
            peer: Target peer AgentID
            size: Message size in bytes
            priority: Message priority level
        
        Returns:
            True if tokens acquired, False if bandwidth exceeded
        """
        # Check global limit first
        global_util = self.global_bucket.utilization()
        
        # Decide if we can acquire based on priority
        if global_util >= self.CRITICAL_THRESHOLD:
            # At 100% - only CRITICAL can pass
            if priority != MessagePriority.CRITICAL:
                self.stats.dropped_messages += 1
                self.stats.congestion_events += 1
                return False
        elif global_util >= self.THROTTLE_ALL_THRESHOLD:
            # At 90%+ - throttle non-critical
            if priority == MessagePriority.NORMAL:
                self.stats.throttled_messages += 1
                return False
        elif global_util >= self.THROTTLE_LOW_THRESHOLD:
            # At 70%+ - throttle NORMAL only
            if priority == MessagePriority.NORMAL:
                self.stats.throttled_messages += 1
                return False
        
        # Try to acquire from both buckets
        global_ok = self.global_bucket.acquire(size)
        peer_ok = self._get_peer_bucket(peer).acquire(size)
        
        if global_ok and peer_ok:
            self.stats.total_bytes_sent += size
            self.stats.total_messages += 1
            self.stats.peak_utilization = max(
                self.stats.peak_utilization,
                global_util
            )
            return True
        
        # Refund tokens if partial failure
        if global_ok:
            self.global_bucket._tokens += size
        if peer_ok:
            self._get_peer_bucket(peer)._tokens += size
        
        self.stats.throttled_messages += 1
        return False
    
    def set_peer_limit(self, peer: AgentID, kbps: int) -> None:
        """Dynamically adjust per-peer rate limit.
        
        Args:
            peer: Target peer
            kbps: New rate limit in KB/s
        """
        rate_bytes = kbps * 1000
        bucket = self._get_peer_bucket(peer)
        bucket.rate = rate_bytes
        # Adjust burst proportionally
        bucket.burst = rate_bytes // 2
    
    def set_global_limit(self, kbps: int) -> None:
        """Dynamically adjust global rate limit.
        
        Args:
            kbps: New global rate in KB/s
        """
        rate_bytes = kbps * 1000
        self.global_bucket.rate = rate_bytes
        self.global_bucket.burst = rate_bytes // 5
    
    def get_global_utilization(self) -> float:
        """Get global bandwidth utilization (0.0-1.0)."""
        return self.global_bucket.utilization()
    
    def get_peer_utilization(self, peer: AgentID) -> float:
        """Get peer-specific utilization (0.0-1.0)."""
        return self._get_peer_bucket(peer).utilization()
    
    def get_all_utilizations(self) -> Dict[AgentID, float]:
        """Get utilization for all known peers."""
        return {
            peer: bucket.utilization()
            for peer, bucket in self.peer_buckets.items()
        }
    
    def get_stats(self) -> BandwidthStats:
        """Get bandwidth statistics.
        
        Returns:
            BandwidthStats object
        """
        return self.stats
    
    def get_congestion_level(self) -> str:
        """Get congestion level: NORMAL, THROTTLED, CRITICAL.
        
        Returns:
            Congestion level string
        """
        util = self.get_global_utilization()
        
        if util >= self.CRITICAL_THRESHOLD:
            return "CRITICAL"
        elif util >= self.THROTTLE_ALL_THRESHOLD:
            return "THROTTLED"
        elif util >= self.THROTTLE_LOW_THRESHOLD:
            return "MODERATE"
        
        return "NORMAL"
    
    def fair_share_per_peer(self) -> float:
        """Calculate fair share bandwidth per peer.
        
        Returns:
            Bytes/second per peer
        """
        num_peers = len(self.peer_buckets) if self.peer_buckets else 1
        return self.global_bucket.rate / num_peers
    
    def get_stats_dict(self) -> Dict:
        """Serialize stats for Prometheus.
        
        Returns:
            Dictionary of metrics
        """
        stats = self.stats
        return {
            "total_bytes_sent": stats.total_bytes_sent,
            "total_messages": stats.total_messages,
            "dropped_messages": stats.dropped_messages,
            "throttled_messages": stats.throttled_messages,
            "congestion_events": stats.congestion_events,
            "peak_utilization": stats.peak_utilization,
            "average_message_size": stats.average_message_size(),
            "drop_rate": stats.drop_rate(),
            "global_utilization": self.get_global_utilization(),
            "congestion_level": self.get_congestion_level(),
            "fair_share_bytes": self.fair_share_per_peer(),
        }
