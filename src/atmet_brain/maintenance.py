"""Cooperative local maintenance leases, held for a database connection's lifetime."""

from contextlib import contextmanager
from contextvars import ContextVar
import os
from pathlib import Path

from .errors import BrainError, require

_owned = ContextVar("atmet_maintenance", default=frozenset())


def acquire(home, exclusive=False):
    home = Path(home).resolve()
    if str(home) in _owned.get():
        return None
    try:
        import fcntl
    except ImportError:
        require(not exclusive, "unsupported_platform", "Guided updates currently require macOS or Linux file locking.")
        return None
    path = home / ".maintenance.lock"
    try:
        fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        require(os.fstat(fd).st_uid == os.getuid(), "unsafe_update_path", "The maintenance lock must belong to this device user.")
        os.fchmod(fd, 0o600)
        fcntl.flock(fd, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
        return fd
    except BaseException as error:
        if "fd" in locals():
            os.close(fd)
        if isinstance(error, (BlockingIOError, OSError)):
            raise BrainError("brain_busy", "This Brain is busy or under maintenance. Stop its processes and retry after the current operation finishes.", 409) from None
        raise


def release(fd):
    if fd is not None:
        os.close(fd)


@contextmanager
def maintenance(home):
    fd = acquire(home, exclusive=True)
    token = _owned.set(_owned.get() | {str(Path(home).resolve())})
    try:
        yield
    finally:
        _owned.reset(token)
        release(fd)
