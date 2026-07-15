import time
from src.api.models import TelemetryInput

def benchmark_telemetry_input_creation(n=1000):
    """Benchmark creation of n TelemetryInput instances."""
    start_time = time.time()
    for _ in range(n):
        # Create instance without timestamp to trigger default
        TelemetryInput(
            voltage=12.5,
            temperature=25.0,
            gyro=0.1,
            current=1.5,
            wheel_speed=1000.0,
            cpu_usage=50.0,
            memory_usage=60.0,
            network_latency=10.0,
            disk_io=100.0,
            error_rate=0.01,
            response_time=5.0,
            active_connections=10
        )
    end_time = time.time()
    return end_time - start_time

if __name__ == "__main__":
    elapsed = benchmark_telemetry_input_creation()
    print(f"Time to create 1000 TelemetryInput instances: {elapsed:.4f} seconds")
