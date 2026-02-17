# Performance Benchmarking Guide

This document provides instructions on how to run and extend the performance benchmark suite for AstraGuard AI.

## Overview

The benchmark suite is designed to measure the performance of core system components, including:
- **Memory Engine**: `AdaptiveMemoryStore` operations (write, retrieve, prune).
- **Swarm Coordination**: `RequestBatcher` throughput (add, flush).
- **Database**: Connection pooling and query latency.

## Prerequisites

Ensure you have installed the project dependencies, including `pytest-benchmark`:

```bash
pip install -r Requirements.txt
```

## Running Benchmarks

### Run All Benchmarks

To execute all benchmarks and view the report:

```bash
pytest -m benchmark
```

To run *only* the benchmarks (skipping standard tests):

```bash
pytest -m benchmark --benchmark-only
```

### Run Specific Benchmarks

To target a specific component:

```bash
# Memory Engine
pytest benchmarks/test_memory_benchmark.py

# Swarm/Network
pytest benchmarks/test_swarm_benchmark.py

# Database
pytest benchmarks/test_db_benchmark.py
```

### Advanced Options

`pytest-benchmark` supports various options for comparing results and exporting data:

```bash
# Compare with previous run
pytest -m benchmark --benchmark-compare

# Export results to JSON
pytest -m benchmark --benchmark-json=results.json
```

## Interpreting Results

The output provides statistical data for each benchmark:

- **Min**: The minimum execution time (best case).
- **Max**: The maximum execution time (worst case).
- **Mean**: The average execution time.
- **StdDev**: Standard deviation (stability of the measurement).
- **OPS**: Operations Per Second (throughput).

### Key Metrics to Watch
- **Memory Write**: Should be < 10ms for typical loads.
- **Swarm Add**: Should be extremely fast (< 1ms) as it's an in-memory append.
- **DB Connection**: Should be fast (< 1ms) when pooled.

## Adding New Benchmarks

To add a new benchmark, create a test file in `benchmarks/` and use the `benchmark` fixture.

### Synchronous Example

```python
def test_cpu_bound_operation(benchmark):
    def workload():
        # Your code here
        pass

    benchmark(workload)
```

### Asynchronous Example

For async code, use the event loop to run the workload:

```python
import asyncio

def test_async_operation(benchmark, event_loop):
    async def workload():
        # Your async code here
        pass

    def run_wrapper():
        event_loop.run_until_complete(workload())

    benchmark(run_wrapper)
```

## CI Integration

Benchmarks are run automatically in CI via `.github/workflows/benchmark.yml`.
Failures or significant performance regressions may be flagged.
