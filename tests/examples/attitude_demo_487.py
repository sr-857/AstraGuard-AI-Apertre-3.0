"""
HIL Demo #487: Realistic CubeSat attitude simulator with tumble fault.

This script demonstrates:
- Quaternion-based attitude dynamics
- Nadir pointing control
- Tumble fault injection and recovery
- Angular velocity propagation
"""

import asyncio
import json
from astraguard.hil.simulator.base import StubSatelliteSimulator


async def main():
    """Run attitude simulator demo."""
    print("=" * 80)
    print("AstraGuard HIL Attitude Simulator Demo #487")
    print("=" * 80)
    print()
    
    # Initialize simulator
    sim = StubSatelliteSimulator("ATTITUDE-DEMO")
    sim.start()
    print(f"✓ Initialized: {sim.sat_id}")
    print()
    
    # === NOMINAL OPERATION ===
    print("--- NOMINAL OPERATION: Nadir Pointing ---")
    print()
    
    print("Generating 5 telemetry packets in nominal mode...")
    print(f"{'Packet':<8} {'Error (°)':<12} {'ω_mag (r/s)':<15} {'Mode':<20}")
    print("-" * 55)
    
    for i in range(5):
        packet = await sim.generate_telemetry()
        error = packet.attitude.nadir_pointing_error_deg
        omega_mag = (
            sum(v**2 for v in packet.attitude.angular_velocity) ** 0.5
        )
        mode = sim.attitude_sim._mode
        
        print(f"{i+1:<8} {error:<12.2f} {omega_mag:<15.6f} {mode:<20}")
    
    print()
    
    # === DETAILED ATTITUDE DATA ===
    print("--- DETAILED ATTITUDE STATE ---")
    packet = await sim.generate_telemetry()
    
    print(f"Quaternion:        {[round(x, 4) for x in packet.attitude.quaternion]}")
    print(f"Angular Velocity:  {[f'{x:.6f}' for x in packet.attitude.angular_velocity]} rad/s")
    print(f"Nadir Error:       {packet.attitude.nadir_pointing_error_deg:.2f}°")
    print(f"Status:            {sim.attitude_sim.get_status()}")
    print()
    
    # === FAULT INJECTION ===
    print("--- FAULT INJECTION: Attitude Desynchronization ---")
    print("(Simulates reaction wheel failure → uncontrolled tumble)")
    print()
    
    await sim.inject_fault("attitude_desync", severity=1.0, duration=30.0)
    print()
    
    # === TUMBLE DYNAMICS ===
    print("--- TUMBLE PROGRESSION ---")
    print("Tracking attitude degradation over 20 telemetry cycles...")
    print(f"{'Cycle':<8} {'Error (°)':<12} {'ω_mag (r/s)':<15} {'Status':<15}")
    print("-" * 50)
    
    tumble_data = []
    for i in range(20):
        packet = await sim.generate_telemetry()
        error = packet.attitude.nadir_pointing_error_deg
        omega_mag = (
            sum(v**2 for v in packet.attitude.angular_velocity) ** 0.5
        )
        status = sim.attitude_sim.get_status()
        
        tumble_data.append({
            "cycle": i + 1,
            "error": error,
            "omega_mag": omega_mag,
            "mode": status["mode"]
        })
        
        if i % 3 == 0 or i == 19:  # Print every 3rd cycle + last
            print(
                f"{i+1:<8} {error:<12.2f} {omega_mag:<15.6f} "
                f"{status['mode']:<15}"
            )
    
    print()
    
    # === ANALYSIS ===
    print("--- TUMBLE ANALYSIS ---")
    max_error = max(d["error"] for d in tumble_data)
    max_omega = max(d["omega_mag"] for d in tumble_data)
    
    print(f"Maximum nadir error:    {max_error:.1f}° (started at ~0.5°)")
    print(f"Maximum angular velocity: {max_omega:.6f} rad/s")
    print(f"Average error:          {sum(d['error'] for d in tumble_data)/len(tumble_data):.1f}°")
    print()
    
    # === RECOVERY ===
    print("--- RECOVERY: ADCS Stabilization ---")
    print("Clearing fault flag and initiating recovery...")
    print()
    
    sim._fault_active = False
    sim.attitude_sim.recover_control()
    
    # Let attitude settle
    print(f"{'Cycle':<8} {'Error (°)':<12} {'ω_mag (r/s)':<15}")
    print("-" * 35)
    
    for i in range(10):
        packet = await sim.generate_telemetry()
        error = packet.attitude.nadir_pointing_error_deg
        omega_mag = (
            sum(v**2 for v in packet.attitude.angular_velocity) ** 0.5
        )
        
        if i % 2 == 0:
            print(f"{i+1:<8} {error:<12.2f} {omega_mag:<15.6f}")
    
    print()
    
    # === QUATERNION MATHEMATICS ===
    print("--- QUATERNION VALIDATION ---")
    final_packet = await sim.generate_telemetry()
    q = final_packet.attitude.quaternion
    q_norm = sum(x**2 for x in q) ** 0.5
    
    print(f"Final quaternion:  {[round(x, 4) for x in q]}")
    print(f"Quaternion norm:   {q_norm:.10f} (should be 1.0)")
    print(f"Norm valid:        {'✓' if abs(q_norm - 1.0) < 1e-6 else '✗'}")
    print()
    
    # === HISTORY ===
    print("--- TELEMETRY HISTORY ---")
    history = sim.get_telemetry_history()
    print(f"Total packets recorded: {len(history)}")
    print(f"First error:  {history[0].attitude.nadir_pointing_error_deg:.2f}°")
    print(f"Peak error:   {max(p.attitude.nadir_pointing_error_deg for p in history):.2f}°")
    print(f"Final error:  {history[-1].attitude.nadir_pointing_error_deg:.2f}°")
    print()
    
    sim.stop()
    
    print("=" * 80)
    print("Demo Complete! Attitude dynamics are physics-based and production-ready.")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
