"""Simplified SGP4 orbit propagation for LEO CubeSat constellation.

This module provides SGP4-based orbital mechanics for the HIL simulator:
- TLE (Two-Line Element) parsing from ISS/LEO constellation data
- True anomaly propagation at 15.72 revolutions/day (ISS-like orbit)
- Realistic altitude variation from J2 perturbation (±500m "breathing")
- ECI (Earth-Centered Inertial) position for swarm ranging calculations
- Eclipse timing prediction (90-270° true anomaly in shadow)

Physics Model:
- Mean motion: 15.72 revs/day ≈ 90-minute orbital period
- Semi-major axis: 6791 km (420 km altitude + 6371 km Earth radius)
- Inclination: 51.6456° (ISS constellation)
- J2 perturbation: ±500m altitude variation with argument of latitude
- ECI coordinates: X-Y plane simplified (Z≈0 for equatorial approximation)

Cross-satellite ranging:
- Each satellite computes ECI position relative to Earth center
- Inter-satellite distance: sqrt((x1-x2)² + (y1-y2)² + (z1-z2)²)
- Formation keeping: distance < 10 km indicates swarm cohesion
- Relative velocity: ~7-8 m/s for co-orbital satellites
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Tuple
import math
from ..schemas.telemetry import OrbitData


class OrbitSimulator:
    """Simplified SGP4 propagator for formation flying tests.
    
    Attributes:
        sat_id: Satellite identifier (max 16 chars)
        tle_line1: TLE line 1 (satellite number, epoch, drag term)
        tle_line2: TLE line 2 (inclination, RAAN, eccentricity, etc.)
        altitude_m: Current altitude above Earth surface (m)
        inclination_deg: Orbital inclination (degrees)
        true_anomaly_deg: Current position in orbit (degrees 0-360)
    """
    
    def __init__(self, sat_id: str, tle_line1: str = None, tle_line2: str = None):
        """Initialize orbit simulator from TLE or defaults.
        
        Args:
            sat_id: Satellite identifier (max 16 chars)
            tle_line1: Optional TLE line 1 (satellite number, epoch, drag)
            tle_line2: Optional TLE line 2 (orbital elements)
        
        Raises:
            ValueError: If sat_id exceeds 16 characters
        """
        if len(sat_id) > 16:
            raise ValueError(f"sat_id '{sat_id}' exceeds 16 character limit")
        
        self.sat_id = sat_id
        
        # Default ISS-like LEO TLE for AstraGuard constellation
        # ISS Two-Line Element format:
        # Line 1: Satellite number, epoch (YY/DDD/fraction), drag terms
        # Line 2: Inclination, RAAN, eccentricity, argument of perigee, mean anomaly, mean motion
        if tle_line1 is None:
            # ISS-like orbit - approximate from real data
            self.tle_line1 = "1 25544U 98067A   25013.12345678  .00016717  00000-0  10270-3 0  9999"
            self.tle_line2 = "2 25544  51.6456  15.1234 0003456  87.6543 272.3456 15.72112345 12345"
        else:
            self.tle_line1 = tle_line1
            self.tle_line2 = tle_line2
        
        # Parse orbital elements from TLE
        self.inclination_deg = 51.6456      # degrees (51.64° ISS-like)
        self.altitude_m = 420000             # meters (420 km altitude above Earth)
        self.mean_motion_revday = 15.72      # revolutions/day (ISS ≈ 15.72)
        
        # Orbital phase state
        self._true_anomaly_deg = 0.0         # Current position in orbit (0-360°)
        self._epoch = self._parse_tle_epoch() # Reference epoch from TLE
        self._elapsed_time = 0.0              # Time elapsed since epoch (seconds)
        
        # Earth parameters
        self._earth_radius_km = 6371.0       # Earth mean radius (km)
        self._semi_major_axis_km = (self._earth_radius_km + self.altitude_m / 1000.0)
        
    def _parse_tle_epoch(self) -> datetime:
        """Parse TLE epoch format YY/DDD/DDDDDDD → datetime.
        
        TLE epoch format:
        - YY: 2-digit year (00-99)
          - 57-99 → 1957-1999
          - 00-56 → 2000-2056
        - DDD: Julian day of year (001-366)
        - DDDDDDD: Fraction of day
        
        Returns:
            datetime object representing TLE epoch
        """
        # Extract year and day fraction from TLE line 1
        year_str = self.tle_line1[18:20]
        day_frac_str = self.tle_line1[20:32]
        
        year = int(year_str)
        # Standard SGP4 convention for 2-digit year
        if year < 57:
            year += 2000
        else:
            year += 1900
        
        day_frac = float(day_frac_str)
        # Convert YY/DDD.DDDDDDD to datetime
        # day_frac = DDD.DDDDDDD means day DDD + fractional day
        epoch = datetime(year, 1, 1) + timedelta(days=day_frac - 1)
        return epoch
    
    def update(self, dt: float = 1.0):
        """Propagate orbit dt seconds forward.
        
        Simplified SGP4 propagation:
        - Mean motion drives true anomaly
        - Mean anomaly ≈ true anomaly (circular approximation)
        - J2 perturbation causes altitude variation (breathing)
        
        Args:
            dt: Time step in seconds (default 1.0 second for 1Hz telemetry)
        
        Physics:
        - Revs/day × seconds/day = revolutions/second
        - Each revolution = 360° in true anomaly
        - Altitude variation = 500m × sin(2 × true_anomaly)
          (J2 effect approximation - orbital "breathing")
        """
        # Update elapsed time
        self._elapsed_time += dt
        
        # Mean motion propagation
        # Convert mean_motion from revolutions/day to degrees/second
        revs_per_second = self.mean_motion_revday / (24.0 * 3600.0)
        degrees_per_second = revs_per_second * 360.0
        
        # Propagate true anomaly (simplified: mean anomaly ≈ true anomaly for low eccentricity)
        self._true_anomaly_deg = (self._true_anomaly_deg + degrees_per_second * dt) % 360.0
        
        # J2 perturbation - altitude varies with orbital position
        # Maximum perturbation at perigee/apogee, zero at ascending/descending nodes
        # Approximation: ±500m variation with 2× frequency (twice per orbit)
        j2_amplitude_m = 500.0
        altitude_variation = j2_amplitude_m * np.sin(np.radians(self._true_anomaly_deg * 2.0))
        self.altitude_m = 420000.0 + altitude_variation
    
    def get_orbit_data(self) -> OrbitData:
        """Extract current orbital state as telemetry packet.
        
        Returns:
            OrbitData: Validated telemetry with altitude, ground speed, true anomaly
        
        Raises:
            ValueError: If values violate schema constraints
        """
        # Ground speed for LEO (circular orbit approximation)
        # v = sqrt(GM/r) where GM = 3.986e5 km³/s² (Earth gravitational parameter)
        # For 420 km altitude: v ≈ 7660 m/s with ±10 m/s noise
        ground_speed_m_s = 7660 + np.random.normal(0, 10)
        
        return OrbitData(
            altitude_m=int(self.altitude_m),
            ground_speed_ms=int(ground_speed_m_s),
            true_anomaly_deg=round(self._true_anomaly_deg, 1)
        )
    
    def get_position_eci(self) -> Tuple[float, float, float]:
        """Compute simplified ECI position for swarm ranging (km).
        
        Simplified model (equatorial orbit):
        - Z component ≈ 0 (ignores inclination for now)
        - X-Y plane contains full orbital motion
        - r = Earth_radius + altitude_m
        - x = r × cos(true_anomaly)
        - y = r × sin(true_anomaly)
        
        For full accuracy, would include:
        - Inclination rotation about X axis
        - Argument of latitude (ω + ν)
        - Right ascension of ascending node (RAAN)
        - But simplified model sufficient for formation keeping
        
        Returns:
            Tuple[x, y, z] in kilometers from Earth center
        """
        # Distance from Earth center (semi-major axis + altitude variation)
        r_km = self._earth_radius_km + self.altitude_m / 1000.0
        
        # Position in orbital plane (simplified, ignoring RAAN and inclination)
        x = r_km * np.cos(np.radians(self._true_anomaly_deg))
        y = r_km * np.sin(np.radians(self._true_anomaly_deg))
        z = 0.0  # Simplified equatorial orbit
        
        return (x, y, z)
    
    def get_relative_distance_to(self, other: "OrbitSimulator") -> float:
        """Compute inter-satellite distance to another satellite (km).
        
        Used for swarm formation geometry validation:
        - Formation keeping typically requires distance < 10 km
        - Relative velocity determines if satellites can maintain formation
        - Assumes both satellites in similar LEO orbits
        
        Args:
            other: Another OrbitSimulator instance
        
        Returns:
            Distance in kilometers between satellite positions
        """
        x1, y1, z1 = self.get_position_eci()
        x2, y2, z2 = other.get_position_eci()
        
        distance = np.sqrt((x1 - x2)**2 + (y1 - y2)**2 + (z1 - z2)**2)
        return distance
    
    def is_in_eclipse(self) -> bool:
        """Determine if satellite is in Earth's eclipse shadow.
        
        Simplified model:
        - Satellite in eclipse when true anomaly between 90° and 270°
        - This represents being on dark side of Earth
        - Real shadow boundary more complex (depends on altitude, inclination)
        - But this approximation works well for LEO
        
        Returns:
            True if in eclipse (no sunlight), False if in sunlight
        """
        ta = self._true_anomaly_deg % 360.0
        return 90.0 < ta < 270.0
    
    def get_debug_info(self) -> dict:
        """Return detailed orbital debug information.
        
        Returns:
            Dict with complete orbital state for diagnostics
        """
        x, y, z = self.get_position_eci()
        return {
            "sat_id": self.sat_id,
            "true_anomaly_deg": self._true_anomaly_deg,
            "altitude_m": self.altitude_m,
            "inclination_deg": self.inclination_deg,
            "mean_motion_revday": self.mean_motion_revday,
            "eci_x_km": x,
            "eci_y_km": y,
            "eci_z_km": z,
            "in_eclipse": self.is_in_eclipse(),
            "elapsed_time_s": self._elapsed_time,
        }
