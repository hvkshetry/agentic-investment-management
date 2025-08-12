"""
Atomic file writing utilities to prevent data corruption during concurrent access.
"""
import os
import json
import tempfile
from pathlib import Path
from typing import Any, Union


def atomic_dump_json(obj: Any, path: Union[str, Path], **json_kwargs) -> None:
    """
    Atomically write JSON data to a file.
    
    This function writes to a temporary file first, then atomically replaces
    the target file. This prevents data corruption if the process is interrupted
    or if multiple processes try to read while writing.
    
    Args:
        obj: Object to serialize to JSON
        path: Target file path
        **json_kwargs: Additional arguments to pass to json.dump
            (e.g., indent=2, default=str, ensure_ascii=False)
    """
    path = Path(path)
    
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Set default JSON options
    json_kwargs.setdefault('indent', 2)
    json_kwargs.setdefault('default', str)
    json_kwargs.setdefault('ensure_ascii', False)
    
    # Create temporary file in the same directory (for atomic rename)
    with tempfile.NamedTemporaryFile(
        mode='w',
        delete=False,
        dir=path.parent,
        prefix=f'.{path.name}.',
        suffix='.tmp',
        encoding='utf-8'
    ) as tmp:
        try:
            # Write JSON to temporary file
            json.dump(obj, tmp, **json_kwargs)
            
            # Ensure data is written to disk
            tmp.flush()
            os.fsync(tmp.fileno())
            
            tmp_path = tmp.name
        except Exception:
            # Clean up temp file on error
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
            raise
    
    # Atomically replace the target file
    # On POSIX systems and modern Windows (NTFS), rename is atomic
    os.replace(tmp_path, path)


def atomic_write_text(content: str, path: Union[str, Path]) -> None:
    """
    Atomically write text content to a file.
    
    Args:
        content: Text content to write
        path: Target file path
    """
    path = Path(path)
    
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create temporary file in the same directory
    with tempfile.NamedTemporaryFile(
        mode='w',
        delete=False,
        dir=path.parent,
        prefix=f'.{path.name}.',
        suffix='.tmp',
        encoding='utf-8'
    ) as tmp:
        try:
            # Write content to temporary file
            tmp.write(content)
            
            # Ensure data is written to disk
            tmp.flush()
            os.fsync(tmp.fileno())
            
            tmp_path = tmp.name
        except Exception:
            # Clean up temp file on error
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
            raise
    
    # Atomically replace the target file
    os.replace(tmp_path, path)


def atomic_append_json_array(new_item: Any, path: Union[str, Path], **json_kwargs) -> None:
    """
    Atomically append an item to a JSON array file.
    
    If the file doesn't exist or is empty, creates a new array with the item.
    
    Args:
        new_item: Item to append to the array
        path: Target file path containing JSON array
        **json_kwargs: Additional arguments to pass to json.dump
    """
    path = Path(path)
    
    # Read existing data
    existing_data = []
    if path.exists() and path.stat().st_size > 0:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
                if not isinstance(existing_data, list):
                    raise ValueError(f"File {path} does not contain a JSON array")
        except (json.JSONDecodeError, FileNotFoundError):
            existing_data = []
    
    # Append new item
    existing_data.append(new_item)
    
    # Write atomically
    atomic_dump_json(existing_data, path, **json_kwargs)