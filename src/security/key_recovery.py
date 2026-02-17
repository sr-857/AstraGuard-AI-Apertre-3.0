"""
Key Recovery System with Shamir's Secret Sharing

Provides:
- Shamir's Secret Sharing for key recovery
- Threshold-based key reconstruction
- Secure share distribution
- Recovery ceremony management
- Backup and restore capabilities
"""

import os
import json
import base64
import secrets
import logging
import hashlib
from typing import List, Dict, Tuple, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from enum import Enum, auto

# Try to import PyCryptodome for SSSS
try:
    from Crypto.Protocol.SecretSharing import Shamir
    from Crypto.Util.number import long_to_bytes, bytes_to_long
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    Shamir = None
    long_to_bytes = None
    bytes_to_long = None

logger = logging.getLogger(__name__)


class RecoveryStatus(Enum):
    """Status of a recovery operation."""
    PENDING = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    FAILED = auto()
    EXPIRED = auto()


@dataclass
class KeyShare:
    """A single share of a split key."""
    share_id: int
    total_shares: int
    threshold: int
    share_data: bytes
    key_fingerprint: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    used_at: Optional[datetime] = None
    used_by: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "share_id": self.share_id,
            "total_shares": self.total_shares,
            "threshold": self.threshold,
            "share_data": base64.b64encode(self.share_data).decode(),
            "key_fingerprint": self.key_fingerprint,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "used_at": self.used_at.isoformat() if self.used_at else None,
            "used_by": self.used_by,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KeyShare":
        return cls(
            share_id=data["share_id"],
            total_shares=data["total_shares"],
            threshold=data["threshold"],
            share_data=base64.b64decode(data["share_data"]),
            key_fingerprint=data["key_fingerprint"],
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            used_at=datetime.fromisoformat(data["used_at"]) if data.get("used_at") else None,
            used_by=data.get("used_by"),
        )
    
    def is_expired(self) -> bool:
        """Check if share has expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at


@dataclass
class RecoveryCeremony:
    """A key recovery ceremony in progress."""
    ceremony_id: str
    key_fingerprint: str
    threshold: int
    total_shares: int
    shares_collected: List[KeyShare] = field(default_factory=list)
    participants: Set[str] = field(default_factory=set)
    status: RecoveryStatus = RecoveryStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    recovered_key: Optional[bytes] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ceremony_id": self.ceremony_id,
            "key_fingerprint": self.key_fingerprint,
            "threshold": self.threshold,
            "total_shares": self.total_shares,
            "shares_collected": [s.to_dict() for s in self.shares_collected],
            "participants": list(self.participants),
            "status": self.status.name,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "recovered_key": base64.b64encode(self.recovered_key).decode() if self.recovered_key else None,
        }


class ShamirSecretSharing:
    """
    Shamir's Secret Sharing implementation.
    
    Splits a secret into n shares where any t shares can reconstruct.
    """
    
    def __init__(self):
        if not HAS_CRYPTO:
            logger.warning("PyCryptodome not available, using fallback implementation")
    
    def split_secret(
        self,
        secret: bytes,
        threshold: int,
        total_shares: int,
    ) -> List[Tuple[int, bytes]]:
        """
        Split a secret into shares.
        
        Args:
            secret: Secret to split
            threshold: Minimum shares needed to reconstruct
            total_shares: Total number of shares to create
        
        Returns:
            List of (share_id, share_data) tuples
        
        Raises:
            ValueError: If threshold > total_shares or invalid parameters
        """
        if threshold > total_shares:
            raise ValueError("Threshold cannot be greater than total shares")
        if threshold < 2:
            raise ValueError("Threshold must be at least 2")
        if total_shares < 2:
            raise ValueError("Total shares must be at least 2")
        
        if HAS_CRYPTO and Shamir:
            # Use PyCryptodome implementation
            shares = Shamir.split(threshold, total_shares, secret)
            return [(i + 1, share) for i, share in enumerate(shares)]
        else:
            # Fallback implementation (simplified, for testing only)
            return self._fallback_split(secret, threshold, total_shares)
    
    def _fallback_split(
        self,
        secret: bytes,
        threshold: int,
        total_shares: int,
    ) -> List[Tuple[int, bytes]]:
        """
        Simplified fallback implementation for testing.
        NOT CRYPTOGRAPHICALLY SECURE - for development only.
        """
        logger.warning("Using fallback SSS implementation - NOT SECURE FOR PRODUCTION")
        
        # Generate random coefficients for polynomial
        coeffs = [bytes_to_long(secret)] + [
            bytes_to_long(secrets.token_bytes(32)) for _ in range(threshold - 1)
        ]
        
        shares = []
        for x in range(1, total_shares + 1):
            # Evaluate polynomial at point x
            y = coeffs[0]
            for i, coeff in enumerate(coeffs[1:], 1):
                y = (y + coeff * pow(x, i, 2**256)) % (2**256)
            
            share_data = long_to_bytes(y, 32)
            shares.append((x, share_data))
        
        return shares
    
    def reconstruct_secret(
        self,
        shares: List[Tuple[int, bytes]],
    ) -> bytes:
        """
        Reconstruct secret from shares.
        
        Args:
            shares: List of (share_id, share_data) tuples
        
        Returns:
            Reconstructed secret
        
        Raises:
            ValueError: If insufficient shares or reconstruction fails
        """
        if not shares:
            raise ValueError("No shares provided")
        
        if HAS_CRYPTO and Shamir:
            # Use PyCryptodome implementation
            return Shamir.combine(shares)
        else:
            # Fallback implementation
            return self._fallback_reconstruct(shares)
    
    def _fallback_reconstruct(
        self,
        shares: List[Tuple[int, bytes]],
    ) -> bytes:
        """
        Lagrange interpolation for secret reconstruction.
        Simplified for testing - NOT PRODUCTION SECURE.
        """
        if len(shares) < 2:
            raise ValueError("At least 2 shares required")
        
        # Lagrange interpolation at x=0
        secret = 0
        for i, (xi, yi_bytes) in enumerate(shares):
            yi = bytes_to_long(yi_bytes)
            
            # Compute Lagrange basis polynomial at x=0
            li = 1
            for j, (xj, _) in enumerate(shares):
                if i != j:
                    li = li * (-xj) * pow(xi - xj, -1, 2**256) % (2**256)
            
            secret = (secret + yi * li) % (2**256)
        
        return long_to_bytes(secret, 32)


class KeyRecoveryManager:
    """
    Manages key recovery using Shamir's Secret Sharing.
    
    Provides:
    - Secure key splitting and distribution
    - Recovery ceremony management
    - Share validation and verification
    - Audit logging of all recovery operations
    """
    
    def __init__(
        self,
        storage_path: Optional[str] = None,
        default_threshold: int = 3,
        default_total_shares: int = 5,
    ):
        """
        Initialize key recovery manager.
        
        Args:
            storage_path: Path for recovery data storage
            default_threshold: Default threshold for new splits
            default_total_shares: Default total shares for new splits
        """
        self.storage_path = Path(storage_path) if storage_path else Path(".key_recovery")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.default_threshold = default_threshold
        self.default_total_shares = default_total_shares
        
        self._sss = ShamirSecretSharing()
        self._active_ceremonies: Dict[str, RecoveryCeremony] = {}
        self._distributed_shares: Dict[str, List[KeyShare]] = {}
        
        self._load_data()
        
        logger.info(f"KeyRecoveryManager initialized (threshold={default_threshold}, "
                   f"shares={default_total_shares})")
    
    def _load_data(self) -> None:
        """Load recovery data from storage."""
        ceremonies_file = self.storage_path / "ceremonies.json"
        if ceremonies_file.exists():
            try:
                with open(ceremonies_file, "r") as f:
                    data = json.load(f)
                    for ceremony_data in data:
                        ceremony = RecoveryCeremony(
                            ceremony_id=ceremony_data["ceremony_id"],
                            key_fingerprint=ceremony_data["key_fingerprint"],
                            threshold=ceremony_data["threshold"],
                            total_shares=ceremony_data["total_shares"],
                            shares_collected=[KeyShare.from_dict(s) for s in ceremony_data.get("shares_collected", [])],
                            participants=set(ceremony_data.get("participants", [])),
                            status=RecoveryStatus[ceremony_data["status"]],
                            created_at=datetime.fromisoformat(ceremony_data["created_at"]),
                            completed_at=datetime.fromisoformat(ceremony_data["completed_at"]) if ceremony_data.get("completed_at") else None,
                            recovered_key=base64.b64decode(ceremony_data["recovered_key"]) if ceremony_data.get("recovered_key") else None,
                        )
                        if ceremony.status in (RecoveryStatus.PENDING, RecoveryStatus.IN_PROGRESS):
                            self._active_ceremonies[ceremony.ceremony_id] = ceremony
            except Exception as e:
                logger.error(f"Failed to load ceremonies: {e}")
        
        shares_file = self.storage_path / "shares.json"
        if shares_file.exists():
            try:
                with open(shares_file, "r") as f:
                    data = json.load(f)
                    for key_fp, shares_data in data.items():
                        self._distributed_shares[key_fp] = [
                            KeyShare.from_dict(s) for s in shares_data
                        ]
            except Exception as e:
                logger.error(f"Failed to load shares: {e}")
    
    def _save_data(self) -> None:
        """Save recovery data to storage."""
        ceremonies_file = self.storage_path / "ceremonies.json"
        try:
            data = [c.to_dict() for c in self._active_ceremonies.values()]
            with open(ceremonies_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save ceremonies: {e}")
        
        shares_file = self.storage_path / "shares.json"
        try:
            data = {
                key_fp: [s.to_dict() for s in shares]
                for key_fp, shares in self._distributed_shares.items()
            }
            with open(shares_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save shares: {e}")
    
    def _compute_fingerprint(self, key_material: bytes) -> str:
        """Compute fingerprint of key material."""
        return hashlib.sha256(key_material).hexdigest()[:16]
    
    def split_key(
        self,
        key_material: bytes,
        key_id: str,
        threshold: Optional[int] = None,
        total_shares: Optional[int] = None,
        share_lifetime_days: int = 365,
    ) -> List[KeyShare]:
        """
        Split a key into shares using Shamir's Secret Sharing.
        
        Args:
            key_material: Key to split
            key_id: Identifier for the key
            threshold: Minimum shares needed (default: from config)
            total_shares: Total shares to create (default: from config)
            share_lifetime_days: How long shares are valid
        
        Returns:
            List of key shares
        
        Raises:
            ValueError: If splitting fails
        """
        threshold = threshold or self.default_threshold
        total_shares = total_shares or self.default_total_shares
        
        fingerprint = self._compute_fingerprint(key_material)
        
        # Split the key
        shares_data = self._sss.split_secret(key_material, threshold, total_shares)
        
        # Create share objects
        shares = []
        expires_at = datetime.now() + timedelta(days=share_lifetime_days)
        
        for share_id, share_data in shares_data:
            share = KeyShare(
                share_id=share_id,
                total_shares=total_shares,
                threshold=threshold,
                share_data=share_data,
                key_fingerprint=fingerprint,
                created_at=datetime.now(),
                expires_at=expires_at,
            )
            shares.append(share)
        
        # Store for tracking
        self._distributed_shares[fingerprint] = shares
        self._save_data()
        
        logger.info(f"Split key {key_id} into {total_shares} shares "
                   f"(threshold={threshold}, fingerprint={fingerprint})")
        
        return shares
    
    def distribute_shares(
        self,
        shares: List[KeyShare],
        recipients: List[str],
    ) -> Dict[str, KeyShare]:
        """
        Distribute shares to recipients.
        
        Args:
            shares: Shares to distribute
            recipients: List of recipient identifiers
        
        Returns:
            Mapping of recipient -> share
        
        Raises:
            ValueError: If recipient count doesn't match share count
        """
        if len(recipients) != len(shares):
            raise ValueError(f"Recipient count ({len(recipients)}) must match share count ({len(shares)})")
        
        distribution = {}
        for recipient, share in zip(recipients, shares):
            distribution[recipient] = share
            logger.info(f"Distributed share {share.share_id} to {recipient}")
        
        return distribution
    
    def initiate_recovery(
        self,
        key_fingerprint: str,
        requested_by: str,
    ) -> RecoveryCeremony:
        """
        Initiate a key recovery ceremony.
        
        Args:
            key_fingerprint: Fingerprint of key to recover
            requested_by: Who requested the recovery
        
        Returns:
            Recovery ceremony object
        
        Raises:
            ValueError: If no shares available for this key
        """
        if key_fingerprint not in self._distributed_shares:
            raise ValueError(f"No shares found for key fingerprint: {key_fingerprint}")
        
        shares = self._distributed_shares[key_fingerprint]
        if not shares:
            raise ValueError(f"No valid shares for key: {key_fingerprint}")
        
        # Use parameters from first share
        first_share = shares[0]
        
        ceremony = RecoveryCeremony(
            ceremony_id=f"rec-{datetime.now().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(4)}",
            key_fingerprint=key_fingerprint,
            threshold=first_share.threshold,
            total_shares=first_share.total_shares,
            participants={requested_by},
            status=RecoveryStatus.IN_PROGRESS,
        )
        
        self._active_ceremonies[ceremony.ceremony_id] = ceremony
        self._save_data()
        
        logger.warning(f"Initiated key recovery ceremony: {ceremony.ceremony_id} "
                      f"for key {key_fingerprint} by {requested_by}")
        
        return ceremony
    
    def submit_share(
        self,
        ceremony_id: str,
        share: KeyShare,
        submitted_by: str,
    ) -> Optional[bytes]:
        """
        Submit a share to a recovery ceremony.
        
        Args:
            ceremony_id: Ceremony to submit to
            share: Share to submit
            submitted_by: Who is submitting
        
        Returns:
            Recovered key if threshold reached, None otherwise
        
        Raises:
            ValueError: If ceremony not found or share invalid
        """
        ceremony = self._active_ceremonies.get(ceremony_id)
        if not ceremony:
            raise ValueError(f"Ceremony not found: {ceremony_id}")
        
        if ceremony.status != RecoveryStatus.IN_PROGRESS:
            raise ValueError(f"Ceremony not in progress: {ceremony.status}")
        
        # Validate share
        if share.key_fingerprint != ceremony.key_fingerprint:
            raise ValueError("Share fingerprint doesn't match ceremony")
        
        if share.is_expired():
            raise ValueError("Share has expired")
        
        if share.used_at:
            raise ValueError("Share has already been used")
        
        # Check for duplicate share IDs
        existing_ids = {s.share_id for s in ceremony.shares_collected}
        if share.share_id in existing_ids:
            raise ValueError(f"Share {share.share_id} already submitted")
        
        # Add share to ceremony
        share.used_at = datetime.now()
        share.used_by = submitted_by
        ceremony.shares_collected.append(share)
        ceremony.participants.add(submitted_by)
        
        logger.info(f"Submitted share {share.share_id} to ceremony {ceremony_id} "
                   f"by {submitted_by} ({len(ceremony.shares_collected)}/{ceremony.threshold})")
        
        # Check if threshold reached
        if len(ceremony.shares_collected) >= ceremony.threshold:
            return self._complete_recovery(ceremony)
        
        self._save_data()
        return None
    
    def _complete_recovery(self, ceremony: RecoveryCeremony) -> bytes:
        """
        Complete recovery ceremony and reconstruct key.
        
        Args:
            ceremony: Ceremony to complete
        
        Returns:
            Recovered key material
        """
        try:
            # Reconstruct key
            shares_data = [
                (s.share_id, s.share_data) for s in ceremony.shares_collected
            ]
            recovered_key = self._sss.reconstruct_secret(shares_data)
            
            ceremony.recovered_key = recovered_key
            ceremony.status = RecoveryStatus.COMPLETED
            ceremony.completed_at = datetime.now()
            
            # Verify fingerprint
            recovered_fingerprint = self._compute_fingerprint(recovered_key)
            if recovered_fingerprint != ceremony.key_fingerprint:
                ceremony.status = RecoveryStatus.FAILED
                raise ValueError("Recovered key fingerprint mismatch - possible corruption")
            
            self._save_data()
            
            logger.warning(f"Completed key recovery ceremony: {ceremony.ceremony_id} "
                          f"with {len(ceremony.shares_collected)} shares")
            
            return recovered_key
            
        except Exception as e:
            ceremony.status = RecoveryStatus.FAILED
            self._save_data()
            raise ValueError(f"Key reconstruction failed: {e}")
    
    def cancel_recovery(self, ceremony_id: str, reason: str) -> bool:
        """
        Cancel a recovery ceremony.
        
        Args:
            ceremony_id: Ceremony to cancel
            reason: Reason for cancellation
        
        Returns:
            True if cancelled successfully
        """
        ceremony = self._active_ceremonies.get(ceremony_id)
        if not ceremony:
            return False
        
        ceremony.status = RecoveryStatus.FAILED
        self._save_data()
        
        logger.info(f"Cancelled recovery ceremony {ceremony_id}: {reason}")
        return True
    
    def get_ceremony_status(self, ceremony_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a recovery ceremony."""
        ceremony = self._active_ceremonies.get(ceremony_id)
        if not ceremony:
            return None
        
        return {
            "ceremony_id": ceremony.ceremony_id,
            "status": ceremony.status.name,
            "key_fingerprint": ceremony.key_fingerprint,
            "shares_collected": len(ceremony.shares_collected),
            "threshold": ceremony.threshold,
            "participants": list(ceremony.participants),
            "created_at": ceremony.created_at.isoformat(),
            "completed": ceremony.status == RecoveryStatus.COMPLETED,
        }
    
    def list_active_ceremonies(self) -> List[Dict[str, Any]]:
        """List all active recovery ceremonies."""
        return [
            self.get_ceremony_status(cid) for cid in self._active_ceremonies.keys()
        ]
    
    def verify_share(self, share: KeyShare, key_fingerprint: str) -> bool:
        """
        Verify a share is valid for a key.
        
        Args:
            share: Share to verify
            key_fingerprint: Expected key fingerprint
        
        Returns:
            True if share is valid
        """
        if share.key_fingerprint != key_fingerprint:
            return False
        
        if share.is_expired():
            return False
        
        if share.used_at:
            return False
        
        return True
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on recovery system."""
        try:
            # Test split and reconstruct
            test_secret = secrets.token_bytes(32)
            test_shares = self._sss.split_secret(test_secret, 2, 3)
            reconstructed = self._sss.reconstruct_secret(test_shares[:2])
            
            if reconstructed != test_secret:
                raise ValueError("SSS test failed - reconstruction mismatch")
            
            return {
                "status": "healthy",
                "sss_available": HAS_CRYPTO,
                "active_ceremonies": len(self._active_ceremonies),
                "keys_with_shares": len(self._distributed_shares),
                "default_threshold": self.default_threshold,
                "default_shares": self.default_total_shares,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }


# Global instance
_recovery_manager: Optional[KeyRecoveryManager] = None


def init_key_recovery_manager(**kwargs) -> KeyRecoveryManager:
    """Initialize global key recovery manager."""
    global _recovery_manager
    _recovery_manager = KeyRecoveryManager(**kwargs)
    return _recovery_manager


def get_key_recovery_manager() -> KeyRecoveryManager:
    """Get global key recovery manager."""
    if _recovery_manager is None:
        raise RuntimeError("Key recovery manager not initialized. Call init_key_recovery_manager() first.")
    return _recovery_manager


def split_key_for_recovery(
    key_material: bytes,
    key_id: str,
    recipients: List[str],
) -> Dict[str, KeyShare]:
    """
    Split a key and distribute to recipients for recovery.
    
    Args:
        key_material: Key to protect
        key_id: Key identifier
        recipients: List of share recipients
    
    Returns:
        Mapping of recipient -> share
    """
    manager = get_key_recovery_manager()
    shares = manager.split_key(key_material, key_id)
    return manager.distribute_shares(shares, recipients)


def initiate_key_recovery(key_fingerprint: str, requested_by: str) -> RecoveryCeremony:
    """Initiate a key recovery ceremony."""
    return get_key_recovery_manager().initiate_recovery(key_fingerprint, requested_by)


def submit_recovery_share(
    ceremony_id: str,
    share: KeyShare,
    submitted_by: str,
) -> Optional[bytes]:
    """Submit a share to a recovery ceremony."""
    return get_key_recovery_manager().submit_share(ceremony_id, share, submitted_by)
