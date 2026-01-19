#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import sys
import subprocess
import os
import json
import time
from datetime import datetime
from pathlib import Path
from typing import List, Any, Optional

# Enable UTF-8 output on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

from models.feedback import FeedbackEvent, FeedbackLabel
from core.secrets import init_secrets_manager, store_secret, get_secret, rotate_secret, list_secrets, health_check


class FeedbackCLI:
    """Interactive feedback review CLI for operator validation."""

    @staticmethod
    def load_pending() -> List[FeedbackEvent]:
        """Load and validate pending events from feedback_pending.json."""
        path = Path("feedback_pending.json")
        if not path.exists():
            return []

        try:
            with open(path) as f:
                raw = json.load(f)
            if not isinstance(raw, list):
                return []
            return [FeedbackEvent.model_validate(e) for e in raw]
        except (json.JSONDecodeError, Exception):
            print("⚠️  Invalid pending store, cleared.")
            path.unlink(missing_ok=True)
            return []

    @staticmethod
    def save_processed(events: List[dict[str, Any]]) -> None:
        """Save processed events to feedback_processed.json."""
        Path("feedback_processed.json").write_text(
            json.dumps(events, separators=(",", ":"))
        )

    @staticmethod
    def review_interactive() -> None:
        """Main interactive review loop for operator feedback."""
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

        processed = [json.loads(e.model_dump_json()) for e in pending]
        FeedbackCLI.save_processed(processed)
        Path("feedback_pending.json").unlink(missing_ok=True)
        print(f"\n🎉 {len(pending)} events processed → review complete! → ready for #53 pinning")


def _get_phase_description(phase: str) -> str:
    descriptions = {
        "LAUNCH": "Rocket ascent and orbital insertion",
        "DEPLOYMENT": "System stabilization and checkout",
        "NOMINAL_OPS": "Standard mission operations",
        "PAYLOAD_OPS": "Science/mission payload operations",
        "SAFE_MODE": "Minimal power survival mode",
    }
    return descriptions.get(phase, "Unknown phase")


def run_status(args: argparse.Namespace) -> None:
    """Display comprehensive system status and health information."""
    try:
        from core.component_health import get_health_monitor, HealthStatus
        import platform

        print("\n" + "=" * 70)
        print("🛰️  AstraGuard AI - System Status Report")
        print("=" * 70)
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Platform: {platform.system()} {platform.release()} ({platform.machine()})")
        print(f"Python: {platform.python_version()}")
        print("=" * 70)

        print("\n📊 COMPONENT HEALTH STATUS")
        print("-" * 70)

        try:
            health_monitor = get_health_monitor()
            components = health_monitor.get_all_health()
        except Exception as e:
            print(f"  ⚠️  Unable to get health status: {e}")
            components = {}

        degraded_count = 0
        failed_count = 0

        if not components:
            print("  ⚠️  No components registered yet.")
        else:
            for name, info in sorted(components.items()):
                status = info.get("status", "unknown")
                if status == "healthy":
                    icon = "✅"
                elif status == "degraded":
                    icon = "⚠️ "
                    degraded_count += 1
                elif status == "failed":
                    icon = "❌"
                    failed_count += 1
                else:
                    icon = "❓"

                print(f"  {icon} {name:30s} {status:10s}", end="")
                if info.get("fallback_active"):
                    print("  [FALLBACK MODE]", end="")
                if info.get("error_count", 0) > 0:
                    print(f"  (Errors: {info['error_count']})", end="")
                print()

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
                print("  ⚠️  Mission phase unavailable (missing prometheus dependencies)")
                print("     Install prometheus-client to see mission phase information")
            else:
                print(f"  ⚠️  Unable to determine mission phase: {e}")
        except Exception as e:
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
        print(f"❌ Missing core dependencies: {e}")
        print("Try installing from requirements.txt.")
        sys.exit(3)


def run_telemetry() -> None:
    subprocess.run(
        [sys.executable, os.path.join("astraguard", "telemetry", "telemetry_stream.py")]
    )


def run_dashboard() -> None:
    subprocess.run(["streamlit", "run", os.path.join("dashboard", "app.py")])


def run_simulation() -> None:
    subprocess.run([sys.executable, os.path.join("simulation", "attitude_3d.py")])


def run_report(args: argparse.Namespace) -> None:
    """Generate and export anomaly reports."""
    try:
        from anomaly.report_generator import get_report_generator
        from datetime import datetime, timedelta
        
        report_generator = get_report_generator()
        
        # Calculate time range
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=args.hours)
        
        # Generate default output filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if args.output:
            output_file = args.output
        else:
            ext = "json" if args.format == "json" else "txt"
            output_file = f"anomaly_report_{timestamp}.{ext}"
        
        print(f"Generating {args.format.upper()} anomaly report...")
        print(f"Time range: {start_time.strftime('%Y-%m-%d %H:%M:%S')} to {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if args.format == "json":
            file_path = report_generator.export_json(output_file, start_time, end_time)
        else:  # text format
            file_path = report_generator.export_text(output_file, start_time, end_time)
        
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
        
    except ImportError:
        print("❌ Anomaly reporting not available. Missing dependencies.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Failed to generate report: {e}")
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
    elif args.command == "feedback" and args.action == "review":
        FeedbackCLI.review_interactive()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
