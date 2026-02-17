"""
Test data factories for generating realistic test data for API testing.

Provides factory classes for creating:
- Telemetry data with various characteristics
- Anomaly records
- User accounts
- API keys
- Feedback submissions
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import random
import uuid
import string
from enum import Enum


class TelemetryFactory:
    """Factory for generating telemetry data."""

    @staticmethod
    def create_normal(
        timestamp: Optional[datetime] = None,
        voltage: float = 8.0,
        temperature: float = 25.0,
        gyro: float = 0.02,
        current: float = 1.1,
        wheel_speed: int = 5000,
        state_of_charge: float = 85.0,
    ) -> Dict[str, Any]:
        """Create normal (non-anomalous) telemetry data."""
        return {
            "timestamp": (timestamp or datetime.now()).isoformat(),
            "voltage": voltage,
            "temperature": temperature,
            "gyro": gyro,
            "current": current,
            "wheel_speed": wheel_speed,
            "state_of_charge": state_of_charge,
        }

    @staticmethod
    def create_anomalous(
        anomaly_type: str = "thermal_fault",
        severity: str = "high",
    ) -> Dict[str, Any]:
        """Create anomalous telemetry data with specified characteristics."""
        if anomaly_type == "thermal_fault":
            return {
                "timestamp": datetime.now().isoformat(),
                "voltage": 8.0,
                "temperature": 95.0,  # High temperature
                "gyro": 0.02,
                "current": 1.1,
                "wheel_speed": 5000,
                "state_of_charge": 85.0,
            }
        elif anomaly_type == "power_loss":
            return {
                "timestamp": datetime.now().isoformat(),
                "voltage": 2.0,  # Very low voltage
                "temperature": 25.0,
                "gyro": 0.02,
                "current": 0.1,  # Very low current
                "wheel_speed": 1000,  # Low wheel speed
                "state_of_charge": 5.0,  # Very low battery
            }
        elif anomaly_type == "gyro_fault":
            return {
                "timestamp": datetime.now().isoformat(),
                "voltage": 8.0,
                "temperature": 25.0,
                "gyro": 2.5,  # High gyro reading
                "current": 1.1,
                "wheel_speed": 10000,  # High wheel speed
                "state_of_charge": 85.0,
            }
        else:  # Current surge
            return {
                "timestamp": datetime.now().isoformat(),
                "voltage": 8.0,
                "temperature": 30.0,
                "gyro": 0.02,
                "current": 5.0,  # High current
                "wheel_speed": 5000,
                "state_of_charge": 85.0,
            }

    @staticmethod
    def create_batch(
        count: int = 10,
        anomaly_rate: float = 0.1,
    ) -> List[Dict[str, Any]]:
        """Create a batch of telemetry data with specified anomaly rate."""
        telemetry_list = []
        for i in range(count):
            if random.random() < anomaly_rate:
                telemetry_list.append(TelemetryFactory.create_anomalous())
            else:
                # Vary the normal data slightly
                telemetry_list.append(
                    TelemetryFactory.create_normal(
                        voltage=8.0 + random.uniform(-0.2, 0.2),
                        temperature=25.0 + random.uniform(-2, 2),
                        gyro=0.02 + random.uniform(-0.01, 0.01),
                        current=1.1 + random.uniform(-0.1, 0.1),
                        wheel_speed=5000 + random.randint(-200, 200),
                        state_of_charge=85.0 + random.uniform(-5, 5),
                    )
                )
        return telemetry_list

    @staticmethod
    def create_time_series(
        count: int = 100,
        start_time: Optional[datetime] = None,
        interval_seconds: int = 60,
    ) -> List[Dict[str, Any]]:
        """Create a time series of telemetry data."""
        if start_time is None:
            start_time = datetime.now()

        telemetry_list = []
        for i in range(count):
            ts = start_time + timedelta(seconds=i * interval_seconds)
            telemetry_list.append(TelemetryFactory.create_normal(timestamp=ts))
        return telemetry_list


class AnomalyFactory:
    """Factory for generating anomaly records."""

    @staticmethod
    def create(
        is_anomaly: bool = True,
        anomaly_type: Optional[str] = None,
        confidence: float = 0.92,
        severity: str = "HIGH",
    ) -> Dict[str, Any]:
        """Create an anomaly record."""
        return {
            "anomaly_id": f"anomaly-{uuid.uuid4().hex[:12]}",
            "telemetry_id": f"telemetry-{uuid.uuid4().hex[:12]}",
            "is_anomaly": is_anomaly,
            "anomaly_type": anomaly_type or ("thermal_fault" if is_anomaly else None),
            "confidence": confidence,
            "severity": severity,
            "timestamp": datetime.now().isoformat(),
            "detected_at": datetime.now().isoformat(),
        }

    @staticmethod
    def create_batch(count: int = 10) -> List[Dict[str, Any]]:
        """Create a batch of anomaly records."""
        return [AnomalyFactory.create() for _ in range(count)]


class UserFactory:
    """Factory for generating user data."""

    @staticmethod
    def create(
        username: Optional[str] = None,
        email: Optional[str] = None,
        is_admin: bool = False,
        permissions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create a user record."""
        if username is None:
            username = f"user_{uuid.uuid4().hex[:8]}"
        if email is None:
            email = f"{username}@example.com"
        if permissions is None:
            permissions = ["read", "write"] if not is_admin else ["read", "write", "admin"]

        return {
            "user_id": f"user-{uuid.uuid4().hex[:12]}",
            "username": username,
            "email": email,
            "display_name": username.replace("_", " ").title(),
            "created_at": datetime.now().isoformat(),
            "is_active": True,
            "is_admin": is_admin,
            "permissions": permissions,
        }

    @staticmethod
    def create_admin() -> Dict[str, Any]:
        """Create an admin user."""
        return UserFactory.create(
            username="admin",
            email="admin@example.com",
            is_admin=True,
            permissions=["read", "write", "admin", "execute"],
        )

    @staticmethod
    def create_batch(count: int = 10, admin_count: int = 1) -> List[Dict[str, Any]]:
        """Create a batch of users."""
        users = []
        for i in range(admin_count):
            users.append(UserFactory.create_admin())
        for i in range(count - admin_count):
            users.append(UserFactory.create())
        return users


class APIKeyFactory:
    """Factory for generating API key data."""

    @staticmethod
    def generate_key() -> str:
        """Generate a valid API key."""
        prefix = "ag-"
        key_part = "".join(random.choices(string.ascii_letters + string.digits, k=32))
        return prefix + key_part

    @staticmethod
    def create(
        name: Optional[str] = None,
        description: str = "Test API Key",
        permissions: Optional[List[str]] = None,
        expires_in_days: int = 90,
    ) -> Dict[str, Any]:
        """Create an API key record."""
        if name is None:
            name = f"key_{uuid.uuid4().hex[:8]}"
        if permissions is None:
            permissions = ["read", "write"]

        now = datetime.now()
        expires_at = now + timedelta(days=expires_in_days)

        return {
            "key_id": f"key-{uuid.uuid4().hex[:12]}",
            "name": name,
            "description": description,
            "prefix": "ag-" + APIKeyFactory.generate_key()[:12],
            "permissions": permissions,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "last_used": None,
            "is_active": True,
        }

    @staticmethod
    def create_batch(count: int = 10) -> List[Dict[str, Any]]:
        """Create a batch of API keys."""
        return [APIKeyFactory.create() for _ in range(count)]


class FeedbackFactory:
    """Factory for generating feedback submissions."""

    class FeedbackLabel(str, Enum):
        """Valid feedback labels."""
        TRUE_POSITIVE = "true_positive"
        FALSE_POSITIVE = "false_positive"
        TRUE_NEGATIVE = "true_negative"
        FALSE_NEGATIVE = "false_negative"
        UNCERTAIN = "uncertain"

    @staticmethod
    def create(
        anomaly_id: Optional[str] = None,
        label: str = "true_positive",
        confidence: float = 0.95,
        notes: str = "Test feedback",
    ) -> Dict[str, Any]:
        """Create a feedback submission."""
        if anomaly_id is None:
            anomaly_id = f"anomaly-{uuid.uuid4().hex[:12]}"

        return {
            "feedback_id": f"feedback-{uuid.uuid4().hex[:12]}",
            "anomaly_id": anomaly_id,
            "label": label,
            "confidence": confidence,
            "notes": notes,
            "submitted_at": datetime.now().isoformat(),
            "useful": True,
        }

    @staticmethod
    def create_batch(count: int = 10) -> List[Dict[str, Any]]:
        """Create a batch of feedback submissions."""
        return [FeedbackFactory.create() for _ in range(count)]


class ContactFactory:
    """Factory for generating contact data."""

    @staticmethod
    def create(
        email: Optional[str] = None,
        name: Optional[str] = None,
        subject: str = "Test Contact",
        message: str = "This is a test message",
    ) -> Dict[str, Any]:
        """Create a contact submission."""
        if email is None:
            email = f"contact_{uuid.uuid4().hex[:8]}@example.com"
        if name is None:
            name = email.split("@")[0].replace("_", " ").title()

        return {
            "contact_id": f"contact-{uuid.uuid4().hex[:12]}",
            "email": email,
            "name": name,
            "subject": subject,
            "message": message,
            "submitted_at": datetime.now().isoformat(),
            "status": "new",
        }

    @staticmethod
    def create_batch(count: int = 10) -> List[Dict[str, Any]]:
        """Create a batch of contact submissions."""
        return [ContactFactory.create() for _ in range(count)]


class RequestFactory:
    """Factory for generating HTTP requests."""

    @staticmethod
    def create_headers(
        api_key: Optional[str] = None,
        content_type: str = "application/json",
    ) -> Dict[str, str]:
        """Create request headers."""
        headers = {"Content-Type": content_type}
        if api_key:
            headers["X-API-Key"] = api_key
        return headers

    @staticmethod
    def create_auth_header(api_key: str) -> Dict[str, str]:
        """Create authorization header."""
        return {"X-API-Key": api_key}


class PerformanceDataFactory:
    """Factory for generating performance test data."""

    @staticmethod
    def create_load_profile(
        duration_seconds: int = 60,
        ramp_up_seconds: int = 10,
        target_rps: float = 100.0,
    ) -> Dict[str, Any]:
        """Create a load test profile."""
        return {
            "duration_seconds": duration_seconds,
            "ramp_up_seconds": ramp_up_seconds,
            "target_rps": target_rps,
            "max_connections": int(target_rps / 10),
            "timeout_seconds": 30,
        }

    @staticmethod
    def create_metrics(
        response_time_ms: float,
        status_code: int,
        timestamp: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Create performance metrics."""
        return {
            "response_time_ms": response_time_ms,
            "status_code": status_code,
            "timestamp": (timestamp or datetime.now()).isoformat(),
            "endpoint": "/api/v1/telemetry",
            "method": "POST",
        }

    @staticmethod
    def create_metrics_batch(
        count: int = 100,
        avg_response_time_ms: float = 50.0,
        std_dev_ms: float = 10.0,
    ) -> List[Dict[str, Any]]:
        """Create a batch of performance metrics."""
        metrics = []
        for _ in range(count):
            response_time = random.gauss(avg_response_time_ms, std_dev_ms)
            metrics.append(
                PerformanceDataFactory.create_metrics(
                    response_time_ms=max(1, response_time),
                    status_code=200,
                )
            )
        return metrics
