"""
Compression Layer using Zstandard (zstd)
Provides high-performance compression/decompression for network payloads.
"""

import zstandard as zstd
import logging

logger = logging.getLogger(__name__)

# Create global compressor/decompressor objects to reuse dictionaries/context
# Level 3 is default, good balance.
compressor = zstd.ZstdCompressor(level=3)
decompressor = zstd.ZstdDecompressor()

def compress_payload(data: bytes) -> bytes:
    """
    Compress bytes using Zstandard.

    Args:
        data: Raw bytes to compress

    Returns:
        Compressed bytes
    """
    try:
        return compressor.compress(data)
    except Exception as e:
        logger.error(f"Compression failed: {e}")
        raise

def decompress_payload(data: bytes) -> bytes:
    """
    Decompress bytes using Zstandard.

    Args:
        data: Compressed bytes

    Returns:
        Decompressed bytes
    """
    try:
        return decompressor.decompress(data)
    except Exception as e:
        logger.error(f"Decompression failed: {e}")
        raise
