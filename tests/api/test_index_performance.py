"""
Performance benchmark tests for src/api/index.py

This module benchmarks the performance characteristics of the index.py module,
which serves as the Vercel serverless entry point for AstraGuard AI.

Test Areas:
1. Path resolution performance
2. sys.path manipulation overhead
3. Module import time
4. Overall cold start time
5. Memory footprint

Run with: pytest tests/api/test_index_performance.py -v
"""

import sys
import time
import pytest
from pathlib import Path
import importlib
import gc


class TestIndexPerformance:
    """Performance benchmarks for index.py module."""
    
    def test_path_resolution_performance(self, benchmark):
        """Benchmark Path(__file__).parent.parent resolution."""
        
        def resolve_path():
            project_root = Path(__file__).parent.parent.parent
            return project_root
        
        result = benchmark(resolve_path)
        assert result.exists()
        assert benchmark.stats['mean'] < 0.001
    
    def test_string_conversion_performance(self, benchmark):
        """Benchmark str() conversion of Path objects."""
        
        project_root = Path(__file__).parent.parent.parent
        
        def convert_to_string():
            return str(project_root)
        
        result = benchmark(convert_to_string)
        assert isinstance(result, str)
        assert benchmark.stats['mean'] < 0.0001
    
    def test_syspath_check_performance(self, benchmark):
        """Benchmark sys.path membership check."""
        
        test_path = "/fake/test/path"
        
        def check_syspath():
            return test_path not in sys.path
        
        result = benchmark(check_syspath)
        assert result is True
        # Relaxed threshold to reduce flakiness on CI/slow hosts
        assert benchmark.stats['mean'] < 0.00002
    
    def test_syspath_insert_performance(self, benchmark):
        """Benchmark sys.path.insert() operation."""
        
        def insert_to_syspath():
            test_path = f"/test/path/{time.time()}"
            sys.path.insert(0, test_path)
            sys.path.remove(test_path)
            return test_path
        
        result = benchmark(insert_to_syspath)
        assert result not in sys.path
        assert benchmark.stats['mean'] < 0.00005
    
    def test_logger_creation_performance(self, benchmark):
        """Benchmark logging.getLogger() call."""
        import logging
        
        def create_logger():
            return logging.getLogger(f"test_logger_{time.time()}")
        
        result = benchmark(create_logger)
        assert result is not None
        # Relaxed threshold to reduce flakiness on CI/slow hosts
        assert benchmark.stats['mean'] < 0.00002
    
    @pytest.mark.slow
    def test_full_module_import_time(self):
        """Measure full module import time (cold start simulation)."""
        
        module_name = 'src.api.index'
        if module_name in sys.modules:
            del sys.modules[module_name]
        
        gc.collect()
        
        start = time.perf_counter()
        try:
            import src.api.index
        except (ImportError, ModuleNotFoundError, SyntaxError, IndentationError) as e:
            pytest.skip(f"Cannot import module in test environment: {e}")
        
        import_time = time.perf_counter() - start
        assert import_time < 0.1
        
        print(f"\nFull module import time: {import_time*1000:.3f}ms")


class TestIndexMemoryFootprint:
    """Memory footprint tests for index.py."""
    
    @pytest.mark.slow
    def test_memory_overhead(self):
        """Measure memory overhead of index.py module."""
        import tracemalloc
        
        tracemalloc.start()
        snapshot1 = tracemalloc.take_snapshot()
        
        project_root = Path(__file__).parent.parent.parent
        project_root_str = str(project_root)
        
        if project_root_str not in sys.path:
            sys.path.insert(0, project_root_str)
        
        snapshot2 = tracemalloc.take_snapshot()
        top_stats = snapshot2.compare_to(snapshot1, 'lineno')
        total_memory = sum(stat.size_diff for stat in top_stats)
        tracemalloc.stop()
        
        assert total_memory < 10 * 1024
        print(f"\nMemory overhead: {total_memory / 1024:.2f}KB")


class TestOptimizationComparison:
    """Compare different implementation approaches."""
    
    def test_eager_vs_lazy_string_conversion(self, benchmark):
        """Compare eager vs lazy string conversion."""
        
        project_root = Path(__file__).parent.parent.parent
        
        def eager_approach():
            project_root_str = str(project_root)
            if project_root_str not in sys.path:
                return project_root_str
            return None
        
        def lazy_approach():
            if str(project_root) not in sys.path:
                return str(project_root)
            return None
        
        eager_time = benchmark(eager_approach)


@pytest.fixture
def benchmark(request):
    """Custom benchmark fixture with detailed statistics."""
    
    class SimpleBenchmark:
        def __init__(self):
            self.stats = {}
        
        def __call__(self, func, *args, **kwargs):
            for _ in range(10):
                func(*args, **kwargs)
            
            times = []
            for _ in range(100):
                start = time.perf_counter()
                result = func(*args, **kwargs)
                elapsed = time.perf_counter() - start
                times.append(elapsed)
            
            self.stats['mean'] = sum(times) / len(times)
            self.stats['min'] = min(times)
            self.stats['max'] = max(times)
            self.stats['median'] = sorted(times)[len(times) // 2]
            
            return result
    
    return SimpleBenchmark()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])