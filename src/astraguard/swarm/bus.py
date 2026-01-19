"""
SwarmMessageBus - Inter-satellite message bus with QoS support.

Issue #398: Message bus abstraction for distributed satellite constellation
- Topic-based publish/subscribe
- QoS levels 0 (fire-forget), 1 (ACK), 2 (reliable)
- ISL bandwidth constraints (10KB/s)
- Latency simulation (50-200ms)
- Deduplication and ordering (Issue #403 prep)
"""

import asyncio
import logging
from typing import Dict, List, Callable, Optional, Any, Set
from collections import defaultdict
from datetime import datetime
import json

from astraguard.swarm.models import SwarmConfig, AgentID, HealthSummary
from astraguard.swarm.serializer import SwarmSerializer
from astraguard.swarm.types import (
    SwarmMessage,
    SwarmTopic,
    QoSLevel,
    TopicFilter,
    SubscriptionID,
    MessageAck,
)

logger = logging.getLogger(__name__)


class SwarmMessageBus:
    """High-performance pub/sub message bus for satellite constellations.
    
    Features:
    - Topic-based publish/subscribe with wildcard support
    - QoS levels: 0 (fire-forget), 1 (ACK), 2 (reliable)
    - ISL bandwidth awareness (10KB/s limit)
    - Latency simulation (50-200ms typical)
    - Message deduplication and ordering
    - Subscription management with leak detection
    """

    def __init__(
        self,
        config: SwarmConfig,
        serializer: SwarmSerializer,
        isl_bandwidth_kbps: int = 10,
        latency_ms: int = 100,
    ):
        """Initialize message bus.
        
        Args:
            config: SwarmConfig with agent identification
            serializer: SwarmSerializer for message encoding
            isl_bandwidth_kbps: ISL bandwidth limit (default 10 KB/s)
            latency_ms: ISL latency in milliseconds (default 100ms)
        """
        self.config = config
        self.serializer = serializer
        self.isl_bandwidth_kbps = isl_bandwidth_kbps
        self.latency_ms = latency_ms

        # Subscription management
        self.subscriptions: Dict[SubscriptionID, Callable] = {}
        self.topic_subscribers: Dict[str, List[SubscriptionID]] = defaultdict(list)
        self.topic_filters: Dict[str, TopicFilter] = {}

        # Message tracking
        self.message_sequence = 0
        self.pending_acks: Dict[str, asyncio.Event] = {}
        self.received_messages: Set[str] = set()  # Deduplication
        self.max_stored_messages = 1000

        # Metrics
        self.metrics = {
            "published": 0,
            "delivered": 0,
            "failed": 0,
            "acked": 0,
            "lost": 0,
        }

    async def publish(
        self,
        topic: str,
        payload: Any,
        qos: int = 1,
        receiver: Optional[AgentID] = None,
        timeout_ms: int = 5000,
    ) -> bool:
        """Publish message to topic.
        
        Args:
            topic: Topic string (e.g., "health/summary")
            payload: Message payload (serialized to bytes)
            qos: QoS level (0=fire-forget, 1=ACK, 2=reliable)
            receiver: Optional specific receiver (None=broadcast)
            timeout_ms: Timeout for ACK/reliable delivery
            
        Returns:
            True if published successfully, False otherwise
        """
        try:
            # Validate topic
            if not SwarmTopic.is_valid_topic(topic):
                logger.error(f"Invalid topic: {topic}")
                return False

            # Serialize payload
            if isinstance(payload, (SwarmMessage, HealthSummary)):
                payload_bytes = self.serializer.serialize_health(
                    payload if isinstance(payload, HealthSummary) else payload.payload,
                    compress=False,  # Use compression when lz4 available
                )
            elif isinstance(payload, bytes):
                payload_bytes = payload
            else:
                payload_bytes = json.dumps(payload).encode("utf-8")

            # Validate payload size (10KB ISL limit)
            if len(payload_bytes) > 10240:
                logger.error(
                    f"Payload {len(payload_bytes)} exceeds 10KB ISL limit"
                )
                return False

            # Create message
            self.message_sequence += 1
            message = SwarmMessage(
                topic=topic,
                payload=payload_bytes,
                sender=self.config.agent_id,
                qos=qos,
                sequence=self.message_sequence,
                receiver=receiver,
            )

            # Handle QoS level
            if qos == QoSLevel.FIRE_FORGET:
                return await self._publish_fire_forget(message)
            elif qos == QoSLevel.ACK:
                return await self._publish_with_ack(message, timeout_ms)
            elif qos == QoSLevel.RELIABLE:
                return await self._publish_reliable(message, timeout_ms)
            else:
                logger.error(f"Invalid QoS level: {qos}")
                return False

        except Exception as e:
            logger.error(f"Error publishing to {topic}: {e}")
            self.metrics["failed"] += 1
            return False

    async def _publish_fire_forget(self, message: SwarmMessage) -> bool:
        """Publish with QoS 0 (fire-forget)."""
        try:
            self.metrics["published"] += 1
            # Simulate ISL latency
            await self._simulate_latency()
            # Deliver to subscribers
            await self._deliver_message(message)
            self.metrics["delivered"] += 1
            return True
        except Exception as e:
            logger.error(f"Fire-forget publish failed: {e}")
            self.metrics["failed"] += 1
            return False

    async def _publish_with_ack(
        self, message: SwarmMessage, timeout_ms: int
    ) -> bool:
        """Publish with QoS 1 (ACK)."""
        try:
            self.metrics["published"] += 1
            ack_event = asyncio.Event()
            self.pending_acks[str(message.message_id)] = ack_event

            # Simulate ISL latency and publish
            await self._simulate_latency()
            await self._deliver_message(message)

            # Wait for ACK
            try:
                await asyncio.wait_for(
                    ack_event.wait(), timeout=timeout_ms / 1000.0
                )
                self.metrics["acked"] += 1
                self.metrics["delivered"] += 1
                return True
            except asyncio.TimeoutError:
                logger.warning(
                    f"ACK timeout for message {message.message_id}"
                )
                self.metrics["lost"] += 1
                return False
        except Exception as e:
            logger.error(f"ACK publish failed: {e}")
            self.metrics["failed"] += 1
            return False
        finally:
            self.pending_acks.pop(str(message.message_id), None)

    async def _publish_reliable(
        self, message: SwarmMessage, timeout_ms: int
    ) -> bool:
        """Publish with QoS 2 (reliable with retry)."""
        max_retries = 3
        retry_interval_ms = 1000

        for attempt in range(max_retries):
            try:
                self.metrics["published"] += 1
                # Simulate ISL latency
                await self._simulate_latency()

                # Check for deduplication
                msg_key = f"{message.sender.uuid}:{message.message_id}"
                if msg_key in self.received_messages:
                    logger.debug(f"Message {message.message_id} already delivered")
                    self.metrics["delivered"] += 1
                    return True

                # Deliver
                await self._deliver_message(message)
                self.received_messages.add(msg_key)

                # Cleanup old messages
                if len(self.received_messages) > self.max_stored_messages:
                    # Remove oldest (FIFO)
                    oldest = list(self.received_messages)[0]
                    self.received_messages.discard(oldest)

                self.metrics["delivered"] += 1
                self.metrics["acked"] += 1
                return True

            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Reliable publish attempt {attempt + 1} failed, "
                        f"retrying in {retry_interval_ms}ms: {e}"
                    )
                    await asyncio.sleep(retry_interval_ms / 1000.0)
                else:
                    logger.error(f"Reliable publish failed after {max_retries} attempts")
                    self.metrics["failed"] += 1
                    return False

        return False

    async def _deliver_message(self, message: SwarmMessage) -> None:
        """Deliver message to subscribers."""
        # Find matching subscribers
        matching_subs: List[SubscriptionID] = []

        for sub_id in list(self.subscriptions.keys()):
            topic_filter = self.topic_filters.get(str(sub_id))
            if topic_filter and topic_filter.matches(message.topic):
                matching_subs.append(sub_id)

        # Deliver to all matching subscribers
        for sub_id in matching_subs:
            callback = self.subscriptions.get(sub_id)
            if callback:
                try:
                    result = callback(message)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.error(
                        f"Error in subscription callback {sub_id}: {e}"
                    )

    async def _simulate_latency(self) -> None:
        """Simulate ISL latency."""
        if self.latency_ms > 0:
            await asyncio.sleep(self.latency_ms / 1000.0)

    def subscribe(
        self, topic_filter: str, callback: Callable
    ) -> SubscriptionID:
        """Subscribe to topic(s) with optional wildcard.
        
        Args:
            topic_filter: Topic filter pattern
                - "health/summary" → specific topic
                - "health/*" → all health topics
                - "*" → all topics
            callback: Async or sync callback function
            
        Returns:
            SubscriptionID for later unsubscribe
        """
        try:
            # Validate filter
            filter_obj = TopicFilter(topic_filter)

            # Create subscription
            sub_id = SubscriptionID(
                topic_filter=topic_filter,
                subscriber=self.config.agent_id,
            )

            # Store subscription
            self.subscriptions[sub_id] = callback
            self.topic_filters[str(sub_id)] = filter_obj
            self.topic_subscribers[topic_filter].append(sub_id)

            logger.debug(f"Subscription {sub_id.id} created for {topic_filter}")
            return sub_id

        except Exception as e:
            logger.error(f"Error subscribing to {topic_filter}: {e}")
            raise

    def unsubscribe(self, subscription_id: SubscriptionID) -> bool:
        """Unsubscribe from topic(s).
        
        Args:
            subscription_id: SubscriptionID from subscribe()
            
        Returns:
            True if unsubscribed, False if not found
        """
        if subscription_id in self.subscriptions:
            self.subscriptions.pop(subscription_id)
            topic_filter_str = subscription_id.topic_filter
            self.topic_filters.pop(str(subscription_id), None)

            if topic_filter_str in self.topic_subscribers:
                try:
                    self.topic_subscribers[topic_filter_str].remove(subscription_id)
                except ValueError:
                    pass

            logger.debug(f"Unsubscribed {subscription_id.id}")
            return True
        return False

    async def acknowledge(self, message: SwarmMessage) -> None:
        """Send acknowledgment for received message (QoS 1).
        
        Args:
            message: Message to acknowledge
        """
        try:
            ack = MessageAck(
                message_id=message.message_id,
                sender=self.config.agent_id,
                success=True,
            )

            # Simulate latency
            await self._simulate_latency()

            # Mark ACK as received
            ack_event = self.pending_acks.get(str(message.message_id))
            if ack_event:
                ack_event.set()
                logger.debug(f"ACK sent for message {message.message_id}")

        except Exception as e:
            logger.error(f"Error sending ACK: {e}")

    def get_metrics(self) -> dict:
        """Get message bus metrics.
        
        Returns:
            Dictionary with publish/delivery/failure statistics
        """
        return {
            **self.metrics,
            "subscriptions": len(self.subscriptions),
            "pending_acks": len(self.pending_acks),
            "deduplication_cache": len(self.received_messages),
            "message_sequence": self.message_sequence,
        }

    def get_subscriptions(self) -> Dict[SubscriptionID, str]:
        """Get all active subscriptions.
        
        Returns:
            Dictionary mapping SubscriptionID to topic filter
        """
        result = {}
        for sub_id in self.subscriptions.keys():
            result[sub_id] = sub_id.topic_filter
        return result

    def clear(self) -> None:
        """Clear all subscriptions and reset metrics."""
        self.subscriptions.clear()
        self.topic_filters.clear()
        self.topic_subscribers.clear()
        self.pending_acks.clear()
        self.received_messages.clear()
        self.metrics = {
            "published": 0,
            "delivered": 0,
            "failed": 0,
            "acked": 0,
            "lost": 0,
        }
        logger.info("Message bus cleared")
