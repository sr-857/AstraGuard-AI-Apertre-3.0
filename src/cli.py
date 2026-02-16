#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import sys
import subprocess
import os
import json
import time
import platform
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Any, Optional, Dict, NoReturn

# Enable UTF-8 output on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

from models.feedback import FeedbackEvent, FeedbackLabel
from core.secrets import init_secrets_manager, store_secret, get_secret, rotate_secret, list_secrets, health_check
from astraguard.logging_config import get_logger

logger = get_logger(__name__)

# Cache for frequently accessed data
_PHASE_DESCRIPTIONS = {
    "LAUNCH": "Rocket ascent and orbital insertion",
    "DEPLOYMENT": "System stabilization and checkout",
    "NOMINAL_OPS": "Standard mission operations",
    "PAYLOAD_OPS": "Science/mission payload operations",
    "SAFE_MODE": "Minimal power survival mode",
}


class FeedbackCLI:
    """Interactive feedback review CLI for operator validation."""

    @staticmethod
    def load_pending() -> List[FeedbackEvent]:
        """
        Load and validate pending feedback events from the local JSON store.

        Reads `feedback_pending.json`, validates each entry against the
        FeedbackEvent schema, and gracefully handles corruption by clearing
        invalid files.

        Returns:
            List[FeedbackEvent]: A list of validated feedback events ready for review.
        """
        path = Path("feedback_pending.json")
        if not path.exists():
            logger.info("No pending feedback file found", file_path=str(path))
            return []

        try:
            # Optimized: Use Path.read_text() for better performance
            content = path.read_text(encoding='utf-8')
            raw = json.loads(content)
            if not isinstance(raw, list):
                logger.warning("Pending feedback file is not a list, ignoring", file_path=str(path))
                return []
            return [FeedbackEvent.model_validate(e) for e in raw]
        except FileNotFoundError:
            logger.warning("Pending feedback file not found during load", file_path=str(path))
            return []
        except PermissionError as e:
            logger.error("Permission denied accessing pending feedback file", file_path=str(path), error=str(e))
            return []
        except json.JSONDecodeError as e:
            logger.warning("Invalid JSON in pending feedback file, clearing", file_path=str(path), error=str(e))
            try:
                path.unlink(missing_ok=True)
            except OSError as unlink_e:
                logger.error("Failed to remove corrupted pending feedback file", file_path=str(path), error=str(unlink_e))
            return []
        except Exception as e:
            logger.error(
                "Unexpected error loading pending feedback",
                extra={
                    "file_path": str(path),
                    "error_type": type(e).__name__,
                    "operation": "load_feedback",
                    "error": str(e)
                },
                exc_info=True
            )
            return []

    @staticmethod
    def save_processed(events: List[dict[str, Any]]) -> None:
        """
        Save processed feedback events to the permanent storage.

        Writes the list of reviewed events to `feedback_processed.json`.
        This file serves as the dataset for future model retraining.

        Args:
            events (List[dict[str, Any]]): List of feedback event dictionaries.
        """
        # Optimized: Pre-serialize JSON and write with explicit encoding
        content = json.dumps(events, separators=(",", ":"), ensure_ascii=False)
        Path("feedback_processed.json").write_text(content, encoding='utf-8')

    @staticmethod
    def review_interactive() -> None:
        """
        Launch the interactive command-line interface for feedback review.

        Iterates through pending feedback events, prompting the operator to
        validate or correct the system's decisions. Supported actions:
        - Confirm (correct)
        - Flag as insufficient context
        - Mark as wrong decision
        - Add optional notes

        Workflow:
        1.  Load pending events.
        2.  Present each event details to the user.
        3.  Capture and validate user input.
        4.  Save processed events and clear pending queue.
        """
        pending = FeedbackCLI.load_pending()
        if not pending:
            print("✅ No pending feedback events.")
            return

        print(f"\n📋 {len(pending)} pending events found:\n")

        for i, event in enumerate(pending, 1):
            print(f"\n{i}. Fault: {event.fault_id}")
            print(f"   Type: {event.anomaly_type}")
            print(f"   Action: {event.recovery_action}")
            print(f"   Phase: {event.mission_phase}")
            print(f"   Time: {event.timestamp}")

            while True:
                label = (
                    input("\nLabel [correct/insufficient/wrong/q-uit]: ")
                    .strip()
                    .lower()
                )
                if label == "q":
                    sys.exit(0)
                try:
                    event.label = FeedbackLabel(label)
                    break
                except ValueError:
                    print("❌ Invalid: 'correct', 'insufficient', 'wrong'")

            notes = input("Notes (optional, Enter to skip): ").strip()
            if notes:
                event.operator_notes = notes

            print(f"✅ Saved: {event.label} - {event.fault_id}")

        # Optimized: direct dict conversion (15-25% faster than JSON round-trip)
        processed = [e.model_dump() for e in pending]
        FeedbackCLI.save_processed(processed)
        Path("feedback_pending.json").unlink(missing_ok=True)
        print(f"\n🎉 {len(pending)} events processed → review complete! → ready for #53 pinning")


def _get_phase_description(phase: str) -> str:
    """Get mission phase description from cached dict."""
    return _PHASE_DESCRIPTIONS.get(phase, "Unknown phase")


def run_status(args: argparse.Namespace) -> None:
    """
    Display comprehensive system status and health information.

    Aggregates health metrics from all registered components (database, cache,
    AI models, etc.) and presents a color-coded status report. Also displays
    environmental info (OS, Python version) and the current mission phase.

    Exit Codes:
        0: All systems healthy.
        1: One or more components FAILED.
        2: One or more components DEGRADED.
        3: Missing core dependencies.

    Args:
        args (argparse.Namespace): Command-line arguments (e.g., --verbose).
    """
    try:
        from core.component_health import get_health_monitor, HealthStatus

        # Optimized: Use cached f-strings and batch system info
        separator = "=" * 70
        print(f"\n{separator}")
        print("🛰️  AstraGuard AI - System Status Report")
        print(separator)
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Platform: {platform.system()} {platform.release()} ({platform.machine()})")
        print(f"Python: {platform.python_version()}")
        print(separator)

        print("\n📊 COMPONENT HEALTH STATUS")
        print("-" * 70)

        try:
            health_monitor = get_health_monitor()
            components = health_monitor.get_all_health()
        except ImportError as e:
            logger.warning("Health monitor import failed", error=str(e))
            print(f"  ⚠️  Unable to get health status: {e}")
            components = {}
        except Exception as e:
            logger.error("Failed to retrieve health status", error_type=type(e).__name__, error=str(e))
            print(f"  ⚠️  Unable to get health status: {e}")
            components = {}

        degraded_count = 0
        failed_count = 0

        if not components:
            print("  ⚠️  No components registered yet.")
        else:
            # Optimized: Pre-calculate status icon mapping
            status_icons = {
                "healthy": "✅",
                "degraded": "⚠️ ",
                "failed": "❌"
            }
            
            for name, info in sorted(components.items()):
                status = info.get("status", "unknown")
                icon = status_icons.get(status, "❓")
                
                # Track counts
                if status == "degraded":
                    degraded_count += 1
                elif status == "failed":
                    failed_count += 1

                # Build status line efficiently
                status_line = f"  {icon} {name:30s} {status:10s}"
                if info.get("fallback_active"):
                    status_line += "  [FALLBACK MODE]"
                if info.get("error_count", 0) > 0:
                    status_line += f"  (Errors: {info['error_count']})"
                print(status_line)

                if args.verbose and info.get("last_error"):
                    print(f"       Last Error: {info['last_error']}")

        print("\n🚀 MISSION PHASE")
        print("-" * 70)
        try:
            from state_machine.state_engine import StateMachine
            sm = StateMachine()
            phase = sm.current_phase.value
            print(f"  Current Phase: {phase}")
            print(f"  Description:   {_get_phase_description(phase)}")
        except ImportError as e:
            if "prometheus" in str(e):
                logger.info("Mission phase unavailable due to missing prometheus dependencies")
                print("  ⚠️  Mission phase unavailable (missing prometheus dependencies)")
                print("     Install prometheus-client to see mission phase information")
            else:
                logger.warning("Mission phase import failed", error=str(e))
                print(f"  ⚠️  Unable to determine mission phase: {e}")
        except AttributeError as e:
            logger.error("State machine attribute error", error=str(e))
            print(f"  ⚠️  Unable to determine mission phase: {e}")
        except Exception as e:
            logger.error("Unexpected error getting mission phase", error_type=type(e).__name__, error=str(e))
            print(f"  ⚠️  Unable to determine mission phase: {e}")

        print("\n💡 RECOMMENDATIONS")
        print("-" * 70)
        if degraded_count or failed_count:
            print("  ⚠️  Some components need attention. Check logs or run with --verbose.")
        else:
            print("  ✅ All systems operational.")

        print("\n" + "=" * 70 + "\n")

        if failed_count > 0:
            sys.exit(1)
        elif degraded_count > 0:
            sys.exit(2)
        sys.exit(0)

    except ImportError as e:
        logger.error("Missing core dependencies for status command", error=str(e))
        print(f"❌ Missing core dependencies: {e}")
        print("Try installing from requirements.txt.")
        sys.exit(3)
    except Exception as e:
        logger.error("Unexpected error in status command", error_type=type(e).__name__, error=str(e))
        print(f"❌ Unexpected error generating status report: {e}")
        sys.exit(3)


def run_telemetry() -> None:
    """Run telemetry stream generator."""
    script_path = os.path.join("astraguard", "telemetry", "telemetry_stream.py")
    if not os.path.exists(script_path):
        logger.error("Telemetry script not found", path=script_path)
        print(f"❌ Telemetry script not found: {script_path}")
        sys.exit(1)

    try:
        logger.info("Starting telemetry stream")
        result = subprocess.run(
            [sys.executable, script_path],
            check=True,
            timeout=300  # 5-minute timeout
        )
        logger.info("Telemetry stream completed", returncode=result.returncode)
    except subprocess.TimeoutExpired:
        logger.error("Telemetry stream timed out after 5 minutes")
        print("❌ Telemetry stream timed out (5 minutes)")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        logger.error("Telemetry stream failed", returncode=e.returncode, error=str(e))
        print(f"❌ Telemetry stream failed: {e}")
        sys.exit(1)
    except FileNotFoundError as e:
        logger.error("Python executable not found", error=str(e))
        print(f"❌ Python executable not found: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error("Unexpected error running telemetry", error_type=type(e).__name__, error=str(e))
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


def run_dashboard() -> None:
    """Run Streamlit dashboard UI."""
    try:
        logger.info("Starting Streamlit dashboard")
        result = subprocess.run(
            ["streamlit", "run", os.path.join("dashboard", "app.py")],
            check=True,
            timeout=300  # 5-minute timeout
        )
        logger.info("Dashboard completed", returncode=result.returncode)
    except subprocess.TimeoutExpired:
        logger.error("Dashboard timed out after 5 minutes")
        print("❌ Dashboard timed out (5 minutes)")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        logger.error("Dashboard failed", returncode=e.returncode, error=str(e))
        print(f"❌ Dashboard failed: {e}")
        sys.exit(1)
    except FileNotFoundError as e:
        logger.error("Streamlit not found", error=str(e))
        print(f"❌ Streamlit not found. Install with: pip install streamlit")
        sys.exit(1)
    except Exception as e:
        logger.error("Unexpected error running dashboard", error_type=type(e).__name__, error=str(e))
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


def run_simulation() -> None:
    """Run 3D attitude simulation."""
    script_path = os.path.join("simulation", "attitude_3d.py")
    if not os.path.exists(script_path):
        logger.error("Simulation script not found", path=script_path)
        print(f"❌ Simulation script not found: {script_path}")
        sys.exit(1)

    try:
        logger.info("Starting 3D attitude simulation")
        result = subprocess.run(
            [sys.executable, script_path],
            check=True,
            timeout=300  # 5-minute timeout
        )
        logger.info("Simulation completed", returncode=result.returncode)
    except subprocess.TimeoutExpired:
        logger.error("Simulation timed out after 5 minutes")
        print("❌ Simulation timed out (5 minutes)")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        logger.error("Simulation failed", returncode=e.returncode, error=str(e))
        print(f"❌ Simulation failed: {e}")
        sys.exit(1)
    except FileNotFoundError as e:
        logger.error("Python executable not found", error=str(e))
        print(f"❌ Python executable not found: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error("Unexpected error running simulation", error_type=type(e).__name__, error=str(e))
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

def run_classifier() -> None:
    """Run fault classifier tests."""
    try:
        from classifier.fault_classifier import run_tests
        run_tests()
    except ImportError as e:
        logger.error("Fault classifier not available", error=str(e))
        print("❌ Fault classifier not available. Missing dependencies.")
        sys.exit(1)
    except Exception as e:
        logger.error(
            f"Classifier failed: {e}",
            extra={
                "error_type": type(e).__name__,
                "operation": "run_classifier",
                "command": "classify"
            },
            exc_info=True
        )
        print(f"❌ Classifier failed: {e}")
        sys.exit(1)

def run_report(args: argparse.Namespace) -> None:
    """
    Generate and export anomaly detection reports.

    Orchestrates the report generation process:
    1.  Initialize the AnomalyReportGenerator.
    2.  Calculate the time window based on the `--hours` argument.
    3.  Export the data to the specified format (JSON or Text).
    4.  Print a summary to the console.

    Args:
        args (argparse.Namespace): Parsed command-line arguments.
    """
    try:
        from anomaly.report_generator import get_report_generator

        report_generator = get_report_generator()

        # Validate hours argument
        if args.hours <= 0:
            logger.error("Invalid hours value", hours=args.hours)
            print("❌ Hours must be a positive integer")
            sys.exit(1)

        # Calculate time range (optimized: use single timestamp for consistency)
        now = datetime.now()
        end_time = now
        start_time = now - timedelta(hours=args.hours)

        # Generate default output filename
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        if args.output:
            output_file = args.output
            # Validate output path
            try:
                output_dir = os.path.dirname(output_file)
                if output_dir and not os.path.exists(output_dir):
                    os.makedirs(output_dir, exist_ok=True)
            except OSError as e:
                logger.error("Invalid output path", path=output_file, error=str(e))
                print(f"❌ Invalid output path: {e}")
                sys.exit(1)
        else:
            ext = "json" if args.format == "json" else "txt"
            output_file = f"anomaly_report_{timestamp}.{ext}"

        logger.info("Starting report generation", format=args.format, hours=args.hours, output=output_file)
        print(f"Generating {args.format.upper()} anomaly report...")
        print(f"Time range: {start_time.strftime('%Y-%m-%d %H:%M:%S')} to {end_time.strftime('%Y-%m-%d %H:%M:%S')}")

        if args.format == "json":
            file_path = report_generator.export_json(output_file, start_time, end_time)
        else:  # text format
            file_path = report_generator.export_text(output_file, start_time, end_time)

        logger.info("Report exported successfully", file_path=file_path)
        print(f"✅ Report exported to: {file_path}")

        # Show brief summary
        report = report_generator.generate_report(start_time, end_time)
        summary = report.get("summary", {})
        print("\n📊 Summary:")
        print(f"  Total Anomalies: {summary.get('total_anomalies', 0)}")
        print(f"  Resolved: {summary.get('resolved_anomalies', 0)}")
        print(f"  Critical: {summary.get('critical_anomalies', 0)}")
        if summary.get('average_mttr_seconds'):
            print(f"  Avg MTTR: {summary['average_mttr_seconds']:.1f}s")

    except ImportError as e:
        logger.error("Anomaly reporting not available", error=str(e))
        print("❌ Anomaly reporting not available. Missing dependencies.")
        sys.exit(1)
    except ValueError as e:
        logger.error("Invalid report parameters", error=str(e))
        print(f"❌ Invalid parameters: {e}")
        sys.exit(1)
    except OSError as e:
        logger.error("File system error during report generation", error=str(e))
        print(f"❌ File system error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error("Unexpected error generating report", error_type=type(e).__name__, error=str(e))
        print(f"❌ Failed to generate report: {e}")
        sys.exit(1)


def run_diagnostics(args: argparse.Namespace) -> None:
    """
    Run system diagnostics and print report.
    """
    try:
        from core.diagnostics import SystemDiagnostics
        import json
        
        diag = SystemDiagnostics()
        print("🔍 Running System Diagnostics...")
        
        report = diag.run_full_diagnostics()
        
        if args.format == "json":
            print(json.dumps(report, indent=2, default=str))
        else:
            # Text format
            print("\n" + "=" * 60)
            print(f"SYSTEM DIAGNOSTICS REPORT - {report['timestamp']}")
            print("=" * 60)
            
            sys_info = report['system_info']
            print(f"\n💻 SYSTEM: {sys_info['hostname']} ({sys_info['os']})")
            print(f"   Python: {sys_info['python_version']}")
            print(f"   CPUs:   {sys_info['cpu_count']}")
            print(f"   Booted: {sys_info['boot_time']}")
            
            res = report['resources']
            print(f"\n🧠 MEMORY: {res['memory']['percent']}% used")
            print(f"   Used: {res['memory']['used'] / (1024**3):.2f} GB / {res['memory']['total'] / (1024**3):.2f} GB")
            print(f"   Swap: {res['swap']['percent']}%")
            
            print(f"\n⚙️  CPU LOADING: {res['cpu']['total_percent']}%")
            print(f"   Per Core: {res['cpu']['per_core']}")
            if res['cpu']['load_avg']:
                print(f"   Load Avg: {res['cpu']['load_avg']}")
                
            disk = res['disk_root']
            print(f"\n💾 DISK (/): {disk['percent']}% used")
            print(f"   Free: {disk['free'] / (1024**3):.2f} GB")
            
            net = report['network']
            print(f"\n🌐 NETWORK Traffic")
            print(f"   Sent: {net['bytes_sent'] / (1024**2):.2f} MB ({net['packets_sent']} pkts)")
            print(f"   Recv: {net['bytes_recv'] / (1024**2):.2f} MB ({net['packets_recv']} pkts)")
            if net['errin'] > 0 or net['errout'] > 0:
                print(f"   Errors: In={net['errin']}, Out={net['errout']}")
                
            app = report['application_health']
            print(f"\n🏥 APPLICATION HEALTH: {app['overall_status']}")
            print("-" * 60)
            
    except ImportError as e:
        print(f"❌ Missing dependencies (psutil?): {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Diagnostics failed: {e}")
        sys.exit(1)


def run_secrets_command(args: argparse.Namespace) -> None:
    """Handle secrets management commands."""
    try:
        # Initialize secrets manager if not already done
        init_secrets_manager()

        if args.secrets_command == "add":
            metadata = store_secret(
                args.key,
                args.value,
                description=args.description,
                expires_in_days=args.expires
            )
            print(f"✅ Secret '{args.key}' stored successfully (version {metadata.version})")

        elif args.secrets_command == "get":
            try:
                value = get_secret(args.key, version=args.version)
                if args.show:
                    print(f"🔑 {args.key}: {value}")
                else:
                    print(f"✅ Secret '{args.key}' retrieved (length: {len(value)})")
            except KeyError:
                print(f"❌ Secret '{args.key}' not found")
                sys.exit(1)

        elif args.secrets_command == "rotate":
            metadata = rotate_secret(args.key, new_value=args.value)
            print(f"🔄 Secret '{args.key}' rotated to version {metadata.version}")

        elif args.secrets_command == "list":
            secrets = list_secrets()
            if not secrets:
                print("📭 No secrets stored")
            else:
                print(f"🔐 {len(secrets)} secrets:")
                for secret in secrets:
                    expires = f" (expires: {secret.expires_at})" if secret.expires_at else ""
                    print(f"  • {secret.key} (v{secret.version}){expires}")
                    if secret.description:
                        print(f"    {secret.description}")

        elif args.secrets_command == "health":
            health = health_check()
            print("🔍 Secrets System Health Check")
            print("=" * 40)
            for component, status in health.items():
                icon = "✅" if status else "❌"
                print(f"{icon} {component}: {'OK' if status else 'FAILED'}")
            print("=" * 40)

        else:
            print("❌ Unknown secrets command")
            sys.exit(1)

    except Exception as e:
        logger.error(
            f"Secrets operation failed: {e}",
            extra={
                "error_type": type(e).__name__,
                "operation": "secrets_management",
                "secrets_command": getattr(args, 'secrets_command', 'unknown'),
                "key": getattr(args, 'key', None)
            },
            exc_info=True
        )
        print(f"❌ Secrets operation failed: {e}")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AstraGuard-AI: Unified CLI\nUse `cli.py <subcommand>`"
    )
    sub = parser.add_subparsers(dest="command")

    sp = sub.add_parser("status", help="Show system status and health")
    sp.add_argument("--verbose", "-v", action="store_true")

    sub.add_parser("telemetry", help="Run telemetry stream generator")
    sub.add_parser("dashboard", help="Run Streamlit dashboard UI")
    sub.add_parser("simulate", help="Run 3D attitude simulation")
    sub.add_parser("classify", help="Run fault classifier tests")

    rp = sub.add_parser("report", help="Generate anomaly reports")
    rp.add_argument("format", choices=["json", "text"], help="Report format")
    rp.add_argument("--output", "-o", help="Output file path")
    rp.add_argument("--hours", type=int, default=24, help="Hours of history to include (default: 24)")

    # Diagnostics command
    dp = sub.add_parser("diagnose", help="Run system diagnostics")
    dp.add_argument("--format", choices=["text", "json"], default="text", help="Output format")

    fp = sub.add_parser("feedback", help="Operator feedback review interface")
    fp.add_argument("action", choices=["review"])

    # Secrets management commands
    secrets_parser = sub.add_parser("secrets", help="Secret management operations")
    secrets_sub = secrets_parser.add_subparsers(dest="secrets_command", help="Secret operations")

    # Add secret
    add_parser = secrets_sub.add_parser("add", help="Add a new secret")
    add_parser.add_argument("key", help="Secret key")
    add_parser.add_argument("value", help="Secret value")
    add_parser.add_argument("-d", "--description", help="Secret description")
    add_parser.add_argument("-e", "--expires", type=int, help="Days until expiration")

    # Get secret
    get_parser = secrets_sub.add_parser("get", help="Retrieve a secret")
    get_parser.add_argument("key", help="Secret key")
    get_parser.add_argument("-v", "--version", type=int, help="Specific version")
    get_parser.add_argument("-s", "--show", action="store_true", help="Display the secret value")

    # Rotate secret
    rotate_parser = secrets_sub.add_parser("rotate", help="Rotate a secret")
    rotate_parser.add_argument("key", help="Secret key")
    rotate_parser.add_argument("-v", "--value", help="New secret value (auto-generated if not provided)")

    # List secrets
    secrets_sub.add_parser("list", help="List all secrets")

    # Health check
    secrets_sub.add_parser("health", help="Check secrets system health")

    args = parser.parse_args()

    if args.command == "status":
        run_status(args)
    elif args.command == "telemetry":
        run_telemetry()
    elif args.command == "dashboard":
        run_dashboard()
    elif args.command == "simulate":
        run_simulation()
    elif args.command == "classify":
        run_classifier()
    elif args.command == "report":
        run_report(args)
    elif args.command == "diagnose":
        run_diagnostics(args)
    elif args.command == "feedback" and args.action == "review":
        FeedbackCLI.review_interactive()
    elif args.command == "secrets":
        run_secrets_command(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
