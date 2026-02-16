"""
Tests for time-series query engine.

Validates:
- <100ms query latency
- Query result caching
- Pre-aggregated rollups
- Parallel query execution
"""

import pytest
import time
import tempfile
import shutil
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

from src.timeseries.storage_engine import TimeSeriesStorage, DataPoint
from src.timeseries.query_engine import (
    QueryEngine,
    QueryCache,
    RollupManager,
    QueryResult
)


class TestQueryCache:
    """Tests for query result caching."""
    
    def test_cache_hit(self):
        """Test cache hit scenario."""
        cache = QueryCache(max_size=10, ttl_seconds=60)
        
        # Create mock result
        result = QueryResult(
            points=[],
            query_time_ms=10.0,
            chunks_scanned=1,
            points_scanned=100
        )
        
        # Store in cache
        cache.put(
            "metric1",
            datetime(2024, 1, 1),
            datetime(2024, 1, 2),
            result
        )
        
        # Retrieve from cache
        cached = cache.get(
            "metric1",
            datetime(2024, 1, 1),
            datetime(2024, 1, 2)
        )
        
        assert cached is not None
        assert cached.cache_hit is True
        assert cached.query_time_ms == 10.0
    
    def test_cache_miss(self):
        """Test cache miss scenario."""
        cache = QueryCache(max_size=10, ttl_seconds=60)
        
        # Try to retrieve non-existent entry
        cached = cache.get(
            "metric1",
            datetime(2024, 1, 1),
            datetime(2024, 1, 2)
        )
        
        assert cached is None
    
    def test_cache_expiration(self):
        """Test cache entry expiration."""
        cache = QueryCache(max_size=10, ttl_seconds=0.1)  # 100ms TTL
        
        result = QueryResult(
            points=[],
            query_time_ms=10.0,
            chunks_scanned=1,
            points_scanned=100
        )
        
        cache.put(
            "metric1",
            datetime(2024, 1, 1),
            datetime(2024, 1, 2),
            result
        )
        
        # Wait for expiration
        time.sleep(0.2)
        
        # Should be expired
        cached = cache.get(
            "metric1",
            datetime(2024, 1, 1),
            datetime(2024, 1, 2)
        )
        
        assert cached is None
    
    def test_cache_invalidation(self):
        """Test cache invalidation."""
        cache = QueryCache(max_size=10, ttl_seconds=60)
        
        # Add entries for metric1
        result1 = QueryResult(
            points=[],
            query_time_ms=10.0,
            chunks_scanned=1,
            points_scanned=100
        )
        cache.put("metric1", datetime(2024, 1, 1), datetime(2024, 1, 2), result1)
        
        # Add entry for metric2
        result2 = QueryResult(
            points=[],
            query_time_ms=20.0,
            chunks_scanned=2,
            points_scanned=200
        )
        cache.put("metric2", datetime(2024, 1, 1), datetime(2024, 1, 2), result2)
        
        # Invalidate metric1
        removed = cache.invalidate("metric1")
        assert removed == 1
        
        # metric1 should be gone
        assert cache.get("metric1", datetime(2024, 1, 1), datetime(2024, 1, 2)) is None
        
        # metric2 should still exist
        assert cache.get("metric2", datetime(2024, 1, 1), datetime(2024, 1, 2)) is not None
    
    def test_cache_lru_eviction(self):
        """Test LRU cache eviction."""
        cache = QueryCache(max_size=3, ttl_seconds=60)
        
        # Add 3 entries
        for i in range(3):
            result = QueryResult(
                points=[],
                query_time_ms=float(i),
                chunks_scanned=i,
                points_scanned=i * 100
            )
            cache.put(f"metric{i}", datetime(2024, 1, 1), datetime(2024, 1, 2), result)
        
        # Access metric0 to make it recently used
        cache.get("metric0", datetime(2024, 1, 1), datetime(2024, 1, 2))
        
        # Add 4th entry (should evict metric1, not metric0)
        result = QueryResult(
            points=[],
            query_time_ms=3.0,
            chunks_scanned=3,
            points_scanned=300
        )
        cache.put("metric3", datetime(2024, 1, 1), datetime(2024, 1, 2), result)
        
        # metric0 should still exist (was accessed recently)
        assert cache.get("metric0", datetime(2024, 1, 1), datetime(2024, 1, 2)) is not None
        
        # metric1 should be evicted (was not accessed)
        assert cache.get("metric1", datetime(2024, 1, 1), datetime(2024, 1, 2)) is None


class TestQueryEngine:
    """Tests for query engine."""
    
    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage for testing."""
        temp_dir = tempfile.mkdtemp()
        storage = TimeSeriesStorage(base_path=temp_dir, max_chunk_points=1000)
        
        yield storage
        
        # Cleanup
        storage.close()
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_query_latency_requirement(self, temp_storage):
        """
        Test that queries complete in <100ms.
        
        This is a key acceptance criterion.
        """
        # Populate storage with test data
        base_time = datetime(2024, 1, 1)
        
        # Write 10,000 data points
        for i in range(10000):
            temp_storage.write(
                "test_metric",
                base_time + timedelta(seconds=i),
                float(i % 100),
                {"tag": "value"}
            )
        
        temp_storage.flush()
        
        # Create query engine
        engine = QueryEngine(temp_storage, cache_size=10)
        
        # Execute query and measure latency
        start_time = base_time
        end_time = base_time + timedelta(hours=3)
        
        latencies = []
        for _ in range(10):  # Run multiple times
            start = time.time()
            result = engine.query("test_metric", start_time, end_time)
            latency_ms = (time.time() - start) * 1000
            latencies.append(latency_ms)
        
        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        
        # Verify <100ms requirement
        assert avg_latency < 100, (
            f"Average query latency {avg_latency:.2f}ms exceeds 100ms requirement"
        )
        assert max_latency < 100, (
            f"Max query latency {max_latency:.2f}ms exceeds 100ms requirement"
        )
        
        # Verify result
        assert len(result.points) > 0
        assert result.query_time_ms < 100
    
    def test_query_with_aggregation(self, temp_storage):
        """Test query with aggregation."""
        # Populate storage
        base_time = datetime(2024, 1, 1)
        
        for i in range(1000):
            temp_storage.write(
                "test_metric",
                base_time + timedelta(seconds=i),
                float(i),
                {}
            )
        
        temp_storage.flush()
        
        engine = QueryEngine(temp_storage)
        
        # Query with aggregation
        result = engine.query(
            "test_metric",
            base_time,
            base_time + timedelta(minutes=20),
            aggregation="mean",
            group_by=timedelta(minutes=1)
        )
        
        assert result.aggregated is True
        assert len(result.points) > 0
        
        # Should have ~20 points (20 minutes / 1 minute intervals)
        assert 15 <= len(result.points) <= 25
    
    def test_query_caching(self, temp_storage):
        """Test that query results are cached."""
        # Populate storage
        base_time = datetime(2024, 1, 1)
        
        for i in range(100):
            temp_storage.write(
                "test_metric",
                base_time + timedelta(seconds=i),
                float(i),
                {}
            )
        
        temp_storage.flush()
        
        engine = QueryEngine(temp_storage, cache_size=10)
        
        # First query (cache miss)
        result1 = engine.query("test_metric", base_time, base_time + timedelta(minutes=2))
        assert result1.cache_hit is False
        
        # Second query (cache hit)
        result2 = engine.query("test_metric", base_time, base_time + timedelta(minutes=2))
        assert result2.cache_hit is True
    
    def test_parallel_queries(self, temp_storage):
        """Test parallel query execution."""
        # Populate storage with multiple metrics
        base_time = datetime(2024, 1, 1)
        
        for metric_idx in range(5):
            for i in range(1000):
                temp_storage.write(
                    f"metric_{metric_idx}",
                    base_time + timedelta(seconds=i),
                    float(i),
                    {}
                )
        
        temp_storage.flush()
        
        engine = QueryEngine(temp_storage, max_workers=4)
        
        # Create parallel queries
        queries = [
            (f"metric_{i}", base_time, base_time + timedelta(minutes=10))
            for i in range(5)
        ]
        
        # Execute in parallel
        start = time.time()
        results = engine.parallel_query(queries)
        total_time = (time.time() - start) * 1000
        
        # Should complete faster than sequential execution
        assert len(results) == 5
        assert total_time < 500  # Should be much faster than 5 * 100ms
        
        for result in results:
            assert len(result.points) > 0
    
    def test_query_with_tags_filter(self, temp_storage):
        """Test query with tags filter."""
        base_time = datetime(2024, 1, 1)
        
        # Write data with different tags
        for i in range(100):
            temp_storage.write(
                "test_metric",
                base_time + timedelta(seconds=i),
                float(i),
                {"satellite": f"SAT{i % 3}", "type": "latency"}
            )
        
        temp_storage.flush()
        
        engine = QueryEngine(temp_storage)
        
        # Query with tags filter
        result = engine.query(
            "test_metric",
            base_time,
            base_time + timedelta(minutes=2),
            tags_filter={"satellite": "SAT0"}
        )
        
        # Should only return points with matching tag
        for point in result.points:
            assert point.tags.get("satellite") == "SAT0"
    
    def test_rollup_creation_and_query(self, temp_storage):
        """Test rollup creation and querying."""
        # Populate storage
        base_time = datetime(2024, 1, 1)
        
        for i in range(10000):
            temp_storage.write(
                "test_metric",
                base_time + timedelta(seconds=i),
                float(i % 100),
                {}
            )
        
        temp_storage.flush()
        
        engine = QueryEngine(temp_storage)
        
        # Create rollup
        success = engine.create_rollup("test_metric", timedelta(minutes=1), "mean")
        assert success is True
        
        # Query using rollup
        result = engine.query(
            "test_metric",
            base_time,
            base_time + timedelta(hours=1),
            aggregation="mean",
            group_by=timedelta(minutes=1),
            use_rollup=True
        )
        
        assert result.aggregated is True
        
        # Should be fast due to rollup
        assert result.query_time_ms < 50
    
    def test_query_planning(self, temp_storage):
        """Test query plan generation."""
        base_time = datetime(2024, 1, 1)
        
        for i in range(1000):
            temp_storage.write(
                "test_metric",
                base_time + timedelta(seconds=i),
                float(i),
                {}
            )
        
        temp_storage.flush()
        
        engine = QueryEngine(temp_storage)
        
        # Generate query plan
        plan = engine.plan_query(
            "test_metric",
            base_time,
            base_time + timedelta(minutes=10),
            aggregation="mean",
            group_by=timedelta(minutes=1)
        )
        
        assert plan.metric_name == "test_metric"
        assert plan.estimated_points > 0
        assert plan.estimated_cost > 0
    
    def test_empty_query(self, temp_storage):
        """Test query with no matching data."""
        engine = QueryEngine(temp_storage)
        
        result = engine.query(
            "nonexistent_metric",
            datetime(2024, 1, 1),
            datetime(2024, 1, 2)
        )
        
        assert len(result.points) == 0
        assert result.chunks_scanned == 0
    
    def test_query_stats(self, temp_storage):
        """Test query statistics collection."""
        base_time = datetime(2024, 1, 1)
        
        for i in range(100):
            temp_storage.write(
                "test_metric",
                base_time + timedelta(seconds=i),
                float(i),
                {}
            )
        
        temp_storage.flush()
        
        engine = QueryEngine(temp_storage)
        
        # Execute some queries
        for _ in range(5):
            engine.query("test_metric", base_time, base_time + timedelta(minutes=1))
        
        stats = engine.get_stats()
        
        assert stats["total_queries"] == 5
        assert stats["avg_query_time_ms"] > 0
        assert "cache_stats" in stats
