"""Tests for CSRF Protection (#646)"""

import pytest
from fastapi import Request, Response
from fastapi.testclient import TestClient
from src.security.csrf_protection import CSRFProtection, get_csrf_protection


class TestCSRFProtection:
    @pytest.fixture
    def csrf(self):
        return CSRFProtection(secret_key="test-secret-key-12345")
    
    def test_generate_token(self, csrf):
        token = csrf.generate_token()
        assert token is not None
        assert len(token) > 0
        assert ":" in token
    
    def test_validate_valid_token(self, csrf):
        token = csrf.generate_token()
        assert csrf.validate_token(token) is True
    
    def test_validate_invalid_token(self, csrf):
        assert csrf.validate_token("invalid:token:format") is False
    
    def test_validate_tampered_token(self, csrf):
        token = csrf.generate_token()
        # Tamper with token
        tampered = token[:-5] + "xxxxx"
        assert csrf.validate_token(tampered) is False
    
    def test_token_expiry(self, csrf):
        # Create CSRF with very short expiry
        short_csrf = CSRFProtection(
            secret_key="test-key",
            token_expiry_hours=0  # Immediate expiry
        )
        token = short_csrf.generate_token()
        
        import time
        time.sleep(0.1)
        
        # Token should be expired
        assert short_csrf.validate_token(token) is False
    
    def test_set_token_cookie(self, csrf):
        response = Response()
        token = csrf.generate_token()
        csrf.set_token_cookie(response, token)
        
        # Check cookie was set
        assert csrf.cookie_name in response.headers.get("set-cookie", "")
    
    def test_singleton(self):
        csrf1 = get_csrf_protection("test-key")
        csrf2 = get_csrf_protection()
        assert csrf1 is csrf2
