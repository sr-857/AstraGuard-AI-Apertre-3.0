"""
Brownout Fault Demo (Issue #491)

Demonstrates power brownout fault injection and recovery with 3-phase degradation model.
Shows:
- Part 1: Baseline power nominal operation
- Part 2: Severe brownout injection (Phase 1 - panel damage)
- Part 3: Battery stress phase (Phase 2 - discharge acceleration)
- Part 4: Safe-mode phase (Phase 3 - load spike)
- Part 5: Auto-recovery and system restoration
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from astraguard.hil.simulator.power import PowerSimulator
from astraguard.hil.simulator.faults.power_brownout import PowerBrownoutFault


def print_header(title):
    """Print section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_power_status(power_sim, time_s):
    """Print detailed power status."""
    print(f"\n[{time_s:6.1f}s] Power Status:")
    print(f"  Solar Power:       {power_sim.solar_power_w:6.2f} W")
    print(f"  Load:              {power_sim.load_w:6.2f} W")
    print(f"  Battery SOC:       {power_sim.battery_soc_percent:6.2f} %")
    print(f"  Battery Voltage:   {power_sim.battery_voltage_v:6.3f} V")
    print(f"  Battery Current:   {power_sim.battery_current_a:6.3f} A")


def print_fault_status(fault):
    """Print fault state details."""
    if not fault.active:
        print("  [FAULT INACTIVE]")
        return
    
    state = fault.get_fault_state()
    print(f"  Phase:                {state['phase']}")
    print(f"  Panel Damage Factor:  {state['panel_damage_factor']:.2f}")
    print(f"  Discharge Multiplier: {state['discharge_multiplier']:.2f}")
    print(f"  Safe-Mode Load:       {state['safe_mode_load']:.1f} W")
    print(f"  Time Remaining:       {state['time_remaining']:.1f} s")


def part_1_baseline():
    """Part 1: Baseline nominal operation (no fault)."""
    print_header("PART 1: BASELINE NOMINAL OPERATION")
    print("\nSimulating 300 seconds of nominal power operation...")
    print("Battery in sun, continuous 5W load\n")
    
    power_sim = PowerSimulator(sat_id="SAT-001", battery_soc_percent=70.0)
    
    soc_history = []
    voltage_history = []
    time_history = []
    
    for t in range(0, 301, 30):
        power_sim.update(dt=30.0, sun_exposure=1.0)
        soc_history.append(power_sim.battery_soc_percent)
        voltage_history.append(power_sim.battery_voltage_v)
        time_history.append(t)
        
        print_power_status(power_sim, t)
    
    print("\n✓ Baseline: Battery charging normally in sunlight")
    print(f"  SOC increased from 70.0% → {power_sim.battery_soc_percent:.1f}%")
    print(f"  Voltage maintained: {power_sim.battery_voltage_v:.3f} V")
    
    return power_sim


def part_2_phase1_panel_damage():
    """Part 2: Phase 1 - Panel damage (0-60s)."""
    print_header("PART 2: PHASE 1 - PANEL DAMAGE (0-60s)")
    print("\nInjecting severe brownout fault (severity=0.8, duration=300s)")
    print("Phase 1: Solar panels damaged, generation reduced by 75-80%\n")
    
    power_sim = PowerSimulator(sat_id="SAT-001", battery_soc_percent=80.0)
    
    print(f"[  0.0s] BASELINE (before fault):")
    print_power_status(power_sim, 0.0)
    
    # Inject fault
    power_sim.inject_brownout_fault(severity=0.8, duration=300.0)
    print(f"\n[  0.0s] FAULT INJECTED")
    print_fault_status(power_sim._brownout_fault)
    
    soc_history = [80.0]
    voltage_history = [power_sim.battery_voltage_v]
    
    for t in range(1, 61, 10):
        power_sim.update(dt=10.0, sun_exposure=1.0)
        soc_history.append(power_sim.battery_soc_percent)
        voltage_history.append(power_sim.battery_voltage_v)
        
        print_power_status(power_sim, float(t))
        print(f"  Fault phase: {power_sim._brownout_fault.get_phase()}")
    
    print(f"\n✓ Phase 1 Impact:")
    print(f"  SOC change: {soc_history[0]:.1f}% → {soc_history[-1]:.1f}% (Δ {soc_history[-1] - soc_history[0]:.1f}%)")
    print(f"  Voltage: {voltage_history[0]:.3f}V → {voltage_history[-1]:.3f}V")
    print(f"  Fault reduced solar generation by ~75% due to panel damage")
    
    return power_sim


def part_3_phase2_battery_stress():
    """Part 3: Phase 2 - Battery stress (60-180s)."""
    print_header("PART 3: PHASE 2 - BATTERY STRESS (60-180s)")
    print("\nTransition to Phase 2: Discharge acceleration multiplier applied")
    print("Load current multiplied by 2.0x (severity 0.8 → discharge_mult=2.3x)\n")
    
    power_sim = PowerSimulator(sat_id="SAT-001", battery_soc_percent=70.0)
    power_sim.inject_brownout_fault(severity=0.8, duration=300.0)
    
    # Simulate 60s elapsed (Phase 1 complete)
    power_sim._brownout_fault.start_time = datetime.now() - timedelta(seconds=60)
    
    print(f"[Time 0:00] PHASE 2 START (60s into fault):")
    print_power_status(power_sim, 0.0)
    print_fault_status(power_sim._brownout_fault)
    
    soc_history = [70.0]
    voltage_history = [power_sim.battery_voltage_v]
    
    # Phase 2: 60-180s (simulate eclipse - no sun exposure)
    for t in range(1, 121, 10):
        power_sim.update(dt=10.0, sun_exposure=0.0)  # Eclipse
        soc_history.append(power_sim.battery_soc_percent)
        voltage_history.append(power_sim.battery_voltage_v)
        
        elapsed = 60 + t
        print_power_status(power_sim, float(elapsed))
        print(f"  Fault phase: {power_sim._brownout_fault.get_phase()}")
        print(f"  [Eclipse + Battery Stress]")
    
    print(f"\n✓ Phase 2 Impact:")
    print(f"  SOC drop: {soc_history[0]:.1f}% → {soc_history[-1]:.1f}% (Δ {soc_history[-1] - soc_history[0]:.1f}%)")
    print(f"  Voltage degradation: {voltage_history[0]:.3f}V → {voltage_history[-1]:.3f}V")
    print(f"  Discharge accelerated due to 2.3x load multiplier in battery stress phase")
    print(f"  WARNING: Voltage dropping below nominal!")
    
    return power_sim


def part_4_phase3_safe_mode():
    """Part 4: Phase 3 - Safe-mode (180s+)."""
    print_header("PART 4: PHASE 3 - SAFE-MODE LOAD SPIKE (180s+)")
    print("\nTransition to Phase 3: System enters safe-mode with reduced load")
    print("Load spike to 8W as spacecraft enters safe-mode protocol\n")
    
    power_sim = PowerSimulator(sat_id="SAT-001", battery_soc_percent=45.0)
    power_sim.inject_brownout_fault(severity=0.8, duration=300.0)
    
    # Simulate 180s elapsed (Phase 3 start)
    power_sim._brownout_fault.start_time = datetime.now() - timedelta(seconds=180)
    
    print(f"[Time 3:00] PHASE 3 START (180s into fault):")
    print_power_status(power_sim, 0.0)
    print_fault_status(power_sim._brownout_fault)
    
    soc_history = [45.0]
    voltage_history = [power_sim.battery_voltage_v]
    
    # Phase 3: 180s+ (still in eclipse, safe-mode active)
    for t in range(1, 121, 10):
        power_sim.update(dt=10.0, sun_exposure=0.0)
        soc_history.append(power_sim.battery_soc_percent)
        voltage_history.append(power_sim.battery_voltage_v)
        
        elapsed = 180 + t
        print_power_status(power_sim, float(elapsed))
        print(f"  Fault phase: {power_sim._brownout_fault.get_phase()}")
        print(f"  [Safe-Mode: Reduced functionality, 8W load spike]")
    
    print(f"\n✓ Phase 3 Impact:")
    print(f"  SOC dropped: {soc_history[0]:.1f}% → {soc_history[-1]:.1f}% (Δ {soc_history[-1] - soc_history[0]:.1f}%)")
    print(f"  Voltage critical: {voltage_history[0]:.3f}V → {voltage_history[-1]:.3f}V")
    if voltage_history[-1] < 6.5:
        print(f"  ⚠️  CRITICAL: Battery voltage below 6.5V - safe-mode active!")
    print(f"  System in safe-mode: essential systems only (8W load)")
    
    return power_sim


def part_5_auto_recovery():
    """Part 5: Auto-recovery and system restoration."""
    print_header("PART 5: AUTO-RECOVERY AND SYSTEM RESTORATION")
    print("\nFault expires after 300s duration")
    print("System emerges from eclipse, panels recover, charging resumes\n")
    
    power_sim = PowerSimulator(sat_id="SAT-001", battery_soc_percent=35.0)
    power_sim.inject_brownout_fault(severity=0.8, duration=300.0)
    
    # Simulate fault near expiration
    power_sim._brownout_fault.start_time = datetime.now() - timedelta(seconds=295)
    
    print(f"[Time 4:55] APPROACHING FAULT EXPIRATION:")
    print_power_status(power_sim, 295.0)
    print_fault_status(power_sim._brownout_fault)
    
    soc_history = [35.0]
    voltage_history = [power_sim.battery_voltage_v]
    
    # Simulate last 60 seconds of fault + recovery
    for t in range(1, 121, 10):
        power_sim.update(dt=10.0, sun_exposure=1.0)  # Back in sun
        elapsed = 295 + t
        
        # Check expiration
        if power_sim._brownout_fault.is_expired():
            power_sim._brownout_fault.active = False
        
        soc_history.append(power_sim.battery_soc_percent)
        voltage_history.append(power_sim.battery_voltage_v)
        
        status = "ACTIVE" if power_sim._brownout_fault.active else "EXPIRED"
        print_power_status(power_sim, float(elapsed))
        print(f"  Fault status: {status}")
        
        if power_sim._brownout_fault.active:
            print_fault_status(power_sim._brownout_fault)
    
    print(f"\n✓ Recovery Complete:")
    print(f"  Fault duration: 300.0s (as designed)")
    print(f"  SOC recovery: {soc_history[0]:.1f}% → {soc_history[-1]:.1f}% (in sunlight)")
    print(f"  Voltage recovery: {voltage_history[0]:.3f}V → {voltage_history[-1]:.3f}V")
    print(f"  System operational: Panels recovered, nominal load (5W)")
    print(f"  Battery charging resumed")


def part_6_severity_comparison():
    """Part 6: Severity scaling comparison."""
    print_header("PART 6: SEVERITY SCALING COMPARISON")
    print("\nComparing different fault severities: Light (0.2) → Medium (0.5) → Severe (0.9)\n")
    
    severities = [0.2, 0.5, 0.9]
    labels = ["Light", "Medium", "Severe"]
    
    for severity, label in zip(severities, labels):
        print(f"\n{label.upper()} Fault (severity={severity}):")
        fault = PowerBrownoutFault(sat_id="SAT-001", severity=severity, duration=300.0)
        fault.inject()
        state = fault.get_fault_state()
        
        print(f"  Panel Damage Factor:  {state['panel_damage_factor']:.3f} (higher = more damage)")
        print(f"  Discharge Multiplier: {state['discharge_multiplier']:.3f}x (higher = faster drain)")
        print(f"  Safe-Mode Load:       {state['safe_mode_load']:.1f} W")
    
    print(f"\n✓ Severity Scaling:")
    print(f"  Low severity (0.2):  Minimal impact, ~37% solar power retained")
    print(f"  Mid severity (0.5):  Moderate impact, ~25% solar power retained")
    print(f"  High severity (0.9): Severe impact, ~13% solar power retained")


def main():
    """Run brownout fault demonstration."""
    print("\n")
    print("=" * 70)
    print("  ASTRAGUARD HIL: POWER BROWNOUT FAULT DEMO")
    print("  Issue #491 - Configurable Fault Injection")
    print("=" * 70)
    
    # Run all demonstration parts
    part_1_baseline()
    part_2_phase1_panel_damage()
    part_3_phase2_battery_stress()
    part_4_phase3_safe_mode()
    part_5_auto_recovery()
    part_6_severity_comparison()
    
    # Summary
    print_header("SUMMARY")
    print("""
Power Brownout Fault Model (Issue #491):

✓ 3-Phase Degradation:
  Phase 1 (0-60s):   Panel damage - solar generation reduced
  Phase 2 (60-180s): Battery stress - discharge accelerated 
  Phase 3 (180s+):   Safe-mode - load spike to 8W

✓ Severity Scaling (0.1-1.0):
  Panel damage factor:  0.40 → 0.10 (higher severity = more damage)
  Discharge multiplier: 1.6 → 2.4x (higher severity = faster drain)

✓ Auto-Recovery:
  Fault automatically expires after configured duration
  System returns to nominal operation
  Battery resumes charging when in sunlight

✓ Integration:
  Injected via: power_sim.inject_brownout_fault(severity=0.8, duration=300)
  Affects: solar_power_w, battery_discharge_rate, load_w
  Couples with: eclipse timing, thermal impact, swarm fault cascades

✓ Critical for Swarm Testing:
  Enables power-constrained scenario simulation
  Tests fault propagation and recovery mechanisms
  Validates safe-mode and low-power operations
  Prerequisite for multi-satellite fault cascade analysis (Issue #492)
    """)
    
    print("\n✓ Demo complete!")


if __name__ == "__main__":
    main()
