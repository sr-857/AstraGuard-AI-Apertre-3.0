"""Orbit simulator demonstration - LEO cycle, eclipse phases, and formation geometry.

Shows:
1. 90-minute LEO orbital cycle with altitude breathing
2. Eclipse phases (true anomaly 90-270°) driving power state
3. Swarm formation geometry with ECI positioning
4. Realistic cross-satellite ranging for constellation tests
"""

import asyncio
import numpy as np
from astraguard.hil.simulator.base import StubSatelliteSimulator
from astraguard.hil.simulator.orbit import OrbitSimulator


async def demo_orbit():
    """Demonstrate LEO orbital mechanics and eclipse timing."""
    
    print("=" * 80)
    print("🛰️  ORBIT SIMULATOR DEMO - AstraGuard HIL Issue #490")
    print("=" * 80)
    
    # ========================================================================
    # PART 1: 90-minute LEO orbital cycle with eclipse detection
    # ========================================================================
    print("\n📡 Part 1: LEO Orbital Cycle (90 minutes / 5400 seconds)")
    print("-" * 80)
    print("Demonstrating true anomaly propagation, altitude breathing, eclipse phases\n")
    
    sim = StubSatelliteSimulator("ORBIT-TEST")
    
    print(f"{'Cycle':>5} | {'Pos':^12} | {'Alt (km)':>8} | Phase      | {'Power':^6} | {'Batt':>5} | {'Thermal':>10}")
    print(f"{'-'*5}-+-{'-'*12}-+-{'-'*8}-+-{'-'*10}-+-{'-'*6}-+-{'-'*5}-+-{'-'*10}")
    
    for cycle in range(30):  # 30 cycles = 30 seconds, showing ~5 min of orbit
        packet = await sim.generate_telemetry()
        
        # Extract data
        ta_deg = packet.orbit.true_anomaly_deg
        alt_km = packet.orbit.altitude_m / 1000.0
        
        # Eclipse phase
        if 90 < ta_deg < 270:
            eclipse_str = "🌑 ECLIPSE"
            phase_name = "SHADOW"
        else:
            eclipse_str = "☀️  SUNLIT"
            phase_name = "SUN   "
        
        # Power state
        power_indicator = f"{packet.power.battery_soc:5.1%}"
        
        # Battery temp indicator
        if packet.thermal.status == "critical":
            temp_emoji = "🔴"
        elif packet.thermal.status == "warning":
            temp_emoji = "🟡"
        else:
            temp_emoji = "🟢"
        
        print(
            f"{cycle:5d} | {ta_deg:7.1f}°    | {alt_km:8.2f} | {phase_name:^10} | "
            f"{power_indicator} | {packet.thermal.battery_temp:5.1f}°C | {temp_emoji} {packet.thermal.status:^8}"
        )
    
    # ========================================================================
    # PART 2: Full 90-minute orbit visualization
    # ========================================================================
    print("\n" + "=" * 80)
    print("☀️  Part 2: Complete 90-Minute Orbit Visualization")
    print("-" * 80)
    print("Sampling every ~10 seconds to show full orbital cycle\n")
    
    sim2 = StubSatelliteSimulator("FULL-ORBIT")
    
    print("Phase Timeline (circle = one complete orbit)\n")
    print("              ☀️ SUNLIT        🌑 ECLIPSE       ☀️ SUNLIT")
    print("      0°-90° / 270°-360°  vs  90°-270°")
    print("")
    
    # Collect full orbit
    orbit_data = []
    for cycle in range(270):  # 270 cycles, each 1 second, covering ~45 min
        packet = await sim2.generate_telemetry()
        ta = packet.orbit.true_anomaly_deg
        eclipse = 90 < ta < 270
        soc = packet.power.battery_soc
        orbit_data.append({
            "ta": ta,
            "eclipse": eclipse,
            "soc": soc,
            "alt": packet.orbit.altitude_m / 1000.0,
        })
    
    # Print orbital map
    orbital_circle = ""
    for i, data in enumerate(orbit_data):
        ta_normalized = data["ta"] / 360.0  # 0 to 1
        position_in_circle = int(ta_normalized * 60)  # 60 chars per circle
        
        if i == 0:
            print("Start: ", end="")
        
        if position_in_circle % 10 == 0 and position_in_circle != 0:
            if data["eclipse"]:
                print("🌑", end="")
            else:
                print("☀️", end="")
        else:
            if data["eclipse"]:
                print("█", end="")
            else:
                print("░", end="")
        
        if (i + 1) % 60 == 0:
            print(" (360°)")
            if i < len(orbit_data) - 1:
                print("       ", end="")
    
    print("\n")
    
    # ========================================================================
    # PART 3: Power/thermal cycles driven by eclipse
    # ========================================================================
    print("=" * 80)
    print("⚡ Part 3: Power & Thermal Cycles Driven by Eclipse")
    print("-" * 80)
    print("Battery SOC and temperature oscillations from orbital eclipse\n")
    
    # Group by phase
    sunlit_periods = [d for d in orbit_data if not d["eclipse"]]
    eclipse_periods = [d for d in orbit_data if d["eclipse"]]
    
    if sunlit_periods:
        print(f"Sunlit phase (0-90° / 270-360°):")
        print(f"  Altitude: {np.mean([d['alt'] for d in sunlit_periods]):.1f} ± {np.std([d['alt'] for d in sunlit_periods]):.1f} km")
        print(f"  Avg SOC: {np.mean([d['soc'] for d in sunlit_periods]):.1%}")
        print(f"  SOC range: {min([d['soc'] for d in sunlit_periods]):.1%} to {max([d['soc'] for d in sunlit_periods]):.1%}")
    
    if eclipse_periods:
        print(f"\nEclipse phase (90-270°):")
        print(f"  Altitude: {np.mean([d['alt'] for d in eclipse_periods]):.1f} ± {np.std([d['alt'] for d in eclipse_periods]):.1f} km")
        print(f"  Avg SOC: {np.mean([d['soc'] for d in eclipse_periods]):.1%}")
        print(f"  SOC range: {min([d['soc'] for d in eclipse_periods]):.1%} to {max([d['soc'] for d in eclipse_periods]):.1%}")
    
    # ========================================================================
    # PART 4: Swarm formation geometry
    # ========================================================================
    print("\n" + "=" * 80)
    print("🛰️  Part 4: Swarm Formation Geometry (ECI Ranging)")
    print("-" * 80)
    print("Multi-satellite inter-distance for formation keeping\n")
    
    # Create constellation
    sats = [
        OrbitSimulator("SAT-LEAD"),
        OrbitSimulator("SAT-TRAIL"),
        OrbitSimulator("SAT-PORT"),
    ]
    
    # Offset second satellite by 45°
    sats[1]._true_anomaly_deg = 45
    # Offset third satellite by 90°
    sats[2]._true_anomaly_deg = 90
    
    print("Initial constellation configuration:\n")
    
    # Print initial state
    positions = []
    for sat in sats:
        pos = sat.get_position_eci()
        positions.append(pos)
        ta = sat._true_anomaly_deg
        print(f"  {sat.sat_id:12s}: True Anomaly = {ta:6.1f}° | ECI = ({pos[0]:7.1f}, {pos[1]:7.1f}, {pos[2]:7.1f}) km")
    
    # Compute inter-satellite distances
    print("\nInter-satellite distances (formation keeping):\n")
    
    distances = []
    for i, sat1 in enumerate(sats):
        for j, sat2 in enumerate(sats):
            if i < j:
                dist = sat1.get_relative_distance_to(sat2)
                distances.append(dist)
                status = "✅ Close" if dist < 10 else "⚠️  Medium" if dist < 100 else "❌ Far"
                print(f"  {sat1.sat_id} ↔ {sat2.sat_id}: {dist:6.1f} km {status}")
    
    # ========================================================================
    # PART 5: Physics insights
    # ========================================================================
    print("\n" + "=" * 80)
    print("📊 Key Orbital Physics")
    print("=" * 80)
    print("""
1. LEO ORBITAL PARAMETERS:
   - Altitude: 420 km above Earth surface
   - Period: 90 minutes (5400 seconds)
   - Mean motion: 15.72 revolutions/day
   - Ground speed: ~7660 m/s (27,600 km/h)
   
2. ECLIPSE GEOMETRY:
   - Shadow angle: 90° to 270° true anomaly
   - Eclipse duration: ~45 minutes per orbit
   - Sunlight duration: ~45 minutes per orbit
   - Perfect for power budget cycling
   
3. ALTITUDE "BREATHING":
   - J2 perturbation: ±500 meters
   - Completes 2 cycles per orbit
   - Caused by Earth's oblateness (J2 term)
   - Affects orbital decay rates
   
4. SWARM FORMATION:
   - Close formation: < 10 km inter-satellite distance
   - Relative velocity: ~7-8 m/s (can maintain formation)
   - Ranging: Each satellite computes distance via ECI positions
   - Formation keeping: Requires active propulsion/attitude control
   
5. CROSS-COUPLING:
   - Eclipse → Solar power disabled → Battery discharge
   - Solar exposure → Thermal heating → Temperature rise
   - Attitude error → Solar panel misalignment → Less power
   - Result: Tight coupling between all subsystems
""")
    
    print("=" * 80)
    print("✅ Full physics stack complete! Orbit → Power → Thermal → Formation")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(demo_orbit())
