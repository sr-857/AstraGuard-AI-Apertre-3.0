import time
import psutil
from fastapi import Request
from src.monitoring.metrics import (
    HTTP_REQUEST_COUNT,
    HTTP_REQUEST_LATENCY,
    ACTIVE_REQUESTS,
    APP_UPTIME_SECONDS,
    START_TIME,
    SYSTEM_CPU_USAGE,
    SYSTEM_MEMORY_USAGE,
)

async def prometheus_middleware(request: Request, call_next):
    method = request.method
    path = request.url.path

    ACTIVE_REQUESTS.inc()
    start_time = time.time()
    status_code = 500  # Default status code

    try:
        # Update system metrics
        SYSTEM_CPU_USAGE.set(psutil.cpu_percent())
        SYSTEM_MEMORY_USAGE.set(psutil.virtual_memory().percent)

        response = await call_next(request)
        status_code = response.status_code
        return response
    except Exception as e:
        status_code = 500
        raise e
    finally:
        latency = time.time() - start_time

        HTTP_REQUEST_LATENCY.labels(
            method=method,
            endpoint=path
        ).observe(latency)

        HTTP_REQUEST_COUNT.labels(
            method=method,
            endpoint=path,
            status_code=str(status_code)
        ).inc()

        ACTIVE_REQUESTS.dec()
        APP_UPTIME_SECONDS.set(time.time() - START_TIME)
