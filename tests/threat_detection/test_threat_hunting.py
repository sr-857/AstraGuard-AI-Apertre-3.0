"""
Tests for Threat Hunting System

Tests proactive threat hunting, IoC hunting, and hunt queries.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

from threat_detection.threat_hunter import (
    ThreatHunter, ThreatHunt, HuntResult, HuntStatus, HuntType,
    get_threat_hunter
)
from threat_detection.ioc_hunter import (
    IoCHunter, IoCMatch, IoCHuntStatus, get_ioc_hunter
)
from threat_detection.ioc_manager import (
    IoCManager, IoCRecord, IoCType, IoCSeverity, get_ioc_manager
)
from threat_detection.hunt_queries import (
    get_query, list_queries, get_queries_by_mitre, HUNT_QUERIES
)
from threat_detection.advanced_anomaly_detector import ThreatSeverity


@pytest.fixture
def threat_hunter():
    """Create a threat hunter instance."""
    return ThreatHunter()


@pytest.fixture
def ioc_hunter():
    """Create an IoC hunter instance."""
    return IoCHunter()


@pytest.fixture
def ioc_manager():
    """Create an IoC manager instance."""
    return IoCManager()


@pytest.fixture
def sample_ioc():
    """Create a sample IoC."""
    return IoCRecord(
        ioc_id="IOC-001",
        ioc_type=IoCType.IP_ADDRESS,
        value="192.168.1.100",
        severity=IoCSeverity.HIGH,
        description="Malicious IP",
        source="test",
        created_at=datetime.now(),
        expires_at=datetime.now() + timedelta(days=30)
    )


@pytest.mark.asyncio
async def test_threat_hunt_creation(threat_hunter):
    """Test threat hunt creation."""
    hunt = await threat_hunter.create_hunt(
        name="Test Hunt",
        description="Test description",
        hunt_type=HuntType.HYPOTHESIS_DRIVEN,
        query_params={"hypothesis": "lateral movement"},
        scope={"entities": ["host-001"]}
    )
    
    assert isinstance(hunt, ThreatHunt)
    assert hunt.name == "Test Hunt"
    assert hunt.hunt_type == HuntType.HYPOTHESIS_DRIVEN
    assert hunt.status == HuntStatus.PLANNED


@pytest.mark.asyncio
async def test_hunt_execution(threat_hunter):
    """Test hunt execution."""
    # Create hunt
    hunt = await threat_hunter.create_hunt(
        name="Execution Test",
        description="Test execution",
        hunt_type=HuntType.INDICATOR_DRIVEN,
        query_params={"indicators": ["192.168.1.100"]}
    )
    
    # Execute
    result = await threat_hunter.execute_hunt(hunt.hunt_id)
    
    assert result.status == HuntStatus.COMPLETED
    assert result.completed_at is not None


@pytest.mark.asyncio
async def test_ioc_hunting(ioc_hunter, ioc_manager, sample_ioc):
    """Test IoC hunting."""
    # Add IoC to manager
    ioc_manager.add_ioc(
        ioc_type=sample_ioc.ioc_type,
        value=sample_ioc.value,
        severity=sample_ioc.severity,
        description=sample_ioc.description,
        source=sample_ioc.source
    )
    
    # Hunt for IoC
    result = await ioc_hunter.hunt_ioc(sample_ioc.ioc_id)
    
    assert result is not None
    assert result.iocs_searched == 1


@pytest.mark.asyncio
async def test_ioc_match_creation():
    """Test IoC match creation."""
    match = IoCMatch(
        match_id="MATCH-001",
        ioc_id="IOC-001",
        ioc_type=IoCType.IP_ADDRESS,
        ioc_value="192.168.1.100",
        matched_value="192.168.1.100",
        match_context="network_log",
        entity_id="host-001",
        entity_type="host",
        match_time=datetime.now(),
        confidence=0.95,
        severity=IoCSeverity.HIGH
    )
    
    assert match.match_id == "MATCH-001"
    assert match.confidence == 0.95


@pytest.mark.asyncio
async def test_hunt_templates(threat_hunter):
    """Test hunt templates."""
    templates = threat_hunter.get_hunt_templates()
    
    assert len(templates) > 0
    assert "lateral_movement" in templates
    assert "persistence_mechanisms" in templates


@pytest.mark.asyncio
async def test_hunt_queries():
    """Test hunt queries."""
    # Test getting specific query
    query = get_query("lateral_movement_rdp")
    assert query is not None
    assert query.query_id == "lateral_movement_rdp"
    
    # Test listing queries
    all_queries = list_queries()
    assert len(all_queries) > 0
    
    # Test filtering by type
    network_queries = list_queries(query_type=QueryType.NETWORK)
    assert len(network_queries) > 0


@pytest.mark.asyncio
async def test_mitre_mapping():
    """Test MITRE ATT&CK technique mapping."""
    # Get queries for specific technique
    queries = get_queries_by_mitre("T1021.001")  # RDP lateral movement
    
    assert len(queries) > 0
    assert any("rdp" in q.query_id for q in queries)


@pytest.mark.asyncio
async def test_hunt_result_creation(threat_hunter):
    """Test hunt result creation."""
    result = HuntResult(
        finding_id="FIND-001",
        hunt_id="HUNT-001",
        timestamp=datetime.now(),
        title="Test Finding",
        description="Test finding description",
        severity=ThreatSeverity.HIGH,
        confidence=0.85,
        affected_entities=["host-001"],
        evidence=["log-001"],
        recommended_actions=["investigate"]
    )
    
    assert result.finding_id == "FIND-001"
    assert result.confidence == 0.85


@pytest.mark.asyncio
async def test_entity_hunting(threat_hunter):
    """Test entity-based hunting."""
    hunt = await threat_hunter.create_hunt(
        name="Entity Hunt",
        description="Hunt specific entity",
        hunt_type=HuntType.ENTITY_DRIVEN,
        query_params={
            "entities": ["user-001"],
            "patterns": ["privilege_escalation"]
        }
    )
    
    result = await threat_hunter.execute_hunt(hunt.hunt_id)
    
    assert result.status == HuntStatus.COMPLETED


@pytest.mark.asyncio
async def test_anomaly_driven_hunt(threat_hunter):
    """Test anomaly-driven hunting."""
    hunt = await threat_hunter.create_hunt(
        name="Anomaly Hunt",
        description="Find anomalies",
        hunt_type=HuntType.ANOMALY_DRIVEN,
        query_params={
            "anomaly_types": ["network_spike", "data_exfiltration"],
            "threshold": 0.8
        }
    )
    
    result = await threat_hunter.execute_hunt(hunt.hunt_id)
    
    assert result.status == HuntStatus.COMPLETED


@pytest.mark.asyncio
async def test_ioc_correlation(ioc_hunter):
    """Test IoC match correlation."""
    # Add multiple matches
    for i in range(5):
        match = IoCMatch(
            match_id=f"MATCH-{i}",
            ioc_id=f"IOC-{i}",
            ioc_type=IoCType.IP_ADDRESS,
            ioc_value=f"192.168.1.{i}",
            matched_value=f"192.168.1.{i}",
            match_context="network_log",
            entity_id="host-001",
            entity_type="host",
            match_time=datetime.now(),
            confidence=0.9,
            severity=IoCSeverity.HIGH
        )
        ioc_hunter.match_history.append(match)
    
    # Correlate
    correlations = ioc_hunter.correlate_matches(time_window=timedelta(hours=1))
    
    assert len(correlations) > 0


@pytest.mark.asyncio
async def test_hunt_statistics(threat_hunter):
    """Test hunt statistics."""
    # Create and execute hunts
    for i in range(3):
        hunt = await threat_hunter.create_hunt(
            name=f"Stat Hunt {i}",
            description="Statistics test",
            hunt_type=HuntType.HYPOTHESIS_DRIVEN,
            query_params={"hypothesis": f"test-{i}"}
        )
        await threat_hunter.execute_hunt(hunt.hunt_id)
    
    stats = threat_hunter.get_statistics()
    
    assert stats["total_hunts"] == 3
    assert stats["hunts_completed"] == 3


@pytest.mark.asyncio
async def test_global_instances():
    """Test global singleton instances."""
    hunter1 = get_threat_hunter()
    hunter2 = get_threat_hunter()
    assert hunter1 is hunter2
    
    ioc_hunter1 = get_ioc_hunter()
    ioc_hunter2 = get_ioc_hunter()
    assert ioc_hunter1 is ioc_hunter2


@pytest.mark.asyncio
async def test_hunt_status_enum():
    """Test HuntStatus enum values."""
    assert HuntStatus.PLANNED.value == "planned"
    assert HuntStatus.IN_PROGRESS.value == "in_progress"
    assert HuntStatus.COMPLETED.value == "completed"
    assert HuntStatus.CANCELLED.value == "cancelled"


@pytest.mark.asyncio
async def test_hunt_type_enum():
    """Test HuntType enum values."""
    assert HuntType.HYPOTHESIS_DRIVEN.value == "hypothesis_driven"
    assert HuntType.INDICATOR_DRIVEN.value == "indicator_driven"
    assert HuntType.ENTITY_DRIVEN.value == "entity_driven"
    assert HuntType.TTP_DRIVEN.value == "ttp_driven"
    assert HuntType.ANOMALY_DRIVEN.value == "anomaly_driven"


@pytest.mark.asyncio
async def test_ioc_hunt_status_enum():
    """Test IoCHuntStatus enum values."""
    assert IoCHuntStatus.PENDING.value == "pending"
    assert IoCHuntStatus.RUNNING.value == "running"
    assert IoCHuntStatus.COMPLETED.value == "completed"
    assert IoCHuntStatus.FAILED.value == "failed"


@pytest.mark.asyncio
async def test_query_categories():
    """Test query categorization."""
    from threat_detection.hunt_queries import get_query_categories
    
    categories = get_query_categories()
    
    assert "lateral_movement" in categories
    assert "persistence" in categories
    assert "data_exfiltration" in categories


@pytest.mark.asyncio
async def test_query_statistics():
    """Test query statistics."""
    from threat_detection.hunt_queries import get_statistics
    
    stats = get_statistics()
    
    assert stats["total_queries"] > 0
    assert "by_type" in stats
    assert "by_severity" in stats
