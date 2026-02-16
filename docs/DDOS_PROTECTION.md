# DDoS Protection

## Overview

AstraGuard's comprehensive DDoS (Distributed Denial of Service) protection system provides multi-layered defense against various types of attacks including HTTP floods, Slowloris attacks, application-layer attacks, and more.

## Features

### Core Protection Mechanisms

1. **IP-based Rate Limiting**
   - Per-second request limits
   - Per-minute request limits
   - Per-hour request limits
   - Configurable burst capacity

2. **Connection Management**
   - Concurrent connection limits per IP
   - Global concurrent connection limits
   - Connection timeout enforcement
   - Slowloris attack detection

3. **Threat Scoring System**
   - Dynamic threat scoring for each IP
   - Automatic score decay over time
   - Auto-blocking based on threat threshold
   - Violation tracking and analysis

4. **Attack Pattern Detection**
   - SQL injection attempt detection
   - XSS (Cross-Site Scripting) detection
   - Path traversal attempt detection
   - Replay attack detection
   - Missing/suspicious User-Agent detection
   - Excessive URL length detection
   - Unusual HTTP method detection

5. **IP Blocking**
   - Temporary IP blocking with TTL
   - Permanent blocking for repeat offenders
   - Manual unblock capability
   - Distributed blocking via Redis

6. **Whitelisting**
   - IP whitelist
   - User-Agent whitelist
   - Path whitelist for health checks
   - Localhost always whitelisted

## Architecture

```
┌─────────────────┐
│  HTTP Request   │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────┐
│  DDoS Protection Middleware     │
│  - Track Connection             │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  Protection Checks              │
│  1. Whitelist Check             │
│  2. Permanent Block Check       │
│  3. Temporary Block Check       │
│  4. Connection Limit Check      │
│  5. Rate Limit Check            │
│  6. Pattern Analysis            │
│  7. Threat Score Update         │
└────────┬────────────────────────┘
         │
         ├─── Blocked ──────┐
         │                  ▼
         │         ┌──────────────┐
         │         │  403 Response │
         │         └──────────────┘
         │
         └─── Allowed ────┐
                          ▼
                 ┌──────────────────┐
                 │  Process Request │
                 └──────────────────┘
```

## Configuration

### YAML Configuration

DDoS protection is configured via `config/ddos_protection.yaml`:

```yaml
ddos_protection:
  enabled: true

  rate_limiting:
    max_requests_per_second: 10
    max_requests_per_minute: 60
    max_requests_per_hour: 3600

  connection_limits:
    max_concurrent_per_ip: 10
    max_total_concurrent: 1000
    connection_timeout_seconds: 30

  ip_blocking:
    enabled: true
    auto_block_threshold: 80.0
    block_duration_seconds: 3600
    permanent_block_threshold: 5
```

### Environment Variables

Override configuration with environment variables:

```bash
# Enable/disable DDoS protection
export DDOS_ENABLED=true

# Rate limiting
export DDOS_MAX_REQUESTS_PER_SECOND=10
export DDOS_MAX_REQUESTS_PER_MINUTE=60

# Connection limits
export DDOS_MAX_CONNECTIONS_PER_IP=10

# Blocking thresholds
export DDOS_AUTO_BLOCK_THRESHOLD=80.0
export DDOS_BLOCK_DURATION=3600
```

### Environment-Specific Settings

The configuration supports environment-specific overrides:

```yaml
environments:
  development:
    ddos_protection:
      rate_limiting:
        max_requests_per_second: 100 # More lenient

  production:
    ddos_protection:
      ip_blocking:
        auto_block_threshold: 75.0 # More strict
```

## Usage

### Automatic Protection

DDoS protection is automatically enabled when the API server starts. No code changes required for basic protection.

### Manual Operations

#### Get Protection Statistics

```python
GET /api/v1/security/ddos/stats
Authorization: Bearer <admin_token>
```

Response:

```json
{
  "enabled": true,
  "timestamp": "2026-02-16T12:00:00Z",
  "statistics": {
    "total_requests_checked": 10000,
    "total_blocked": 42,
    "active_threats": 3,
    "blocked_ips_count": 5,
    "active_connections": 15,
    "tracked_ips": 150,
    "top_threats": [
      {
        "ip": "203.0.113.45",
        "score": 85.5,
        "violations": 12,
        "recent_violations": [...]
      }
    ]
  }
}
```

#### Unblock an IP

```python
POST /api/v1/security/ddos/unblock/{ip}
Authorization: Bearer <admin_token>
```

Response:

```json
{
  "success": true,
  "ip": "203.0.113.45",
  "message": "IP 203.0.113.45 has been unblocked",
  "timestamp": "2026-02-16T12:00:00Z"
}
```

### Programmatic Usage

```python
from security import DDoSProtection, DDoSConfig, load_ddos_config

# Load configuration
config = load_ddos_config()

# Create protection instance
ddos = DDoSProtection(redis_client=redis, config=config)

# Check a request
is_allowed, reason = await ddos.check_request(request)

if not is_allowed:
    return JSONResponse(
        status_code=403,
        content={"error": reason}
    )

# Get statistics
stats = await ddos.get_stats()

# Manually unblock an IP
await ddos.unblock_ip("203.0.113.45")
```

## Threat Scoring

### How It Works

Each IP address is assigned a threat score (0-100):

- **0-30**: Low threat - requests allowed
- **30-60**: Medium threat - monitored closely
- **60-80**: High threat - warnings logged
- **80-100**: Critical threat - auto-blocked

### Violation Scores

Different violations contribute different scores:

| Violation Type            | Score Added |
| ------------------------- | ----------- |
| Rate limit exceeded       | 15          |
| Connection limit exceeded | 10          |
| Suspicious pattern        | 20          |
| SQL injection attempt     | 50          |
| XSS attempt               | 50          |
| Path traversal attempt    | 40          |
| Replay attack             | 30          |
| Unusual HTTP method       | 25          |
| Missing User-Agent        | 20          |

### Score Decay

Threat scores decay over time:

- **Decay rate**: 1 point per minute
- Encourages good behavior
- Prevents permanent blocking of legitimate users

## Attack Detection

### SQL Injection

Detects patterns like:

- `UNION SELECT`
- `DROP TABLE`
- `INSERT INTO`
- SQL comments (`--`, `/*`)

### XSS (Cross-Site Scripting)

Detects patterns like:

- `<script>`
- `javascript:`
- `onerror=`
- `onload=`

### Path Traversal

Detects:

- `../` sequences
- `..%2f` URL-encoded variants

### HTTP Floods

Detects when:

- Requests per second exceed threshold
- Identical requests repeated rapidly

### Slowloris Attacks

Detects when:

- Connections held open too long
- Too many slow connections from single IP

## Monitoring

### Prometheus Metrics

DDoS protection exports Prometheus metrics:

```
# Blocked requests by reason and severity
astra_ddos_requests_blocked_total{reason="rate_limit", severity="medium"}

# Threats detected by attack type
astra_ddos_threats_detected_total{attack_type="sql_injection_attempt"}

# Active connections
astra_ddos_active_connections

# Protection check latency
astra_ddos_check_duration_seconds
```

### Logging

DDoS events are logged with structured logging:

```json
{
  "timestamp": "2026-02-16T12:00:00Z",
  "level": "WARNING",
  "event": "ddos_block",
  "ip": "203.0.113.45",
  "reason": "threat_score_exceeded",
  "threat_score": 85.5,
  "violations": ["rate_limit", "suspicious_pattern"]
}
```

## Performance

### Latency

- **Average check time**: < 1ms per request
- **P99 latency**: < 5ms per request
- Uses efficient in-memory data structures
- Optional Redis for distributed state

### Memory Usage

- **Per IP tracking**: ~500 bytes
- **Request history**: Limited to 1000 entries per IP
- **Violation history**: Limited to 100 entries per IP
- Automatic cleanup of expired blocks

### Scalability

- **Horizontal scaling**: Via Redis-backed state
- **High concurrency**: Async/await design
- **Thread-safe**: Uses asyncio locks
- **Distributed**: Works across multiple instances

## Best Practices

### Production Deployment

1. **Enable Redis**: For distributed state across instances

   ```yaml
   redis:
     use_redis: true
   ```

2. **Adjust Thresholds**: Based on your traffic patterns

   ```yaml
   rate_limiting:
     max_requests_per_second: 20 # Adjust based on load
   ```

3. **Monitor Metrics**: Set up alerts for blocked requests

   ```
   rate(astra_ddos_requests_blocked_total[5m]) > 10
   ```

4. **Whitelist Health Checks**: Add monitoring IPs to whitelist

   ```yaml
   whitelist:
     ips:
       - "10.0.0.100" # Monitoring system
   ```

5. **Log Rotation**: Ensure log files are rotated
   ```yaml
   logging:
     log_blocked_requests: true
     log_level: "INFO"
   ```

### Testing

Run the test suite:

```bash
# Run all DDoS protection tests
pytest tests/security/test_ddos_protection.py -v

# Run specific test
pytest tests/security/test_ddos_protection.py::test_rate_limit_per_second -v

# Run with coverage
pytest tests/security/test_ddos_protection.py --cov=security.ddos_protection
```

### Development

For development, use more lenient settings:

```bash
export ENVIRONMENT=development
export DDOS_MAX_REQUESTS_PER_SECOND=100
export DDOS_AUTO_BLOCK_THRESHOLD=90.0
```

## Troubleshooting

### Issue: Legitimate users getting blocked

**Solution**:

- Check if IP is in whitelist
- Review threat scores: `GET /api/v1/security/ddos/stats`
- Increase thresholds in config
- Manually unblock: `POST /api/v1/security/ddos/unblock/{ip}`

### Issue: Redis connection errors

**Solution**:

- DDoS protection falls back to local state
- Check Redis connectivity
- Verify `REDIS_URL` environment variable

### Issue: High memory usage

**Solution**:

- Reduce `request_window_seconds`
- Implement more aggressive cleanup
- Use Redis instead of local state

### Issue: False positives on pattern detection

**Solution**:

- Add legitimate patterns to whitelist
- Adjust `suspicious_pattern_threshold`
- Review and tune detection rules

## Security Considerations

1. **IP Spoofing**: Use `X-Forwarded-For` carefully in production
2. **Distributed Attacks**: Enable Redis for cross-instance protection
3. **Configuration Security**: Store config in secure location
4. **Admin Access**: Protect admin endpoints with strong auth
5. **Logging**: Don't log sensitive data in violations

## Compliance

DDoS protection helps meet compliance requirements:

- **PCI-DSS**: Requirement 6.6 (Web Application Firewall)
- **GDPR**: Security measures for data protection
- **SOC 2**: System availability and security
- **ISO 27001**: Access control and monitoring

## Future Enhancements

Planned improvements:

- [ ] Machine learning-based anomaly detection
- [ ] Geographic IP filtering
- [ ] CAPTCHA challenge for suspicious requests
- [ ] Honeypot endpoint integration
- [ ] Advanced bot detection
- [ ] API rate limiting per user/token
- [ ] Custom rule engine

## Support

For issues or questions:

- GitHub Issues: [Report an issue](https://github.com/sr-857/AstraGuard-AI-Apertre-3.0/issues)
- Documentation: [Full docs](../README.md)
- Security: Contact security team for vulnerabilities

## References

- [OWASP DDoS Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Denial_of_Service_Cheat_Sheet.html)
- [NIST Guidelines on DDoS](https://csrc.nist.gov/publications/detail/sp/800-61/rev-2/final)
- [CloudFlare DDoS Best Practices](https://www.cloudflare.com/learning/ddos/ddos-mitigation/)
