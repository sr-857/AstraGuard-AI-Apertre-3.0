"""
HIL Demo #488: CubeSat EPS simulator with orbital power cycles.

This script demonstrates:
- Realistic power generation and consumption
- Orbital sunlight/eclipse cycling (90-minute orbit)
- Battery charge/discharge dynamics
- Brownout fault injection
- Solar panel degradation
"""

import asyncio
import numpy as np
from astraguard.hil.simulator.base import StubSatelliteSimulator


async def main():
    """Run power system demo."""
    print("=" * 80)
    print("AstraGuard HIL EPS (Power System) Demo #488")
    print("=" * 80)
    print()
    
    sim = StubSatelliteSimulator("POWER-DEMO")
    sim.start()
    
    print(f"✓ Initialized: {sim.sat_id}")
    print(f"  Battery: 7.0 Ah @ 8.4V nominal (3U CubeSat)")
    print(f"  Solar: 0.12 m² @ 28% efficiency")
    print(f"  Orbit: 90 minutes LEO (520km altitude)")
    print()
    
    # === SUNLIGHT/ECLIPSE CYCLE ===
    print("--- ORBITAL POWER CYCLE (One 90-minute Orbit) ---")
    print()
    print("Tracking power through complete orbit cycle...")
    print()
    
    print(f"{'Time(s)':<10} {'Phase':<12} {'SOC':<8} {'V(bus)':<8} {'I_sol':<8} {'I_load':<8}")
    print("-" * 60)
    
    orbit_data = []
    for cycle in range(90):  # Simulate at 60x speed: 90 cycles = 90 minutes
        for _ in range(60):  # 60 updates per cycle
            packet = await sim.generate_telemetry()
        
        orbit_data.append({
            "time": sim.power_sim.elapsed_time,
            "phase": "☀️" if not sim.power_sim._is_in_eclipse() else "🌑",
            "soc": packet.power.battery_soc,
            "voltage": packet.power.battery_voltage,
            "solar_i": packet.power.solar_current,
            "load_i": packet.power.load_current
        })
        
        # Print every 15 cycles (every quarter of orbit)
        if cycle % 15 == 0 or cycle == 89:
            d = orbit_data[-1]
            print(
                f"{d['time']:<10.0f} {d['phase']:<12} "
                f"{d['soc']:<8.1%} {d['voltage']:<8.2f} "
                f"{d['solar_i']:<8.2f} {d['load_i']:<8.2f}"
            )
    
    print()
    
    # === CYCLE STATISTICS ===
    print("--- CYCLE STATISTICS ---")
    soc_values = [d["soc"] for d in orbit_data]
    voltage_values = [d["voltage"] for d in orbit_data]
    
    print(f"SOC range:      {min(soc_values):.1%} → {max(soc_values):.1%}")
    print(f"SOC mean:       {np.mean(soc_values):.1%}")
    print(f"Voltage range:  {min(voltage_values):.2f}V → {max(voltage_values):.2f}V")
    print(f"Voltage mean:   {np.mean(voltage_values):.2f}V")
    
    # Identify eclipse periods
    eclipse_count = sum(1 for d in orbit_data if d['phase'] == '🌑')
    sunlight_count = sum(1 for d in orbit_data if d['phase'] == '☀️')
    print(f"Sunlight time:  {sunlight_count * 60}s ({sunlight_count/len(orbit_data)*100:.1f}%)")
    print(f"Eclipse time:   {eclipse_count * 60}s ({eclipse_count/len(orbit_data)*100:.1f}%)")
    print()
    
    # === BROWNOUT FAULT ===
    print("--- FAULT INJECTION: Power Brownout ---")
    print("(Simulates solar panel micrometeorite damage)")
    print()
    
    await sim.inject_fault("power_brownout", severity=0.8, duration=300.0)
    print()
    
    print("Tracking power during fault condition...")
    print()
    print(f"{'Time(s)':<10} {'Phase':<12} {'SOC':<8} {'V(bus)':<8} {'Degrad':<8}")
    print("-" * 50)
    
    fault_data = []
    for cycle in range(10):  # 10 minutes under fault
        for _ in range(60):
            packet = await sim.generate_telemetry()
        
        fault_data.append({
            "time": sim.power_sim.elapsed_time,
            "phase": "☀️" if not sim.power_sim._is_in_eclipse() else "🌑",
            "soc": packet.power.battery_soc,
            "voltage": packet.power.battery_voltage,
            "degradation": sim.power_sim._panel_degradation
        })
        
        if cycle % 2 == 0:
            d = fault_data[-1]
            print(
                f"{d['time']:<10.0f} {d['phase']:<12} "
                f"{d['soc']:<8.1%} {d['voltage']:<8.2f} "
                f"{d['degradation']:<8.1%}"
            )
    
    print()
    
    # === FAULT ANALYSIS ===
    print("--- FAULT IMPACT ANALYSIS ---")
    normal_soc = np.mean(soc_values)
    fault_soc = np.mean([d["soc"] for d in fault_data])
    normal_voltage = np.mean(voltage_values)
    fault_voltage = np.mean([d["voltage"] for d in fault_data])
    
    print(f"Normal SOC:     {normal_soc:.1%}")
    print(f"Fault SOC:      {fault_soc:.1%}")
    print(f"SOC degradation: {(normal_soc - fault_soc)*100:.1f}%")
    print()
    print(f"Normal voltage: {normal_voltage:.2f}V")
    print(f"Fault voltage:  {fault_voltage:.2f}V")
    print(f"Voltage drop:   {normal_voltage - fault_voltage:.2f}V")
    print()
    
    panel_degradation = sim.power_sim._panel_degradation
    print(f"Panel degradation: {panel_degradation:.1%} efficiency remaining")
    print()
    
    # === POWER BUDGET ===
    print("--- POWER BUDGET ANALYSIS ---")
    status = sim.power_sim.get_status()
    
    print(f"Current orbit phase: {status['orbit_phase']:.1f}° (0=sun, 180=eclipse)")
    print(f"In eclipse: {status['in_eclipse']}")
    print(f"Battery temperature: {status['battery_temp']:.1f}°C")
    print(f"Elapsed time: {status['elapsed_time']:.0f}s ({status['elapsed_time']/60:.1f}min)")
    print()
    
    # === TELEMETRY HISTORY ===
    print("--- TELEMETRY HISTORY ---")
    history = sim.get_telemetry_history()
    print(f"Total packets: {len(history)}")
    
    # Find min/max values
    powers = [p.power for p in history]
    soc_min = min(p.battery_soc for p in powers)
    soc_max = max(p.battery_soc for p in powers)
    v_min = min(p.battery_voltage for p in powers)
    v_max = max(p.battery_voltage for p in powers)
    
    print(f"SOC: {soc_min:.1%} → {soc_max:.1%}")
    print(f"Voltage: {v_min:.2f}V → {v_max:.2f}V")
    print()
    
    sim.stop()
    
    print("=" * 80)
    print("Demo Complete! EPS dynamics show realistic orbital power cycling.")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
