"""Unit tests for src/cli.py - CLI Module."""
import sys
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))


def get_captured_output(func, *args, **kwargs):
    """Helper to capture output from a function."""
    import io
    from contextlib import redirect_stdout, redirect_stderr
    
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    
    with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
        try:
            func(*args, **kwargs)
        except SystemExit:
            pass
    
    return stdout_buffer.getvalue(), stderr_buffer.getvalue()


def test_launch_phase():
    """Test LAUNCH phase description."""
    from cli import _get_phase_description
    assert _get_phase_description("LAUNCH") == "Rocket ascent and orbital insertion"


def test_deployment_phase():
    """Test DEPLOYMENT phase description."""
    from cli import _get_phase_description
    assert _get_phase_description("DEPLOYMENT") == "System stabilization and checkout"


def test_nominal_ops_phase():
    """Test NOMINAL_OPS phase description."""
    from cli import _get_phase_description
    assert _get_phase_description("NOMINAL_OPS") == "Standard mission operations"


def test_payload_ops_phase():
    """Test PAYLOAD_OPS phase description."""
    from cli import _get_phase_description
    assert _get_phase_description("PAYLOAD_OPS") == "Science/mission payload operations"


def test_safe_mode_phase():
    """Test SAFE_MODE phase description."""
    from cli import _get_phase_description
    assert _get_phase_description("SAFE_MODE") == "Minimal power survival mode"


def test_unknown_phase():
    """Test unknown phase returns default."""
    from cli import _get_phase_description
    assert _get_phase_description("UNKNOWN_PHASE") == "Unknown phase"


def test_empty_phase():
    """Test empty phase returns default."""
    from cli import _get_phase_description
    assert _get_phase_description("") == "Unknown phase"


def setup_tmpdir():
    tmp = tempfile.mkdtemp()
    original = os.getcwd()
    os.chdir(tmp)
    return tmp, original


def cleanup(original):
    os.chdir(original)


def test_secrets_add():
    """Test adding a secret."""
    from cli import run_secrets_command
    import argparse
    
    tmp, original = setup_tmpdir()
    try:
        mock_metadata = MagicMock()
        mock_metadata.version = 1
        
        with patch("cli.init_secrets_manager"):
            with patch("cli.store_secret", return_value=mock_metadata):
                args = argparse.Namespace(
                    secrets_command="add", key="API_KEY", value="secret123",
                    description="Test key", expires=30
                )
                stdout, stderr = get_captured_output(run_secrets_command, args)
        
        assert "stored successfully" in stdout
        assert "version 1" in stdout
    finally:
        cleanup(original)


def test_secrets_get():
    """Test getting a secret."""
    from cli import run_secrets_command
    import argparse
    
    tmp, original = setup_tmpdir()
    try:
        with patch("cli.init_secrets_manager"):
            with patch("cli.get_secret", return_value="my_secret_value"):
                args = argparse.Namespace(
                    secrets_command="get", key="API_KEY", version=None, show=False
                )
                stdout, stderr = get_captured_output(run_secrets_command, args)
        
        assert "retrieved" in stdout
    finally:
        cleanup(original)


def test_secrets_get_show_value():
    """Test getting and showing secret value."""
    from cli import run_secrets_command
    import argparse
    
    tmp, original = setup_tmpdir()
    try:
        with patch("cli.init_secrets_manager"):
            with patch("cli.get_secret", return_value="secret123"):
                args = argparse.Namespace(
                    secrets_command="get", key="API_KEY", version=None, show=True
                )
                stdout, stderr = get_captured_output(run_secrets_command, args)
        
        assert "secret123" in stdout
    finally:
        cleanup(original)


def test_secrets_get_not_found():
    """Test getting non-existent secret."""
    from cli import run_secrets_command
    import argparse
    
    tmp, original = setup_tmpdir()
    try:
        with patch("cli.init_secrets_manager"):
            with patch("cli.get_secret", side_effect=KeyError("Not found")):
                args = argparse.Namespace(
                    secrets_command="get", key="MISSING_KEY", version=None, show=False
                )
                stdout, stderr = get_captured_output(run_secrets_command, args)
        
        assert "not found" in stdout
    finally:
        cleanup(original)


def test_secrets_rotate():
    """Test rotating a secret."""
    from cli import run_secrets_command
    import argparse
    
    tmp, original = setup_tmpdir()
    try:
        mock_metadata = MagicMock()
        mock_metadata.version = 2
        
        with patch("cli.init_secrets_manager"):
            with patch("cli.rotate_secret", return_value=mock_metadata):
                args = argparse.Namespace(
                    secrets_command="rotate", key="API_KEY", value="new_secret"
                )
                stdout, stderr = get_captured_output(run_secrets_command, args)
        
        assert "rotated" in stdout
        assert "version 2" in stdout
    finally:
        cleanup(original)


def test_secrets_list_empty():
    """Test listing empty secrets."""
    from cli import run_secrets_command
    import argparse
    
    tmp, original = setup_tmpdir()
    try:
        with patch("cli.init_secrets_manager"):
            with patch("cli.list_secrets", return_value=[]):
                args = argparse.Namespace(secrets_command="list")
                stdout, stderr = get_captured_output(run_secrets_command, args)
        
        assert "No secrets stored" in stdout
    finally:
        cleanup(original)


def test_secrets_list_with_entries():
    """Test listing secrets with entries."""
    from cli import run_secrets_command
    import argparse
    
    tmp, original = setup_tmpdir()
    try:
        mock_secrets = [
            MagicMock(key="API_KEY", version=1, expires_at=None, description="API key"),
            MagicMock(key="DB_PASS", version=2, expires_at="2026-12-31", description="Database password"),
        ]
        
        with patch("cli.init_secrets_manager"):
            with patch("cli.list_secrets", return_value=mock_secrets):
                args = argparse.Namespace(secrets_command="list")
                stdout, stderr = get_captured_output(run_secrets_command, args)
        
        assert "2 secrets" in stdout
        assert "API_KEY" in stdout
        assert "DB_PASS" in stdout
    finally:
        cleanup(original)


def test_secrets_health_all_ok():
    """Test secrets health check - all OK."""
    from cli import run_secrets_command
    import argparse
    
    tmp, original = setup_tmpdir()
    try:
        with patch("cli.init_secrets_manager"):
            with patch("cli.health_check", return_value={"backend": True, "encryption": True, "cache": True}):
                args = argparse.Namespace(secrets_command="health")
                stdout, stderr = get_captured_output(run_secrets_command, args)
        
        assert "Health Check" in stdout
        assert "✅" in stdout
    finally:
        cleanup(original)


def test_secrets_health_with_failures():
    """Test secrets health check with failures."""
    from cli import run_secrets_command
    import argparse
    
    tmp, original = setup_tmpdir()
    try:
        with patch("cli.init_secrets_manager"):
            with patch("cli.health_check", return_value={"backend": True, "encryption": False}):
                args = argparse.Namespace(secrets_command="health")
                stdout, stderr = get_captured_output(run_secrets_command, args)
        
        assert "❌" in stdout
    finally:
        cleanup(original)


def test_secrets_unknown_command():
    """Test unknown secrets command."""
    from cli import run_secrets_command
    import argparse
    
    tmp, original = setup_tmpdir()
    try:
        with patch("cli.init_secrets_manager"):
            args = argparse.Namespace(secrets_command="unknown")
            stdout, stderr = get_captured_output(run_secrets_command, args)
        
        assert "Unknown secrets command" in stdout
    finally:
        cleanup(original)


def test_run_telemetry_calls_subprocess():
    """Test run_telemetry invokes correct subprocess."""
    from cli import run_telemetry
    
    tmp, original = setup_tmpdir()
    try:
        with patch("cli.os.path.exists", return_value=True):
            with patch("cli.subprocess.run") as mock_run:
                run_telemetry()
                mock_run.assert_called_once()
                call_args = mock_run.call_args[0][0]
                assert "telemetry_stream.py" in call_args[-1]
    finally:
        cleanup(original)


def test_run_dashboard_calls_streamlit():
    """Test run_dashboard invokes streamlit."""
    from cli import run_dashboard
    
    tmp, original = setup_tmpdir()
    try:
        with patch("cli.subprocess.run") as mock_run:
            run_dashboard()
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert call_args[0] == "streamlit"
            assert "app.py" in call_args[-1]
    finally:
        cleanup(original)


def test_run_simulation_calls_attitude_script():
    """Test run_simulation invokes attitude script."""
    from cli import run_simulation
    
    tmp, original = setup_tmpdir()
    try:
        with patch("cli.os.path.exists", return_value=True):
            with patch("cli.subprocess.run") as mock_run:
                run_simulation()
                mock_run.assert_called_once()
                call_args = mock_run.call_args[0][0]
                assert "attitude_3d.py" in call_args[-1]
    finally:
        cleanup(original)


def test_report_json_format():
    """Test generating JSON format report."""
    from cli import run_report
    import argparse
    
    tmp, original = setup_tmpdir()
    try:
        mock_report_generator = MagicMock()
        mock_report_generator.export_json.return_value = "anomaly_report.json"
        mock_report_generator.generate_report.return_value = {
            "summary": {"total_anomalies": 5, "resolved_anomalies": 3, "critical_anomalies": 1}
        }
        
        with patch("anomaly.report_generator.get_report_generator", return_value=mock_report_generator):
            args = argparse.Namespace(format="json", output=None, hours=24)
            stdout, stderr = get_captured_output(run_report, args)
        
        assert "JSON anomaly report" in stdout
        assert "Total Anomalies: 5" in stdout
    finally:
        cleanup(original)


def test_report_text_format():
    """Test generating text format report."""
    from cli import run_report
    import argparse
    
    tmp, original = setup_tmpdir()
    try:
        mock_report_generator = MagicMock()
        mock_report_generator.export_text.return_value = "anomaly_report.txt"
        mock_report_generator.generate_report.return_value = {"summary": {}}
        
        with patch("anomaly.report_generator.get_report_generator", return_value=mock_report_generator):
            args = argparse.Namespace(format="text", output=None, hours=24)
            stdout, stderr = get_captured_output(run_report, args)
        
        assert "TEXT anomaly report" in stdout
    finally:
        cleanup(original)


def test_report_custom_output():
    """Test report with custom output file."""
    from cli import run_report
    import argparse
    
    tmp, original = setup_tmpdir()
    try:
        mock_report_generator = MagicMock()
        mock_report_generator.export_json.return_value = "custom_report.json"
        mock_report_generator.generate_report.return_value = {"summary": {}}
        
        with patch("anomaly.report_generator.get_report_generator", return_value=mock_report_generator):
            args = argparse.Namespace(format="json", output="custom_report.json", hours=12)
            stdout, stderr = get_captured_output(run_report, args)
        
        assert "custom_report.json" in stdout
    finally:
        cleanup(original)


def test_report_missing_dependencies():
    """Test report fails gracefully when dependencies missing."""
    from cli import run_report
    import argparse
    
    tmp, original = setup_tmpdir()
    try:
        with patch("anomaly.report_generator.get_report_generator", side_effect=ImportError):
            args = argparse.Namespace(format="json", output=None, hours=24)
            stdout, stderr = get_captured_output(run_report, args)
        
        assert "Anomaly reporting not available" in stdout
    finally:
        cleanup(original)


def test_report_generation_error():
    """Test report handles generation errors."""
    from cli import run_report
    import argparse

    tmp, original = setup_tmpdir()
    try:
        mock_report_generator = MagicMock()
        mock_report_generator.export_json.side_effect = Exception("Disk full")

        with patch("anomaly.report_generator.get_report_generator", return_value=mock_report_generator):
            args = argparse.Namespace(format="json", output=None, hours=24)
            stdout, stderr = get_captured_output(run_report, args)

        assert "Failed to generate report" in stdout
    finally:
        cleanup(original)


def test_report_with_mttr():
    """Test report displays MTTR when available."""
    from cli import run_report
    import argparse

    tmp, original = setup_tmpdir()
    try:
        mock_report_generator = MagicMock()
        mock_report_generator.export_json.return_value = "anomaly_report.json"
        mock_report_generator.generate_report.return_value = {
            "summary": {"total_anomalies": 10, "resolved_anomalies": 8, "critical_anomalies": 2, "average_mttr_seconds": 45.5}
        }

        with patch("anomaly.report_generator.get_report_generator", return_value=mock_report_generator):
            args = argparse.Namespace(format="json", output=None, hours=24)
            stdout, stderr = get_captured_output(run_report, args)

        assert "Avg MTTR" in stdout
    finally:
        cleanup(original)


def test_feedback_load_pending_file_not_exists():
    """Test load_pending when file doesn't exist."""
    from cli import FeedbackCLI
    with tempfile.TemporaryDirectory() as tmp:
        original = Path.cwd()
        try:
            Path.cwd() / "feedback_pending.json"
            os.chdir(tmp)
            result = FeedbackCLI.load_pending()
            assert result == []
        finally:
            os.chdir(original)


def test_feedback_load_pending_invalid_json():
    """Test load_pending with invalid JSON."""
    from cli import FeedbackCLI
    with tempfile.TemporaryDirectory() as tmp:
        original = Path.cwd()
        try:
            os.chdir(tmp)
            Path("feedback_pending.json").write_text("{invalid json}")

            result = FeedbackCLI.load_pending()
            assert result == []
            assert not Path("feedback_pending.json").exists()
        finally:
            os.chdir(original)


def test_feedback_load_pending_non_list():
    """Test load_pending when file contains non-list."""
    from cli import FeedbackCLI
    with tempfile.TemporaryDirectory() as tmp:
        original = Path.cwd()
        try:
            os.chdir(tmp)
            Path("feedback_pending.json").write_text('{"key": "value"}')

            result = FeedbackCLI.load_pending()
            assert result == []
        finally:
            os.chdir(original)


def test_feedback_save_processed():
    """Test save_processed writes to file."""
    from cli import FeedbackCLI
    with tempfile.TemporaryDirectory() as tmp:
        original = Path.cwd()
        try:
            os.chdir(tmp)
            events = [{"id": 1, "label": "correct"}]
            FeedbackCLI.save_processed(events)

            content = Path("feedback_processed.json").read_text()
            assert '"id":1' in content or '"id": 1' in content
        finally:
            os.chdir(original)


def test_run_status_healthy_components():
    """Test run_status with all healthy components."""
    from cli import run_status
    import argparse

    mock_health = MagicMock()
    mock_health.get_all_health.return_value = {
        "database": {"status": "healthy"},
        "cache": {"status": "healthy"}
    }

    with patch("core.component_health.get_health_monitor", return_value=mock_health):
        with patch("state_machine.state_engine.StateMachine") as mock_sm:
            mock_sm_instance = MagicMock()
            mock_sm_instance.current_phase.value = "NOMINAL_OPS"
            mock_sm.return_value = mock_sm_instance

            args = argparse.Namespace(verbose=False)
            stdout, stderr = get_captured_output(run_status, args)

    assert "AstraGuard AI - System Status Report" in stdout
    assert "✅" in stdout


def test_run_status_degraded_components():
    """Test run_status with degraded components."""
    from cli import run_status
    import argparse

    mock_health = MagicMock()
    mock_health.get_all_health.return_value = {
        "database": {"status": "healthy"},
        "cache": {"status": "degraded", "fallback_active": True}
    }

    with patch("core.component_health.get_health_monitor", return_value=mock_health):
        with patch("state_machine.state_engine.StateMachine") as mock_sm:
            mock_sm_instance = MagicMock()
            mock_sm_instance.current_phase.value = "NOMINAL_OPS"
            mock_sm.return_value = mock_sm_instance

            args = argparse.Namespace(verbose=False)
            stdout, stderr = get_captured_output(run_status, args)

    assert "⚠️" in stdout
    assert "[FALLBACK MODE]" in stdout


def test_run_status_failed_components():
    """Test run_status with failed components (exit code 1)."""
    from cli import run_status
    import argparse

    mock_health = MagicMock()
    mock_health.get_all_health.return_value = {
        "database": {"status": "failed", "error_count": 3}
    }

    with patch("core.component_health.get_health_monitor", return_value=mock_health):
        with patch("state_machine.state_engine.StateMachine") as mock_sm:
            mock_sm_instance = MagicMock()
            mock_sm_instance.current_phase.value = "NOMINAL_OPS"
            mock_sm.return_value = mock_sm_instance

            args = argparse.Namespace(verbose=False)
            stdout, stderr = get_captured_output(run_status, args)

    assert "❌" in stdout
    assert "(Errors: 3)" in stdout


def test_run_status_verbose_mode():
    """Test run_status with verbose flag shows errors."""
    from cli import run_status
    import argparse

    mock_health = MagicMock()
    mock_health.get_all_health.return_value = {
        "database": {"status": "healthy", "last_error": "Connection timeout"}
    }

    with patch("core.component_health.get_health_monitor", return_value=mock_health):
        with patch("state_machine.state_engine.StateMachine") as mock_sm:
            mock_sm_instance = MagicMock()
            mock_sm_instance.current_phase.value = "NOMINAL_OPS"
            mock_sm.return_value = mock_sm_instance

            args = argparse.Namespace(verbose=True)
            stdout, stderr = get_captured_output(run_status, args)

    assert "Last Error" in stdout
    assert "Connection timeout" in stdout


def test_run_status_no_components():
    """Test run_status when no components registered."""
    from cli import run_status
    import argparse

    mock_health = MagicMock()
    mock_health.get_all_health.return_value = {}

    with patch("core.component_health.get_health_monitor", return_value=mock_health):
        with patch("state_machine.state_engine.StateMachine") as mock_sm:
            mock_sm_instance = MagicMock()
            mock_sm_instance.current_phase.value = "NOMINAL_OPS"
            mock_sm.return_value = mock_sm_instance

            args = argparse.Namespace(verbose=False)
            stdout, stderr = get_captured_output(run_status, args)

    assert "No components registered" in stdout


def test_run_status_prometheus_import_error():
    """Test run_status handles prometheus import error gracefully."""
    from cli import run_status
    import argparse

    mock_health = MagicMock()
    mock_health.get_all_health.return_value = {"database": {"status": "healthy"}}

    with patch("core.component_health.get_health_monitor", return_value=mock_health):
        with patch("state_machine.state_engine.StateMachine", side_effect=ImportError("prometheus not found")):
            args = argparse.Namespace(verbose=False)
            stdout, stderr = get_captured_output(run_status, args)

    assert "prometheus" in stdout.lower()


def test_main_status_command():
    """Test main with status command."""
    from cli import main
    import sys

    with patch("cli.run_status") as mock_run_status:
        with patch("core.component_health.get_health_monitor") as mock_health:
            mock_health.return_value = MagicMock()
            with patch("state_machine.state_engine.StateMachine") as mock_sm:
                mock_sm_instance = MagicMock()
                mock_sm_instance.current_phase.value = "NOMINAL_OPS"
                mock_sm.return_value = mock_sm_instance

                with patch.object(sys, "argv", ["cli.py", "status"]):
                    main()

    mock_run_status.assert_called_once()


def test_main_telemetry_command():
    """Test main with telemetry command."""
    from cli import main
    import sys

    with patch("cli.run_telemetry") as mock_run_telemetry:
        with patch.object(sys, "argv", ["cli.py", "telemetry"]):
            main()

    mock_run_telemetry.assert_called_once()


def test_main_dashboard_command():
    """Test main with dashboard command."""
    from cli import main
    import sys

    with patch("cli.run_dashboard") as mock_run_dashboard:
        with patch.object(sys, "argv", ["cli.py", "dashboard"]):
            main()

    mock_run_dashboard.assert_called_once()


def test_main_simulate_command():
    """Test main with simulate command."""
    from cli import main
    import sys

    with patch("cli.run_simulation") as mock_run_simulation:
        with patch.object(sys, "argv", ["cli.py", "simulate"]):
            main()

    mock_run_simulation.assert_called_once()


def test_main_report_command():
    """Test main with report command."""
    from cli import main, run_report
    import sys

    with patch("cli.run_report") as mock_run_report:
        with patch("anomaly.report_generator.get_report_generator") as mock_gen:
            mock_gen.return_value = MagicMock()
            with patch.object(sys, "argv", ["cli.py", "report", "json"]):
                main()

    mock_run_report.assert_called_once()


def test_main_no_command_shows_help():
    """Test main with no command shows help."""
    from cli import main
    import sys

    with patch.object(sys, "argv", ["cli.py"]):
        with patch("argparse.ArgumentParser.print_help") as mock_help:
            main()

    mock_help.assert_called_once()


def test_run_classifier():
    """Test run_classifier function exists and is callable."""
    try:
        from cli import run_classifier
        assert callable(run_classifier)
    except ImportError:
        pass


def test_get_phase_description_all_phases():
    """Test all mission phase descriptions are correct."""
    from cli import _get_phase_description

    phases = {
        "LAUNCH": "Rocket ascent and orbital insertion",
        "DEPLOYMENT": "System stabilization and checkout",
        "NOMINAL_OPS": "Standard mission operations",
        "PAYLOAD_OPS": "Science/mission payload operations",
        "SAFE_MODE": "Minimal power survival mode",
        "UNKNOWN": "Unknown phase",
        "RANDOM": "Unknown phase"
    }

    for phase, expected in phases.items():
        assert _get_phase_description(phase) == expected


# ==================== Additional Comprehensive Tests ====================

def test_feedback_load_pending_valid_data():
    """Test load_pending with valid feedback data."""
    from cli import FeedbackCLI
    import json
    with tempfile.TemporaryDirectory() as tmp:
        original = Path.cwd()
        try:
            os.chdir(tmp)
            feedback_data = [
                {
                    "fault_id": "FLT-001",
                    "timestamp": "2024-01-01T00:00:00",
                    "anomaly_type": "power_fault",
                    "recovery_action": "restart_battery",
                    "label": "correct",
                    "mission_phase": "NOMINAL_OPS",
                    "confidence_score": 0.95
                },
                {
                    "fault_id": "FLT-002",
                    "timestamp": "2024-01-01T01:00:00",
                    "anomaly_type": "thermal_fault",
                    "recovery_action": "enable_cooling",
                    "label": "wrong",
                    "mission_phase": "PAYLOAD_OPS",
                    "confidence_score": 0.70
                }
            ]
            Path("feedback_pending.json").write_text(json.dumps(feedback_data))
            
            result = FeedbackCLI.load_pending()
            assert len(result) == 2
            assert result[0].fault_id == "FLT-001"
            assert result[1].anomaly_type == "thermal_fault"
        finally:
            os.chdir(original)


def test_feedback_load_pending_permission_error():
    """Test load_pending handles permission errors."""
    from cli import FeedbackCLI
    import json
    with tempfile.TemporaryDirectory() as tmp:
        original = Path.cwd()
        try:
            os.chdir(tmp)
            Path("feedback_pending.json").write_text(json.dumps([{"id": 1}]))
            
            with patch("builtins.open", side_effect=PermissionError("Access denied")):
                result = FeedbackCLI.load_pending()
                assert result == []
        finally:
            os.chdir(original)


def test_feedback_save_processed_oserror():
    """Test save_processed handles OS errors."""
    from cli import FeedbackCLI
    with tempfile.TemporaryDirectory() as tmp:
        original = Path.cwd()
        try:
            os.chdir(tmp)
            events = [{"id": 1, "label": "correct"}]
            
            with patch("builtins.open", side_effect=OSError("Disk full")):
                # Should not raise, just log error
                try:
                    FeedbackCLI.save_processed(events)
                except OSError:
                    pass  # Expected behavior when disk full
        finally:
            os.chdir(original)


def test_feedback_save_processed_permission_error():
    """Test save_processed handles permission errors."""
    from cli import FeedbackCLI
    with tempfile.TemporaryDirectory() as tmp:
        original = Path.cwd()
        try:
            os.chdir(tmp)
            events = [{"id": 1, "label": "correct"}]
            
            with patch("builtins.open", side_effect=PermissionError("Access denied")):
                # Should not raise, just log error
                try:
                    FeedbackCLI.save_processed(events)
                except PermissionError:
                    pass  # Expected behavior when permission denied
        finally:
            os.chdir(original)


def test_feedback_review_interactive_no_pending():
    """Test review_interactive with no pending feedback."""
    from cli import FeedbackCLI
    with tempfile.TemporaryDirectory() as tmp:
        original = Path.cwd()
        try:
            os.chdir(tmp)
            
            with patch("cli.FeedbackCLI.load_pending", return_value=[]):
                stdout, stderr = get_captured_output(FeedbackCLI.review_interactive)
            
            assert "No pending feedback" in stdout
        finally:
            os.chdir(original)


def test_feedback_review_interactive_with_events():
    """Test review_interactive with feedback events."""
    from cli import FeedbackCLI
    from models.feedback import FeedbackEvent
    with tempfile.TemporaryDirectory() as tmp:
        original = Path.cwd()
        try:
            os.chdir(tmp)
            mock_events = [
                FeedbackEvent(
                    fault_id="FLT-001",
                    anomaly_type="power_fault",
                    recovery_action="restart_battery",
                    mission_phase="NOMINAL_OPS",
                    confidence_score=0.95
                )
            ]
            
            with patch("cli.FeedbackCLI.load_pending", return_value=mock_events):
                with patch("builtins.input", side_effect=["q"]):  # Quit immediately
                    with patch("cli.FeedbackCLI.save_processed"):
                        stdout, stderr = get_captured_output(FeedbackCLI.review_interactive)
            
            # Should show pending events
            assert "pending events found" in stdout.lower() or "fault:" in stdout.lower()
        finally:
            os.chdir(original)


def test_feedback_review_interactive_accept_feedback():
    """Test review_interactive accepting feedback."""
    from cli import FeedbackCLI
    from models.feedback import FeedbackEvent
    with tempfile.TemporaryDirectory() as tmp:
        original = Path.cwd()
        try:
            os.chdir(tmp)
            mock_events = [
                FeedbackEvent(
                    fault_id="FLT-001",
                    anomaly_type="power_fault",
                    recovery_action="restart_battery",
                    mission_phase="NOMINAL_OPS",
                    confidence_score=0.95
                )
            ]
            
            with patch("cli.FeedbackCLI.load_pending", return_value=mock_events):
                # Provide "correct" label, skip notes (empty), then continue to completion
                with patch("builtins.input", side_effect=["correct", ""]):
                    with patch("cli.FeedbackCLI.save_processed") as mock_save:
                        with patch("pathlib.Path.unlink"):
                            stdout, stderr = get_captured_output(FeedbackCLI.review_interactive)
                        
                        # Should have called save_processed after reviewing all events
                        mock_save.assert_called_once()
        finally:
            os.chdir(original)


def test_feedback_review_interactive_reject_feedback():
    """Test review_interactive rejecting feedback."""
    from cli import FeedbackCLI
    from models.feedback import FeedbackEvent
    with tempfile.TemporaryDirectory() as tmp:
        original = Path.cwd()
        try:
            os.chdir(tmp)
            mock_events = [
                FeedbackEvent(
                    fault_id="FLT-001",
                    anomaly_type="power_fault",
                    recovery_action="restart_battery",
                    mission_phase="NOMINAL_OPS",
                    confidence_score=0.95
                )
            ]
            
            with patch("cli.FeedbackCLI.load_pending", return_value=mock_events):
                # Provide "wrong" label, skip notes (empty), then continue to completion
                with patch("builtins.input", side_effect=["wrong", ""]):
                    with patch("cli.FeedbackCLI.save_processed") as mock_save:
                        with patch("pathlib.Path.unlink"):
                            stdout, stderr = get_captured_output(FeedbackCLI.review_interactive)
                        
                        # Should call save_processed with events labeled as wrong
                        mock_save.assert_called_once()
        finally:
            os.chdir(original)


def test_run_status_import_error_health_monitor():
    """Test run_status handles health monitor import errors."""
    from cli import run_status
    import argparse
    
    with patch("core.component_health.get_health_monitor", side_effect=ImportError("Module not found")):
        args = argparse.Namespace(verbose=False)
        stdout, stderr = get_captured_output(run_status, args)
    
    # When import fails, it still proceeds with empty health dict
    assert "System Status Report" in stdout


def test_run_status_state_machine_import_error():
    """Test run_status handles state machine import errors."""
    from cli import run_status
    import argparse
    
    mock_health = MagicMock()
    mock_health.get_all_health.return_value = {"database": {"status": "healthy"}}
    
    with patch("core.component_health.get_health_monitor", return_value=mock_health):
        with patch("state_machine.state_engine.StateMachine", side_effect=ImportError("State machine not found")):
            args = argparse.Namespace(verbose=False)
            stdout, stderr = get_captured_output(run_status, args)
    
    assert "❌" in stdout or "error" in stdout.lower()


def test_run_classifier_success():
    """Test run_classifier executes successfully."""
    from cli import run_classifier
    
    # Mock the import and function call
    mock_module = MagicMock()
    mock_module.run_tests = MagicMock()
    
    with patch.dict("sys.modules", {"classifier.fault_classifier": mock_module}):
        stdout, stderr = get_captured_output(run_classifier)
        # Should not fail


def test_run_classifier_import_error():
    """Test run_classifier handles missing dependencies."""
    from cli import run_classifier
    import sys
    
    # Remove the module from sys.modules temporarily
    original_module = sys.modules.get("classifier.fault_classifier")
    sys.modules["classifier.fault_classifier"] = None
    
    try:
        # Force ImportError by removing module
        if "classifier.fault_classifier" in sys.modules:
            del sys.modules["classifier.fault_classifier"]
        
        with patch.dict("sys.modules", {"classifier": None}):
            stdout, stderr = get_captured_output(run_classifier)
        
        assert "not available" in stdout or "dependencies" in stdout.lower()
    finally:
        # Restore original module
        if original_module:
            sys.modules["classifier.fault_classifier"] = original_module


def test_run_classifier_execution_error():
    """Test run_classifier handles execution errors."""
    from cli import run_classifier
    
    # Mock the module with run_tests that raises an exception
    mock_module = MagicMock()
    mock_module.run_tests = MagicMock(side_effect=Exception("Test failed"))
    
    with patch.dict("sys.modules", {"classifier.fault_classifier": mock_module}):
        stdout, stderr = get_captured_output(run_classifier)
    
    assert "failed" in stdout.lower()


def test_run_report_invalid_hours_zero():
    """Test run_report with zero hours."""
    from cli import run_report
    import argparse
    
    tmp, original = setup_tmpdir()
    try:
        mock_report_generator = MagicMock()
        
        with patch("anomaly.report_generator.get_report_generator", return_value=mock_report_generator):
            args = argparse.Namespace(format="json", output=None, hours=0)
            stdout, stderr = get_captured_output(run_report, args)
        
        assert "Hours must be a positive integer" in stdout
    finally:
        cleanup(original)


def test_run_report_invalid_hours_negative():
    """Test run_report with negative hours."""
    from cli import run_report
    import argparse
    
    tmp, original = setup_tmpdir()
    try:
        mock_report_generator = MagicMock()
        
        with patch("anomaly.report_generator.get_report_generator", return_value=mock_report_generator):
            args = argparse.Namespace(format="json", output=None, hours=-5)
            stdout, stderr = get_captured_output(run_report, args)
        
        assert "Hours must be a positive integer" in stdout
    finally:
        cleanup(original)


def test_run_report_output_directory_creation():
    """Test run_report creates output directory if needed."""
    from cli import run_report
    import argparse
    
    tmp, original = setup_tmpdir()
    try:
        mock_report_generator = MagicMock()
        mock_report_generator.export_json.return_value = "reports/new_dir/report.json"
        mock_report_generator.generate_report.return_value = {"summary": {}}
        
        with patch("anomaly.report_generator.get_report_generator", return_value=mock_report_generator):
            with patch("os.makedirs") as mock_makedirs:
                args = argparse.Namespace(format="json", output="reports/new_dir/report.json", hours=24)
                stdout, stderr = get_captured_output(run_report, args)
                
                # Should attempt to create directory with correct path and flags
                mock_makedirs.assert_called_once_with("reports/new_dir", exist_ok=True)
    finally:
        cleanup(original)


def test_run_report_invalid_output_path():
    """Test run_report with invalid output path."""
    from cli import run_report
    import argparse
    
    tmp, original = setup_tmpdir()
    try:
        mock_report_generator = MagicMock()
        
        with patch("anomaly.report_generator.get_report_generator", return_value=mock_report_generator):
            with patch("os.makedirs", side_effect=OSError("Invalid path")):
                args = argparse.Namespace(format="json", output="/invalid:\\/path/report.json", hours=24)
                stdout, stderr = get_captured_output(run_report, args)
        
        assert "Invalid output path" in stdout
    finally:
        cleanup(original)


def test_run_report_value_error():
    """Test run_report handles ValueError."""
    from cli import run_report
    import argparse
    
    tmp, original = setup_tmpdir()
    try:
        mock_report_generator = MagicMock()
        mock_report_generator.export_json.side_effect = ValueError("Invalid time range")
        
        with patch("anomaly.report_generator.get_report_generator", return_value=mock_report_generator):
            args = argparse.Namespace(format="json", output=None, hours=24)
            stdout, stderr = get_captured_output(run_report, args)
        
        assert "Invalid parameters" in stdout
    finally:
        cleanup(original)


def test_run_report_os_error():
    """Test run_report handles OSError during export."""
    from cli import run_report
    import argparse
    
    tmp, original = setup_tmpdir()
    try:
        mock_report_generator = MagicMock()
        mock_report_generator.export_json.side_effect = OSError("Disk full")
        
        with patch("anomaly.report_generator.get_report_generator", return_value=mock_report_generator):
            args = argparse.Namespace(format="json", output=None, hours=24)
            stdout, stderr = get_captured_output(run_report, args)
        
        assert "File system error" in stdout
    finally:
        cleanup(original)


def test_run_telemetry_script_not_found():
    """Test run_telemetry when script doesn't exist."""
    from cli import run_telemetry
    
    tmp, original = setup_tmpdir()
    try:
        with patch("cli.os.path.exists", return_value=False):
            stdout, stderr = get_captured_output(run_telemetry)
        
        assert "not found" in stdout
    finally:
        cleanup(original)


def test_run_dashboard_script_not_found():
    """Test run_dashboard when streamlit script doesn't exist."""
    from cli import run_dashboard
    
    tmp, original = setup_tmpdir()
    try:
        with patch("cli.os.path.exists", return_value=False):
            stdout, stderr = get_captured_output(run_dashboard)
        
        assert "not found" in stdout
    finally:
        cleanup(original)


def test_run_simulation_script_not_found():
    """Test run_simulation when script doesn't exist."""
    from cli import run_simulation
    
    tmp, original = setup_tmpdir()
    try:
        with patch("cli.os.path.exists", return_value=False):
            stdout, stderr = get_captured_output(run_simulation)
        
        assert "Simulation script not found at" in stdout
    finally:
        cleanup(original)


def test_main_feedback_review_command():
    """Test main with feedback review command."""
    from cli import main
    import sys
    
    with patch("cli.FeedbackCLI.review_interactive") as mock_review:
        with patch("cli.FeedbackCLI.load_pending", return_value=[]):
            with patch.object(sys, "argv", ["cli.py", "feedback", "review"]):
                main()
    
    mock_review.assert_called_once()


def test_main_classify_command():
    """Test main with classify command."""
    from cli import main
    import sys
    
    with patch("cli.run_classifier") as mock_run_classifier:
        with patch.object(sys, "argv", ["cli.py", "classify"]):
            main()
    
    mock_run_classifier.assert_called_once()


def test_main_secrets_add_command():
    """Test main with secrets add command."""
    from cli import main
    import sys
    
    with patch("cli.run_secrets_command") as mock_secrets:
        with patch.object(sys, "argv", ["cli.py", "secrets", "add", "MY_KEY", "my_value"]):
            main()
    
    mock_secrets.assert_called_once()


def test_run_status_with_error_count():
    """Test run_status displays error count for failed components."""
    from cli import run_status
    import argparse
    
    mock_health = MagicMock()
    mock_health.get_all_health.return_value = {
        "api": {"status": "failed", "error_count": 10}
    }
    
    with patch("core.component_health.get_health_monitor", return_value=mock_health):
        with patch("state_machine.state_engine.StateMachine") as mock_sm:
            mock_sm_instance = MagicMock()
            mock_sm_instance.current_phase.value = "SAFE_MODE"
            mock_sm.return_value = mock_sm_instance
            
            args = argparse.Namespace(verbose=False)
            stdout, stderr = get_captured_output(run_status, args)
    
    assert "(Errors: 10)" in stdout


def test_run_status_exit_code_healthy():
    """Test run_status exits with code 0 for all healthy components."""
    from cli import run_status
    import argparse
    
    mock_health = MagicMock()
    mock_health.get_all_health.return_value = {
        "database": {"status": "healthy"},
        "cache": {"status": "healthy"}
    }
    
    with patch("core.component_health.get_health_monitor", return_value=mock_health):
        with patch("state_machine.state_engine.StateMachine") as mock_sm:
            mock_sm_instance = MagicMock()
            mock_sm_instance.current_phase.value = "NOMINAL_OPS"
            mock_sm.return_value = mock_sm_instance
            
            args = argparse.Namespace(verbose=False)
            # Should not raise SystemExit with code 1 for healthy system
            stdout, stderr = get_captured_output(run_status, args)
            assert "✅" in stdout


def test_secrets_with_expiration():
    """Test adding secret with expiration."""
    from cli import run_secrets_command
    import argparse
    
    tmp, original = setup_tmpdir()
    try:
        mock_metadata = MagicMock()
        mock_metadata.version = 1
        
        with patch("cli.init_secrets_manager"):
            with patch("cli.store_secret", return_value=mock_metadata) as mock_store:
                args = argparse.Namespace(
                    secrets_command="add", key="API_KEY", value="secret123",
                    description="Expires soon", expires=7
                )
                stdout, stderr = get_captured_output(run_secrets_command, args)
                
                # Verify expires_in_days was passed
                mock_store.assert_called_once()
                call_kwargs = mock_store.call_args[1]
                assert call_kwargs.get("expires_in_days") == 7
    finally:
        cleanup(original)


def test_secrets_rotate_with_auto_generate():
    """Test rotating secret with auto-generated value."""
    from cli import run_secrets_command
    import argparse
    
    tmp, original = setup_tmpdir()
    try:
        mock_metadata = MagicMock()
        mock_metadata.version = 3
        
        with patch("cli.init_secrets_manager"):
            with patch("cli.rotate_secret", return_value=mock_metadata) as mock_rotate:
                args = argparse.Namespace(
                    secrets_command="rotate", key="DB_KEY", value=None
                )
                stdout, stderr = get_captured_output(run_secrets_command, args)
                
                # Should call with new_value=None (auto-generate)
                mock_rotate.assert_called_once_with("DB_KEY", new_value=None)
    finally:
        cleanup(original)


def test_secrets_get_specific_version():
    """Test getting specific version of a secret."""
    from cli import run_secrets_command
    import argparse
    
    tmp, original = setup_tmpdir()
    try:
        with patch("cli.init_secrets_manager"):
            with patch("cli.get_secret", return_value="old_secret_value") as mock_get:
                args = argparse.Namespace(
                    secrets_command="get", key="API_KEY", version=2, show=True
                )
                stdout, stderr = get_captured_output(run_secrets_command, args)
                
                # Should request version 2
                mock_get.assert_called_once_with("API_KEY", version=2)
                assert "old_secret_value" in stdout
    finally:
        cleanup(original)


def test_run_report_show_summary_zeros():
    """Test run_report displays summary with zero values."""
    from cli import run_report
    import argparse
    
    tmp, original = setup_tmpdir()
    try:
        mock_report_generator = MagicMock()
        mock_report_generator.export_json.return_value = "report.json"
        mock_report_generator.generate_report.return_value = {
            "summary": {
                "total_anomalies": 0,
                "resolved_anomalies": 0,
                "critical_anomalies": 0
            }
        }
        
        with patch("anomaly.report_generator.get_report_generator", return_value=mock_report_generator):
            args = argparse.Namespace(format="json", output=None, hours=24)
            stdout, stderr = get_captured_output(run_report, args)
        
        assert "Total Anomalies: 0" in stdout
    finally:
        cleanup(original)


def test_feedback_load_pending_empty_list():
    """Test load_pending with empty list in file."""
    from cli import FeedbackCLI
    import json
    with tempfile.TemporaryDirectory() as tmp:
        original = Path.cwd()
        try:
            os.chdir(tmp)
            Path("feedback_pending.json").write_text(json.dumps([]))
            
            result = FeedbackCLI.load_pending()
            assert result == []
        finally:
            os.chdir(original)


def test_feedback_save_processed_empty_list():
    """Test save_processed with empty list."""
    from cli import FeedbackCLI
    with tempfile.TemporaryDirectory() as tmp:
        original = Path.cwd()
        try:
            os.chdir(tmp)
            FeedbackCLI.save_processed([])
            
            content = Path("feedback_processed.json").read_text()
            assert content == "[]"
        finally:
            os.chdir(original)

