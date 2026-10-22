"""A selected-directory connector with bounded, no-symlink reads."""

import os
from pathlib import Path
import stat

from ..errors import BrainError, require

MIMES = {".txt": "text/plain", ".md": "text/markdown", ".csv": "text/csv", ".json": "application/json"}


def read_contained(root, relative):
    parts = Path(relative).parts
    require(parts and ".." not in parts and not Path(relative).is_absolute(), "invalid_path", "Invalid connector path.")
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory = getattr(os, "O_DIRECTORY", 0)
    fd = os.open(root, os.O_RDONLY | directory | nofollow)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | directory | nofollow, dir_fd=fd)
            os.close(fd)
            fd = child
        file_fd = os.open(parts[-1], os.O_RDONLY | nofollow, dir_fd=fd)
        with os.fdopen(file_fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            require(stat.S_ISREG(before.st_mode) and before.st_size <= 200_000,
                    "file_size", "Connector files must be regular files up to 200000 bytes.")
            data = stream.read(200_001)
            after = os.fstat(stream.fileno())
            require(len(data) <= 200_000 and before.st_mtime_ns == after.st_mtime_ns and before.st_size == after.st_size,
                    "file_changed", "File changed during capture. Retry synchronization.")
            return data.decode("utf-8")
    except (OSError, UnicodeError):
        raise BrainError("file_read_failed", "A selected file could not be read safely.") from None
    finally:
        os.close(fd)


def scan(root):
    root = Path(root)
    require(root.is_dir() and not root.is_symlink(), "invalid_root", "Choose an existing non-symlink directory.")
    result = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file() or path.suffix.lower() not in MIMES:
            continue
        relative = path.relative_to(root).as_posix()
        require(not any(part.startswith(".") for part in Path(relative).parts),
                "hidden_file", "Selected roots cannot include supported hidden files. Use a dedicated import directory.")
        result.append({"external_id": relative, "title": relative, "content": read_contained(root, relative),
                       "mime": MIMES[path.suffix.lower()]})
        require(len(result) <= 500, "connector_limit", "Split import roots larger than 500 supported files.")
    return result
