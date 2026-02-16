"""Benchmark script for accuracy.py performance improvements."""

import time
import random
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from astraguard.hil.metrics.accuracy import AccuracyCollector


def generate_test_data(num_satellites: int, num_events: int, num_classifications: int):
    """Generate test data for benchmarking."""
    collector = AccuracyCollector()
    
    satellite_ids = [f"SAT-{i:03d}" for i in range(num_satellites)]
    fault_types = ["power_failure", "sensor_drift", "attitude_error", "communication_loss"]
    
    # Generate ground truth events
    for _ in range(num_events):
        sat_id = random.choice(satellite_ids)
        timestamp = random.uniform(0, 1000)
        fault_type = random.choice([None] + fault_types)  # Include nominal
        collector.record_ground_truth(sat_id, timestamp, fault_type)
    
    # Generate classifications
    for _ in range(num_classifications):
        sat_id = random.choice(satellite_ids)
        timestamp = random.uniform(0, 1000)
        predicted_fault = random.choice([None] + fault_types)
        confidence = random.uniform(0.5, 1.0)
        is_correct = random.choice([True, False])
        collector.record_agent_classification(
            sat_id, timestamp, predicted_fault, confidence, is_correct
        )
    
    return collector


def benchmark_operation(name: str, operation, iterations: int = 5):
    """Benchmark a specific operation."""
    times = []
    
    for i in range(iterations):
        start = time.perf_counter()
        result = operation()
        end = time.perf_counter()
        times.append(end - start)
    
    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)
    
    print(f"\n{name}:")
    print(f"  Average: {avg_time*1000:.2f} ms")
    print(f"  Min:     {min_time*1000:.2f} ms")
    print(f"  Max:     {max_time*1000:.2f} ms")
    
    return avg_time


def main():
    """Run performance benchmarks."""
    print("=" * 70)
    print("Accuracy.py Performance Benchmark")
    print("=" * 70)
    
    # Test with different data sizes
    test_configs = [
        (10, 100, 500),      # Small
        (50, 500, 2500),     # Medium
        (100, 1000, 5000),   # Large
    ]
    
    for num_sats, num_events, num_classifications in test_configs:
        print(f"\n{'='*70}")
        print(f"Test Configuration:")
        print(f"  Satellites: {num_sats}")
        print(f"  Ground Truth Events: {num_events}")
        print(f"  Classifications: {num_classifications}")
        print(f"{'='*70}")
        
        collector = generate_test_data(num_sats, num_events, num_classifications)
        
        # Benchmark different operations
        benchmark_operation(
            "get_accuracy_stats()",
            lambda: collector.get_accuracy_stats(),
            iterations=10
        )
        
        benchmark_operation(
            "get_stats_by_satellite()",
            lambda: collector.get_stats_by_satellite(),
            iterations=10
        )
        
        benchmark_operation(
            "get_confusion_matrix()",
            lambda: collector.get_confusion_matrix(),
            iterations=10
        )
        
        benchmark_operation(
            "get_summary() [Full Report]",
            lambda: collector.get_summary(),
            iterations=5
        )
    
    print(f"\n{'='*70}")
    print("Benchmark Complete!")
    print("=" * 70)
    print("\nKey Optimizations Applied:")
    print("  ✓ Removed duplicate logger declarations")
    print("  ✓ Fixed duplicate _find_ground_truth_fault method")
    print("  ✓ Optimized _calculate_per_fault_stats() to O(n) from O(n*m)")
    print("  ✓ Optimized get_stats_by_satellite() with single-pass iteration")
    print("  ✓ Fixed indentation errors for proper exception handling")
    print("  ✓ Using defaultdict for efficient data aggregation")
    print("=" * 70)


if __name__ == "__main__":
    main()
