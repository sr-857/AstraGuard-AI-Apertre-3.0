#!/usr/bin/env python3
"""
AstraGuard Performance Benchmarking Suite (#709)

Unified benchmarking suite that runs all performance benchmarks and provides
comprehensive reporting, baseline comparison, and performance regression detection.

Usage:
    python tests/benchmarks/run_benchmark_suite.py
    python tests/benchmarks/run_benchmark_suite.py --output results.json
    python tests/benchmarks/run_benchmark_suite.py --baseline baselines/production.json
    python tests/benchmarks/run_benchmark_suite.py --save-baseline
    python tests/benchmarks/run_benchmark_suite.py --quick  # Run subset of benchmarks
"""

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from statistics import mean, stdev

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


@dataclass
class BenchmarkResult:
    """Individual benchmark result."""
    name: str
    category: str
    duration_seconds: float
    success: bool
    error_message: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None


@dataclass
class SuiteResult:
    """Complete suite results."""
    suite_name: str
    total_benchmarks: int
    successful: int
    failed: int
    total_duration_seconds: float
    results: List[BenchmarkResult]
    timestamp: str
    system_info: Dict[str, str]
    passed: bool


class BenchmarkSuite:
    """Main benchmarking suite runner."""

    def __init__(self, quick_mode: bool = False):
        self.quick_mode = quick_mode
        self.results: List[BenchmarkResult] = []
        self.start_time: float = 0

    def run_benchmark(self, name: str, category: str, benchmark_func, *args, **kwargs) -> BenchmarkResult:
        """Run a single benchmark and capture results."""
        print(f"\n{'='*70}")
        print(f"  Running: {name}")
        print(f"  Category: {category}")
        print(f"{'='*70}")

        start_time = time.time()
        success = True
        error_message = None
        metrics = {}

        try:
            result = benchmark_func(*args, **kwargs)
            if asyncio.iscoroutine(result):
                result = asyncio.run(result)
            
            # Extract metrics if result is a dict
            if isinstance(result, dict):
                metrics = result
            elif isinstance(result, (tuple, list)):
                # Convert tuple/list results to metrics
                if len(result) == 3:  # Common pattern: avg, min, max
                    metrics = {
                        "average": result[0],
                        "minimum": result[1],
                        "maximum": result[2]
                    }

        except Exception as e:
            success = False
            error_message = str(e)
            print(f"❌ FAILED: {error_message}")

        duration = time.time() - start_time

        result = BenchmarkResult(
            name=name,
            category=category,
            duration_seconds=duration,
            success=success,
            error_message=error_message,
            metrics=metrics,
            timestamp=datetime.now().isoformat()
        )

        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"\n{status} - Duration: {duration:.4f}s")

        return result

    async def run_all_benchmarks(self) -> SuiteResult:
        """Run all benchmarks in the suite."""
        self.start_time = time.time()
        print("\n" + "="*80)
        print("🚀 ASTRAGUARD PERFORMANCE BENCHMARKING SUITE")
        print("="*80)
        print(f"Mode: {'QUICK' if self.quick_mode else 'FULL'}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)

        # Storage Benchmarks
        if not self.quick_mode:
            result = self.run_benchmark(
                "Storage Performance",
                "Storage",
                self._run_storage_benchmark
            )
            self.results.append(result)

        # Latency Benchmarks
        result = self.run_benchmark(
            "Latency Collector",
            "Metrics",
            self._run_latency_benchmark
        )
        self.results.append(result)

        # Anomaly Detector Benchmarks
        result = self.run_benchmark(
            "Anomaly Detector",
            "ML",
            self._run_anomaly_benchmark
        )
        self.results.append(result)

        # Metrics Storage Benchmarks
        if not self.quick_mode:
            result = self.run_benchmark(
                "Metrics Storage",
                "Metrics",
                self._run_metrics_storage_benchmark
            )
            self.results.append(result)

        # Cache Benchmarks
        result = self.run_benchmark(
            "Cache Operations",
            "Performance",
            self._run_cache_benchmark
        )
        self.results.append(result)

        # State Serialization Benchmarks
        if not self.quick_mode:
            result = self.run_benchmark(
                "State Serialization",
                "Performance",
                self._run_serialization_benchmark
            )
            self.results.append(result)

        # Discovery/Heartbeat Benchmarks
        if not self.quick_mode:
            result = self.run_benchmark(
                "Discovery & Heartbeat",
                "Swarm",
                self._run_discovery_benchmark
            )
            self.results.append(result)

        # Orchestrator Benchmarks
        if not self.quick_mode:
            result = self.run_benchmark(
                "Orchestrator Performance",
                "Swarm",
                self._run_orchestrator_benchmark
            )
            self.results.append(result)

        # Compile suite results
        total_duration = time.time() - self.start_time
        successful = sum(1 for r in self.results if r.success)
        failed = len(self.results) - successful

        suite_result = SuiteResult(
            suite_name="AstraGuard Performance Suite",
            total_benchmarks=len(self.results),
            successful=successful,
            failed=failed,
            total_duration_seconds=total_duration,
            results=self.results,
            timestamp=datetime.now().isoformat(),
            system_info=self._get_system_info(),
            passed=failed == 0
        )

        return suite_result

    def _run_storage_benchmark(self):
        """Run storage benchmark."""
        from tests.benchmarks.benchmark_storage import main as bench_storage
        return bench_storage()

    def _run_latency_benchmark(self):
        """Run latency benchmark."""
        from tests.benchmarks.benchmark_latency import benchmark_latency
        return benchmark_latency()

    async def _run_anomaly_benchmark(self):
        """Run anomaly detector benchmark."""
        from tests.benchmarks.benchmark_anomaly_detector import benchmark_anomaly_detector
        return await benchmark_anomaly_detector()

    async def _run_metrics_storage_benchmark(self):
        """Run metrics storage benchmark."""
        from tests.benchmarks.benchmark_metrics_storage import benchmark_metrics_storage
        return await benchmark_metrics_storage()

    def _run_cache_benchmark(self):
        """Run cache benchmark."""
        from tests.benchmarks.cache_benchmarks import print_results
        return print_results()

    def _run_serialization_benchmark(self):
        """Run state serialization benchmark."""
        from tests.benchmarks.state_serialization import main as bench_serial
        return bench_serial()

    def _run_discovery_benchmark(self):
        """Run discovery/heartbeat benchmark."""
        from tests.benchmarks.discovery_heartbeat import main as bench_discovery
        return bench_discovery()

    def _run_orchestrator_benchmark(self):
        """Run orchestrator benchmark."""
        from tests.benchmarks.bench_orchestrator import main as bench_orch
        return bench_orch()

    def _get_system_info(self) -> Dict[str, str]:
        """Get system information."""
        import platform
        import psutil

        return {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "processor": platform.processor(),
            "cpu_count": str(psutil.cpu_count()),
            "memory_gb": f"{psutil.virtual_memory().total / (1024**3):.2f}",
        }


class ResultsReporter:
    """Generate formatted reports from benchmark results."""

    @staticmethod
    def print_summary(suite_result: SuiteResult):
        """Print formatted summary to console."""
        print("\n" + "="*80)
        print("📊 BENCHMARK SUITE SUMMARY")
        print("="*80)

        # Overall status
        status = "🎉 ALL PASSED" if suite_result.passed else "❌ FAILURES DETECTED"
        print(f"\nOverall Status: {status}")
        print(f"Total Benchmarks: {suite_result.total_benchmarks}")
        print(f"Successful: {suite_result.successful} ✅")
        print(f"Failed: {suite_result.failed} ❌")
        print(f"Total Duration: {suite_result.total_duration_seconds:.2f}s")

        # Results by category
        print("\n" + "-"*80)
        print("Results by Category:")
        print("-"*80)

        categories: Dict[str, List[BenchmarkResult]] = {}
        for result in suite_result.results:
            if result.category not in categories:
                categories[result.category] = []
            categories[result.category].append(result)

        for category,results in sorted(categories.items()):
            successful = sum(1 for r in results if r.success)
            total = len(results)
            avg_duration = mean([r.duration_seconds for r in results])

            print(f"\n{category}:")
            print(f"  ├─ Benchmarks: {total}")
            print(f"  ├─ Success Rate: {successful}/{total} ({successful/total*100:.1f}%)")
            print(f"  └─ Avg Duration: {avg_duration:.4f}s")

        # Individual results
        print("\n" + "-"*80)
        print("Individual Benchmark Results:")
        print("-"*80)

        for result in suite_result.results:
            status = "✅" if result.success else "❌"
            print(f"\n{status} {result.name}")
            print(f"   Duration: {result.duration_seconds:.4f}s")
            if result.metrics:
                print(f"   Metrics: {json.dumps(result.metrics, indent=2)}")
            if not result.success:
                print(f"   Error: {result.error_message}")

        # System info
        print("\n" + "-"*80)
        print("System Information:")
        print("-"*80)
        for key, value in suite_result.system_info.items():
            print(f"  {key}: {value}")

        print("\n" + "="*80)
        print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80 + "\n")

    @staticmethod
    def save_json(suite_result: SuiteResult, output_path: Path):
        """Save results to JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict with proper serialization
        data = {
            "suite_name": suite_result.suite_name,
            "total_benchmarks": suite_result.total_benchmarks,
            "successful": suite_result.successful,
            "failed": suite_result.failed,
            "total_duration_seconds": suite_result.total_duration_seconds,
            "timestamp": suite_result.timestamp,
            "passed": suite_result.passed,
            "system_info": suite_result.system_info,
            "results": [asdict(r) for r in suite_result.results]
        }

        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"\n💾 Results saved to: {output_path}")

    @staticmethod
    def compare_with_baseline(current: SuiteResult, baseline_path: Path, threshold_pct: float = 10.0) -> bool:
        """Compare current results with baseline."""
        if not baseline_path.exists():
            print(f"\n⚠️  Baseline file not found: {baseline_path}")
            return True

        with open(baseline_path) as f:
            baseline_data = json.load(f)

        print("\n" + "="*80)
        print("📈 BASELINE COMPARISON")
        print("="*80)

        # Compare overall metrics
        baseline_duration = baseline_data.get("total_duration_seconds", 0)
        current_duration = current.total_duration_seconds
        duration_change = ((current_duration - baseline_duration) / baseline_duration) * 100

        print(f"\nOverall Duration:")
        print(f"  Baseline: {baseline_duration:.2f}s")
        print(f"  Current:  {current_duration:.2f}s")
        print(f"  Change:   {duration_change:+.2f}%")

        # Compare individual benchmarks
        baseline_results = {r["name"]: r for r in baseline_data.get("results", [])}
        regressions = []

        print("\nIndividual Benchmark Comparison:")
        for result in current.results:
            if result.name in baseline_results:
                baseline_result = baseline_results[result.name]
                baseline_time = baseline_result["duration_seconds"]
                current_time = result.duration_seconds
                change_pct = ((current_time - baseline_time) / baseline_time) * 100

                status = "✅" if change_pct <= threshold_pct else "⚠️"
                print(f"  {status} {result.name}: {change_pct:+.2f}%")

                if change_pct > threshold_pct:
                    regressions.append(result.name)

        if regressions:
            print(f"\n❌ Performance regressions detected in {len(regressions)} benchmarks:")
            for name in regressions:
                print(f"  - {name}")
            return False
        else:
            print("\n✅ No performance regressions detected!")
            return True


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="AstraGuard Performance Benchmarking Suite"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output JSON file for results"
    )
    parser.add_argument(
        "--baseline", "-b",
        type=Path,
        help="Baseline JSON file for comparison"
    )
    parser.add_argument(
        "--save-baseline",
        action="store_true",
        help="Save results as new baseline"
    )
    parser.add_argument(
        "--quick", "-q",
        action="store_true",
        help="Run quick subset of benchmarks"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=10.0,
        help="Performance regression threshold percentage (default: 10%%)"
    )

    args = parser.parse_args()

    # Run benchmark suite
    suite = BenchmarkSuite(quick_mode=args.quick)
    results = await suite.run_all_benchmarks()

    # Print summary
    ResultsReporter.print_summary(results)

    # Save results if requested
    if args.output:
        ResultsReporter.save_json(results, args.output)

    # Save as baseline if requested
    if args.save_baseline:
        baseline_dir = Path(__file__).parent / "baselines"
        baseline_path = baseline_dir / "baseline.json"
        ResultsReporter.save_json(results, baseline_path)
        print(f"✅ Baseline saved to: {baseline_path}")

    # Compare with baseline if provided
    if args.baseline:
        comparison_passed = ResultsReporter.compare_with_baseline(
            results,
            args.baseline,
            args.threshold
        )
        if not comparison_passed:
            print("\n❌ Baseline comparison failed - performance regression detected!")
            return 1

    # Exit with appropriate code
    if not results.passed:
        print("\n❌ Benchmark suite failed!")
        return 1

    print("\n✅ Benchmark suite completed successfully!")
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Benchmark suite interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
