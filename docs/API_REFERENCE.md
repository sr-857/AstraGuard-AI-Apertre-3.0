# 🌐 API Reference

This page contains the REST API overview and examples extracted from the project `README.md`.

- Back to hub: [`README.md`](../README.md)

---

## 🌐 REST API for External Integration

AstraGuard AI provides a **production-ready FastAPI server** for programmatic access and integration with external systems.

### API Features

✅ **Input Validation**: Pydantic models with comprehensive data validation  
✅ **OpenAPI Documentation**: Interactive Swagger UI at `/docs`  
✅ **CORS Support**: Ready for web frontend integration  
✅ **Batch Processing**: Submit 1-1000 telemetry points in a single request  
✅ **Rate Limiting**: Configurable limits to prevent abuse  
✅ **Authentication**: API key support for production deployments  
✅ **Versioning**: `/api/v1/` prefix for future compatibility  
✅ **100% Test Coverage**: 23/23 tests passing  

---

## Quick Start Example

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"

# Submit telemetry
response = requests.post(f"{BASE_URL}/telemetry", json={
    "timestamp": "2026-01-04T12:00:00Z",
    "voltage": 7.2,
    "temperature": 35.5,
    "gyro": 0.08,
    "mission_phase": "NOMINAL_OPS"
})

result = response.json()
print(result)
```

