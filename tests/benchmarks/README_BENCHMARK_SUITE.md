# AstraGuard Performance Benchmarking Suite (#709)

Comprehensive performance benchmarking suite that executes all AstraGuard benchmarks, aggregates results, and provides detailed reporting with baseline comparison support.

## Features

✅ **Unified Runner** - Single command to run all benchmarks  
✅ **Multiple Categories** - Storage, ML, Metrics, Swarm, Performance  
✅ **Results Aggregation** - Consolidated reporting across all benchmarks  
✅ **JSON Export** - Machine-readable results for CI/CD integration  
✅ **Baseline Comparison** - Detect performance regressions  
✅ **Quick Mode** - Run subset of critical benchmarks quickly  
✅ **Detailed Reporting** - Console-friendly formatted output  

## Installation

```bash
# Install dependencies
pip install -r src/config/requirements.txt
pip install psutil  # For system info collection
```

## Usage

### Basic Usage

Run all benchmarks:
```bash
python tests/benchmarks/run_benchmark_suite.py
```

### Quick Mode

Run only critical benchmarks (faster):
```bash
python tests/benchmarks/run_benchmark_suite.py --quick
```

### Save Results

Export results to JSON:
```bash
python tests/benchmarks/run_benchmark_suite.py --output results/benchmark_$(date +%Y%m%d).json
```

### Baseline Comparison

Compare against a baseline to detect regressions:
```bash
# First, create a baseline
python tests/benchmarks/run_benchmark_suite.py --save-baseline

# Later, compare new results
python tests/benchmarks/run_benchmark_suite.py --baseline tests/benchmarks/baselines/baseline.json
```

### Custom Regression Threshold

Set custom performance regression threshold (default is 10%):
```bash
python tests/benchmarks/run_benchmark_suite.py --baseline baselines/baseline.json --threshold 15
```

## Benchmark Categories

### Storage
- **Storage Performance** - File I/O and storage operations

### Metrics
- **Latency Collector** - Telemetry latency tracking
- **Metrics Storage** - Metrics persistence and retrieval

### ML (Machine Learning)
- **Anomaly Detector** - ML model inference performance

### Performance
- **Cache Operations** - Caching layer performance
- **State Serialization** - Serialization/deserialization benchmarks

### Swarm
- **Discovery & Heartbeat** - Peer discovery and liveness
- **Orchestrator Performance** - Multi-agent coordination

## Output Format

### Console Output

The suite provides structured console output including:
- Individual benchmark progress
- Success/failure status
- Duration metrics
- Overall summary
- Category breakdowns
- System information

Example:
```
================================================================================
🚀 ASTRAGUARD PERFORMANCE BENCHMARKING SUITE
================================================================================
Mode: FULL
Started: 2026-02-15 10:30:00
================================================================================

Running: Storage Performance
✅ PASSED - Duration: 2.3456s

Running: Latency Collector
✅ PASSED - Duration: 1.2345s

...

================================================================================
📊 BENCHMARK SUITE SUMMARY
================================================================================

Overall Status: 🎉 ALL PASSED
Total Benchmarks: 8
Successful: 8 ✅
Failed: 0 ❌
Total Duration: 15.67s

Results by Category:
--------------------------------------------------------------------------------

Storage:
  ├─ Benchmarks: 1
  ├─ Success Rate: 1/1 (100.0%)
  └─ Avg Duration: 2.3456s

Metrics:
  ├─ Benchmarks: 2
  ├─ Success Rate: 2/2 (100.0%)
  └─ Avg Duration: 1.5432s

...
```

### JSON Output

Structured JSON format suitable for CI/CD pipelines:

```json
{
  "suite_name": "AstraGuard Performance Suite",
  "total_benchmarks": 8,
  "successful": 8,
  "failed": 0,
  "total_duration_seconds": 15.67,
  "timestamp": "2026-02-15T10:30:15.123456",
  "passed": true,
  "system_info": {
    "python_version": "3.11.0",
    "platform": "Windows-10-10.0.19045-SP0",
    "processor": "Intel64 Family 6 Model 142 Stepping 12, GenuineIntel",
    "cpu_count": "8",
    "memory_gb": "16.00"
  },
  "results": [
    {
      "name": "Storage Performance",
      "category": "Storage",
      "duration_seconds": 2.3456,
      "success": true,
      "error_message": null,
      "metrics": {},
      "timestamp": "2026-02-15T10:30:01.234567"
    },
   ...
  ]
}
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Performance Benchmarks

on: [push, pull_request]

jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install -r src/config/requirements.txt
      
      - name: Run benchmarks
        run: |
          python tests/benchmarks/run_benchmark_suite.py \
            --output results.json \
            --baseline tests/benchmarks/baselines/baseline.json \
            --threshold 10
      
      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: benchmark-results
          path: results.json
```

## Baseline Management

### Creating Baselines

Establish a performance baseline:
```bash
# After verifying performance is acceptable
python tests/benchmarks/run_benchmark_suite.py --save-baseline
```

This creates `tests/benchmarks/baselines/baseline.json`.

### Updating Baselines

When intentional performance changes are made:
```bash
# Run benchmarks and save new baseline
python tests/benchmarks/run_benchmark_suite.py --save-baseline
```

### Multiple Baselines

Maintain different baselines for different environments:
```bash
# Production baseline
python tests/benchmarks/run_benchmark_suite.py -o baselines/production.json

# Development baseline (may be slower)
python tests/benchmarks/run_benchmark_suite.py -o baselines/development.json

# CI baseline
python tests/benchmarks/run_benchmark_suite.py -o baselines/ci.json
```

## Performance Regression Detection

The suite automatically detects regressions when using `--baseline`:

### Good Results (No Regression)
```
📈 BASELINE COMPARISON
================================================================================

Overall Duration:
  Baseline: 15.20s
  Current:  15.67s
  Change:   +3.09%

Individual Benchmark Comparison:
  ✅ Storage Performance: +2.5%
  ✅ Latency Collector: +1.2%
  ✅ Anomaly Detector: -0.5%
  ...

✅ No performance regressions detected!
```

### Regression Detected
```
📈 BASELINE COMPARISON
================================================================================

Overall Duration:
  Baseline: 15.20s
  Current:  18.50s
  Change:   +21.71%

Individual Benchmark Comparison:
  ⚠️ Storage Performance: +15.3%
  ✅ Latency Collector: +1.2%
  ⚠️ Anomaly Detector: +12.8%
  ...

❌ Performance regressions detected in 2 benchmarks:
  - Storage Performance
  - Anomaly Detector

❌ Baseline comparison failed - performance regression detected!
```

## Troubleshooting

### Import Errors

If you encounter import errors:
```bash
# Ensure src is in Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

# Or use absolute path
cd /path/to/AstraGuard-AI-Apertre-3.0
python tests/benchmarks/run_benchmark_suite.py
```

### Missing Dependencies

```bash
# Install all requirements
pip install -r src/config/requirements.txt
pip install psutil
```

### Benchmark Failures

Individual benchmark failures don't stop the suite. Check the summary for:
- Error messages
- Stack traces
- Failed benchmark names

## Contributing

### Adding New Benchmarks

1. Create benchmark file in `tests/benchmarks/`
2. Add benchmark function to `run_benchmark_suite.py`:

```python
def _run_my_benchmark(self):
    """Run my new benchmark."""
    from tests.benchmarks.my_benchmark import benchmark_func
    return benchmark_func()

# In run_all_benchmarks():
result = self.run_benchmark(
    "My Benchmark Name",
    "Category",
    self._run_my_benchmark
)
self.results.append(result)
```

### Testing the Suite

```bash
# Quick smoke test
python tests/benchmarks/run_benchmark_suite.py --quick

# Full test
python tests/benchmarks/run_benchmark_suite.py
```

## Issue Reference

This suite was created to address:
- **Issue #709**: Create performance benchmarking suite
- **Category**: dev-experience
- **Labels**: apertre3.0, medium, dev-experience

## License

MIT License - Part of AstraGuard AI project
