"""Small serialization, time and private-file helpers."""

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time
import uuid
from datetime import datetime, timezone

from .errors import BrainError, require


def now():
    return time.time()


def uid(prefix):
    return prefix + "_" + uuid.uuid4().hex


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def loads(value):
    return json.loads(value)


def sha(value):
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def timestamp(value=None):
    if value is None:
        return now()
    if isinstance(value, bool):
        raise BrainError("invalid_time", "A time must be an ISO timestamp or Unix seconds.")
    if isinstance(value, (float, int)):
        require(0 <= value < 253402300799, "invalid_time", "Time is outside the supported range.")
        return float(value)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        require(parsed.tzinfo is not None, "invalid_time", "ISO timestamps need a timezone.")
        return parsed.timestamp()
    except (ValueError, OverflowError):
        raise BrainError("invalid_time", "Use an ISO timestamp with timezone or Unix seconds.") from None


def iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def text(value, name="text", maximum=200_000, allow_empty=False):
    require(isinstance(value, str), "invalid_input", f"{name} must be text.")
    require((allow_empty or bool(value.strip())) and len(value) <= maximum,
            "invalid_input", f"{name} is empty or too large.")
    return value


def slug(value):
    require(isinstance(value, str) and re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,79}", value),
            "invalid_slug", "Use a lowercase slug with letters, digits, underscores or hyphens.")
    return value


def private_write(path, data, overwrite=True):
    """Atomic private write. Callers choose paths at the local operator boundary."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not overwrite:
        require(not path.exists(), "already_exists", "Destination already exists.", 409)
    fd, temporary = tempfile.mkstemp(prefix=".atmet-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data.encode() if isinstance(data, str) else data)
            stream.flush()
            os.fsync(stream.fileno())
        if not overwrite:
            # Hard link avoids replacing a destination created concurrently.
            os.link(temporary, path)
            os.unlink(temporary)
        else:
            os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def safe_resource_path(value):
    path = Path(value)
    require(isinstance(value, str) and len(value) <= 240 and not path.is_absolute()
            and ".." not in path.parts and "\\" not in value and bool(path.parts),
            "invalid_resource", "Skill resources need a relative path without parent traversal.")
    return path.as_posix()
