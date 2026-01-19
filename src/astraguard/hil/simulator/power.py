"""
Realistic CubeSat EPS (Electrical Power System) simulation with orbital power cycles.

This module provides physics-based power system dynamics including solar generation,
battery charging/discharging, and orbital eclipse cycles typical of LEO operations.
"""

import numpy as np
from typing import Optional
from datetime import datetime
from .faults.power_brownout import PowerBrownoutFault


class PowerSimulator:
    """
    Electrical Power System simulator for 3U CubeSat in LEO.
    
    Models:
    - 2x 18650 LiIon batteries (8.4V nominal, 3.5Ah each = 7Ah total)
    - 6x 3U deployable solar panels (12 cm² effective area)
    - 90-minute orbital period with 40min sun / 10min eclipse
    - Realistic load profile (ADCS, comms, payload)
    """
    
    def __init__(self, sat_id: str):
        """
        Initialize power system.
        
        Args:
            sat_id: Satellite identifier
        """
        self.sat_id = sat_id
        self.start_time = datetime.now()
        self.elapsed_time = 0.0
        
        # Battery: 2x 18650 LiIon cells in series
        # Nominal voltage: 3.7V * 2 = 7.4V, so 8.4V with boost converter
        self.battery_capacity_ah = 7.0  # Total capacity (Ah)
        self.battery_soc = 0.85  # Initial 85% state of charge
        self.battery_voltage = 8.2  # V
        self.battery_temp = 20.0  # °C (nominal)
        
        # Solar panels: 6x deployable arrays on 3U form factor
        self.solar_efficiency = 0.28  # Triple-junction cells @ 28%
        self.panel_area_m2 = 0.12  # Total deployed area (m²)
        self.solar_constant = 1366.0  # W/m² at Earth orbit
        self._panel_degradation = 1.0  # Degradation factor (1.0 = nominal)
        
        # Orbital mechanics
        self._orbit_phase = 0.0  # 0-360° true anomaly
        self.orbital_period_s = 5400  # 90 minutes
        self.sun_phase_start = 45  # Sun exposure starts at 45°
        self.sun_phase_end = 225  # Eclipse starts at 225°
        
        # Load profile
        self.nominal_load_w = 5.0  # Base load (Comms + ADCS + payload)
        self.eclipse_load_w = 3.0  # Reduced load during eclipse (safe mode)
        
        # Fault state
        self._fault_active = False
        self._fault_type = None
        self._brownout_fault: Optional[PowerBrownoutFault] = None
    
    def update(self, dt: float = 1.0, sun_exposure: float = 1.0) -> None:
        """
        Propagate power system state forward dt seconds.
        
        Includes orbital position, solar generation, and battery dynamics.
        
        Args:
            dt: Time step in seconds (default 1.0 = 1Hz telemetry)
            sun_exposure: Environmental factor (1.0 = nominal, <1.0 = atmospheric effects)
        """
        self.elapsed_time += dt
        
        # Update orbital phase (deg/s at LEO altitude)
        # LEO orbital rate: ~0.0635°/s = 360°/5400s
        orbital_rate_deg_per_s = 360.0 / self.orbital_period_s
        self._orbit_phase = (self._orbit_phase + orbital_rate_deg_per_s * dt) % 360.0
        
        # Determine if in eclipse
        in_eclipse = self._is_in_eclipse()
        
        # Calculate solar power generation
        if not in_eclipse:
            # Solar irradiance accounting for incident angle
            # Assume sun exposure varies with position in orbit
            solar_flux = self.solar_constant * sun_exposure * self._panel_degradation
            
            # Power = Irradiance * Area * Efficiency
            solar_power_w = solar_flux * self.panel_area_m2 * self.solar_efficiency
        else:
            solar_power_w = 0.0
        
        # Select appropriate load
        load_w = self.eclipse_load_w if in_eclipse else self.nominal_load_w
        
        # Apply brownout fault if active
        if self._brownout_fault and self._brownout_fault.active:
            fault_state = self._brownout_fault.get_fault_state()
            
            if fault_state["active"]:
                # Phase 1: Solar panel degradation
                solar_power_w *= fault_state["panel_damage_factor"]
                
                # Phase 2: Battery discharge acceleration
                # Increased nominal/eclipse loads
                if fault_state["phase"] == "battery_stress":
                    load_w *= fault_state["discharge_multiplier"]
                
                # Phase 3: Safe-mode load spike
                if fault_state["phase"] == "safe_mode":
                    load_w = fault_state["safe_mode_load"]
                
                # Check if fault expired
                if self._brownout_fault.is_expired():
                    self._brownout_fault.active = False
                    self._panel_degradation = 1.0  # Recovery
        
        # Battery charge/discharge dynamics
        net_power_w = solar_power_w - load_w
        
        # Convert power to charge/discharge in Ah
        # Energy = Power * Time (Wh)
        # Charge = Energy / Voltage (Ah)
        energy_change_wh = net_power_w * (dt / 3600.0)  # Convert seconds to hours
        charge_change_ah = energy_change_wh / 8.4  # Nominal bus voltage
        
        # Update SOC
        soc_change = charge_change_ah / self.battery_capacity_ah
        self.battery_soc = np.clip(self.battery_soc + soc_change, 0.0, 1.0)
        
        # Update voltage based on SOC (realistic LiIon curve)
        # 8.4V at 100% SOC, ~6.5V at 0% SOC
        self.battery_voltage = 8.4 - (1.0 - self.battery_soc) * 1.9
        
        # Thermal effects (simplified)
        if not in_eclipse and solar_power_w > 5.0:
            self.battery_temp = 20.0 + (solar_power_w / 10.0)  # Heat from power
        else:
            self.battery_temp = 20.0 - (3.0 if in_eclipse else 0)  # Radiative cooling
    
    def _is_in_eclipse(self) -> bool:
        """
        Determine if satellite is in Earth's eclipse shadow.
        
        Returns:
            True if in eclipse, False if in sunlight
        """
        # Eclipse shadow spans 135° of 360° orbit (roughly)
        # Simplified: eclipse from 135° to 225° (90-minute orbit geometry)
        eclipse_start = 135.0
        eclipse_end = 225.0
        
        phase = self._orbit_phase % 360.0
        return eclipse_start <= phase <= eclipse_end
    
    def inject_brownout_fault(self, severity: float = 1.0) -> None:
        """
        Inject power brownout fault.
        
        Simulates solar panel damage and increased power consumption.
        
        Args:
            severity: Fault severity (0.0-1.0), where 1.0 is worst case
        """
        self._fault_active = True
        self._fault_type = "power_brownout"
        
        # Panel degradation from micrometeorite damage
        self._panel_degradation *= (1.0 - severity * 0.5)
    
    def recover_power_system(self) -> None:
        """Recover from power fault (e.g., MPPT recovery)."""
        self._fault_active = False
        self._fault_type = None
    
    def get_power_data(self):
        """
        Get current power system state as PowerData model.
        
        Returns:
            PowerData with voltage, SOC, solar/load currents
        """
        from ..schemas.telemetry import PowerData
        
        # Calculate currents at nominal bus voltage
        if not self._is_in_eclipse():
            solar_flux = self.solar_constant * self._panel_degradation
            solar_power_w = (
                solar_flux * self.panel_area_m2 * self.solar_efficiency
            )
        else:
            solar_power_w = 0.0
        
        load_w = self.eclipse_load_w if self._is_in_eclipse() else self.nominal_load_w
        
        # Apply fault effects
        if self._fault_active and self._fault_type == "power_brownout":
            solar_power_w *= 0.5
            load_w *= 1.3
        
        solar_current = solar_power_w / max(self.battery_voltage, 1.0)
        load_current = load_w / max(self.battery_voltage, 1.0)
        
        return PowerData(
            battery_voltage=round(self.battery_voltage, 2),
            battery_soc=round(self.battery_soc, 3),
            solar_current=round(solar_current, 3),
            load_current=round(load_current, 3)
        )
    
    def get_status(self) -> dict:
        """
        Get comprehensive power system status.
        
        Returns:
            Dict with detailed power state information
        """
        return {
            "orbit_phase": round(self._orbit_phase, 1),
            "in_eclipse": self._is_in_eclipse(),
            "battery_soc": round(self.battery_soc, 3),
            "battery_voltage": round(self.battery_voltage, 2),
            "battery_temp": round(self.battery_temp, 1),
            "panel_degradation": round(self._panel_degradation, 3),
            "fault_active": self._fault_active,
            "elapsed_time": round(self.elapsed_time, 1)
        }
    
    def inject_brownout_fault(self, severity: float = 1.0, duration: float = 300.0):
        """Inject configurable power brownout fault.
        
        Creates a multi-phase brownout fault:
        - Phase 1 (0-60s): Solar panel damage
        - Phase 2 (60-180s): Battery discharge acceleration
        - Phase 3 (180s+): Safe-mode load spike
        
        Args:
            severity: Fault severity (0.1-1.0)
                - 0.1: Minor (60% panel loss)
                - 0.5: Medium (75% panel loss)
                - 0.9: Severe (90% panel loss)
            duration: Total fault duration in seconds (default 300s = 5min)
        """
        self._brownout_fault = PowerBrownoutFault(self.sat_id, severity, duration)
        self._brownout_fault.inject()
        self._fault_active = True
        self._fault_type = "power_brownout"
        
        # Apply initial degradation from fault
        fault_state = self._brownout_fault.get_fault_state()
        self._panel_degradation = fault_state["panel_damage_factor"]
