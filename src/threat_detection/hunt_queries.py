"""
Hunt Queries for Threat Hunting

Pre-built queries for common threat hunting scenarios.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class QueryType(Enum):
    """Types of hunt queries."""
    LOG_ANALYSIS = "log_analysis"
    BEHAVIORAL = "behavioral"
    NETWORK = "network"
    ENDPOINT = "endpoint"
    IDENTITY = "identity"
    CLOUD = "cloud"


class QuerySeverity(Enum):
    """Severity levels for queries."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class HuntQuery:
    """Definition of a hunt query."""
    query_id: str
    name: str
    description: str
    query_type: QueryType
    severity: QuerySeverity
    query_template: str
    parameters: Dict[str, Any]
    expected_results: str
    false_positive_rate: float
    mitre_techniques: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "query_id": self.query_id,
            "name": self.name,
            "description": self.description,
            "query_type": self.query_type.value,
            "severity": self.severity.value,
            "query_template": self.query_template,
            "parameters": self.parameters,
            "expected_results": self.expected_results,
            "false_positive_rate": self.false_positive_rate,
            "mitre_techniques": self.mitre_techniques
        }


# Pre-built hunt queries
HUNT_QUERIES = {
    # Lateral Movement Detection
    "lateral_movement_rdp": HuntQuery(
        query_id="lateral_movement_rdp",
        name="RDP Lateral Movement",
        description="Detect RDP connections between internal systems",
        query_type=QueryType.NETWORK,
        severity=QuerySeverity.HIGH,
        query_template="""
        SELECT source_ip, destination_ip, timestamp, username
        FROM network_logs
        WHERE destination_port = 3389
          AND source_ip IN (SELECT ip FROM internal_hosts)
          AND destination_ip IN (SELECT ip FROM internal_hosts)
          AND timestamp > {start_time}
        ORDER BY timestamp DESC
        """,
        parameters={
            "start_time": "24h ago",
            "internal_networks": ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]
        },
        expected_results="RDP sessions between internal hosts",
        false_positive_rate=0.05,
        mitre_techniques=["T1021.001"]
    ),
    
    "lateral_movement_smb": HuntQuery(
        query_id="lateral_movement_smb",
        name="SMB Lateral Movement",
        description="Detect SMB file shares and admin$ access",
        query_type=QueryType.NETWORK,
        severity=QuerySeverity.HIGH,
        query_template="""
        SELECT source_ip, destination_ip, share_name, operation
        FROM smb_logs
        WHERE (share_name LIKE '%admin$%' OR share_name LIKE '%c$%')
          AND timestamp > {start_time}
        ORDER BY timestamp DESC
        """,
        parameters={
            "start_time": "24h ago"
        },
        expected_results="Admin share access from remote systems",
        false_positive_rate=0.10,
        mitre_techniques=["T1021.002"]
    ),
    
    "lateral_movement_ssh": HuntQuery(
        query_id="lateral_movement_ssh",
        name="SSH Lateral Movement",
        description="Detect SSH connections between internal servers",
        query_type=QueryType.NETWORK,
        severity=QuerySeverity.MEDIUM,
        query_template="""
        SELECT source_ip, destination_ip, username, auth_method
        FROM ssh_logs
        WHERE destination_port = 22
          AND source_ip IN (SELECT ip FROM internal_servers)
          AND destination_ip IN (SELECT ip FROM internal_servers)
          AND timestamp > {start_time}
        ORDER BY timestamp DESC
        """,
        parameters={
            "start_time": "24h ago"
        },
        expected_results="SSH sessions between internal servers",
        false_positive_rate=0.15,
        mitre_techniques=["T1021.004"]
    ),
    
    # Persistence Mechanisms
    "persistence_registry": HuntQuery(
        query_id="persistence_registry",
        name="Registry Persistence",
        description="Detect registry modifications for persistence",
        query_type=QueryType.ENDPOINT,
        severity=QuerySeverity.HIGH,
        query_template="""
        SELECT system_id, registry_key, value_name, value_data
        FROM registry_changes
        WHERE registry_key IN (
            'HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run',
            'HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows\\CurrentVersion\\Run',
            'HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\RunOnce'
        )
        AND timestamp > {start_time}
        ORDER BY timestamp DESC
        """,
        parameters={
            "start_time": "7d ago"
        },
        expected_results="New registry run keys",
        false_positive_rate=0.20,
        mitre_techniques=["T1547.001"]
    ),
    
    "persistence_scheduled_task": HuntQuery(
        query_id="persistence_scheduled_task",
        name="Scheduled Task Persistence",
        description="Detect new scheduled tasks",
        query_type=QueryType.ENDPOINT,
        severity=QuerySeverity.MEDIUM,
        query_template="""
        SELECT system_id, task_name, task_path, author, action
        FROM scheduled_tasks
        WHERE created_time > {start_time}
          AND (action LIKE '%powershell%' OR action LIKE '%cmd%' OR action LIKE '%wscript%')
        ORDER BY created_time DESC
        """,
        parameters={
            "start_time": "7d ago"
        },
        expected_results="New scheduled tasks with script execution",
        false_positive_rate=0.25,
        mitre_techniques=["T1053.005"]
    ),
    
    "persistence_service": HuntQuery(
        query_id="persistence_service",
        name="New Service Installation",
        description="Detect new Windows services",
        query_type=QueryType.ENDPOINT,
        severity=QuerySeverity.HIGH,
        query_template="""
        SELECT system_id, service_name, display_name, binary_path, start_type
        FROM service_installs
        WHERE install_time > {start_time}
          AND (binary_path LIKE '%temp%' OR binary_path LIKE '%appdata%')
        ORDER BY install_time DESC
        """,
        parameters={
            "start_time": "7d ago"
        },
        expected_results="Services installed from temp directories",
        false_positive_rate=0.10,
        mitre_techniques=["T1543.003"]
    ),
    
    # Data Exfiltration
    "data_exfiltration_large_transfer": HuntQuery(
        query_id="data_exfiltration_large_transfer",
        name="Large Data Transfers",
        description="Detect unusually large outbound data transfers",
        query_type=QueryType.NETWORK,
        severity=QuerySeverity.HIGH,
        query_template="""
        SELECT source_ip, destination_ip, destination_port, 
               SUM(bytes_out) as total_bytes, COUNT(*) as connection_count
        FROM network_flows
        WHERE direction = 'outbound'
          AND destination_ip NOT IN (SELECT ip FROM internal_networks)
          AND timestamp > {start_time}
        GROUP BY source_ip, destination_ip, destination_port
        HAVING total_bytes > {threshold_bytes}
        ORDER BY total_bytes DESC
        """,
        parameters={
            "start_time": "24h ago",
            "threshold_bytes": 1073741824  # 1GB
        },
        expected_results="Large outbound data transfers",
        false_positive_rate=0.15,
        mitre_techniques=["T1041", "T1048"]
    ),
    
    "data_exfiltration_dns_tunnel": HuntQuery(
        query_id="data_exfiltration_dns_tunnel",
        name="DNS Tunneling Detection",
        description="Detect potential DNS tunneling activity",
        query_type=QueryType.NETWORK,
        severity=QuerySeverity.HIGH,
        query_template="""
        SELECT source_ip, dns_query, query_length, query_count
        FROM dns_logs
        WHERE query_length > {min_query_length}
          AND timestamp > {start_time}
        GROUP BY source_ip, dns_query
        HAVING query_count > {min_query_count}
        ORDER BY query_count DESC
        """,
        parameters={
            "start_time": "24h ago",
            "min_query_length": 50,
            "min_query_count": 100
        },
        expected_results="Long DNS queries with high frequency",
        false_positive_rate=0.20,
        mitre_techniques=["T1071.004"]
    ),
    
    # Privilege Escalation
    "privesc_sudo_abuse": HuntQuery(
        query_id="privesc_sudo_abuse",
        name="Sudo Privilege Escalation",
        description="Detect suspicious sudo usage",
        query_type=QueryType.IDENTITY,
        severity=QuerySeverity.HIGH,
        query_template="""
        SELECT username, command, timestamp, success
        FROM sudo_logs
        WHERE command NOT IN (
            '/bin/su', '/usr/bin/sudo', '/bin/bash'
        )
        AND timestamp > {start_time}
        ORDER BY timestamp DESC
        """,
        parameters={
            "start_time": "24h ago"
        },
        expected_results="Unusual sudo command execution",
        false_positive_rate=0.10,
        mitre_techniques=["T1548.003"]
    ),
    
    "privesc_token_impersonation": HuntQuery(
        query_id="privesc_token_impersonation",
        name="Token Impersonation",
        description="Detect token impersonation attempts",
        query_type=QueryType.ENDPOINT,
        severity=QuerySeverity.CRITICAL,
        query_template="""
        SELECT system_id, process_name, target_user, impersonation_level
        FROM token_events
        WHERE impersonation_level IN ('Impersonation', 'Delegation')
          AND process_name NOT IN ('lsass.exe', 'svchost.exe', 'services.exe')
          AND timestamp > {start_time}
        ORDER BY timestamp DESC
        """,
        parameters={
            "start_time": "24h ago"
        },
        expected_results="Token impersonation by non-system processes",
        false_positive_rate=0.05,
        mitre_techniques=["T1134.001"]
    ),
    
    # Credential Access
    "credential_access_brute_force": HuntQuery(
        query_id="credential_access_brute_force",
        name="Brute Force Authentication",
        description="Detect brute force authentication attempts",
        query_type=QueryType.IDENTITY,
        severity=QuerySeverity.HIGH,
        query_template="""
        SELECT source_ip, username, COUNT(*) as attempt_count
        FROM authentication_logs
        WHERE result = 'failure'
          AND timestamp > {start_time}
        GROUP BY source_ip, username
        HAVING attempt_count > {threshold}
        ORDER BY attempt_count DESC
        """,
        parameters={
            "start_time": "1h ago",
            "threshold": 10
        },
        expected_results="Multiple failed authentication attempts",
        false_positive_rate=0.10,
        mitre_techniques=["T1110.001"]
    ),
    
    "credential_access_kerberoasting": HuntQuery(
        query_id="credential_access_kerberoasting",
        name="Kerberoasting Detection",
        description="Detect Kerberoasting activity",
        query_type=QueryType.IDENTITY,
        severity=QuerySeverity.HIGH,
        query_template="""
        SELECT username, service_name, ticket_type, encryption_type
        FROM kerberos_logs
        WHERE ticket_type = 'TGS'
          AND encryption_type = 'RC4-HMAC'
          AND timestamp > {start_time}
        ORDER BY timestamp DESC
        """,
        parameters={
            "start_time": "24h ago"
        },
        expected_results="RC4 encrypted TGS tickets (susceptible to cracking)",
        false_positive_rate=0.15,
        mitre_techniques=["T1558.003"]
    ),
    
    # Defense Evasion
    "defense_evasion_process_injection": HuntQuery(
        query_id="defense_evasion_process_injection",
        name="Process Injection",
        description="Detect process injection techniques",
        query_type=QueryType.ENDPOINT,
        severity=QuerySeverity.CRITICAL,
        query_template="""
        SELECT source_process, target_process, technique, timestamp
        FROM process_injection_events
        WHERE technique IN ('CreateRemoteThread', 'ProcessHollowing', 'APCInjection')
          AND timestamp > {start_time}
        ORDER BY timestamp DESC
        """,
        parameters={
            "start_time": "24h ago"
        },
        expected_results="Process injection events",
        false_positive_rate=0.05,
        mitre_techniques=["T1055"]
    ),
    
    "defense_evasion_log_clearing": HuntQuery(
        query_id="defense_evasion_log_clearing",
        name="Log Clearing Activity",
        description="Detect security log clearing",
        query_type=QueryType.ENDPOINT,
        severity=QuerySeverity.HIGH,
        query_template="""
        SELECT system_id, user, event_id, log_type
        FROM system_events
        WHERE event_id IN (1102, 104)  # Security log cleared, System log cleared
          AND timestamp > {start_time}
        ORDER BY timestamp DESC
        """,
        parameters={
            "start_time": "7d ago"
        },
        expected_results="Security or system log clearing events",
        false_positive_rate=0.05,
        mitre_techniques=["T1070.001"]
    ),
    
    # Command and Control
    "c2_beaconing_detection": HuntQuery(
        query_id="c2_beaconing_detection",
        name="C2 Beaconing Detection",
        description="Detect potential C2 beaconing patterns",
        query_type=QueryType.NETWORK,
        severity=QuerySeverity.HIGH,
        query_template="""
        SELECT source_ip, destination_ip, destination_port,
               COUNT(*) as connection_count,
               AVG(interval) as avg_interval,
               STDDEV(interval) as stddev_interval
        FROM network_connections
        WHERE timestamp > {start_time}
        GROUP BY source_ip, destination_ip, destination_port
        HAVING connection_count > {min_connections}
           AND stddev_interval < {max_stddev}
        ORDER BY connection_count DESC
        """,
        parameters={
            "start_time": "24h ago",
            "min_connections": 50,
            "max_stddev": 60  # seconds
        },
        expected_results="Regular connection patterns (potential beaconing)",
        false_positive_rate=0.20,
        mitre_techniques=["T1071"]
    ),
    
    # Initial Access
    "initial_access_phishing": HuntQuery(
        query_id="initial_access_phishing",
        name="Phishing Detection",
        description="Detect potential phishing email indicators",
        query_type=QueryType.LOG_ANALYSIS,
        severity=QuerySeverity.HIGH,
        query_template="""
        SELECT sender, subject, attachment_name, recipient_count
        FROM email_logs
        WHERE (subject LIKE '%urgent%' OR subject LIKE '%invoice%' OR subject LIKE '%payment%')
          AND attachment_name IS NOT NULL
          AND timestamp > {start_time}
        ORDER BY recipient_count DESC
        """,
        parameters={
            "start_time": "24h ago"
        },
        expected_results="Suspicious emails with attachments",
        false_positive_rate=0.30,
        mitre_techniques=["T1566.001"]
    ),
    
    "initial_access_external_remote_services": HuntQuery(
        query_id="initial_access_external_remote_services",
        name="External Remote Services",
        description="Detect external remote access connections",
        query_type=QueryType.NETWORK,
        severity=QuerySeverity.MEDIUM,
        query_template="""
        SELECT source_ip, destination_ip, destination_port, service_type
        FROM network_connections
        WHERE source_ip NOT IN (SELECT ip FROM internal_networks)
          AND destination_port IN (3389, 22, 5900, 5985, 5986)
          AND timestamp > {start_time}
        ORDER BY timestamp DESC
        """,
        parameters={
            "start_time": "24h ago"
        },
        expected_results="External connections to remote services",
        false_positive_rate=0.25,
        mitre_techniques=["T1133"]
    ),
    
    # Impact
    "impact_ransomware_indicators": HuntQuery(
        query_id="impact_ransomware_indicators",
        name="Ransomware Indicators",
        description="Detect potential ransomware activity",
        query_type=QueryType.ENDPOINT,
        severity=QuerySeverity.CRITICAL,
        query_template="""
        SELECT system_id, process_name, file_operation, file_extension, count(*)
        FROM file_events
        WHERE file_operation = 'modified'
          AND file_extension IN ('.encrypted', '.locked', '.crypto', '. ransom')
          AND timestamp > {start_time}
        GROUP BY system_id, process_name, file_operation, file_extension
        HAVING count(*) > {threshold}
        ORDER BY count(*) DESC
        """,
        parameters={
            "start_time": "4h ago",
            "threshold": 100
        },
        expected_results="Mass file modifications with suspicious extensions",
        false_positive_rate=0.05,
        mitre_techniques=["T1486"]
    ),
    
    "impact_data_destruction": HuntQuery(
        query_id="impact_data_destruction",
        name="Data Destruction",
        description="Detect data destruction attempts",
        query_type=QueryType.ENDPOINT,
        severity=QuerySeverity.CRITICAL,
        query_template="""
        SELECT system_id, process_name, command_line, deleted_count
        FROM process_events
        WHERE (command_line LIKE '%del%' OR command_line LIKE '%rm%' OR command_line LIKE '%shred%')
          AND deleted_count > {threshold}
          AND timestamp > {start_time}
        ORDER BY deleted_count DESC
        """,
        parameters={
            "start_time": "4h ago",
            "threshold": 1000
        },
        expected_results="Mass file deletion commands",
        false_positive_rate=0.10,
        mitre_techniques=["T1485"]
    )
}


def get_query(query_id: str) -> Optional[HuntQuery]:
    """Get a hunt query by ID."""
    return HUNT_QUERIES.get(query_id)


def list_queries(query_type: Optional[QueryType] = None,
                severity: Optional[QuerySeverity] = None) -> List[HuntQuery]:
    """List hunt queries with optional filtering."""
    queries = list(HUNT_QUERIES.values())
    
    if query_type:
        queries = [q for q in queries if q.query_type == query_type]
    
    if severity:
        queries = [q for q in queries if q.severity == severity]
    
    return queries


def get_queries_by_mitre(technique_id: str) -> List[HuntQuery]:
    """Get queries mapped to a specific MITRE ATT&CK technique."""
    return [
        q for q in HUNT_QUERIES.values()
        if technique_id in q.mitre_techniques
    ]


def get_query_categories() -> Dict[str, List[str]]:
    """Get queries organized by category."""
    categories = {
        "lateral_movement": [],
        "persistence": [],
        "data_exfiltration": [],
        "privilege_escalation": [],
        "credential_access": [],
        "defense_evasion": [],
        "command_and_control": [],
        "initial_access": [],
        "impact": []
    }
    
    for query_id, query in HUNT_QUERIES.items():
        if "lateral_movement" in query_id:
            categories["lateral_movement"].append(query_id)
        elif "persistence" in query_id:
            categories["persistence"].append(query_id)
        elif "data_exfiltration" in query_id:
            categories["data_exfiltration"].append(query_id)
        elif "privesc" in query_id:
            categories["privilege_escalation"].append(query_id)
        elif "credential" in query_id:
            categories["credential_access"].append(query_id)
        elif "defense_evasion" in query_id:
            categories["defense_evasion"].append(query_id)
        elif "c2" in query_id:
            categories["command_and_control"].append(query_id)
        elif "initial_access" in query_id:
            categories["initial_access"].append(query_id)
        elif "impact" in query_id:
            categories["impact"].append(query_id)
    
    return categories


def get_statistics() -> Dict[str, Any]:
    """Get query statistics."""
    by_type = {}
    by_severity = {}
    
    for query in HUNT_QUERIES.values():
        qtype = query.query_type.value
        severity = query.severity.value
        
        by_type[qtype] = by_type.get(qtype, 0) + 1
        by_severity[severity] = by_severity.get(severity, 0) + 1
    
    return {
        "total_queries": len(HUNT_QUERIES),
        "by_type": by_type,
        "by_severity": by_severity,
        "categories": len(get_query_categories())
    }
