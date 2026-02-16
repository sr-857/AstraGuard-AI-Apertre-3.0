

"""
Unit tests for phase_aware_handler.py

This test suite ensures high reliability of the PhaseAwareAnomalyHandler
and DecisionTracer classes with comprehensive coverage of:
- Anomaly handling logic
- Phase-aware policy evaluation
- Recurrence tracking
- Escalation mechanisms
- Decision logging and tracing
"""

import pytest
import logging
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from pathlib import Path
import json
from dataclasses import asdict

from anomaly_agent.phase_aware_handler import (
    PhaseAwareAnomalyHandler,
    DecisionTracer
)
from state_machine.state_engine import MissionPhase
from state_machine.mission_phase_policy_engine import (
    PolicyDecision,
    EscalationLevel
)


_ESCALATE_LEVEL = EscalationLevel.ESCALATE_SAFE_MODE.value

def _non_escalating_level() -> str:
    """Return the value of the first EscalationLevel member that is not ESCALATE_SAFE_MODE."""
    for member in EscalationLevel:
        if member is not EscalationLevel.ESCALATE_SAFE_MODE:
            return member.value
    return "NO_ACTION"

_NORMAL_LEVEL = _non_escalating_level()



@pytest.fixture
def mock_state_machine():
    state_machine = Mock()
    state_machine.get_current_phase.return_value = MissionPhase.NOMINAL_OPS
    state_machine.force_safe_mode.return_value = {
        'success': True,
        'message': 'Transitioned to SAFE_MODE'
    }
    return state_machine


@pytest.fixture
def mock_policy_loader():
    loader = Mock()
    loader.get_policy.return_value = {
        'phases': {
            'NOMINAL_OPS': {
                'allowed_actions': ['log', 'warn', 'escalate'],
                'threshold_multiplier': 1.0
            },
            'SAFE_MODE': {
                'allowed_actions': ['log'],
                'threshold_multiplier': 0.5
            }
        }
    }
    return loader


@pytest.fixture
def mock_policy_engine():
    engine = Mock()

    default_decision = Mock()
    default_decision.escalation_level = _NORMAL_LEVEL
    default_decision.recommended_action = 'log'
    default_decision.severity = 'MEDIUM'
    default_decision.reasoning = 'Normal operational parameters'

    engine.evaluate.return_value = default_decision
    engine.get_phase_constraints.return_value = {
        'allowed_actions': ['log', 'warn', 'escalate'],
        'forbidden_actions': [],
        'threshold_multiplier': 1.0
    }

    return engine


@pytest.fixture
def handler(mock_state_machine, mock_policy_loader):
    with patch('anomaly_agent.phase_aware_handler.MissionPhasePolicyEngine'):
        h = PhaseAwareAnomalyHandler(
            state_machine=mock_state_machine,
            policy_loader=mock_policy_loader,
            enable_recurrence_tracking=True
        )
    return h


@pytest.fixture
def handler_with_mock_engine(mock_state_machine, mock_policy_loader, mock_policy_engine, request):
    with patch('anomaly_agent.phase_aware_handler.MissionPhasePolicyEngine'):
        h = PhaseAwareAnomalyHandler(
            state_machine=mock_state_machine,
            policy_loader=mock_policy_loader,
            enable_recurrence_tracking=True
        )
    h.policy_engine = mock_policy_engine
    p = patch(
        'anomaly_agent.phase_aware_handler.asdict',
        side_effect=lambda obj: {
            k: v for k, v in vars(obj).items() if not k.startswith('_')
        } if not hasattr(obj, '__dataclass_fields__') else asdict(obj)
    )
    p.start()
    request.addfinalizer(p.stop)
    return h


@pytest.fixture
def decision_tracer():
    return DecisionTracer(max_decisions=100)


class TestPhaseAwareAnomalyHandlerInitialization:

    def test_init_with_all_parameters(self, mock_state_machine, mock_policy_loader):
        with patch('anomaly_agent.phase_aware_handler.MissionPhasePolicyEngine'):
            handler = PhaseAwareAnomalyHandler(
                state_machine=mock_state_machine,
                policy_loader=mock_policy_loader,
                enable_recurrence_tracking=True
            )

        assert handler.state_machine == mock_state_machine
        assert handler.policy_loader == mock_policy_loader
        assert handler.enable_recurrence_tracking is True
        assert handler.anomaly_history == []
        assert handler.recurrence_window == timedelta(seconds=3600)

    def test_init_without_policy_loader(self, mock_state_machine):
        with patch('anomaly_agent.phase_aware_handler.MissionPhasePolicyLoader') as mock_loader_class:
            with patch('anomaly_agent.phase_aware_handler.MissionPhasePolicyEngine'):
                PhaseAwareAnomalyHandler(
                    state_machine=mock_state_machine,
                    policy_loader=None
                )
            mock_loader_class.assert_called_once()

    def test_init_recurrence_tracking_disabled(self, mock_state_machine, mock_policy_loader):
        with patch('anomaly_agent.phase_aware_handler.MissionPhasePolicyEngine'):
            handler = PhaseAwareAnomalyHandler(
                state_machine=mock_state_machine,
                policy_loader=mock_policy_loader,
                enable_recurrence_tracking=False
            )

        assert handler.enable_recurrence_tracking is False


class TestHandleAnomaly:

    def test_handle_anomaly_basic_flow(self, handler_with_mock_engine, mock_state_machine):
        result = handler_with_mock_engine.handle_anomaly(
            anomaly_type='power_fault',
            severity_score=0.7,
            confidence=0.9,
            anomaly_metadata={'component': 'battery'}
        )

        assert result['success'] is True
        assert result['anomaly_type'] == 'power_fault'
        assert result['severity_score'] == 0.7
        assert result['detection_confidence'] == 0.9
        assert result['mission_phase'] == MissionPhase.NOMINAL_OPS.value
        assert 'decision_id' in result
        assert 'timestamp' in result
        assert 'policy_decision' in result
        assert 'recurrence_info' in result
        assert 'explanation' in result

        mock_state_machine.get_current_phase.assert_called_once()

    def test_handle_anomaly_with_escalation(self, handler_with_mock_engine, mock_state_machine):
        escalation_decision = Mock()
        escalation_decision.escalation_level = _ESCALATE_LEVEL
        escalation_decision.recommended_action = 'escalate'
        escalation_decision.severity = 'CRITICAL'
        escalation_decision.reasoning = 'Critical system failure'
        escalation_decision.mission_phase = 'NOMINAL_OPS' 
        handler_with_mock_engine.policy_engine.evaluate.return_value = escalation_decision

        result = handler_with_mock_engine.handle_anomaly(
            anomaly_type='thermal_critical',
            severity_score=0.95,
            confidence=0.98
        )

        assert result['should_escalate_to_safe_mode'] is True
        mock_state_machine.force_safe_mode.assert_called_once()

    def test_handle_anomaly_without_escalation(self, handler_with_mock_engine, mock_state_machine):
        result = handler_with_mock_engine.handle_anomaly(
            anomaly_type='minor_glitch',
            severity_score=0.3,
            confidence=0.85
        )

        assert result['should_escalate_to_safe_mode'] is False
        mock_state_machine.force_safe_mode.assert_not_called()

    def test_handle_anomaly_without_metadata(self, handler_with_mock_engine):
        result = handler_with_mock_engine.handle_anomaly(
            anomaly_type='test_fault',
            severity_score=0.5,
            confidence=0.8,
            anomaly_metadata=None
        )

        assert result['success'] is True
        assert result['anomaly_type'] == 'test_fault'

    def test_handle_anomaly_updates_recurrence(self, handler_with_mock_engine):
        for _ in range(3):
            result = handler_with_mock_engine.handle_anomaly(
                anomaly_type='repeated_fault',
                severity_score=0.6,
                confidence=0.8
            )

        assert result['recurrence_info']['count'] == 3
        assert result['recurrence_info']['total_in_window'] == 3

    @patch('anomaly_agent.phase_aware_handler.ANOMALIES_BY_TYPE')
    def test_handle_anomaly_updates_metrics(self, mock_metrics, handler_with_mock_engine):
        mock_labels = Mock()
        mock_metrics.labels.return_value = mock_labels

        handler_with_mock_engine.handle_anomaly(
            anomaly_type='sensor_error',
            severity_score=0.6,
            confidence=0.85
        )

        mock_metrics.labels.assert_called_once()
        mock_labels.inc.assert_called_once()

    @patch('anomaly_agent.phase_aware_handler.ANOMALIES_BY_TYPE')
    def test_handle_anomaly_metrics_failure_is_logged(
        self, mock_metrics, handler_with_mock_engine, caplog
    ):
        mock_metrics.labels.side_effect = Exception("Metrics service down")

        result = handler_with_mock_engine.handle_anomaly(
            anomaly_type='test_fault',
            severity_score=0.5,
            confidence=0.8
        )

        assert result['success'] is True
        assert "Failed to update metrics" in caplog.text

    @patch('anomaly_agent.phase_aware_handler.build_explanation')
    def test_handle_anomaly_builds_explanation(
        self, mock_build_explanation, handler_with_mock_engine
    ):
        mock_build_explanation.return_value = "Detailed explanation"

        result = handler_with_mock_engine.handle_anomaly(
            anomaly_type='test_fault',
            severity_score=0.6,
            confidence=0.85
        )

        mock_build_explanation.assert_called_once()
        call_args = mock_build_explanation.call_args[0][0]
        assert 'primary_factor' in call_args
        assert 'secondary_factors' in call_args
        assert 'mission_phase' in call_args
        assert 'confidence' in call_args
        assert result['explanation'] == "Detailed explanation"


class TestRecurrenceTracking:

    def test_recurrence_tracking_first_occurrence(self, handler):
        recurrence_info = handler._update_recurrence_tracking('new_fault')

        assert recurrence_info['count'] == 1
        assert recurrence_info['total_in_window'] == 1
        assert recurrence_info['last_occurrence'] is None
        assert recurrence_info['time_since_last_seconds'] is None

    def test_recurrence_tracking_multiple_occurrences(self, handler):
        handler._update_recurrence_tracking('repeated_fault')
        recurrence_info = handler._update_recurrence_tracking('repeated_fault')

        assert recurrence_info['count'] == 2
        assert recurrence_info['total_in_window'] == 2
        assert recurrence_info['last_occurrence'] is not None
        assert recurrence_info['time_since_last_seconds'] is not None
        assert recurrence_info['time_since_last_seconds'] >= 0

    def test_recurrence_tracking_different_types(self, handler):
        handler._update_recurrence_tracking('fault_a')
        handler._update_recurrence_tracking('fault_b')
        handler._update_recurrence_tracking('fault_a')

        recurrence_info_a = handler._update_recurrence_tracking('fault_a')
        assert recurrence_info_a['count'] == 3

        recurrence_info_b = handler._update_recurrence_tracking('fault_b')
        assert recurrence_info_b['count'] == 2

    def test_recurrence_tracking_time_window(self, handler):
        handler.recurrence_window = timedelta(seconds=1)

        old_time = datetime.now() - timedelta(seconds=2)
        handler.anomaly_history.append(('old_fault', old_time))

        recurrence_info = handler._update_recurrence_tracking('old_fault')

        assert recurrence_info['count'] == 2
        assert recurrence_info['total_in_window'] == 1

    def test_recurrence_tracking_cleanup(self, handler):
        old_time = datetime.now() - timedelta(hours=25)
        for i in range(1100):
            handler.anomaly_history.append((f'fault_{i}', old_time))

        handler._update_recurrence_tracking('new_fault')

        assert len(handler.anomaly_history) <= 1000

    def test_recurrence_tracking_disabled(self, mock_state_machine, mock_policy_loader):
        with patch('anomaly_agent.phase_aware_handler.MissionPhasePolicyEngine'):
            h = PhaseAwareAnomalyHandler(
                state_machine=mock_state_machine,
                policy_loader=mock_policy_loader,
                enable_recurrence_tracking=False
            )

        recurrence_info = h._update_recurrence_tracking('test_fault')
        assert recurrence_info is not None


class TestEscalation:

    def test_execute_escalation_success(self, handler, mock_state_machine):
        decision = {
            'anomaly_type': 'critical_fault',
            'severity_score': 0.95,
            'mission_phase': 'NOMINAL_OPS'
        }

        handler._execute_escalation(decision)

        mock_state_machine.force_safe_mode.assert_called_once()

    def test_execute_escalation_failure(self, handler, mock_state_machine, caplog):
        mock_state_machine.force_safe_mode.side_effect = Exception("Escalation failed")

        decision = {
            'anomaly_type': 'critical_fault',
            'severity_score': 0.95,
            'mission_phase': 'NOMINAL_OPS'
        }

        handler._execute_escalation(decision)

        assert "Failed to execute escalation" in caplog.text



class TestRecordAnomalyForReporting:

    @patch('anomaly_agent.phase_aware_handler.Path')
    def test_record_anomaly_creates_new_file(self, mock_path_class, handler):
        mock_path = Mock()
        mock_path.exists.return_value = False
        mock_path_class.return_value = mock_path

        decision = {
            'decision_id': 'TEST_123',
            'anomaly_type': 'test_fault',
            'recommended_action': 'log',
            'mission_phase': 'NOMINAL_OPS',
            'timestamp': datetime.now(),
            'detection_confidence': 0.8
        }

        handler._record_anomaly_for_reporting(decision, {})

        mock_path.write_text.assert_called_once()
        written_content = mock_path.write_text.call_args[0][0]
        events = json.loads(written_content)
        assert len(events) == 1
        assert events[0]['fault_id'] == 'TEST_123'

    @patch('anomaly_agent.phase_aware_handler.Path')
    def test_record_anomaly_appends_to_existing_file(self, mock_path_class, handler):
        mock_path = Mock()
        mock_path.exists.return_value = True

        existing_events = [
            {
                'fault_id': 'OLD_123',
                'anomaly_type': 'old_fault',
                'recovery_action': 'log',
                'mission_phase': 'LAUNCH',
                'timestamp': '2024-01-01T00:00:00',
                'confidence_score': 0.7,
                'label': None
            }
        ]
        mock_path.read_text.return_value = json.dumps(existing_events)
        mock_path_class.return_value = mock_path

        decision = {
            'decision_id': 'NEW_456',
            'anomaly_type': 'new_fault',
            'recommended_action': 'warn',
            'mission_phase': 'NOMINAL_OPS',
            'timestamp': datetime.now(),
            'detection_confidence': 0.9
        }

        handler._record_anomaly_for_reporting(decision, {})

        mock_path.write_text.assert_called_once()
        written_content = mock_path.write_text.call_args[0][0]
        events = json.loads(written_content)
        assert len(events) == 2
        assert events[0]['fault_id'] == 'OLD_123'
        assert events[1]['fault_id'] == 'NEW_456'

    @patch('anomaly_agent.phase_aware_handler.Path')
    def test_record_anomaly_handles_corrupt_file(self, mock_path_class, handler, caplog):
        mock_path = Mock()
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = "{ invalid json"
        mock_path_class.return_value = mock_path

        decision = {
            'decision_id': 'TEST_789',
            'anomaly_type': 'test_fault',
            'recommended_action': 'log',
            'mission_phase': 'NOMINAL_OPS',
            'timestamp': datetime.now(),
            'detection_confidence': 0.8
        }

        handler._record_anomaly_for_reporting(decision, {})

        written_content = mock_path.write_text.call_args[0][0]
        events = json.loads(written_content)
        assert len(events) == 1
        assert "Corrupt pending feedback file" in caplog.text

    @patch('anomaly_agent.phase_aware_handler.Path')
    def test_record_anomaly_handles_exception(self, mock_path_class, handler, caplog):
        mock_path_class.side_effect = Exception("File system error")

        decision = {
            'decision_id': 'TEST_999',
            'anomaly_type': 'test_fault',
            'recommended_action': 'log',
            'mission_phase': 'NOMINAL_OPS',
            'timestamp': datetime.now(),
            'detection_confidence': 0.8
        }

        handler._record_anomaly_for_reporting(decision, {})

        assert "Failed to record anomaly for reporting" in caplog.text


class TestLogDecision:

    def test_log_decision_structure(self, handler, caplog):
        decision = {
            'timestamp': datetime.now(),
            'decision_id': 'TEST_LOG_123',
            'anomaly_type': 'test_fault',
            'severity_score': 0.7,
            'detection_confidence': 0.85,
            'mission_phase': 'NOMINAL_OPS',
            'recommended_action': 'warn',
            'should_escalate_to_safe_mode': False,
            'recurrence_info': {'count': 1},
            'reasoning': 'Test reasoning'
        }

        with caplog.at_level(logging.INFO):
            handler._log_decision(decision)

        assert 'TEST_LOG_123' in caplog.text
        assert 'test_fault' in caplog.text
        assert 'Anomaly decision' in caplog.text


class TestPhaseConstraints:

    def test_get_phase_constraints_current_phase(self, handler_with_mock_engine):
        constraints = handler_with_mock_engine.get_phase_constraints()

        assert 'allowed_actions' in constraints
        assert 'forbidden_actions' in constraints
        assert 'threshold_multiplier' in constraints

    def test_get_phase_constraints_specific_phase(self, handler_with_mock_engine):
        handler_with_mock_engine.get_phase_constraints(phase=MissionPhase.SAFE_MODE)

        handler_with_mock_engine.policy_engine.get_phase_constraints.assert_called_with(
            MissionPhase.SAFE_MODE
        )


class TestAnomalyHistory:

    def test_get_anomaly_history_all(self, handler):
        handler.anomaly_history = [
            ('fault_a', datetime.now()),
            ('fault_b', datetime.now()),
            ('fault_a', datetime.now())
        ]

        history = handler.get_anomaly_history()

        assert len(history) == 3
        assert history == handler.anomaly_history
        assert history is not handler.anomaly_history   # must be a copy

    def test_get_anomaly_history_filtered(self, handler):
        now = datetime.now()
        handler.anomaly_history = [
            ('fault_a', now),
            ('fault_b', now),
            ('fault_a', now)
        ]

        history = handler.get_anomaly_history(anomaly_type='fault_a')

        assert len(history) == 2
        assert all(a_type == 'fault_a' for a_type, _ in history)

    def test_clear_anomaly_history(self, handler):
        handler.anomaly_history = [
            ('fault_a', datetime.now()),
            ('fault_b', datetime.now())
        ]

        handler.clear_anomaly_history()

        assert len(handler.anomaly_history) == 0


class TestReloadPolicies:

    def test_reload_policies_success(self, handler, mock_policy_loader):
        handler.reload_policies()

        mock_policy_loader.reload.assert_called_once_with(None)

    def test_reload_policies_with_new_path(self, handler, mock_policy_loader):
        new_path = "/path/to/new/config.yaml"
        handler.reload_policies(new_config_path=new_path)

        mock_policy_loader.reload.assert_called_once_with(new_path)

    def test_reload_policies_failure(self, handler, mock_policy_loader, caplog):
        mock_policy_loader.reload.side_effect = Exception("Config file not found")

        handler.reload_policies()

        assert "Failed to reload policies" in caplog.text


class TestGenerateDecisionId:

    def test_generate_decision_id_format(self, handler):
        decision_id = handler._generate_decision_id()

        assert decision_id.startswith('DECISION_')
        parts = decision_id.split('_')
        assert len(parts) == 3
        assert parts[1].isdigit()
        assert parts[2].isdigit()
        assert len(parts[2]) == 5

    def test_generate_decision_id_uniqueness(self, handler):
        ids = [handler._generate_decision_id() for _ in range(10)]

        assert len(ids) == len(set(ids))


class TestDecisionTracerInitialization:

    def test_init_default(self):
        tracer = DecisionTracer()

        assert tracer.max_decisions == 1000
        assert tracer.decisions == []

    def test_init_custom_max(self):
        tracer = DecisionTracer(max_decisions=500)

        assert tracer.max_decisions == 500


class TestDecisionTracerAddDecision:

    def test_add_decision(self, decision_tracer):
        decision = {
            'decision_id': 'TEST_1',
            'anomaly_type': 'fault_a',
            'mission_phase': 'NOMINAL_OPS'
        }

        decision_tracer.add_decision(decision)

        assert len(decision_tracer.decisions) == 1
        assert decision_tracer.decisions[0] == decision

    def test_add_multiple_decisions(self, decision_tracer):
        for i in range(5):
            decision_tracer.add_decision({'decision_id': f'TEST_{i}', 'anomaly_type': 'fault'})

        assert len(decision_tracer.decisions) == 5

    def test_add_decision_enforces_max(self):
        tracer = DecisionTracer(max_decisions=3)

        for i in range(5):
            tracer.add_decision({'decision_id': f'TEST_{i}'})

        assert len(tracer.decisions) == 3
        assert tracer.decisions[0]['decision_id'] == 'TEST_2'
        assert tracer.decisions[2]['decision_id'] == 'TEST_4'


class TestDecisionTracerQueryMethods:

    def test_get_decisions_for_phase(self, decision_tracer):
        decision_tracer.add_decision({'decision_id': '1', 'mission_phase': 'LAUNCH'})
        decision_tracer.add_decision({'decision_id': '2', 'mission_phase': 'NOMINAL_OPS'})
        decision_tracer.add_decision({'decision_id': '3', 'mission_phase': 'LAUNCH'})

        launch_decisions = decision_tracer.get_decisions_for_phase('LAUNCH')

        assert len(launch_decisions) == 2
        assert all(d['mission_phase'] == 'LAUNCH' for d in launch_decisions)

    def test_get_decisions_for_anomaly_type(self, decision_tracer):
        decision_tracer.add_decision({'decision_id': '1', 'anomaly_type': 'power_fault'})
        decision_tracer.add_decision({'decision_id': '2', 'anomaly_type': 'thermal_fault'})
        decision_tracer.add_decision({'decision_id': '3', 'anomaly_type': 'power_fault'})

        power_decisions = decision_tracer.get_decisions_for_anomaly_type('power_fault')

        assert len(power_decisions) == 2
        assert all(d['anomaly_type'] == 'power_fault' for d in power_decisions)

    def test_get_escalations(self, decision_tracer):
        decision_tracer.add_decision({'decision_id': '1', 'should_escalate_to_safe_mode': False})
        decision_tracer.add_decision({'decision_id': '2', 'should_escalate_to_safe_mode': True})
        decision_tracer.add_decision({'decision_id': '3', 'should_escalate_to_safe_mode': True})

        escalations = decision_tracer.get_escalations()

        assert len(escalations) == 2
        assert all(d['should_escalate_to_safe_mode'] for d in escalations)


class TestDecisionTracerSummaryStats:

    def test_get_summary_stats_empty(self, decision_tracer):
        stats = decision_tracer.get_summary_stats()

        assert stats == {'total_decisions': 0}

    def test_get_summary_stats_comprehensive(self, decision_tracer):
        decision_tracer.add_decision({
            'mission_phase': 'LAUNCH',
            'anomaly_type': 'power_fault',
            'should_escalate_to_safe_mode': False
        })
        decision_tracer.add_decision({
            'mission_phase': 'LAUNCH',
            'anomaly_type': 'thermal_fault',
            'should_escalate_to_safe_mode': True
        })
        decision_tracer.add_decision({
            'mission_phase': 'NOMINAL_OPS',
            'anomaly_type': 'power_fault',
            'should_escalate_to_safe_mode': True
        })

        stats = decision_tracer.get_summary_stats()

        assert stats['total_decisions'] == 3
        assert stats['total_escalations'] == 2
        assert stats['escalation_rate'] == pytest.approx(2 / 3)
        assert stats['by_phase'] == {'LAUNCH': 2, 'NOMINAL_OPS': 1}
        assert stats['by_anomaly_type'] == {'power_fault': 2, 'thermal_fault': 1}

    def test_get_summary_stats_no_escalations(self, decision_tracer):
        decision_tracer.add_decision({
            'mission_phase': 'NOMINAL_OPS',
            'should_escalate_to_safe_mode': False
        })

        stats = decision_tracer.get_summary_stats()

        assert stats['total_escalations'] == 0
        assert stats['escalation_rate'] == 0.0


class TestIntegration:

    def test_full_anomaly_handling_workflow(self, handler_with_mock_engine, mock_state_machine):
        result = handler_with_mock_engine.handle_anomaly(
            anomaly_type='integration_test_fault',
            severity_score=0.75,
            confidence=0.9,
            anomaly_metadata={'component': 'test_component', 'sensor_id': 'SENSOR_123'}
        )

        assert result['success'] is True
        assert 'decision_id' in result
        assert 'explanation' in result
        assert 'recurrence_info' in result

        mock_state_machine.get_current_phase.assert_called()
        handler_with_mock_engine.policy_engine.evaluate.assert_called_once()

    def test_repeated_anomaly_escalation_workflow(self, handler_with_mock_engine, mock_state_machine):
        def mock_evaluate(mission_phase, anomaly_type, severity_score, anomaly_attributes):
            if anomaly_attributes.get('recurrence_count', 0) >= 3:
                d = Mock()
                d.escalation_level = _ESCALATE_LEVEL
                d.recommended_action = 'escalate'
                d.severity = 'CRITICAL'
                d.reasoning = 'Repeated failures detected'
                return d
            d = Mock()
            d.escalation_level = _NORMAL_LEVEL
            d.recommended_action = 'warn'
            d.severity = 'MEDIUM'
            d.reasoning = 'Monitoring situation'
            return d

        handler_with_mock_engine.policy_engine.evaluate.side_effect = mock_evaluate

        for _ in range(3):
            result = handler_with_mock_engine.handle_anomaly(
                anomaly_type='repeated_critical_fault',
                severity_score=0.8,
                confidence=0.9
            )

        assert result['should_escalate_to_safe_mode'] is True
        mock_state_machine.force_safe_mode.assert_called_once()


class TestEdgeCases:

    def test_handle_anomaly_with_zero_severity(self, handler_with_mock_engine):
        result = handler_with_mock_engine.handle_anomaly(
            anomaly_type='zero_severity',
            severity_score=0.0,
            confidence=0.5
        )

        assert result['success'] is True
        assert result['severity_score'] == 0.0

    def test_handle_anomaly_with_max_severity(self, handler_with_mock_engine):
        result = handler_with_mock_engine.handle_anomaly(
            anomaly_type='max_severity',
            severity_score=1.0,
            confidence=1.0
        )

        assert result['success'] is True
        assert result['severity_score'] == 1.0

    def test_handle_anomaly_with_empty_string_type(self, handler_with_mock_engine):
        result = handler_with_mock_engine.handle_anomaly(
            anomaly_type='',
            severity_score=0.5,
            confidence=0.8
        )

        assert result['success'] is True
        assert result['anomaly_type'] == ''

    def test_handle_anomaly_with_very_long_type(self, handler_with_mock_engine):
        long_type = 'a' * 1000
        result = handler_with_mock_engine.handle_anomaly(
            anomaly_type=long_type,
            severity_score=0.5,
            confidence=0.8
        )

        assert result['success'] is True
        assert result['anomaly_type'] == long_type


class TestDecisionTracerRecordAnomalyForReporting:
    """Test the _record_anomaly_for_reporting method in DecisionTracer."""

    @patch('anomaly_agent.phase_aware_handler.get_report_generator')
    def test_record_anomaly_critical_severity(self, mock_get_generator, decision_tracer):
        mock_generator = Mock()
        mock_get_generator.return_value = mock_generator

        decision = {
            'anomaly_type': 'critical_fault',
            'severity_score': 0.9,
            'detection_confidence': 0.95,
            'mission_phase': 'NOMINAL_OPS',
            'recurrence_info': {'count': 1},
            'explanation': 'Critical system failure'
        }

        decision_tracer._record_anomaly_for_reporting(decision, {'component': 'power'})

        mock_generator.record_anomaly.assert_called_once()
        call_kwargs = mock_generator.record_anomaly.call_args[1]
        assert call_kwargs['anomaly_type'] == 'critical_fault'
        assert call_kwargs['severity'] == 'CRITICAL'
        assert call_kwargs['confidence'] == 0.95
        assert call_kwargs['mission_phase'] == 'NOMINAL_OPS'
        assert 'severity_score' in call_kwargs['telemetry_data']
        assert call_kwargs['explanation'] == 'Critical system failure'

    @patch('anomaly_agent.phase_aware_handler.get_report_generator')
    def test_record_anomaly_high_severity(self, mock_get_generator, decision_tracer):
        mock_generator = Mock()
        mock_get_generator.return_value = mock_generator

        decision = {
            'anomaly_type': 'high_fault',
            'severity_score': 0.7,
            'detection_confidence': 0.85,
            'mission_phase': 'LAUNCH',
            'recurrence_info': {}
        }

        decision_tracer._record_anomaly_for_reporting(decision, {})

        call_kwargs = mock_generator.record_anomaly.call_args[1]
        assert call_kwargs['severity'] == 'HIGH'

    @patch('anomaly_agent.phase_aware_handler.get_report_generator')
    def test_record_anomaly_medium_severity(self, mock_get_generator, decision_tracer):
        mock_generator = Mock()
        mock_get_generator.return_value = mock_generator

        decision = {
            'anomaly_type': 'medium_fault',
            'severity_score': 0.5,
            'detection_confidence': 0.75,
            'mission_phase': 'NOMINAL_OPS',
        }

        decision_tracer._record_anomaly_for_reporting(decision, None)

        call_kwargs = mock_generator.record_anomaly.call_args[1]
        assert call_kwargs['severity'] == 'MEDIUM'

    @patch('anomaly_agent.phase_aware_handler.get_report_generator')
    def test_record_anomaly_low_severity(self, mock_get_generator, decision_tracer):
        mock_generator = Mock()
        mock_get_generator.return_value = mock_generator

        decision = {
            'anomaly_type': 'low_fault',
            'severity_score': 0.2,
            'detection_confidence': 0.65,
            'mission_phase': 'SAFE_MODE'
        }

        decision_tracer._record_anomaly_for_reporting(decision, {})

        call_kwargs = mock_generator.record_anomaly.call_args[1]
        assert call_kwargs['severity'] == 'LOW'

    @patch('anomaly_agent.phase_aware_handler.get_report_generator')
    def test_record_anomaly_severity_boundary_critical(self, mock_get_generator, decision_tracer):
        mock_generator = Mock()
        mock_get_generator.return_value = mock_generator

        decision = {
            'anomaly_type': 'boundary_test',
            'severity_score': 0.8,
            'mission_phase': 'NOMINAL_OPS'
        }

        decision_tracer._record_anomaly_for_reporting(decision, {})

        call_kwargs = mock_generator.record_anomaly.call_args[1]
        assert call_kwargs['severity'] == 'CRITICAL'

    @patch('anomaly_agent.phase_aware_handler.get_report_generator')
    def test_record_anomaly_severity_boundary_high(self, mock_get_generator, decision_tracer):
        mock_generator = Mock()
        mock_get_generator.return_value = mock_generator

        decision = {
            'anomaly_type': 'boundary_test',
            'severity_score': 0.6,
            'mission_phase': 'NOMINAL_OPS'
        }

        decision_tracer._record_anomaly_for_reporting(decision, {})

        call_kwargs = mock_generator.record_anomaly.call_args[1]
        assert call_kwargs['severity'] == 'HIGH'

    @patch('anomaly_agent.phase_aware_handler.get_report_generator')
    def test_record_anomaly_severity_boundary_medium(self, mock_get_generator, decision_tracer):
        mock_generator = Mock()
        mock_get_generator.return_value = mock_generator

        decision = {
            'anomaly_type': 'boundary_test',
            'severity_score': 0.4,
            'mission_phase': 'NOMINAL_OPS'
        }

        decision_tracer._record_anomaly_for_reporting(decision, {})

        call_kwargs = mock_generator.record_anomaly.call_args[1]
        assert call_kwargs['severity'] == 'MEDIUM'

    @patch('anomaly_agent.phase_aware_handler.get_report_generator')
    def test_record_anomaly_with_metadata(self, mock_get_generator, decision_tracer):
        mock_generator = Mock()
        mock_get_generator.return_value = mock_generator

        decision = {
            'anomaly_type': 'test_fault',
            'severity_score': 0.7,
            'detection_confidence': 0.9,
            'mission_phase': 'NOMINAL_OPS',
            'recurrence_info': {'count': 2, 'total_in_window': 1}
        }

        metadata = {'sensor_id': 'SENSOR_001', 'component': 'thermal'}

        decision_tracer._record_anomaly_for_reporting(decision, metadata)

        call_kwargs = mock_generator.record_anomaly.call_args[1]
        telemetry = call_kwargs['telemetry_data']
        assert 'sensor_id' in telemetry
        assert telemetry['sensor_id'] == 'SENSOR_001'
        assert 'component' in telemetry
        assert telemetry['component'] == 'thermal'

    @patch('anomaly_agent.phase_aware_handler.get_report_generator')
    def test_record_anomaly_missing_optional_fields(self, mock_get_generator, decision_tracer):
        mock_generator = Mock()
        mock_get_generator.return_value = mock_generator

        decision = {
            'anomaly_type': 'minimal_fault',
            'mission_phase': 'NOMINAL_OPS'
        }

        decision_tracer._record_anomaly_for_reporting(decision, {})

        call_kwargs = mock_generator.record_anomaly.call_args[1]
        assert call_kwargs['severity'] == 'MEDIUM'
        assert call_kwargs['confidence'] == 0.0

    @patch('anomaly_agent.phase_aware_handler.get_report_generator')
    def test_record_anomaly_exception_handling(self, mock_get_generator, decision_tracer, caplog):
        mock_get_generator.side_effect = Exception("Report generator unavailable")

        decision = {
            'anomaly_type': 'test_fault',
            'severity_score': 0.7,
            'mission_phase': 'NOMINAL_OPS'
        }

        with caplog.at_level(logging.WARNING):
            decision_tracer._record_anomaly_for_reporting(decision, {})

        assert "Failed to record anomaly for reporting" in caplog.text

    @patch('anomaly_agent.phase_aware_handler.get_report_generator')
    def test_record_anomaly_generator_method_fails(self, mock_get_generator, decision_tracer, caplog):
        mock_generator = Mock()
        mock_generator.record_anomaly.side_effect = Exception("Database connection failed")
        mock_get_generator.return_value = mock_generator

        decision = {
            'anomaly_type': 'test_fault',
            'severity_score': 0.6,
            'mission_phase': 'NOMINAL_OPS'
        }

        with caplog.at_level(logging.WARNING):
            decision_tracer._record_anomaly_for_reporting(decision, {})

        assert "Failed to record anomaly for reporting" in caplog.text


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--cov=anomaly_agent.phase_aware_handler', '--cov-report=html'])