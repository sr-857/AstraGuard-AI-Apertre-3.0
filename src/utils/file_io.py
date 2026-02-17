"""
Reusable file I/O utilities.
Safe, logged, and cross-platform.
"""

from pathlib import Path
import json
import logging
from typing import Any, Union, Optional
import aiofiles
from astraguard.logging_config import get_logger

logger = get_logger(__name__)

def ensure_directory(path: Union[str, Path]) -> Path:
    """
    Ensure directory exists, creating parents if needed.

    Args:
        path: Path to directory or file. If it has a suffix, assumes it's a file and creates parent dir.

    Returns:
        Path object of the created/verified directory.
    """
    path_obj = Path(path)
    # If it looks like a file (has extension), get parent directory
    # Note: This is a heuristic. Explicit directory paths without extensions are preferred.
    if path_obj.suffix:
        dir_path = path_obj.parent
    else:
        dir_path = path_obj

    try:
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path
    except OSError as e:
        logger.error("Failed to create directory", path=str(dir_path), error=str(e), exc_info=True)
        raise

def read_text_file(path: Union[str, Path], encoding: str = "utf-8") -> str:
    """
    Read text file content synchronously.

    Args:
        path: Path to file.
        encoding: File encoding (default: utf-8).

    Returns:
        File content as string.
    """
    path_obj = Path(path)
    try:
        with open(path_obj, "r", encoding=encoding) as f:
            return f.read()
    except FileNotFoundError:
        logger.warning("File not found", path=str(path_obj))
        raise
    except OSError as e:
        logger.error("Failed to read file", path=str(path_obj), error=str(e), exc_info=True)
        raise

def write_text_file(
    path: Union[str, Path],
    content: str,
    encoding: str = "utf-8",
    overwrite: bool = True
) -> None:
    """
    Write text file content synchronously.

    Args:
        path: Path to file.
        content: String content to write.
        encoding: File encoding (default: utf-8).
        overwrite: Whether to overwrite existing file (default: True).
    """
    path_obj = Path(path)

    # Ensure parent directory exists
    try:
        path_obj.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error("Failed to create parent directory", path=str(path_obj.parent), error=str(e), exc_info=True)
        raise

    mode = "w" if overwrite else "x"
    try:
        with open(path_obj, mode, encoding=encoding) as f:
            f.write(content)
        logger.info("File written successfully", path=str(path_obj))
    except FileExistsError:
        logger.warning("File already exists and overwrite=False", path=str(path_obj))
        raise
    except OSError as e:
        logger.error("Failed to write file", path=str(path_obj), error=str(e), exc_info=True)
        raise

def append_text_file(
    path: Union[str, Path],
    content: str,
    encoding: str = "utf-8"
) -> None:
    """
    Append content to text file synchronously.

    Args:
        path: Path to file.
        content: String content to append.
        encoding: File encoding (default: utf-8).
    """
    path_obj = Path(path)

    # Ensure parent directory exists
    try:
        path_obj.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error("Failed to create parent directory", path=str(path_obj.parent), error=str(e), exc_info=True)
        raise

    try:
        with open(path_obj, "a", encoding=encoding) as f:
            f.write(content)
        logger.info("File appended successfully", path=str(path_obj))
    except OSError as e:
        logger.error("Failed to append to file", path=str(path_obj), error=str(e), exc_info=True)
        raise

def read_json(path: Union[str, Path], encoding: str = "utf-8") -> Any:
    """
    Read JSON file content synchronously.

    Args:
        path: Path to file.
        encoding: File encoding (default: utf-8).

    Returns:
        Parsed JSON data.
    """
    content = read_text_file(path, encoding)
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.error("Failed to decode JSON from file", path=str(path), error=str(e), exc_info=True)
        raise

def write_json(
    path: Union[str, Path],
    data: Any,
    encoding: str = "utf-8",
    indent: int = 2,
    overwrite: bool = True
) -> None:
    """
    Write JSON data to file synchronously.

    Args:
        path: Path to file.
        data: JSON serializable data.
        encoding: File encoding (default: utf-8).
        indent: JSON indentation level (default: 2).
        overwrite: Whether to overwrite existing file (default: True).
    """
    try:
        content = json.dumps(data, indent=indent)
        write_text_file(path, content, encoding, overwrite)
    except (TypeError, ValueError) as e:
         logger.error("Failed to serialize data to JSON", path=str(path), error=str(e), exc_info=True)
         raise

# ============================================================================
# ASYNC IMPLEMENTATIONS
# ============================================================================

async def read_text_file_async(path: Union[str, Path], encoding: str = "utf-8") -> str:
    """
    Read text file content asynchronously.

    Args:
        path: Path to file.
        encoding: File encoding (default: utf-8).

    Returns:
        File content as string.
    """
    path_obj = Path(path)
    try:
        async with aiofiles.open(path_obj, "r", encoding=encoding) as f:
            return await f.read()
    except FileNotFoundError:
        logger.warning("File not found (async)", path=str(path_obj))
        raise
    except OSError as e:
        logger.error("Failed to read file async", path=str(path_obj), error=str(e), exc_info=True)
        raise

async def write_text_file_async(
    path: Union[str, Path],
    content: str,
    encoding: str = "utf-8",
    overwrite: bool = True
) -> None:
    """
    Write text file content asynchronously.

    Args:
        path: Path to file.
        content: String content to write.
        encoding: File encoding (default: utf-8).
        overwrite: Whether to overwrite existing file (default: True).
    """
    path_obj = Path(path)

    # Ensure parent directory exists (synchronous call is usually fine here as it's fast)
    try:
        path_obj.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error("Failed to create parent directory", path=str(path_obj.parent), error=str(e), exc_info=True)
        raise

    mode = "w" if overwrite else "x"
    try:
        async with aiofiles.open(path_obj, mode, encoding=encoding) as f:
            await f.write(content)
        logger.info("File written async successfully", path=str(path_obj))
    except FileExistsError:
        logger.warning("File already exists and overwrite=False (async)", path=str(path_obj))
        raise
    except OSError as e:
        logger.error("Failed to write file async", path=str(path_obj), error=str(e), exc_info=True)
        raise

async def append_text_file_async(
    path: Union[str, Path],
    content: str,
    encoding: str = "utf-8"
) -> None:
    """
    Append content to text file asynchronously.

    Args:
        path: Path to file.
        content: String content to append.
        encoding: File encoding (default: utf-8).
    """
    path_obj = Path(path)

    # Ensure parent directory exists
    try:
        path_obj.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error("Failed to create parent directory", path=str(path_obj.parent), error=str(e), exc_info=True)
        raise

    try:
        async with aiofiles.open(path_obj, "a", encoding=encoding) as f:
            await f.write(content)
        logger.info("File appended async successfully", path=str(path_obj))
    except OSError as e:
        logger.error("Failed to append to file async", path=str(path_obj), error=str(e), exc_info=True)
        raise

async def read_json_async(path: Union[str, Path], encoding: str = "utf-8") -> Any:
    """
    Read JSON file content asynchronously.

    Args:
        path: Path to file.
        encoding: File encoding (default: utf-8).

    Returns:
        Parsed JSON data.
    """
    content = await read_text_file_async(path, encoding)
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.error("Failed to decode JSON from file async", path=str(path), error=str(e), exc_info=True)
        raise

async def write_json_async(
    path: Union[str, Path],
    data: Any,
    encoding: str = "utf-8",
    indent: int = 2,
    overwrite: bool = True
) -> None:
    """
    Write JSON data to file asynchronously.

    Args:
        path: Path to file.
        data: JSON serializable data.
        encoding: File encoding (default: utf-8).
        indent: JSON indentation level (default: 2).
        overwrite: Whether to overwrite existing file (default: True).
    """
    try:
        content = json.dumps(data, indent=indent)
        await write_text_file_async(path, content, encoding, overwrite)
    except (TypeError, ValueError) as e:
         logger.error("Failed to serialize data to JSON async", path=str(path), error=str(e), exc_info=True)
         raise
