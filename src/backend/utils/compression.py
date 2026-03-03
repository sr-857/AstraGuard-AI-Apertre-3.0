"""
Compression Utilities

Provides compression and decompression utilities for files, strings, and data.
Supports multiple compression formats including gzip, zlib, and bz2.

Features:
- File compression/decompression (gzip, bz2)
- String/bytes compression
- Archive creation (zip, tar)
- Compression ratio calculation
- Memory-efficient streaming for large files
"""

import gzip
import bz2
import zlib
import zipfile
import tarfile
import logging
import shutil
from pathlib import Path
from typing import Union, Optional, List, Dict, Any
from enum import Enum
import io

logger = logging.getLogger(__name__)


class CompressionFormat(Enum):
    """Supported compression formats."""
    GZIP = "gzip"
    BZ2 = "bz2"
    ZLIB = "zlib"
    ZIP = "zip"
    TAR_GZ = "tar.gz"
    TAR_BZ2 = "tar.bz2"


def compress_file(
    input_path: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
    format: CompressionFormat = CompressionFormat.GZIP,
    compression_level: int = 9
) -> Path:
    """
    Compress a file using the specified format.

    Args:
        input_path: Path to the file to compress
        output_path: Path for the compressed file (auto-generated if None)
        format: Compression format to use
        compression_level: Compression level (1-9, where 9 is maximum)

    Returns:
        Path to the compressed file

    Raises:
        FileNotFoundError: If input file doesn't exist
        ValueError: If compression format is unsupported

    Example:
        >>> compressed = compress_file("data.log", format=CompressionFormat.GZIP)
        >>> print(compressed)
        data.log.gz
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # Auto-generate output path if not provided
    if output_path is None:
        extension_map = {
            CompressionFormat.GZIP: ".gz",
            CompressionFormat.BZ2: ".bz2",
            CompressionFormat.ZLIB: ".zlib",
        }
        ext = extension_map.get(format, ".compressed")
        output_path = input_path.with_suffix(input_path.suffix + ext)
    else:
        output_path = Path(output_path)

    logger.info(f"Compressing {input_path} to {output_path} using {format.value}")

    try:
        if format == CompressionFormat.GZIP:
            with open(input_path, 'rb') as f_in:
                with gzip.open(output_path, 'wb', compresslevel=compression_level) as f_out:
                    shutil.copyfileobj(f_in, f_out)
        elif format == CompressionFormat.BZ2:
            with open(input_path, 'rb') as f_in:
                with bz2.open(output_path, 'wb', compresslevel=compression_level) as f_out:
                    shutil.copyfileobj(f_in, f_out)
        elif format == CompressionFormat.ZLIB:
            with open(input_path, 'rb') as f_in:
                data = f_in.read()
                compressed = zlib.compress(data, level=compression_level)
                with open(output_path, 'wb') as f_out:
                    f_out.write(compressed)
        else:
            raise ValueError(f"Unsupported compression format: {format}")

        original_size = input_path.stat().st_size
        compressed_size = output_path.stat().st_size
        ratio = get_compression_ratio(original_size, compressed_size)
        logger.info(f"Compression complete. Ratio: {ratio:.2f}x")

        return output_path

    except Exception as e:
        logger.error(f"Compression failed: {e}")
        raise


def decompress_file(
    input_path: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
    format: Optional[CompressionFormat] = None
) -> Path:
    """
    Decompress a file.

    Args:
        input_path: Path to the compressed file
        output_path: Path for the decompressed file (auto-generated if None)
        format: Compression format (auto-detected if None)

    Returns:
        Path to the decompressed file

    Raises:
        FileNotFoundError: If input file doesn't exist
        ValueError: If format cannot be determined

    Example:
        >>> decompressed = decompress_file("data.log.gz")
        >>> print(decompressed)
        data.log
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # Auto-detect format from extension if not provided
    if format is None:
        suffix = input_path.suffix.lower()
        format_map = {
            '.gz': CompressionFormat.GZIP,
            '.bz2': CompressionFormat.BZ2,
            '.zlib': CompressionFormat.ZLIB,
        }
        format = format_map.get(suffix)
        if format is None:
            raise ValueError(f"Cannot auto-detect compression format for: {input_path}")

    # Auto-generate output path if not provided
    if output_path is None:
        if input_path.suffix in ['.gz', '.bz2', '.zlib']:
            output_path = input_path.with_suffix('')
        else:
            output_path = input_path.with_suffix('.decompressed')
    else:
        output_path = Path(output_path)

    logger.info(f"Decompressing {input_path} to {output_path} using {format.value}")

    try:
        if format == CompressionFormat.GZIP:
            with gzip.open(input_path, 'rb') as f_in:
                with open(output_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        elif format == CompressionFormat.BZ2:
            with bz2.open(input_path, 'rb') as f_in:
                with open(output_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        elif format == CompressionFormat.ZLIB:
            with open(input_path, 'rb') as f_in:
                compressed = f_in.read()
                decompressed = zlib.decompress(compressed)
                with open(output_path, 'wb') as f_out:
                    f_out.write(decompressed)
        else:
            raise ValueError(f"Unsupported compression format: {format}")

        logger.info(f"Decompression complete")
        return output_path

    except Exception as e:
        logger.error(f"Decompression failed: {e}")
        raise


def compress_string(
    data: str,
    format: CompressionFormat = CompressionFormat.ZLIB,
    compression_level: int = 9
) -> bytes:
    """
    Compress a string to bytes.

    Args:
        data: String to compress
        format: Compression format
        compression_level: Compression level (1-9)

    Returns:
        Compressed bytes

    Example:
        >>> text = "Hello, World!" * 100
        >>> compressed = compress_string(text)
        >>> len(compressed) < len(text.encode())
        True
    """
    data_bytes = data.encode('utf-8')
    return compress_data(data_bytes, format, compression_level)


def decompress_string(
    compressed_data: bytes,
    format: CompressionFormat = CompressionFormat.ZLIB
) -> str:
    """
    Decompress bytes to a string.

    Args:
        compressed_data: Compressed bytes
        format: Compression format

    Returns:
        Decompressed string

    Example:
        >>> text = "Hello, World!" * 100
        >>> compressed = compress_string(text)
        >>> decompressed = decompress_string(compressed)
        >>> text == decompressed
        True
    """
    decompressed_bytes = decompress_data(compressed_data, format)
    return decompressed_bytes.decode('utf-8')


def compress_data(
    data: bytes,
    format: CompressionFormat = CompressionFormat.ZLIB,
    compression_level: int = 9
) -> bytes:
    """
    Compress bytes using the specified format.

    Args:
        data: Bytes to compress
        format: Compression format
        compression_level: Compression level (1-9)

    Returns:
        Compressed bytes

    Raises:
        ValueError: If compression format is unsupported

    Example:
        >>> data = b"test data" * 100
        >>> compressed = compress_data(data, CompressionFormat.GZIP)
        >>> len(compressed) < len(data)
        True
    """
    try:
        if format == CompressionFormat.GZIP:
            return gzip.compress(data, compresslevel=compression_level)
        elif format == CompressionFormat.BZ2:
            return bz2.compress(data, compresslevel=compression_level)
        elif format == CompressionFormat.ZLIB:
            return zlib.compress(data, level=compression_level)
        else:
            raise ValueError(f"Unsupported compression format for data: {format}")
    except Exception as e:
        logger.error(f"Data compression failed: {e}")
        raise


def decompress_data(
    compressed_data: bytes,
    format: CompressionFormat = CompressionFormat.ZLIB
) -> bytes:
    """
    Decompress bytes.

    Args:
        compressed_data: Compressed bytes
        format: Compression format

    Returns:
        Decompressed bytes

    Raises:
        ValueError: If compression format is unsupported

    Example:
        >>> data = b"test data" * 100
        >>> compressed = compress_data(data)
        >>> decompressed = decompress_data(compressed)
        >>> data == decompressed
        True
    """
    try:
        if format == CompressionFormat.GZIP:
            return gzip.decompress(compressed_data)
        elif format == CompressionFormat.BZ2:
            return bz2.decompress(compressed_data)
        elif format == CompressionFormat.ZLIB:
            return zlib.decompress(compressed_data)
        else:
            raise ValueError(f"Unsupported compression format for data: {format}")
    except Exception as e:
        logger.error(f"Data decompression failed: {e}")
        raise


def create_archive(
    files: List[Union[str, Path]],
    archive_path: Union[str, Path],
    format: CompressionFormat = CompressionFormat.ZIP,
    base_dir: Optional[Union[str, Path]] = None
) -> Path:
    """
    Create an archive containing multiple files.

    Args:
        files: List of files to include in the archive
        archive_path: Path for the archive file
        format: Archive format (ZIP, TAR_GZ, or TAR_BZ2)
        base_dir: Base directory for relative paths (None for absolute)

    Returns:
        Path to the created archive

    Raises:
        FileNotFoundError: If any input file doesn't exist
        ValueError: If archive format is unsupported

    Example:
        >>> files = ["file1.txt", "file2.txt"]
        >>> archive = create_archive(files, "backup.zip")
        >>> archive.exists()
        True
    """
    archive_path = Path(archive_path)
    files = [Path(f) for f in files]

    # Validate all files exist
    for file_path in files:
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

    logger.info(f"Creating {format.value} archive: {archive_path}")

    try:
        if format == CompressionFormat.ZIP:
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path in files:
                    arcname = file_path.name if base_dir is None else file_path.relative_to(base_dir)
                    zipf.write(file_path, arcname=str(arcname))
                    logger.debug(f"Added {file_path} as {arcname}")

        elif format in [CompressionFormat.TAR_GZ, CompressionFormat.TAR_BZ2]:
            mode = 'w:gz' if format == CompressionFormat.TAR_GZ else 'w:bz2'
            with tarfile.open(archive_path, mode) as tarf:
                for file_path in files:
                    arcname = file_path.name if base_dir is None else file_path.relative_to(base_dir)
                    tarf.add(file_path, arcname=str(arcname))
                    logger.debug(f"Added {file_path} as {arcname}")
        else:
            raise ValueError(f"Unsupported archive format: {format}")

        logger.info(f"Archive created successfully: {archive_path}")
        return archive_path

    except Exception as e:
        logger.error(f"Archive creation failed: {e}")
        raise


def extract_archive(
    archive_path: Union[str, Path],
    extract_dir: Union[str, Path],
    format: Optional[CompressionFormat] = None
) -> Path:
    """
    Extract an archive.

    Args:
        archive_path: Path to the archive file
        extract_dir: Directory to extract files to
        format: Archive format (auto-detected if None)

    Returns:
        Path to the extraction directory

    Raises:
        FileNotFoundError: If archive file doesn't exist
        ValueError: If archive format cannot be determined

    Example:
        >>> extract_dir = extract_archive("backup.zip", "restored/")
        >>> extract_dir.exists()
        True
    """
    archive_path = Path(archive_path)
    extract_dir = Path(extract_dir)

    if not archive_path.exists():
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    # Auto-detect format from extension if not provided
    if format is None:
        suffix = archive_path.suffix.lower()
        if suffix == '.zip':
            format = CompressionFormat.ZIP
        elif archive_path.name.endswith('.tar.gz'):
            format = CompressionFormat.TAR_GZ
        elif archive_path.name.endswith('.tar.bz2'):
            format = CompressionFormat.TAR_BZ2
        else:
            raise ValueError(f"Cannot auto-detect archive format for: {archive_path}")

    logger.info(f"Extracting {format.value} archive to {extract_dir}")

    try:
        extract_dir.mkdir(parents=True, exist_ok=True)

        if format == CompressionFormat.ZIP:
            with zipfile.ZipFile(archive_path, 'r') as zipf:
                zipf.extractall(extract_dir)
                logger.debug(f"Extracted {len(zipf.namelist())} files")

        elif format in [CompressionFormat.TAR_GZ, CompressionFormat.TAR_BZ2]:
            mode = 'r:gz' if format == CompressionFormat.TAR_GZ else 'r:bz2'
            with tarfile.open(archive_path, mode) as tarf:
                tarf.extractall(extract_dir)
                logger.debug(f"Extracted {len(tarf.getnames())} files")
        else:
            raise ValueError(f"Unsupported archive format: {format}")

        logger.info(f"Extraction complete")
        return extract_dir

    except Exception as e:
        logger.error(f"Archive extraction failed: {e}")
        raise


def get_compression_ratio(original_size: int, compressed_size: int) -> float:
    """
    Calculate compression ratio.

    Args:
        original_size: Original data size in bytes
        compressed_size: Compressed data size in bytes

    Returns:
        Compression ratio (original / compressed)

    Example:
        >>> ratio = get_compression_ratio(1000, 250)
        >>> ratio
        4.0
    """
    if compressed_size == 0:
        return 0.0
    return original_size / compressed_size
