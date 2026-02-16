"""
Test Data Generators

Generates realistic test data for AstraGuard testing scenarios.
"""

import random
import string
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


class TelemetryGenerator:
    """
    Generate realistic telemetry data for testing.
    
    Example:
        >>> gen = TelemetryGenerator()
        >>> data = gen.generate()
        >>> assert "voltage" in data
        >>> assert 7.0 <= data["voltage"] <= 9.0
    """
    
    def __init__(
        self,
        voltage_range: tuple = (7.0, 9.0),
        temp_range: tuple = (20.0, 50.0),
        gyro_range: tuple = (-0.2, 0.2),
        current_range: tuple = (0.5, 2.0),
        wheel_speed_range: tuple = (0.0, 10.0)
    ):
        """
        Initialize telemetry generator with custom ranges.
        
        Args:
            voltage_range: Min/max voltage values
            temp_range: Min/max temperature values
            gyro_range: Min/max gyroscope values
            current_range: Min/max current values
            wheel_speed_range: Min/max wheel speed values
        """
        self.voltage_range = voltage_range
        self.temp_range = temp_range
        self.gyro_range = gyro_range
        self.current_range = current_range
        self.wheel_speed_range = wheel_speed_range
    
    def generate(
        self,
        anomalous: bool = False,
        timestamp: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Generate single telemetry reading.
        
        Args:
            anomalous: Generate anomalous data
            timestamp: Optional timestamp
            
        Returns:
            Telemetry data dict
        """
        if anomalous:
            # Generate anomalous values outside normal ranges
            voltage = random.uniform(3.0, 6.0) or random.uniform(10.0, 12.0)
            temperature = random.uniform(60.0, 80.0)
            gyro = random.uniform(0.5, 1.0)
            current = random.uniform(3.0, 5.0)
            wheel_speed = random.uniform(15.0, 20.0)
        else:
            voltage = random.uniform(*self.voltage_range)
            temperature = random.uniform(*self.temp_range)
            gyro = random.uniform(*self.gyro_range)
            current = random.uniform(*self.current_range)
            wheel_speed = random.uniform(*self.wheel_speed_range)
        
        return {
            "voltage": round(voltage, 2),
            "temperature": round(temperature, 2),
            "gyro": round(gyro, 3),
            "current": round(current, 2),
            "wheel_speed": round(wheel_speed, 2),
            "timestamp": (timestamp or datetime.now()).isoformat()
        }
    
    def generate_batch(
        self,
        count: int = 10,
        anomalous_ratio: float = 0.0,
        start_time: Optional[datetime] = None,
        interval_seconds: float = 1.0
    ) -> List[Dict[str, Any]]:
        """
        Generate batch of telemetry readings.
        
        Args:
            count: Number of readings to generate
            anomalous_ratio: Fraction of anomalous readings (0.0 to 1.0)
            start_time: Starting timestamp
            interval_seconds: Time between readings
            
        Returns:
            List of telemetry dicts
        """
        start_time = start_time or datetime.now()
        batch = []
        
        for i in range(count):
            is_anomalous = random.random() < anomalous_ratio
            timestamp = start_time + timedelta(seconds=i * interval_seconds)
            batch.append(self.generate(anomalous=is_anomalous, timestamp=timestamp))
        
        return batch
    
    def generate_time_series(
        self,
        duration_seconds: int = 60,
        sample_rate: float = 1.0,
        drift: bool = False,
        noise: float = 0.1
    ) -> List[Dict[str, Any]]:
        """
        Generate time series telemetry with optional drift and noise.
        
        Args:
            duration_seconds: Total duration
            sample_rate: Samples per second
            drift: Include gradual drift in values
            noise: Amount of random noise (0.0 to 1.0)
            
        Returns:
            List of telemetry readings
        """
        num_samples = int(duration_seconds * sample_rate)
        base_values = self.generate()
        time_series = []
        
        for i in range(num_samples):
            timestamp = datetime.now() + timedelta(seconds=i / sample_rate)
            
            # Apply drift if enabled
            drift_factor = (i / num_samples) if drift else 0
            
            # Add noise
            noise_voltage = random.uniform(-noise, noise)
            noise_temp = random.uniform(-noise * 5, noise * 5)
            
            data = {
                "voltage": round(base_values["voltage"] + drift_factor + noise_voltage, 2),
                "temperature": round(base_values["temperature"] + drift_factor * 10 + noise_temp, 2),
                "gyro": round(base_values["gyro"] + random.uniform(-noise/10, noise/10), 3),
                "current": round(base_values["current"] + random.uniform(-noise, noise), 2),
                "wheel_speed": round(base_values["wheel_speed"] + random.uniform(-noise, noise), 2),
                "timestamp": timestamp.isoformat()
            }
            time_series.append(data)
        
        return time_series


class UserGenerator:
    """
    Generate realistic user data for testing.
    
    Example:
        >>> gen = UserGenerator()
        >>> user = gen.generate()
        >>> assert "@" in user["email"]
    """
    
    def __init__(self):
        """Initialize user generator."""
        self.roles = ["ADMIN", "OPERATOR", "VIEWER", "GUEST"]
        self.domains = ["test.com", "example.org", "demo.net"]
    
    def generate(
        self,
        username: Optional[str] = None,
        role: Optional[str] = None,
        active: bool = True
    ) -> Dict[str, Any]:
        """
        Generate user data.
        
        Args:
            username: Optional username
            role: Optional role
            active: User active status
            
        Returns:
            User data dict
        """
        if not username:
            username = f"user_{random.randint(1000, 9999)}"
        
        if not role:
            role = random.choice(self.roles)
        
        domain = random.choice(self.domains)
        
        return {
            "id": f"user-{random.randint(10000, 99999)}",
            "username": username,
            "email": f"{username}@{domain}",
            "role": role,
            "is_active": active,
            "created_at": datetime.now().isoformat(),
            "last_login": (datetime.now() - timedelta(hours=random.randint(1, 24))).isoformat()
        }
    
    def generate_batch(self, count: int = 10) -> List[Dict[str, Any]]:
        """Generate batch of users."""
        return [self.generate() for _ in range(count)]


class APIKeyGenerator:
    """
    Generate API keys for testing.
    
    Example:
        >>> gen = APIKeyGenerator()
        >>> key = gen.generate()
        >>> assert len(key["key"]) == 32
    """
    
    def __init__(self):
        """Initialize API key generator."""
        self.permission_sets = [
            {"read"},
            {"read", "write"},
            {"read", "write", "admin"},
            {"read", "delete"},
        ]
    
    def generate(
        self,
        name: Optional[str] = None,
        permissions: Optional[set] = None,
        expires_in_days: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate API key data.
        
        Args:
            name: Optional key name
            permissions: Optional permission set
            expires_in_days: Optional expiration days
            
        Returns:
            API key data dict
        """
        if not name:
            name = f"key_{random.randint(1000, 9999)}"
        
        if not permissions:
            permissions = random.choice(self.permission_sets)
        
        key = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        
        created_at = datetime.now()
        expires_at = None
        if expires_in_days:
            expires_at = created_at + timedelta(days=expires_in_days)
        
        return {
            "key": key,
            "name": name,
            "permissions": list(permissions),
            "created_at": created_at.isoformat(),
            "expires_at": expires_at.isoformat() if expires_at else None,
            "usage_count": random.randint(0, 1000),
            "last_used": (created_at - timedelta(hours=random.randint(1, 48))).isoformat()
        }
    
    def generate_batch(self, count: int = 5) -> List[Dict[str, Any]]:
        """Generate batch of API keys."""
        return [self.generate() for _ in range(count)]


class AnomalyGenerator:
    """
    Generate anomalous telemetry patterns for testing.
    
    Example:
        >>> gen = AnomalyGenerator()
        >>> anomalies = gen.generate_spike_pattern()
        >>> # Returns telemetry with sudden spike
    """
    
    def __init__(self):
        """Initialize anomaly generator."""
        self.telemetry_gen = TelemetryGenerator()
    
    def generate_spike_pattern(
        self,
        duration: int = 20,
        spike_at: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Generate data with sudden spike anomaly.
        
        Args:
            duration: Total samples
            spike_at: Sample index for spike
            
        Returns:
            List of telemetry with spike
        """
        data = []
        for i in range(duration):
            if i == spike_at:
                anomalous = self.telemetry_gen.generate(anomalous=True)
                data.append(anomalous)
            else:
                normal = self.telemetry_gen.generate(anomalous=False)
                data.append(normal)
        return data
    
    def generate_drift_pattern(
        self,
        duration: int = 30,
        drift_start: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Generate data with gradual drift anomaly.
        
        Args:
            duration: Total samples
            drift_start: Sample where drift begins
            
        Returns:
            List of telemetry with drift
        """
        base = self.telemetry_gen.generate()
        data = []
        
        for i in range(duration):
            if i < drift_start:
                data.append(self.telemetry_gen.generate())
            else:
                drift_amount = (i - drift_start) * 0.1
                drifted = base.copy()
                drifted["voltage"] += drift_amount
                drifted["temperature"] += drift_amount * 2
                data.append(drifted)
        
        return data
    
    def generate_oscillation_pattern(
        self,
        duration: int = 30,
        frequency: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Generate oscillating anomaly pattern.
        
        Args:
            duration: Total samples
            frequency: Oscillation frequency
            
        Returns:
            List of telemetry with oscillation
        """
        import math
        base = self.telemetry_gen.generate()
        data = []
        
        for i in range(duration):
            oscillation = math.sin(i * frequency) * 2
            item = base.copy()
            item["voltage"] = base["voltage"] + oscillation
            item["timestamp"] = (datetime.now() + timedelta(seconds=i)).isoformat()
            data.append(item)
        
        return data


# Convenience functions

def quick_telemetry(count: int = 1, anomalous: bool = False) -> List[Dict[str, Any]]:
    """
    Quick function to generate telemetry data.
    
    Args:
        count: Number of readings
        anomalous: Generate anomalous data
        
    Returns:
        List of telemetry dicts (single item if count=1)
        
    Example:
        >>> data = quick_telemetry(5)
        >>> assert len(data) == 5
    """
    gen = TelemetryGenerator()
    if count == 1:
        return gen.generate(anomalous=anomalous)
    return [gen.generate(anomalous=anomalous) for _ in range(count)]


def quick_user(role: str = "OPERATOR") -> Dict[str, Any]:
    """
    Quick function to generate a user.
    
    Args:
        role: User role
        
    Returns:
        User data dict
        
    Example:
        >>> user = quick_user("ADMIN")
        >>> assert user["role"] == "ADMIN"
    """
    gen = UserGenerator()
    return gen.generate(role=role)


def quick_api_key(permissions: Optional[set] = None) -> Dict[str, Any]:
    """
    Quick function to generate an API key.
    
    Args:
        permissions: Permission set
        
    Returns:
        API key data dict
        
    Example:
        >>> key = quick_api_key({"read", "write"})
        >>> assert "write" in key["permissions"]
    """
    gen = APIKeyGenerator()
    return gen.generate(permissions=permissions)
