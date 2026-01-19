"""HIL Scenario Schema Demo - Shows scenario loading and validation workflow."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from astraguard.hil.scenarios import (
    load_scenario,
    validate_scenario,
    SCENARIO_SCHEMA,
)


def demo_scenarios():
    """Demonstrate scenario loading and validation."""
    print("="*70)
    print("HIL TEST SCENARIO SCHEMA DEMO")
    print("="*70)
    print()

    # Load scenarios
    print("[1] LOADING SCENARIOS")
    print("-" * 70)

    try:
        nominal = load_scenario(
            "astraguard/hil/scenarios/sample_scenarios/nominal.yaml"
        )
        print("[OK] Loaded nominal.yaml")
        print(f"     Name: {nominal.name}")
        print(f"     Description: {nominal.description}")
        print(f"     Duration: {nominal.duration_s}s")
        print(f"     Satellites: {len(nominal.satellites)}")
        print(f"     Faults: {len(nominal.fault_sequence)}")
    except Exception as e:
        print(f"[ERROR] Failed to load nominal.yaml: {e}")
        nominal = None

    print()

    try:
        cascade = load_scenario(
            "astraguard/hil/scenarios/sample_scenarios/cascade_fail.yaml"
        )
        print("[OK] Loaded cascade_fail.yaml")
        print(f"     Name: {cascade.name}")
        print(f"     Description: {cascade.description}")
        print(f"     Duration: {cascade.duration_s}s")
        print(f"     Satellites: {len(cascade.satellites)}")
        print(f"     Faults: {len(cascade.fault_sequence)}")
    except Exception as e:
        print(f"[ERROR] Failed to load cascade_fail.yaml: {e}")
        cascade = None

    print()
    print()

    # Validate scenarios
    print("[2] VALIDATING SCENARIOS")
    print("-" * 70)

    scenarios = []
    if nominal:
        scenarios.append(("nominal.yaml", nominal))
    if cascade:
        scenarios.append(("cascade_fail.yaml", cascade))

    for scenario_name, scenario in scenarios:
        result = validate_scenario(scenario)
        status = "[OK] PASS" if result["valid"] else "[FAIL] INVALID"
        print(f"{status} {scenario_name}")
        print(f"      Satellites: {result['satellite_count']}")
        print(f"      Faults: {result['fault_count']}")

        if result["issues"]:
            print(f"      Issues:")
            for issue in result["issues"]:
                print(f"        - {issue}")
        print()

    print()

    # Detailed inspection
    if nominal:
        print("[3] NOMINAL SCENARIO DETAILS")
        print("-" * 70)
        print(f"Name: {nominal.name}")
        print(f"Description: {nominal.description}")
        print()
        print("Satellites:")
        for sat in nominal.satellites:
            print(f"  {sat.id}")
            print(f"    Position: {sat.initial_position_km}")
            print(f"    Neighbors: {sat.neighbors if sat.neighbors else '(none)'}")

        print()
        print("Success Criteria:")
        print(f"  Max nadir error: {nominal.success_criteria.max_nadir_error_deg}°")
        print(f"  Min battery SOC: {nominal.success_criteria.min_battery_soc:.1%}")
        print(f"  Max temperature: {nominal.success_criteria.max_temperature_c}°C")
        print(f"  Max packet loss: {nominal.success_criteria.max_packet_loss:.1%}")
        print()
        print()

    # Cascade with faults
    if cascade:
        print("[4] CASCADE SCENARIO WITH FAULTS")
        print("-" * 70)
        print(f"Name: {cascade.name}")
        print(f"Description: {cascade.description}")
        print()
        print("Formation (3-satellite constellation):")
        for sat in cascade.satellites:
            print(f"  {sat.id}")
            print(f"    Position: {sat.initial_position_km} km")
            print(f"    Neighbors: {sat.neighbors if sat.neighbors else '(none)'}")

        print()
        print(f"Fault Sequence ({len(cascade.fault_sequence)} injection{'s' if len(cascade.fault_sequence) != 1 else ''}):")
        for i, fault in enumerate(cascade.fault_sequence, 1):
            print(f"  [{i}] {fault.type.value}")
            print(f"      Target: {fault.satellite}")
            print(f"      Start: {fault.start_time_s}s")
            print(f"      Duration: {fault.duration_s}s")
            print(f"      Severity: {fault.severity:.1%}")

        print()
        print("Success Criteria (Degraded Mode):")
        print(f"  Max nadir error: {cascade.success_criteria.max_nadir_error_deg}°")
        print(f"  Min battery SOC: {cascade.success_criteria.min_battery_soc:.1%}")
        print(f"  Max temperature: {cascade.success_criteria.max_temperature_c}°C")
        print(f"  Max packet loss: {cascade.success_criteria.max_packet_loss:.1%}")
        print()
        print()

    # Schema documentation
    print("[5] SCENARIO SCHEMA REFERENCE")
    print("-" * 70)
    print(SCENARIO_SCHEMA)
    print()
    print()

    # Summary
    print("[6] TEST EXECUTION READINESS")
    print("-" * 70)
    all_valid = all(validate_scenario(s[1])["valid"] for s in scenarios)
    if all_valid:
        print("[OK] All scenarios validated and ready for execution")
        print()
        print("Next steps:")
        print("  1. Use load_scenario() to parse YAML")
        print("  2. Create StubSatelliteSimulator with scenario.satellites")
        print("  3. Register neighbors via add_nearby_sat()")
        print("  4. Schedule faults at specified times")
        print("  5. Validate against success_criteria")
        print("  6. Log results for audit trail")
    else:
        print("[FAIL] Validation errors detected - review above")
    print()
    print("="*70)


def demo_schema():
    """Show YAML schema example."""
    print()
    print("="*70)
    print("EXAMPLE YAML SCHEMA")
    print("="*70)
    print()

    example = """
# HIL Test Scenario - Thermal Cascade Formation Test

name: "thermal_cascade_test"
description: "Patient zero radiator failure spreading across formation"

duration_s: 1200  # 20 minute test

satellites:
  - id: "SAT1"
    initial_position_km: [0, 0, 420]
    neighbors: ["SAT2", "SAT3"]
  
  - id: "SAT2"
    initial_position_km: [1.2, 0, 420]  # 1.2 km away (close)
    neighbors: ["SAT1"]
  
  - id: "SAT3"
    initial_position_km: [3.5, 0, 420]  # 3.5 km away (medium)
    neighbors: ["SAT1"]

fault_sequence:
  - type: thermal_runaway
    satellite: SAT1
    start_time_s: 60        # Inject at t=60s
    severity: 0.7           # 70% radiator failure (catastrophic)
    duration_s: 600         # Fault active for 10 minutes

success_criteria:
  max_nadir_error_deg: 8.0      # Allow some attitude drift
  min_battery_soc: 0.4          # Battery can drop to 40%
  max_temperature_c: 65.0       # Critical temp threshold
  max_packet_loss: 0.15         # Allow up to 15% comms loss
"""
    print(example)
    print("="*70)


if __name__ == "__main__":
    print()
    demo_scenarios()
    demo_schema()
    print()
    print("[INFO] Scenario-driven HIL testing now enabled!")
    print("[INFO] Create .yaml files in hil/scenarios/sample_scenarios/")
    print("[INFO] Use load_scenario() + validate_scenario() in your tests")
    print()
