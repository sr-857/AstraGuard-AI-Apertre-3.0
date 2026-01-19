"""HIL Scenario Execution Demo - Run YAML scenarios autonomously."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from astraguard.hil.scenarios.parser import run_scenario_file


def demo_scenario_execution():
    """Demonstrate full scenario execution from YAML."""
    print()
    print("=" * 70)
    print("HIL SCENARIO EXECUTION DEMO")
    print("=" * 70)
    print()

    # Scenario 1: Nominal formation
    print("[1] NOMINAL FORMATION TEST (20x speed)")
    print("-" * 70)
    print("Running: nominal.yaml")
    print("  - 2 satellites in formation")
    print("  - No faults injected")
    print("  - Duration: 900s")
    print()

    try:
        result1 = run_scenario_file(
            "astraguard/hil/scenarios/sample_scenarios/nominal.yaml",
            speed=20.0,
            verbose=True
        )

        print()
        print("RESULTS:")
        print(f"  Status: {'[OK] PASS' if result1['success'] else '[X] FAIL'}")
        print(f"  Simulated time: {result1['simulated_time_s']:.0f}s")
        print(f"  Wall time: {result1['execution_time_s']:.2f}s")
        print(f"  Speed efficiency: {result1['simulated_time_s'] / result1['execution_time_s']:.1f}x")
        print(f"  Log entries: {len(result1['execution_log'])}")

        # Show final criteria
        final = result1["final_criteria"]
        print()
        print("FINAL CRITERIA:")
        for sat_id, sat_results in final["per_sat"].items():
            status = "[+]" if sat_results["pass"] else "[*]"
            print(f"  {status} {sat_id}")
            if "criteria" in sat_results:
                for criterion, passed in sat_results["criteria"].items():
                    print(f"      {criterion}: {'[OK]' if passed else '[!]'}")
    except Exception as e:
        print(f"[ERROR] Failed to execute nominal scenario: {e}")
        import traceback
        traceback.print_exc()

    print()
    print()

    # Scenario 2: Thermal cascade
    print("[2] THERMAL CASCADE TEST (10x speed)")
    print("-" * 70)
    print("Running: cascade_fail.yaml")
    print("  - 3 satellites in formation (1.2km spacing)")
    print("  - Thermal runaway on SAT1 at t=60s")
    print("  - Severity: 70% (catastrophic radiator failure)")
    print("  - Duration: 1200s test")
    print()

    try:
        result2 = run_scenario_file(
            "astraguard/hil/scenarios/sample_scenarios/cascade_fail.yaml",
            speed=10.0,
            verbose=True
        )

        print()
        print("RESULTS:")
        print(f"  Status: {'[OK] PASS' if result2['success'] else '[*] DEGRADED'}")
        print(f"  Simulated time: {result2['simulated_time_s']:.0f}s")
        print(f"  Wall time: {result2['execution_time_s']:.2f}s")
        print(f"  Speed efficiency: {result2['simulated_time_s'] / result2['execution_time_s']:.1f}x")
        print(f"  Log entries: {len(result2['execution_log'])}")

        # Show final criteria
        final = result2["final_criteria"]
        print()
        print("FINAL CRITERIA:")
        for sat_id, sat_results in final["per_sat"].items():
            status = "[+]" if sat_results["pass"] else "[*]"
            print(f"  {status} {sat_id}")
            if "criteria" in sat_results:
                for criterion, passed in sat_results["criteria"].items():
                    print(f"      {criterion}: {'[OK]' if passed else '[!]'}")

        # Show cascade progression
        print()
        print("CASCADE PROGRESSION:")
        log = result2["execution_log"]
        if log:
            # Find fault injection time
            for i, entry in enumerate(log):
                if entry["status"].active_faults:
                    print(f"  T+{entry['time_s']:.0f}s: Faults injected - {entry['status'].active_faults}")
                    if i + 1 < len(log):
                        next_entry = log[i + 1]
                        print(f"  T+{next_entry['time_s']:.0f}s: Cascade status: {next_entry['status'].criteria_pass}")
                    break

    except Exception as e:
        print(f"[ERROR] Failed to execute cascade scenario: {e}")
        import traceback
        traceback.print_exc()

    print()
    print()

    # Summary
    print("[3] EXECUTION SUMMARY")
    print("-" * 70)
    print("[OK] Scenario-driven HIL testing operational")
    print()
    print("Supported features:")
    print("  + Load scenarios from YAML files")
    print("  + Auto-provision simulators with formation geometry")
    print("  + Precise fault injection timing (±0.5s tolerance)")
    print("  + Real-time success criteria monitoring")
    print("  + Configurable playback speed (1x - 100x+)")
    print("  + Execution logging for audit trails")
    print()
    print("Next steps:")
    print("  1. Create custom scenarios in astraguard/hil/scenarios/sample_scenarios/")
    print("  2. Use run_scenario_file() or asyncio.run(execute_scenario_file())")
    print("  3. Integrate with CI/CD for regression testing")
    print("  4. Use 20x speed for hackathon demos (complete in 45s)")
    print()
    print("=" * 70)
    print()


def demo_custom_scenario():
    """Show how to create and run a custom scenario."""
    print()
    print("=" * 70)
    print("CUSTOM SCENARIO TEMPLATE")
    print("=" * 70)
    print()

    template = """
# Save as: astraguard/hil/scenarios/sample_scenarios/custom.yaml

name: "custom_test"
description: "Your scenario description"
duration_s: 600

satellites:
  - id: "SAT-A"
    initial_position_km: [0, 0, 420]
    neighbors: ["SAT-B"]
  
  - id: "SAT-B"
    initial_position_km: [2.0, 0, 420]
    neighbors: ["SAT-A"]

fault_sequence:
  - type: power_brownout
    satellite: SAT-A
    start_time_s: 100
    severity: 0.6
    duration_s: 300

success_criteria:
  max_nadir_error_deg: 10.0
  min_battery_soc: 0.3
  max_temperature_c: 60.0
  max_packet_loss: 0.2

# Run with:
# from astraguard.hil.scenarios.parser import run_scenario_file
# result = run_scenario_file("astraguard/hil/scenarios/sample_scenarios/custom.yaml", speed=20.0)
"""

    print(template)
    print("=" * 70)
    print()


if __name__ == "__main__":
    print()
    demo_scenario_execution()
    demo_custom_scenario()
    print()
    print("[INFO] Scenario-driven HIL testing now LIVE!")
    print("[INFO] One YAML file = full swarm chaos simulation!")
    print()
