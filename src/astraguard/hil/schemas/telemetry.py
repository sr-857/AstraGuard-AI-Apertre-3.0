"""
Production Pydantic models for all AstraGuard HIL telemetry.

This module provides the single source of truth for telemetry data structures
across the entire HIL pipeline: simulator → swarm agents → BDH.
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional
from datetime import datetime


class AttitudeData(BaseModel):
    """Satellite attitude and orientation data."""
    
    quaternion: list = Field(..., description="Normalized quaternion [w, x, y, z]")
    angular_velocity: list = Field(..., description="Angular velocity [rad/s] in body frame")
    nadir_pointing_error_deg: float = Field(
        ...,
        ge=0,
        le=180,
        description="Nadir pointing error in degrees"
    )
    
    @field_validator("quaternion", mode="before")
    @classmethod
    def validate_quaternion(cls, v):
        """Ensure quaternion is exactly 4 floats."""
        if not isinstance(v, (list, tuple)):
            raise ValueError("quaternion must be a list or tuple")
        if len(v) != 4:
            raise ValueError(f"quaternion must have exactly 4 elements, got {len(v)}")
        try:
            v = [float(x) for x in v]
        except (TypeError, ValueError):
            raise ValueError("quaternion elements must be convertible to float")
        return v
    
    @field_validator("angular_velocity", mode="before")
    @classmethod
    def validate_angular_velocity(cls, v):
        """Ensure angular velocity is exactly 3 floats."""
        if not isinstance(v, (list, tuple)):
            raise ValueError("angular_velocity must be a list or tuple")
        if len(v) != 3:
            raise ValueError(f"angular_velocity must have exactly 3 elements, got {len(v)}")
        try:
            v = [float(x) for x in v]
        except (TypeError, ValueError):
            raise ValueError("angular_velocity elements must be convertible to float")
        return v


class PowerData(BaseModel):
    """Battery and power system data."""
    
    battery_voltage: float = Field(
        ...,
        ge=0,
        le=30,
        description="Battery voltage in volts (nominal ~8.4V for LiIon)"
    )
    battery_soc: float = Field(
        ...,
        ge=0,
        le=1,
        description="Battery state of charge (0.0 = empty, 1.0 = full)"
    )
    solar_current: float = Field(
        ...,
        ge=0,
        description="Solar panel current in amps"
    )
    load_current: float = Field(
        ...,
        ge=0,
        description="Total load current in amps"
    )


class ThermalData(BaseModel):
    """Temperature and thermal status data."""
    
    battery_temp: float = Field(
        ...,
        ge=-50,
        le=85,
        description="Battery temperature in Celsius"
    )
    eps_temp: float = Field(
        ...,
        ge=-50,
        le=85,
        description="Electrical Power System temperature in Celsius"
    )
    status: str = Field(
        ...,
        description="Thermal status: nominal, warning, or critical"
    )
    
    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        """Ensure status is valid."""
        valid_statuses = {"nominal", "warning", "critical"}
        if v not in valid_statuses:
            raise ValueError(f"status must be one of {valid_statuses}, got {v}")
        return v


class OrbitData(BaseModel):
    """Orbital mechanics and position data."""
    
    altitude_m: float = Field(
        ...,
        ge=100000,
        le=2000000,
        description="Orbital altitude in meters (LEO range)"
    )
    ground_speed_ms: float = Field(
        ...,
        ge=7000,
        le=8000,
        description="Ground track velocity in m/s (LEO ~7.66 km/s)"
    )
    true_anomaly_deg: float = Field(
        ...,
        ge=0,
        le=360,
        description="True anomaly in degrees"
    )


class TelemetryPacket(BaseModel):
    """
    Primary versioned telemetry packet - single source of truth.
    
    This is the canonical format for all satellite telemetry in the HIL pipeline.
    Strict validation ensures data consistency across simulator, agents, and BDH.
    """
    
    version: str = Field(default="v1.0", description="Schema version")
    timestamp: datetime = Field(..., description="Packet timestamp (UTC)")
    satellite_id: str = Field(..., max_length=16, description="Unique satellite identifier")
    
    # Core subsystems
    attitude: AttitudeData = Field(..., description="Attitude and orientation")
    power: PowerData = Field(..., description="Power system status")
    thermal: ThermalData = Field(..., description="Thermal status")
    orbit: OrbitData = Field(..., description="Orbital parameters")
    
    # Metadata
    mission_mode: str = Field(..., description="Current mission mode")
    ground_contact: bool = Field(default=False, description="Ground station contact flag")
    
    @field_validator("mission_mode")
    @classmethod
    def validate_mission_mode(cls, v):
        """Ensure mission mode is valid."""
        valid_modes = {"idle", "nominal", "safe", "recovery"}
        if v not in valid_modes:
            raise ValueError(f"mission_mode must be one of {valid_modes}, got {v}")
        return v
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "version": "v1.0",
                "timestamp": "2026-01-13T19:47:21.190505",
                "satellite_id": "SAT001",
                "attitude": {
                    "quaternion": [0.707, 0.0, 0.0, 0.707],
                    "angular_velocity": [0.001, 0.002, 0.001],
                    "nadir_pointing_error_deg": 1.5
                },
                "power": {
                    "battery_voltage": 8.4,
                    "battery_soc": 0.87,
                    "solar_current": 0.8,
                    "load_current": 0.3
                },
                "thermal": {
                    "battery_temp": 15.2,
                    "eps_temp": 22.1,
                    "status": "nominal"
                },
                "orbit": {
                    "altitude_m": 520000,
                    "ground_speed_ms": 7660,
                    "true_anomaly_deg": 45.0
                },
                "mission_mode": "nominal",
                "ground_contact": False
            }
        }
    )
