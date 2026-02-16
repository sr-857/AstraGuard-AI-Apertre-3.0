# TLS/SSL Setup Guide for AstraGuard AI

This guide explains how to configure TLS/SSL encryption for all internal service communication in AstraGuard AI, ensuring secure communication between microservices (Memory Engine, Anomaly Detection, API Service, etc.).

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Certificate Generation](#certificate-generation)
4. [Configuration](#configuration)
5. [Service-Specific Setup](#service-specific-setup)
6. [Environment Variables](#environment-variables)
7. [Testing TLS](#testing-tls)
8. [Troubleshooting](#troubleshooting)

## Overview

AstraGuard AI enforces TLS/SSL encryption for all internal service communication to:

- **Prevent eavesdropping**: All data transmitted between services is encrypted
- **Ensure authentication**: Services verify each other's identities using certificates
- **Enable compliance**: Meet security standards (SOC 2, PCI DSS, etc.)
- **Support mutual TLS (mTLS)**: Optional service-to-service authentication

### Supported Protocols

- **HTTPS**: For HTTP-based API communication
- **Redis over TLS (rediss://)**: For Redis connections
- **AMQP over TLS (amqps://)**: For message queue connections
- **Kafka over TLS (SSL://)**: For streaming data

## Quick Start

### 1. Enable TLS (Development Mode)

```bash
# Set environment variables
export TLS_ENABLED=true
export TLS_ENFORCE=false  # Allow HTTP in development
export TLS_VERIFY_MODE=none  # Don't verify certificates in dev

# Start the application
python -m src.api.service
```

### 2. Enable TLS (Production Mode)

```bash
# Set environment variables
export TLS_ENABLED=true
export TLS_ENFORCE=true  # Reject non-TLS connections
export TLS_VERIFY_MODE=required
export TLS_MIN_VERSION=1.2
export TLS_CERT_FILE=/path/to/server.crt
export TLS_KEY_FILE=/path/to/server.key
export TLS_CA_FILE=/path/to/ca.crt

# Start the application
python -m src.api.service
```

## Certificate Generation

### Option 1: Self-Signed Certificates (Development)

```bash
# Create certificates directory
mkdir -p certs/dev

# Generate CA key and certificate
openssl genrsa -out certs/dev/ca.key 4096
openssl req -new -x509 -days 365 -key certs/dev/ca.key -out certs/dev/ca.crt \
  -subj "/C=US/ST=State/L=City/O=AstraGuard/CN=AstraGuard CA"

# Generate server key and certificate
openssl genrsa -out certs/dev/server.key 4096
openssl req -new -key certs/dev/server.key -out certs/dev/server.csr \
  -subj "/C=US/ST=State/L=City/O=AstraGuard/CN=localhost"
openssl x509 -req -in certs/dev/server.csr -CA certs/dev/ca.crt \
  -CAkey certs/dev/ca.key -CAcreateserial -out certs/dev/server.crt -days 365

# Set permissions
chmod 600 certs/dev/*.key
```

### Option 2: Let's Encrypt (Production)

```bash
# Install certbot
sudo apt-get install certbot

# Generate certificate
sudo certbot certonly --standalone -d your-domain.com

# Certificates will be at:
# /etc/letsencrypt/live/your-domain.com/fullchain.pem
# /etc/letsencrypt/live/your-domain.com/privkey.pem
```

### Option 3: Cloud Provider (AWS, GCP, Azure)

**AWS Certificate Manager:**
```bash
# Use AWS CLI to request a certificate
aws acm request-certificate \
  --domain-name your-domain.com \
  --validation-method DNS \
  --idempotency-token 123456
```

**Google Cloud:**
```bash
# Use gcloud to create a certificate
gcloud compute ssl-certificates create astraguard-cert \
  --domains=your-domain.com \
  --global
```

## Configuration

### Configuration File

Edit `src/config/tls_config.yaml`:

```yaml
default:
  enabled: true
  enforce_tls: true
  verify_mode: required
  min_tls_version: "1.2"
  cert_file: "certs/server.crt"
  key_file: "certs/server.key"
  ca_file: "certs/ca.crt"

api:
  enabled: true
  enforce_tls: true
  cert_file: "certs/api.crt"
  key_file: "certs/api.key"

redis:
  enabled: true
  enforce_tls: true
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TLS_ENABLED` | Enable TLS encryption | `true` |
| `TLS_ENFORCE` | Reject non-TLS connections | `true` |
| `TLS_CERT_FILE` | Path to TLS certificate | `certs/server.crt` |
| `TLS_KEY_FILE` | Path to TLS private key | `certs/server.key` |
| `TLS_CA_FILE` | Path to CA bundle | `certs/ca.crt` |
| `TLS_VERIFY_MODE` | Certificate verification mode | `required` |
| `TLS_MIN_VERSION` | Minimum TLS version | `1.2` |
| `TLS_MUTUAL_TLS` | Enable mutual TLS | `false` |
| `TLS_CIPHER_SUITES` | Allowed cipher suites | `ECDHE+AESGCM:...` |

## Service-Specific Setup

### API Service

```python
from core.tls_config import get_tls_config
from core.tls_enforcement import TLSMiddleware

# TLS middleware is automatically added in src/api/service.py
# Check TLS status:
curl https://localhost:8000/api/v1/tls/status
```

### Redis Client

```python
from backend.redis_client import RedisClient

# Automatically uses TLS if TLS_ENFORCE=true
redis_client = RedisClient(redis_url="rediss://localhost:6379")
await redis_client.connect()
```

### Memory Engine

```python
from core.tls_enforcement import require_tls

@require_tls
def connect_to_memory_engine(url: str):
    # This function will reject non-TLS URLs
    return connect(url)
```

### Anomaly Detector

```python
from core.secure_http_client import SecureHTTPClient

client = SecureHTTPClient(service_name="anomaly_detector")
response = await client.get("https://internal-api/anomaly-check")
```

## Testing TLS

### 1. Check TLS Status

```bash
curl https://localhost:8000/api/v1/tls/status
```

Expected response:
```json
{
  "tls_enabled": true,
  "tls_enforced": true,
  "tls_configured": true,
  "request_secure": true,
  "min_tls_version": "TLSVersion.TLSv1_2",
  "mutual_tls": false,
  "timestamp": "2024-01-15T10:30:00"
}
```

### 2. Validate TLS Configuration

```bash
curl https://localhost:8000/api/v1/tls/validate
```

### 3. Test with OpenSSL

```bash
# Test TLS connection
openssl s_client -connect localhost:8000 -tls1_2

# Test with specific certificate
openssl s_client -connect localhost:8000 \
  -cert certs/client.crt \
  -key certs/client.key \
  -CAfile certs/ca.crt
```

### 4. Test Redis TLS

```bash
# Connect to Redis with TLS
redis-cli --tls -h localhost -p 6379 \
  --cert certs/redis.crt \
  --key certs/redis.key \
  --cacert certs/ca.crt \
  ping
```

## Troubleshooting

### Issue: "TLS is not enabled"

**Cause**: TLS configuration is disabled or missing certificates.

**Solution**:
```bash
# Check environment variables
echo $TLS_ENABLED
echo $TLS_CERT_FILE

# Verify certificate files exist
ls -la certs/

# Enable TLS
export TLS_ENABLED=true
export TLS_ENFORCE=true
```

### Issue: "Certificate verification failed"

**Cause**: CA certificate is missing or incorrect.

**Solution**:
```bash
# Update CA file path
export TLS_CA_FILE=/path/to/ca.crt

# Or disable verification (development only)
export TLS_VERIFY_MODE=none
```

### Issue: "HTTP URL not allowed when TLS is enforced"

**Cause**: Trying to use HTTP when TLS enforcement is enabled.

**Solution**:
```bash
# Use HTTPS instead of HTTP
export REDIS_URL=rediss://localhost:6379  # Note: rediss:// not redis://

# Or disable TLS enforcement (development only)
export TLS_ENFORCE=false
```

### Issue: "Redis connection failed with TLS"

**Cause**: Redis server not configured for TLS or certificate mismatch.

**Solution**:
```bash
# Check Redis TLS configuration
redis-cli CONFIG GET tls-port
redis-cli CONFIG GET tls-cert-file

# Verify certificate
openssl x509 -in certs/redis.crt -text -noout

# Test without TLS (development only)
export TLS_ENFORCE=false
export REDIS_URL=redis://localhost:6379
```

### Issue: "SSL: CERTIFICATE_VERIFY_FAILED"

**Cause**: Python cannot verify the certificate.

**Solution**:
```python
# Update certifi package
pip install --upgrade certifi

# Or specify CA bundle explicitly
export TLS_CA_FILE=$(python -m certifi)
```

### Issue: "TLS version mismatch"

**Cause**: Client and server have different TLS version requirements.

**Solution**:
```bash
# Check supported TLS versions
openssl s_client -connect localhost:8000 -tls1_3

# Adjust minimum TLS version
export TLS_MIN_VERSION=1.2  # or 1.3
```

## Security Best Practices

1. **Always use TLS 1.2 or higher** in production
2. **Enable mutual TLS (mTLS)** for service-to-service authentication
3. **Use strong cipher suites** (disable weak ciphers)
4. **Rotate certificates regularly** (every 90 days)
5. **Use certificate pinning** for critical services
6. **Monitor TLS handshake failures** and alert on anomalies
7. **Store private keys securely** (use hardware security modules if possible)

## Compliance

### SOC 2 Compliance

- Enable TLS 1.2+ for all connections
- Use mutual TLS for service authentication
- Log all TLS connections and failures
- Rotate certificates every 90 days

### PCI DSS Compliance

- Use TLS 1.2+ with strong cipher suites
- Disable SSLv2, SSLv3, TLS 1.0, TLS 1.1
- Implement certificate pinning
- Regular vulnerability scans

### FIPS 140-2 Compliance

```bash
# Enable FIPS mode
export TLS_FIPS_MODE=true

# Use FIPS-approved algorithms only
export TLS_CIPHER_SUITES="FIPS:!aNULL:!eNULL"
```

## Additional Resources

- [OpenSSL Documentation](https://www.openssl.org/docs/)
- [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [Redis TLS Configuration](https://redis.io/topics/encryption)

## Support

For TLS-related issues:

1. Check the logs: `logs/audit/audit.log`
2. Run validation: `curl https://localhost:8000/api/v1/tls/validate`
3. Review this guide
4. Open an issue with TLS configuration details (redact sensitive information)
