"""
Backend Utilities Module

Provides utility functions for backend operations including compression,
data processing, file handling, and test data seeding.
"""

from .compression import (
    compress_file,
    decompress_file,
    compress_string,
    decompress_string,
    compress_data,
    decompress_data,
    create_archive,
    extract_archive,
    get_compression_ratio,
    CompressionFormat,
)

from .seeders import (
    DatabaseSeeder,
    MemoryStoreSeeder,
    ScenarioSeeder,
    SeedConfig,
    ScenarioType,
    quick_seed_db,
    quick_seed_telemetry,
    quick_seed_users,
)

__all__ = [
    # Compression utilities
    "compress_file",
    "decompress_file",
    "compress_string",
    "decompress_string",
    "compress_data",
    "decompress_data",
    "create_archive",
    "extract_archive",
    "get_compression_ratio",
    "CompressionFormat",
    # Seeding utilities
    "DatabaseSeeder",
    "MemoryStoreSeeder",
    "ScenarioSeeder",
    "SeedConfig",
    "ScenarioType",
    "quick_seed_db",
    "quick_seed_telemetry",
    "quick_seed_users",
]
