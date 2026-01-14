#!/usr/bin/env python3
"""
Issue #493: Thermal Cascade Demonstration

Demonstrates contagious thermal runaway spreading across swarm formation.
Patient zero thermal failure → heat coupling → secondary infections → cascade failure.

Formation geometry:
- SAT-A (patient zero) at origin
- SAT-B at 1.2km (close, high infection risk)
- SAT-C at 4.5km (far, low infection risk)
"""

import sys
import asyncio
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from astraguard.hil.simulator import StubSatelliteSimulator


def print_header(title):
    """Print section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def status_emoji(status: str) -> str:
    """Get symbol for thermal status."""
    if status == "critical":
        return "[CRIT]"
    elif status == "warning":
        return "[WARN]"
    else:
        return "[OK]"


async def demo_baseline():
    """Scenario 1: Baseline nominal conditions."""
    print_header("Scenario 1: BASELINE NOMINAL CONDITIONS")
    
    sat_a = StubSatelliteSimulator("SAT-A")
    sat_b = StubSatelliteSimulator("SAT-B")
    sat_c = StubSatelliteSimulator("SAT-C")
    
    print("\n3-satellite formation in LEO (nominal temperatures)")
    print("SAT-A <-1.2km-> SAT-B <-3.3km-> SAT-C\n")
    
    for step in range(5):
        t_a = (await sat_a.generate_telemetry()).thermal.battery_temp
        t_b = (await sat_b.generate_telemetry()).thermal.battery_temp
        t_c = (await sat_c.generate_telemetry()).thermal.battery_temp
        
        print(f"T+{step*10:3d}s: SAT-A {t_a:5.1f} C | SAT-B {t_b:5.1f} C | SAT-C {t_c:5.1f} C")
    
    print("\n[BASELINE] All satellites nominal (~15-20°C)")


async def demo_patient_zero():
    """Scenario 2: Patient zero thermal runaway."""
    print_header("Scenario 2: PATIENT ZERO RUNAWAY (SAT-A)")
    
    sat_a = StubSatelliteSimulator("SAT-A")
    sat_b = StubSatelliteSimulator("SAT-B")
    sat_c = StubSatelliteSimulator("SAT-C")
    
    # Formation setup
    sat_a.add_nearby_sat("SAT-B", 1.2)
    sat_a.add_nearby_sat("SAT-C", 4.5)
    sat_b.add_nearby_sat("SAT-A", 1.2)
    sat_c.add_nearby_sat("SAT-A", 4.5)
    
    # Warm up
    for _ in range(3):
        await sat_a.generate_telemetry()
        await sat_b.generate_telemetry()
        await sat_c.generate_telemetry()
    
    print("\n3-satellite formation in LEO:")
    print("SAT-A <-1.2km-> SAT-B <-3.3km-> SAT-C")
    print("\n[HEAT] SAT-A RADIATOR FAILURE (30% contagion)\n")
    
    # Inject fault
    await sat_a.inject_fault("thermal_runaway", severity=0.5)
    
    # Monitor cascade
    print("Time    SAT-A Status  Temp      SAT-B Status  Temp      SAT-C Status  Temp")
    print("-" * 75)
    
    for step in range(20):
        t_a = await sat_a.generate_telemetry()
        t_b = await sat_b.generate_telemetry()
        t_c = await sat_c.generate_telemetry()
        
        status_a = t_a.thermal.status
        status_b = t_b.thermal.status
        status_c = t_c.thermal.status
        
        emoji_a = status_emoji(status_a)
        emoji_b = status_emoji(status_b)
        emoji_c = status_emoji(status_c)
        
        print(f"T+{step*10:3d}s {status_a} {status_a:8s} {t_a.thermal.battery_temp:5.1f}C  "
              f"{status_b} {status_b:8s} {t_b.thermal.battery_temp:5.1f}C  "
              f"{status_c} {status_c:8s} {t_c.thermal.battery_temp:5.1f}C")
    
    # Check infection status
    fault_a = sat_a.thermal_sim._thermal_fault
    if fault_a:
        print(f"\nSAT-A Cascade State:")
        print(f"  Active: {fault_a.active}")
        print(f"  Infected neighbors: {fault_a.infected_neighbors}")
        print(f"  Contagion rate: {fault_a.contagion_rate:.2f}")


async def demo_close_formation_cascade():
    """Scenario 3: Close formation with high infection risk."""
    print_header("Scenario 3: CLOSE FORMATION CASCADE (1km spacing)")
    
    satellites = {}
    for name in ["SAT-A", "SAT-B", "SAT-C", "SAT-D"]:
        satellites[name] = StubSatelliteSimulator(name)
    
    # Close formation: 1km linear spacing
    distances = {
        "SAT-A": [("SAT-B", 1.0), ("SAT-C", 2.0), ("SAT-D", 3.0)],
        "SAT-B": [("SAT-A", 1.0), ("SAT-C", 1.0), ("SAT-D", 2.0)],
        "SAT-C": [("SAT-A", 2.0), ("SAT-B", 1.0), ("SAT-D", 1.0)],
        "SAT-D": [("SAT-A", 3.0), ("SAT-B", 2.0), ("SAT-C", 1.0)],
    }
    
    for sat_name, neighbors in distances.items():
        for neighbor_name, distance in neighbors:
            satellites[sat_name].add_nearby_sat(neighbor_name, distance)
    
    print("\nClose formation (1km spacing) - 4 satellites in tight array")
    print("SAT-A <-1km-> SAT-B <-1km-> SAT-C <-1km-> SAT-D\n")
    
    # Warmup
    for _ in range(2):
        for sat in satellites.values():
            await sat.generate_telemetry()
    
    print("[HEAT] INJECTING RUNAWAY ON SAT-A (50% contagion)\n")
    await satellites["SAT-A"].inject_fault("thermal_runaway", severity=0.5)
    
    print("Time    Status/Temp Legend: RED=CRITICAL >60C | YELLOW=WARNING 45-60C | GREEN=NOMINAL <45C\n")
    print("T+Xs:   SAT-A        SAT-B        SAT-C        SAT-D")
    print("-" * 60)
    
    for step in range(15):
        temps = {}
        for name, sat in satellites.items():
            t = await sat.generate_telemetry()
            temps[name] = (status_emoji(t.thermal.status), t.thermal.battery_temp)
        
        line = f"T+{step*10:3d}s: "
        for name in ["SAT-A", "SAT-B", "SAT-C", "SAT-D"]:
            emoji, temp = temps[name]
            line += f" {emoji}{temp:5.1f}C    "
        print(line)
    
    # Final cascade state
    print("\nCascade Status:")
    for name, sat in satellites.items():
        fault = sat.thermal_sim._thermal_fault
        if fault and fault.active:
            print(f"  {name}: Infected {fault.infected_neighbors}")


async def demo_mixed_distance_formation():
    """Scenario 4: Mixed distances (realistic operational formation)."""
    print_header("Scenario 4: MIXED DISTANCE FORMATION")
    
    sat_a = StubSatelliteSimulator("SAT-A")  # Patient zero
    sat_b = StubSatelliteSimulator("SAT-B")  # Close
    sat_c = StubSatelliteSimulator("SAT-C")  # Medium
    sat_d = StubSatelliteSimulator("SAT-D")  # Far
    
    # Realistic formation
    sat_a.add_nearby_sat("SAT-B", 1.5)
    sat_a.add_nearby_sat("SAT-C", 2.8)
    sat_a.add_nearby_sat("SAT-D", 4.8)
    
    print("\nMixed formation distances:")
    print("  SAT-A (origin) -> SAT-B (1.5km, close)")
    print("  SAT-A (origin) -> SAT-C (2.8km, medium)")
    print("  SAT-A (origin) -> SAT-D (4.8km, far edge)")
    print("\n[HEAT] INJECTING RUNAWAY (SEVERE, 70% contagion)\n")
    
    # Warmup
    for _ in range(2):
        await sat_a.generate_telemetry()
        await sat_b.generate_telemetry()
        await sat_c.generate_telemetry()
        await sat_d.generate_telemetry()
    
    # Severe fault
    await sat_a.inject_fault("thermal_runaway", severity=1.0)
    
    print("Time    SAT-A (Patient Zero) | SAT-B (Close) | SAT-C (Medium) | SAT-D (Far)")
    print("-" * 75)
    
    for step in range(18):
        t_a = (await sat_a.generate_telemetry()).thermal
        t_b = (await sat_b.generate_telemetry()).thermal
        t_c = (await sat_c.generate_telemetry()).thermal
        t_d = (await sat_d.generate_telemetry()).thermal
        
        print(f"T+{step*10:3d}s: {status_emoji(t_a.status)} {t_a.battery_temp:5.1f}C "
              f"| {status_emoji(t_b.status)} {t_b.battery_temp:5.1f}C "
              f"| {status_emoji(t_c.status)} {t_c.battery_temp:5.1f}C "
              f"| {status_emoji(t_d.status)} {t_d.battery_temp:5.1f}C")
    
    print("\nAnalysis:")
    fault = sat_a.thermal_sim._thermal_fault
    if fault:
        print(f"  SAT-A infected: {fault.infected_neighbors}")
        print(f"  High contagion (0.7) spreads to close satellites")
        print(f"  Far satellite (>4.5km) unlikely to get infected")


async def demo_recovery_scenario():
    """Scenario 5: Coordinated recovery policy."""
    print_header("Scenario 5: COORDINATED RECOVERY POLICY")
    
    sat_a = StubSatelliteSimulator("SAT-A")
    
    print("\n1. Autonomous thermal management triggered")
    print("2. SAT-A enters safe mode, initiates emergency restart")
    print("3. Radiator mechanisms reset (simulated)\n")
    
    # Warmup
    for _ in range(3):
        await sat_a.generate_telemetry()
    
    print("Phase 1: Thermal runaway active (30 seconds)")
    await sat_a.inject_fault("thermal_runaway", severity=0.5)
    
    print("Time    Temp      Status        Fault State")
    print("-" * 50)
    
    for step in range(10):
        t = await sat_a.generate_telemetry()
        fault = sat_a.thermal_sim._thermal_fault
        fault_state = "ACTIVE" if (fault and not fault.is_expired()) else "RECOVERED"
        
        print(f"T+{step*10:3d}s: {t.thermal.battery_temp:5.1f}C  {t.thermal.status:10s} {fault_state}")
    
    print("\nPhase 2: Fault duration expired, auto-recovery")
    
    for step in range(10, 15):
        t = await sat_a.generate_telemetry()
        fault = sat_a.thermal_sim._thermal_fault
        fault_state = "EXPIRED" if (fault and fault.is_expired()) else "ACTIVE"
        
        print(f"T+{step*10:3d}s: {t.thermal.battery_temp:5.1f}C  {t.thermal.status:10s} {fault_state}")
    
    print("\nRecovery Timeline:")
    print("  T+0s: Fault injected, radiator capacity drops to 10%")
    print("  T+0-300s: Cascade active, attempting neighbor infection")
    print("  T+300s: Fault expires, auto-recovery initiated")
    print("  T+300+: Temperature gradually decreases as radiator recovers")


async def main():
    """Run all demonstrations."""
    print("\n" + "=" * 70)
    print("  ASTRAGUARD-AI: THERMAL CASCADE DEMONSTRATION (Issue #493)")
    print("  Contagious Thermal Runaway Across Formation")
    print("=" * 70)
    
    try:
        await demo_baseline()
        await demo_patient_zero()
        await demo_close_formation_cascade()
        await demo_mixed_distance_formation()
        await demo_recovery_scenario()
        
        print_header("DEMONSTRATION COMPLETE")
        print("""
Key Insights:
1. Radiator Failure: Primary infection drops radiator to 10% capacity
2. Heat Coupling: Nearby infected satellites add 2W+ heat each
3. Distance Effect: <2km = ~40% infection risk, >4km = <5% risk
4. Formation Risk: Tight formations (1km) face cascade failure
5. Auto-Recovery: Fault expires after 10 minutes, triggers recovery
6. Swarm Vulnerability: One satellite threatens entire formation

Coordination Strategies:
- Thermal load shedding (reduce base_heat_w by stopping non-critical systems)
- Formation separation (increase distance >5km to break cascade)
- Radiator rotation (deploy backup radiators)
- Propulsive maneuver (burn fuel to increase drag/cooling)

AstraGuard agents must implement coordinated thermal management!
        """)
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
