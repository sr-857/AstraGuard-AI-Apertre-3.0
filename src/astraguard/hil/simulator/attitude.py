"""
Realistic CubeSat attitude simulation with quaternion dynamics.

This module provides physics-based attitude propagation for LEO satellites,
enabling realistic testing of formation keeping and fault recovery scenarios.
"""

import numpy as np
from typing import Tuple
import math
from datetime import datetime


class AttitudeSimulator:
    """
    Quaternion-based attitude dynamics for LEO CubeSats.
    
    Simulates realistic spacecraft attitude using quaternion representation,
    angular velocity integration, and controllable fault modes.
    """
    
    def __init__(self, sat_id: str):
        """
        Initialize attitude simulator for a satellite.
        
        Args:
            sat_id: Satellite identifier
        """
        self.sat_id = sat_id
        self.start_time = datetime.now()
        
        # Attitude state: normalized quaternion [w, x, y, z]
        # Initially pointed nadir (toward Earth)
        self._quaternion = np.array([1.0, 0.0, 0.0, 0.0], dtype=float)
        
        # Angular velocity [rad/s] in body frame
        # Small z-bias from orbital mechanics
        self._angular_velocity = np.array([0.0, 0.0, 0.001], dtype=float)
        
        # Control mode
        self._mode = "nadir_pointing"  # nominal mode
        self._fault_active = False
        self._tumble_start = None
    
    def update(self, dt: float = 1.0) -> None:
        """
        Propagate attitude dynamics forward dt seconds.
        
        Args:
            dt: Time step in seconds
        """
        if self._fault_active and self._mode == "tumble":
            # Tumble mode: chaotic rotation with random perturbations
            # This simulates reaction wheel failure causing uncontrolled spin
            self._angular_velocity += np.random.normal(0, 0.02, 3)
            self._angular_velocity = np.clip(self._angular_velocity, -0.5, 0.5)
        else:
            # Nominal: small damping to stabilize attitude
            self._angular_velocity *= 0.98
        
        # Quaternion integration using exponential map
        # q_new = q_old * exp(0.5 * ω * dt)
        omega = self._angular_velocity
        omega_norm = np.linalg.norm(omega)
        
        if omega_norm > 1e-6:
            # Compute quaternion increment
            angle = omega_norm * dt * 0.5
            axis = omega / omega_norm
            
            q_increment = np.array([
                math.cos(angle),
                math.sin(angle) * axis[0],
                math.sin(angle) * axis[1],
                math.sin(angle) * axis[2]
            ])
            
            # Quaternion multiplication: q_new = q_old * q_increment
            self._quaternion = self._quaternion_multiply(self._quaternion, q_increment)
        
        # Normalize to maintain unit quaternion
        self._quaternion /= np.linalg.norm(self._quaternion)
    
    def inject_tumble_fault(self) -> None:
        """
        Reaction wheel failure → uncontrolled tumble.
        
        Simulates a reaction wheel mechanical failure causing the satellite
        to enter an uncontrolled tumbling state.
        """
        self._fault_active = True
        self._mode = "tumble"
        self._tumble_start = datetime.now()
        
        # Impart random angular velocity (tumble spin)
        self._angular_velocity = np.random.uniform(-0.3, 0.3, 3)
    
    def recover_control(self) -> None:
        """
        ADCS (Attitude Determination and Control System) recovery successful.
        
        Simulates successful recovery from tumble through thrusters or
        magnetic torquers.
        """
        self._fault_active = False
        self._mode = "nadir_pointing"
        
        # Gradually dampen angular velocity during recovery
        self._angular_velocity *= 0.05
    
    def get_attitude_data(self):
        """
        Get current attitude state as AttitudeData model.
        
        Returns:
            AttitudeData with current quaternion, angular velocity, and error
        """
        from ..schemas.telemetry import AttitudeData
        
        # Calculate nadir pointing error
        # Nadir direction in ECF: [0, 0, 1] (spacecraft +Z points toward Earth)
        nadir_ecf = np.array([0.0, 0.0, 1.0])
        
        # Body z-axis (spacecraft pointing direction)
        z_body = self._quaternion_rotate_vector(self._quaternion, np.array([0.0, 0.0, 1.0]))
        
        # Nadir error: angle between body z-axis and nadir
        cos_angle = np.clip(np.dot(z_body, nadir_ecf), -1.0, 1.0)
        nadir_error_deg = math.degrees(math.acos(cos_angle))
        
        return AttitudeData(
            quaternion=self._quaternion.tolist(),
            angular_velocity=self._angular_velocity.tolist(),
            nadir_pointing_error_deg=round(nadir_error_deg, 2)
        )
    
    @staticmethod
    def _quaternion_multiply(q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
        """
        Multiply two quaternions: q_result = q1 * q2.
        
        Args:
            q1: First quaternion [w, x, y, z]
            q2: Second quaternion [w, x, y, z]
            
        Returns:
            Product quaternion [w, x, y, z]
        """
        w1, x1, y1, z1 = q1
        w2, x2, y2, z2 = q2
        
        return np.array([
            w1*w2 - x1*x2 - y1*y2 - z1*z2,
            w1*x2 + x1*w2 + y1*z2 - z1*y2,
            w1*y2 - x1*z2 + y1*w2 + z1*x2,
            w1*z2 + x1*y2 - y1*x2 + z1*w2
        ])
    
    @staticmethod
    def _quaternion_rotate_vector(q: np.ndarray, v: np.ndarray) -> np.ndarray:
        """
        Rotate a vector using a quaternion: v_rotated = q * v * q^*.
        
        Args:
            q: Quaternion [w, x, y, z]
            v: Vector [x, y, z]
            
        Returns:
            Rotated vector [x, y, z]
        """
        # Convert vector to quaternion form [0, x, y, z]
        v_quat = np.array([0.0, v[0], v[1], v[2]])
        
        # Conjugate of q: q* = [w, -x, -y, -z]
        q_conj = np.array([q[0], -q[1], -q[2], -q[3]])
        
        # Compute q * v * q^*
        result = AttitudeSimulator._quaternion_multiply(
            q,
            AttitudeSimulator._quaternion_multiply(v_quat, q_conj)
        )
        
        # Extract vector part [x, y, z]
        return result[1:]
    
    def get_tumble_duration(self) -> float:
        """
        Get duration of current tumble (if active).
        
        Returns:
            Duration in seconds, or 0 if not tumbling
        """
        if self._fault_active and self._tumble_start:
            return (datetime.now() - self._tumble_start).total_seconds()
        return 0.0
    
    def get_status(self) -> dict:
        """
        Get comprehensive status dictionary.
        
        Returns:
            Dict with mode, fault status, and quaternion info
        """
        return {
            "mode": self._mode,
            "fault_active": self._fault_active,
            "quaternion_norm": float(np.linalg.norm(self._quaternion)),
            "angular_velocity_magnitude": float(np.linalg.norm(self._angular_velocity)),
            "tumble_duration": self.get_tumble_duration()
        }
