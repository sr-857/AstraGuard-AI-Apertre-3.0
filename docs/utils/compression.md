# Backend Compression Utilities

This module provides comprehensive compression and decompression utilities for the AstraGuard backend.

## Features

- **File Compression/Decompression**: Support for gzip, bz2, and zlib formats
- **String Compression**: Easy-to-use string compression with encoding handling
- **Data Compression**: Direct bytes compression for any binary data
- **Archive Operations**: Create and extract ZIP, TAR.GZ, and TAR.BZ2 archives
- **Compression Metrics**: Calculate compression ratios
- **Memory Efficient**: Stream-based processing for large files

## Installation

```python
from src.backend.utils import (
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
```

## Usage Examples

### File Compression

```python
from pathlib import Path
from src.backend.utils import compress_file, decompress_file, CompressionFormat

# Compress a file with auto-generated output name
compressed = compress_file("large_log.txt", format=CompressionFormat.GZIP)
print(f"Compressed to: {compressed}")  # large_log.txt.gz

# Compress with custom output path
compressed = compress_file(
    "data.json",
    output_path="backup/data.json.bz2",
    format=CompressionFormat.BZ2,
    compression_level=9  # Maximum compression
)

# Decompress (format auto-detected)
decompressed = decompress_file("large_log.txt.gz")
print(f"Decompressed to: {decompressed}")  # large_log.txt
```

### String Compression

```python
from src.backend.utils import compress_string, decompress_string

# Compress a string
text = "This is a long string that will be compressed" * 100
compressed_bytes = compress_string(text)

# Decompress back to string
original_text = decompress_string(compressed_bytes)
assert text == original_text

# Calculate space savings
original_size = len(text.encode('utf-8'))
compressed_size = len(compressed_bytes)
ratio = original_size / compressed_size
print(f"Compression ratio: {ratio:.2f}x")
```

### Data Compression

```python
from src.backend.utils import compress_data, decompress_data, CompressionFormat

# Compress binary data
data = b"Binary data to compress" * 50
compressed = compress_data(data, format=CompressionFormat.ZLIB, compression_level=6)

# Decompress
original = decompress_data(compressed, format=CompressionFormat.ZLIB)
assert data == original
```

### Archive Operations

```python
from src.backend.utils import create_archive, extract_archive, CompressionFormat

# Create a ZIP archive
files = ["config.yaml", "data.json", "logs/app.log"]
archive = create_archive(
    files,
    "backup.zip",
    format=CompressionFormat.ZIP
)

# Create a compressed TAR archive
archive = create_archive(
    files,
    "backup.tar.gz",
    format=CompressionFormat.TAR_GZ
)

# Extract archive (format auto-detected)
extract_dir = extract_archive("backup.zip", "restored/")
print(f"Extracted to: {extract_dir}")
```

### Compression Ratio Calculation

```python
from src.backend.utils import get_compression_ratio, compress_file
from pathlib import Path

# Compress a file
original_file = Path("large_data.json")
compressed_file = compress_file(original_file)

# Calculate compression ratio
original_size = original_file.stat().st_size
compressed_size = compressed_file.stat().st_size
ratio = get_compression_ratio(original_size, compressed_size)

print(f"Original size: {original_size:,} bytes")
print(f"Compressed size: {compressed_size:,} bytes")
print(f"Compression ratio: {ratio:.2f}x")
print(f"Space saved: {(1 - 1/ratio) * 100:.1f}%")
```

## Compression Formats

The module supports the following compression formats:

- **GZIP** (`CompressionFormat.GZIP`): Fast compression with good ratio, widely compatible
- **BZ2** (`CompressionFormat.BZ2`): Better compression than gzip, slower
- **ZLIB** (`CompressionFormat.ZLIB`): Similar to gzip, used for in-memory compression
- **ZIP** (`CompressionFormat.ZIP`): Archive format with compression
- **TAR.GZ** (`CompressionFormat.TAR_GZ`): TAR archive with gzip compression
- **TAR.BZ2** (`CompressionFormat.TAR_BZ2`): TAR archive with bz2 compression

## API Reference

### compress_file()

Compress a file using the specified format.

**Parameters:**
- `input_path` (str | Path): Path to the file to compress
- `output_path` (str | Path, optional): Path for compressed file (auto-generated if None)
- `format` (CompressionFormat): Compression format (default: GZIP)
- `compression_level` (int): Compression level 1-9, where 9 is maximum (default: 9)

**Returns:** Path to the compressed file

### decompress_file()

Decompress a file.

**Parameters:**
- `input_path` (str | Path): Path to the compressed file
- `output_path` (str | Path, optional): Path for decompressed file (auto-generated if None)
- `format` (CompressionFormat, optional): Format (auto-detected if None)

**Returns:** Path to the decompressed file

### compress_string()

Compress a string to bytes.

**Parameters:**
- `data` (str): String to compress
- `format` (CompressionFormat): Compression format (default: ZLIB)
- `compression_level` (int): Compression level 1-9 (default: 9)

**Returns:** Compressed bytes

### decompress_string()

Decompress bytes to a string.

**Parameters:**
- `compressed_data` (bytes): Compressed bytes
- `format` (CompressionFormat): Compression format (default: ZLIB)

**Returns:** Decompressed string

### compress_data()

Compress bytes using the specified format.

**Parameters:**
- `data` (bytes): Bytes to compress
- `format` (CompressionFormat): Compression format (default: ZLIB)
- `compression_level` (int): Compression level 1-9 (default: 9)

**Returns:** Compressed bytes

### decompress_data()

Decompress bytes.

**Parameters:**
- `compressed_data` (bytes): Compressed bytes
- `format` (CompressionFormat): Compression format (default: ZLIB)

**Returns:** Decompressed bytes

### create_archive()

Create an archive containing multiple files.

**Parameters:**
- `files` (List[str | Path]): List of files to include
- `archive_path` (str | Path): Path for the archive file
- `format` (CompressionFormat): Archive format (default: ZIP)
- `base_dir` (str | Path, optional): Base directory for relative paths

**Returns:** Path to the created archive

### extract_archive()

Extract an archive.

**Parameters:**
- `archive_path` (str | Path): Path to the archive file
- `extract_dir` (str | Path): Directory to extract files to
- `format` (CompressionFormat, optional): Format (auto-detected if None)

**Returns:** Path to the extraction directory

### get_compression_ratio()

Calculate compression ratio.

**Parameters:**
- `original_size` (int): Original data size in bytes
- `compressed_size` (int): Compressed data size in bytes

**Returns:** Compression ratio (original / compressed)

## Best Practices

1. **Choose the Right Format:**
   - Use GZIP for general-purpose compression (fast, good ratio)
   - Use BZ2 when maximum compression is needed (slower)
   - Use ZLIB for in-memory data compression
   - Use ZIP for cross-platform archives

2. **Compression Levels:**
   - Level 1: Fastest, least compression
   - Level 6: Balanced (good default)
   - Level 9: Best compression, slowest

3. **Large Files:**
   - The utilities use streaming for memory efficiency
   - Large files are processed in chunks
   - No need to load entire file into memory

4. **Error Handling:**
   - Functions raise `FileNotFoundError` if files don't exist
   - Functions raise `ValueError` for unsupported formats
   - All operations are logged for debugging

## Testing

Run the test suite:

```bash
pytest tests/utils/test_compression.py -v
```

The test suite includes:
- File compression/decompression tests
- String compression tests
- Data compression tests
- Archive operations tests
- Compression ratio validation
- Edge cases (large data, random data, etc.)

## Performance Considerations

- **GZIP**: ~10-30 MB/s compression speed
- **BZ2**: ~5-15 MB/s compression speed (better ratio)
- **ZLIB**: Similar to GZIP, optimized for in-memory operations

Actual performance depends on data characteristics and compression level.

## Integration Examples

### Log File Rotation with Compression

```python
from pathlib import Path
from src.backend.utils import compress_file, CompressionFormat

def rotate_log(log_path: str, keep_days=7):
    """Rotate and compress old log files."""
    log_file = Path(log_path)
    
    # Compress the current log
    compressed = compress_file(log_file, format=CompressionFormat.GZIP)
    
    # Delete original
    log_file.unlink()
    
    # Clean old compressed logs
    for old_log in log_file.parent.glob("*.log.gz"):
        age_days = (datetime.now() - datetime.fromtimestamp(old_log.stat().st_mtime)).days
        if age_days > keep_days:
            old_log.unlink()
```

### Backup System

```python
from datetime import datetime
from src.backend.utils import create_archive, CompressionFormat

def create_backup():
    """Create compressed backup of important files."""
    backup_files = [
        "config/settings.yaml",
        "data/database.db",
        "logs/app.log",
    ]
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"backup_{timestamp}.tar.gz"
    
    archive = create_archive(
        backup_files,
        f"backups/{archive_name}",
        format=CompressionFormat.TAR_GZ
    )
    
    return archive
```

### API Response Compression

```python
from src.backend.utils import compress_string, CompressionFormat
import json

def compress_api_response(data: dict) -> bytes:
    """Compress JSON API response."""
    json_str = json.dumps(data)
    return compress_string(json_str, format=CompressionFormat.GZIP)
```

## License

Part of the AstraGuard AI Apertre 3.0 project.
