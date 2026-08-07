"""
Key Management for AstraGuard Security Module.

Provides key hierarchy management, metadata tracking, and key lifecycle
operations including creation, rotation, and revocation.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class KeyType(Enum):
    """Types of cryptographic keys managed by the system."""
    DATA_ENCRYPTION = "data_encryption"
    KEY_ENCRYPTION = "key_encryption"
    SIGNING = "signing"
    MASTER = "master"
    DERIVED = "derived"


class KeyStatus(Enum):
    """Lifecycle status of a managed key."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    COMPROMISED = "compromised"
    DESTROYED = "destroyed"
    PENDING_ROTATION = "pending_rotation"


@dataclass
class KeyMetadata:
    """Metadata associated with a managed cryptographic key."""
    key_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    key_type: KeyType = KeyType.DATA_ENCRYPTION
    status: KeyStatus = KeyStatus.ACTIVE
    algorithm: str = "AES-256-GCM"
    created_at: datetime = field(default_factory=datetime.utcnow)
    rotated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    tags: Dict[str, str] = field(default_factory=dict)

    def is_active(self) -> bool:
        return self.status == KeyStatus.ACTIVE

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at


@dataclass
class ManagedKey:
    """A cryptographic key together with its lifecycle metadata."""
    metadata: KeyMetadata = field(default_factory=KeyMetadata)
    key_material: bytes = b""
    encrypted_key_material: Optional[str] = None

    @property
    def key_id(self) -> str:
        return self.metadata.key_id

    @property
    def is_active(self) -> bool:
        return self.metadata.is_active()


class KeyHierarchy:
    """
    Manages a hierarchy of cryptographic keys.

    Organises keys in a master → key-encryption-key → data-encryption-key
    structure, supporting envelope encryption patterns.
    """

    def __init__(self) -> None:
        self._keys: Dict[str, ManagedKey] = {}
        logger.info("KeyHierarchy initialised")

    # ------------------------------------------------------------------
    # Key registration
    # ------------------------------------------------------------------

    def register_key(self, managed_key: ManagedKey) -> None:
        """Register an existing ManagedKey into the hierarchy."""
        self._keys[managed_key.key_id] = managed_key
        logger.debug("Registered key %s (%s)", managed_key.key_id, managed_key.metadata.key_type)

    def create_key(
        self,
        key_type: KeyType = KeyType.DATA_ENCRYPTION,
        algorithm: str = "AES-256-GCM",
        tags: Optional[Dict[str, str]] = None,
    ) -> ManagedKey:
        """Create and register a new ManagedKey."""
        import os
        metadata = KeyMetadata(
            key_type=key_type,
            algorithm=algorithm,
            tags=tags or {},
        )
        key = ManagedKey(metadata=metadata, key_material=os.urandom(32))
        self.register_key(key)
        logger.info("Created key %s of type %s", key.key_id, key_type)
        return key

    # ------------------------------------------------------------------
    # Key retrieval
    # ------------------------------------------------------------------

    def get_key(self, key_id: str) -> Optional[ManagedKey]:
        """Return a ManagedKey by its ID, or None if not found."""
        return self._keys.get(key_id)

    def list_keys(self, key_type: Optional[KeyType] = None, status: Optional[KeyStatus] = None) -> List[ManagedKey]:
        """Return all keys, optionally filtered by type and/or status."""
        keys = list(self._keys.values())
        if key_type is not None:
            keys = [k for k in keys if k.metadata.key_type == key_type]
        if status is not None:
            keys = [k for k in keys if k.metadata.status == status]
        return keys

    # ------------------------------------------------------------------
    # Key lifecycle
    # ------------------------------------------------------------------

    def rotate_key(self, key_id: str) -> Optional[ManagedKey]:
        """Mark a key as pending rotation and create its successor."""
        old_key = self._keys.get(key_id)
        if old_key is None:
            logger.warning("rotate_key: key %s not found", key_id)
            return None
        old_key.metadata.status = KeyStatus.PENDING_ROTATION
        old_key.metadata.rotated_at = datetime.utcnow()
        new_key = self.create_key(
            key_type=old_key.metadata.key_type,
            algorithm=old_key.metadata.algorithm,
            tags={**old_key.metadata.tags, "rotated_from": key_id},
        )
        logger.info("Rotated key %s → %s", key_id, new_key.key_id)
        return new_key

    def revoke_key(self, key_id: str) -> bool:
        """Mark a key as compromised/destroyed."""
        key = self._keys.get(key_id)
        if key is None:
            return False
        key.metadata.status = KeyStatus.COMPROMISED
        logger.warning("Revoked key %s", key_id)
        return True

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------

    def get_active_dek(self) -> Optional[ManagedKey]:
        """Return the first active Data Encryption Key, if any."""
        deks = self.list_keys(key_type=KeyType.DATA_ENCRYPTION, status=KeyStatus.ACTIVE)
        return deks[0] if deks else None

    def stats(self) -> Dict[str, Any]:
        """Return a summary of the current key inventory."""
        return {
            "total": len(self._keys),
            "active": sum(1 for k in self._keys.values() if k.metadata.status == KeyStatus.ACTIVE),
            "by_type": {
                kt.value: sum(1 for k in self._keys.values() if k.metadata.key_type == kt)
                for kt in KeyType
            },
        }


# ---------------------------------------------------------------------------
# Module-level singleton helpers
# ---------------------------------------------------------------------------

_key_hierarchy: Optional[KeyHierarchy] = None


def init_key_hierarchy(**kwargs: Any) -> KeyHierarchy:
    """Initialise (or re-initialise) the module-level KeyHierarchy singleton."""
    global _key_hierarchy
    _key_hierarchy = KeyHierarchy()
    logger.info("KeyHierarchy singleton initialised")
    return _key_hierarchy


def get_key_hierarchy() -> Optional[KeyHierarchy]:
    """Return the module-level KeyHierarchy singleton (or None if not initialised)."""
    return _key_hierarchy
