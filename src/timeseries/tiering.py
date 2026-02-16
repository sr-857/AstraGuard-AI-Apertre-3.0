"""
Data Tiering Module for Time-Series Storage

Implements hot/warm/cold storage tiers for cost optimization:
- Hot tier: Recent data in memory (fastest access)
- Warm tier: SSD storage for medium-term data
- Cold tier: Compressed archival storage (cheapest)

Automatic tier migration based on data age and access patterns.
"""

import os
import json
import shutil
import logging
import threading
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from collections import defaultdict
import heapq

from .storage_engine import TimeSeriesStorage, ChunkMetadata, DataPoint

logger = logging.getLogger(__name__)


class StorageTier(str, Enum):
    """Storage tier levels."""
    HOT = "hot"      # In-memory / Redis
    WARM = "warm"    # Local SSD
    COLD = "cold"    # Compressed archival / Object storage


@dataclass
class TierConfig:
    """Configuration for a storage tier."""
    tier: StorageTier
    path: str
    max_age_days: int  # Data older than this moves to next tier
    compression_level: int  # 0-9, 0 = no compression
    replication_factor: int = 1


class TieredStorageManager:
    """
    Manages data across hot, warm, and cold storage tiers.
    
    Automatically migrates data based on age and access patterns
    to optimize cost and performance.
    """
    
    def __init__(
        self,
        storage: TimeSeriesStorage,
        hot_path: str = "data/timeseries/hot",
        warm_path: str = "data/timeseries/warm",
        cold_path: str = "data/timeseries/cold",
        hot_max_age_days: int = 1,
        warm_max_age_days: int = 7,
        hot_compression: int = 0,
        warm_compression: int = 3,
        cold_compression: int = 9
    ):
        """
        Initialize tiered storage manager.
        
        Args:
            storage: TimeSeriesStorage instance
            hot_path: Path for hot tier storage
            warm_path: Path for warm tier storage
            cold_path: Path for cold tier storage
            hot_max_age_days: Max age for hot tier
            warm_max_age_days: Max age for warm tier
            hot_compression: Compression level for hot tier (0 = none)
            warm_compression: Compression level for warm tier
            cold_compression: Compression level for cold tier
        """
        self.storage = storage
        
        # Configure tiers
        self.tiers = {
            StorageTier.HOT: TierConfig(
                tier=StorageTier.HOT,
                path=hot_path,
                max_age_days=hot_max_age_days,
                compression_level=hot_compression
            ),
            StorageTier.WARM: TierConfig(
                tier=StorageTier.WARM,
                path=warm_path,
                max_age_days=warm_max_age_days,
                compression_level=warm_compression
            ),
            StorageTier.COLD: TierConfig(
                tier=StorageTier.COLD,
                path=cold_path,
                max_age_days=365 * 10,  # 10 years
                compression_level=cold_compression
            )
        }
        
        # Create tier directories
        for tier_config in self.tiers.values():
            Path(tier_config.path).mkdir(parents=True, exist_ok=True)
        
        # Track chunk locations
        self._chunk_tiers: Dict[str, StorageTier] = {}
        self._access_counts: Dict[str, int] = defaultdict(int)
        self._last_access: Dict[str, datetime] = {}
        self._lock = threading.RLock()
        
        # Hot tier cache (in-memory)
        self._hot_cache: Dict[str, List[DataPoint]] = {}
        self._hot_cache_size = 100  # Max chunks in hot cache
        
        # Stats
        self._migration_count = 0
        self._bytes_migrated = 0
        
        logger.info(
            f"TieredStorageManager initialized: "
            f"hot={hot_max_age_days}d, warm={warm_max_age_days}d"
        )
    
    def get_tier_for_chunk(self, chunk_meta: ChunkMetadata) -> StorageTier:
        """
        Determine appropriate tier for a chunk based on age.
        
        Args:
            chunk_meta: Chunk metadata
            
        Returns:
            Recommended storage tier
        """
        age_days = (datetime.now() - chunk_meta.end_time).days
        
        if age_days <= self.tiers[StorageTier.HOT].max_age_days:
            return StorageTier.HOT
        elif age_days <= self.tiers[StorageTier.WARM].max_age_days:
            return StorageTier.WARM
        else:
            return StorageTier.COLD
    
    def get_chunk_tier(self, chunk_path: str) -> StorageTier:
        """Get current tier of a chunk."""
        with self._lock:
            return self._chunk_tiers.get(chunk_path, StorageTier.WARM)
    
    def migrate_chunk(
        self,
        chunk_meta: ChunkMetadata,
        target_tier: StorageTier
    ) -> bool:
        """
        Migrate a chunk to a different storage tier.
        
        Args:
            chunk_meta: Chunk metadata
            target_tier: Target storage tier
            
        Returns:
            True if migration succeeded
        """
        try:
            source_path = Path(chunk_meta.file_path)
            if not source_path.exists():
                logger.warning(f"Chunk file not found: {source_path}")
                return False
            
            # Determine target path
            tier_config = self.tiers[target_tier]
            relative_path = source_path.relative_to(self.storage.base_path)
            target_path = Path(tier_config.path) / relative_path
            
            # Create target directory
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file with appropriate compression
            if tier_config.compression_level > 0:
                # Apply additional compression for cold tier
                self._compress_and_copy(source_path, target_path, tier_config.compression_level)
            else:
                # Simple copy for hot/warm tiers
                shutil.copy2(source_path, target_path)
            
            # Copy metadata
            source_meta = source_path.with_suffix('.json')
            target_meta = target_path.with_suffix('.json')
            if source_meta.exists():
                shutil.copy2(source_meta, target_meta)
            
            # Update tracking
            with self._lock:
                old_tier = self._chunk_tiers.get(str(source_path))
                self._chunk_tiers[str(target_path)] = target_tier
                self._migration_count += 1
                self._bytes_migrated += source_path.stat().st_size
            
            # Remove from source if not hot tier (keep hot tier as primary)
            if old_tier != StorageTier.HOT and target_tier != StorageTier.HOT:
                source_path.unlink()
                if source_meta.exists():
                    source_meta.unlink()
            
            logger.info(
                f"Migrated chunk {chunk_meta.metric_name} "
                f"from {old_tier} to {target_tier}: {target_path}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to migrate chunk {chunk_meta.file_path}: {e}")
            return False
    
    def _compress_and_copy(
        self,
        source: Path,
        target: Path,
        level: int
    ) -> None:
        """
        Copy file with compression.
        
        Args:
            source: Source file path
            target: Target file path
            level: Compression level (1-9)
        """
        import gzip
        
        with open(source, 'rb') as f_in:
            with gzip.open(target, 'wb', compresslevel=level) as f_out:
                shutil.copyfileobj(f_in, f_out)
    
    def _decompress_and_read(self, path: Path) -> bytes:
        """
        Read file, decompressing if necessary.
        
        Args:
            path: File path
            
        Returns:
            File contents
        """
        import gzip
        
        # Check if file is gzip compressed
        with open(path, 'rb') as f:
            magic = f.read(2)
        
        if magic == b'\x1f\x8b':  # gzip magic number
            with gzip.open(path, 'rb') as f:
                return f.read()
        else:
            with open(path, 'rb') as f:
                return f.read()
    
    def promote_to_hot(self, chunk_meta: ChunkMetadata) -> bool:
        """
        Promote a chunk to hot tier (in-memory cache).
        
        Args:
            chunk_meta: Chunk metadata
            
        Returns:
            True if promotion succeeded
        """
        try:
            # Load data into memory
            from .storage_engine import TimeSeriesChunk
            
            chunk = TimeSeriesChunk(
                chunk_meta.metric_name,
                chunk_meta.start_time,
                self.storage.base_path
            )
            chunk._metadata = chunk_meta
            points = chunk.load()
            
            with self._lock:
                # Evict if necessary
                if len(self._hot_cache) >= self._hot_cache_size:
                    # Remove oldest accessed
                    if self._last_access:
                        oldest = min(self._last_access.keys(), key=lambda k: self._last_access[k])
                        del self._hot_cache[oldest]
                        del self._last_access[oldest]
                
                # Add to hot cache
                cache_key = chunk_meta.file_path
                self._hot_cache[cache_key] = points
                self._last_access[cache_key] = datetime.now()
                self._chunk_tiers[cache_key] = StorageTier.HOT
            
            logger.debug(f"Promoted chunk to hot tier: {chunk_meta.file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to promote chunk to hot tier: {e}")
            return False
    
    def get_from_hot(self, chunk_path: str) -> Optional[List[DataPoint]]:
        """
        Get chunk data from hot tier cache.
        
        Args:
            chunk_path: Chunk file path
            
        Returns:
            Data points if in hot cache, None otherwise
        """
        with self._lock:
            if chunk_path in self._hot_cache:
                self._access_counts[chunk_path] += 1
                self._last_access[chunk_path] = datetime.now()
                return self._hot_cache[chunk_path]
            return None
    
    def run_tier_migration(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Run automatic tier migration for all chunks.
        
        Args:
            dry_run: If True, only report what would be done
            
        Returns:
            Statistics about migration
        """
        stats = {
            "dry_run": dry_run,
            "chunks_migrated": 0,
            "bytes_migrated": 0,
            "hot_promotions": 0,
            "errors": 0,
            "tier_distribution": {
                StorageTier.HOT: 0,
                StorageTier.WARM: 0,
                StorageTier.COLD: 0
            }
        }
        
        # Get all chunks
        all_chunks = []
        for metric in self.storage._index.get_all_metrics():
            time_range = self.storage._index.get_time_range(metric)
            if time_range:
                chunks = self.storage._index.find_chunks(metric, time_range[0], time_range[1])
                all_chunks.extend(chunks)
        
        # Determine target tier for each chunk
        for chunk_meta in all_chunks:
            target_tier = self.get_tier_for_chunk(chunk_meta)
            current_tier = self.get_chunk_tier(chunk_meta.file_path)
            
            stats["tier_distribution"][current_tier] += 1
            
            if target_tier != current_tier:
                if not dry_run:
                    success = self.migrate_chunk(chunk_meta, target_tier)
                    if success:
                        stats["chunks_migrated"] += 1
                        stats["bytes_migrated"] += chunk_meta.compressed_size
                    else:
                        stats["errors"] += 1
                else:
                    stats["chunks_migrated"] += 1
                    stats["bytes_migrated"] += chunk_meta.compressed_size
        
        # Promote frequently accessed chunks to hot tier
        hot_candidates = self._get_hot_promotion_candidates()
        for chunk_path in hot_candidates:
            # Find chunk metadata
            for chunk_meta in all_chunks:
                if chunk_meta.file_path == chunk_path:
                    if not dry_run:
                        success = self.promote_to_hot(chunk_meta)
                        if success:
                            stats["hot_promotions"] += 1
                    else:
                        stats["hot_promotions"] += 1
                    break
        
        logger.info(
            f"Tier migration complete: "
            f"{stats['chunks_migrated']} migrated, "
            f"{stats['hot_promotions']} promoted to hot"
        )
        
        return stats
    
    def _get_hot_promotion_candidates(self, count: int = 10) -> List[str]:
        """
        Get chunks that should be promoted to hot tier.
        
        Based on access frequency and recency.
        
        Args:
            count: Number of candidates to return
            
        Returns:
            List of chunk paths
        """
        with self._lock:
            # Score chunks by access count and recency
            now = datetime.now()
            scores = []
            
            for chunk_path, access_count in self._access_counts.items():
                last_access = self._last_access.get(chunk_path, now)
                hours_since_access = (now - last_access).total_seconds() / 3600
                
                # Score: higher access count is better, recent access is better
                score = access_count / (1 + hours_since_access)
                scores.append((score, chunk_path))
            
            # Return top candidates not already in hot tier
            candidates = []
            for score, chunk_path in heapq.nlargest(count * 2, scores):
                if self._chunk_tiers.get(chunk_path) != StorageTier.HOT:
                    candidates.append(chunk_path)
                    if len(candidates) >= count:
                        break
            
            return candidates
    
    def get_tier_stats(self) -> Dict[str, Any]:
        """
        Get statistics about tier distribution.
        
        Returns:
            Dictionary with tier statistics
        """
        with self._lock:
            tier_counts = defaultdict(int)
            tier_bytes = defaultdict(int)
            
            for chunk_path, tier in self._chunk_tiers.items():
                tier_counts[tier] += 1
                try:
                    size = os.path.getsize(chunk_path)
                    tier_bytes[tier] += size
                except OSError:
                    pass
            
            return {
                "tier_counts": dict(tier_counts),
                "tier_bytes": {k: v for k, v in tier_bytes.items()},
                "hot_cache_size": len(self._hot_cache),
                "hot_cache_max": self._hot_cache_size,
                "total_migrations": self._migration_count,
                "total_bytes_migrated": self._bytes_migrated
            }
    
    def get_storage_costs(self) -> Dict[str, float]:
        """
        Estimate storage costs for each tier.
        
        Returns:
            Dictionary with cost estimates per tier
        """
        # Simplified cost model (per GB per month)
        costs_per_gb = {
            StorageTier.HOT: 0.50,    # SSD
            StorageTier.WARM: 0.10,   # HDD
            StorageTier.COLD: 0.02    # Archive
        }
        
        stats = self.get_tier_stats()
        tier_bytes = stats["tier_bytes"]
        
        costs = {}
        for tier, bytes_used in tier_bytes.items():
            gb_used = bytes_used / (1024 ** 3)
            costs[tier] = gb_used * costs_per_gb[tier]
        
        costs["total"] = sum(costs.values())
        return costs


class AccessPatternAnalyzer:
    """
    Analyzes access patterns to optimize tier placement.
    """
    
    def __init__(self):
        self._access_log: List[Tuple[str, datetime, str]] = []  # (chunk_path, timestamp, operation)
        self._lock = threading.RLock()
    
    def record_access(self, chunk_path: str, operation: str = "read") -> None:
        """
        Record a chunk access.
        
        Args:
            chunk_path: Path to accessed chunk
            operation: Type of operation (read, write, etc.)
        """
        with self._lock:
            self._access_log.append((chunk_path, datetime.now(), operation))
    
    def get_access_frequency(self, chunk_path: str, hours: int = 24) -> int:
        """
        Get access frequency for a chunk.
        
        Args:
            chunk_path: Chunk path
            hours: Time window in hours
            
        Returns:
            Number of accesses in time window
        """
        with self._lock:
            cutoff = datetime.now() - timedelta(hours=hours)
            return sum(
                1 for path, ts, _ in self._access_log
                if path == chunk_path and ts > cutoff
            )
    
    def get_hot_spots(self, top_n: int = 10) -> List[Tuple[str, int]]:
        """
        Get most frequently accessed chunks.
        
        Args:
            top_n: Number of top chunks to return
            
        Returns:
            List of (chunk_path, access_count) tuples
        """
        with self._lock:
            # Count accesses in last 24 hours
            cutoff = datetime.now() - timedelta(hours=24)
            recent_accesses = [
                path for path, ts, _ in self._access_log
                if ts > cutoff
            ]
            
            # Count by chunk
            counts = defaultdict(int)
            for path in recent_accesses:
                counts[path] += 1
            
            # Return top N
            return heapq.nlargest(top_n, counts.items(), key=lambda x: x[1])
    
    def clear_old_logs(self, max_age_hours: int = 168) -> int:
        """
        Clear old access logs.
        
        Args:
            max_age_hours: Maximum age to keep
            
        Returns:
            Number of entries removed
        """
        with self._lock:
            cutoff = datetime.now() - timedelta(hours=max_age_hours)
            original_len = len(self._access_log)
            self._access_log = [
                entry for entry in self._access_log
                if entry[1] > cutoff
            ]
            return original_len - len(self._access_log)
