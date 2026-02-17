"""
Tests for Compression Utilities

Comprehensive test suite for the compression utilities module.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from src.backend.utils.compression import (
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


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    shutil.rmtree(tmp)


@pytest.fixture
def sample_file(temp_dir):
    """Create a sample text file for testing."""
    file_path = temp_dir / "sample.txt"
    content = "Hello, World!\n" * 1000  # Create some repetitive content
    file_path.write_text(content)
    return file_path


@pytest.fixture
def sample_files(temp_dir):
    """Create multiple sample files for archive testing."""
    files = []
    for i in range(3):
        file_path = temp_dir / f"file{i}.txt"
        content = f"Content of file {i}\n" * 100
        file_path.write_text(content)
        files.append(file_path)
    return files


class TestFileCompression:
    """Test file compression and decompression."""

    def test_compress_file_gzip(self, sample_file, temp_dir):
        """Test gzip file compression."""
        compressed = compress_file(sample_file, format=CompressionFormat.GZIP)
        assert compressed.exists()
        assert compressed.suffix == ".gz"
        assert compressed.stat().st_size < sample_file.stat().st_size

    def test_compress_file_bz2(self, sample_file, temp_dir):
        """Test bz2 file compression."""
        compressed = compress_file(sample_file, format=CompressionFormat.BZ2)
        assert compressed.exists()
        assert compressed.suffix == ".bz2"
        assert compressed.stat().st_size < sample_file.stat().st_size

    def test_compress_file_zlib(self, sample_file, temp_dir):
        """Test zlib file compression."""
        compressed = compress_file(sample_file, format=CompressionFormat.ZLIB)
        assert compressed.exists()
        assert compressed.suffix == ".zlib"
        assert compressed.stat().st_size < sample_file.stat().st_size

    def test_compress_file_with_custom_output(self, sample_file, temp_dir):
        """Test compression with custom output path."""
        output_path = temp_dir / "custom_output.gz"
        compressed = compress_file(sample_file, output_path=output_path)
        assert compressed == output_path
        assert output_path.exists()

    def test_compress_file_not_found(self, temp_dir):
        """Test compression of non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            compress_file(temp_dir / "nonexistent.txt")

    def test_decompress_file_gzip(self, sample_file, temp_dir):
        """Test gzip file decompression."""
        compressed = compress_file(sample_file, format=CompressionFormat.GZIP)
        decompressed = decompress_file(compressed)
        
        assert decompressed.exists()
        assert decompressed.read_text() == sample_file.read_text()

    def test_decompress_file_bz2(self, sample_file, temp_dir):
        """Test bz2 file decompression."""
        compressed = compress_file(sample_file, format=CompressionFormat.BZ2)
        decompressed = decompress_file(compressed)
        
        assert decompressed.exists()
        assert decompressed.read_text() == sample_file.read_text()

    def test_decompress_file_zlib(self, sample_file, temp_dir):
        """Test zlib file decompression."""
        compressed = compress_file(sample_file, format=CompressionFormat.ZLIB)
        decompressed = decompress_file(compressed)
        
        assert decompressed.exists()
        assert decompressed.read_text() == sample_file.read_text()

    def test_decompress_file_auto_detect(self, sample_file, temp_dir):
        """Test auto-detection of compression format."""
        compressed = compress_file(sample_file, format=CompressionFormat.GZIP)
        decompressed = decompress_file(compressed)  # No format specified
        
        assert decompressed.read_text() == sample_file.read_text()

    def test_decompress_file_not_found(self, temp_dir):
        """Test decompression of non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            decompress_file(temp_dir / "nonexistent.gz")

    def test_compression_with_different_levels(self, sample_file, temp_dir):
        """Test different compression levels."""
        compressed_low = compress_file(
            sample_file, 
            output_path=temp_dir / "low.gz",
            compression_level=1
        )
        compressed_high = compress_file(
            sample_file, 
            output_path=temp_dir / "high.gz",
            compression_level=9
        )
        
        # Higher compression should result in smaller file
        assert compressed_high.stat().st_size <= compressed_low.stat().st_size


class TestStringCompression:
    """Test string compression and decompression."""

    def test_compress_decompress_string(self):
        """Test string compression and decompression."""
        original = "Hello, World!" * 100
        compressed = compress_string(original)
        decompressed = decompress_string(compressed)
        
        assert decompressed == original
        assert len(compressed) < len(original.encode())

    def test_compress_string_different_formats(self):
        """Test string compression with different formats."""
        original = "Test data " * 50
        
        for format in [CompressionFormat.GZIP, CompressionFormat.BZ2, CompressionFormat.ZLIB]:
            compressed = compress_string(original, format=format)
            decompressed = decompress_string(compressed, format=format)
            assert decompressed == original

    def test_compress_empty_string(self):
        """Test compression of empty string."""
        compressed = compress_string("")
        decompressed = decompress_string(compressed)
        assert decompressed == ""

    def test_compress_unicode_string(self):
        """Test compression of unicode strings."""
        original = "Hello 世界 🌍" * 50
        compressed = compress_string(original)
        decompressed = decompress_string(compressed)
        assert decompressed == original


class TestDataCompression:
    """Test byte data compression and decompression."""

    def test_compress_decompress_data(self):
        """Test data compression and decompression."""
        original = b"Test data" * 100
        compressed = compress_data(original)
        decompressed = decompress_data(compressed)
        
        assert decompressed == original
        assert len(compressed) < len(original)

    def test_compress_data_different_formats(self):
        """Test data compression with different formats."""
        original = b"Binary data " * 50
        
        for format in [CompressionFormat.GZIP, CompressionFormat.BZ2, CompressionFormat.ZLIB]:
            compressed = compress_data(original, format=format)
            decompressed = decompress_data(compressed, format=format)
            assert decompressed == original

    def test_compress_empty_data(self):
        """Test compression of empty data."""
        compressed = compress_data(b"")
        decompressed = decompress_data(compressed)
        assert decompressed == b""

    def test_compress_data_with_compression_levels(self):
        """Test data compression with different levels."""
        original = b"Repeating data " * 100
        
        compressed_low = compress_data(original, compression_level=1)
        compressed_high = compress_data(original, compression_level=9)
        
        # Both should decompress correctly
        assert decompress_data(compressed_low) == original
        assert decompress_data(compressed_high) == original
        
        # Higher compression should be smaller or equal
        assert len(compressed_high) <= len(compressed_low)


class TestArchiveOperations:
    """Test archive creation and extraction."""

    def test_create_zip_archive(self, sample_files, temp_dir):
        """Test ZIP archive creation."""
        archive_path = temp_dir / "archive.zip"
        result = create_archive(sample_files, archive_path, format=CompressionFormat.ZIP)
        
        assert result.exists()
        assert result == archive_path

    def test_create_tar_gz_archive(self, sample_files, temp_dir):
        """Test TAR.GZ archive creation."""
        archive_path = temp_dir / "archive.tar.gz"
        result = create_archive(sample_files, archive_path, format=CompressionFormat.TAR_GZ)
        
        assert result.exists()
        assert result == archive_path

    def test_create_tar_bz2_archive(self, sample_files, temp_dir):
        """Test TAR.BZ2 archive creation."""
        archive_path = temp_dir / "archive.tar.bz2"
        result = create_archive(sample_files, archive_path, format=CompressionFormat.TAR_BZ2)
        
        assert result.exists()
        assert result == archive_path

    def test_extract_zip_archive(self, sample_files, temp_dir):
        """Test ZIP archive extraction."""
        archive_path = temp_dir / "archive.zip"
        create_archive(sample_files, archive_path, format=CompressionFormat.ZIP)
        
        extract_dir = temp_dir / "extracted"
        result = extract_archive(archive_path, extract_dir)
        
        assert result.exists()
        assert len(list(extract_dir.iterdir())) == len(sample_files)
        
        # Verify content
        for original_file in sample_files:
            extracted_file = extract_dir / original_file.name
            assert extracted_file.exists()
            assert extracted_file.read_text() == original_file.read_text()

    def test_extract_tar_gz_archive(self, sample_files, temp_dir):
        """Test TAR.GZ archive extraction."""
        archive_path = temp_dir / "archive.tar.gz"
        create_archive(sample_files, archive_path, format=CompressionFormat.TAR_GZ)
        
        extract_dir = temp_dir / "extracted"
        result = extract_archive(archive_path, extract_dir)
        
        assert result.exists()
        assert len(list(extract_dir.iterdir())) == len(sample_files)

    def test_extract_tar_bz2_archive(self, sample_files, temp_dir):
        """Test TAR.BZ2 archive extraction."""
        archive_path = temp_dir / "archive.tar.bz2"
        create_archive(sample_files, archive_path, format=CompressionFormat.TAR_BZ2)
        
        extract_dir = temp_dir / "extracted"
        result = extract_archive(archive_path, extract_dir)
        
        assert result.exists()
        assert len(list(extract_dir.iterdir())) == len(sample_files)

    def test_extract_archive_auto_detect(self, sample_files, temp_dir):
        """Test auto-detection of archive format during extraction."""
        archive_path = temp_dir / "archive.zip"
        create_archive(sample_files, archive_path, format=CompressionFormat.ZIP)
        
        extract_dir = temp_dir / "extracted"
        result = extract_archive(archive_path, extract_dir)  # No format specified
        
        assert result.exists()
        assert len(list(extract_dir.iterdir())) == len(sample_files)

    def test_create_archive_file_not_found(self, temp_dir):
        """Test archive creation with non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            create_archive([temp_dir / "nonexistent.txt"], temp_dir / "archive.zip")

    def test_extract_archive_not_found(self, temp_dir):
        """Test extraction of non-existent archive raises error."""
        with pytest.raises(FileNotFoundError):
            extract_archive(temp_dir / "nonexistent.zip", temp_dir / "extracted")


class TestCompressionRatio:
    """Test compression ratio calculation."""

    def test_compression_ratio_basic(self):
        """Test basic compression ratio calculation."""
        ratio = get_compression_ratio(1000, 250)
        assert ratio == 4.0

    def test_compression_ratio_no_compression(self):
        """Test ratio when sizes are equal."""
        ratio = get_compression_ratio(1000, 1000)
        assert ratio == 1.0

    def test_compression_ratio_expansion(self):
        """Test ratio when compressed is larger."""
        ratio = get_compression_ratio(100, 200)
        assert ratio == 0.5

    def test_compression_ratio_zero_compressed(self):
        """Test ratio with zero compressed size."""
        ratio = get_compression_ratio(1000, 0)
        assert ratio == 0.0

    def test_real_compression_ratio(self, sample_file):
        """Test compression ratio with real file."""
        compressed = compress_file(sample_file)
        
        original_size = sample_file.stat().st_size
        compressed_size = compressed.stat().st_size
        ratio = get_compression_ratio(original_size, compressed_size)
        
        # For repetitive content, expect good compression
        assert ratio > 1.0


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_compress_large_data(self):
        """Test compression of large data."""
        large_data = b"X" * 10_000_000  # 10 MB
        compressed = compress_data(large_data)
        decompressed = decompress_data(compressed)
        
        assert decompressed == large_data
        assert len(compressed) < len(large_data)

    def test_compress_random_data(self):
        """Test compression of random (incompressible) data."""
        import random
        random_data = bytes([random.randint(0, 255) for _ in range(1000)])
        
        compressed = compress_data(random_data)
        decompressed = decompress_data(compressed)
        
        assert decompressed == random_data
        # Random data may not compress well, so just verify correctness

    def test_multiple_compression_cycles(self):
        """Test multiple compression/decompression cycles."""
        original = "Test data " * 100
        
        # Compress and decompress multiple times
        for _ in range(3):
            compressed = compress_string(original)
            original = decompress_string(compressed)
        
        assert original == "Test data " * 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
