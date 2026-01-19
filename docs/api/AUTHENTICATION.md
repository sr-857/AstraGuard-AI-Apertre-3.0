# API Authentication Implementation

## Overview

Basic API authentication has been successfully implemented for AstraGuard-AI using API keys with role-based permissions and rate limiting.

## Features Implemented

### ✅ API Key Management
- **APIKeyManager** class for managing API keys
- Key generation with configurable permissions
- Key validation and rate limiting
- Persistent storage in JSON format

### ✅ Authentication Dependencies
- `get_api_key()` dependency for FastAPI endpoints
- `require_permission()` for role-based access control
- Automatic key validation and rate limit checking

### ✅ Protected Endpoints
All core API endpoints now require authentication:
- `POST /api/v1/telemetry` - Submit telemetry (write permission)
- `POST /api/v1/telemetry/batch` - Batch telemetry submission (write permission)
- `GET /api/v1/status` - System status (read permission)
- `GET /api/v1/phase` - Current mission phase (read permission)
- `POST /api/v1/phase` - Update mission phase (admin permission)
- `GET /api/v1/memory/stats` - Memory statistics (read permission)
- `GET /api/v1/history/anomalies` - Anomaly history (read permission)

### ✅ Public Endpoints
Health check endpoints remain public for load balancers:
- `GET /` - Root health check
- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics (basic auth protected)

## Usage

### Environment Configuration

Set the `API_KEYS` environment variable with a JSON array of API keys:

```bash
export API_KEYS='[
  {
    "key": "your-api-key-here",
    "user": "service-name",
    "permissions": ["read", "write"],
    "created_at": "2024-01-01T00:00:00",
    "rate_limit": 1000
  }
]'
```

### API Key Permissions

- **read**: Access to GET endpoints (status, history, etc.)
- **write**: Access to POST endpoints (telemetry submission)
- **admin**: Full access including phase management

### Making Authenticated Requests

Include the API key in the `X-API-Key` header:

```bash
curl -H "X-API-Key: your-api-key-here" \
     -H "Content-Type: application/json" \
     -d '{"sensor_id": "test", "value": 42.0}' \
     http://localhost:8000/api/v1/telemetry
```

### Default Development Key

A default API key is automatically created for development:
```
API Key: 5SKLBQk-eCZ3-8hdt8G4JO3gUpFGiE7URJjL9hdDUNM
Permissions: read, write, admin
```

⚠️ **SECURITY WARNING**: This default key should NOT be used in production!

## Testing

Run the authentication tests:

```bash
python test_auth.py
```

## Security Features

- **Rate Limiting**: Configurable requests per hour per key
- **Permission-based Access**: Granular control over endpoint access
- **Key Expiration**: Optional key expiration dates
- **Secure Key Generation**: Cryptographically secure random keys
- **Request Logging**: Tracks key usage and last access time

## Files Modified

- `api/auth.py` - New authentication module
- `api/service.py` - Added authentication dependencies to endpoints

## Next Steps

1. **Environment Setup**: Configure `API_KEYS` environment variable in production
2. **Key Rotation**: Implement key rotation policies
3. **Monitoring**: Add authentication metrics and logging
4. **Documentation**: Update API documentation with authentication requirements