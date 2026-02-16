"""
Tests for the encryption system
"""

import pytest
import os
import tempfile
import shutil
from datetime import datetime, timedelta

from security import (
    init_encryption_system,
    get_encryption_status,
    encrypt_data,
    decrypt_data,
    EncryptionEngine,
    EncryptedData,
    EncryptionAlgorithm,
    HSMProvider,
    ComplianceStandard,
)


@pytest.fixture
def temp_storage():
    """Create temporary storage for tests."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
async def encryption_system(temp_storage):
    """Initialize encryption system for tests."""
    # Set required environment variable
    os.environ["MASTER_KEY_SEED"] = "test-master-key-seed-for-testing-only"
    
    status = await init_encryption_system(
        master_key="test-master-key-32-bytes-long!!",
        storage_path=temp_storage,
        enable_hsm=False,  # Use mock HSM
        fips_enabled=False,  # Disable FIPS for testing
        auto_rotation=False,  # Disable auto-rotation for tests
    )
    
    yield status
    
    # Cleanup
    if "MASTER_KEY_SEED" in os.environ:
        del os.environ["MASTER_KEY_SEED"]


@pytest.mark.asyncio
async def test_encryption_system_initialization(encryption_system):
    """Test that encryption system initializes correctly."""
    status = encryption_system
    
    assert status["encryption_engine"]["status"] == "initialized"
    assert status["key_hierarchy"]["status"] == "initialized"
    assert status["compliance"]["status"] == "initialized"
    assert status["key_rotation"]["status"] == "initialized"
    assert status["key_recovery"]["status"] == "initialized"
    assert status["field_encryption"]["status"] == "initialized"
    assert status["zero_knowledge"]["status"] == "initialized"


@pytest.mark.asyncio
async def test_basic_encrypt_decrypt(encryption_system):
    """Test basic encryption and decryption."""
    plaintext = "Hello, World! This is sensitive data."
    
    # Encrypt
    encrypted_data, encrypted_dek = encrypt_data(plaintext)
    
    assert encrypted_data is not None
    assert encrypted_dek is not None
    assert encrypted_data.ciphertext is not None
    assert encrypted_data.iv is not None
    assert encrypted_data.tag is not None
    
    # Decrypt
    decrypted = decrypt_data(encrypted_data, encrypted_dek)
    
    assert decrypted.decode() == plaintext


@pytest.mark.asyncio
async def test_encrypt_decrypt_bytes(encryption_system):
    """Test encryption of binary data."""
    plaintext = b"Binary data \x00\x01\x02\x03"
    
    encrypted_data, encrypted_dek = encrypt_data(plaintext)
    decrypted = decrypt_data(encrypted_data, encrypted_dek)
    
    assert decrypted == plaintext


@pytest.mark.asyncio
async def test_encrypt_decrypt_with_aad(encryption_system):
    """Test encryption with additional authenticated data."""
    plaintext = "Sensitive data"
    aad = b"contextual-data"
    
    encrypted_data, encrypted_dek = encrypt_data(plaintext, associated_data=aad)
    decrypted = decrypt_data(encrypted_data, encrypted_dek, associated_data=aad)
    
    assert decrypted.decode() == plaintext


@pytest.mark.asyncio
async def test_encryption_performance(encryption_system):
    """Test that encryption meets <5ms performance requirement."""
    import time
    
    engine = encryption_system["encryption_engine"]
    
    plaintext = "Test data for performance measurement"
    
    # Warm up
    for _ in range(10):
        enc, dek = encrypt_data(plaintext)
        decrypt_data(enc, dek)
    
    # Measure encryption
    times = []
    for _ in range(100):
        start = time.perf_counter()
        enc, dek = encrypt_data(plaintext)
        elapsed_ms = (time.perf_counter() - start) * 1000
        times.append(elapsed_ms)
    
    avg_time = sum(times) / len(times)
    max_time = max(times)
    p99 = sorted(times)[int(len(times) * 0.99)]
    
    # Assert performance requirements
    assert avg_time < 5.0, f"Average encryption time {avg_time:.2f}ms exceeds 5ms"
    assert p99 < 5.0, f"P99 encryption time {p99:.2f}ms exceeds 5ms"
    
    print(f"Encryption performance: avg={avg_time:.2f}ms, max={max_time:.2f}ms, p99={p99:.2f}ms")


@pytest.mark.asyncio
async def test_encrypted_data_serialization(encryption_system):
    """Test serialization and deserialization of encrypted data."""
    plaintext = "Test serialization"
    
    encrypted_data, encrypted_dek = encrypt_data(plaintext)
    
    # Serialize
    data_dict = encrypted_data.to_dict()
    
    # Deserialize
    restored = EncryptedData.from_dict(data_dict)
    
    # Decrypt with restored data
    decrypted = decrypt_data(restored, encrypted_dek)
    
    assert decrypted.decode() == plaintext


@pytest.mark.asyncio
async def test_encryption_status(encryption_system):
    """Test getting encryption system status."""
    status = get_encryption_status()
    
    assert "components" in status
    assert "encryption_engine" in status["components"]
    assert "key_hierarchy" in status["components"]


@pytest.mark.asyncio
async def test_multiple_encryption_operations(encryption_system):
    """Test multiple consecutive encryption operations."""
    plaintexts = [f"Message {i}" for i in range(100)]
    
    encrypted_pairs = []
    for plaintext in plaintexts:
        enc, dek = encrypt_data(plaintext)
        encrypted_pairs.append((enc, dek))
    
    # Verify all can be decrypted
    for i, (enc, dek) in enumerate(encrypted_pairs):
        decrypted = decrypt_data(enc, dek)
        assert decrypted.decode() == plaintexts[i]


@pytest.mark.asyncio
async def test_encryption_with_different_sizes(encryption_system):
    """Test encryption with various data sizes."""
    sizes = [1, 10, 100, 1000, 10000, 100000]
    
    for size in sizes:
        plaintext = "A" * size
        enc, dek = encrypt_data(plaintext)
        decrypted = decrypt_data(enc, dek)
        assert decrypted.decode() == plaintext


@pytest.mark.asyncio
async def test_encryption_engine_direct(encryption_system):
    """Test using encryption engine directly."""
    from security import get_encryption_engine
    
    engine = get_encryption_engine()
    
    plaintext = b"Direct engine test"
    enc, dek = engine.encrypt(plaintext)
    decrypted = engine.decrypt(enc, dek)
    
    assert decrypted == plaintext
    
    # Check performance stats
    stats = engine.get_performance_stats()
    assert "avg_ms" in stats
    assert "count" in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
