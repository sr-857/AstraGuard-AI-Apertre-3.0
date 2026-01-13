# Profiling & Benchmarks Guide

This guide explains how to profile and benchmark AstraGuard AI backend components for performance analysis and regression detection.

## Quick Start

### Run Microbenchmarks

```bash
# Run all benchmarks
python tools/benchmarks/run_microbench.py

# Run specific benchmarks
python tools/benchmarks/run_microbench.py --pattern "bench_fallback*"

# Compare against baseline
python tools/benchmarks/run_microbench.py --compare benchmarks/baselines/initial.json
```

### Profile a Module

```bash
# Profile with pyinstrument (recommended for quick analysis)
python tools/benchmarks/run_profile.py --target backend.fallback.manager

# Profile with cProfile (for detailed deterministic profiling)
python tools/benchmarks/run_profile.py --profiler cprofile --target backend.fallback.manager

# Profile memory usage
python tools/benchmarks/run_profile.py --profiler memory --target backend.cache.in_memory
```

### Run End-to-End Benchmarks

```bash
# Start the API server first
uvicorn backend.main:app --host 0.0.0.0 --port 8000

# In another terminal, run E2E benchmarks
python tools/benchmarks/run_e2e_bench.py --url http://localhost:8000 -c 10 -d 30
```

---

## Profiling Toolkit

### `run_profile.py`

Unified profiler wrapper supporting multiple backends:

| Profiler | Flag | Best For |
|----------|------|----------|
| pyinstrument | `--profiler pyinstrument` | Quick overview, flamegraph-style HTML |
| cProfile | `--profiler cprofile` | Detailed function-level timing |
| memory_profiler | `--profiler memory` | Memory allocation analysis |

**Output Directory:** `profiling_output/`

#### Example: Profile Fallback Cascade

```bash
python tools/benchmarks/run_profile.py \
    --target backend.fallback.manager \
    --profiler pyinstrument \
    --output fallback_cascade.html
```

Then open `profiling_output/fallback_cascade.html` in your browser for an interactive flamegraph.

#### Example: Profile with cProfile + snakeviz

```bash
python tools/benchmarks/run_profile.py \
    --target backend.safe_condition_parser \
    --profiler cprofile

# View with snakeviz
pip install snakeviz
python -m snakeviz profiling_output/backend_safe_condition_parser_*.prof
```

---

## Microbenchmarks

Microbenchmarks use [pytest-benchmark](https://pytest-benchmark.readthedocs.io/) to measure function performance.

### Available Benchmarks

| File | Target | Description |
|------|--------|-------------|
| `benchmarks/bench_fallback.py` | `FallbackManager.cascade()` | Mode transition decisions |
| `benchmarks/bench_orchestrator.py` | `RecoveryOrchestrator` | Recovery cycle evaluation |
| `benchmarks/bench_condition_parser.py` | `evaluate()` | Condition expression parsing |
| `benchmarks/cache_benchmarks.py` | `InMemoryLRUCache` | Cache operations |

### Running Benchmarks

```bash
# Run all benchmarks with verbose output
pytest benchmarks/ --benchmark-only -v

# Run with comparison to baseline
pytest benchmarks/ --benchmark-only --benchmark-compare=benchmarks/baselines/initial.json

# Save results to JSON
pytest benchmarks/ --benchmark-only --benchmark-json=results.json
```

### Writing New Benchmarks

```python
import pytest
from backend.my_module import my_function

def test_my_function_performance(benchmark):
    """Benchmark my_function with typical inputs."""
    
    def run_function():
        return my_function(input_data)
    
    result = benchmark(run_function)
    assert result is not None  # Validate result
```

---

## Baseline Management

### Creating a Baseline

After running benchmarks on a stable version:

```bash
python tools/benchmarks/run_microbench.py --save-baseline
```

This saves results to `benchmarks/baselines/initial.json`.

### Updating Baselines

When performance improves intentionally (optimization merged):

1. Run benchmarks on the new code
2. Verify improvements are real and stable
3. Save new baseline:
   ```bash
   python tools/benchmarks/run_microbench.py --save-baseline
   ```
4. Commit the updated `benchmarks/baselines/initial.json`

### Regression Thresholds

Configured in `tools/benchmarks/bench_config.yaml`:

```yaml
regression:
  warning_threshold: 10  # 10% slowdown triggers warning
  failure_threshold: 20  # 20% slowdown triggers failure
```

---

## CI Integration

The `bench-perf.yml` workflow runs automatically on:
- Push to `main` or `develop`
- Pull requests to `main` or `develop`

### What CI Does

1. **Runs microbenchmarks** with pytest-benchmark
2. **Compares against baseline** in `benchmarks/baselines/initial.json`
3. **Uploads results** as artifacts
4. **Comments on PRs** if regression detected (non-blocking)

### Viewing Results

1. Go to the Actions tab on GitHub
2. Select the "Performance Benchmarks" workflow
3. Download the `benchmark-results` artifact

---

## Interpreting Results

### Flamegraph (pyinstrument)

- **Width** = Time spent in function
- **Depth** = Call stack depth
- **Color** = Function type (your code vs library)

Look for wide bars — these are the hot paths.

### cProfile Stats

Key columns:
- `tottime`: Time spent in function (excluding children)
- `cumtime`: Time spent in function (including children)
- `ncalls`: Number of calls

Focus on high `tottime` for optimization targets.

### Memory Profile

- `Peak Memory`: Maximum memory used
- High peak with quick drop = large temporary allocations

---

## Best Practices

### Reducing Benchmark Noise

1. **Close other applications** during local benchmarks
2. **Use warmup** (`--benchmark-warmup=on`)
3. **Multiple rounds** (`--benchmark-min-rounds=10`)
4. **Seed random values** in test data

### When to Rebaseline

- After confirmed performance improvements
- After changing benchmark methodology
- After major refactoring that changes hot paths

### Performance PR Guidelines

1. Include benchmark results in PR description
2. Compare before/after for changed code paths
3. Explain any intentional regressions (e.g., added safety checks)

---

## Troubleshooting

### "Module not found" errors

Ensure you're running from the project root:

```bash
cd /path/to/AstraGuard-AI
python tools/benchmarks/run_profile.py ...
```

### Benchmarks are flaky

Increase warmup and rounds:

```bash
pytest benchmarks/ --benchmark-warmup=on --benchmark-min-rounds=20
```

### Memory profiler is slow

Memory profiling adds overhead. Use sparingly and with smaller inputs.
