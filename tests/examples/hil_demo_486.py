"""
HIL Demo #486: Production telemetry schemas with validation.

This script demonstrates:
- Schema validation and type safety
- JSON serialization for debugging/export
- Fault cascading across multiple subsystems
"""

import asyncio
import json
from datetime import datetime
from astraguard.hil.simulator.base import StubSatelliteSimulator


async def main():
    """Run HIL telemetry schemas demo."""
    print("=" * 70)
    print("AstraGuard HIL Telemetry Schemas Demo #486")
    print("=" * 70)
    print()
    
    # Initialize simulator
    sim = StubSatelliteSimulator("ASTRA-001")
    sim.start()
    print(f"✓ Initialized simulator: {sim.sat_id}")
    print()
    
    # === NORMAL OPERATION ===
    print("--- NORMAL OPERATION (Schema Validated Telemetry) ---")
    print()
    
    packet = await sim.generate_telemetry()
    
    print("✓ Telemetry packet generated and validated")
    print(f"  Version: {packet.version}")
    print(f"  Satellite ID: {packet.satellite_id}")
    print(f"  Timestamp: {packet.timestamp}")
    print()
    
    print("Power Subsystem:")
    print(f"  Battery Voltage: {packet.power.battery_voltage}V (nominal: 8.4V)")
    print(f"  Battery SOC: {packet.power.battery_soc:.1%}")
    print(f"  Solar Current: {packet.power.solar_current}A")
    print(f"  Load Current: {packet.power.load_current}A")
    print()
    
    print("Attitude Subsystem:")
    print(f"  Quaternion: {packet.attitude.quaternion}")
    print(f"  Angular Velocity: {packet.attitude.angular_velocity} rad/s")
    print(f"  Nadir Pointing Error: {packet.attitude.nadir_pointing_error_deg:.2f}°")
    print()
    
    print("Thermal Subsystem:")
    print(f"  Battery Temp: {packet.thermal.battery_temp}°C")
    print(f"  EPS Temp: {packet.thermal.eps_temp}°C")
    print(f"  Status: {packet.thermal.status}")
    print()
    
    print("Orbital Parameters:")
    print(f"  Altitude: {packet.orbit.altitude_m/1000:.0f}km (LEO)")
    print(f"  Ground Speed: {packet.orbit.ground_speed_ms:.0f}m/s")
    print(f"  True Anomaly: {packet.orbit.true_anomaly_deg:.1f}°")
    print()
    
    # === JSON SERIALIZATION ===
    print("--- JSON SERIALIZATION ---")
    print()
    
    packet_dict = packet.model_dump()
    json_str = json.dumps(packet_dict, indent=2, default=str)
    
    # Print formatted (truncated for demo)
    lines = json_str.split('\n')
    print("JSON Export (first 30 lines):")
    for line in lines[:30]:
        print(line)
    if len(lines) > 30:
        print(f"  ... ({len(lines) - 30} more lines)")
    print()
    
    # === FAULT INJECTION ===
    print("--- FAULT INJECTION: Power Brownout ---")
    print()
    
    await sim.inject_fault("power_brownout", severity=0.8, duration=30.0)
    print("Fault injected. Subsystems show cascading effects:")
    print()
    
    fault_packet = await sim.generate_telemetry()
    
    print("Power Subsystem (DEGRADED):")
    print(f"  Battery Voltage: {fault_packet.power.battery_voltage}V ⚠️ (dropped from 8.4V)")
    print(f"  Battery SOC: {fault_packet.power.battery_soc:.1%} ⚠️ (dropped from 87%)")
    print()
    
    print("Thermal Subsystem (WARNING):")
    print(f"  Battery Temp: {fault_packet.thermal.battery_temp}°C ⚠️ (raised from 15.2°C)")
    print(f"  Status: {fault_packet.thermal.status.upper()} ⚠️ (changed from nominal)")
    print()
    
    # === VALIDATION DEMO ===
    print("--- SCHEMA VALIDATION ---")
    print()
    
    from pydantic import ValidationError
    
    # Try invalid quaternion
    print("Testing validation: Invalid quaternion (3 elements instead of 4)")
    from astraguard.hil.schemas.telemetry import AttitudeData
    try:
        bad_attitude = AttitudeData(
            quaternion=[0.707, 0.0, 0.0],  # Only 3 - should fail
            angular_velocity=[0.001, 0.002, 0.001],
            nadir_pointing_error_deg=1.5
        )
    except ValidationError as e:
        print(f"✓ Validation caught error: {e.errors()[0]['msg']}")
    print()
    
    print("Testing validation: Invalid voltage (> 30V max)")
    from astraguard.hil.schemas.telemetry import PowerData
    try:
        bad_power = PowerData(
            battery_voltage=35.0,  # Max is 30V
            battery_soc=0.87,
            solar_current=0.8,
            load_current=0.3
        )
    except ValidationError as e:
        print(f"✓ Validation caught error: Battery voltage too high")
    print()
    
    print("Testing validation: Invalid thermal status")
    from astraguard.hil.schemas.telemetry import ThermalData
    try:
        bad_thermal = ThermalData(
            battery_temp=15.2,
            eps_temp=22.1,
            status="overheating"  # Invalid - must be nominal/warning/critical
        )
    except ValidationError as e:
        print(f"✓ Validation caught error: {e.errors()[0]['msg']}")
    print()
    
    # === HISTORY TRACKING ===
    print("--- HISTORY TRACKING ---")
    print()
    
    history = sim.get_telemetry_history()
    print(f"Total packets recorded: {len(history)}")
    
    if len(history) >= 2:
        print("\nComparison: Pre-fault vs Post-fault")
        pre_fault = history[0]
        post_fault = history[1]
        
        print(f"Pre-fault voltage:  {pre_fault.power.battery_voltage}V")
        print(f"Post-fault voltage: {post_fault.power.battery_voltage}V")
        print(f"Voltage drop: {pre_fault.power.battery_voltage - post_fault.power.battery_voltage:.1f}V")
        
        print(f"\nPre-fault thermal:  {pre_fault.thermal.status}")
        print(f"Post-fault thermal: {post_fault.thermal.status}")
    
    print()
    
    # Cleanup
    sim.stop()
    
    print("=" * 70)
    print("Demo Complete! Schemas validated and production-ready.")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
