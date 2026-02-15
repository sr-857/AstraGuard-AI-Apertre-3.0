"""Combined tests for security infrastructure (#649, #650, #655, #656, #657)"""

import pytest
import os
import tempfile
from src.security.audit_logger import AuditLogger, AuditEventType
from src.security.waf_rules import WAFRules
from src.security.api_key_manager import APIKeyManager
from src.security.tls_config import TLSConfig


class TestAuditLogger:
    def test_log_event(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            logger = AuditLogger(f.name)
            
            event_hash = logger.log_event(
                AuditEventType.LOGIN,
                "user123",
                "User logged in",
                result="success"
            )
            
            assert event_hash is not None
            assert len(event_hash) == 64  # SHA-256
            
            os.unlink(f.name)


class TestWAFRules:
    def test_sql_injection_detection(self):
        waf = WAFRules()
        
        assert waf.check_sql_injection("SELECT * FROM users WHERE id=1") is False
        assert waf.check_sql_injection("1' OR '1'='1") is True
        assert waf.check_sql_injection("'; DROP TABLE users--") is True
    
    def test_xss_detection(self):
        waf = WAFRules()
        
        assert waf.check_xss("Hello world") is False
        assert waf.check_xss("<script>alert('xss')</script>") is True
        assert waf.check_xss("javascript:alert(1)") is True
    
    def test_rate_limiting(self):
        waf = WAFRules(rate_limit_per_minute=2)
        
        assert waf.check_rate_limit("client1") is False
        assert waf.check_rate_limit("client1") is False
        assert waf.check_rate_limit("client1") is True  # Exceeded


class TestAPIKeyManager:
    def test_generate_key(self):
        manager = APIKeyManager()
        key = manager.generate_key("user123", "test_key")
        
        assert key.startswith("ak_")
        assert len(key) > 10
    
    def test_validate_key(self):
        manager = APIKeyManager()
        key = manager.generate_key("user123", "test_key")
        
        user_id = manager.validate_key(key)
        assert user_id == "user123"
    
    def test_revoke_key(self):
        manager = APIKeyManager()
        key = manager.generate_key("user123", "test_key")
        
        assert manager.revoke_key(key) is True
        assert manager.validate_key(key) is None


class TestTLSConfig:
    def test_create_ssl_context(self):
        tls = TLSConfig()
        context = tls.create_ssl_context()
        
        assert context is not None
        assert context.minimum_version.name == "TLSv1_3"
