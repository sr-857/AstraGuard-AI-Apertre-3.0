"""
Test script for Predictive Maintenance functionality.
"""

import asyncio
import sys
import logging
from datetime import datetime, timedelta
import numpy as np

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Add project root to path
sys.path.insert(0, '..')

from memory_engine.memory_store import AdaptiveMemoryStore
from security_engine.predictive_maintenance import (
    get_predictive_maintenance_engine,
    TimeSeriesData,
    FailureType
)

async def test_predictive_maintenance():
    """Test the predictive maintenance functionality."""
    print("🧪 Testing Predictive Maintenance Engine")
    print("=" * 50)

    # Initialize memory store
    memory_store = AdaptiveMemoryStore()

    # Initialize predictive maintenance engine
    engine = await get_predictive_maintenance_engine(memory_store)
    print("✅ Predictive maintenance engine initialized")

    # Generate sample training data
    print("\n📊 Generating sample training data...")
    base_time = datetime.now() - timedelta(days=7)

    for i in range(1000):  # 1000 data points
        timestamp = base_time + timedelta(hours=i)

        # Simulate normal operation with occasional anomalies
        cpu_usage = np.random.normal(45, 10)  # Normal CPU usage around 45%
        memory_usage = np.random.normal(60, 15)  # Normal memory usage around 60%
        network_latency = np.random.normal(50, 20)  # Normal latency around 50ms
        disk_io = np.random.normal(100, 30)  # Normal disk I/O around 100 ops/sec
        error_rate = np.random.normal(0.1, 0.05)  # Low error rate
        response_time = np.random.normal(200, 50)  # Normal response time
        active_connections = np.random.randint(10, 50)

        # Introduce some anomalies
        failure_occurred = False
        if i > 800:  # Recent anomalies
            if np.random.random() < 0.1:  # 10% chance of failure
                failure_type = np.random.choice(list(FailureType))
                if failure_type == FailureType.CPU_SPIKE:
                    cpu_usage = np.random.uniform(85, 95)
                elif failure_type == FailureType.MEMORY_LEAK:
                    memory_usage = np.random.uniform(90, 98)
                elif failure_type == FailureType.NETWORK_LATENCY:
                    network_latency = np.random.uniform(500, 2000)
                failure_occurred = True

        # Create training data point
        data_point = TimeSeriesData(
            timestamp=timestamp,
            cpu_usage=max(0, min(100, cpu_usage)),
            memory_usage=max(0, min(100, memory_usage)),
            network_latency=max(0, network_latency),
            disk_io=max(0, disk_io),
            error_rate=max(0, error_rate),
            response_time=max(0, response_time),
            active_connections=active_connections,
            failure_occurred=failure_occurred
        )

        await engine.add_training_data(data_point)

    print(f"✅ Added {len(engine.training_data)} training data points")

    # Train models
    print("\n🤖 Training predictive models...")
    training_metrics = await engine.train_models()
    print("✅ Model training completed")
    print(f"📈 Training metrics: {training_metrics}")

    # Test predictions
    print("\n🔮 Testing failure predictions...")

    # Create a test data point that might indicate impending failure
    test_data = TimeSeriesData(
        timestamp=datetime.now(),
        cpu_usage=85.0,  # Very high CPU usage
        memory_usage=90.0,  # Very high memory usage
        network_latency=200.0,  # High latency
        disk_io=250.0,  # Very high disk I/O
        error_rate=2.0,  # High error rate
        response_time=500.0,  # Slow response time
        active_connections=75,  # High connection count
        failure_occurred=False
    )

    predictions = await engine.predict_failures(test_data)

    print(f"🎯 Generated {len(predictions)} predictions")

    for i, prediction in enumerate(predictions, 1):
        print(f"\nPrediction {i}:")
        print(f"  Failure Type: {prediction.failure_type.value}")
        print(f"  Probability: {prediction.probability:.2f}")
        print(f"  Predicted Time: {prediction.predicted_time}")
        print(f"  Confidence: {prediction.confidence:.2f}")
        print(f"  Model Used: {prediction.model_used.value}")
        print(f"  Preventive Actions: {prediction.preventive_actions}")

    # Test preventive actions
    if predictions:
        print("\n🛠️  Testing preventive actions...")
        actions = await engine.trigger_preventive_actions(predictions)
        print(f"✅ Triggered {len(actions)} preventive actions: {actions}")

    print("\n🎉 Predictive maintenance test completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_predictive_maintenance())