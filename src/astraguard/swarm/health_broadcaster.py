"""
Health Broadcaster - Periodic broadcasting of compressed HealthSummary.

Issue #401: Communication protocols - health state broadcasting
- Broadcasts HealthSummary every 30s (normal) with congestion backoff
- Compresses using Issue #399 StateCompressor
- HMAC signatures for authenticity over noisy ISL
- Congestion detection: backoff 30s→60s→120s during anomaly storms
- Integration: Registry (#400), Bus (#398), Compressor (#399)
"""

import asyncio
import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from astraguard.swarm.models import AgentID, HealthSummary, SwarmConfig
from astraguard.swarm.registry import SwarmRegistry
from astraguard.swarm.bus import SwarmMessageBus
from astraguard.swarm.compressor import StateCompressor

logger = logging.getLogger(__name__)

# Configuration
BROADCAST_INTERVAL = 30  # seconds (normal)
CONGESTION_THRESHOLD = 0.7  # 70% utilization triggers backoff
HEALTH_DELTA_THRESHOLD = 0.95  # Skip broadcast if health unchanged >95%
BROADCAST_TOPIC = "health/"


@dataclass
class BroadcastMetrics:
    """Metrics for health broadcasting."""
    
    total_broadcasts: int = 0
    successful_broadcasts: int = 0
    failed_broadcasts: int = 0
    skipped_broadcasts: int = 0
    average_latency_ms: float = 0.0
    current_interval: float = BROADCAST_INTERVAL
    current_congestion_level: float = 0.0


class HealthBroadcaster:
    """Broadcasts compressed health state to satellite constellation."""
    
    def __init__(
        self,
        config: SwarmConfig,
        agent_id: AgentID,
        registry: SwarmRegistry,
        bus: SwarmMessageBus,
        compressor: StateCompressor,
        private_key: Optional[bytes] = None
    ):
        """Initialize health broadcaster.
        
        Args:
            config: SwarmConfig with agent configuration
            agent_id: This agent's ID
            registry: SwarmRegistry for peer management
            bus: SwarmMessageBus for pub/sub
            compressor: StateCompressor for health data compression
            private_key: Optional private key for HMAC signing (default: agent_id.to_bytes())
        """
        self.config = config
        self.agent_id = agent_id
        self.registry = registry
        self.bus = bus
        self.compressor = compressor
        # Use agent_id's constellation + serial as key material
        key_material = f"{agent_id.constellation}:{agent_id.satellite_serial}".encode()
        self.private_key = private_key or key_material
        
        self._broadcast_task: Optional[asyncio.Task] = None
        self._is_running = False
        self._last_health_hash: Optional[str] = None
        self._current_interval = BROADCAST_INTERVAL
        self.metrics = BroadcastMetrics()
        
        logger.info(f"HealthBroadcaster initialized for {agent_id.constellation}")
    
    async def start(self):
        """Start the health broadcaster background task."""
        if self._is_running:
            logger.warning("HealthBroadcaster already running")
            return
        
        self._is_running = True
        self._broadcast_task = asyncio.create_task(self._broadcast_loop())
        logger.info("HealthBroadcaster started")
    
    async def stop(self):
        """Stop the health broadcaster gracefully."""
        if not self._is_running:
            return
        
        self._is_running = False
        if self._broadcast_task:
            self._broadcast_task.cancel()
            try:
                await self._broadcast_task
            except asyncio.CancelledError:
                pass
        
        logger.info(f"HealthBroadcaster stopped. Metrics: {self.metrics}")
    
    async def _broadcast_loop(self):
        """Main broadcast loop with adaptive congestion backoff."""
        while self._is_running:
            try:
                # Check congestion and adjust interval
                congestion_level = self.get_congestion_level()
                self._adjust_broadcast_interval(congestion_level)
                
                # Broadcast health
                await self._broadcast_health()
                
                # Sleep with current interval
                await asyncio.sleep(self._current_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in broadcast loop: {e}", exc_info=True)
                await asyncio.sleep(self._current_interval)
    
    async def _broadcast_health(self):
        """Broadcast current health state with compression and HMAC signature."""
        try:
            # Get current health from registry
            health = self.registry.get_peer_health(self.agent_id)
            if not health:
                health = HealthSummary(
                    anomaly_signature=[0.0] * 32,
                    risk_score=0.0,
                    recurrence_score=0.0,
                    timestamp=datetime.utcnow()
                )
            
            # Skip if health unchanged >95%
            if not self._should_broadcast(health):
                self.metrics.skipped_broadcasts += 1
                return
            
            # Compress health state
            compressed_health = self.compressor.compress(health)
            
            # Create signed payload
            payload = {
                "agent_id": self.agent_id.uuid.hex,
                "constellation": self.agent_id.constellation,
                "compressed_health": compressed_health.hex(),
                "timestamp": datetime.utcnow().isoformat(),
            }
            
            # Add HMAC signature
            payload["signature"] = self._sign_payload(payload)
            
            # Publish to bus with QoS=1 (at least once)
            start_time = datetime.utcnow()
            await self.bus.publish(
                topic=BROADCAST_TOPIC + self.agent_id.constellation,
                payload=json.dumps(payload),
                qos=1,  # AT_LEAST_ONCE
                receiver=None  # Broadcast to all
            )
            
            # Record metrics
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            self._update_metrics(True, latency_ms)
            
            # Update hash for next comparison
            self._last_health_hash = self._hash_health(health)
            
        except Exception as e:
            logger.error(f"Error broadcasting health: {e}", exc_info=True)
            self._update_metrics(False, 0.0)
    
    def _should_broadcast(self, health: HealthSummary) -> bool:
        """Check if health has changed enough to broadcast.
        
        Skips broadcast if health unchanged >95% to reduce bandwidth.
        """
        current_hash = self._hash_health(health)
        
        if self._last_health_hash is None:
            return True
        
        # Simple hash comparison: broadcast if hash changed
        # In production, could use more sophisticated delta detection
        return current_hash != self._last_health_hash
    
    def _hash_health(self, health: HealthSummary) -> str:
        """Create hash of health for change detection."""
        data = f"{health.risk_score}:{health.recurrence_score}:{','.join(str(x) for x in health.anomaly_signature[:8])}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    def _sign_payload(self, payload: dict) -> str:
        """Create HMAC signature for payload authenticity.
        
        Signature covers: agent_id, constellation, compressed_health, timestamp
        """
        # Remove signature field for signing
        sig_data = f"{payload['agent_id']}:{payload['constellation']}:{payload['compressed_health']}:{payload['timestamp']}"
        signature = hmac.new(
            self.private_key,
            sig_data.encode(),
            hashlib.sha256
        ).digest()
        return signature.hex()
    
    @staticmethod
    def verify_signature(payload: dict, public_key: bytes) -> bool:
        """Verify HMAC signature of received health broadcast.
        
        Args:
            payload: Health broadcast message
            public_key: Agent's public key (same as private for HMAC)
            
        Returns:
            True if signature is valid
        """
        stored_sig = payload.get("signature", "")
        
        sig_data = f"{payload['agent_id']}:{payload['constellation']}:{payload['compressed_health']}:{payload['timestamp']}"
        expected_sig = hmac.new(
            public_key,
            sig_data.encode(),
            hashlib.sha256
        ).digest().hex()
        
        return hmac.compare_digest(stored_sig, expected_sig)
    
    def _adjust_broadcast_interval(self, congestion_level: float):
        """Adjust broadcast interval based on congestion.
        
        Normal: 30s
        Congestion >70%: 60s (2x)
        Severe >85%: 120s (4x)
        """
        self.metrics.current_congestion_level = congestion_level
        
        if congestion_level > 0.85:
            self._current_interval = 120.0
        elif congestion_level > 0.7:
            self._current_interval = 60.0
        else:
            self._current_interval = BROADCAST_INTERVAL
        
        self.metrics.current_interval = self._current_interval
    
    def get_congestion_level(self) -> float:
        """Get current congestion level from bus utilization.
        
        Returns:
            Float 0.0-1.0 representing bandwidth utilization
        """
        # In production, would track actual bus utilization
        # For now, estimate from queue depth
        queue_depth = len(self.bus._message_queue) if hasattr(self.bus, '_message_queue') else 0
        max_queue = 100  # Arbitrary max queue depth
        
        # Simple heuristic: high queue = high congestion
        congestion = min(1.0, queue_depth / max_queue)
        return congestion
    
    def _update_metrics(self, success: bool, latency_ms: float):
        """Update broadcast metrics."""
        self.metrics.total_broadcasts += 1
        
        if success:
            self.metrics.successful_broadcasts += 1
            # Update running average latency
            avg = self.metrics.average_latency_ms
            count = self.metrics.successful_broadcasts
            self.metrics.average_latency_ms = (avg * (count - 1) + latency_ms) / count
        else:
            self.metrics.failed_broadcasts += 1
    
    def get_metrics(self) -> BroadcastMetrics:
        """Get current broadcast metrics."""
        return self.metrics
    
    def get_delivery_rate(self) -> float:
        """Get broadcast delivery success rate (0.0-1.0)."""
        if self.metrics.total_broadcasts == 0:
            return 0.0
        return self.metrics.successful_broadcasts / (self.metrics.total_broadcasts - self.metrics.skipped_broadcasts)
