import time
import tempfile
import os
from src.astraguard.hil.metrics.accuracy import AccuracyCollector

def benchmark_accuracy():
    """Benchmark AccuracyCollector performance before and after optimizations."""
    collector = AccuracyCollector()

    # Generate test data
    num_events = 10000
    num_classifications = 10000
    print(f"Generating {num_events} ground truth events and {num_classifications} classifications...")

    # Generate ground truth events
    for i in range(num_events):
        sat_id = f"SAT{(i % 10) + 1}"
        scenario_time = float(i * 0.1)
        fault_type = f"FAULT{(i % 5) + 1}" if i % 2 == 0 else None
        collector.record_ground_truth(sat_id, scenario_time, fault_type)

    # Generate agent classifications
    for i in range(num_classifications):
        sat_id = f"SAT{(i % 10) + 1}"
        scenario_time = float(i * 0.1)
        predicted_fault = f"FAULT{(i % 5) + 1}" if i % 3 == 0 else None
        confidence = float((i % 100) / 100.0)
        is_correct = (i % 2 == 0)  # Alternate correct/incorrect
        collector.record_agent_classification(sat_id, scenario_time, predicted_fault, confidence, is_correct)

    print(f"Generated {len(collector.ground_truth_events)} events and {len(collector.agent_classifications)} classifications")

    # Benchmark get_accuracy_stats()
    print("Benchmarking get_accuracy_stats()...")
    start_time = time.time()
    stats = collector.get_accuracy_stats()
    stats_time = time.time() - start_time
    print(".4f")

    # Benchmark get_stats_by_satellite()
    print("Benchmarking get_stats_by_satellite()...")
    start_time = time.time()
    sat_stats = collector.get_stats_by_satellite()
    sat_stats_time = time.time() - start_time
    print(".4f")

    # Benchmark get_confusion_matrix()
    print("Benchmarking get_confusion_matrix()...")
    start_time = time.time()
    confusion = collector.get_confusion_matrix()
    confusion_time = time.time() - start_time
    print(".4f")

    # Benchmark export_csv()
    print("Benchmarking export_csv()...")
    with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        start_time = time.time()
        collector.export_csv(tmp_path)
        export_time = time.time() - start_time
        print(".4f")

        # Verify file size
        file_size = os.path.getsize(tmp_path)
        print(f"CSV file size: {file_size} bytes")

    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    # Benchmark get_summary()
    print("Benchmarking get_summary()...")
    start_time = time.time()
    summary = collector.get_summary()
    summary_time = time.time() - start_time
    print(".4f")

    print("\nBenchmark complete!")

if __name__ == "__main__":
    benchmark_accuracy()
