"""
Benchmark for PhaseAwareAnomalyHandler performance.

This script benchmarks the handler's performance, particularly focusing on:
1. _update_recurrence_tracking - the main bottleneck
2. _record_anomaly_for_reporting - file I/O
3. Overall handle_anomaly latency
"""

import time
import random
import os
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from anomaly_agent.phase_aware_handler import PhaseAwareAnomalyHandler
from state_machine.state_engine import StateMachine
from config.mission_phase_policy_loader import MissionPhasePolicyLoader




def create_test_handler() -> PhaseAwareAnomalyHandler:
    """Create a test handler instance."""
    state_machine = StateMachine()
    policy_loader = MissionPhasePolicyLoader()
    return PhaseAwareAnomalyHandler(
        state_machine=state_machine,
        policy_loader=policy_loader,
        enable_recurrence_tracking=True
    )


def benchmark_handle_anomaly(num_iterations: int = 100) -> Dict[str, float]:
    """
    Benchmark the handle_anomaly method.
    
    Returns dict with timing metrics.
    """
    handler = create_test_handler()
    handler.clear_anomaly_history()
    
    anomaly_types = ['power_fault', 'thermal_fault', 'attitude_fault', 'communication_loss']
    
    latencies = []
    
    for i in range(num_iterations):
        anomaly_type = random.choice(anomaly_types)
        severity = random.uniform(0.3, 0.95)
        confidence = random.uniform(0.6, 0.99)
        
        start_time = time.perf_counter()
        decision = handler.handle_anomaly(
            anomaly_type=anomaly_type,
            severity_score=severity,
            confidence=confidence,
            anomaly_metadata={"source": "benchmark", "iteration": i}
        )
        latency = time.perf_counter() - start_time
        
        latencies.append(latency * 1000)  # Convert to ms
    
    return {
        'iterations': num_iterations,
        'avg_latency_ms': sum(latencies) / len(latencies),
        'min_latency_ms': min(latencies),
        'max_latency_ms': max(latencies),
        'total_time_ms': sum(latencies)
    }


def benchmark_recurrence_tracking(num_history_items: int, num_queries: int = 100) -> Dict[str, float]:
    """
    Benchmark the _update_recurrence_tracking method with varying history sizes.
    
    This shows how performance degrades as history grows.
    """
    handler = create_test_handler()
    handler.clear_anomaly_history()
    
    # Pre-populate history
    for i in range(num_history_items):
        anomaly_type = random.choice(['power_fault', 'thermal_fault'])
        handler.anomaly_history.append(
            (anomaly_type, datetime.now() - timedelta(seconds=random.randint(0, 3600)))
        )
    
    # Benchmark queries
    latencies = []
    for _ in range(num_queries):
        start_time = time.perf_counter()
        handler._update_recurrence_tracking('power_fault')
        latency = time.perf_counter() - start_time
        latencies.append(latency * 1000)  # Convert to ms
    
    return {
        'history_size': num_history_items,
        'num_queries': num_queries,
        'avg_latency_ms': sum(latencies) / len(latencies),
        'min_latency_ms': min(latencies),
        'max_latency_ms': max(latencies)
    }


def benchmark_file_io(num_iterations: int = 50) -> Dict[str, float]:
    """
    Benchmark the _record_anomaly_for_reporting file I/O.
    """
    handler = create_test_handler()
    
    # Create a test decision
    decision = {
        'decision_id': 'TEST_001',
        'anomaly_type': 'power_fault',
        'recommended_action': 'ESCALATE',
        'mission_phase': 'NOMINAL_OPS',
        'timestamp': datetime.now(),
        'detection_confidence': 0.95,
        'severity_score': 0.8
    }
    
    metadata = {'source': 'benchmark'}
    
    latencies = []
    
    for i in range(num_iterations):
        decision['decision_id'] = f'TEST_{i:05d}'
        
        start_time = time.perf_counter()
        handler._record_anomaly_for_reporting(decision, metadata)
        latency = time.perf_counter() - start_time
        
        latencies.append(latency * 1000)  # Convert to ms
    
    # Cleanup
    pending_file = Path("feedback_pending.json")
    if pending_file.exists():
        pending_file.unlink()
    
    return {
        'iterations': num_iterations,
        'avg_latency_ms': sum(latencies) / len(latencies),
        'min_latency_ms': min(latencies),
        'max_latency_ms': max(latencies),
        'total_time_ms': sum(latencies)
    }


def main():
    """Run all benchmarks."""
    print("=" * 60)
    print("PhaseAwareAnomalyHandler Performance Benchmark")
    print("=" * 60)
    
    # Benchmark 1: Overall handle_anomaly
    print("\n1. Benchmarking handle_anomaly (100 iterations)...")
    results = benchmark_handle_anomaly(100)
    print(f"   Average latency: {results['avg_latency_ms']:.3f} ms")
    print(f"   Min latency: {results['min_latency_ms']:.3f} ms")
    print(f"   Max latency: {results['max_latency_ms']:.3f} ms")
    
    # Benchmark 2: Recurrence tracking with varying history sizes
    print("\n2. Benchmarking recurrence tracking with varying history sizes...")
    for history_size in [10, 100, 500, 1000]:
        results = benchmark_recurrence_tracking(history_size, 100)
        print(f"   History size {results['history_size']:4d}: "
              f"avg={results['avg_latency_ms']:.3f} ms, "
              f"max={results['max_latency_ms']:.3f} ms")
    
    # Benchmark 3: File I/O
    print("\n3. Benchmarking file I/O (50 iterations)...")
    results = benchmark_file_io(50)
    print(f"   Average latency: {results['avg_latency_ms']:.3f} ms")
    print(f"   Min latency: {results['min_latency_ms']:.3f} ms")
    print(f"   Max latency: {results['max_latency_ms']:.3f} ms")
    
    print("\n" + "=" * 60)
    print("Benchmark complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
