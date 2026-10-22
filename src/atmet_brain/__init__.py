"""Atmet Brain public Python interface."""

from ._version import __version__

from .brain import Brain
from .errors import BrainError

__all__ = ["Brain", "BrainError", "__version__"]
