"""
Abstract base class and utilities for satellite HIL simulation.

This module provides the foundational SatelliteSimulator abstract base class
that powers all HIL testing for AstraGuard swarm behaviors.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime
from ..schemas.telemetry import (
    TelemetryPacket,
    AttitudeData,
    PowerData,
    ThermalData,
    OrbitData,
)
from .attitude import AttitudeSimulator
from .power import PowerSimulator
from .thermal import ThermalSimulator
from .orbit import OrbitSimulator
from .comms import CommsSimulator


class SatelliteSimulator(ABC):
    """
    Abstract base class for all CubeSat HIL simulation.
    
    Defines the core interface that all satellite simulator implementations must follow,
    including telemetry generation, fault injection, and lifecycle management.
    """
    
    def __init__(self, sat_id: str):
        """
        Initialize a satellite simulator.
        
        Args:
            sat_id: Unique identifier for this satellite
        """
        self.sat_id = sat_id
        self._running = False
        self._telemetry_history: List[TelemetryPacket] = []
    
    @abstractmethod
    async def generate_telemetry(self) -> TelemetryPacket:
        """
        Generate one telemetry packet for this satellite.
        
        Returns:
            TelemetryPacket with current satellite state
        """
        pass
    
    @abstractmethod
    async def inject_fault(
        self, 
        fault_type: str, 
        severity: float = 1.0, 
        duration: float = 60.0
    ) -> None:
        """
        Inject configurable fault into satellite simulation.
        
        Args:
            fault_type: Type of fault to inject (e.g., 'power_brownout', 'thermal_spike')
            severity: Fault severity on scale 0.0-1.0
            duration: Fault duration in seconds
        """
        pass
    
    def start(self) -> None:
        """Mark simulator as running (for orchestration)."""
        self._running = True
    
    def stop(self) -> None:
        """Mark simulator as stopped."""
        self._running = False
    
    def get_telemetry_history(self) -> List[TelemetryPacket]:
        """
        Get copy of telemetry history.
        
        Returns:
            List of all recorded TelemetryPackets
        """
        return self._telemetry_history.copy()
    
    def record_telemetry(self, packet: TelemetryPacket) -> None:
        """
        Internal method: append telemetry packet to history.
        
        Args:
            packet: TelemetryPacket to record
        """
        self._telemetry_history.append(packet)
    
    def add_nearby_sat(self, sat_id: str, distance_km: float) -> None:
        """
        Register nearby satellite in formation for cascade propagation.
        
        Used for thermal cascade and comms range calculations in formation.
        
        Args:
            sat_id: Satellite identifier string
            distance_km: Distance to this satellite (km)
        """
        from .faults.thermal_runaway import NeighborProximity
        self.thermal_sim.nearby_sats.append(NeighborProximity(sat_id, distance_km, 1.0))


class StubSatelliteSimulator(SatelliteSimulator):
    """
    Temporary concrete implementation of SatelliteSimulator for testing.
    
    Generates realistic LEO telemetry values and simulates fault states.
    This stub will be replaced by specialized implementations in subsequent PRs.
    """
    
    def __init__(self, sat_id: str):
        """Initialize stub simulator."""
        super().__init__(sat_id)
        self._fault_active = False
        self._fault_type: Optional[str] = None
        
        # Attitude dynamics simulator
        self.attitude_sim = AttitudeSimulator(sat_id)
        self._tumble_injected = False
        
        # Power system simulator
        self.power_sim = PowerSimulator(sat_id)
        
        # Thermal dynamics simulator
        self.thermal_sim = ThermalSimulator(sat_id)
        
        # Orbital mechanics simulator
        self.orbit_sim = OrbitSimulator(sat_id)
        
        # Communications simulator
        self.comms_sim = CommsSimulator(sat_id)
        self._comms_fault: Optional[object] = None
    
    async def generate_telemetry(self) -> TelemetryPacket:
        """
        Generate LEO satellite telemetry with production schemas.
        
        Returns telemetry with realistic orbital, attitude, power, and thermal dynamics.
        Propagates all physics in correct order: orbit → attitude → power → thermal.
        """
        import random
        
        timestamp = datetime.now()
        
        # Update orbital mechanics first (drives eclipse timing and altitude)
        self.orbit_sim.update(dt=1.0)
        orbit = self.orbit_sim.get_orbit_data()
        
        # Update attitude dynamics (1Hz telemetry)
        self.attitude_sim.update(dt=1.0)
        
        # Eclipse timing from orbital true anomaly (90-270° = in shadow)
        is_eclipse = self.orbit_sim.is_in_eclipse()
        
        # Update power dynamics - attitude affects solar panel exposure + eclipse disables solar
        nadir_error = self.attitude_sim.get_attitude_data().nadir_pointing_error_deg
        sun_exposure = 0.0 if is_eclipse else max(0.0, 1.0 - (nadir_error / 90.0))
        self.power_sim.update(dt=1.0, sun_exposure=sun_exposure)
        
        # Inject attitude fault if needed
        if self._fault_active and self._fault_type == "attitude_desync" and not self._tumble_injected:
            self.attitude_sim.inject_tumble_fault()
            self._tumble_injected = True
        
        # Recover control if fault is cleared
        if not self._fault_active and self._tumble_injected:
            self.attitude_sim.recover_control()
            self._tumble_injected = False
        
        # Get current attitude data
        attitude = self.attitude_sim.get_attitude_data()
        
        # Get power data
        power = self.power_sim.get_power_data()
        
        # Thermal dynamics: coupled to power state and attitude error
        # Use eclipse from orbit (more accurate than power current threshold)
        solar_flux = 1366.0 if not is_eclipse else 0.0
        attitude_error_deg = attitude.nadir_pointing_error_deg
        
        # Update thermal with coupled physics
        self.thermal_sim.update(
            dt=1.0,
            solar_flux=solar_flux,
            attitude_error_deg=attitude_error_deg,
            eclipse=is_eclipse
        )
        
        thermal = self.thermal_sim.get_thermal_data()
        
        # Update comms simulator - coupled to power and orbit (range)
        # Altitude in meters → range in km (simplified: altitude/1000)
        range_km = max(500.0, orbit.altitude_m / 1000.0)
        self.comms_sim.update(power_voltage=power.battery_voltage, range_km=range_km)
        
        # Build packet
        packet = TelemetryPacket(
            timestamp=timestamp,
            satellite_id=self.sat_id,
            attitude=attitude,
            power=power,
            thermal=thermal,
            orbit=orbit,
            mission_mode="nominal",
            ground_contact=random.choice([True, False])
        )
        
        self.record_telemetry(packet)
        return packet
    
    async def inject_fault(
        self, 
        fault_type: str, 
        severity: float = 1.0, 
        duration: float = 60.0
    ) -> None:
        """
        Inject fault into stub simulator.
        
        Args:
            fault_type: Type of fault (e.g., 'power_brownout', 'attitude_desync')
            severity: Fault severity (0.0-1.0)
            duration: Fault duration in seconds
        """
        self._fault_active = True
        self._fault_type = fault_type
        
        if fault_type == "power_brownout":
            self.power_sim.inject_brownout_fault(severity)
        elif fault_type == "attitude_desync":
            # Attitude fault will be injected on next telemetry generation
            pass
        elif fault_type == "thermal_runaway":
            # Cascade fault: contagion_rate = 0.3 + severity * 0.4 (0.3-0.7 range)
            contagion_rate = 0.3 + severity * 0.4
            self.thermal_sim.inject_runaway_fault(contagion_rate=contagion_rate)
        elif fault_type == "comms_dropout":
            from .faults.comms_dropout import CommsDropoutFault
            packet_loss = 0.3 + severity * 0.5  # 0.3-0.8 based on severity
            self._comms_fault = CommsDropoutFault(
                self.sat_id, 
                pattern="gilbert", 
                packet_loss=packet_loss, 
                duration=duration
            )
            self._comms_fault.inject()
        
        print(
            f"Sat {self.sat_id}: Injected {fault_type} fault "
            f"(severity={severity}, duration={duration}s)"
        )
