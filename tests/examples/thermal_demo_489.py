"""Thermal simulator demonstration - orbital cycle and runaway cascade.

Shows:
1. Realistic orbital thermal cycling (sunlight/eclipse)
2. Attitude effects on temperature (tumbling = thermal stress)
3. Thermal runaway cascade triggered by radiator failure
4. Temperature-driven mission mode transitions
"""

import asyncio
from astraguard.hil.simulator.base import StubSatelliteSimulator


async def demo_thermal():
    """Demonstrate orbital thermal cycles and fault scenarios."""
    
    print("=" * 70)
    print("🌍 THERMAL SIMULATOR DEMO - AstraGuard HIL Issue #489")
    print("=" * 70)
    
    # Create satellite simulator
    sim = StubSatelliteSimulator("THERMAL-SAT")
    
    # ========================================================================
    # PART 1: Normal orbital thermal cycle (sunlight + eclipse)
    # ========================================================================
    print("\n📡 Part 1: Normal Orbital Thermal Cycle")
    print("-" * 70)
    print("Simulating satellite orbiting through sunlight and eclipse phases")
    print("(Real orbit = 90 min, simulation = 20 steps for visualization)\n")
    
    for step in range(20):
        packet = await sim.generate_telemetry()
        thermal = packet.thermal
        attitude = packet.attitude
        power = packet.power
        
        # Status emoji
        status_emoji = {
            "nominal": "🟢",
            "warning": "🟡",
            "critical": "🔴"
        }[thermal.status]
        
        # Orbital phase simulation (simplified)
        in_eclipse = power.solar_current < 0.1
        eclipse_str = "🌑 ECLIPSE" if in_eclipse else "☀️  SUNLIT "
        
        # Attitude quality
        pointing_error = attitude.nadir_pointing_error_deg
        pointing_str = f"{pointing_error:5.1f}°"
        if pointing_error > 30:
            pointing_str += " 🔄 TUMBLING"
        
        print(
            f"Step {step:2d}: {status_emoji} {thermal.status:8s} | "
            f"Batt: {thermal.battery_temp:5.1f}°C | "
            f"EPS: {thermal.eps_temp:5.1f}°C | "
            f"{eclipse_str} | "
            f"Error: {pointing_str}"
        )
    
    # ========================================================================
    # PART 2: Thermal runaway cascade
    # ========================================================================
    print("\n" + "=" * 70)
    print("🔥 Part 2: Thermal Runaway Cascade (Radiator Failure)")
    print("-" * 70)
    print("Injecting radiator failure fault → monitoring thermal escalation\n")
    
    # Create fresh simulator for runaway demo
    sim_runaway = StubSatelliteSimulator("RUNAWAY-SAT")
    
    # Inject thermal runaway fault
    print("⚠️  FAULT INJECTED: thermal_runaway (severity=1.0)")
    print("   Radiator capacity degraded to 20% of nominal\n")
    await sim_runaway.inject_fault("thermal_runaway", severity=1.0)
    
    print("Monitoring thermal escalation...")
    print("-" * 70)
    
    max_cycles = 15
    for cycle in range(max_cycles):
        packet = await sim_runaway.generate_telemetry()
        thermal = packet.thermal
        
        # Status emoji
        if thermal.status == "nominal":
            status_icon = "🟢 NOMINAL"
        elif thermal.status == "warning":
            status_icon = "🟡 WARNING"
        else:  # critical
            status_icon = "🔴 CRITICAL"
        
        print(
            f"Cycle {cycle:2d}: {status_icon:15s} | "
            f"Batt: {thermal.battery_temp:5.1f}°C | "
            f"EPS: {thermal.eps_temp:5.1f}°C"
        )
        
        # Show escalation milestones
        if thermal.battery_temp > 45 and thermal.battery_temp < 50:
            print("           ⚠️  Temperature exceeds 45°C - WARNING threshold")
        elif thermal.battery_temp > 60:
            print("           🚨 CRITICAL: Battery exceeds 60°C - Mission at risk!")
            if cycle > 8:  # Give it a few cycles then show recovery attempt
                break
    
    # ========================================================================
    # PART 3: Recovery after fault
    # ========================================================================
    print("\n" + "=" * 70)
    print("🔧 Part 3: Fault Recovery and Temperature Management")
    print("-" * 70)
    print("Ground command: Reduce solar load by entering eclipse safe-mode\n")
    
    # The satellite naturally enters eclipse in its orbit
    # Just continue monitoring as it cools
    print("Waiting for eclipse phase to cool down...\n")
    
    for cycle in range(10):
        packet = await sim_runaway.generate_telemetry()
        thermal = packet.thermal
        power = packet.power
        
        in_eclipse = power.solar_current < 0.1
        eclipse_str = "🌑" if in_eclipse else "☀️"
        
        if thermal.status == "critical":
            icon = "🔴"
        elif thermal.status == "warning":
            icon = "🟡"
        else:
            icon = "🟢"
        
        print(
            f"Cycle {cycle:2d}: {icon} {thermal.status:8s} | "
            f"Batt: {thermal.battery_temp:5.1f}°C | "
            f"{eclipse_str} Orbit phase"
        )
        
        if thermal.status == "nominal" and thermal.battery_temp < 30:
            print("           ✅ Temperature stabilized - recovery complete")
            break
    
    # ========================================================================
    # PART 4: Physics insights
    # ========================================================================
    print("\n" + "=" * 70)
    print("📊 Key Physics Insights")
    print("=" * 70)
    print("""
1. ORBITAL CYCLING: Thermal oscillates with 90-minute orbit
   - Sunlit phase (~45 min): Solar heating dominates
   - Eclipse phase (~45 min): Radiative cooling to space
   
2. ATTITUDE COUPLING: Tumbling = thermal stress
   - 0° nadir error: Optimal attitude, minimal solar absorption
   - 90° nadir error: Sideways tumble, 2x solar heating
   - Result: Tumble faults can trigger thermal cascades
   
3. THERMAL RUNAWAY: Radiator failure cascade
   - Degraded radiator loses 80% capacity
   - Temperature rise accelerates exponentially
   - Battery at 60°C triggers critical status
   - Mission implications: Safe-mode required immediately
   
4. MISSION CONSTRAINTS: "Critical" status drives policy
   - Battery > 60°C: Payload shutdown, survival mode only
   - Battery > 45°C: Reduce communications, power down non-essential
   - Status < 45°C: Full operational capability
   
5. SWARM IMPLICATIONS: Thermal cascades spread
   - One satellite's radiator failure → thermal stress
   - May reduce cooperation window in swarm maneuvers
   - Coordination algorithms must account for thermal state
""")
    
    print("=" * 70)
    print("✅ Demo complete - thermal physics now drive swarm behavior!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(demo_thermal())
