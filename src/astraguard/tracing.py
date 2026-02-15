"""
AstraGuard OpenTelemetry Tracing Module
Distributed tracing with Jaeger for production observability
"""

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from contextlib import contextmanager, asynccontextmanager
import logging
import os
from typing import Optional, Any, Dict, Tuple, Generator, AsyncGenerator
from core.secrets import get_secret
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger: logging.Logger = logging.getLogger(__name__)

# ============================================================================
# JAEGER EXPORTER CONFIGURATION
# ============================================================================

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((ConnectionError, OSError)),
    reraise=True
)
def initialize_tracing(
    service_name: str = "astra-guard",
    jaeger_host: str = "localhost",
    jaeger_port: int = 6831,
    enabled: bool = True,
    batch_size: int = 512,
    export_interval: float = 5.0
) -> TracerProvider:
    """
    Initialize OpenTelemetry tracing with a Jaeger backend.

    Configures a global TracerProvider that exports spans to a Jaeger agent
    via gRPC. Includes automatic resource tagging (environment, version) and
    batch processing for performance.

    Robustness:
    - Retries connection failures with exponential backoff.
    - Returns a no-op provider if tracing is disabled or initialization fails.

    Args:
        service_name: Name of the service for tracing
        jaeger_host: Jaeger agent hostname
        jaeger_port: Jaeger agent port (1-65535)
        enabled: Enable/disable tracing
        batch_size: Max batch size for span export (must be > 0)
        export_interval: Export interval in seconds (must be > 0)
        
    Returns:
        TracerProvider instance
        
    Raises:
        ValueError: If configuration parameters are invalid
        ConnectionError: If unable to connect to Jaeger (after retries)
    """
    if not enabled:
        logger.info("⚠️  Tracing disabled - using no-op tracer provider")
        return TracerProvider()
    
    # Input validation
    if not (1 <= jaeger_port <= 65535):
        logger.error(
            f"Invalid jaeger_port: {jaeger_port} "
            f"(must be between 1 and 65535)"
        )
        raise ValueError(f"jaeger_port must be between 1-65535, got {jaeger_port}")
    
    if batch_size <= 0:
        logger.error(f"Invalid batch_size: {batch_size} (must be > 0)")
        raise ValueError(f"batch_size must be positive, got {batch_size}")
    
    if export_interval <= 0:
        logger.error(f"Invalid export_interval: {export_interval} (must be > 0)")
        raise ValueError(f"export_interval must be positive, got {export_interval}")
    
    try:
        # Configure Jaeger exporter
        jaeger_exporter = JaegerExporter(
            agent_host_name=jaeger_host,
            agent_port=jaeger_port,
            transport_format="grpc",
        )
        
        # Create tracer provider with service resource
        resource = Resource.create({
            SERVICE_NAME: service_name,
            "environment": get_secret("environment", "development"),
            "version": get_secret("app_version", "1.0.0"),
        })
        
        provider = TracerProvider(resource=resource)
        processor = BatchSpanProcessor(
            jaeger_exporter,
            max_export_batch_size=batch_size,
            schedule_delay_millis=int(export_interval * 1000)
        )
        provider.add_span_processor(processor)
        
        # Set global tracer provider
        trace.set_tracer_provider(provider)
        
        logger.info(f"✅ Tracing initialized - Jaeger at {jaeger_host}:{jaeger_port}")
        return provider
        
    except (ConnectionError, OSError) as e:
        # Network/connection issues - already retried by tenacity decorator
        logger.error(
            f"Failed to connect to Jaeger at {jaeger_host}:{jaeger_port} "
            f"after retries: {e}"
        )
        raise
    except ImportError as e:
        logger.error(f"Missing OpenTelemetry dependency: {e}")
        logger.info("Falling back to no-op tracer provider")
        return TracerProvider()
    except ValueError as e:
        # Configuration errors
        logger.error(f"Invalid tracing configuration: {e}")
        raise
    except Exception as e:
        # Unexpected errors - log with full context
        logger.warning(
            f"Unexpected error initializing Jaeger "
            f"(host={jaeger_host}, port={jaeger_port}): {type(e).__name__}: {e}"
        )
        logger.info("Falling back to no-op tracer provider")
        return TracerProvider()



def setup_auto_instrumentation():
    """
    Setup automatic instrumentation for common libraries
    Must be called before creating FastAPI app
    """
    # Instrument requests library
    try:
        RequestsInstrumentor().instrument()
        logger.info("✅ Auto-instrumentation enabled for requests")
    except ImportError as e:
        logger.warning(f"⚠️  Missing requests instrumentation library: {e}")
    except RuntimeError as e:
        logger.warning(f"⚠️  Failed to instrument requests library: {e}")
    except AttributeError as e:
        logger.error(
            f"Requests instrumentation method not found: {e}. "
            f"Check OpenTelemetry version compatibility."
        )
    
    # Instrument Redis library
    try:
        RedisInstrumentor().instrument()
        logger.info("✅ Auto-instrumentation enabled for Redis")
    except ImportError as e:
        logger.warning(f"⚠️  Missing Redis instrumentation library: {e}")
    except RuntimeError as e:
        logger.warning(f"⚠️  Failed to instrument Redis library: {e}")
    except AttributeError as e:
        logger.error(
            f"Redis instrumentation method not found: {e}. "
            f"Check OpenTelemetry version compatibility."
        )


def instrument_fastapi(app: Any) -> None:
    """
    Instrument FastAPI application with OpenTelemetry

    Args:
        app: FastAPI application instance
        
    Raises:
        TypeError: If app is None or invalid type
    """
    if app is None:
        logger.error("Cannot instrument FastAPI: app is None")
        raise TypeError("FastAPI app cannot be None")
    
    try:
        FastAPIInstrumentor.instrument_app(app)
        logger.info("✅ FastAPI instrumented with OpenTelemetry")
    except ImportError as e:
        logger.warning(f"⚠️  Missing FastAPI instrumentation: {e}")
    except TypeError as e:
        logger.error(
            f"Invalid FastAPI app type: {type(app).__name__}. "
            f"Expected FastAPI instance: {e}"
        )
        raise
    except RuntimeError as e:
        logger.warning(f"⚠️  Failed to instrument FastAPI: {e}")
    except AttributeError as e:
        logger.error(
            f"FastAPI instrumentation method not found: {e}. "
            f"Check OpenTelemetry version compatibility."
        )


# ============================================================================
# TRACER CONTEXT MANAGERS
# ============================================================================

def get_tracer(name: str = __name__) -> trace.Tracer:
    """Get a tracer instance"""
    return trace.get_tracer(name)


@contextmanager
def span(name: str, attributes: Optional[Dict[str, Any]] = None) -> Generator[Any, None, None]:
    """
    Context manager for creating manual OpenTelemetry spans.

    Wraps a block of code in a custom span, allowing for granular performance
    tracking and attribute tagging. Automatically handles span lifecycle (start/end)
    and exception recording.

    Args:
        name (str): The operation name to display in the trace.
        attributes (Optional[dict]): Key-value pairs to annotate the span
                                     (e.g., {"user_id": "123", "retry": "true"}).

    Yields:
        trace.Span: The active span object for further customization.

    Example:
        with span("process_image", {"image_size": "1024x768"}):
            process(image)
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(name) as span_obj:
        if attributes:
            for key, value in attributes.items():
                try:
                    span_obj.set_attribute(key, str(value))
                except (TypeError, ValueError) as e:
                    logger.warning(
                        f"Failed to set span attribute '{key}': {e}. "
                        f"Attribute type: {type(value).__name__}"
                    )
                except Exception as e:
                    logger.debug(
                        f"Unexpected error setting attribute '{key}': {e}"
                    )
        yield span_obj



@contextmanager
def span_anomaly_detection(data_size: int, model_name: str = "default") -> Generator[Any, None, None]:
    """
    Trace anomaly detection workflow with sub-spans
    
    Args:
        data_size: Size of input data
        model_name: Name of ML model
    """
    tracer = get_tracer()
    with tracer.start_as_current_span("anomaly_detection") as main_span:
        main_span.set_attribute("data.size", data_size)
        main_span.set_attribute("model", model_name)
        
        try:
            yield main_span
        except RuntimeError as e:
            main_span.record_exception(e)
            raise
        except Exception as e:
            main_span.record_exception(e)
            raise


@contextmanager
def span_model_inference(model_type: str, input_shape: Any) -> Generator[Any, None, None]:
    """
    Trace ML model inference operations
    
    Args:
        model_type: Type of model (e.g., 'classifier', 'detector')
        input_shape: Shape of input data
    """
    tracer = get_tracer()
    with tracer.start_as_current_span("model_inference") as span_obj:
        span_obj.set_attribute("model.type", model_type)
        span_obj.set_attribute("input.shape", str(input_shape))
        yield span_obj


@contextmanager
def span_external_call(service: str, operation: str, timeout: Optional[float] = None) -> Generator[Any, None, None]:
    """
    Trace external service calls (API, database, etc.)
    
    Args:
        service: External service name
        operation: Operation being performed
        timeout: Operation timeout in seconds
    """
    tracer = get_tracer()
    with tracer.start_as_current_span("external_call") as span_obj:
        span_obj.set_attribute("service", service)
        span_obj.set_attribute("operation", operation)
        if timeout:
            span_obj.set_attribute("timeout", timeout)
        yield span_obj


@contextmanager
def span_database_query(query_type: str, table: Optional[str] = None) -> Generator[Any, None, None]:
    """
    Trace database query operations
    
    Args:
        query_type: Type of query (SELECT, INSERT, UPDATE, etc.)
        table: Table name (optional)
    """
    tracer = get_tracer()
    with tracer.start_as_current_span("database_query") as span_obj:
        span_obj.set_attribute("query.type", query_type)
        if table:
            span_obj.set_attribute("table", table)
        yield span_obj


@contextmanager
def span_cache_operation(operation: str, key: str, cache_type: str = "redis") -> Generator[Any, None, None]:
    """
    Trace cache operations
    
    Args:
        operation: Cache operation (get, set, delete)
        key: Cache key
        cache_type: Type of cache (default: redis)
    """
    tracer = get_tracer()
    with tracer.start_as_current_span("cache_operation") as span_obj:
        span_obj.set_attribute("cache.operation", operation)
        span_obj.set_attribute("cache.key", key)
        span_obj.set_attribute("cache.type", cache_type)
        yield span_obj


@contextmanager
def span_circuit_breaker(name: str, operation: str) -> Generator[Any, None, None]:
    """
    Trace circuit breaker operations
    
    Args:
        name: Name of the circuit breaker
        operation: Operation type (call, trip, reset, half-open)
    """
    tracer = get_tracer()
    with tracer.start_as_current_span("circuit_breaker") as span_obj:
        span_obj.set_attribute("breaker.name", name)
        span_obj.set_attribute("breaker.operation", operation)
        yield span_obj


@contextmanager
def span_retry(endpoint: str, attempt: int) -> Generator[Any, None, None]:
    """
    Trace retry attempts
    
    Args:
        endpoint: Endpoint being retried
        attempt: Retry attempt number
    """
    tracer = get_tracer()
    with tracer.start_as_current_span("retry") as span_obj:
        span_obj.set_attribute("endpoint", endpoint)
        span_obj.set_attribute("attempt", attempt)
        yield span_obj


# ============================================================================
# TRACING SHUTDOWN
# ============================================================================

def shutdown_tracing() -> None:
    """
    Gracefully shutdown tracer and flush pending spans
    Call this on application shutdown
    """
    try:
        provider = trace.get_tracer_provider()
        
        if not hasattr(provider, 'force_flush'):
            logger.debug("Tracer provider does not support force_flush (no-op provider)")
            return
        
        # Attempt to flush with timeout
        provider.force_flush(timeout_millis=5000)
        logger.info("✅ Tracing flushed and shutdown complete")
        
    except ConnectionError as e:
        logger.warning(
            f"⚠️  Connection error during tracing shutdown: {e}. "
            f"Some spans may not have been exported."
        )
    except TimeoutError as e:
        logger.warning(
            f"⚠️  Timeout during span flush: {e}. "
            f"Some pending spans may not have been exported."
        )
    except RuntimeError as e:
        logger.warning(f"⚠️  Runtime error during tracing shutdown: {e}")
    except Exception as e:
        # Unexpected errors during shutdown - log but don't raise
        logger.warning(
            f"Unexpected error during tracing shutdown: {type(e).__name__}: {e}"
        )


# ASYNC CONTEXT MANAGERS

@asynccontextmanager
async def async_span(name: str, attributes: Optional[Dict[str, Any]] = None) -> AsyncGenerator[Any, None]:
    """
    Async context manager for creating spans

    Args:
        name: Span name
        attributes: Optional span attributes

    Example:
        async with async_span("database_query", {"table": "users"}):
            # Do async work
            pass
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(name) as span_obj:
        if attributes:
            for key, value in attributes.items():
                span_obj.set_attribute(key, str(value))
        yield span_obj


@asynccontextmanager
async def async_span_anomaly_detection(data_size: int, model_name: str = "default") -> AsyncGenerator[Any, None]:
    """
    Async trace anomaly detection workflow with sub-spans

    Args:
        data_size: Size of input data
        model_name: Name of ML model
    """
    tracer = get_tracer()
    with tracer.start_as_current_span("anomaly_detection") as main_span:
        main_span.set_attribute("data.size", data_size)
        main_span.set_attribute("model", model_name)

        try:
            yield main_span
        except RuntimeError as e:
            main_span.record_exception(e)
            raise
        except Exception as e:
            main_span.record_exception(e)
            raise


@asynccontextmanager
async def async_span_external_call(service: str, operation: str, timeout: Optional[float] = None) -> AsyncGenerator[Any, None]:
    """
    Async trace external service calls (API, database, etc.)

    Args:
        service: External service name
        operation: Operation being performed
        timeout: Operation timeout in seconds
    """
    tracer = get_tracer()
    with tracer.start_as_current_span("external_call") as span_obj:
        span_obj.set_attribute("service", service)
        span_obj.set_attribute("operation", operation)
        if timeout:
            span_obj.set_attribute("timeout", timeout)
        yield span_obj
