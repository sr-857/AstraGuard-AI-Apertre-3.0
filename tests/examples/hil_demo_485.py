"""
HIL Demo #485: SatelliteSimulator base class demonstration.

This script demonstrates the core HIL simulation capabilities:
- Telemetry generation
- Fault injection
- Lifecycle management
"""

import asyncio
from astraguard.hil.simulator.base import StubSatelliteSimulator


async def main():
    """Run HIL simulation demo."""
    print("=" * 60)
    print("AstraGuard HIL Simulator Demo #485")
    print("=" * 60)
    print()
    
    # Initialize simulator
    sim = StubSatelliteSimulator("DEMO-SAT")
    sim.start()
    print(f"✓ Initialized simulator: {sim.sat_id}")
    print()
    
    # Generate normal telemetry
    print("--- NORMAL OPERATION ---")
    print("Generating 5 telemetry packets...")
    for i in range(5):
        telemetry = await sim.generate_telemetry()
        voltage = telemetry.data["battery_voltage"]
        temp = telemetry.data["temperature"]
        alt = telemetry.data["orbit_altitude"]
        print(f"  Packet #{i+1}: {voltage}V | {temp:.1f}°C | Alt: {alt}m")
    
    print()
    
    # Inject fault
    print("--- FAULT INJECTION ---")
    await sim.inject_fault("power_brownout", severity=0.8, duration=30.0)
    print()
    
    # Generate faulty telemetry
    print("--- POST-FAULT OPERATION ---")
    print("Generating 3 telemetry packets under fault...")
    for i in range(3):
        telemetry = await sim.generate_telemetry()
        voltage = telemetry.data["battery_voltage"]
        temp = telemetry.data["temperature"]
        print(f"  Packet #{i+6}: {voltage}V | {temp:.1f}°C [FAULT ACTIVE]")
    
    print()
    
    # History
    print("--- TELEMETRY HISTORY ---")
    history = sim.get_telemetry_history()
    print(f"Total packets recorded: {len(history)}")
    print(f"First packet timestamp: {history[0].timestamp}")
    print(f"Last packet timestamp: {history[-1].timestamp}")
    
    print()
    
    # Lifecycle
    print("--- LIFECYCLE ---")
    sim.stop()
    print(f"✓ Simulator stopped (running={sim._running})")
    
    print()
    print("=" * 60)
    print("Demo Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
