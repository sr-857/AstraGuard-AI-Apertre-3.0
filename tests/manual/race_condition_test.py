import threading
import time
import numpy as np
from memory_engine.memory_store import AdaptiveMemoryStore
from datetime import datetime
from core.secrets import init_secrets_manager

# Initialize secrets manager
import os
os.environ["SECRETS_MASTER_KEY"] = "dummy_key_for_testing_12345"
init_secrets_manager()

def test_thread_safety():
    """Test thread safety of retrieve method with concurrent writes."""
    store = AdaptiveMemoryStore(max_capacity=1000)

    # Populate with initial events
    for i in range(100):
        embedding = np.random.rand(384).tolist()
        metadata = {'severity': 0.5, 'type': f'event_{i}'}
        store.write(embedding, metadata)

    errors = []

    def retrieve_worker():
        """Worker that repeatedly calls retrieve."""
        try:
            for _ in range(100):
                query = np.random.rand(384).tolist()
                results = store.retrieve(query, top_k=5)
                # Basic sanity check
                assert len(results) <= 5
                time.sleep(0.001)  # Small delay to allow interleaving
        except Exception as e:
            errors.append(f"Retrieve error: {e}")

    def write_worker():
        """Worker that repeatedly calls write."""
        try:
            for i in range(100):
                embedding = np.random.rand(384).tolist()
                metadata = {'severity': 0.5, 'type': f'new_event_{i}'}
                store.write(embedding, metadata)
                time.sleep(0.001)  # Small delay to allow interleaving
        except Exception as e:
            errors.append(f"Write error: {e}")

    # Start multiple threads
    threads = []
    for _ in range(5):
        threads.append(threading.Thread(target=retrieve_worker))
        threads.append(threading.Thread(target=write_worker))

    # Start all threads
    for t in threads:
        t.start()

    # Wait for all to complete
    for t in threads:
        t.join()

    if errors:
        print(f"Errors occurred: {errors}")
        return False
    else:
        print("No race condition errors detected.")
        return True

if __name__ == "__main__":
    success = test_thread_safety()
    if success:
        print("Thread safety test passed!")
    else:
        print("Thread safety test failed!")
