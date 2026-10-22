"""Typed local configuration. Lower scopes can reduce limits, never grant rights."""

from dataclasses import dataclass
import os
from pathlib import Path
import tomllib

from .errors import require

CONFIG_KEYS = {"max_context_chars", "max_results", "allow_remote_processing"}


def validate_settings(settings):
    require(isinstance(settings, dict) and not (set(settings) - CONFIG_KEYS),
            "invalid_config", "Unknown configuration key. Permissions are managed as grants.")
    for name, low, high in [("max_context_chars", 500, 100_000), ("max_results", 1, 100)]:
        if name in settings:
            value = settings[name]
            require(type(value) is int and low <= value <= high, "invalid_config", f"Invalid {name}.")
    if "allow_remote_processing" in settings:
        require(type(settings["allow_remote_processing"]) is bool,
                "invalid_config", "allow_remote_processing must be true or false.")
    return settings


@dataclass(frozen=True)
class Settings:
    max_context_chars: int = 16_000
    max_results: int = 12
    allow_remote_processing: bool = False

    @classmethod
    def load(cls, home):
        path = Path(home) / "config.toml"
        data = tomllib.loads(path.read_text()) if path.exists() else {}
        require(set(data) <= {"brain"}, "invalid_config", "Only the [brain] configuration table is supported.")
        values = validate_settings(data.get("brain", {}))
        return cls(**values)

    def constrain(self, *layers):
        result = {"max_context_chars": self.max_context_chars, "max_results": self.max_results,
                  "allow_remote_processing": self.allow_remote_processing}
        for layer in layers:
            validate_settings(layer)
            for key, value in layer.items():
                result[key] = result[key] and value if key == "allow_remote_processing" else min(result[key], value)
        return result


def default_home():
    return Path(os.environ.get("ATMET_HOME", "~/.atmet-brain")).expanduser()
