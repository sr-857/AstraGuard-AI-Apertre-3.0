"""
Automatic Key Rotation System

Provides:
- Scheduled key rotation with configurable policies
- Grace period management for seamless transitions
- Key lineage tracking
- Automated rotation triggers (time-based, usage-based)
- Emergency rotation capabilities
"""

import os
import json
import logging
import asyncio
import threading
from typing import Optional, Dict, List, Any, Callable, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
import schedule
import time

from .key_management import (
    KeyHierarchy, KeyMetadata, KeyType, KeyStatus, ManagedKey,
    get_key_hierarchy, init_key_hierarchy,
)
from .hsm_client import HSMClient, get_hsm_client, init_hsm_client, HSMProvider

logger = logging.getLogger(__name__)


class RotationTrigger(Enum):
    """Reasons for key rotation."""
    SCHEDULED = auto()
    USAGE_LIMIT = auto()
    EMERGENCY = auto()
    COMPROMISE = auto()
    POLICY_CHANGE = auto()
    MANUAL = auto()


@dataclass
class RotationPolicy:
    """Policy for automatic key rotation."""
    key_type: KeyType
    rotation_period_days: int = 90
    grace_period_days: int = 7
    max_usage_count: Optional[int] = None  # Rotate after N uses
    auto_rotate: bool = True
    notify_before_days: int = 14
    retain_old_keys_days: int = 30
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "key_type": self.key_type.value,
            "rotation_period_days": self.rotation_period_days,
            "grace_period_days": self.grace_period_days,
            "max_usage_count": self.max_usage_count,
            "auto_rotate": self.auto_rotate,
            "notify_before_days": self.notify_before_days,
            "retain_old_keys_days": self.retain_old_keys_days,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RotationPolicy":
        return cls(
            key_type=KeyType(data["key_type"]),
            rotation_period_days=data["rotation_period_days"],
            grace_period_days=data["grace_period_days"],
            max_usage_count=data.get("max_usage_count"),
            auto_rotate=data.get("auto_rotate", True),
            notify_before_days=data.get("notify_before_days", 14),
            retain_old_keys_days=data.get("retain_old_keys_days", 30),
        )


@dataclass
class RotationEvent:
    """Record of a key rotation event."""
    event_id: str
    key_id: str
    old_key_id: Optional[str]
    new_key_id: str
    trigger: RotationTrigger
    rotated_at: datetime
    grace_period_ends: datetime
    old_key_retires_at: datetime
    status: str = "active"  # active, completed, failed
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "key_id": self.key_id,
            "old_key_id": self.old_key_id,
            "new_key_id": self.new_key_id,
            "trigger": self.trigger.name,
            "rotated_at": self.rotated_at.isoformat(),
            "grace_period_ends": self.grace_period_ends.isoformat(),
            "old_key_retires_at": self.old_key_retires_at.isoformat(),
            "status": self.status,
        }


class KeyRotationManager:
    """
    Manages automatic key rotation with policies and scheduling.
    
    Features:
    - Time-based rotation (e.g., every 90 days)
    - Usage-based rotation (e.g., after 1M encryptions)
    - Grace periods for seamless transitions
    - Emergency rotation capabilities
    - Audit logging of all rotation events
    """
    
    def __init__(
        self,
        key_hierarchy: Optional[KeyHierarchy] = None,
        hsm_client: Optional[HSMClient] = None,
        storage_path: Optional[str] = None,
        check_interval_minutes: int = 60,
    ):
        """
        Initialize key rotation manager.
        
        Args:
            key_hierarchy: Key hierarchy instance
            hsm_client: HSM client for HSM-backed keys
            storage_path: Path for rotation event storage
            check_interval_minutes: How often to check for rotations needed
        """
        self.key_hierarchy = key_hierarchy or get_key_hierarchy()
        self.hsm_client = hsm_client or get_hsm_client()
        self.storage_path = Path(storage_path) if storage_path else Path(".key_rotations")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.check_interval = timedelta(minutes=check_interval_minutes)
        self._policies: Dict[KeyType, RotationPolicy] = {}
        self._rotation_history: List[RotationEvent] = []
        self._active_rotations: Dict[str, RotationEvent] = {}
        self._callbacks: List[Callable[[RotationEvent], None]] = []
        
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._scheduler_thread: Optional[threading.Thread] = None
        
        self._load_history()
        self._setup_default_policies()
        
        logger.info("KeyRotationManager initialized")
    
    def _setup_default_policies(self) -> None:
        """Set up default rotation policies."""
        self._policies[KeyType.KEY_ENCRYPTION] = RotationPolicy(
            key_type=KeyType.KEY_ENCRYPTION,
            rotation_period_days=90,
            grace_period_days=7,
            auto_rotate=True,
        )
        
        self._policies[KeyType.DATA_ENCRYPTION] = RotationPolicy(
            key_type=KeyType.DATA_ENCRYPTION,
            rotation_period_days=1,  # DEKs rotate daily
            grace_period_days=1,
            max_usage_count=100000,  # Or after 100K uses
            auto_rotate=True,
        )
    
    def _load_history(self) -> None:
        """Load rotation history from storage."""
        history_file = self.storage_path / "rotation_history.json"
        if history_file.exists():
            try:
                with open(history_file, "r") as f:
                    data = json.load(f)
                    for event_data in data:
                        event = RotationEvent(
                            event_id=event_data["event_id"],
                            key_id=event_data["key_id"],
                            old_key_id=event_data.get("old_key_id"),
                            new_key_id=event_data["new_key_id"],
                            trigger=RotationTrigger[event_data["trigger"]],
                            rotated_at=datetime.fromisoformat(event_data["rotated_at"]),
                            grace_period_ends=datetime.fromisoformat(event_data["grace_period_ends"]),
                            old_key_retires_at=datetime.fromisoformat(event_data["old_key_retires_at"]),
                            status=event_data["status"],
                        )
                        self._rotation_history.append(event)
                        if event.status == "active":
                            self._active_rotations[event.key_id] = event
            except Exception as e:
                logger.error(f"Failed to load rotation history: {e}")
    
    def _save_history(self) -> None:
        """Save rotation history to storage."""
        history_file = self.storage_path / "rotation_history.json"
        try:
            data = [event.to_dict() for event in self._rotation_history]
            with open(history_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save rotation history: {e}")
    
    def set_policy(self, policy: RotationPolicy) -> None:
        """Set rotation policy for a key type."""
        with self._lock:
            self._policies[policy.key_type] = policy
            logger.info(f"Set rotation policy for {policy.key_type.value}: "
                       f"{policy.rotation_period_days} days")
    
    def get_policy(self, key_type: KeyType) -> Optional[RotationPolicy]:
        """Get rotation policy for a key type."""
        return self._policies.get(key_type)
    
    def register_callback(self, callback: Callable[[RotationEvent], None]) -> None:
        """Register callback for rotation events."""
        self._callbacks.append(callback)
    
    def _notify_callbacks(self, event: RotationEvent) -> None:
        """Notify all registered callbacks."""
        for callback in self._callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Rotation callback failed: {e}")
    
    def check_rotation_needed(self, key: ManagedKey) -> Optional[RotationTrigger]:
        """
        Check if a key needs rotation.
        
        Args:
            key: Key to check
        
        Returns:
            RotationTrigger if rotation needed, None otherwise
        """
        policy = self._policies.get(key.metadata.key_type)
        if not policy or not policy.auto_rotate:
            return None
        
        # Check time-based rotation
        if key.metadata.rotated_at:
            time_since_rotation = datetime.now() - key.metadata.rotated_at
            if time_since_rotation >= timedelta(days=policy.rotation_period_days):
                return RotationTrigger.SCHEDULED
        else:
            # Never rotated - check creation time
            time_since_creation = datetime.now() - key.metadata.created_at
            if time_since_creation >= timedelta(days=policy.rotation_period_days):
                return RotationTrigger.SCHEDULED
        
        # Check usage-based rotation
        if policy.max_usage_count and key.metadata.usage_count >= policy.max_usage_count:
            return RotationTrigger.USAGE_LIMIT
        
        return None
    
    def rotate_kek(self, trigger: RotationTrigger = RotationTrigger.MANUAL) -> RotationEvent:
        """
        Rotate the Key Encryption Key (KEK).
        
        Args:
            trigger: Reason for rotation
        
        Returns:
            RotationEvent record
        """
        with self._lock:
            # Get current KEK
            old_kek_id = None
            if self.key_hierarchy._current_kek:
                old_kek_id = self.key_hierarchy._current_kek.metadata.key_id
            
            # Perform rotation
            new_kek_id = self.key_hierarchy.rotate_kek()
            
            policy = self._policies.get(KeyType.KEY_ENCRYPTION)
            grace_days = policy.grace_period_days if policy else 7
            
            event = RotationEvent(
                event_id=f"rot-{datetime.now().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(4)}",
                key_id="kek",
                old_key_id=old_kek_id,
                new_key_id=new_kek_id,
                trigger=trigger,
                rotated_at=datetime.now(),
                grace_period_ends=datetime.now() + timedelta(days=grace_days),
                old_key_retires_at=datetime.now() + timedelta(days=policy.retain_old_keys_days if policy else 30),
            )
            
            self._rotation_history.append(event)
            self._active_rotations["kek"] = event
            self._save_history()
            
            self._notify_callbacks(event)
            
            logger.info(f"Rotated KEK: {old_kek_id} -> {new_kek_id} ({trigger.name})")
            return event
    
    def rotate_dek(
        self,
        key_id: str,
        trigger: RotationTrigger = RotationTrigger.MANUAL,
    ) -> Optional[RotationEvent]:
        """
        Rotate a specific Data Encryption Key.
        
        Args:
            key_id: DEK to rotate
            trigger: Reason for rotation
        
        Returns:
            RotationEvent record or None
        """
        with self._lock:
            key = self.key_hierarchy.get_key(key_id)
            if not key:
                logger.warning(f"Key not found for rotation: {key_id}")
                return None
            
            # Mark old key as rotating
            key.metadata.status = KeyStatus.ROTATING
            key.metadata.rotated_at = datetime.now()
            
            # Generate new DEK
            new_dek = self.key_hierarchy.generate_dek(
                purpose=key_id.split("-")[1] if "-" in key_id else "general",
                expires_in_days=1,
                hsm_backed=key.metadata.hsm_key_handle is not None,
            )
            
            policy = self._policies.get(KeyType.DATA_ENCRYPTION)
            grace_days = policy.grace_period_days if policy else 1
            
            event = RotationEvent(
                event_id=f"rot-{datetime.now().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(4)}",
                key_id=key_id,
                old_key_id=key_id,
                new_key_id=new_dek.metadata.key_id,
                trigger=trigger,
                rotated_at=datetime.now(),
                grace_period_ends=datetime.now() + timedelta(days=grace_days),
                old_key_retires_at=datetime.now() + timedelta(days=policy.retain_old_keys_days if policy else 7),
            )
            
            self._rotation_history.append(event)
            self._active_rotations[key_id] = event
            self._save_history()
            
            self._notify_callbacks(event)
            
            logger.info(f"Rotated DEK: {key_id} -> {new_dek.metadata.key_id} ({trigger.name})")
            return event
    
    def emergency_rotation(self, reason: str) -> List[RotationEvent]:
        """
        Perform emergency rotation of all keys.
        
        Args:
            reason: Reason for emergency rotation
        
        Returns:
            List of rotation events
        """
        logger.warning(f"EMERGENCY KEY ROTATION: {reason}")
        
        events = []
        
        # Rotate KEK first
        kek_event = self.rotate_kek(trigger=RotationTrigger.EMERGENCY)
        events.append(kek_event)
        
        # Rotate all active DEKs
        all_keys = self.key_hierarchy.list_keys()
        for key_meta in all_keys:
            if key_meta.key_type == KeyType.DATA_ENCRYPTION and key_meta.is_active():
                event = self.rotate_dek(key_meta.key_id, trigger=RotationTrigger.EMERGENCY)
                if event:
                    events.append(event)
        
        return events
    
    def complete_rotation(self, key_id: str) -> bool:
        """
        Mark a rotation as complete (grace period ended).
        
        Args:
            key_id: Key that was rotated
        
        Returns:
            True if completed successfully
        """
        with self._lock:
            event = self._active_rotations.get(key_id)
            if not event:
                return False
            
            # Retire old key
            if event.old_key_id:
                old_key = self.key_hierarchy.get_key(event.old_key_id)
                if old_key:
                    old_key.metadata.status = KeyStatus.RETIRED
            
            event.status = "completed"
            del self._active_rotations[key_id]
            self._save_history()
            
            logger.info(f"Completed rotation for {key_id}")
            return True
    
    def get_active_rotations(self) -> List[RotationEvent]:
        """Get all active (in grace period) rotations."""
        return list(self._active_rotations.values())
    
    def get_rotation_history(
        self,
        key_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[RotationEvent]:
        """
        Get rotation history.
        
        Args:
            key_id: Filter by specific key
            limit: Maximum number of events
        
        Returns:
            List of rotation events
        """
        events = self._rotation_history
        if key_id:
            events = [e for e in events if e.key_id == key_id]
        
        return sorted(events, key=lambda e: e.rotated_at, reverse=True)[:limit]
    
    def check_all_rotations(self) -> List[RotationEvent]:
        """
        Check all keys and rotate if needed.
        
        Returns:
            List of rotation events performed
        """
        events = []
        
        # Check KEK
        if self.key_hierarchy._current_kek:
            trigger = self.check_rotation_needed(self.key_hierarchy._current_kek)
            if trigger:
                event = self.rotate_kek(trigger=trigger)
                events.append(event)
        
        # Check all DEKs
        all_keys = self.key_hierarchy.list_keys()
        for key_meta in all_keys:
            if key_meta.key_type == KeyType.DATA_ENCRYPTION:
                key = self.key_hierarchy.get_key(key_meta.key_id)
                if key:
                    trigger = self.check_rotation_needed(key)
                    if trigger:
                        event = self.rotate_dek(key_meta.key_id, trigger=trigger)
                        if event:
                            events.append(event)
        
        # Check for completed grace periods
        now = datetime.now()
        for key_id, event in list(self._active_rotations.items()):
            if now >= event.grace_period_ends:
                self.complete_rotation(key_id)
        
        return events
    
    def start_scheduler(self) -> None:
        """Start the automatic rotation scheduler."""
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            logger.warning("Scheduler already running")
            return
        
        self._stop_event.clear()
        self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._scheduler_thread.start()
        
        logger.info("Key rotation scheduler started")
    
    def stop_scheduler(self) -> None:
        """Stop the automatic rotation scheduler."""
        self._stop_event.set()
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5)
            logger.info("Key rotation scheduler stopped")
    
    def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        while not self._stop_event.is_set():
            try:
                self.check_all_rotations()
            except Exception as e:
                logger.error(f"Rotation check failed: {e}")
            
            # Sleep until next check
            self._stop_event.wait(self.check_interval.total_seconds())
    
    def get_status(self) -> Dict[str, Any]:
        """Get rotation manager status."""
        return {
            "scheduler_running": self._scheduler_thread is not None and self._scheduler_thread.is_alive(),
            "active_rotations": len(self._active_rotations),
            "total_rotations": len(self._rotation_history),
            "policies": {k.value: v.to_dict() for k, v in self._policies.items()},
            "next_check_seconds": self.check_interval.total_seconds(),
        }


# Global instance
_rotation_manager: Optional[KeyRotationManager] = None


def init_key_rotation_manager(**kwargs) -> KeyRotationManager:
    """Initialize global key rotation manager."""
    global _rotation_manager
    _rotation_manager = KeyRotationManager(**kwargs)
    return _rotation_manager


def get_key_rotation_manager() -> KeyRotationManager:
    """Get global key rotation manager."""
    if _rotation_manager is None:
        raise RuntimeError("Key rotation manager not initialized. Call init_key_rotation_manager() first.")
    return _rotation_manager


def start_automatic_rotation() -> None:
    """Start automatic rotation scheduler."""
    get_key_rotation_manager().start_scheduler()


def stop_automatic_rotation() -> None:
    """Stop automatic rotation scheduler."""
    get_key_rotation_manager().stop_scheduler()


def emergency_rotate_all(reason: str) -> List[RotationEvent]:
    """Perform emergency rotation of all keys."""
    return get_key_rotation_manager().emergency_rotation(reason)
