"""
CSRF (Cross-Site Request Forgery) Protection for AstraGuard

Implements double-submit cookie pattern with token generation and validation.
Protects state-changing operations from CSRF attacks.
"""

import logging
import secrets
import hmac
import hashlib
from typing import Optional
from datetime import datetime, timedelta
from fastapi import Request, HTTPException, status
from fastapi.responses import Response

logger = logging.getLogger(__name__)


class CSRFProtection:
    """
    CSRF protection using double-submit cookie pattern.
    
    Features:
    - Secure token generation
    - Token validation with HMAC
    - Configurable token expiry
    - Integration with FastAPI
    """
    
    def __init__(
        self,
        secret_key: str,
        token_expiry_hours: int = 24,
        cookie_name: str = "csrf_token",
        header_name: str = "X-CSRF-Token"
    ):
        """
        Initialize CSRF protection.
        
        Args:
            secret_key: Secret key for HMAC signing
            token_expiry_hours: Token validity period
            cookie_name: Name of CSRF cookie
            header_name: Name of CSRF header
        """
        self.secret_key = secret_key.encode()
        self.token_expiry = timedelta(hours=token_expiry_hours)
        self.cookie_name = cookie_name
        self.header_name = header_name
        
        logger.info(f"CSRF protection initialized with {token_expiry_hours}h expiry")
    
    def generate_token(self) -> str:
        """
        Generate a new CSRF token.
        
        Returns:
            Secure random token
        """
        # Generate random token
        random_token = secrets.token_urlsafe(32)
        
        # Add timestamp
        timestamp = datetime.now().isoformat()
        
        # Create signed token
        message = f"{random_token}:{timestamp}"
        signature = hmac.new(
            self.secret_key,
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        token = f"{message}:{signature}"
        logger.debug("Generated new CSRF token")
        
        return token
    
    def validate_token(self, token: str) -> bool:
        """
        Validate a CSRF token.
        
        Args:
            token: Token to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Parse token
            parts = token.split(":")
            if len(parts) != 3:
                logger.warning("Invalid CSRF token format")
                return False
            
            random_token, timestamp_str, signature = parts
            
            # Verify signature
            message = f"{random_token}:{timestamp_str}"
            expected_signature = hmac.new(
                self.secret_key,
                message.encode(),
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(signature, expected_signature):
                logger.warning("CSRF token signature mismatch")
                return False
            
            # Check expiry
            timestamp = datetime.fromisoformat(timestamp_str)
            if datetime.now() - timestamp > self.token_expiry:
                logger.warning("CSRF token expired")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating CSRF token: {e}")
            return False
    
    def set_token_cookie(self, response: Response, token: str):
        """
        Set CSRF token as cookie.
        
        Args:
            response: FastAPI response
            token: CSRF token to set
        """
        response.set_cookie(
            key=self.cookie_name,
            value=token,
            httponly=True,
            secure=True,  # HTTPS only
            samesite="strict",
            max_age=int(self.token_expiry.total_seconds())
        )
    
    async def validate_request(self, request: Request):
        """
        Validate CSRF token from request.
        
        Args:
            request: FastAPI request
            
        Raises:
            HTTPException: If CSRF validation fails
        """
        # Skip validation for safe methods
        if request.method in ["GET", "HEAD", "OPTIONS"]:
            return
        
        # Get token from cookie
        cookie_token = request.cookies.get(self.cookie_name)
        if not cookie_token:
            logger.warning("CSRF cookie missing")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF cookie missing"
            )
        
        # Get token from header
        header_token = request.headers.get(self.header_name)
        if not header_token:
            logger.warning("CSRF header missing")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token missing from header"
            )
        
        # Verify tokens match (double-submit pattern)
        if not hmac.compare_digest(cookie_token, header_token):
            logger.warning("CSRF token mismatch")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token mismatch"
            )
        
        # Validate token
        if not self.validate_token(cookie_token):
            logger.warning("CSRF token validation failed")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or expired CSRF token"
            )
        
        logger.debug("CSRF validation successful")


# Global instance
_csrf_protection: Optional[CSRFProtection] = None


def get_csrf_protection(secret_key: Optional[str] = None) -> CSRFProtection:
    """Get or create CSRF protection instance."""
    global _csrf_protection
    
    if _csrf_protection is None:
        if secret_key is None:
            # In production, get from environment
            import os
            secret_key = os.getenv("CSRF_SECRET_KEY", secrets.token_urlsafe(32))
        
        _csrf_protection = CSRFProtection(secret_key)
    
    return _csrf_protection


# FastAPI dependency
async def csrf_protect(request: Request):
    """FastAPI dependency for CSRF protection."""
    csrf = get_csrf_protection()
    await csrf.validate_request(request)
