"""
WAF (Web Application Firewall) Rules for AstraGuard

Implements security rules for SQL injection, XSS, and rate limiting.
"""

import re
import logging
from typing import Optional
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class WAFRules:
    """
    Web Application Firewall rules.
    
    Features:
    - SQL injection detection
    - XSS prevention
    - Rate limiting
    - Request validation
    """
    
    def __init__(self, rate_limit_per_minute: int = 60):
        """Initialize WAF rules."""
        self.rate_limit = rate_limit_per_minute
        self._request_counts = defaultdict(list)
        
        # SQL injection patterns
        self.sql_patterns = [
            r"(\bunion\b.*\bselect\b)",
            r"(\bor\b.*=.*)",
            r"(;.*drop\b.*table)",
            r"(exec\s*\()",
            r"(script.*>)",
        ]
        
        # XSS patterns
        self.xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"onerror\s*=",
            r"onload\s*=",
        ]
        
        logger.info("WAF rules initialized")
    
    def check_sql_injection(self, input_str: str) -> bool:
        """Check for SQL injection patterns."""
        for pattern in self.sql_patterns:
            if re.search(pattern, input_str, re.IGNORECASE):
                logger.warning(f"SQL injection detected: {pattern}")
                return True
        return False
    
    def check_xss(self, input_str: str) -> bool:
        """Check for XSS patterns."""
        for pattern in self.xss_patterns:
            if re.search(pattern, input_str, re.IGNORECASE):
                logger.warning(f"XSS detected: {pattern}")
                return True
        return False
    
    def check_rate_limit(self, client_id: str) -> bool:
        """Check if client exceeds rate limit."""
        now = datetime.now()
        cutoff = now - timedelta(minutes=1)
        
        # Clean old requests
        self._request_counts[client_id] = [
            ts for ts in self._request_counts[client_id]
            if ts > cutoff
        ]
        
        # Check limit
        if len(self._request_counts[client_id]) >= self.rate_limit:
            logger.warning(f"Rate limit exceeded: {client_id}")
            return True
        
        # Record request
        self._request_counts[client_id].append(now)
        return False


# Global instance
_waf_rules: Optional[WAFRules] = None


def get_waf_rules() -> WAFRules:
    """Get global WAF rules."""
    global _waf_rules
    if _waf_rules is None:
        _waf_rules = WAFRules()
    return _waf_rules
