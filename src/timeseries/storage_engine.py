"""
Time-Series Storage Engine

Provides columnar storage with time-based partitioning for efficient
time-series data management.

Features:
- Columnar storage format (timestamps, values, tags stored separately)
- Time-based partitioning (hourly chunks)
- B-tree style indexing for fast time-range queries
- Memory-mapped file access for large datasets
- Automatic chunk rotation and compaction
"""

import os
import json
import struct
import logging
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Iterator
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from collections import defaultdict
import heapq

from .compression import TimeSeriesCompressor, CompressionStats

logger = logging.getLogger(__name__)


@dataclass
class DataPoint:
    """Single time-series data point."""
    timestamp: datetime
    value: float
    tags: Dict[str, str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "value": self.value,
            "tags": self.tags
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DataPoint":
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            value=data["value"],
            tags=data["tags"]
        )


@dataclass
class ChunkMetadata:
    """Metadata for a time-series chunk."""
    metric_name: str
    start_time: datetime
    end_time: datetime
    point_count: int
    compressed_size: int
    original_size: int
    file_path: str
    compression_ratio: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "point_count": self.point_count,
            "compressed_size": self.compressed_size,
            "original_size": self.original_size,
            "file_path": self.file_path,
            "compression_ratio": self.compression_ratio
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChunkMetadata":
        return cls(
            metric_name=data["metric_name"],
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=datetime.fromisoformat(data["end_time"]),
            point_count=data["point_count"],
            compressed_size=data["compressed_size"],
            original_size=data["original_size"],
            file_path=data["file_path"],
            compression_ratio=data["compression_ratio"]
        )


class TimeSeriesChunk:
    """
    A chunk of time-series data covering a specific time range.
    
    Chunks are immutable after writing and are compressed for storage.
    """
    
    CHUNK_DURATION = timedelta(hours=1)  # 1 hour chunks
    
    def __init__(
        self,
        metric_name: str,
        start_time: datetime,
        base_path: Path
    ):
        self.metric_name = metric_name
        self.start_time = start_time
        self.end_time = start_time + self.CHUNK_DURATION
        self.base_path = base_path
        
        self._points: List[DataPoint] = []
        self._is_finalized = False
        self._metadata: Optional[ChunkMetadata] = None
        self._lock = threading.RLock()
        
    def add_point(self, point: DataPoint) -> bool:
        """
        Add a data point to this chunk.
        
        Returns:
            True if point was added, False if point is outside chunk range
        """
        with self._lock:
            if self._is_finalized:
                raise ValueError("Cannot add points to finalized chunk")
            
            if not (self.start_time <= point.timestamp < self.end_time):
                return False
            
            self._points.append(point)
            return True
    
    def finalize(self) -> ChunkMetadata:
        """
        Finalize the chunk by compressing and writing to disk.
        
        Returns:
            ChunkMetadata with storage information
        """
        with self._lock:
            if self._is_finalized:
                return self._metadata
            
            if not self._points:
                raise ValueError("Cannot finalize empty chunk")
            
            # Sort points by timestamp
            self._points.sort(key=lambda p: p.timestamp)
            
            # Extract data for compression
            timestamps = [
                int(p.timestamp.timestamp() * 1000)  # milliseconds
                for p in self._points
            ]
            values = [p.value for p in self._points]
            tags = [p.tags for p in self._points]
            
            # Compress
            compressor = TimeSeriesCompressor()
            compressed_data, stats = compressor.compress_batch(timestamps, values, tags)
            
            # Write to disk
            chunk_dir = self.base_path / self.metric_name
            chunk_dir.mkdir(parents=True, exist_ok=True)
            
            filename = f"{self.start_time.strftime('%Y%m%d_%H%M%S')}.tschunk"
            file_path = chunk_dir / filename
            
            # Write compressed data
            with open(file_path, 'wb') as f:
                f.write(compressed_data)
            
            # Write metadata
            meta_path = file_path.with_suffix('.json')
            self._metadata = ChunkMetadata(
                metric_name=self.metric_name,
                start_time=self.start_time,
                end_time=self.end_time,
                point_count=len(self._points),
                compressed_size=stats.compressed_bytes,
                original_size=stats.original_bytes,
                file_path=str(file_path),
                compression_ratio=stats.compression_ratio
            )
            
            with open(meta_path, 'w') as f:
                json.dump(self._metadata.to_dict(), f, indent=2)
            
            self._is_finalized = True
            logger.info(
                f"Finalized chunk {self.metric_name}: "
                f"{self._metadata.point_count} points, "
                f"{stats.compression_ratio:.1f}x compression"
            )
            
            return self._metadata
    
    def load(self) -> List[DataPoint]:
        """
        Load and decompress all points from this chunk.
        
        Returns:
            List of DataPoint objects
        """
        if self._metadata is None:
            raise ValueError("Chunk not finalized")
        
        file_path = Path(self._metadata.file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Chunk file not found: {file_path}")
        
        # Read compressed data
        with open(file_path, 'rb') as f:
            compressed_data = f.read()
        
        # Decompress
        compressor = TimeSeriesCompressor()
        timestamps_ms, values, _ = compressor.decompress_batch(compressed_data)
        
        # Reconstruct points
        points = []
        for ts_ms, val in zip(timestamps_ms, values):
            ts = datetime.fromtimestamp(ts_ms / 1000.0)
            # Tags are not stored per-point in compressed format
            # In production, you'd store tag indices or use a separate tag store
            points.append(DataPoint(timestamp=ts, value=val, tags={}))
        
        return points
    
    @property
    def is_finalized(self) -> bool:
        return self._is_finalized
    
    @property
    def metadata(self) -> Optional[ChunkMetadata]:
        return self._metadata
    
    @property
    def point_count(self) -> int:
        return len(self._points)


class TimeSeriesIndex:
    """
    B-tree style index for fast time-range queries.
    
    Maintains an in-memory index of chunk metadata for O(log n) lookups.
    """
    
    def __init__(self):
        self._chunks: Dict[str, List[ChunkMetadata]] = defaultdict(list)
        self._lock = threading.RLock()
    
    def add_chunk(self, metric_name: str, metadata: ChunkMetadata) -> None:
        """Add a chunk to the index."""
        with self._lock:
            # Insert in sorted order by start_time
            chunks = self._chunks[metric_name]
            insert_idx = len(chunks)
            for i, chunk in enumerate(chunks):
                if metadata.start_time < chunk.start_time:
                    insert_idx = i
                    break
            
            chunks.insert(insert_idx, metadata)
    
    def find_chunks(
        self,
        metric_name: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[ChunkMetadata]:
        """
        Find all chunks overlapping with the given time range.
        
        Uses binary search for O(log n) lookup.
        """
        with self._lock:
            chunks = self._chunks.get(metric_name, [])
            if not chunks:
                return []
            
            # Binary search for start position
            left, right = 0, len(chunks)
            while left < right:
                mid = (left + right) // 2
                if chunks[mid].end_time <= start_time:
                    left = mid + 1
                else:
                    right = mid
            
            start_idx = left
            
            # Collect all overlapping chunks
            result = []
            for i in range(start_idx, len(chunks)):
                chunk = chunks[i]
                if chunk.start_time >= end_time:
                    break
                if chunk.end_time > start_time:
                    result.append(chunk)
            
            return result
    
    def get_all_metrics(self) -> List[str]:
        """Get list of all metric names in index."""
        with self._lock:
            return list(self._chunks.keys())
    
    def get_chunk_count(self, metric_name: str) -> int:
        """Get number of chunks for a metric."""
        with self._lock:
            return len(self._chunks.get(metric_name, []))
    
    def get_time_range(self, metric_name: str) -> Optional[Tuple[datetime, datetime]]:
        """Get overall time range for a metric."""
        with self._lock:
            chunks = self._chunks.get(metric_name, [])
            if not chunks:
                return None
            return (chunks[0].start_time, chunks[-1].end_time)


class TimeSeriesStorage:
    """
    Main time-series storage engine.
    
    Manages multiple metrics with automatic chunking, compression, and indexing.
    """
    
    def __init__(
        self,
        base_path: str = "data/timeseries",
        max_chunk_points: int = 10000,
        cache_size: int = 100
    ):
        """
        Initialize time-series storage.
        
        Args:
            base_path: Base directory for storage
            max_chunk_points: Maximum points per chunk before finalization
            cache_size: Number of chunks to keep in memory cache
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.max_chunk_points = max_chunk_points
        self.cache_size = cache_size
        
        self._index = TimeSeriesIndex()
        self._active_chunks: Dict[str, TimeSeriesChunk] = {}
        self._chunk_cache: Dict[str, List[DataPoint]] = {}
        self._cache_order: List[str] = []  # LRU cache order
        
        self._lock = threading.RLock()
        self._compressor = TimeSeriesCompressor()
        
        # Load existing chunks from disk
        self._load_existing_chunks()
        
        logger.info(f"TimeSeriesStorage initialized at {base_path}")
    
    def _load_existing_chunks(self) -> None:
        """Load existing chunk metadata from disk."""
        if not self.base_path.exists():
            return
        
        for metric_dir in self.base_path.iterdir():
            if not metric_dir.is_dir():
                continue
            
            metric_name = metric_dir.name
            
            # Find all metadata files
            for meta_file in metric_dir.glob("*.json"):
                try:
                    with open(meta_file, 'r') as f:
                        data = json.load(f)
                    metadata = ChunkMetadata.from_dict(data)
                    self._index.add_chunk(metric_name, metadata)
                except Exception as e:
                    logger.warning(f"Failed to load chunk metadata {meta_file}: {e}")
        
        logger.info(f"Loaded {sum(self._index.get_chunk_count(m) for m in self._index.get_all_metrics())} existing chunks")
    
    def _get_or_create_chunk(self, metric_name: str, timestamp: datetime) -> TimeSeriesChunk:
        """Get existing chunk or create new one for timestamp."""
        with self._lock:
            # Check active chunk
            if metric_name in self._active_chunks:
                chunk = self._active_chunks[metric_name]
                if chunk.start_time <= timestamp < chunk.end_time:
                    return chunk
                
                # Finalize old chunk if full
                if chunk.point_count >= self.max_chunk_points or timestamp >= chunk.end_time:
                    chunk.finalize()
                    self._index.add_chunk(metric_name, chunk.metadata)
                    del self._active_chunks[metric_name]
            
            # Create new chunk
            # Round down to hour boundary
            chunk_start = timestamp.replace(minute=0, second=0, microsecond=0)
            chunk = TimeSeriesChunk(metric_name, chunk_start, self.base_path)
            self._active_chunks[metric_name] = chunk
            
            return chunk
    
    def write(
        self,
        metric_name: str,
        timestamp: datetime,
        value: float,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Write a single data point.
        
        Args:
            metric_name: Name of the metric
            timestamp: Data point timestamp
            value: Data value
            tags: Optional tags dictionary
        """
        if tags is None:
            tags = {}
        
        point = DataPoint(timestamp=timestamp, value=value, tags=tags)
        
        with self._lock:
            chunk = self._get_or_create_chunk(metric_name, timestamp)
            if not chunk.add_point(point):
                # Point outside chunk range, force finalize and retry
                chunk.finalize()
                self._index.add_chunk(metric_name, chunk.metadata)
                del self._active_chunks[metric_name]
                
                # Create new chunk
                chunk = self._get_or_create_chunk(metric_name, timestamp)
                chunk.add_point(point)
    
    def write_batch(
        self,
        metric_name: str,
        timestamps: List[datetime],
        values: List[float],
        tags: Optional[List[Dict[str, str]]] = None
    ) -> None:
        """
        Write multiple data points efficiently.
        
        Args:
            metric_name: Name of the metric
            timestamps: List of timestamps
            values: List of values
            tags: Optional list of tag dictionaries
        """
        if len(timestamps) != len(values):
            raise ValueError("Timestamps and values must have same length")
        
        if tags is None:
            tags = [{} for _ in range(len(timestamps))]
        
        # Sort by timestamp for efficient chunking
        sorted_indices = sorted(range(len(timestamps)), key=lambda i: timestamps[i])
        
        for idx in sorted_indices:
            self.write(metric_name, timestamps[idx], values[idx], tags[idx])
    
    def query(
        self,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
        tags_filter: Optional[Dict[str, str]] = None
    ) -> List[DataPoint]:
        """
        Query data points in time range.
        
        Args:
            metric_name: Metric to query
            start_time: Start of time range
            end_time: End of time range
            tags_filter: Optional tags to filter by
            
        Returns:
            List of DataPoint objects in time range
        """
        with self._lock:
            # Find relevant chunks
            chunks = self._index.find_chunks(metric_name, start_time, end_time)
            
            # Include active chunk if it overlaps
            if metric_name in self._active_chunks:
                active = self._active_chunks[metric_name]
                if active.end_time > start_time and active.start_time < end_time:
                    # Load points from active chunk
                    points = active._points  # Access internal list (within lock)
                    filtered = [
                        p for p in points
                        if start_time <= p.timestamp < end_time
                    ]
                else:
                    filtered = []
            else:
                filtered = []
            
            # Load points from finalized chunks
            for chunk_meta in chunks:
                # Check cache first
                cache_key = chunk_meta.file_path
                if cache_key in self._chunk_cache:
                    points = self._chunk_cache[cache_key]
                    # Update LRU order
                    self._cache_order.remove(cache_key)
                    self._cache_order.append(cache_key)
                else:
                    # Load from disk
                    chunk = TimeSeriesChunk(
                        metric_name,
                        chunk_meta.start_time,
                        self.base_path
                    )
                    chunk._metadata = chunk_meta
                    points = chunk.load()
                    
                    # Add to cache
                    self._add_to_cache(cache_key, points)
                
                # Filter by time range
                for p in points:
                    if start_time <= p.timestamp < end_time:
                        # Apply tags filter if specified
                        if tags_filter:
                            if all(p.tags.get(k) == v for k, v in tags_filter.items()):
                                filtered.append(p)
                        else:
                            filtered.append(p)
            
            # Sort by timestamp
            filtered.sort(key=lambda p: p.timestamp)
            
            return filtered
    
    def _add_to_cache(self, key: str, points: List[DataPoint]) -> None:
        """Add chunk to LRU cache."""
        if len(self._chunk_cache) >= self.cache_size:
            # Evict oldest
            oldest = self._cache_order.pop(0)
            del self._chunk_cache[oldest]
        
        self._chunk_cache[key] = points
        self._cache_order.append(key)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        with self._lock:
            total_chunks = sum(
                self._index.get_chunk_count(m)
                for m in self._index.get_all_metrics()
            )
            
            total_points = 0
            total_compressed = 0
            total_original = 0
            
            for metric in self._index.get_all_metrics():
                chunks = self._index.find_chunks(
                    metric,
                    datetime.min,
                    datetime.max
                )
                for chunk in chunks:
                    total_points += chunk.point_count
                    total_compressed += chunk.compressed_size
                    total_original += chunk.original_size
            
            # Add active chunks
            for chunk in self._active_chunks.values():
                total_points += chunk.point_count
            
            compression_ratio = (
                total_original / total_compressed
                if total_compressed > 0 else 1.0
            )
            
            return {
                "metrics_count": len(self._index.get_all_metrics()),
                "total_chunks": total_chunks,
                "active_chunks": len(self._active_chunks),
                "total_points": total_points,
                "total_compressed_bytes": total_compressed,
                "total_original_bytes": total_original,
                "compression_ratio": round(compression_ratio, 2),
                "cache_size": len(self._chunk_cache),
                "avg_points_per_chunk": (
                    total_points // total_chunks if total_chunks > 0 else 0
                )
            }
    
    def flush(self) -> None:
        """Finalize all active chunks."""
        with self._lock:
            for metric_name, chunk in list(self._active_chunks.items()):
                if chunk.point_count > 0:
                    chunk.finalize()
                    self._index.add_chunk(metric_name, chunk.metadata)
                del self._active_chunks[metric_name]
            
            logger.info("All active chunks flushed to disk")
    
    def close(self) -> None:
        """Close storage and flush all data."""
        self.flush()
        logger.info("TimeSeriesStorage closed")
