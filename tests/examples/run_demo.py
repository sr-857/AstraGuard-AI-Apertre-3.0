#!/usr/bin/env python3
"""
AstraGuard Demo - Streaming Anomaly Detection with Adaptive Memory

This demo shows the complete system in action:
1. Streaming telemetry data
2. Anomaly detection
3. Memory-aware decision making
4. Automated response

Run: python examples/run_demo.py
"""

import sys
import os
import time
import numpy as np
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from memory_engine import AdaptiveMemoryStore, RecurrenceScorer


def generate_telemetry_stream():
    """Simulate streaming telemetry data"""
    while True:
        # Normal telemetry
        voltage = 8.0 + np.random.normal(0, 0.1)
        temperature = 25.0 + np.random.normal(0, 2.0)
        gyro = 0.0 + np.random.normal(0, 0.01)

        # Occasionally inject anomalies
        if np.random.random() < 0.1:  # 10% chance
            fault_type = np.random.choice(["voltage", "thermal", "attitude"])
            if fault_type == "voltage":
                voltage = 7.0  # Below threshold
            elif fault_type == "thermal":
                temperature = 35.0  # Above threshold
            else:
                gyro = 0.08  # Above threshold

        yield {
            "timestamp": datetime.now(),
            "voltage": voltage,
            "temperature": temperature,
            "gyro": gyro,
        }

        time.sleep(0.5)  # 2 Hz


def detect_anomaly(data):
    """Simple threshold-based anomaly detection"""
    is_anomalous = False
    fault_type = "normal"
    severity = 0.0

    if data["voltage"] < 7.3:
        is_anomalous = True
        fault_type = "power_fault"
        severity = 0.8
    elif data["temperature"] > 32.0:
        is_anomalous = True
        fault_type = "thermal_fault"
        severity = 0.7
    elif abs(data["gyro"]) > 0.05:
        is_anomalous = True
        fault_type = "attitude_fault"
        severity = 0.6

    return is_anomalous, fault_type, severity


def create_embedding(data):
    """Create simple embedding from telemetry"""
    # Normalize values
    voltage_norm = (data["voltage"] - 7.0) / 2.0
    temp_norm = (data["temperature"] - 20.0) / 20.0
    gyro_norm = data["gyro"] / 0.1

    # Create 384-dim embedding (simple repetition for demo)
    base = np.array([voltage_norm, temp_norm, gyro_norm])
    embedding = np.tile(base, 128)  # 384 dimensions

    return embedding


def run_demo():
    """Run the complete demo"""
    print("=" * 70)
    print("AstraGuard Demo - Streaming Anomaly Detection with Adaptive Memory")
    print("=" * 70)
    print("\nInitializing system...")

    # Initialize components
    memory = AdaptiveMemoryStore(decay_lambda=0.1, max_capacity=1000)
    scorer = RecurrenceScorer(resonance_factor=0.3)

    print("✓ Memory engine initialized")
    print("✓ Recurrence scorer ready")
    print("\nStarting telemetry stream...\n")

    stream = generate_telemetry_stream()
    event_count = 0
    anomaly_count = 0

    try:
        for data in stream:
            event_count += 1

            # Detect anomaly
            is_anomalous, fault_type, severity = detect_anomaly(data)

            if is_anomalous:
                anomaly_count += 1

                # Create embedding
                embedding = create_embedding(data)

                # Check memory for similar incidents
                similar = memory.retrieve(embedding, top_k=3)

                # Calculate resonance score
                metadata = {
                    "severity": severity,
                    "type": fault_type,
                    "timestamp": data["timestamp"].timestamp(),
                }
                resonance = scorer.score_event(metadata, [s[1] for s in similar])

                # Store in memory
                memory.write(embedding, metadata)

                # Display detection
                print(
                    f"\n[{data['timestamp'].strftime('%H:%M:%S')}] ⚠️  ANOMALY DETECTED"
                )
                print(f"  Type: {fault_type}")
                print(f"  Severity: {severity:.2f}")
                print(f"  Resonance: {resonance:.2f}")
                print(f"  Similar incidents: {len(similar)}")

                if similar:
                    print(f"  Memory match score: {similar[0][0]:.2f}")

                # Get memory stats
                stats = memory.get_stats()
                print(
                    f"\n  Memory: {stats['total_events']} events, "
                    f"{stats['critical_events']} critical"
                )

            # Progress indicator
            if event_count % 10 == 0:
                print(
                    f"\r[{event_count} events processed, "
                    f"{anomaly_count} anomalies detected]",
                    end="",
                    flush=True,
                )

            # Run for 50 events then exit
            if event_count >= 50:
                break

    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")

    print("\n\n" + "=" * 70)
    print("Demo Complete")
    print("=" * 70)
    print(f"\nTotal events processed: {event_count}")
    print(f"Anomalies detected: {anomaly_count}")
    print(f"Detection rate: {anomaly_count/event_count*100:.1f}%")

    stats = memory.get_stats()
    print(f"\nMemory statistics:")
    print(f"  Total events: {stats['total_events']}")
    print(f"  Critical events: {stats['critical_events']}")
    print(f"  Max recurrence: {stats['max_recurrence']}")

    print("\n✓ System ran successfully with no errors!")


if __name__ == "__main__":
    run_demo()
