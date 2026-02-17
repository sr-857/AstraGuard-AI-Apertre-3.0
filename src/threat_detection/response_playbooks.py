"""
Response Playbooks for Automated Threat Response

Defines pre-built response playbooks for common threat scenarios.
"""

from typing import Dict, List, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
import logging

from .automated_response import ResponseAction, ResponsePriority, ResponsePlaybook
from .advanced_anomaly_detector import ThreatCategory, ThreatSeverity

logger = logging.getLogger(__name__)


class PlaybookTemplate(Enum):
    """Pre-defined playbook templates."""
    MALWARE_RESPONSE = "malware_response"
    INTRUSION_RESPONSE = "intrusion_response"
    DATA_EXFILTRATION_RESPONSE = "data_exfiltration_response"
    PRIVILEGE_ESCALATION_RESPONSE = "privilege_escalation_response"
    DENIAL_OF_SERVICE_RESPONSE = "denial_of_service_response"
    LATERAL_MOVEMENT_RESPONSE = "lateral_movement_response"
    POLICY_VIOLATION_RESPONSE = "policy_violation_response"


async def action_isolate_system(context: Dict[str, Any]) -> bool:
    """Action: Isolate affected system from network."""
    try:
        detection = context.get("detection", {})
        logger.warning(f"ISOLATING SYSTEM: {detection.get('detection_id')}")
        # In production: implement actual network isolation
        # - Disable network interfaces
        # - Block at firewall
        # - Move to quarantine VLAN
        return True
    except Exception as e:
        logger.error(f"System isolation failed: {e}")
        return False


async def action_block_ip(context: Dict[str, Any]) -> bool:
    """Action: Block malicious IP address."""
    try:
        detection = context.get("detection", {})
        source_data = detection.get("source_data", {})
        ip = source_data.get("source_ip") or source_data.get("ip")
        
        if ip:
            logger.warning(f"BLOCKING IP: {ip}")
            # In production: implement actual IP blocking
            # - Add to firewall blacklist
            # - Update WAF rules
            # - Block at edge router
            return True
        return False
    except Exception as e:
        logger.error(f"IP blocking failed: {e}")
        return False


async def action_disable_account(context: Dict[str, Any]) -> bool:
    """Action: Disable compromised user account."""
    try:
        detection = context.get("detection", {})
        source_data = detection.get("source_data", {})
        user = source_data.get("user") or source_data.get("username")
        
        if user:
            logger.warning(f"DISABLING ACCOUNT: {user}")
            # In production: implement actual account disable
            # - Disable in identity provider
            # - Revoke active sessions
            # - Block authentication
            return True
        return False
    except Exception as e:
        logger.error(f"Account disable failed: {e}")
        return False


async def action_collect_forensics(context: Dict[str, Any]) -> bool:
    """Action: Collect forensic evidence."""
    try:
        detection = context.get("detection", {})
        logger.info(f"COLLECTING FORENSICS: {detection.get('detection_id')}")
        # In production: implement evidence collection
        # - Capture memory dump
        # - Collect logs
        # - Snapshot disk
        # - Preserve network traffic
        return True
    except Exception as e:
        logger.error(f"Forensics collection failed: {e}")
        return False


async def action_alert_security_team(context: Dict[str, Any]) -> bool:
    """Action: Alert security team."""
    try:
        detection = context.get("detection", {})
        logger.warning(
            f"SECURITY ALERT: Detection {detection.get('detection_id')} - "
            f"Category: {detection.get('category')}, "
            f"Severity: {detection.get('severity')}"
        )
        # In production: implement actual alerting
        # - Send to SIEM
        # - Page on-call
        # - Create incident ticket
        # - Send Slack/Teams notification
        return True
    except Exception as e:
        logger.error(f"Security alert failed: {e}")
        return False


async def action_increase_monitoring(context: Dict[str, Any]) -> bool:
    """Action: Increase monitoring on affected entity."""
    try:
        detection = context.get("detection", {})
        logger.info(f"INCREASING MONITORING: {detection.get('detection_id')}")
        # In production: implement monitoring increase
        # - Enable detailed logging
        # - Increase metric collection frequency
        # - Enable packet capture
        # - Add to watch list
        return True
    except Exception as e:
        logger.error(f"Monitoring increase failed: {e}")
        return False


async def action_terminate_process(context: Dict[str, Any]) -> bool:
    """Action: Terminate malicious process."""
    try:
        detection = context.get("detection", {})
        source_data = detection.get("source_data", {})
        pid = source_data.get("pid") or source_data.get("process_id")
        
        if pid:
            logger.warning(f"TERMINATING PROCESS: {pid}")
            # In production: implement process termination
            # - Kill process
            # - Prevent restart
            # - Block executable
            return True
        return False
    except Exception as e:
        logger.error(f"Process termination failed: {e}")
        return False


async def action_block_file_hash(context: Dict[str, Any]) -> bool:
    """Action: Block file by hash."""
    try:
        detection = context.get("detection", {})
        source_data = detection.get("source_data", {})
        file_hash = source_data.get("file_hash") or source_data.get("hash")
        
        if file_hash:
            logger.warning(f"BLOCKING FILE HASH: {file_hash}")
            # In production: implement hash blocking
            # - Add to EPP/EDR blacklist
            # - Update file integrity monitoring
            # - Quarantine matching files
            return True
        return False
    except Exception as e:
        logger.error(f"File hash blocking failed: {e}")
        return False


async def action_rate_limit(context: Dict[str, Any]) -> bool:
    """Action: Apply rate limiting."""
    try:
        detection = context.get("detection", {})
        source_data = detection.get("source_data", {})
        ip = source_data.get("source_ip")
        
        if ip:
            logger.warning(f"APPLYING RATE LIMIT: {ip}")
            # In production: implement rate limiting
            # - Configure WAF rate limits
            # - Update load balancer rules
            # - Enable DDoS protection
            return True
        return False
    except Exception as e:
        logger.error(f"Rate limiting failed: {e}")
        return False


async def action_revoke_sessions(context: Dict[str, Any]) -> bool:
    """Action: Revoke active user sessions."""
    try:
        detection = context.get("detection", {})
        source_data = detection.get("source_data", {})
        user = source_data.get("user") or source_data.get("username")
        
        if user:
            logger.warning(f"REVOKING SESSIONS: {user}")
            # In production: implement session revocation
            # - Invalidate JWT tokens
            # - Clear session cache
            # - Force re-authentication
            return True
        return False
    except Exception as e:
        logger.error(f"Session revocation failed: {e}")
        return False


# Define standard response actions
STANDARD_ACTIONS = {
    "isolate_system": ResponseAction(
        action_id="isolate_system",
        name="Isolate System",
        description="Isolate affected system from the network",
        priority=ResponsePriority.CRITICAL,
        max_execution_time=30,
        requires_approval=True,
        auto_execute_severity=[ThreatSeverity.CRITICAL],
        action_func=action_isolate_system
    ),
    
    "block_ip": ResponseAction(
        action_id="block_ip",
        name="Block IP Address",
        description="Block malicious IP address at firewall",
        priority=ResponsePriority.HIGH,
        max_execution_time=15,
        requires_approval=False,
        auto_execute_severity=[ThreatSeverity.CRITICAL, ThreatSeverity.HIGH],
        action_func=action_block_ip
    ),
    
    "disable_account": ResponseAction(
        action_id="disable_account",
        name="Disable User Account",
        description="Disable compromised user account",
        priority=ResponsePriority.CRITICAL,
        max_execution_time=10,
        requires_approval=True,
        auto_execute_severity=[ThreatSeverity.CRITICAL],
        action_func=action_disable_account
    ),
    
    "collect_forensics": ResponseAction(
        action_id="collect_forensics",
        name="Collect Forensics",
        description="Collect forensic evidence from affected system",
        priority=ResponsePriority.HIGH,
        max_execution_time=300,
        requires_approval=False,
        auto_execute_severity=[ThreatSeverity.CRITICAL, ThreatSeverity.HIGH, ThreatSeverity.MEDIUM],
        action_func=action_collect_forensics
    ),
    
    "alert_security_team": ResponseAction(
        action_id="alert_security_team",
        name="Alert Security Team",
        description="Send alert to security team",
        priority=ResponsePriority.CRITICAL,
        max_execution_time=5,
        requires_approval=False,
        auto_execute_severity=[ThreatSeverity.CRITICAL, ThreatSeverity.HIGH, ThreatSeverity.MEDIUM, ThreatSeverity.LOW],
        action_func=action_alert_security_team
    ),
    
    "increase_monitoring": ResponseAction(
        action_id="increase_monitoring",
        name="Increase Monitoring",
        description="Increase monitoring on affected entity",
        priority=ResponsePriority.MEDIUM,
        max_execution_time=10,
        requires_approval=False,
        auto_execute_severity=[ThreatSeverity.HIGH, ThreatSeverity.MEDIUM],
        action_func=action_increase_monitoring
    ),
    
    "terminate_process": ResponseAction(
        action_id="terminate_process",
        name="Terminate Process",
        description="Terminate malicious process",
        priority=ResponsePriority.HIGH,
        max_execution_time=5,
        requires_approval=True,
        auto_execute_severity=[ThreatSeverity.CRITICAL],
        action_func=action_terminate_process
    ),
    
    "block_file_hash": ResponseAction(
        action_id="block_file_hash",
        name="Block File Hash",
        description="Block file execution by hash",
        priority=ResponsePriority.HIGH,
        max_execution_time=10,
        requires_approval=False,
        auto_execute_severity=[ThreatSeverity.CRITICAL, ThreatSeverity.HIGH],
        action_func=action_block_file_hash
    ),
    
    "rate_limit": ResponseAction(
        action_id="rate_limit",
        name="Apply Rate Limit",
        description="Apply rate limiting to source",
        priority=ResponsePriority.MEDIUM,
        max_execution_time=15,
        requires_approval=False,
        auto_execute_severity=[ThreatSeverity.HIGH, ThreatSeverity.MEDIUM],
        action_func=action_rate_limit
    ),
    
    "revoke_sessions": ResponseAction(
        action_id="revoke_sessions",
        name="Revoke Sessions",
        description="Revoke active user sessions",
        priority=ResponsePriority.HIGH,
        max_execution_time=10,
        requires_approval=True,
        auto_execute_severity=[ThreatSeverity.CRITICAL, ThreatSeverity.HIGH],
        action_func=action_revoke_sessions
    )
}


# Define standard playbooks
STANDARD_PLAYBOOKS = {
    PlaybookTemplate.MALWARE_RESPONSE: ResponsePlaybook(
        playbook_id="malware_response",
        name="Malware Response",
        description="Response playbook for malware detection",
        threat_categories=[ThreatCategory.MALWARE],
        severity_levels=[ThreatSeverity.CRITICAL, ThreatSeverity.HIGH, ThreatSeverity.MEDIUM],
        actions=[
            "alert_security_team",
            "isolate_system",
            "terminate_process",
            "block_file_hash",
            "collect_forensics"
        ],
        execution_mode="sequential"
    ),
    
    PlaybookTemplate.INTRUSION_RESPONSE: ResponsePlaybook(
        playbook_id="intrusion_response",
        name="Intrusion Response",
        description="Response playbook for intrusion detection",
        threat_categories=[ThreatCategory.INTRUSION],
        severity_levels=[ThreatSeverity.CRITICAL, ThreatSeverity.HIGH],
        actions=[
            "alert_security_team",
            "block_ip",
            "disable_account",
            "revoke_sessions",
            "collect_forensics",
            "increase_monitoring"
        ],
        execution_mode="sequential"
    ),
    
    PlaybookTemplate.DATA_EXFILTRATION_RESPONSE: ResponsePlaybook(
        playbook_id="data_exfiltration_response",
        name="Data Exfiltration Response",
        description="Response playbook for data exfiltration detection",
        threat_categories=[ThreatCategory.DATA_EXFILTRATION],
        severity_levels=[ThreatSeverity.CRITICAL, ThreatSeverity.HIGH],
        actions=[
            "alert_security_team",
            "isolate_system",
            "block_ip",
            "disable_account",
            "revoke_sessions",
            "collect_forensics"
        ],
        execution_mode="sequential"
    ),
    
    PlaybookTemplate.PRIVILEGE_ESCALATION_RESPONSE: ResponsePlaybook(
        playbook_id="privilege_escalation_response",
        name="Privilege Escalation Response",
        description="Response playbook for privilege escalation detection",
        threat_categories=[ThreatCategory.PRIVILEGE_ESCALATION],
        severity_levels=[ThreatSeverity.CRITICAL, ThreatSeverity.HIGH],
        actions=[
            "alert_security_team",
            "disable_account",
            "revoke_sessions",
            "terminate_process",
            "collect_forensics"
        ],
        execution_mode="sequential"
    ),
    
    PlaybookTemplate.DENIAL_OF_SERVICE_RESPONSE: ResponsePlaybook(
        playbook_id="denial_of_service_response",
        name="Denial of Service Response",
        description="Response playbook for DoS/DDoS detection",
        threat_categories=[ThreatCategory.DENIAL_OF_SERVICE],
        severity_levels=[ThreatSeverity.CRITICAL, ThreatSeverity.HIGH, ThreatSeverity.MEDIUM],
        actions=[
            "alert_security_team",
            "rate_limit",
            "block_ip",
            "increase_monitoring"
        ],
        execution_mode="parallel"
    ),
    
    PlaybookTemplate.LATERAL_MOVEMENT_RESPONSE: ResponsePlaybook(
        playbook_id="lateral_movement_response",
        name="Lateral Movement Response",
        description="Response playbook for lateral movement detection",
        threat_categories=[ThreatCategory.LATERAL_MOVEMENT],
        severity_levels=[ThreatSeverity.CRITICAL, ThreatSeverity.HIGH],
        actions=[
            "alert_security_team",
            "isolate_system",
            "block_ip",
            "disable_account",
            "collect_forensics"
        ],
        execution_mode="sequential"
    ),
    
    PlaybookTemplate.POLICY_VIOLATION_RESPONSE: ResponsePlaybook(
        playbook_id="policy_violation_response",
        name="Policy Violation Response",
        description="Response playbook for policy violation detection",
        threat_categories=[ThreatCategory.POLICY_VIOLATION],
        severity_levels=[ThreatSeverity.HIGH, ThreatSeverity.MEDIUM, ThreatSeverity.LOW],
        actions=[
            "alert_security_team",
            "increase_monitoring"
        ],
        execution_mode="sequential"
    )
}


def register_standard_playbooks(response_system):
    """Register all standard actions and playbooks with the response system."""
    # Register actions
    for action in STANDARD_ACTIONS.values():
        response_system.register_action(action)
        logger.info(f"Registered action: {action.action_id}")
    
    # Register playbooks
    for playbook in STANDARD_PLAYBOOKS.values():
        response_system.register_playbook(playbook)
        logger.info(f"Registered playbook: {playbook.playbook_id}")
    
    logger.info("All standard playbooks registered successfully")


def get_playbook_template(template: PlaybookTemplate) -> Optional[ResponsePlaybook]:
    """Get a standard playbook template."""
    return STANDARD_PLAYBOOKS.get(template)


def list_available_playbooks() -> List[Dict[str, Any]]:
    """List all available playbook templates."""
    return [
        {
            "id": pb.playbook_id,
            "name": pb.name,
            "description": pb.description,
            "categories": [cat.value for cat in pb.threat_categories],
            "severity_levels": [sev.value for sev in pb.severity_levels],
            "actions": pb.actions
        }
        for pb in STANDARD_PLAYBOOKS.values()
    ]
