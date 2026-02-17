"""
Tests for Automated Response System

Tests response orchestration, playbooks, and mitigation execution.
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock

from threat_detection.automated_response import (
    AutomatedResponseSystem, ResponseResult, ResponseStatus,
    get_automated_response
)
from threat_detection.response_playbooks import (
    ResponseAction, ResponsePlaybook, get_response_playbook_manager
)
from threat_detection.mitigation_engine import (
    MitigationEngine, MitigationAction, MitigationStatus, MitigationType,
    get_mitigation_engine, register_standard_mitigations
)
from threat_detection.advanced_anomaly_detector import (
    ThreatDetection, ThreatSeverity, ThreatCategory
)


@pytest.fixture
def response_system():
    """Create an automated response system instance."""
    return AutomatedResponseSystem()


@pytest.fixture
def mitigation_engine():
    """Create a mitigation engine instance."""
    engine = MitigationEngine()
    register_standard_mitigations(engine)
    return engine


@pytest.fixture
def sample_threat():
    """Create a sample threat detection."""
    return ThreatDetection(
        detection_id="THREAT-001",
        threat_type="malware",
        category=ThreatCategory.MALWARE,
        severity=ThreatSeverity.HIGH,
        confidence=0.9,
        description="Test malware detection",
        affected_entities=["host-001"],
        source_data={},
        timestamp=datetime.now()
    )


@pytest.mark.asyncio
async def test_response_system_initialization(response_system):
    """Test response system initialization."""
    assert response_system is not None
    assert response_system.playbooks == {}
    assert response_system.response_history == []


@pytest.mark.asyncio
async def test_response_execution(response_system, sample_threat):
    """Test response execution."""
    # Register a test playbook
    playbook = ResponsePlaybook(
        playbook_id="test-playbook",
        name="Test Playbook",
        description="Test response playbook",
        threat_types=["malware"],
        severity_levels=[ThreatSeverity.HIGH],
        actions=[
            ResponseAction(
                action_id="test-action",
                name="Test Action",
                description="Test response action",
                action_type="notification",
                execute_func=AsyncMock(return_value=True),
                requires_approval=False
            )
        ]
    )
    response_system.register_playbook(playbook)
    
    # Execute response
    result = await response_system.execute_response(
        detection=sample_threat,
        auto_approve=True
    )
    
    assert isinstance(result, ResponseResult)
    assert result.status in [ResponseStatus.COMPLETED, ResponseStatus.PENDING]


@pytest.mark.asyncio
async def test_mitigation_action_registration(mitigation_engine):
    """Test mitigation action registration."""
    action = MitigationAction(
        action_id="test-mitigation",
        name="Test Mitigation",
        description="Test mitigation action",
        mitigation_type=MitigationType.CONTAINMENT,
        action_func=AsyncMock(return_value=True),
        max_duration=30
    )
    
    mitigation_engine.register_action(action)
    assert "test-mitigation" in mitigation_engine.actions


@pytest.mark.asyncio
async def test_mitigation_execution(mitigation_engine):
    """Test mitigation execution."""
    result = await mitigation_engine.execute_mitigation(
        threat_id="THREAT-001",
        action_id="block_attacker",
        context={"attacker_ip": "192.168.1.100"},
        approve=True
    )
    
    assert result is not None
    assert result.threat_id == "THREAT-001"
    assert result.action_id == "block_attacker"


@pytest.mark.asyncio
async def test_mitigation_rollback(mitigation_engine):
    """Test mitigation rollback."""
    # Execute first
    result = await mitigation_engine.execute_mitigation(
        threat_id="THREAT-001",
        action_id="isolate_network",
        context={"system_id": "host-001"},
        approve=True
    )
    
    # Rollback
    success = await mitigation_engine.rollback_mitigation(result.mitigation_id)
    
    # Should succeed since isolate_network has rollback
    assert success is True


@pytest.mark.asyncio
async def test_response_approval_workflow(response_system, sample_threat):
    """Test response approval workflow."""
    # Create action requiring approval
    action = ResponseAction(
        action_id="approval-action",
        name="Approval Action",
        description="Requires approval",
        action_type="mitigation",
        execute_func=AsyncMock(return_value=True),
        requires_approval=True
    )
    
    playbook = ResponsePlaybook(
        playbook_id="approval-playbook",
        name="Approval Playbook",
        description="Test approval",
        threat_types=["malware"],
        severity_levels=[ThreatSeverity.HIGH],
        actions=[action]
    )
    response_system.register_playbook(playbook)
    
    # Without approval - should be pending
    result_no_approval = await response_system.execute_response(
        detection=sample_threat,
        auto_approve=False
    )
    
    # With approval - should execute
    result_with_approval = await response_system.execute_response(
        detection=sample_threat,
        auto_approve=True
    )


@pytest.mark.asyncio
async def test_playbook_selection(response_system):
    """Test playbook selection based on threat."""
    # Register multiple playbooks
    playbook1 = ResponsePlaybook(
        playbook_id="malware-playbook",
        name="Malware Response",
        description="Malware response",
        threat_types=["malware"],
        severity_levels=[ThreatSeverity.HIGH, ThreatSeverity.CRITICAL],
        actions=[]
    )
    
    playbook2 = ResponsePlaybook(
        playbook_id="intrusion-playbook",
        name="Intrusion Response",
        description="Intrusion response",
        threat_types=["intrusion"],
        severity_levels=[ThreatSeverity.HIGH],
        actions=[]
    )
    
    response_system.register_playbook(playbook1)
    response_system.register_playbook(playbook2)
    
    # Test selection
    selected = response_system._select_playbooks(
        threat_type="malware",
        severity=ThreatSeverity.HIGH
    )
    
    assert len(selected) == 1
    assert selected[0].playbook_id == "malware-playbook"


@pytest.mark.asyncio
async def test_response_latency_requirement(response_system, sample_threat):
    """Test response latency is under 5s requirement."""
    # Register simple playbook
    action = ResponseAction(
        action_id="quick-action",
        name="Quick Action",
        description="Fast response",
        action_type="notification",
        execute_func=AsyncMock(return_value=True),
        requires_approval=False
    )
    
    playbook = ResponsePlaybook(
        playbook_id="quick-playbook",
        name="Quick Playbook",
        description="Fast response playbook",
        threat_types=["malware"],
        severity_levels=[ThreatSeverity.HIGH],
        actions=[action]
    )
    response_system.register_playbook(playbook)
    
    # Measure response time
    start = datetime.now()
    await response_system.execute_response(
        detection=sample_threat,
        auto_approve=True
    )
    elapsed = (datetime.now() - start).total_seconds()
    
    assert elapsed < 5.0, f"Response took {elapsed}s, exceeds 5s requirement"


@pytest.mark.asyncio
async def test_mitigation_effectiveness_tracking(mitigation_engine):
    """Test mitigation effectiveness tracking."""
    # Execute multiple mitigations
    for i in range(5):
        result = await mitigation_engine.execute_mitigation(
            threat_id=f"THREAT-{i}",
            action_id="block_attacker",
            context={"attacker_ip": f"192.168.1.{i}"},
            approve=True
        )
        
        # Update effectiveness
        mitigation_engine.update_effectiveness(
            result.mitigation_id,
            score=0.8 + (i * 0.05)
        )
    
    # Check effectiveness
    effectiveness = mitigation_engine.get_action_effectiveness("block_attacker")
    assert 0 <= effectiveness <= 1


@pytest.mark.asyncio
async def test_response_history(response_system, sample_threat):
    """Test response history tracking."""
    # Execute responses
    for i in range(3):
        await response_system.execute_response(
            detection=sample_threat,
            auto_approve=True
        )
    
    # Check history
    history = response_system.get_response_history(limit=10)
    assert len(history) == 3


@pytest.mark.asyncio
async def test_circuit_breaker_protection(response_system, sample_threat):
    """Test circuit breaker protection."""
    # Simulate failures to trigger circuit breaker
    failing_action = ResponseAction(
        action_id="failing-action",
        name="Failing Action",
        description="Always fails",
        action_type="mitigation",
        execute_func=AsyncMock(side_effect=Exception("Simulated failure")),
        requires_approval=False
    )
    
    playbook = ResponsePlaybook(
        playbook_id="failing-playbook",
        name="Failing Playbook",
        description="Always fails",
        threat_types=["malware"],
        severity_levels=[ThreatSeverity.HIGH],
        actions=[failing_action]
    )
    response_system.register_playbook(playbook)
    
    # Execute multiple times to trigger circuit breaker
    results = []
    for i in range(10):
        try:
            result = await response_system.execute_response(
                detection=sample_threat,
                auto_approve=True
            )
            results.append(result)
        except Exception:
            pass
    
    # Circuit breaker should have opened
    assert response_system.circuit_breaker.is_open is True


@pytest.mark.asyncio
async def test_global_instances():
    """Test global singleton instances."""
    system1 = get_automated_response()
    system2 = get_automated_response()
    assert system1 is system2
    
    engine1 = get_mitigation_engine()
    engine2 = get_mitigation_engine()
    assert engine1 is engine2


@pytest.mark.asyncio
async def test_response_status_enum():
    """Test ResponseStatus enum values."""
    assert ResponseStatus.PENDING.value == "pending"
    assert ResponseStatus.IN_PROGRESS.value == "in_progress"
    assert ResponseStatus.COMPLETED.value == "completed"
    assert ResponseStatus.FAILED.value == "failed"


@pytest.mark.asyncio
async def test_mitigation_status_enum():
    """Test MitigationStatus enum values."""
    assert MitigationStatus.PLANNED.value == "planned"
    assert MitigationStatus.IN_PROGRESS.value == "in_progress"
    assert MitigationStatus.SUCCESS.value == "success"
    assert MitigationStatus.FAILED.value == "failed"
    assert MitigationStatus.ROLLED_BACK.value == "rolled_back"


@pytest.mark.asyncio
async def test_mitigation_type_enum():
    """Test MitigationType enum values."""
    assert MitigationType.CONTAINMENT.value == "containment"
    assert MitigationType.ERADICATION.value == "eradication"
    assert MitigationType.RECOVERY.value == "recovery"
    assert MitigationType.PREVENTION.value == "prevention"
