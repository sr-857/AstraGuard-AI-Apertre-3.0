import pytest
import json
import asyncio
from pathlib import Path
from src.utils.file_io import (
    ensure_directory,
    read_text_file,
    write_text_file,
    append_text_file,
    read_json,
    write_json,
    read_text_file_async,
    write_text_file_async,
    append_text_file_async,
    read_json_async,
    write_json_async,
)

# Sync Tests

def test_ensure_directory(tmp_path):
    # Test creating a new directory
    new_dir = tmp_path / "new_dir"
    assert not new_dir.exists()
    created_dir = ensure_directory(new_dir)
    assert created_dir.exists()
    assert created_dir == new_dir

    # Test ensuring existing directory
    same_dir = ensure_directory(new_dir)
    assert same_dir.exists()

    # Test with file path (should create parent)
    file_path = tmp_path / "parent/file.txt"
    ensure_directory(file_path)
    assert (tmp_path / "parent").exists()

def test_write_read_text_file(tmp_path):
    file_path = tmp_path / "test.txt"
    content = "Hello, World!"

    write_text_file(file_path, content)
    assert file_path.exists()

    read_content = read_text_file(file_path)
    assert read_content == content

def test_write_text_file_overwrite(tmp_path):
    file_path = tmp_path / "test.txt"
    write_text_file(file_path, "Initial")

    # Test overwrite=True (default)
    write_text_file(file_path, "Overwritten")
    assert read_text_file(file_path) == "Overwritten"

    # Test overwrite=False
    with pytest.raises(FileExistsError):
        write_text_file(file_path, "Fail", overwrite=False)

def test_read_text_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_text_file(tmp_path / "nonexistent.txt")

def test_append_text_file(tmp_path):
    file_path = tmp_path / "append.txt"
    write_text_file(file_path, "Start.")

    append_text_file(file_path, "End.")
    assert read_text_file(file_path) == "Start.End."

    # Test append creates file if not exists (and dir)
    new_path = tmp_path / "new/append.txt"
    append_text_file(new_path, "New.")
    assert read_text_file(new_path) == "New."

def test_write_read_json(tmp_path):
    file_path = tmp_path / "data.json"
    data = {"key": "value", "list": [1, 2, 3]}

    write_json(file_path, data)
    assert file_path.exists()

    loaded_data = read_json(file_path)
    assert loaded_data == data

def test_read_json_decode_error(tmp_path):
    file_path = tmp_path / "bad.json"
    write_text_file(file_path, "{invalid json")

    with pytest.raises(json.JSONDecodeError):
        read_json(file_path)

def test_write_json_type_error(tmp_path):
    file_path = tmp_path / "bad_type.json"
    data = {"key": set([1, 2])} # Sets are not JSON serializable

    with pytest.raises(TypeError):
        write_json(file_path, data)

# Async Tests

@pytest.mark.asyncio
async def test_write_read_text_file_async(tmp_path):
    file_path = tmp_path / "async_test.txt"
    content = "Async Hello!"

    await write_text_file_async(file_path, content)
    assert file_path.exists()

    read_content = await read_text_file_async(file_path)
    assert read_content == content

@pytest.mark.asyncio
async def test_read_text_file_async_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        await read_text_file_async(tmp_path / "async_nonexistent.txt")

@pytest.mark.asyncio
async def test_write_text_file_async_overwrite(tmp_path):
    file_path = tmp_path / "async_overwrite.txt"
    await write_text_file_async(file_path, "Initial")

    await write_text_file_async(file_path, "Overwritten")
    assert await read_text_file_async(file_path) == "Overwritten"

    with pytest.raises(FileExistsError):
        await write_text_file_async(file_path, "Fail", overwrite=False)

@pytest.mark.asyncio
async def test_append_text_file_async(tmp_path):
    file_path = tmp_path / "async_append.txt"
    await write_text_file_async(file_path, "Start.")

    await append_text_file_async(file_path, "End.")
    assert await read_text_file_async(file_path) == "Start.End."

@pytest.mark.asyncio
async def test_write_read_json_async(tmp_path):
    file_path = tmp_path / "async_data.json"
    data = {"key": "value", "async": True}

    await write_json_async(file_path, data)
    assert file_path.exists()

    loaded_data = await read_json_async(file_path)
    assert loaded_data == data

@pytest.mark.asyncio
async def test_read_json_async_decode_error(tmp_path):
    file_path = tmp_path / "async_bad.json"
    await write_text_file_async(file_path, "{invalid json")

    with pytest.raises(json.JSONDecodeError):
        await read_json_async(file_path)
