# API Error Handling

AstraGuard AI uses a standardized error response format for all API endpoints. This document outlines the error structure, codes, and troubleshooting steps.

## Error Response Format

All API errors return a JSON response with the following structure:

```json
{
  "success": false,
  "error": {
    "code": "VAL_001",
    "message": "Invalid telemetry payload",
    "details": {
      "field": "timestamp"
    },
    "trace_id": "abc12345-6789-0123-4567-89abcdef0123"
  }
}
```

### Fields

- `success`: Always `false` for errors.
- `error.code`: A unique error code (see below).
- `error.message`: A human-readable error message.
- `error.details`: (Optional) Additional context, such as validation errors.
- `error.trace_id`: A unique ID for tracing the request across logs.

## Error Categories

| Category | HTTP Status | Code Prefix | Description |
| :--- | :--- | :--- | :--- |
| **Validation** | 400 | `VAL_` | Invalid input data (e.g., missing fields, wrong type). |
| **Authentication** | 401/403 | `AUTH_` | Missing or invalid API key, or insufficient permissions. |
| **Rate Limit** | 429 | `RATE_` | Too many requests. Retry after the window resets. |
| **Not Found** | 404 | `RES_` | The requested resource does not exist. |
| **Server** | 500 | `SRV_` | Unexpected internal server error. |
| **Dependency** | 502/503 | `DEP_` | External service (Redis, DB, ML Model) unavailable. |

## Error Codes

### Validation Errors (`VAL_`)
| Code | Message | Description |
| :--- | :--- | :--- |
| `VAL_000` | Bad Request | Generic client error. |
| `VAL_001` | Validation Error | Input payload failed schema validation. Check `details`. |

### Authentication Errors (`AUTH_`)
| Code | Message | Description |
| :--- | :--- | :--- |
| `AUTH_001` | Unauthorized | Missing or invalid authentication credentials. |
| `AUTH_003` | Forbidden | Authenticated user lacks permission for this action. |

### Resource Errors (`RES_`)
| Code | Message | Description |
| :--- | :--- | :--- |
| `RES_001` | Resource Not Found | The requested endpoint or resource ID was not found. |

### Rate Limit Errors (`RATE_`)
| Code | Message | Description |
| :--- | :--- | :--- |
| `RATE_001` | Too Many Requests | Rate limit exceeded. |

### Server Errors (`SRV_`)
| Code | Message | Description |
| :--- | :--- | :--- |
| `SRV_000` | Internal Error | Generic server error. |
| `SRV_001` | Internal Server Error | Unexpected failure in API processing. |
| `SRV_002` | Anomaly Engine Error | Failure in anomaly detection logic. |
| `SRV_003` | Policy Error | Failure in policy evaluation. |
| `SRV_004` | State Error | Failure in state machine transition. |
| `SRV_005` | Database Error | Database operation failed. |
| `SRV_999` | Unexpected Error | Catch-all for unhandled exceptions. |

### Dependency Errors (`DEP_`)
| Code | Message | Description |
| :--- | :--- | :--- |
| `DEP_001` | Dependency Failure | Generic external dependency failure. |
| `DEP_002` | Model Load Error | Failed to load ML model. |
| `DEP_003` | Service Unavailable | Redis or other critical service is down. |

## Resilience

The API implements automatic resilience mechanisms:

- **Retries**: Transient errors (e.g., connection timeouts) are automatically retried with exponential backoff.
- **Circuit Breakers**: If a dependency (like Redis) fails repeatedly, the system will "fail fast" with `DEP_003` to prevent cascading failures until the service recovers.

## Support

If you encounter persistent errors, please report them with the `trace_id` from the error response.
