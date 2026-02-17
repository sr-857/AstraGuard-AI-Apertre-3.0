"""
Tests for Test Data Seeding Utilities

Comprehensive test suite for the seeding utilities module.
"""

import pytest
import sqlite3
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from src.backend.utils.seeders import (
    DatabaseSeeder,
    MemoryStoreSeeder,
    ScenarioSeeder,
    SeedConfig,
    ScenarioType,
    quick_seed_db,
    quick_seed_telemetry,
    quick_seed_users,
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    shutil.rmtree(tmp)


@pytest.fixture
def test_db(temp_dir):
    """Create a test database with schema."""
    db_path = temp_dir / "test.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create test tables
    cursor.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1
        )
    """)
    
    cursor.execute("""
        CREATE TABLE telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            voltage REAL NOT NULL,
            temperature REAL NOT NULL,
            gyro REAL NOT NULL,
            current REAL NOT NULL,
            wheel_speed REAL NOT NULL,
            timestamp TEXT NOT NULL,
            is_anomalous BOOLEAN DEFAULT 0
        )
    """)
    
    cursor.execute("""
        CREATE TABLE contact_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            ip_address TEXT,
            user_agent TEXT,
            submitted_at TEXT NOT NULL,
            status TEXT DEFAULT 'pending'
        )
    """)
    
    cursor.execute("""
        CREATE TABLE api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            permissions TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT,
            usage_count INTEGER DEFAULT 0
        )
    """)
    
    conn.commit()
    conn.close()
    
    yield db_path


class TestSeedConfig:
    """Test SeedConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = SeedConfig()
        assert config.telemetry_count == 100
        assert config.user_count == 10
        assert config.anomaly_ratio == 0.1
        assert config.time_range_hours == 24
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = SeedConfig(
            telemetry_count=200,
            user_count=20,
            anomaly_ratio=0.3,
            time_range_hours=48
        )
        assert config.telemetry_count == 200
        assert config.user_count == 20
        assert config.anomaly_ratio == 0.3
        assert config.time_range_hours == 48
    
    def test_invalid_anomaly_ratio(self):
        """Test validation of anomaly ratio."""
        with pytest.raises(ValueError):
            SeedConfig(anomaly_ratio=1.5)
        
        with pytest.raises(ValueError):
            SeedConfig(anomaly_ratio=-0.1)


class TestDatabaseSeeder:
    """Test DatabaseSeeder class."""
    
    def test_context_manager(self, test_db):
        """Test context manager usage."""
        with DatabaseSeeder(test_db) as seeder:
            assert seeder.conn is not None
        # Connection should be closed after exiting context
    
    def test_connect_close(self, test_db):
        """Test manual connect/close."""
        seeder = DatabaseSeeder(test_db)
        assert seeder.conn is None
        
        seeder.connect()
        assert seeder.conn is not None
        
        seeder.close()
        assert seeder.conn is None
    
    def test_seed_users(self, test_db):
        """Test seeding users."""
        with DatabaseSeeder(test_db) as seeder:
            user_ids = seeder.seed_users(count=10)
            
            assert len(user_ids) == 10
            
            # Verify users were inserted
            cursor = seeder.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users")
            count = cursor.fetchone()[0]
            assert count == 10
            
            # Verify user data structure
            cursor.execute("SELECT * FROM users LIMIT 1")
            user = cursor.fetchone()
            assert user is not None
    
    def test_seed_users_with_roles(self, test_db):
        """Test seeding users with specific roles."""
        with DatabaseSeeder(test_db) as seeder:
            user_ids = seeder.seed_users(count=5, roles=["admin"])
            
            # Verify all users have admin role
            cursor = seeder.conn.cursor()
            cursor.execute("SELECT role FROM users")
            roles = [row[0] for row in cursor.fetchall()]
            assert all(role == "admin" for role in roles)
    
    def test_seed_telemetry(self, test_db):
        """Test seeding telemetry data."""
        with DatabaseSeeder(test_db) as seeder:
            telemetry_ids = seeder.seed_telemetry(count=100)
            
            assert len(telemetry_ids) == 100
            
            # Verify telemetry was inserted
            cursor = seeder.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM telemetry")
            count = cursor.fetchone()[0]
            assert count == 100
    
    def test_seed_telemetry_anomaly_ratio(self, test_db):
        """Test telemetry with specified anomaly ratio."""
        with DatabaseSeeder(test_db) as seeder:
            seeder.seed_telemetry(count=100, anomalous_ratio=0.3)
            
            # Check anomalous count (should be approximately 30)
            cursor = seeder.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM telemetry WHERE is_anomalous = 1")
            anomalous_count = cursor.fetchone()[0]
            
            # Allow some variance due to randomness
            assert 20 <= anomalous_count <= 40
    
    def test_seed_contact_submissions(self, test_db):
        """Test seeding contact submissions."""
        with DatabaseSeeder(test_db) as seeder:
            submission_ids = seeder.seed_contact_submissions(count=20)
            
            assert len(submission_ids) == 20
            
            # Verify submissions were inserted
            cursor = seeder.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM contact_submissions")
            count = cursor.fetchone()[0]
            assert count == 20
    
    def test_seed_contact_submissions_status_distribution(self, test_db):
        """Test contact submissions with status distribution."""
        with DatabaseSeeder(test_db) as seeder:
            status_dist = {"pending": 0.5, "resolved": 0.5}
            seeder.seed_contact_submissions(count=20, status_distribution=status_dist)
            
            cursor = seeder.conn.cursor()
            cursor.execute("SELECT status FROM contact_submissions")
            statuses = [row[0] for row in cursor.fetchall()]
            
            # Check that we have both statuses
            assert "pending" in statuses
            assert "resolved" in statuses
    
    def test_seed_api_keys(self, test_db):
        """Test seeding API keys."""
        with DatabaseSeeder(test_db) as seeder:
            keys = seeder.seed_api_keys(count=5)
            
            assert len(keys) == 5
            
            # Verify keys were inserted
            cursor = seeder.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM api_keys")
            count = cursor.fetchone()[0]
            assert count == 5
            
            # Verify key format
            assert all(len(key) == 32 for key in keys)
    
    def test_clear_table(self, test_db):
        """Test clearing a table."""
        with DatabaseSeeder(test_db) as seeder:
            # Seed some data
            seeder.seed_users(count=10)
            
            # Verify data exists
            cursor = seeder.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users")
            assert cursor.fetchone()[0] == 10
            
            # Clear the table
            seeder.clear_table("users")
            
            # Verify table is empty
            cursor.execute("SELECT COUNT(*) FROM users")
            assert cursor.fetchone()[0] == 0


class TestMemoryStoreSeeder:
    """Test MemoryStoreSeeder class."""
    
    def test_seed_telemetry_list(self):
        """Test seeding telemetry into a list."""
        telemetry = []
        MemoryStoreSeeder.seed_telemetry_list(telemetry, count=50)
        
        assert len(telemetry) == 50
        
        # Verify data structure
        for item in telemetry:
            assert "voltage" in item
            assert "temperature" in item
            assert "gyro" in item
            assert "timestamp" in item
            assert "is_anomalous" in item
    
    def test_seed_telemetry_with_anomalies(self):
        """Test seeding telemetry with anomalies."""
        telemetry = []
        MemoryStoreSeeder.seed_telemetry_list(
            telemetry,
            count=100,
            anomalous_ratio=0.4
        )
        
        anomalous_count = sum(1 for item in telemetry if item["is_anomalous"])
        
        # Allow variance due to randomness
        assert 30 <= anomalous_count <= 50
    
    def test_seed_user_dict(self):
        """Test seeding users into a dictionary."""
        users = {}
        MemoryStoreSeeder.seed_user_dict(users, count=10)
        
        assert len(users) == 10
        
        # Verify data structure
        for username, user in users.items():
            assert "id" in user
            assert "email" in user
            assert "role" in user
            assert user["username"] == username
    
    def test_seed_user_dict_with_roles(self):
        """Test seeding users with specific roles."""
        users = {}
        MemoryStoreSeeder.seed_user_dict(users, count=5, roles=["operator"])
        
        # Verify all users have operator role
        assert all(user["role"] == "operator" for user in users.values())


class TestScenarioSeeder:
    """Test ScenarioSeeder class."""
    
    def test_seed_normal_ops(self, test_db):
        """Test seeding normal operations scenario."""
        with DatabaseSeeder(test_db) as db_seeder:
            ScenarioSeeder.seed_scenario(ScenarioType.NORMAL_OPS, db_seeder)
            
            cursor = db_seeder.conn.cursor()
            
            # Verify users were seeded
            cursor.execute("SELECT COUNT(*) FROM users")
            assert cursor.fetchone()[0] == 5
            
            # Verify telemetry was seeded
            cursor.execute("SELECT COUNT(*) FROM telemetry")
            assert cursor.fetchone()[0] == 100
            
            # Verify API keys were seeded
            cursor.execute("SELECT COUNT(*) FROM api_keys")
            assert cursor.fetchone()[0] == 3
    
    def test_seed_anomaly_detection(self, test_db):
        """Test seeding anomaly detection scenario."""
        with DatabaseSeeder(test_db) as db_seeder:
            ScenarioSeeder.seed_scenario(ScenarioType.ANOMALY_DETECTION, db_seeder)
            
            cursor = db_seeder.conn.cursor()
            
            # Verify telemetry was seeded
            cursor.execute("SELECT COUNT(*) FROM telemetry")
            assert cursor.fetchone()[0] == 200
            
            # Verify higher anomaly ratio
            cursor.execute("SELECT COUNT(*) FROM telemetry WHERE is_anomalous = 1")
            anomalous_count = cursor.fetchone()[0]
            assert anomalous_count > 40  # ~30% of 200
    
    def test_seed_stress_test(self, test_db):
        """Test seeding stress test scenario."""
        with DatabaseSeeder(test_db) as db_seeder:
            ScenarioSeeder.seed_scenario(ScenarioType.STRESS_TEST, db_seeder)
            
            cursor = db_seeder.conn.cursor()
            
            # Verify large amounts of data
            cursor.execute("SELECT COUNT(*) FROM users")
            assert cursor.fetchone()[0] == 50
            
            cursor.execute("SELECT COUNT(*) FROM telemetry")
            assert cursor.fetchone()[0] == 10000
            
            cursor.execute("SELECT COUNT(*) FROM contact_submissions")
            assert cursor.fetchone()[0] == 500
    
    def test_seed_empty(self, test_db):
        """Test seeding empty scenario (clears all data)."""
        with DatabaseSeeder(test_db) as db_seeder:
            # First seed some data
            db_seeder.seed_users(count=10)
            db_seeder.seed_telemetry(count=50)
            
            # Now clear everything
            ScenarioSeeder.seed_scenario(ScenarioType.EMPTY, db_seeder)
            
            cursor = db_seeder.conn.cursor()
            
            # Verify all tables are empty
            cursor.execute("SELECT COUNT(*) FROM users")
            assert cursor.fetchone()[0] == 0
            
            cursor.execute("SELECT COUNT(*) FROM telemetry")
            assert cursor.fetchone()[0] == 0


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_quick_seed_db(self, test_db):
        """Test quick_seed_db function."""
        quick_seed_db(test_db, ScenarioType.NORMAL_OPS)
        
        # Verify data was seeded
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM users")
        assert cursor.fetchone()[0] > 0
        
        cursor.execute("SELECT COUNT(*) FROM telemetry")
        assert cursor.fetchone()[0] > 0
        
        conn.close()
    
    def test_quick_seed_telemetry(self):
        """Test quick_seed_telemetry function."""
        telemetry = quick_seed_telemetry(count=50)
        
        assert len(telemetry) == 50
        assert all("voltage" in item for item in telemetry)
    
    def test_quick_seed_telemetry_with_anomalies(self):
        """Test quick_seed_telemetry with anomalies."""
        telemetry = quick_seed_telemetry(count=100, anomalous=True)
        
        assert len(telemetry) == 100
        anomalous_count = sum(1 for item in telemetry if item.get("is_anomalous"))
        assert anomalous_count > 0
    
    def test_quick_seed_users(self):
        """Test quick_seed_users function."""
        users = quick_seed_users(count=5)
        
        assert len(users) == 5
        assert all("email" in user for user in users.values())


class TestDataQuality:
    """Test quality and consistency of seeded data."""
    
    def test_telemetry_timestamps_ordered(self, test_db):
        """Test that telemetry timestamps are in order."""
        with DatabaseSeeder(test_db) as seeder:
            seeder.seed_telemetry(count=50)
            
            cursor = seeder.conn.cursor()
            cursor.execute("SELECT timestamp FROM telemetry ORDER BY id")
            timestamps = [datetime.fromisoformat(row[0]) for row in cursor.fetchall()]
            
            # Verify timestamps are in ascending order
            for i in range(len(timestamps) - 1):
                assert timestamps[i] <= timestamps[i + 1]
    
    def test_user_emails_unique(self, test_db):
        """Test that user emails are unique."""
        with DatabaseSeeder(test_db) as seeder:
            seeder.seed_users(count=20)
            
            cursor = seeder.conn.cursor()
            cursor.execute("SELECT email FROM users")
            emails = [row[0] for row in cursor.fetchall()]
            
            # Verify all emails are unique
            assert len(emails) == len(set(emails))
    
    def test_api_keys_unique(self, test_db):
        """Test that API keys are unique."""
        with DatabaseSeeder(test_db) as seeder:
            keys = seeder.seed_api_keys(count=10)
            
            # Verify all keys are unique
            assert len(keys) == len(set(keys))
    
    def test_telemetry_values_in_range(self, test_db):
        """Test that telemetry values are within reasonable ranges."""
        with DatabaseSeeder(test_db) as seeder:
            seeder.seed_telemetry(count=100, anomalous_ratio=0.0)
            
            cursor = seeder.conn.cursor()
            cursor.execute("SELECT voltage, temperature FROM telemetry")
            
            for row in cursor.fetchall():
                voltage, temperature = row
                # Normal ranges
                assert 3.0 <= voltage <= 12.0
                assert -100 <= temperature <= 150


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_seed_zero_records(self, test_db):
        """Test seeding zero records."""
        with DatabaseSeeder(test_db) as seeder:
            user_ids = seeder.seed_users(count=0)
            assert len(user_ids) == 0
    
    def test_seed_large_batch(self, test_db):
        """Test seeding a large batch of records."""
        with DatabaseSeeder(test_db) as seeder:
            telemetry_ids = seeder.seed_telemetry(count=5000)
            assert len(telemetry_ids) == 5000
    
    def test_seed_with_fixed_random_seed(self):
        """Test reproducible seeding with fixed random seed."""
        config1 = SeedConfig(seed=42)
        telemetry1 = quick_seed_telemetry(count=10)
        
        config2 = SeedConfig(seed=42)
        telemetry2 = quick_seed_telemetry(count=10)
        
        # Results should be identical with same seed
        assert telemetry1[0]["voltage"] == telemetry2[0]["voltage"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
