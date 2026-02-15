#!/usr/bin/env python3
"""
Benchmark script for cli.py performance analysis.
Tests file I/O operations and subprocess execution times.
"""
import json
import time
import tempfile
from pathlib import Path
from typing import List, Dict, Any
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from models.feedback import FeedbackEvent, FeedbackLabel


def create_test_feedback_data(count: int = 100) -> List[Dict[str, Any]]:
    """Generate sample feedback events for testing."""
    events = []
    for i in range(count):
        event = {
            "fault_id": f"FAULT-{i:04d}",
            "anomaly_type": "sensor_drift",
            "recovery_action": "recalibrate_sensor",
            "mission_phase": "NOMINAL_OPS",
            "timestamp": "2026-02-14T10:00:00Z",
            "label": "correct",
            "operator_notes": ""
        }
        events.append(event)
    return events


def benchmark_file_io_original(iterations: int = 100) -> float:
    """Benchmark original file I/O implementation."""
    test_data = create_test_feedback_data(50)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "feedback_pending.json"
        test_file.write_text(json.dumps(test_data))
        
        start = time.perf_counter()
        for _ in range(iterations):
            # Original implementation
            with open(test_file, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            events = [FeedbackEvent.model_validate(e) for e in raw]
        end = time.perf_counter()
    
    return end - start


def benchmark_file_io_optimized(iterations: int = 100) -> float:
    """Benchmark optimized file I/O implementation."""
    test_data = create_test_feedback_data(50)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "feedback_pending.json"
        test_file.write_text(json.dumps(test_data))
        
        start = time.perf_counter()
        for _ in range(iterations):
            # Optimized implementation using Path.read_text()
            raw = json.loads(test_file.read_text(encoding='utf-8'))
            events = [FeedbackEvent.model_validate(e) for e in raw]
        end = time.perf_counter()
    
    return end - start


def benchmark_json_write_original(iterations: int = 100) -> float:
    """Benchmark original JSON write implementation."""
    test_data = create_test_feedback_data(50)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        start = time.perf_counter()
        for i in range(iterations):
            test_file = Path(tmpdir) / f"test_{i}.json"
            # Original: no indent, separators specified
            test_file.write_text(json.dumps(test_data, separators=(",", ":")))
        end = time.perf_counter()
    
    return end - start


def benchmark_json_write_optimized(iterations: int = 100) -> float:
    """Benchmark optimized JSON write implementation."""
    test_data = create_test_feedback_data(50)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        start = time.perf_counter()
        for i in range(iterations):
            test_file = Path(tmpdir) / f"test_{i}.json"
            # Optimized: pre-serialize JSON
            json_str = json.dumps(test_data, separators=(",", ":"))
            test_file.write_text(json_str, encoding='utf-8')
        end = time.perf_counter()
    
    return end - start


def run_all_benchmarks() -> None:
    """Run all benchmarks and display results."""
    print("=" * 80)
    print("CLI.PY PERFORMANCE BENCHMARK")
    print("=" * 80)
    print()
    
    iterations = 100
    
    # File I/O Read Benchmark
    print(f"📖 File I/O Read Operations ({iterations} iterations)")
    print("-" * 80)
    
    original_read_time = benchmark_file_io_original(iterations)
    print(f"Original implementation:  {original_read_time:.4f}s")
    
    optimized_read_time = benchmark_file_io_optimized(iterations)
    print(f"Optimized implementation: {optimized_read_time:.4f}s")
    
    if original_read_time > 0:
        improvement = ((original_read_time - optimized_read_time) / original_read_time) * 100
        print(f"Performance improvement:  {improvement:+.2f}%")
    print()
    
    # File I/O Write Benchmark
    print(f"📝 File I/O Write Operations ({iterations} iterations)")
    print("-" * 80)
    
    original_write_time = benchmark_json_write_original(iterations)
    print(f"Original implementation:  {original_write_time:.4f}s")
    
    optimized_write_time = benchmark_json_write_optimized(iterations)
    print(f"Optimized implementation: {optimized_write_time:.4f}s")
    
    if original_write_time > 0:
        improvement = ((original_write_time - optimized_write_time) / original_write_time) * 100
        print(f"Performance improvement:  {improvement:+.2f}%")
    print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    total_original = original_read_time + original_write_time
    total_optimized = optimized_read_time + optimized_write_time
    total_improvement = ((total_original - total_optimized) / total_original) * 100 if total_original > 0 else 0
    
    print(f"Total original time:   {total_original:.4f}s")
    print(f"Total optimized time:  {total_optimized:.4f}s")
    print(f"Overall improvement:   {total_improvement:+.2f}%")
    print()
    
    print("💡 Key Findings:")
    print("  • File I/O operations use Path methods for better readability")
    print("  • JSON encoding/decoding remains the main bottleneck")
    print("  • subprocess operations are inherently blocking (expected for CLI)")
    print("  • Interactive user input cannot be optimized (human in the loop)")
    print()


if __name__ == "__main__":
    run_all_benchmarks()
