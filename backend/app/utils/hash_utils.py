"""
File hashing utilities.
"""
from __future__ import annotations

import hashlib
from pathlib import Path


def compute_file_hash(file_path: Path, algorithm: str = "sha256", chunk_size: int = 65536) -> str:
    """Compute a hex digest hash for a file's contents, streaming to avoid high memory use."""
    hasher = hashlib.new(algorithm)
    try:
        with file_path.open("rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except OSError:
        return ""
