"""CubeSat thermal model with orbital heating + attitude coupling.

This module simulates realistic thermal dynamics for a 3U CubeSat:
- Solar heating coupled to attitude error (tumbling = thermal stress)
- Passive radiator cooling capacity
- Temperature state tracking for battery, EPS
- Thermal runaway fault model (radiator failure)
- 3-tier status: nominal/warning/critical for mission planning

Physics Model:
- Heat input = internal dissipation + solar absorption (attitude-dependent)
- Solar absorption increases with nadir pointing error (tumbling oven effect)
- Passive cooling scales with temperature gradient to space (3K background)
- Runaway fault degrades radiator to 20% capacity (realistic degradation)
- Battery > 60°C triggers critical status and thermal runaway cascade
"""

import numpy as np
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from ..schemas.telemetry import ThermalData


class ThermalSimulator:
    """3U CubeSat thermal dynamics with radiator + heater control.
    
    Attributes:
        sat_id: Satellite identifier (max 16 chars for telemetry)
        battery_temp: Battery pack temperature (°C)
        eps_temp: EPS (power module) temperature (°C)
        payload_temp: Payload module temperature (°C)
        base_heat_w: Internal dissipation (W) - electronics/motors
        radiator_capacity_wk: Passive radiator cooling (W/K)
        heater_power_w: Heater output when active (W)
        status: Thermal status (nominal/warning/critical)
    """
    
    def __init__(self, sat_id: str):
        """Initialize thermal simulator.
        
        Args:
            sat_id: Satellite identifier string (max 16 chars)
        
        Raises:
            ValueError: If sat_id exceeds 16 characters
        """
        if len(sat_id) > 16:
            raise ValueError(f"sat_id '{sat_id}' exceeds 16 character limit")
        
        self.sat_id = sat_id
        
        # Initial temperatures (°C) - starting at nominal Earth orbit conditions
        self.battery_temp = 15.0  # Colder initially
        self.eps_temp = 20.0      # Electronics at room temperature
        self.payload_temp = 18.0  # Payload nominal
        
        # Thermal parameters for 3U CubeSat with deployable radiators
        # Based on realistic CubeSat thermal analysis (JSC 20793 standards)
        self.base_heat_w = 4.0              # Internal dissipation (W): electronics + motors
        self.radiator_capacity_wk = 8.0     # Passive cooling: 8W per °C above background (3K space)
        self.heater_power_w = 2.0           # Active heater (W) - for eclipse thermal control
        
        # Thermal mass (J/°C) - represents heat capacity of satellite structure
        self.battery_thermal_mass = 50.0    # Battery pack has larger mass
        self.eps_thermal_mass = 40.0        # Power module thermal mass
        
        # Status tracking
        self.status = "nominal"             # thermal state: nominal/warning/critical
        self._fault_active = False          # Runaway fault flag
        self._runaway_triggered = False     # Persistent runaway state
        self._time_in_critical = 0.0        # Tracks duration at critical temp
        
        # Cascade/formation awareness
        self._thermal_fault: Optional[object] = None  # ThermalRunawayFault instance
        self.nearby_sats: List[object] = []  # NeighborProximity list for formation
        
    def update(self, dt: float, solar_flux: float, attitude_error_deg: float, eclipse: bool = False):
        """Propagate thermal state with coupled physics and cascade effects.
        
        Heat flow model:
        - Solar heating: absorption increases with attitude error (tumbling = oven)
        - Internal heating: base electronics dissipation
        - Radiative cooling: proportional to temp above background (3K space)
        - Eclipse: reduced solar input
        - Fault: degraded radiator capacity
        - Cascade: nearby infected satellites add heat input
        
        Args:
            dt: Time step (seconds)
            solar_flux: Solar irradiance (W/m²) - 1366 W/m² at 1 AU in sunlight, 0 in eclipse
            attitude_error_deg: Nadir pointing error (degrees) - affects solar absorption
            eclipse: Whether satellite is in eclipse (affects solar and cooling)
        
        Physics validation:
            - Attitude error 0-90°: absorption multiplier 1.0-2.0 (tumble = 2x heating)
            - Eclipse: solar_flux forced to 0 regardless of input
            - Temperature bounds: -40°C (cold case) to +80°C (survival limit)
            - Cascade: each nearby infected satellite adds 1-3W heat
        """
        # Enforce eclipse condition
        if eclipse:
            solar_flux = 0.0
        
        # Solar heating (W) - coupled to attitude error
        # Surface area: 0.18 m² per side × 3 sides = 0.54 m² exposed
        # Absorption coefficient: 0.15 (15% of solar radiation absorbed, rest reflected)
        # Attitude multiplier: sin(error_deg) for effective surface area increase
        # At error=0°: absorption = 1366 * 0.54 * 0.15 = 110W
        # At error=90° (tumbling): absorption = 1366 * 0.54 * 0.15 * 2.0 = 220W
        attitude_multiplier = 1.0 + (attitude_error_deg / 90.0)  # 1.0 to 2.0 range
        solar_heating_w = solar_flux * 0.54 * 0.15 * attitude_multiplier
        
        # Total heat input (W)
        total_heat_w = self.base_heat_w + solar_heating_w
        
        # Cascade effects: nearby infected satellites add heat input
        if self._thermal_fault and self._thermal_fault.active:
            # Each infected neighbor adds 1-3W ambient heat (thermal coupling)
            cascade_heat_w = len(self._thermal_fault.infected_neighbors) * 2.0
            total_heat_w += cascade_heat_w
            
            # Attempt to infect new neighbors each update
            for neighbor in self.nearby_sats:
                if neighbor.sat_id not in self._thermal_fault.infected_neighbors:
                    if self._thermal_fault.infect_neighbor(neighbor):
                        self._thermal_fault.infected_neighbors.append(neighbor.sat_id)
        
        # Thermal runaway fault: degraded radiator capacity
        radiator_capacity = self.radiator_capacity_wk
        if self._fault_active or (self._thermal_fault and self._thermal_fault.active):
            total_heat_w *= 1.8  # Heater power goes into heat instead of dissipating
            radiator_capacity *= 0.1  # 90% cooling loss - catastrophic radiator failure
        
        # Temperature rates (°C/s) using thermal mass and capacitance
        # Rate = (Heat in - Heat out) / Thermal mass
        # Heat out = radiator_capacity * (temp - background_3K ≈ temp - 0)
        # More conservative heating rate with larger thermal mass
        battery_cooling_w = radiator_capacity * max(0.1, self.battery_temp / 20.0) * 0.3  # Reduced cooling effect
        battery_rate = (total_heat_w * 0.4 - battery_cooling_w) / self.battery_thermal_mass
        
        eps_cooling_w = radiator_capacity * max(0.1, self.eps_temp / 20.0) * 0.6  # Reduced cooling effect
        eps_rate = (total_heat_w * 0.6 - eps_cooling_w) / self.eps_thermal_mass
        
        # Integrate temperatures
        self.battery_temp += battery_rate * dt
        self.eps_temp += eps_rate * dt
        
        # Status logic - threshold-based state machine
        if self.battery_temp > 60:
            self.status = "critical"
            self._runaway_triggered = True
            self._time_in_critical += dt
        elif self.battery_temp > 45:
            self.status = "warning"
            self._time_in_critical = 0.0
        else:
            self.status = "nominal"
            self._time_in_critical = 0.0
        
        # Saturate realistic bounds (CubeSat operational/survival limits)
        # Cold: -40°C minimum (battery chemistry limit)
        # Hot: +80°C maximum (component survival)
        self.battery_temp = np.clip(self.battery_temp, -40, 80)
        self.eps_temp = np.clip(self.eps_temp, -40, 85)
        self.payload_temp = np.clip(self.payload_temp, -40, 75)
    
    def inject_runaway_fault(self, contagion_rate: float = 0.2, severity: float = 1.0):
        """Inject thermal runaway fault with cascade contagion model.
        
        Primary infection: Creates radiator failure that spreads to nearby satellites
        through formation heat coupling. Implements distance-based infection probability.
        
        Args:
            contagion_rate: Base infection probability (0.05-0.8)
            severity: Fault severity 0.0-1.0 (1.0 = catastrophic 90% loss)
        """
        from .faults.thermal_runaway import ThermalRunawayFault
        
        # Create cascade fault with contagion parameters
        self._thermal_fault = ThermalRunawayFault(
            sat_id=self.sat_id,
            contagion_rate=contagion_rate,
            duration=600.0  # 10 minute cascade
        )
        
        # Activate primary infection
        self._thermal_fault.inject()
        self._fault_active = True
        
        # Degrade radiator capacity based on severity
        # severity 1.0 -> 0.1 multiplier (90% loss)
        # severity 0.0 -> 1.0 multiplier (0% loss)
        degradation_factor = 1.0 - (0.9 * severity)
        self.radiator_capacity_wk *= degradation_factor
    
    def recover_from_fault(self):
        """Recover from thermal fault (e.g., heater restart, radiator repairs).
        
        Resets fault flag - in reality would require ground control commands
        or autonomous recovery procedures. Radiator capacity restoration.
        """
        self._fault_active = False
        self.radiator_capacity_wk = 8.0  # Reset to nominal
        self._runaway_triggered = False
    
    def get_thermal_data(self) -> ThermalData:
        """Extract current thermal state as telemetry packet.
        
        Returns:
            ThermalData: Validated thermal telemetry with rounded precision
        
        Raises:
            ValueError: If temperature values violate schema constraints
        """
        return ThermalData(
            battery_temp=round(self.battery_temp, 1),
            eps_temp=round(self.eps_temp, 1),
            status=self.status
        )
    
    def get_debug_info(self) -> Dict:
        """Get detailed thermal debug information.
        
        Returns:
            Dict with internal state for diagnostics
        """
        return {
            "battery_temp": self.battery_temp,
            "eps_temp": self.eps_temp,
            "payload_temp": self.payload_temp,
            "status": self.status,
            "fault_active": self._fault_active,
            "runaway_triggered": self._runaway_triggered,
            "time_in_critical": self._time_in_critical,
            "radiator_capacity_wk": self.radiator_capacity_wk,
        }
