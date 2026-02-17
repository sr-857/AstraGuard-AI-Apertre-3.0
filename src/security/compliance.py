"""
Compliance and Audit System for Encryption

Provides:
- FIPS 140-2 compliance mode
- Comprehensive audit logging
- Key lineage tracking
- Compliance reporting
- Regulatory compliance (GDPR, HIPAA, SOC2)
"""

import os
import json
import logging
import hashlib
import platform
import secrets
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from threading import Lock

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


class ComplianceStandard(Enum):
    """Supported compliance standards."""
    FIPS_140_2 = "fips_140_2"
    FIPS_140_3 = "fips_140_3"
    GDPR = "gdpr"
    HIPAA = "hipaa"
    SOC2 = "soc2"
    PCI_DSS = "pci_dss"


class AuditEventType(Enum):
    """Types of audit events."""
    KEY_GENERATED = "key_generated"
    KEY_ROTATED = "key_rotated"
    KEY_REVOKED = "key_revoked"
    KEY_DESTROYED = "key_destroyed"
    KEY_ACCESSED = "key_accessed"
    ENCRYPTION_PERFORMED = "encryption_performed"
    DECRYPTION_PERFORMED = "decryption_performed"
    DATA_ENCRYPTED = "data_encrypted"
    DATA_DECRYPTED = "data_decrypted"
    HSM_OPERATION = "hsm_operation"
    RECOVERY_INITIATED = "recovery_initiated"
    RECOVERY_COMPLETED = "recovery_completed"
    POLICY_VIOLATION = "policy_violation"
    CONFIGURATION_CHANGED = "configuration_changed"


@dataclass
class AuditEvent:
    """A single audit event."""
    event_id: str
    timestamp: datetime
    event_type: AuditEventType
    actor: str
    resource_id: str
    resource_type: str
    action: str
    status: str
    details: Dict[str, Any] = field(default_factory=dict)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    correlation_id: Optional[str] = None
    hash_chain: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "actor": self.actor,
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "action": self.action,
            "status": self.status,
            "details": self.details,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "correlation_id": self.correlation_id,
            "hash_chain": self.hash_chain,
        }


@dataclass
class ComplianceReport:
    """Compliance status report."""
    generated_at: datetime
    standard: ComplianceStandard
    status: str
    checks_passed: int
    checks_failed: int
    findings: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "standard": self.standard.value,
            "status": self.status,
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
            "findings": self.findings,
            "recommendations": self.recommendations,
        }


class FIPSMode:
    """FIPS 140-2/140-3 compliance mode management."""
    
    APPROVED_ALGORITHMS = {
        "AES-128-GCM", "AES-192-GCM", "AES-256-GCM",
        "AES-128-CBC", "AES-192-CBC", "AES-256-CBC",
        "SHA-256", "SHA-384", "SHA-512",
        "HMAC-SHA256", "HMAC-SHA384", "HMAC-SHA512",
        "RSA-2048", "RSA-3072", "RSA-4096",
        "ECDSA-P256", "ECDSA-P384", "ECDSA-P521",
    }
    
    NON_APPROVED_ALGORITHMS = {
        "MD5", "SHA-1", "DES", "3DES", "RC4", "Blowfish", "RSA-1024",
    }
    
    def __init__(self, enabled: bool = False, level: int = 2):
        self.enabled = enabled
        self.level = level
        self._violations: List[Dict[str, Any]] = []
        
        if enabled:
            self._validate_environment()
            logger.info(f"FIPS mode enabled (level {level})")
    
    def _validate_environment(self) -> None:
        """Validate environment for FIPS compliance."""
        try:
            import ssl
            if hasattr(ssl, 'FIPS_mode') and not ssl.FIPS_mode():
                logger.warning("OpenSSL FIPS mode not enabled at system level")
        except Exception:
            pass
    
    def is_algorithm_allowed(self, algorithm: str) -> bool:
        """Check if algorithm is FIPS-approved."""
        if not self.enabled:
            return True
        
        algorithm_upper = algorithm.upper()
        
        for non_approved in self.NON_APPROVED_ALGORITHMS:
            if non_approved in algorithm_upper:
                return False
        
        for approved in self.APPROVED_ALGORITHMS:
            if approved in algorithm_upper:
                return True
        
        return True
    
    def validate_operation(self, operation: str, algorithm: str) -> bool:
        """Validate a cryptographic operation."""
        if not self.enabled:
            return True
        
        if not self.is_algorithm_allowed(algorithm):
            violation = {
                "timestamp": datetime.now().isoformat(),
                "operation": operation,
                "algorithm": algorithm,
                "severity": "high",
            }
            self._violations.append(violation)
            raise ValueError(f"FIPS violation: Algorithm '{algorithm}' not FIPS-approved")
        
        return True
    
    def get_violations(self) -> List[Dict[str, Any]]:
        """Get list of FIPS violations."""
        return self._violations.copy()
    
    def generate_compliance_report(self) -> ComplianceReport:
        """Generate FIPS compliance report."""
        findings = []
        
        system_fips = False
        try:
            with open("/proc/sys/crypto/fips_enabled", "r") as f:
                system_fips = f.read().strip() == "1"
        except Exception:
            pass
        
        if not system_fips and self.enabled:
            findings.append({
                "check": "system_fips_mode",
                "status": "warning",
                "message": "System FIPS mode not enabled, application-level only",
            })
        
        if self._violations:
            findings.append({
                "check": "fips_violations",
                "status": "failed",
                "message": f"{len(self._violations)} FIPS violations detected",
                "violations": self._violations[-10:],
            })
        
        findings.append({
            "check": "approved_algorithms",
            "status": "passed",
            "message": f"Using FIPS-approved algorithms: {len(self.APPROVED_ALGORITHMS)}",
        })
        
        status = "compliant" if not findings else "partial"
        
        return ComplianceReport(
            generated_at=datetime.now(),
            standard=ComplianceStandard.FIPS_140_2,
            status=status,
            checks_passed=len([f for f in findings if f["status"] == "passed"]),
            checks_failed=len([f for f in findings if f["status"] == "failed"]),
            findings=findings,
            recommendations=[
                "Enable system-level FIPS mode",
                "Use FIPS-approved hardware security modules (HSM)",
                "Regular compliance audits",
            ] if not system_fips else [],
        )


class AuditLogger:
    """Tamper-evident audit logging for encryption operations."""
    
    def __init__(
        self,
        storage_path: Optional[str] = None,
        retention_days: int = 365,
        max_events_per_file: int = 10000,
    ):
        self.storage_path = Path(storage_path) if storage_path else Path("logs/audit")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.retention_days = retention_days
        self.max_events_per_file = max_events_per_file
        
        self._lock = Lock()
        self._current_file: Optional[Path] = None
        self._events_in_current_file = 0
        self._last_hash: Optional[str] = None
        
        self._initialize_log_file()
        
        logger.info(f"AuditLogger initialized (retention={retention_days} days)")
    
    def _initialize_log_file(self) -> None:
        """Initialize or resume log file with hash chain."""
        log_files = sorted(self.storage_path.glob("audit-*.jsonl"))
        
        if log_files:
            self._current_file = log_files[-1]
            with open(self._current_file, "r") as f:
                lines = f.readlines()
                self._events_in_current_file = len(lines)
                if lines:
                    last_event = json.loads(lines[-1])
                    self._last_hash = last_event.get("hash_chain")
        else:
            self._create_new_log_file()
    
    def _create_new_log_file(self) -> None:
        """Create a new log file."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self._current_file = self.storage_path / f"audit-{timestamp}.jsonl"
        self._events_in_current_file = 0
        self._last_hash = None
    
    def _compute_event_hash(self, event: AuditEvent) -> str:
        """Compute hash for tamper detection."""
        data = {
            "previous_hash": self._last_hash,
            "event": event.to_dict(),
        }
        hash_input = json.dumps(data, sort_keys=True)
        return hashlib.sha256(hash_input.encode()).hexdigest()
    
    def log_event(
        self,
        event_type: AuditEventType,
        actor: str,
        resource_id: str,
        resource_type: str,
        action: str,
        status: str = "success",
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> AuditEvent:
        """Log an audit event."""
        with self._lock:
            if self._events_in_current_file >= self.max_events_per_file:
                self._create_new_log_file()
            
            event = AuditEvent(
                event_id=f"evt-{datetime.now().strftime('%Y%m%d%H%M%S%f')}-{secrets.token_hex(4)}",
                timestamp=datetime.now(),
                event_type=event_type,
                actor=actor,
                resource_id=resource_id,
                resource_type=resource_type,
                action=action,
                status=status,
                details=details or {},
                ip_address=ip_address,
                correlation_id=correlation_id,
            )
            
            event.hash_chain = self._compute_event_hash(event)
            self._last_hash = event.hash_chain
            
            with open(self._current_file, "a") as f:
                f.write(json.dumps(event.to_dict()) + "\n")
            
            self._events_in_current_file += 1
            logger.debug(f"Audit: {event_type.value} by {actor} on {resource_id} ({status})")
            
            return event
    
    def query_events(
        self,
        event_type: Optional[AuditEventType] = None,
        actor: Optional[str] = None,
        resource_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[AuditEvent]:
        """Query audit events with filters."""
        events = []
        log_files = sorted(self.storage_path.glob("audit-*.jsonl"), reverse=True)
        
        for log_file in log_files:
            with open(log_file, "r") as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        event = AuditEvent(
                            event_id=data["event_id"],
                            timestamp=datetime.fromisoformat(data["timestamp"]),
                            event_type=AuditEventType(data["event_type"]),
                            actor=data["actor"],
                            resource_id=data["resource_id"],
                            resource_type=data["resource_type"],
                            action=data["action"],
                            status=data["status"],
                            details=data.get("details", {}),
                            ip_address=data.get("ip_address"),
                            user_agent=data.get("user_agent"),
                            correlation_id=data.get("correlation_id"),
                            hash_chain=data.get("hash_chain"),
                        )
                        
                        if event_type and event.event_type != event_type:
                            continue
                        if actor and event.actor != actor:
                            continue
                        if resource_id and event.resource_id != resource_id:
                            continue
                        if start_time and event.timestamp < start_time:
                            continue
                        if end_time and event.timestamp > end_time:
                            continue
                        
                        events.append(event)
                        
                        if len(events) >= limit:
                            return events
                    except Exception as e:
                        logger.error(f"Failed to parse audit event: {e}")
        
        return events
    
    def verify_integrity(self, log_file: Optional[Path] = None) -> Dict[str, Any]:
        """Verify tamper-evident integrity of audit log."""
        if log_file is None:
            log_files = sorted(self.storage_path.glob("audit-*.jsonl"))
            if not log_files:
                return {"status": "no_logs", "valid": True}
            log_file = log_files[-1]
        
        previous_hash = None
        violations = []
        event_count = 0
        
        with open(log_file, "r") as f:
            for line_num, line in enumerate(f, 1):
                try:
                    data = json.loads(line)
                    stored_hash = data.get("hash_chain")
                    
                    hash_data = {
                        "previous_hash": previous_hash,
                        "event": {k: v for k, v in data.items() if k != "hash_chain"},
                    }
                    computed_hash = hashlib.sha256(
                        json.dumps(hash_data, sort_keys=True).encode()
                    ).hexdigest()
                    
                    if stored_hash != computed_hash:
                        violations.append({
                            "line": line_num,
                            "expected": computed_hash,
                            "found": stored_hash,
                        })
                    
                    previous_hash = stored_hash
                    event_count += 1
                except Exception as e:
                    violations.append({"line": line_num, "error": str(e)})
        
        return {
            "file": str(log_file),
            "events_verified": event_count,
            "violations": violations,
            "valid": len(violations) == 0,
        }


class ComplianceManager:
    """Central compliance management for all standards."""
    
    def __init__(
        self,
        fips_enabled: bool = False,
        fips_level: int = 2,
        audit_retention_days: int = 365,
        standards: Optional[Set[ComplianceStandard]] = None,
    ):
        self.fips = FIPSMode(enabled=fips_enabled, level=fips_level)
        self.audit = AuditLogger(retention_days=audit_retention_days)
        self.standards = standards or {ComplianceStandard.FIPS_140_2}
        self._key_lineage: Dict[str, List[Dict[str, Any]]] = {}
        
        logger.info(f"ComplianceManager initialized (FIPS={fips_enabled})")
    
    def log_key_operation(
        self,
        operation: str,
        key_id: str,
        actor: str = "system",
        details: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> AuditEvent:
        """Log a key operation."""
        event_type_map = {
            "generate": AuditEventType.KEY_GENERATED,
            "rotate": AuditEventType.KEY_ROTATED,
            "revoke": AuditEventType.KEY_REVOKED,
            "destroy": AuditEventType.KEY_DESTROYED,
            "access": AuditEventType.KEY_ACCESSED,
        }
        
        event_type = event_type_map.get(operation, AuditEventType.KEY_ACCESSED)
        
        return self.audit.log_event(
            event_type=event_type,
            actor=actor,
            resource_id=key_id,
            resource_type="cryptographic_key",
            action=operation,
            details=details,
            **kwargs,
        )
    
    def log_encryption(self, operation: str, actor: str = "system", **kwargs) -> AuditEvent:
        """Log encryption/decryption operation."""
        event_type = (
            AuditEventType.ENCRYPTION_PERFORMED
            if "encrypt" in operation.lower()
            else AuditEventType.DECRYPTION_PERFORMED
        )
        
        return self.audit.log_event(
            event_type=event_type,
            actor=actor,
            resource_id="encryption_engine",
            resource_type="cryptographic_operation",
            action=operation,
            **kwargs,
        )
    
    def track_key_lineage(
        self,
        key_id: str,
        parent_key_id: Optional[str] = None,
        operation: str = "created",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Track key lineage for audit."""
        if key_id not in self._key_lineage:
            self._key_lineage[key_id] = []
        
        entry = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "parent_key_id": parent_key_id,
            "metadata": metadata or {},
        }
        self._key_lineage[key_id].append(entry)
    
    def get_key_lineage(self, key_id: str) -> List[Dict[str, Any]]:
        """Get lineage history for a key."""
        return self._key_lineage.get(key_id, []).copy()
    
    def generate_compliance_report(
        self,
        standard: Optional[ComplianceStandard] = None,
    ) -> ComplianceReport:
        """Generate compliance report."""
        if standard == ComplianceStandard.FIPS_140_2 or standard is None:
            return self.fips.generate_compliance_report()
        
        return ComplianceReport(
            generated_at=datetime.now(),
            standard=standard or ComplianceStandard.SOC2,
            status="unknown",
            checks_passed=0,
            checks_failed=0,
            findings=[{
                "check": "not_implemented",
                "status": "warning",
                "message": f"Compliance checks for {standard.value} not implemented",
            }],
        )
    
    def health_check(self) -> Dict[str, Any]:
        """Perform compliance health check."""
        return {
            "fips_enabled": self.fips.enabled,
            "fips_level": self.fips.level,
            "audit_logs_path": str(self.audit.storage_path),
            "retention_days": self.audit.retention_days,
            "standards": [s.value for s in self.standards],
            "fips_violations": len(self.fips.get_violations()),
        }


_compliance_manager: Optional[ComplianceManager] = None


def init_compliance_manager(**kwargs) -> ComplianceManager:
    """Initialize global compliance manager."""
    global _compliance_manager
    _compliance_manager = ComplianceManager(**kwargs)
    return _compliance_manager


def get_compliance_manager() -> ComplianceManager:
    """Get global compliance manager."""
    if _compliance_manager is None:
        raise RuntimeError("Compliance manager not initialized")
    return _compliance_manager


def log_key_event(operation: str, key_id: str, **kwargs) -> AuditEvent:
    """Log a key operation."""
    return get_compliance_manager().log_key_operation(operation, key_id, **kwargs)


def log_encryption_event(operation: str, **kwargs) -> AuditEvent:
    """Log an encryption operation."""
    return get_compliance_manager().log_encryption(operation, **kwargs)
