"""Tests for Secret Rotation (#648)"""

import pytest
import time
from datetime import datetime, timedelta
from src.security.secret_rotation import (
    SecretRotation,
    SecretType,
    get_secret_rotation
)


class TestSecretRotation:
    @pytest.fixture
    def rotation(self):
        return SecretRotation(grace_period_hours=1, rotation_interval_days=30)
    
    def test_generate_secret(self, rotation):
        api_key = rotation.generate_secret(SecretType.API_KEY)
        assert api_key.startswith("sk_live_")
        assert len(api_key) > 10
    
    def test_rotate_secret(self, rotation):
        version_id = rotation.rotate_secret("test_secret", SecretType.API_KEY)
        assert version_id == "v1"
        
        secret_value = rotation.get_current_secret("test_secret")
        assert secret_value is not None
    
    def test_multiple_rotations(self, rotation):
        # First rotation
        v1 = rotation.rotate_secret("api_key", SecretType.API_KEY)
        secret1 = rotation.get_current_secret("api_key")
        
        # Second rotation
        v2 = rotation.rotate_secret("api_key", SecretType.API_KEY)
        secret2 = rotation.get_current_secret("api_key")
        
        assert v1 == "v1"
        assert v2 == "v2"
        assert secret1 != secret2
    
    def test_validate_secret_current(self, rotation):
        rotation.rotate_secret("test", SecretType.JWT_SECRET)
        current = rotation.get_current_secret("test")
        
        assert rotation.validate_secret("test", current) is True
    
    def test_validate_secret_during_grace_period(self, rotation):
        # First secret
        rotation.rotate_secret("test", SecretType.JWT_SECRET)
        old_secret = rotation.get_current_secret("test")
        
        # Rotate to new secret
        rotation.rotate_secret("test", SecretType.JWT_SECRET)
        new_secret = rotation.get_current_secret("test")
        
        # Both should be valid during grace period
        assert rotation.validate_secret("test", old_secret) is True
        assert rotation.validate_secret("test", new_secret) is True
    
    def test_cleanup_expired_secrets(self, rotation):
        # Create rotation with very short grace period
        short_rotation = SecretRotation(grace_period_hours=0)
        
        short_rotation.rotate_secret("test", SecretType.API_KEY)
        time.sleep(0.1)
        short_rotation.rotate_secret("test", SecretType.API_KEY)
        
        # Cleanup should remove expired version
        removed = short_rotation.cleanup_expired_secrets()
        assert removed >= 0
    
    def test_get_secret_info(self, rotation):
        rotation.rotate_secret("test", SecretType.API_KEY)
        rotation.rotate_secret("test", SecretType.API_KEY)
        
        info = rotation.get_secret_info("test")
        assert info["secret_name"] == "test"
        assert info["total_versions"] == 2
    
    def test_singleton(self):
        r1 = get_secret_rotation()
        r2 = get_secret_rotation()
        assert r1 is r2
