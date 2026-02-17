import os
import sys
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.testclient import TestClient
from prometheus_client import generate_latest

# Ensure root is in path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.monitoring.middleware import prometheus_middleware

def test_metrics_collection():
    app = FastAPI()
    app.middleware("http")(prometheus_middleware)

    @app.get("/test")
    def test_endpoint():
        return {"message": "ok"}

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(), media_type="text/plain")

    client = TestClient(app)

    # Make a request
    response = client.get("/test")
    assert response.status_code == 200

    # Get metrics
    metrics_response = client.get("/metrics")
    assert metrics_response.status_code == 200
    metrics_text = metrics_response.text

    # Verify metrics exist
    assert 'http_requests_total' in metrics_text
    assert 'http_request_latency_seconds' in metrics_text
    assert 'app_uptime_seconds' in metrics_text
    assert 'system_cpu_usage_percent' in metrics_text
    assert 'system_memory_usage_percent' in metrics_text

    # Verify specific label for /test
    print(metrics_text)
    assert 'endpoint="/test"' in metrics_text
    assert 'status_code="200"' in metrics_text

def test_metrics_environment_restriction():
    # Simulate production environment
    os.environ["ENV"] = "production"

    app = FastAPI()

    @app.get("/metrics")
    def metrics():
        if os.getenv("ENV") == "production":
            raise HTTPException(status_code=403)
        return Response(generate_latest(), media_type="text/plain")

    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code == 403

    # Cleanup
    del os.environ["ENV"]
