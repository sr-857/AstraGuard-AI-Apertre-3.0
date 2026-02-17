"""
Test Data Seeding Utilities

Provides comprehensive test data seeding capabilities for databases, APIs, and test scenarios.
Supports SQLite, in-memory stores, and various AstraGuard-specific data structures.

Features:
- Database seeding (users, telemetry, anomalies, submissions)
- Scenario-based seeding (normal ops, stress test, anomaly scenarios)
- Batch operations for performance
- Cleanup utilities
- Flexible configuration
"""

import sqlite3
import logging
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ScenarioType(Enum):
    """Predefined seeding scenarios."""
    NORMAL_OPS = "normal_ops"
    ANOMALY_DETECTION = "anomaly_detection"
    STRESS_TEST = "stress_test"
    HIGH_LOAD = "high_load"
    FAILURE_RECOVERY = "failure_recovery"
    EMPTY = "empty"


@dataclass
class SeedConfig:
    """Configuration for data seeding."""
    telemetry_count: int = 100
    user_count: int = 10
    api_key_count: int = 5
    anomaly_ratio: float = 0.1
    time_range_hours: int = 24
    batch_size: int = 50
    seed: Optional[int] = None
    
    def __post_init__(self):
        """Validate configuration."""
        if self.anomaly_ratio < 0 or self.anomaly_ratio > 1:
            raise ValueError("anomaly_ratio must be between 0 and 1")
        if self.seed is not None:
            random.seed(self.seed)


class DatabaseSeeder:
    """
    Database seeding utility for test data.
    
    Supports SQLite databases and provides methods to seed various entities.
    
    Example:
        >>> seeder = DatabaseSeeder("test.db")
        >>> seeder.seed_users(count=10)
        >>> seeder.seed_telemetry(count=100)
    """
    
    def __init__(self, db_path: Union[str, Path]):
        """
        Initialize database seeder.
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = Path(db_path)
        self.conn: Optional[sqlite3.Connection] = None
        
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        
    def connect(self):
        """Open database connection."""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            logger.debug(f"Connected to database: {self.db_path}")
            
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.commit()
            self.conn.close()
            self.conn = None
            logger.debug(f"Closed database connection: {self.db_path}")
    
    def seed_users(
        self,
        count: int = 10,
        roles: Optional[List[str]] = None,
        table_name: str = "users"
    ) -> List[int]:
        """
        Seed user records.
        
        Args:
            count: Number of users to create
            roles: List of roles to assign (random if None)
            table_name: Target table name
            
        Returns:
            List of inserted user IDs
        """
        if not self.conn:
            self.connect()
            
        roles = roles or ["admin", "operator", "analyst", "viewer"]
        user_ids = []
        
        cursor = self.conn.cursor()
        
        for i in range(count):
            username = f"test_user_{i:04d}"
            email = f"{username}@test.com"
            role = random.choice(roles)
            created_at = datetime.now() - timedelta(days=random.randint(1, 365))
            
            try:
                cursor.execute(f"""
                    INSERT INTO {table_name} 
                    (username, email, role, created_at, is_active)
                    VALUES (?, ?, ?, ?, ?)
                """, (username, email, role, created_at.isoformat(), True))
                
                user_ids.append(cursor.lastrowid)
                
            except sqlite3.Error as e:
                logger.warning(f"Failed to insert user {username}: {e}")
                
        self.conn.commit()
        logger.info(f"Seeded {len(user_ids)} users")
        return user_ids
    
    def seed_telemetry(
        self,
        count: int = 100,
        anomalous_ratio: float = 0.1,
        time_range_hours: int = 24,
        table_name: str = "telemetry"
    ) -> List[int]:
        """
        Seed telemetry records.
        
        Args:
            count: Number of telemetry records
            anomalous_ratio: Ratio of anomalous readings
            time_range_hours: Time range for timestamps
            table_name: Target table name
            
        Returns:
            List of inserted telemetry IDs
        """
        if not self.conn:
            self.connect()
            
        telemetry_ids = []
        cursor = self.conn.cursor()
        
        start_time = datetime.now() - timedelta(hours=time_range_hours)
        interval = timedelta(hours=time_range_hours) / count
        
        for i in range(count):
            timestamp = start_time + (interval * i)
            is_anomalous = random.random() < anomalous_ratio
            
            # Generate telemetry values
            if is_anomalous:
                voltage = random.uniform(3.0, 6.0) if random.random() < 0.5 else random.uniform(10.0, 12.0)
                temperature = random.uniform(60.0, 85.0)
                current = random.uniform(3.0, 5.0)
            else:
                voltage = random.uniform(7.0, 9.0)
                temperature = random.uniform(20.0, 50.0)
                current = random.uniform(0.5, 2.0)
            
            gyro = random.uniform(-0.2, 0.2)
            wheel_speed = random.uniform(0.0, 10.0)
            
            try:
                cursor.execute(f"""
                    INSERT INTO {table_name}
                    (voltage, temperature, gyro, current, wheel_speed, timestamp, is_anomalous)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    round(voltage, 2),
                    round(temperature, 2),
                    round(gyro, 3),
                    round(current, 2),
                    round(wheel_speed, 2),
                    timestamp.isoformat(),
                    is_anomalous
                ))
                
                telemetry_ids.append(cursor.lastrowid)
                
            except sqlite3.Error as e:
                logger.warning(f"Failed to insert telemetry record: {e}")
                
        self.conn.commit()
        logger.info(f"Seeded {len(telemetry_ids)} telemetry records")
        return telemetry_ids
    
    def seed_contact_submissions(
        self,
        count: int = 20,
        status_distribution: Optional[Dict[str, float]] = None,
        table_name: str = "contact_submissions"
    ) -> List[int]:
        """
        Seed contact form submissions.
        
        Args:
            count: Number of submissions
            status_distribution: Distribution of statuses (e.g., {"pending": 0.7, "resolved": 0.3})
            table_name: Target table name
            
        Returns:
            List of inserted submission IDs
        """
        if not self.conn:
            self.connect()
            
        status_distribution = status_distribution or {
            "pending": 0.5,
            "in_progress": 0.3,
            "resolved": 0.15,
            "closed": 0.05
        }
        
        statuses = []
        for status, prob in status_distribution.items():
            statuses.extend([status] * int(count * prob))
        
        # Fill remaining with "pending"
        while len(statuses) < count:
            statuses.append("pending")
        
        random.shuffle(statuses)
        
        submission_ids = []
        cursor = self.conn.cursor()
        
        subjects = [
            "Technical Support Request",
            "Feature Request",
            "Bug Report",
            "General Inquiry",
            "Account Issue",
            "Billing Question",
            "API Access Request"
        ]
        
        for i in range(count):
            name = f"User {i + 1}"
            email = f"user{i+1}@example.com"
            phone = f"+1555{random.randint(1000000, 9999999)}"
            subject = random.choice(subjects)
            message = f"This is a test message for submission {i+1}. " * random.randint(2, 5)
            ip_address = f"192.168.{random.randint(1, 255)}.{random.randint(1, 255)}"
            user_agent = "Mozilla/5.0 (Test Browser)"
            submitted_at = datetime.now() - timedelta(hours=random.randint(1, 720))
            status = statuses[i] if i < len(statuses) else "pending"
            
            try:
                cursor.execute(f"""
                    INSERT INTO {table_name}
                    (name, email, phone, subject, message, ip_address, user_agent, submitted_at, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (name, email, phone, subject, message, ip_address, user_agent,
                      submitted_at.isoformat(), status))
                
                submission_ids.append(cursor.lastrowid)
                
            except sqlite3.Error as e:
                logger.warning(f"Failed to insert submission: {e}")
                
        self.conn.commit()
        logger.info(f"Seeded {len(submission_ids)} contact submissions")
        return submission_ids
    
    def seed_api_keys(
        self,
        count: int = 5,
        table_name: str = "api_keys"
    ) -> List[str]:
        """
        Seed API keys.
        
        Args:
            count: Number of API keys
            table_name: Target table name
            
        Returns:
            List of generated API keys
        """
        if not self.conn:
            self.connect()
            
        import string
        
        keys = []
        cursor = self.conn.cursor()
        
        permission_sets = [
            "read",
            "read,write",
            "read,write,admin",
            "read,delete"
        ]
        
        for i in range(count):
            key = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
            name = f"test_key_{i:04d}"
            permissions = random.choice(permission_sets)
            created_at = datetime.now() - timedelta(days=random.randint(1, 180))
            expires_at = created_at + timedelta(days=random.randint(30, 365))
            
            try:
                cursor.execute(f"""
                    INSERT INTO {table_name}
                    (key, name, permissions, created_at, expires_at, usage_count)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (key, name, permissions, created_at.isoformat(),
                      expires_at.isoformat(), random.randint(0, 1000)))
                
                keys.append(key)
                
            except sqlite3.Error as e:
                logger.warning(f"Failed to insert API key: {e}")
                
        self.conn.commit()
        logger.info(f"Seeded {count} API keys")
        return keys
    
    def clear_table(self, table_name: str):
        """
        Clear all records from a table.
        
        Args:
            table_name: Table to clear
        """
        if not self.conn:
            self.connect()
            
        try:
            self.conn.execute(f"DELETE FROM {table_name}")
            self.conn.commit()
            logger.info(f"Cleared table: {table_name}")
        except sqlite3.Error as e:
            logger.error(f"Failed to clear table {table_name}: {e}")
            raise


class MemoryStoreSeeder:
    """
    Seeder for in-memory data structures (lists, dicts, etc.).
    
    Example:
        >>> seeder = MemoryStoreSeeder()
        >>> data = []
        >>> seeder.seed_telemetry_list(data, count=50)
        >>> len(data)
        50
    """
    
    @staticmethod
    def seed_telemetry_list(
        target_list: List,
        count: int = 100,
        anomalous_ratio: float = 0.1,
        time_range_hours: int = 24
    ):
        """
        Seed telemetry data into a list.
        
        Args:
            target_list: List to populate
            count: Number of records
            anomalous_ratio: Ratio of anomalous records
            time_range_hours: Time range for timestamps
        """
        start_time = datetime.now() - timedelta(hours=time_range_hours)
        interval = timedelta(hours=time_range_hours) / count
        
        for i in range(count):
            timestamp = start_time + (interval * i)
            is_anomalous = random.random() < anomalous_ratio
            
            if is_anomalous:
                voltage = random.uniform(3.0, 6.0) if random.random() < 0.5 else random.uniform(10.0, 12.0)
                temperature = random.uniform(60.0, 85.0)
            else:
                voltage = random.uniform(7.0, 9.0)
                temperature = random.uniform(20.0, 50.0)
            
            telemetry = {
                "voltage": round(voltage, 2),
                "temperature": round(temperature, 2),
                "gyro": round(random.uniform(-0.2, 0.2), 3),
                "current": round(random.uniform(0.5, 2.0), 2),
                "wheel_speed": round(random.uniform(0.0, 10.0), 2),
                "timestamp": timestamp.isoformat(),
                "is_anomalous": is_anomalous
            }
            target_list.append(telemetry)
        
        logger.info(f"Seeded {count} telemetry records into list")
    
    @staticmethod
    def seed_user_dict(
        target_dict: Dict,
        count: int = 10,
        roles: Optional[List[str]] = None
    ):
        """
        Seed user data into a dictionary (keyed by username).
        
        Args:
            target_dict: Dictionary to populate
            count: Number of users
            roles: List of roles
        """
        roles = roles or ["admin", "operator", "analyst", "viewer"]
        
        for i in range(count):
            username = f"test_user_{i:04d}"
            user = {
                "id": f"user-{random.randint(10000, 99999)}",
                "username": username,
                "email": f"{username}@test.com",
                "role": random.choice(roles),
                "is_active": True,
                "created_at": (datetime.now() - timedelta(days=random.randint(1, 365))).isoformat()
            }
            target_dict[username] = user
        
        logger.info(f"Seeded {count} users into dictionary")


class ScenarioSeeder:
    """
    Seed data for specific test scenarios.
    
    Example:
        >>> seeder = ScenarioSeeder()
        >>> db_seeder = DatabaseSeeder("test.db")
        >>> seeder.seed_scenario(ScenarioType.STRESS_TEST, db_seeder)
    """
    
    @staticmethod
    def seed_scenario(
        scenario: ScenarioType,
        db_seeder: DatabaseSeeder,
        config: Optional[SeedConfig] = None
    ):
        """
        Seed data for a specific scenario.
        
        Args:
            scenario: Scenario type to seed
            db_seeder: Database seeder instance
            config: Optional seed configuration
        """
        config = config or SeedConfig()
        
        logger.info(f"Seeding scenario: {scenario.value}")
        
        if scenario == ScenarioType.NORMAL_OPS:
            db_seeder.seed_users(count=5)
            db_seeder.seed_telemetry(count=100, anomalous_ratio=0.05, time_range_hours=24)
            db_seeder.seed_api_keys(count=3)
            
        elif scenario == ScenarioType.ANOMALY_DETECTION:
            db_seeder.seed_users(count=3)
            db_seeder.seed_telemetry(count=200, anomalous_ratio=0.3, time_range_hours=12)
            
        elif scenario == ScenarioType.STRESS_TEST:
            db_seeder.seed_users(count=50)
            db_seeder.seed_telemetry(count=10000, anomalous_ratio=0.1, time_range_hours=168)
            db_seeder.seed_api_keys(count=20)
            db_seeder.seed_contact_submissions(count=500)
            
        elif scenario == ScenarioType.HIGH_LOAD:
            db_seeder.seed_telemetry(count=5000, anomalous_ratio=0.05, time_range_hours=48)
            db_seeder.seed_contact_submissions(count=200)
            
        elif scenario == ScenarioType.FAILURE_RECOVERY:
            db_seeder.seed_users(count=10)
            db_seeder.seed_telemetry(count=500, anomalous_ratio=0.5, time_range_hours=12)
            
        elif scenario == ScenarioType.EMPTY:
            # Clear all tables
            for table in ["users", "telemetry", "api_keys", "contact_submissions"]:
                try:
                    db_seeder.clear_table(table)
                except Exception as e:
                    logger.debug(f"Table {table} may not exist: {e}")
        
        logger.info(f"Scenario seeding complete: {scenario.value}")


# Convenience functions

def quick_seed_db(
    db_path: Union[str, Path],
    scenario: ScenarioType = ScenarioType.NORMAL_OPS,
    config: Optional[SeedConfig] = None
):
    """
    Quick function to seed a database with a scenario.
    
    Args:
        db_path: Path to database
        scenario: Scenario to seed
        config: Optional configuration
        
    Example:
        >>> quick_seed_db("test.db", ScenarioType.NORMAL_OPS)
    """
    with DatabaseSeeder(db_path) as seeder:
        ScenarioSeeder.seed_scenario(scenario, seeder, config)


def quick_seed_telemetry(count: int = 100, anomalous: bool = False) -> List[Dict[str, Any]]:
    """
    Quick function to generate telemetry data.
    
    Args:
        count: Number of records
        anomalous: Whether to include anomalies
        
    Returns:
        List of telemetry dictionaries
        
    Example:
        >>> data = quick_seed_telemetry(50, anomalous=True)
        >>> len(data)
        50
    """
    telemetry = []
    anomalous_ratio = 0.3 if anomalous else 0.0
    MemoryStoreSeeder.seed_telemetry_list(telemetry, count=count, anomalous_ratio=anomalous_ratio)
    return telemetry


def quick_seed_users(count: int = 10) -> Dict[str, Dict[str, Any]]:
    """
    Quick function to generate user data.
    
    Args:
        count: Number of users
        
    Returns:
        Dictionary of users keyed by username
        
    Example:
        >>> users = quick_seed_users(5)
        >>> len(users)
        5
    """
    users = {}
    MemoryStoreSeeder.seed_user_dict(users, count=count)
    return users
