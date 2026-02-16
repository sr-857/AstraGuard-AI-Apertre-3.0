"""
Redis client for distributed resilience coordination.

DEPRECATED: This module is maintained for backward compatibility.
New code should import from backend.storage.RedisAdapter instead.

Migration path:
    # Old (deprecated):
    from backend.redis_client import RedisClient
    
    # New (preferred):
    from backend.storage import RedisAdapter
"""

import warnings
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from urllib.parse import urlparse

# Import the new storage abstraction
from backend.storage import RedisAdapter, Storage, MemoryStorage

# Import timeout handling for backward compatibility
from core.timeout_handler import get_timeout_config

logger = logging.getLogger(__name__)


# Compatibility exports
__all__ = ["RedisClient", "Storage", "RedisAdapter", "MemoryStorage"]


class RedisClient:
    """
    DEPRECATED: Redis client for distributed coordination.
    
    This is a compatibility wrapper around backend.storage.RedisAdapter.
    New code should use RedisAdapter directly for better modularity.
    
    Migration guide:
        Old: RedisClient(redis_url="redis://localhost:6379")
        New: RedisAdapter(redis_url="redis://localhost:6379")
    """

    def __init__(self, redis_url: str = "redis://localhost:6379", timeout: float = None):
        """Initialize Redis client (delegates to RedisAdapter).

        Args:
            redis_url: Redis connection URL (default: localhost:6379)
                       Use rediss:// for TLS-encrypted connections
            timeout: Default timeout for operations (uses env config if None)
            use_tls: Force TLS usage (None = auto-detect from URL and config)
            ssl_context: Optional SSL context for custom TLS configuration
            service_name: Service name for TLS configuration lookup
        """
        warnings.warn(
            "RedisClient is deprecated and will be removed in a future version. "
            "Use backend.storage.RedisAdapter instead. "
            "See module docstring for migration guide.",
            DeprecationWarning,
            stacklevel=2,
        )
        
        self.redis_url = redis_url
        self.timeout = timeout or get_timeout_config().redis_timeout
        
        # Delegate to RedisAdapter
        self._adapter = RedisAdapter(
            redis_url=redis_url,
            timeout=self.timeout
        )
        
        # Expose adapter's connection state
        self.connected = False
        self.redis = None  # For backward compatibility

    async def connect(self) -> bool:
        """Establish connection to Redis with TLS support.

        Returns:
            True if successful, False otherwise
        """
        result = await self._adapter.connect()
        self.connected = self._adapter.connected
        self.redis = self._adapter.redis  # Expose for backward compatibility
        return result


    async def close(self):
        """Close Redis connection."""
        await self._adapter.close()
        self.connected = False
        self.redis = None

    async def leader_election(self, instance_id: str, ttl: int = 30) -> bool:
        """Attempt leader election with TTL-based expiry.

        Uses SET with NX (only if not exists) to ensure only one leader.
        TTL ensures automatic failover on instance failure.

        Args:
            instance_id: Unique instance identifier
            ttl: Time to live for leadership (seconds, default: 30)

        Returns:
            True if elected leader, False if leader already exists
        """
        if not self.connected:
            logger.warning("Redis not connected, cannot perform leader election")
            return False

        result = await self._adapter.set_nx(
            "astra:resilience:leader",
            instance_id,
            expire=ttl
        )
        
        if result:
            logger.info(f"Instance {instance_id} elected as leader (TTL: {ttl}s)")
        else:
            logger.debug(f"Instance {instance_id} did not win leader election")
        
        return result

    async def renew_leadership(self, instance_id: str, ttl: int = 30) -> bool:
        """Renew leadership TTL if currently leader.

        Uses atomic Lua script to prevent TOCTOU race condition.

        Args:
            instance_id: Current instance ID (must match leader)
            ttl: New TTL (seconds)

        Returns:
            True if renewed, False if not leader
        """
        if not self.connected:
            return False

        # Lua script for atomic check-and-expire operation
        lua_script = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            redis.call("EXPIRE", KEYS[1], ARGV[2])
            return 1
        else
            return 0
        end
        """

        result = await self._adapter.eval_script(
            lua_script,
            keys=["astra:resilience:leader"],
            args=[instance_id, ttl]
        )

        renewed = bool(result)
        if renewed:
            logger.debug(f"Leadership renewed for {instance_id} (TTL: {ttl}s)")
        else:
            logger.debug(f"Leadership renewal failed for {instance_id} (not current leader)")

        return renewed

    async def get_leader(self) -> Optional[str]:
        """Get current leader instance ID.

        Returns:
            Instance ID of current leader, or None if no leader
        """
        if not self.connected:
            return None

        try:
            leader = await self._adapter.get("astra:resilience:leader")
            return leader
        except Exception as e:
            logger.error(f"Failed to get leader: {e}")
            return None

    async def publish_state(self, channel: str, state: Dict[str, Any]) -> int:
        """Publish resilience state to cluster via pub/sub.

        Args:
            channel: Channel name (e.g., "astra:resilience:state")
            state: State dictionary to publish

        Returns:
            Number of subscribers that received the message
        """
        if not self.connected:
            logger.warning("Redis not connected, cannot publish state")
            return 0

        return await self._adapter.publish(channel, state)

    async def register_vote(
        self, instance_id: str, vote: Dict[str, Any], ttl: int = 30
    ) -> bool:
        """Register instance vote in cluster consensus.

        Args:
            instance_id: Instance ID voting
            vote: Vote data (e.g., circuit breaker state, fallback mode)
            ttl: Vote expiry time (seconds)

        Returns:
            True if registered, False otherwise
        """
        if not self.connected:
            return False

        try:
            key = f"astra:resilience:vote:{instance_id}"
            # Create shallow copy to avoid mutating caller's dict
            vote_copy = dict(vote)
            vote_copy["timestamp"] = datetime.utcnow().isoformat()
            
            result = await self._adapter.set(key, vote_copy, expire=ttl)
            if result:
                logger.debug(f"Registered vote from {instance_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to register vote: {e}")
            return False

    async def get_cluster_votes(
        self, prefix: str = "astra:resilience:vote"
    ) -> Dict[str, Any]:
        """Retrieve all instance votes for consensus.

        Args:
            prefix: Key prefix for votes (default: astra:resilience:vote)

        Returns:
            Dict mapping instance_id to vote data
        """
        if not self.connected:
            return {}

        try:
            # Scan for vote keys
            pattern = f"{prefix}:*"
            keys = await self._adapter.scan_keys(pattern)

            if not keys:
                logger.debug("No votes found in cluster")
                return {}

            # Batch get all values
            votes_data = await self._adapter.pipeline_get(keys)

            # Parse votes
            votes = {}
            for key, value in votes_data.items():
                if value:
                    try:
                        instance_id = key.split(":")[-1]
                        votes[instance_id] = value
                    except (IndexError, AttributeError) as e:
                        logger.warning(f"Failed to parse vote from {key}: {e}")

            logger.debug(f"Retrieved {len(votes)} votes from cluster")
            return votes
        except Exception as e:
            logger.error(f"Failed to get cluster votes: {e}")
            return {}

    async def get_instance_health(self, instance_id: str) -> Optional[Dict]:
        """Get last known health state of instance.

        Args:
            instance_id: Instance ID to query

        Returns:
            Health state dict or None if not found
        """
        if not self.connected:
            return None

        try:
            key = f"astra:health:{instance_id}"
            health = await self._adapter.get(key)
            return health
        except Exception as e:
            logger.error(f"Failed to get health for {instance_id}: {e}")
            return None

    async def publish_health(
        self, instance_id: str, health: Dict[str, Any], ttl: int = 60
    ) -> bool:
        """Publish instance health state to cluster.

        Args:
            instance_id: Instance ID publishing health
            health: Health state dictionary
            ttl: Health data TTL (seconds)

        Returns:
            True if published, False otherwise
        """
        if not self.connected:
            return False

        try:
            key = f"astra:health:{instance_id}"
            # Create shallow copy to avoid mutating caller's dict
            health_copy = dict(health)
            health_copy["timestamp"] = datetime.utcnow().isoformat()
            
            result = await self._adapter.set(key, health_copy, expire=ttl)
            if result:
                logger.debug(f"Published health for {instance_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to publish health: {e}")
            return False

    async def get_all_instance_health(self) -> Dict[str, Dict]:
        """Get health states of all instances.

        Returns:
            Dict mapping instance_id to health state
        """
        if not self.connected:
            return {}

        try:
            # Scan for health keys
            pattern = "astra:health:*"
            keys = await self._adapter.scan_keys(pattern)

            if not keys:
                return {}

            # Batch get all values
            health_data = await self._adapter.pipeline_get(keys)

            # Parse health states
            health_states = {}
            for key, value in health_data.items():
                if value:
                    try:
                        instance_id = key.split(":")[-1]
                        health_states[instance_id] = value
                    except (IndexError, AttributeError) as e:
                        logger.warning(f"Failed to parse health from {key}: {e}")

            logger.debug(f"Retrieved health for {len(health_states)} instances")
            return health_states
        except Exception as e:
            logger.error(f"Failed to get all instance health: {e}")
            return {}

    async def clear_stale_votes(self, prefix: str = "astra:resilience:vote") -> int:
        """Remove expired/stale votes (cleanup).

        Args:
            prefix: Key prefix for votes

        Returns:
            Number of votes cleared
        """
        if not self.connected:
            return 0

        try:
            # Scan for vote keys
            pattern = f"{prefix}:*"
            keys = await self._adapter.scan_keys(pattern)

            if not keys:
                return 0

            # Batch delete
            cleared = await self._adapter.pipeline_delete(keys)
            
            if cleared > 0:
                logger.debug(f"Cleared {cleared} stale votes")
            return cleared
        except Exception as e:
            logger.error(f"Failed to clear stale votes: {e}")
            return 0

    async def subscribe_to_channel(self, channel: str):
        """Subscribe to pub/sub channel.

        Args:
            channel: Channel name to subscribe to

        Returns:
            Subscription object for listening to messages
        """
        if not self.connected:
            return None

        return await self._adapter.subscribe(channel)

    async def health_check(self) -> bool:
        """Perform health check on Redis connection.

        Returns:
            True if healthy, False otherwise
        """
        if not self.connected:
            return False

        result = await self._adapter.health_check()
        self.connected = self._adapter.connected
        return result
