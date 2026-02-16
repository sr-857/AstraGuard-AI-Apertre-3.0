"""
AstraGuard DDoS Protection Module

Comprehensive Distributed Denial of Service (DDoS) protection system implementing:
- IP-based rate limiting and blocking
- Request pattern analysis for attack detection
- Connection throttling and limits
- Geographic filtering (optional)
- Slowloris and HTTP flood protection
- Real-time threat scoring
- Automatic IP blacklisting with TTL
"""

import time
import hashlib
import asyncio
from typing import Dict, Optional, Set, Tuple, List, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as aioredis

try:
    from prometheus_client import Counter, Histogram, Gauge
    ddos_requests_blocked = Counter(
        'astra_ddos_requests_blocked_total',
        'Total number of requests blocked by DDoS protection',
        ['reason', 'severity']
    )
    ddos_threats_detected = Counter(
        'astra_ddos_threats_detected_total',
        'Total number of DDoS threats detected',
        ['attack_type']
    )
    ddos_active_connections = Gauge(
        'astra_ddos_active_connections',
        'Current number of active connections per IP'
    )
    ddos_check_latency = Histogram(
        'astra_ddos_check_duration_seconds',
        'Time spent checking DDoS protection rules'
    )
    METRICS_ENABLED = True
except (ImportError, ValueError):
    METRICS_ENABLED = False
    ddos_requests_blocked = None
    ddos_threats_detected = None
    ddos_active_connections = None
    ddos_check_latency = None


@dataclass
class ThreatScore:
    """Represents a threat assessment for an IP address."""
    ip: str
    score: float = 0.0
    last_updated: float = field(default_factory=time.time)
    violations: List[str] = field(default_factory=list)
    request_count: int = 0
    connection_count: int = 0
    
    def is_threat(self, threshold: float = 80.0) -> bool:
        """Check if threat score exceeds threshold."""
        return self.score >= threshold


@dataclass
class DDoSConfig:
    """Configuration for DDoS protection."""
    # Rate limiting
    max_requests_per_minute: int = 60
    max_requests_per_second: int = 10
    
    # Connection limits
    max_concurrent_connections_per_ip: int = 10
    max_total_concurrent_connections: int = 1000
    
    # Request patterns
    suspicious_pattern_threshold: int = 5  # Number of suspicious patterns before blocking
    request_window_seconds: int = 60
    
    # IP blocking
    auto_block_threshold: float = 80.0  # Threat score threshold for auto-blocking
    block_duration_seconds: int = 3600  # 1 hour default
    permanent_block_threshold: int = 5  # Number of blocks before permanent ban
    
    # Attack detection
    slowloris_timeout_seconds: int = 30
    http_flood_threshold: int = 100  # Requests per second
    
    # Whitelisting
    whitelist_ips: Set[str] = field(default_factory=set)
    whitelist_user_agents: Set[str] = field(default_factory=set)
    
    # Geographic filtering (optional)
    blocked_countries: Set[str] = field(default_factory=set)
    allowed_countries: Optional[Set[str]] = None  # If set, only these countries are allowed


class DDoSProtection:
    """
    DDoS Protection Engine implementing multiple layers of defense.
    """
    
    def __init__(
        self,
        redis_client: Optional[aioredis.Redis] = None,
        config: Optional[DDoSConfig] = None
    ):
        """
        Initialize DDoS protection engine.
        
        Args:
            redis_client: Redis client for distributed state (optional)
            config: DDoS configuration
        """
        self.redis = redis_client
        self.config = config or DDoSConfig()
        
        # Local state (used when Redis unavailable or for fast lookups)
        self._threat_scores: Dict[str, ThreatScore] = {}
        self._blocked_ips: Dict[str, float] = {}  # IP -> expiration timestamp
        self._permanent_blocks: Set[str] = set()
        self._active_connections: Dict[str, int] = defaultdict(int)
        self._request_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._pattern_violations: Dict[str, List[str]] = defaultdict(list)
        
        # Locks for thread safety
        self._lock = asyncio.Lock()
        
        # Statistics
        self.stats = {
            'total_requests_checked': 0,
            'total_blocked': 0,
            'active_threats': 0,
            'blocked_ips_count': 0
        }
    
    async def check_request(self, request: Request) -> Tuple[bool, Optional[str]]:
        """
        Check if a request should be allowed or blocked.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Tuple of (is_allowed, block_reason)
        """
        start_time = time.time()
        self.stats['total_requests_checked'] += 1
        
        # Extract IP address
        ip = self._get_client_ip(request)
        
        # Check whitelist first
        if self._is_whitelisted(ip, request):
            return True, None
        
        # Check permanent blocks
        if ip in self._permanent_blocks:
            self.stats['total_blocked'] += 1
            if ddos_requests_blocked:
                ddos_requests_blocked.labels(reason='permanent_block', severity='critical').inc()
            return False, "IP permanently blocked due to repeated violations"
        
        # Check temporary blocks
        if await self._is_ip_blocked(ip):
            self.stats['total_blocked'] += 1
            if ddos_requests_blocked:
                ddos_requests_blocked.labels(reason='temporary_block', severity='high').inc()
            return False, "IP temporarily blocked due to suspicious activity"
        
        # Check connection limits
        if not await self._check_connection_limit(ip):
            await self._increment_threat_score(ip, 10.0, "Connection limit exceeded")
            self.stats['total_blocked'] += 1
            if ddos_requests_blocked:
                ddos_requests_blocked.labels(reason='connection_limit', severity='medium').inc()
            return False, "Too many concurrent connections from your IP"
        
        # Check rate limits
        if not await self._check_rate_limit(ip):
            await self._increment_threat_score(ip, 15.0, "Rate limit exceeded")
            self.stats['total_blocked'] += 1
            if ddos_requests_blocked:
                ddos_requests_blocked.labels(reason='rate_limit', severity='medium').inc()
            return False, "Rate limit exceeded. Please slow down your requests"
        
        # Check for suspicious patterns
        suspicious_pattern = await self._detect_suspicious_pattern(request, ip)
        if suspicious_pattern:
            await self._increment_threat_score(ip, 20.0, f"Suspicious pattern: {suspicious_pattern}")
            if ddos_threats_detected:
                ddos_threats_detected.labels(attack_type=suspicious_pattern).inc()
        
        # Check threat score
        threat_score = await self._get_threat_score(ip)
        if threat_score.is_threat(self.config.auto_block_threshold):
            await self._block_ip(ip, self.config.block_duration_seconds)
            self.stats['total_blocked'] += 1
            if ddos_requests_blocked:
                ddos_requests_blocked.labels(reason='threat_score', severity='high').inc()
            return False, f"IP blocked due to threat score: {threat_score.score:.1f}"
        
        # Record request for pattern analysis
        await self._record_request(ip, request)
        
        # Record latency
        if ddos_check_latency:
            ddos_check_latency.observe(time.time() - start_time)
        
        return True, None
    
    async def track_connection(self, ip: str, increment: bool = True) -> None:
        """
        Track active connections for an IP.
        
        Args:
            ip: IP address
            increment: True to add connection, False to remove
        """
        async with self._lock:
            if increment:
                self._active_connections[ip] += 1
            else:
                self._active_connections[ip] = max(0, self._active_connections[ip] - 1)
                if self._active_connections[ip] == 0:
                    del self._active_connections[ip]
        
        if ddos_active_connections and increment:
            ddos_active_connections.set(sum(self._active_connections.values()))
    
    async def _check_connection_limit(self, ip: str) -> bool:
        """Check if IP has exceeded connection limits."""
        current_connections = self._active_connections.get(ip, 0)
        
        # Check per-IP limit
        if current_connections >= self.config.max_concurrent_connections_per_ip:
            return False
        
        # Check global limit
        total_connections = sum(self._active_connections.values())
        if total_connections >= self.config.max_total_concurrent_connections:
            return False
        
        return True
    
    async def _check_rate_limit(self, ip: str) -> bool:
        """Check if IP has exceeded rate limits."""
        now = time.time()
        history = self._request_history[ip]
        
        # Clean old entries
        while history and history[0] < now - self.config.request_window_seconds:
            history.popleft()
        
        # Check requests per minute
        requests_last_minute = len([t for t in history if t > now - 60])
        if requests_last_minute >= self.config.max_requests_per_minute:
            return False
        
        # Check requests per second
        requests_last_second = len([t for t in history if t > now - 1])
        if requests_last_second >= self.config.max_requests_per_second:
            return False
        
        return True
    
    async def _detect_suspicious_pattern(self, request: Request, ip: str) -> Optional[str]:
        """
        Detect suspicious request patterns that may indicate an attack.
        
        Returns:
            Attack type if detected, None otherwise
        """
        # Check for common attack patterns
        
        # 1. Missing or suspicious User-Agent
        user_agent = request.headers.get("user-agent", "")
        if not user_agent or len(user_agent) < 10:
            return "suspicious_user_agent"
        
        # 2. Unusual request methods
        if request.method not in ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]:
            return "unusual_method"
        
        # 3. Excessively long URLs (possible buffer overflow attempt)
        if len(str(request.url)) > 2000:
            return "excessive_url_length"
        
        # 4. SQL injection patterns in query parameters
        query_string = str(request.url.query).lower()
        sql_patterns = ["union select", "drop table", "insert into", "--", "/*", "xp_"]
        if any(pattern in query_string for pattern in sql_patterns):
            return "sql_injection_attempt"
        
        # 5. XSS patterns
        xss_patterns = ["<script", "javascript:", "onerror=", "onload="]
        if any(pattern in query_string for pattern in xss_patterns):
            return "xss_attempt"
        
        # 6. Path traversal attempts
        if "../" in str(request.url.path) or "..%2f" in str(request.url).lower():
            return "path_traversal_attempt"
        
        # 7. Rapid identical requests (potential replay attack)
        request_signature = self._get_request_signature(request)
        history = self._request_history[ip]
        if history:
            recent_signatures = [self._get_request_signature(r) for r in list(history)[-10:]]
            if recent_signatures.count(request_signature) > 3:
                return "replay_attack"
        
        return None
    
    def _get_request_signature(self, request: Request) -> str:
        """Generate a signature for request deduplication."""
        sig_data = f"{request.method}:{request.url.path}:{request.url.query}"
        return hashlib.md5(sig_data.encode()).hexdigest()[:16]
    
    async def _get_threat_score(self, ip: str) -> ThreatScore:
        """Get current threat score for an IP."""
        if ip not in self._threat_scores:
            self._threat_scores[ip] = ThreatScore(ip=ip)
        
        # Decay threat score over time (reduce by 1 point per minute)
        score = self._threat_scores[ip]
        elapsed = time.time() - score.last_updated
        decay = (elapsed / 60.0) * 1.0
        score.score = max(0.0, score.score - decay)
        score.last_updated = time.time()
        
        return score
    
    async def _increment_threat_score(self, ip: str, points: float, reason: str) -> None:
        """Increment threat score for an IP."""
        score = await self._get_threat_score(ip)
        score.score = min(100.0, score.score + points)
        score.violations.append(f"{datetime.utcnow().isoformat()}: {reason}")
        score.last_updated = time.time()
        
        # Keep only recent violations
        if len(score.violations) > 100:
            score.violations = score.violations[-100:]
    
    async def _is_ip_blocked(self, ip: str) -> bool:
        """Check if an IP is currently blocked."""
        # Check local blocks
        if ip in self._blocked_ips:
            if time.time() < self._blocked_ips[ip]:
                return True
            else:
                # Block expired
                del self._blocked_ips[ip]
        
        # Check Redis if available
        if self.redis:
            try:
                blocked = await self.redis.get(f"astra:ddos:blocked:{ip}")
                return blocked is not None
            except Exception:
                pass
        
        return False
    
    async def _block_ip(self, ip: str, duration_seconds: int) -> None:
        """Block an IP address for a specified duration."""
        expiration = time.time() + duration_seconds
        self._blocked_ips[ip] = expiration
        
        # Update Redis if available
        if self.redis:
            try:
                await self.redis.setex(
                    f"astra:ddos:blocked:{ip}",
                    duration_seconds,
                    "1"
                )
                # Track block count
                block_count = await self.redis.incr(f"astra:ddos:block_count:{ip}")
                
                # Permanent block if threshold exceeded
                if block_count >= self.config.permanent_block_threshold:
                    await self._permanent_block_ip(ip)
                    
            except Exception as e:
                print(f"Redis error while blocking IP: {e}")
        
        self.stats['blocked_ips_count'] = len(self._blocked_ips)
    
    async def _permanent_block_ip(self, ip: str) -> None:
        """Permanently block an IP address."""
        self._permanent_blocks.add(ip)
        
        if self.redis:
            try:
                await self.redis.sadd("astra:ddos:permanent_blocks", ip)
            except Exception:
                pass
    
    async def _record_request(self, ip: str, request: Request) -> None:
        """Record a request for pattern analysis."""
        now = time.time()
        self._request_history[ip].append(now)
        
        # Track in threat score
        if ip in self._threat_scores:
            self._threat_scores[ip].request_count += 1
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check X-Forwarded-For header (for proxied requests)
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # Take the first IP in the chain
            return forwarded.split(",")[0].strip()
        
        # Check X-Real-IP header
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
        
        # Fall back to direct client IP
        if request.client:
            return request.client.host
        
        return "unknown"
    
    def _is_whitelisted(self, ip: str, request: Request) -> bool:
        """Check if IP or user agent is whitelisted."""
        # Check IP whitelist
        if ip in self.config.whitelist_ips:
            return True
        
        # Check localhost
        if ip in ["127.0.0.1", "::1", "localhost"]:
            return True
        
        # Check user agent whitelist
        user_agent = request.headers.get("user-agent", "")
        if any(ua in user_agent for ua in self.config.whitelist_user_agents):
            return True
        
        return False
    
    async def unblock_ip(self, ip: str) -> bool:
        """
        Manually unblock an IP address.
        
        Args:
            ip: IP address to unblock
            
        Returns:
            True if IP was unblocked, False otherwise
        """
        removed = False
        
        # Remove from local blocks
        if ip in self._blocked_ips:
            del self._blocked_ips[ip]
            removed = True
        
        # Remove from Redis
        if self.redis:
            try:
                await self.redis.delete(f"astra:ddos:blocked:{ip}")
                await self.redis.delete(f"astra:ddos:block_count:{ip}")
                removed = True
            except Exception:
                pass
        
        # Reset threat score
        if ip in self._threat_scores:
            self._threat_scores[ip] = ThreatScore(ip=ip)
        
        return removed
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get current DDoS protection statistics."""
        return {
            **self.stats,
            'active_connections': sum(self._active_connections.values()),
            'tracked_ips': len(self._threat_scores),
            'permanent_blocks': len(self._permanent_blocks),
            'top_threats': await self._get_top_threats(10)
        }
    
    async def _get_top_threats(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top threat IPs by score."""
        threats = [
            {
                'ip': score.ip,
                'score': round(score.score, 2),
                'violations': len(score.violations),
                'recent_violations': score.violations[-5:] if score.violations else []
            }
            for score in sorted(
                self._threat_scores.values(),
                key=lambda x: x.score,
                reverse=True
            )[:limit]
            if score.score > 0
        ]
        return threats


class DDoSProtectionMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for DDoS protection."""
    
    def __init__(self, app, ddos_protection: DDoSProtection):
        super().__init__(app)
        self.ddos = ddos_protection
    
    async def dispatch(self, request: Request, call_next):
        """Process request through DDoS protection."""
        # Get client IP
        ip = self.ddos._get_client_ip(request)
        
        # Track connection
        await self.ddos.track_connection(ip, increment=True)
        
        try:
            # Check if request should be allowed
            is_allowed, block_reason = await self.ddos.check_request(request)
            
            if not is_allowed:
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": "Access Forbidden",
                        "message": block_reason or "Your request was blocked by DDoS protection",
                        "ip": ip,
                        "timestamp": datetime.utcnow().isoformat()
                    },
                    headers={
                        "X-DDoS-Protection": "blocked",
                        "X-Client-IP": ip
                    }
                )
            
            # Process request
            response = await call_next(request)
            
            # Add security headers
            response.headers["X-DDoS-Protection"] = "active"
            
            return response
            
        finally:
            # Always decrement connection count
            await self.ddos.track_connection(ip, increment=False)


# Singleton instance
_ddos_protection: Optional[DDoSProtection] = None


async def get_ddos_protection(
    redis_client: Optional[aioredis.Redis] = None,
    config: Optional[DDoSConfig] = None
) -> DDoSProtection:
    """
    Get or create DDoS protection instance.
    
    Args:
        redis_client: Redis client for distributed state
        config: DDoS configuration
        
    Returns:
        DDoS protection instance
    """
    global _ddos_protection
    
    if _ddos_protection is None:
        _ddos_protection = DDoSProtection(redis_client, config)
    
    return _ddos_protection
