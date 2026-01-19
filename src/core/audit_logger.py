"""
AstraGuard AI Centralized Audit Logging Module

Provides comprehensive audit logging for security events, access attempts,
system changes, and compliance tracking for satellite operations.

Features:
- Structured JSON logging with consistent schema
- Audit event types for all security-relevant operations
- Log rotation and archival to prevent disk space issues
- Tamper-evident logging through SHA-256 hashing
- Sensitive data sanitization
- Integration with existing logging infrastructure
"""

import os
import json
import hashlib
import logging
import logging.handlers
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum
from pathlib import Path
import structlog
from astraguard.logging_config import get_logger


class AuditEventType(str, Enum):
    """Audit event types for comprehensive security tracking."""

    # Authentication & Authorization
    AUTHENTICATION_SUCCESS = "authentication_success"
    AUTHENTICATION_FAILURE = "authentication_failure"
    AUTHORIZATION_SUCCESS = "authorization_success"
    AUTHORIZATION_FAILURE = "authorization_failure"
    SESSION_START = "session_start"
    SESSION_END = "session_end"

    # Data Access & Operations
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    TELEMETRY_SUBMISSION = "telemetry_submission"
    CONFIGURATION_CHANGE = "configuration_change"

    # Anomaly Detection & Response
    ANOMALY_DETECTED = "anomaly_detected"
    ANOMALY_RESPONSE = "anomaly_response"
    RECOVERY_ACTION = "recovery_action"
    PHASE_TRANSITION = "phase_transition"

    # System & Security Events
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    SECURITY_VIOLATION = "security_violation"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"

    # Administrative Actions
    USER_CREATED = "user_created"
    USER_MODIFIED = "user_modified"
    USER_DELETED = "user_deleted"
    API_KEY_CREATED = "api_key_created"
    API_KEY_REVOKED = "api_key_revoked"
    API_KEY_ROTATED = "api_key_rotated"
    PERMISSION_CHANGE = "permission_change"


class AuditLogger:
    """
    Centralized audit logger with tamper-evident features and structured logging.

    Provides comprehensive audit trail for compliance and security monitoring.
    """

    def __init__(
        self,
        log_dir: str = "logs/audit",
        max_bytes: int = 10 * 1024 * 1024,  # 10MB per file
        backup_count: int = 5,
        service_name: str = "astra-guard"
    ):
        """
        Initialize audit logger with rotation and tamper-evident features.

        Args:
            log_dir: Directory for audit logs
            max_bytes: Maximum bytes per log file before rotation
            backup_count: Number of backup files to keep
            service_name: Name of the service for log entries
        """
        self.service_name = service_name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Main audit log file
        self.audit_log_path = self.log_dir / "audit.log"
        self.integrity_log_path = self.log_dir / "audit_integrity.log"

        # Setup rotating file handler for audit logs
        self.audit_handler = logging.handlers.RotatingFileHandler(
            self.audit_log_path,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        self.audit_handler.setFormatter(logging.Formatter('%(message)s'))

        # Setup integrity log handler (append-only)
        self.integrity_handler = logging.FileHandler(self.integrity_log_path)
        self.integrity_handler.setFormatter(logging.Formatter('%(message)s'))

        # Create audit logger
        self.audit_logger = logging.getLogger('astra_audit')
        self.audit_logger.setLevel(logging.INFO)
        self.audit_logger.addHandler(self.audit_handler)
        self.audit_logger.addHandler(self.integrity_handler)

        # Structlog logger for integration
        self.struct_logger = get_logger('audit')

        # Track last hash for tamper-evident chain
        self._last_hash = self._load_last_hash()

    def _load_last_hash(self) -> str:
        """Load the last hash from integrity log for tamper-evident chain."""
        if not self.integrity_log_path.exists():
            return "0" * 64  # Initial hash

        try:
            with open(self.integrity_log_path, 'r') as f:
                lines = f.readlines()
                if lines:
                    last_line = lines[-1].strip()
                    # Extract hash from integrity log entry
                    if '|' in last_line:
                        return last_line.split('|')[0]
        except Exception:
            pass

        return "0" * 64

    def _sanitize_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize sensitive information from audit data.

        Removes or masks passwords, API keys, tokens, and other sensitive data.
        """
        sanitized = data.copy()

        # Fields to completely remove
        sensitive_fields = {
            'password', 'api_key', 'token', 'secret', 'private_key',
            'encryption_key', 'jwt_secret', 'session_token'
        }

        # Fields to mask (show first/last few characters)
        mask_fields = {'hashed_key', 'encrypted_data'}

        for key in list(sanitized.keys()):
            if key.lower() in sensitive_fields:
                sanitized[key] = "[REDACTED]"
            elif key.lower() in mask_fields and isinstance(sanitized[key], str):
                if len(sanitized[key]) > 8:
                    sanitized[key] = sanitized[key][:4] + "****" + sanitized[key][-4:]
                else:
                    sanitized[key] = "****"

        return sanitized

    def _create_audit_entry(
        self,
        event_type: AuditEventType,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        status: str = "success",
        details: Optional[Dict[str, Any]] = None,
        **extra
    ) -> Dict[str, Any]:
        """
        Create a standardized audit log entry.

        Args:
            event_type: Type of audit event
            user_id: ID of the user performing the action
            ip_address: IP address of the request
            user_agent: User agent string
            session_id: Session identifier
            resource: Resource being accessed/modified
            action: Action being performed
            status: Success/failure status
            details: Additional event-specific details
            **extra: Additional context fields

        Returns:
            Structured audit entry dictionary
        """
        timestamp = datetime.utcnow().isoformat() + "Z"

        entry = {
            "timestamp": timestamp,
            "service": self.service_name,
            "event_type": event_type.value,
            "user_id": user_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "session_id": session_id,
            "resource": resource,
            "action": action,
            "status": status,
            "details": self._sanitize_sensitive_data(details or {}),
            **extra
        }

        # Remove None values
        entry = {k: v for k, v in entry.items() if v is not None}

        return entry

    def log_event(
        self,
        event_type: AuditEventType,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        status: str = "success",
        details: Optional[Dict[str, Any]] = None,
        **extra
    ) -> None:
        """
        Log an audit event with tamper-evident hashing.

        Creates a structured JSON log entry and maintains integrity chain.
        """
        # Create audit entry
        entry = self._create_audit_entry(
            event_type=event_type,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            resource=resource,
            action=action,
            status=status,
            details=details,
            **extra
        )

        # Convert to JSON
        entry_json = json.dumps(entry, sort_keys=True, default=str)

        # Create hash chain for tamper-evident logging
        hash_input = self._last_hash + entry_json
        current_hash = hashlib.sha256(hash_input.encode()).hexdigest()

        # Create integrity entry
        integrity_entry = f"{current_hash}|{entry_json}"

        # Log to audit file (JSON only)
        self.audit_logger.info(entry_json)

        # Log to integrity file (hash + JSON)
        self.integrity_handler.emit(
            logging.LogRecord(
                name='audit_integrity',
                level=logging.INFO,
                pathname='',
                lineno=0,
                msg=integrity_entry,
                args=(),
                exc_info=None
            )
        )

        # Update last hash for chain
        self._last_hash = current_hash

        # Also log to structlog for integration with existing logging
        self.struct_logger.info(
            "audit_event",
            event_type=event_type.value,
            user_id=user_id,
            resource=resource,
            action=action,
            status=status,
            **(details or {})
        )

    def verify_integrity(self) -> bool:
        """
        Verify the integrity of audit logs using hash chain.

        Returns:
            True if logs are intact, False if tampering detected
        """
        if not self.integrity_log_path.exists():
            return True

        expected_hash = "0" * 64

        try:
            with open(self.integrity_log_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    parts = line.split('|', 1)
                    if len(parts) != 2:
                        return False

                    stored_hash, entry_json = parts

                    # Verify hash chain
                    hash_input = expected_hash + entry_json
                    calculated_hash = hashlib.sha256(hash_input.encode()).hexdigest()

                    if calculated_hash != stored_hash:
                        return False

                    expected_hash = stored_hash

            return True

        except Exception:
            return False

    def query_audit_logs(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_type: Optional[AuditEventType] = None,
        user_id: Optional[str] = None,
        resource: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Query audit logs with filtering capabilities.

        Args:
            start_time: Start time for query
            end_time: End time for query
            event_type: Filter by event type
            user_id: Filter by user ID
            resource: Filter by resource
            status: Filter by status
            limit: Maximum number of entries to return

        Returns:
            List of matching audit entries
        """
        results = []

        # Check all audit log files (including rotated ones)
        log_files = [self.audit_log_path]
        for i in range(1, self.audit_handler.backupCount + 1):
            backup_file = self.log_dir / f"audit.log.{i}"
            if backup_file.exists():
                log_files.append(backup_file)

        for log_file in log_files:
            try:
                with open(log_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue

                        try:
                            entry = json.loads(line)

                            # Apply filters
                            if start_time and datetime.fromisoformat(entry['timestamp'][:-1]) < start_time:
                                continue
                            if end_time and datetime.fromisoformat(entry['timestamp'][:-1]) > end_time:
                                continue
                            if event_type and entry.get('event_type') != event_type.value:
                                continue
                            if user_id and entry.get('user_id') != user_id:
                                continue
                            if resource and entry.get('resource') != resource:
                                continue
                            if status and entry.get('status') != status:
                                continue

                            results.append(entry)

                            if len(results) >= limit:
                                return results

                        except json.JSONDecodeError:
                            continue

            except FileNotFoundError:
                continue

        return results

    def get_audit_stats(self) -> Dict[str, Any]:
        """
        Get audit log statistics.

        Returns:
            Dictionary with audit statistics
        """
        total_entries = 0
        event_counts = {}
        user_counts = {}
        recent_entries = []

        # Count entries in current log file
        try:
            with open(self.audit_log_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        entry = json.loads(line)
                        total_entries += 1

                        # Count event types
                        event_type = entry.get('event_type', 'unknown')
                        event_counts[event_type] = event_counts.get(event_type, 0) + 1

                        # Count users
                        user_id = entry.get('user_id')
                        if user_id:
                            user_counts[user_id] = user_counts.get(user_id, 0) + 1

                        # Keep recent entries
                        if len(recent_entries) < 10:
                            recent_entries.append(entry)

                    except json.JSONDecodeError:
                        continue

        except FileNotFoundError:
            pass

        return {
            "total_entries": total_entries,
            "event_type_counts": event_counts,
            "unique_users": len(user_counts),
            "integrity_verified": self.verify_integrity(),
            "log_file_size": self.audit_log_path.stat().st_size if self.audit_log_path.exists() else 0,
            "recent_entries": recent_entries[-5:]  # Last 5 entries
        }


# Global audit logger instance
_audit_logger = None

def get_audit_logger() -> AuditLogger:
    """Get global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


# Convenience functions for common audit events
def log_authentication_success(user_id: str, ip_address: Optional[str] = None, **extra):
    """Log successful authentication."""
    get_audit_logger().log_event(
        AuditEventType.AUTHENTICATION_SUCCESS,
        user_id=user_id,
        ip_address=ip_address,
        **extra
    )

def log_authentication_failure(user_id: Optional[str] = None, ip_address: Optional[str] = None, **extra):
    """Log failed authentication."""
    get_audit_logger().log_event(
        AuditEventType.AUTHENTICATION_FAILURE,
        user_id=user_id,
        ip_address=ip_address,
        status="failure",
        **extra
    )

def log_authorization_success(user_id: str, resource: str, action: str, **extra):
    """Log successful authorization."""
    get_audit_logger().log_event(
        AuditEventType.AUTHORIZATION_SUCCESS,
        user_id=user_id,
        resource=resource,
        action=action,
        **extra
    )

def log_authorization_failure(user_id: str, resource: str, action: str, **extra):
    """Log failed authorization."""
    get_audit_logger().log_event(
        AuditEventType.AUTHORIZATION_FAILURE,
        user_id=user_id,
        resource=resource,
        action=action,
        status="failure",
        **extra
    )

def log_data_access(user_id: str, resource: str, action: str = "read", **extra):
    """Log data access event."""
    get_audit_logger().log_event(
        AuditEventType.DATA_ACCESS,
        user_id=user_id,
        resource=resource,
        action=action,
        **extra
    )

def log_anomaly_detected(user_id: Optional[str], anomaly_type: str, severity: str, **extra):
    """Log anomaly detection event."""
    get_audit_logger().log_event(
        AuditEventType.ANOMALY_DETECTED,
        user_id=user_id,
        resource="anomaly_detector",
        action="detect",
        details={"anomaly_type": anomaly_type, "severity": severity},
        **extra
    )

def log_recovery_action(user_id: Optional[str], action_type: str, component: str, **extra):
    """Log recovery action event."""
    get_audit_logger().log_event(
        AuditEventType.RECOVERY_ACTION,
        user_id=user_id,
        resource=component,
        action=action_type,
        **extra
    )

def log_configuration_change(user_id: str, resource: str, action: str, **extra):
    """Log configuration change event."""
    get_audit_logger().log_event(
        AuditEventType.CONFIGURATION_CHANGE,
        user_id=user_id,
        resource=resource,
        action=action,
        **extra
    )
