"""
Unit tests for Adaptive Memory Store
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
import sys
import os
import multiprocessing as mp
import asyncio

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from memory_engine.memory_store import AdaptiveMemoryStore, MemoryEvent


# Module-level worker function for multiprocessing (must be at module level to be picklable)
def _worker_concurrent_access(args):
    """Worker function for concurrent access testing"""
    process_id, temp_store_path = args
    
    async def _async_worker():
        try:
            # Create a new memory store instance for this process
            worker_memory = AdaptiveMemoryStore(decay_lambda=0.1, max_capacity=100)
            worker_memory.storage_path = temp_store_path

            # Load existing data
            worker_memory.load()

            # Add a new event
            embedding = np.random.rand(384)
            metadata = {'severity': 0.5, 'type': f'process_{process_id}_event'}
            await worker_memory.write(embedding, metadata)

            # Save the updated data
            await worker_memory.save()

            return True
        except Exception as e:
            print(f"Process {process_id} failed: {e}")
            return False

    return asyncio.run(_async_worker())


class TestAdaptiveMemoryStore:
    """Test suite for AdaptiveMemoryStore"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.memory = AdaptiveMemoryStore(decay_lambda=0.1, max_capacity=100)
    
    def test_initialization(self):
        """Test memory store initializes correctly"""
        assert self.memory.decay_lambda == 0.1
        assert self.memory.max_capacity == 100
        assert len(self.memory.memory) == 0
    
    async def test_write_event(self):
        """Test writing events to memory"""
        embedding = np.random.rand(384)
        metadata = {'severity': 0.8, 'type': 'power_fault'}
        
        await self.memory.write(embedding, metadata)
        
        assert len(self.memory.memory) == 1
        assert self.memory.memory[0].metadata['type'] == 'power_fault'
    
    async def test_retrieve_similar(self):
        """Test retrieving similar events"""
        # Add some events
        for i in range(5):
            embedding = np.random.rand(384)
            metadata = {'severity': 0.5 + i * 0.1, 'type': f'event_{i}'}
            await self.memory.write(embedding, metadata)
        
        # Query
        query = np.random.rand(384)
        results = self.memory.retrieve(query, top_k=3)
        
        assert len(results) <= 3
        assert all(isinstance(r, tuple) and len(r) == 3 for r in results)
    
    async def test_recurrence_detection(self):
        """Test that similar events boost recurrence count"""
        embedding = np.random.rand(384)
        metadata = {'severity': 0.8, 'type': 'recurring_fault'}
        
        # Write same event twice
        await self.memory.write(embedding, metadata)
        await self.memory.write(embedding, metadata)
        
        # Should only have 1 event with recurrence_count = 2
        assert len(self.memory.memory) == 1
        assert self.memory.memory[0].recurrence_count == 2
    
    async def test_prune_old_events(self):
        """Test pruning removes old events"""
        # Add old event
        old_embedding = np.random.rand(384)
        old_metadata = {'severity': 0.5, 'type': 'old_event'}
        old_time = datetime.now() - timedelta(hours=48)
        await self.memory.write(old_embedding, old_metadata, timestamp=old_time)
        
        # Add recent event
        new_embedding = np.random.rand(384)
        new_metadata = {'severity': 0.5, 'type': 'new_event'}
        await self.memory.write(new_embedding, new_metadata)
        
        # Prune events older than 24 hours
        pruned = self.memory.prune(max_age_hours=24, keep_critical=False)
        
        assert pruned == 1
        assert len(self.memory.memory) == 1
        assert self.memory.memory[0].metadata['type'] == 'new_event'
    
    async def test_critical_events_not_pruned(self):
        """Test that critical events are never pruned"""
        # Add old critical event
        embedding = np.random.rand(384)
        metadata = {'severity': 0.9, 'type': 'critical_fault', 'critical': True}
        old_time = datetime.now() - timedelta(hours=72)
        await self.memory.write(embedding, metadata, timestamp=old_time)
        
        # Prune
        pruned = self.memory.prune(max_age_hours=24, keep_critical=True)
        
        # Critical event should remain
        assert len(self.memory.memory) == 1
        assert self.memory.memory[0].is_critical
    
    async def test_replay_time_range(self):
        """Test replaying events within time range"""
        # Add events at different times
        now = datetime.now()
        for i in range(5):
            embedding = np.random.rand(384)
            metadata = {'severity': 0.5, 'type': f'event_{i}', 'timestamp': i}
            timestamp = now - timedelta(hours=i)
            await self.memory.write(embedding, metadata, timestamp=timestamp)
        
        # Replay last 2 hours
        start = now - timedelta(hours=2)
        end = now
        events = self.memory.replay(start, end)
        
        assert len(events) <= 3  # Events from 0, 1, 2 hours ago
    
    async def test_get_stats(self):
        """Test memory statistics"""
        # Add some events
        for i in range(3):
            embedding = np.random.rand(384)
            metadata = {'severity': 0.5, 'critical': i == 0}
            await self.memory.write(embedding, metadata)

        stats = self.memory.get_stats()

        assert stats['total_events'] == 3
        assert stats['critical_events'] == 1
        assert 'avg_age_hours' in stats
        assert 'max_recurrence' in stats

    async def test_load_failure_clears_memory(self):
        """Test that load failure clears memory to prevent stale data"""
        # Add some events to memory
        for i in range(3):
            embedding = np.random.rand(384)
            metadata = {'severity': 0.5, 'type': f'event_{i}'}
            await self.memory.write(embedding, metadata)

        assert len(self.memory.memory) == 3

        # Create a corrupted file to simulate load failure
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pkl') as f:
            f.write(b'corrupted data')
            corrupted_path = f.name

        # Temporarily change storage path to corrupted file
        original_path = self.memory.storage_path
        self.memory.storage_path = corrupted_path

        try:
            # Attempt to load, should fail and clear memory
            result = self.memory.load()
            assert result is False
            assert len(self.memory.memory) == 0  # Memory should be cleared
        finally:
            # Restore original path and clean up
            self.memory.storage_path = original_path
            os.unlink(corrupted_path)

    async def test_concurrent_save_load_operations(self):
        """Test concurrent save and load operations across multiple processes"""
        import tempfile
        import os

        # Create a temporary file for testing
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pkl') as f:
            temp_store_path = f.name

        try:
            # Initialize memory store with temp path
            self.memory.storage_path = temp_store_path

            # Add initial events
            for i in range(5):
                embedding = np.random.rand(384)
                metadata = {'severity': 0.5, 'type': f'initial_event_{i}'}
                await self.memory.write(embedding, metadata)

            # Save initial state
            await self.memory.save()

            # Test concurrent operations using multiprocessing
            num_processes = 4
            with mp.Pool(processes=num_processes) as pool:
                # Each process will perform save/load operations
                args = [(i, temp_store_path) for i in range(num_processes)]
                results = pool.map(_worker_concurrent_access, args)

            # Verify all processes succeeded
            assert all(results), "Some concurrent operations failed"

            # Reload and verify final state
            new_memory = AdaptiveMemoryStore()
            new_memory.storage_path = temp_store_path
            loaded = new_memory.load()
            assert loaded, "Failed to load final state"

            # Should have at least the initial 5 events plus events from processes
            assert len(new_memory.memory) >= 5, f"Expected at least 5 events, got {len(new_memory.memory)}"

            # Verify no corruption - all events should have valid metadata
            for event in new_memory.memory:
                assert 'type' in event.metadata
                assert isinstance(event.metadata['type'], str)

        finally:
            # Clean up temp file and lock file
            if os.path.exists(temp_store_path):
                os.unlink(temp_store_path)
            lock_file = temp_store_path + ".lock"
            if os.path.exists(lock_file):
                os.unlink(lock_file)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
