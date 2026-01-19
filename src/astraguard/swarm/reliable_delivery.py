"""
Reliable Delivery Layer - ACK/NACK with Adaptive Retry

Issue #403: Communication protocols - reliable message delivery
- Sequence number tracking for deduplication
- ACK/NACK protocol for confirmation
- Adaptive retry schedule: 1s→2s→4s→8s (max 3 retries)
- 99.9% delivery guarantee under 20% packet loss
- Integration with SwarmMessageBus (Issue #398)
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Set
import asyncio
import logging
from enum import IntEnum

from astraguard.swarm.types import SwarmMessage, QoSLevel, SwarmTopic
from astraguard.swarm.bus import SwarmMessageBus
from astraguard.swarm.models import AgentID

logger = logging.getLogger(__name__)


class AckStatus(IntEnum):
    """ACK/NACK status codes."""
    PENDING = 0
    ACKNOWLEDGED = 1
    NACK_CONGESTION = 2
    NACK_INVALID = 3
    TIMEOUT = 4


@dataclass
class SentMsg:
    """Metadata for sent message tracking."""
    seq: int
    topic: str
    payload: bytes
    sender_id: AgentID
    retries: int = 0
    sent_at: datetime = field(default_factory=datetime.utcnow)
    last_retry_at: Optional[datetime] = None
    acknowledged: bool = False
    ack_status: AckStatus = AckStatus.PENDING
    
    def retry_delay(self) -> float:
        """Get retry delay based on retry count (1s→2s→4s→8s)."""
        delays = {0: 1.0, 1: 2.0, 2: 4.0}
        return delays.get(self.retries, 8.0)
    
    def is_expired(self, timeout: int = 15) -> bool:
        """Check if message has exceeded total timeout (15s)."""
        return (datetime.utcnow() - self.sent_at).total_seconds() > timeout
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for logging."""
        return {
            "seq": self.seq,
            "topic": self.topic,
            "retries": self.retries,
            "acknowledged": self.acknowledged,
            "ack_status": self.ack_status.name,
            "age_seconds": (datetime.utcnow() - self.sent_at).total_seconds(),
        }


@dataclass
class DeliveryStats:
    """Statistics for reliable delivery."""
    total_published: int = 0
    successful_acks: int = 0
    nack_congestion: int = 0
    nack_invalid: int = 0
    timeouts: int = 0
    retries_performed: int = 0
    duplicates_rejected: int = 0
    
    def delivery_rate(self) -> float:
        """Successful delivery / total published."""
        if self.total_published == 0:
            return 0.0
        return self.successful_acks / self.total_published
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for Prometheus."""
        return {
            "total_published": self.total_published,
            "successful_acks": self.successful_acks,
            "nack_congestion": self.nack_congestion,
            "nack_invalid": self.nack_invalid,
            "timeouts": self.timeouts,
            "retries_performed": self.retries_performed,
            "duplicates_rejected": self.duplicates_rejected,
            "delivery_rate": self.delivery_rate(),
        }


class ReliableDelivery:
    """Reliable delivery layer with ACK/NACK and adaptive retry."""
    
    def __init__(self, bus: SwarmMessageBus, sender_id: AgentID):
        """Initialize reliable delivery.
        
        Args:
            bus: SwarmMessageBus for publishing
            sender_id: AgentID of this sender
        """
        self.bus = bus
        self.sender_id = sender_id
        self.pending: Dict[int, SentMsg] = {}  # seq → SentMsg
        self.next_seq = 0
        self.received_seqs: Set[int] = set()  # For deduplication
        self.stats = DeliveryStats()
        self._ack_events: Dict[int, asyncio.Event] = {}
        self._ack_status: Dict[int, AckStatus] = {}
    
    def _get_next_sequence(self) -> int:
        """Generate next sequence number."""
        seq = self.next_seq
        self.next_seq += 1
        return seq
    
    async def publish_reliable(
        self,
        topic: str,
        payload: bytes,
        max_retries: int = 3
    ) -> bool:
        """Publish message reliably with ACK/NACK.
        
        Args:
            topic: Message topic
            payload: Compressed payload (bytes)
            max_retries: Max retry attempts (default 3)
        
        Returns:
            True if delivered, False if timeout/failure
        """
        seq = self._get_next_sequence()
        sent_msg = SentMsg(
            seq=seq,
            topic=topic,
            payload=payload,
            sender_id=self.sender_id,
        )
        
        self.pending[seq] = sent_msg
        self.stats.total_published += 1
        
        # Create ACK event for this sequence
        self._ack_events[seq] = asyncio.Event()
        
        try:
            # Initial send + retry loop
            return await self._send_with_retry(sent_msg, max_retries)
        finally:
            # Cleanup
            if seq in self._ack_events:
                del self._ack_events[seq]
            if seq in self._ack_status:
                del self._ack_status[seq]
    
    async def _send_with_retry(
        self,
        sent_msg: SentMsg,
        max_retries: int
    ) -> bool:
        """Send message with adaptive retry schedule.
        
        Args:
            sent_msg: Message to send
            max_retries: Max retries allowed
        
        Returns:
            True on ACK, False on timeout/max retries
        """
        while sent_msg.retries <= max_retries:
            # Publish to bus
            await self.bus.publish(
                topic=sent_msg.topic,
                payload=sent_msg.payload,
                qos=QoSLevel.RELIABLE
            )
            
            sent_msg.sent_at = datetime.utcnow()
            sent_msg.last_retry_at = datetime.utcnow()
            
            logger.debug(
                f"Reliable publish: seq={sent_msg.seq}, topic={sent_msg.topic}, "
                f"retry={sent_msg.retries}"
            )
            
            # Wait for ACK with timeout
            retry_delay = sent_msg.retry_delay()
            ack_timeout = min(retry_delay, 8.0)  # Max 8s wait per attempt
            
            try:
                await asyncio.wait_for(
                    self._ack_events[sent_msg.seq].wait(),
                    timeout=ack_timeout
                )
                
                # ACK received - check status
                ack_status = self._ack_status.get(sent_msg.seq, AckStatus.PENDING)
                
                if ack_status == AckStatus.ACKNOWLEDGED:
                    sent_msg.acknowledged = True
                    self.pending.pop(sent_msg.seq, None)
                    self.stats.successful_acks += 1
                    logger.info(
                        f"Delivery confirmed: seq={sent_msg.seq}, "
                        f"topic={sent_msg.topic}, retries={sent_msg.retries}"
                    )
                    return True
                
                elif ack_status == AckStatus.NACK_CONGESTION:
                    # Congestion - retry with backoff
                    self.stats.nack_congestion += 1
                    sent_msg.retries += 1
                    self.stats.retries_performed += 1
                    
                    if sent_msg.retries <= max_retries:
                        wait_time = sent_msg.retry_delay()
                        logger.warning(
                            f"NACK congestion: seq={sent_msg.seq}, "
                            f"waiting {wait_time}s before retry {sent_msg.retries}"
                        )
                        await asyncio.sleep(wait_time)
                        # Reset event for next attempt
                        self._ack_events[sent_msg.seq] = asyncio.Event()
                        continue
                    else:
                        self.stats.timeouts += 1
                        self.pending.pop(sent_msg.seq, None)
                        return False
                
                elif ack_status == AckStatus.NACK_INVALID:
                    # Invalid message - don't retry
                    self.stats.nack_invalid += 1
                    self.pending.pop(sent_msg.seq, None)
                    logger.error(f"NACK invalid: seq={sent_msg.seq}")
                    return False
            
            except asyncio.TimeoutError:
                # No ACK received - exponential backoff
                sent_msg.retries += 1
                self.stats.retries_performed += 1
                
                if sent_msg.retries <= max_retries:
                    wait_time = sent_msg.retry_delay()
                    logger.warning(
                        f"ACK timeout: seq={sent_msg.seq}, "
                        f"waiting {wait_time}s before retry {sent_msg.retries}"
                    )
                    await asyncio.sleep(wait_time)
                    # Reset event for next attempt
                    self._ack_events[sent_msg.seq] = asyncio.Event()
                    continue
                else:
                    self.stats.timeouts += 1
                    self.pending.pop(sent_msg.seq, None)
                    logger.error(
                        f"Delivery failed (timeout): seq={sent_msg.seq}, "
                        f"retries={sent_msg.retries}"
                    )
                    return False
        
        return False
    
    def handle_ack(self, seq: int) -> None:
        """Process ACK for sequence number.
        
        Args:
            seq: Sequence number being acknowledged
        """
        if seq in self.pending:
            self._ack_status[seq] = AckStatus.ACKNOWLEDGED
            if seq in self._ack_events:
                self._ack_events[seq].set()
    
    def handle_nack(self, seq: int, reason: str = "congestion") -> None:
        """Process NACK for sequence number.
        
        Args:
            seq: Sequence number being nacked
            reason: NACK reason ("congestion" or "invalid")
        """
        if seq in self.pending:
            if reason == "congestion":
                self._ack_status[seq] = AckStatus.NACK_CONGESTION
            else:
                self._ack_status[seq] = AckStatus.NACK_INVALID
            
            if seq in self._ack_events:
                self._ack_events[seq].set()
    
    def mark_received(self, seq: int) -> bool:
        """Mark sequence as received for deduplication.
        
        Args:
            seq: Sequence number received
        
        Returns:
            True if new, False if duplicate
        """
        if seq in self.received_seqs:
            self.stats.duplicates_rejected += 1
            return False
        
        self.received_seqs.add(seq)
        # Keep window of last 1000 sequences
        if len(self.received_seqs) > 1000:
            # Remove oldest
            oldest = min(self.received_seqs)
            self.received_seqs.discard(oldest)
        
        return True
    
    def get_stats(self) -> DeliveryStats:
        """Get delivery statistics.
        
        Returns:
            DeliveryStats object
        """
        return self.stats
    
    def get_pending_count(self) -> int:
        """Get count of unacknowledged messages."""
        return len(self.pending)
    
    def cleanup_expired(self) -> int:
        """Remove expired messages from pending.
        
        Returns:
            Count of expired messages removed
        """
        expired_seqs = [
            seq for seq, msg in self.pending.items()
            if msg.is_expired()
        ]
        
        for seq in expired_seqs:
            self.pending.pop(seq, None)
            self.stats.timeouts += 1
        
        return len(expired_seqs)
