#!/usr/bin/env python3
"""
AstraGuard AI REST API Usage Examples

Examples of how to interact with the REST API programmatically.
"""

import requests
import json
from datetime import datetime


# Base URL (adjust if running on different host/port)
BASE_URL = "http://localhost:8000"


def example_health_check():
    """Example: Check API health."""
    print("\n=== Health Check ===")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")


def example_submit_telemetry():
    """Example: Submit single telemetry point."""
    print("\n=== Submit Telemetry ===")

    telemetry = {
        "voltage": 7.2,
        "temperature": 35.5,
        "gyro": 0.08,
        "current": 1.5,
        "wheel_speed": 4200
    }

    response = requests.post(
        f"{BASE_URL}/api/v1/telemetry",
        json=telemetry
    )

    print(f"Status Code: {response.status_code}")
    result = response.json()
    print(f"Is Anomaly: {result['is_anomaly']}")
    print(f"Anomaly Score: {result['anomaly_score']:.3f}")
    print(f"Anomaly Type: {result['anomaly_type']}")
    print(f"Recommended Action: {result['recommended_action']}")
    print(f"Reasoning: {result['reasoning']}")


def example_submit_anomalous_telemetry():
    """Example: Submit anomalous telemetry."""
    print("\n=== Submit Anomalous Telemetry ===")

    # Low voltage + high temperature = anomaly
    telemetry = {
        "voltage": 6.5,  # Below threshold
        "temperature": 50.0,  # High temperature
        "gyro": 0.2,  # High gyro
        "current": 2.0,
        "wheel_speed": 5000
    }

    response = requests.post(
        f"{BASE_URL}/api/v1/telemetry",
        json=telemetry
    )

    result = response.json()
    print(f"Is Anomaly: {result['is_anomaly']}")
    print(f"Anomaly Type: {result['anomaly_type']}")
    print(f"Severity: {result['severity_level']} ({result['severity_score']:.2f})")
    print(f"Escalate to Safe Mode: {result['should_escalate_to_safe_mode']}")
    print(f"Recommended Action: {result['recommended_action']}")
    print(f"Allowed Actions: {', '.join(result['allowed_actions'])}")
    print(f"Reasoning: {result['reasoning']}")


def example_batch_telemetry():
    """Example: Submit batch of telemetry points."""
    print("\n=== Batch Telemetry Submission ===")

    batch = {
        "telemetry": [
            {"voltage": 8.0, "temperature": 25.0, "gyro": 0.01},
            {"voltage": 7.5, "temperature": 30.0, "gyro": 0.02},
            {"voltage": 6.5, "temperature": 50.0, "gyro": 0.2},  # Anomaly
            {"voltage": 8.2, "temperature": 28.0, "gyro": 0.015},
        ]
    }

    response = requests.post(
        f"{BASE_URL}/api/v1/telemetry/batch",
        json=batch
    )

    result = response.json()
    print(f"Total Processed: {result['total_processed']}")
    print(f"Anomalies Detected: {result['anomalies_detected']}")
    print("\nResults:")
    for i, r in enumerate(result['results']):
        print(f"  {i+1}. Anomaly: {r['is_anomaly']}, Type: {r['anomaly_type']}, Score: {r['anomaly_score']:.3f}")


def example_get_system_status():
    """Example: Get system status."""
    print("\n=== System Status ===")

    response = requests.get(f"{BASE_URL}/api/v1/status")
    result = response.json()

    print(f"Overall Status: {result['status']}")
    print(f"Mission Phase: {result['mission_phase']}")
    print(f"Uptime: {result['uptime_seconds']:.2f} seconds")
    print(f"Components:")
    for name, health in result['components'].items():
        print(f"  - {name}: {health.get('status', 'UNKNOWN')}")


def example_get_phase():
    """Example: Get current mission phase."""
    print("\n=== Current Mission Phase ===")

    response = requests.get(f"{BASE_URL}/api/v1/phase")
    result = response.json()

    print(f"Phase: {result['phase']}")
    print(f"Description: {result['description']}")
    print(f"Allowed Actions: {', '.join(result['constraints']['allowed_actions'])}")
    print(f"Forbidden Actions: {', '.join(result['constraints']['forbidden_actions'])}")
    print(f"Threshold Multiplier: {result['constraints']['threshold_multiplier']}x")


def example_update_phase():
    """Example: Update mission phase."""
    print("\n=== Update Mission Phase ===")

    # Transition to SAFE_MODE (force=True for guaranteed transition)
    request = {
        "phase": "SAFE_MODE",
        "force": True
    }

    response = requests.post(
        f"{BASE_URL}/api/v1/phase",
        json=request
    )

    result = response.json()
    print(f"Success: {result['success']}")
    print(f"Previous Phase: {result['previous_phase']}")
    print(f"New Phase: {result['new_phase']}")
    print(f"Message: {result['message']}")


def example_get_memory_stats():
    """Example: Get memory store statistics."""
    print("\n=== Memory Statistics ===")

    response = requests.get(f"{BASE_URL}/api/v1/memory/stats")
    result = response.json()

    print(f"Total Events: {result['total_events']}")
    print(f"Critical Events: {result['critical_events']}")
    print(f"Average Age: {result['avg_age_hours']:.2f} hours")
    print(f"Max Recurrence: {result['max_recurrence']}")


def example_get_anomaly_history():
    """Example: Get anomaly history."""
    print("\n=== Anomaly History ===")

    # Query with limit
    response = requests.get(
        f"{BASE_URL}/api/v1/history/anomalies",
        params={"limit": 5}
    )

    result = response.json()
    print(f"Total Anomalies: {result['count']}")
    print(f"\nLast {min(5, result['count'])} Anomalies:")
    for anomaly in result['anomalies']:
        print(f"  - {anomaly['timestamp']}: {anomaly['anomaly_type']} "
              f"(severity: {anomaly['severity_score']:.2f}, "
              f"action: {anomaly['recommended_action']})")


def example_filter_anomaly_history():
    """Example: Filter anomaly history by severity."""
    print("\n=== Filtered Anomaly History (High Severity) ===")

    response = requests.get(
        f"{BASE_URL}/api/v1/history/anomalies",
        params={
            "limit": 10,
            "severity_min": 0.7  # Only high severity
        }
    )

    result = response.json()
    print(f"High Severity Anomalies: {result['count']}")
    for anomaly in result['anomalies']:
        print(f"  - {anomaly['anomaly_type']}: {anomaly['severity_score']:.2f}")


def example_integration_workflow():
    """Example: Complete integration workflow."""
    print("\n=== Complete Integration Workflow ===")

    # 1. Check health
    print("\n1. Checking API health...")
    health = requests.get(f"{BASE_URL}/health").json()
    print(f"   API Status: {health['status']}")

    # 2. Get current phase
    print("\n2. Getting current mission phase...")
    phase = requests.get(f"{BASE_URL}/api/v1/phase").json()
    print(f"   Current Phase: {phase['phase']}")

    # 3. Submit telemetry
    print("\n3. Submitting telemetry...")
    telemetry = {
        "voltage": 6.0,
        "temperature": 55.0,
        "gyro": 0.3
    }
    detection = requests.post(
        f"{BASE_URL}/api/v1/telemetry",
        json=telemetry
    ).json()
    print(f"   Anomaly Detected: {detection['is_anomaly']}")
    print(f"   Recommended Action: {detection['recommended_action']}")

    # 4. Check updated phase (if escalated)
    print("\n4. Checking if phase changed...")
    new_phase = requests.get(f"{BASE_URL}/api/v1/phase").json()
    print(f"   New Phase: {new_phase['phase']}")

    # 5. Get anomaly history
    print("\n5. Retrieving anomaly history...")
    history = requests.get(
        f"{BASE_URL}/api/v1/history/anomalies",
        params={"limit": 3}
    ).json()
    print(f"   Total Anomalies in History: {history['count']}")

    # 6. Get memory stats
    print("\n6. Getting memory statistics...")
    memory = requests.get(f"{BASE_URL}/api/v1/memory/stats").json()
    print(f"   Events in Memory: {memory['total_events']}")


def main():
    """Run all examples."""
    print("=" * 70)
    print("AstraGuard AI REST API Usage Examples")
    print("=" * 70)
    print(f"\nBase URL: {BASE_URL}")
    print("\nMake sure the API server is running:")
    print("  python run_api.py")
    print("  OR")
    print("  python cli.py api")
    print("\n" + "=" * 70)

    try:
        # Basic examples
        example_health_check()
        example_submit_telemetry()
        example_submit_anomalous_telemetry()
        example_batch_telemetry()

        # Status and phase examples
        example_get_system_status()
        example_get_phase()
        # example_update_phase()  # Commented to avoid changing phase

        # Memory and history examples
        example_get_memory_stats()
        example_get_anomaly_history()
        example_filter_anomaly_history()

        # Integration workflow
        example_integration_workflow()

        print("\n" + "=" * 70)
        print("All examples completed successfully!")
        print("=" * 70)

    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Could not connect to API server.")
        print("Make sure the server is running on", BASE_URL)
        print("\nStart the server with:")
        print("  python run_api.py")
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")


if __name__ == "__main__":
    main()
