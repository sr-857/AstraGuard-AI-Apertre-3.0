"""
Tests for time-series compression module.

Validates:
- 10x compression ratio target
- Lossless compression/decompression
- Performance requirements
"""

import pytest
import struct
import random
from datetime import datetime, timedelta

from src.timeseries.compression import (
    GorillaCompressor,
    TimestampCompressor,
    TimeSeriesCompressor,
    CompressionStats
)


class TestGorillaCompressor:
    """Tests for Gorilla XOR compression."""
    
    def test_basic_compression(self):
        """Test basic value compression."""
        compressor = GorillaCompressor()
        
        values = [1.0, 1.1, 1.2, 1.3, 1.4]
        for v in values:
            compressor.compress_value(v)
        
        data = compressor.flush()
        assert len(data) > 0
        
        # Decompress
        decompressor = GorillaCompressor()
        restored = decompressor.decompress_values(data, len(values))
        
        assert len(restored) == len(values)
        for original, recovered in zip(values, restored):
            assert abs(original - recovered) < 0.001
    
    def test_similar_values_compression(self):
        """Test compression of similar values (high compression ratio)."""
        compressor = GorillaCompressor()
        
        # Generate similar values (typical for time-series)
        base = 100.0
        values = [base + random.gauss(0, 0.1) for _ in range(1000)]
        
        for v in values:
            compressor.compress_value(v)
        
        data = compressor.flush()
        
        # Calculate compression ratio
        original_size = len(values) * 8  # 8 bytes per float64
        compressed_size = len(data)
        ratio = original_size / compressed_size
        
        # Should achieve good compression for similar values
        assert ratio > 5.0, f"Compression ratio {ratio} below threshold"
    
    def test_rapidly_changing_values(self):
        """Test compression of rapidly changing values."""
        compressor = GorillaCompressor()
        
        # Alternating high/low values
        values = [1000.0 if i % 2 == 0 else -1000.0 for i in range(100)]
        
        for v in values:
            compressor.compress_value(v)
        
        data = compressor.flush()
        
        # Decompress and verify
        decompressor = GorillaCompressor()
        restored = decompressor.decompress_values(data, len(values))
        
        assert len(restored) == len(values)
        for original, recovered in zip(values, restored):
            assert abs(original - recovered) < 0.001
    
    def test_empty_decompression(self):
        """Test handling of empty data."""
        decompressor = GorillaCompressor()
        result = decompressor.decompress_values(b'', 0)
        assert result == []


class TestTimestampCompressor:
    """Tests for delta-of-delta timestamp compression."""
    
    def test_regular_intervals(self):
        """Test compression of regular timestamp intervals."""
        compressor = TimestampCompressor()
        
        # 1-second intervals
        base_time = int(datetime(2024, 1, 1).timestamp() * 1000)
        timestamps = [base_time + i * 1000 for i in range(1000)]
        
        for ts in timestamps:
            compressor.compress_timestamp(ts)
        
        data = compressor.flush()
        
        # Should achieve excellent compression for regular intervals
        original_size = len(timestamps) * 8
        compressed_size = len(data)
        ratio = original_size / compressed_size
        
        assert ratio > 10.0, f"Timestamp compression ratio {ratio} below threshold"
        
        # Verify decompression
        decompressor = TimestampCompressor()
        restored = decompressor.decompress_timestamps(data, len(timestamps))
        
        assert restored == timestamps
    
    def test_irregular_intervals(self):
        """Test compression of irregular timestamp intervals."""
        compressor = TimestampCompressor()
        
        base_time = int(datetime(2024, 1, 1).timestamp() * 1000)
        timestamps = [base_time]
        
        # Add irregular intervals
        current = base_time
        for _ in range(999):
            interval = random.randint(100, 5000)  # 100ms to 5s
            current += interval
            timestamps.append(current)
        
        for ts in timestamps:
            compressor.compress_timestamp(ts)
        
        data = compressor.flush()
        
        # Verify decompression
        decompressor = TimestampCompressor()
        restored = decompressor.decompress_timestamps(data, len(timestamps))
        
        assert restored == timestamps
    
    def test_mixed_intervals(self):
        """Test compression of mixed regular and burst intervals."""
        compressor = TimestampCompressor()
        
        base_time = int(datetime(2024, 1, 1).timestamp() * 1000)
        timestamps = []
        
        # Regular intervals with occasional bursts
        current = base_time
        for i in range(1000):
            if i % 100 == 0:
                # Burst: 10 timestamps at 10ms intervals
                for j in range(10):
                    timestamps.append(current + j * 10)
                current += 10 * 10
            else:
                # Regular 1-second interval
                timestamps.append(current)
                current += 1000
        
        for ts in timestamps:
            compressor.compress_timestamp(ts)
        
        data = compressor.flush()
        
        # Verify decompression
        decompressor = TimestampCompressor()
        restored = decompressor.decompress_timestamps(data, len(timestamps))
        
        assert restored == timestamps


class TestTimeSeriesCompressor:
    """Tests for main time-series compressor."""
    
    def test_compression_ratio_target(self):
        """
        Test that 10x compression ratio is achieved.
        
        This is the main acceptance criterion for compression.
        """
        compressor = TimeSeriesCompressor()
        
        # Generate realistic time-series data
        base_time = int(datetime(2024, 1, 1).timestamp() * 1000)
        
        timestamps = []
        values = []
        
        # Simulate 10,000 data points over 1 hour
        current_time = base_time
        current_value = 50.0
        
        for i in range(10000):
            # 1-second intervals with slight jitter
            current_time += 1000 + random.randint(-10, 10)
            # Value with small random walk
            current_value += random.gauss(0, 0.5)
            current_value = max(0, min(100, current_value))  # Clamp to 0-100
            
            timestamps.append(current_time)
            values.append(current_value)
        
        # Compress
        compressed, stats = compressor.compress_batch(timestamps, values)
        
        # Verify 10x compression ratio
        assert stats.compression_ratio >= 10.0, (
            f"Compression ratio {stats.compression_ratio:.2f}x "
            f"does not meet 10x target. "
            f"Original: {stats.original_bytes}, "
            f"Compressed: {stats.compressed_bytes}"
        )
        
        # Verify decompression
        restored_ts, restored_vals, _ = compressor.decompress_batch(compressed)
        
        assert len(restored_ts) == len(timestamps)
        assert len(restored_vals) == len(values)
        
        # Timestamps should be exact
        assert restored_ts == timestamps
        
        # Values should be within floating point precision
        for orig, recov in zip(values, restored_vals):
            assert abs(orig - recov) < 0.01
    
    def test_batch_compression_performance(self):
        """Test compression performance."""
        import time
        
        compressor = TimeSeriesCompressor()
        
        # Generate test data
        base_time = int(datetime(2024, 1, 1).timestamp() * 1000)
        timestamps = [base_time + i * 1000 for i in range(10000)]
        values = [50.0 + random.gauss(0, 5) for _ in range(10000)]
        
        # Measure compression time
        start = time.time()
        compressed, stats = compressor.compress_batch(timestamps, values)
        compress_time = (time.time() - start) * 1000
        
        # Measure decompression time
        start = time.time()
        restored_ts, restored_vals, _ = compressor.decompress_batch(compressed)
        decompress_time = (time.time() - start) * 1000
        
        # Should be fast (< 100ms for 10k points)
        assert compress_time < 100, f"Compression too slow: {compress_time:.2f}ms"
        assert decompress_time < 100, f"Decompression too slow: {decompress_time:.2f}ms"
    
    def test_with_tags(self):
        """Test compression with tags."""
        compressor = TimeSeriesCompressor()
        
        base_time = int(datetime(2024, 1, 1).timestamp() * 1000)
        timestamps = [base_time + i * 1000 for i in range(100)]
        values = [float(i) for i in range(100)]
        tags = [{"satellite": f"SAT{i % 5}", "metric": "latency"} for i in range(100)]
        
        compressed, stats = compressor.compress_batch(timestamps, values, tags)
        
        # Verify decompression
        restored_ts, restored_vals, restored_tags = compressor.decompress_batch(compressed)
        
        assert len(restored_ts) == len(timestamps)
        assert len(restored_vals) == len(values)
    
    def test_empty_batch(self):
        """Test handling of empty batch."""
        compressor = TimeSeriesCompressor()
        
        compressed, stats = compressor.compress_batch([], [])
        
        assert stats.points_count == 0
        assert stats.original_bytes == 0
        
        # Decompress empty
        restored_ts, restored_vals, _ = compressor.decompress_batch(compressed)
        assert restored_ts == []
        assert restored_vals == []
    
    def test_single_point(self):
        """Test compression of single point."""
        compressor = TimeSeriesCompressor()
        
        timestamps = [int(datetime(2024, 1, 1).timestamp() * 1000)]
        values = [42.0]
        
        compressed, stats = compressor.compress_batch(timestamps, values)
        
        restored_ts, restored_vals, _ = compressor.decompress_batch(compressed)
        
        assert restored_ts == timestamps
        assert restored_vals == values
    
    def test_compression_stats(self):
        """Test compression statistics calculation."""
        stats = TimeSeriesCompressor.get_compression_stats(1000, 100)
        
        assert stats["original_bytes"] == 1000
        assert stats["compressed_bytes"] == 100
        assert stats["compression_ratio"] == 10.0
        assert "90.0%" in stats["savings_percent"]
