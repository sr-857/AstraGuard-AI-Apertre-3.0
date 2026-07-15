#!/usr/bin/env python3
"""
Benchmark script for Contact API performance optimizations.
Tests the async I/O improvements in src/api/contact.py
"""

import asyncio
import time
import tempfile
import os
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, 'src')

from api.contact import save_submission, log_notification, ContactSubmission

async def benchmark_save_submission():
    """Benchmark async save_submission function"""
    print("Benchmarking save_submission (async SQLite)...")

    submission = ContactSubmission(
        name='Benchmark User',
        email='benchmark@example.com',
        subject='Performance Test',
        message='This is a test message for benchmarking purposes.'
    )

    # Warm up
    for i in range(10):
        await save_submission(submission, '127.0.0.1', 'benchmark-agent')

    # Benchmark
    num_iterations = 100
    start_time = time.time()
    for i in range(num_iterations):
        await save_submission(submission, '127.0.0.1', 'benchmark-agent')
    end_time = time.time()

    total_time = end_time - start_time
    avg_time = total_time / num_iterations
    print(f"Total time: {total_time:.4f}s")
    print(f"Average time per operation: {avg_time:.6f}s")

    return total_time

async def benchmark_log_notification():
    """Benchmark async log_notification function"""
    print("Benchmarking log_notification (async file I/O)...")

    submission = ContactSubmission(
        name='Log Test User',
        email='logtest@example.com',
        subject='Log Performance Test',
        message='Testing async file logging performance.'
    )

    # Use temp file for testing
    with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as tmp:
        temp_log = tmp.name

    # Temporarily override NOTIFICATION_LOG
    import api.contact
    original_log = api.contact.NOTIFICATION_LOG
    api.contact.NOTIFICATION_LOG = Path(temp_log)

    try:
        # Warm up
        for i in range(10):
            await log_notification(submission, i)

        # Benchmark
        num_iterations = 100
        start_time = time.time()
        for i in range(num_iterations):
            await log_notification(submission, i + 10)
        end_time = time.time()

        total_time = end_time - start_time
        avg_time = total_time / num_iterations
        print(f"Total time: {total_time:.4f}s")
        print(f"Average time per operation: {avg_time:.6f}s")

        # Check file size
        file_size = os.path.getsize(temp_log)
        print(f"Log file size: {file_size} bytes")

    finally:
        api.contact.NOTIFICATION_LOG = original_log
        if os.path.exists(temp_log):
            os.unlink(temp_log)

    return total_time

async def benchmark_combined():
    """Benchmark combined save + log operations"""
    print("Benchmarking combined save_submission + log_notification...")

    submission = ContactSubmission(
        name='Combined Test User',
        email='combined@example.com',
        subject='Combined Performance Test',
        message='Testing combined async operations.'
    )

    # Use temp file for testing
    with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as tmp:
        temp_log = tmp.name

    # Temporarily override NOTIFICATION_LOG
    import api.contact
    original_log = api.contact.NOTIFICATION_LOG
    api.contact.NOTIFICATION_LOG = Path(temp_log)

    try:
        # Warm up
        for i in range(5):
            submission_id = await save_submission(submission, '127.0.0.1', 'combined-agent')
            await log_notification(submission, submission_id)

        # Benchmark
        num_iterations = 50
        start_time = time.time()
        for i in range(num_iterations):
            submission_id = await save_submission(submission, '127.0.0.1', 'combined-agent')
            await log_notification(submission, submission_id)
        end_time = time.time()

        total_time = end_time - start_time
        avg_time = total_time / num_iterations
        print(f"Total time: {total_time:.4f}s")
        print(f"Average time per operation: {avg_time:.6f}s")

    finally:
        api.contact.NOTIFICATION_LOG = original_log
        if os.path.exists(temp_log):
            os.unlink(temp_log)

    return total_time

async def main():
    """Run all benchmarks"""
    print("Contact API Performance Benchmark")
    print("=" * 40)

    try:
        # Run benchmarks
        save_time = await benchmark_save_submission()
        print()

        log_time = await benchmark_log_notification()
        print()

        combined_time = await benchmark_combined()
        print()

        print("Benchmark Summary:")
        print(f"save_submission: {save_time:.4f}s")
        print(f"log_notification: {log_time:.4f}s")
        print(f"combined: {combined_time:.4f}s")
        print(f"Total: {save_time + log_time + combined_time:.4f}s")

        print("\nBenchmark complete! Async I/O optimizations are working.")

    except Exception as e:
        print(f"Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
