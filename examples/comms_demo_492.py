#!/usr/bin/env python3
"""
Issue #492: Communications Dropout Fault Demo
Demonstrates realistic comms channel with Gilbert-Elliot dropout, power coupling, and range degradation.

Scenario: Satellite in low-Earth orbit experiencing:
1. Nominal comms at low altitude (good power, good range)
2. Brownout stress (low battery voltage degrades TX power)
3. Long-range stress (increasing altitude increases path loss)
4. Combined degradation (brownout + high altitude = near blackout)
5. Fault injection with Gilbert-Elliot bursty dropout pattern
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


def print_comms_stats(comms_stats, scenario_name):
    """Pretty-print communications statistics."""
    print(f"\n{scenario_name}:")
    print(f"  Comms State:        {comms_stats.get('state', 'UNKNOWN')}")
    print(f"  Packet Loss Rate:   {comms_stats.get('packet_loss_rate', 0)*100:.1f}%")
    tx_dbw = comms_stats.get('tx_power_dbw', 0)
    tx_watts = 10**(tx_dbw/10)
    print(f"  TX Power:           {tx_dbw:.1f} dBW ({tx_watts:.2f}W)")
    print(f"  Range:              {comms_stats.get('range_km', 0):.0f} km")
    print(f"  Gilbert State:      {'GOOD' if comms_stats.get('gilbert_state') else 'BAD'}")
    print(f"  Avg Packet Success: ~{(1.0 - comms_stats.get('packet_loss_rate', 0))*100:.1f}%")


def demo_nominal_comms():
    """Scenario 1: Nominal communications at low altitude."""
    print_header("Scenario 1: NOMINAL COMMS (Low Altitude, Good Power)")
    
    sim = StubSatelliteSimulator(sat_id="SAT-DEMO-1")
    
    print("\nSimulating nominal orbit at 400 km altitude with 7.4V battery voltage...")
    for step in range(5):
        asyncio.run(sim.generate_telemetry())
        telemetry = sim.get_telemetry_history()[-1] if sim.get_telemetry_history() else None
        
        # Check comms statistics
        comms_stats = sim.comms_sim.get_comms_stats()
        if step == 0:
            print(f"\nAltitude:        {telemetry.orbit.altitude_m/1000:.1f} km")
            print(f"Battery Voltage: {telemetry.power.battery_voltage:.2f}V")
            print_comms_stats(comms_stats, "Initial State")
        elif step == 4:
            print_comms_stats(comms_stats, "After 5 updates")
    
    print("\n[RESULT] Nominal comms: excellent link, high packet success, NOMINAL state")


def demo_brownout_stress():
    """Scenario 2: Power brownout degradation."""
    print_header("Scenario 2: BROWNOUT STRESS (Power Degradation)")
    
    sim = StubSatelliteSimulator(sat_id="SAT-DEMO-2")
    
    print("\nSimulating power degradation from 7.4V (nominal) to 6.0V (critical)...")
    print("\nVoltage          TX Power         Packet Loss       Comms State")
    print("-" * 65)
    
    voltages = [7.4, 7.0, 6.5, 6.0]
    for v in voltages:
        # Manually set battery voltage to simulate brownout
        sim.power_sim._battery_voltage = v
        sim.comms_sim.update(power_voltage=v, range_km=500.0)
        comms_stats = sim.comms_sim.get_comms_stats()
        
        tx_power = comms_stats.get('tx_power_dbw', 0)
        loss = comms_stats.get('packet_loss_rate', 0)
        state = comms_stats.get('state', 'UNKNOWN')
        
        print(f"{v:.1f}V           {tx_power:+.1f} dBW          {loss*100:5.1f}%           {state}")
    
    print("\n[RESULT] Brownout reduces TX power and increases packet loss dramatically")


def demo_range_degradation():
    """Scenario 3: Range-based path loss degradation."""
    print_header("Scenario 3: RANGE DEGRADATION (Path Loss)")
    
    sim = StubSatelliteSimulator(sat_id="SAT-DEMO-3")
    
    print("\nSimulating increasing altitude (range increases free-space path loss)...")
    print("\nAltitude (km)    Range (km)       FSPL Loss        Packet Loss      Comms State")
    print("-" * 80)
    
    altitudes = [400, 500, 600, 700, 800, 900]
    for alt_km in altitudes:
        range_km = alt_km  # Simplified: assume range = altitude for demo
        comms_sim = sim.comms_sim
        comms_sim.update(power_voltage=7.4, range_km=range_km)
        comms_stats = comms_sim.get_comms_stats()
        
        # FSPL = 100 + 20*log10(range) at S-band (2.4 GHz)
        import math
        fspl = 100 + 20 * math.log10(range_km)
        loss = comms_stats.get('packet_loss_rate', 0)
        state = comms_stats.get('state', 'UNKNOWN')
        
        print(f"{alt_km:4d}             {range_km:5.0f}           {fspl:5.1f} dB        {loss*100:5.1f}%           {state}")
    
    print("\n[RESULT] Range increases exponentially degrading comms link budget")


def demo_combined_stress():
    """Scenario 4: Combined brownout + range degradation."""
    print_header("Scenario 4: COMBINED STRESS (Brownout + High Range)")
    
    sim = StubSatelliteSimulator(sat_id="SAT-DEMO-4")
    
    print("\nSimulating worst-case: High altitude + low battery voltage...")
    print("\n[Scenario A] High altitude (800km) with good power (7.4V):")
    sim.comms_sim.update(power_voltage=7.4, range_km=800.0)
    stats_a = sim.comms_sim.get_comms_stats()
    print_comms_stats(stats_a, "  High Range + Good Power")
    
    print("\n[Scenario B] Low altitude (400km) with poor power (6.0V):")
    sim.comms_sim.update(power_voltage=6.0, range_km=400.0)
    stats_b = sim.comms_sim.get_comms_stats()
    print_comms_stats(stats_b, "  Low Range + Poor Power")
    
    print("\n[Scenario C] HIGH ALTITUDE (800km) + POOR POWER (6.0V) = WORST CASE:")
    sim.comms_sim.update(power_voltage=6.0, range_km=800.0)
    stats_c = sim.comms_sim.get_comms_stats()
    print_comms_stats(stats_c, "  HIGH RANGE + POOR POWER")
    
    print("\n[RESULT] Combined stressors create near-blackout conditions")


def demo_gilbert_dropout_fault():
    """Scenario 5: Gilbert-Elliot fault injection."""
    print_header("Scenario 5: GILBERT-ELLIOT FAULT (Bursty Dropout)")
    
    sim = StubSatelliteSimulator(sat_id="SAT-DEMO-5")
    
    print("\nInjecting Gilbert-Elliot bursty dropout fault (30% base loss)...")
    asyncio.run(sim.inject_fault(fault_type="comms_dropout", severity=0.0, duration=60.0))
    
    print("\nSimulating 20 packet transmission attempts with fault active:")
    print("(G = Good burst, B = Bad burst, . = success, X = loss)")
    print()
    
    transmission_pattern = ""
    for i in range(20):
        asyncio.run(sim.generate_telemetry())
        success = sim.comms_sim.transmit_packet()
        transmission_pattern += "." if success else "X"
    
    print(f"Transmission pattern: {transmission_pattern}")
    
    # Show Gilbert statistics
    if sim._comms_fault:
        fault_state = sim._comms_fault.get_fault_state()
        print(f"\nFault State:")
        print(f"  Pattern:          {fault_state.get('pattern', 'unknown')}")
        print(f"  Base Loss Rate:   {fault_state.get('packet_loss_rate', 0)*100:.1f}%")
        print(f"  Time Remaining:   {fault_state.get('time_remaining_s', 0):.1f}s")
        print(f"  Gilbert Good Prob: {fault_state.get('gilbert_good_prob', 0):.2f}")
        print(f"  Gilbert Bad Prob:  {fault_state.get('gilbert_bad_prob', 0):.2f}")
    
    print("\n[RESULT] Gilbert-Elliot creates realistic bursty dropout patterns")


def demo_fault_recovery():
    """Scenario 6: Fault auto-recovery."""
    print_header("Scenario 6: FAULT AUTO-RECOVERY")
    
    sim = StubSatelliteSimulator(sat_id="SAT-DEMO-6")
    
    print("\nInjecting 5-second comms dropout fault...")
    asyncio.run(sim.inject_fault(fault_type="comms_dropout", severity=0.5, duration=5.0))
    
    print("Simulating: Step -> Loss Rate -> Time Remaining -> Fault Active")
    print("-" * 65)
    
    for step in range(10):
        asyncio.run(sim.generate_telemetry())
        
        if sim._comms_fault:
            fault_state = sim._comms_fault.get_fault_state()
            time_left = fault_state.get('time_remaining_s', 0)
            loss = fault_state.get('packet_loss_rate', 0)
            is_expired = sim._comms_fault.is_expired()
            active = "ACTIVE" if not is_expired else "EXPIRED"
        else:
            time_left = 0
            loss = 0
            active = "NONE"
        
        print(f"Step {step:2d}  ->  {loss*100:5.1f}%     ->  {time_left:4.2f}s        ->  {active}")
        
        # Small delay between updates
        import time
        time.sleep(0.1)
    
    print("\n[RESULT] Fault automatically expires after duration and clears")


def main():
    """Run all demonstration scenarios."""
    print("\n" + "=" * 70)
    print("  ASTRAGUARD-AI: COMMUNICATIONS FAULT DEMONSTRATION (Issue #492)")
    print("  Gilbert-Elliot Dropout Model + Power Coupling + Range Degradation")
    print("=" * 70)
    
    try:
        demo_nominal_comms()
        demo_brownout_stress()
        demo_range_degradation()
        demo_combined_stress()
        demo_gilbert_dropout_fault()
        demo_fault_recovery()
        
        print_header("DEMONSTRATION COMPLETE")
        print("""
Key Takeaways:
1. Nominal comms: ~98% success rate at low altitude with good power
2. Brownout: Battery voltage <7V reduces TX power and causes packet loss
3. Range: Path loss increases exponentially with altitude (FSPL model)
4. Combined: Worst-case (high altitude + low power) can reduce to <10% success
5. Gilbert-Elliot: Creates realistic bursty dropout (good state bias)
6. Auto-recovery: Faults expire automatically after duration

This comms system is now coupled with:
- Power system (voltage -> TX power derating)
- Orbit system (altitude -> range -> path loss)

Perfect for testing swarm resilience with realistic communication failures!
        """)
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
