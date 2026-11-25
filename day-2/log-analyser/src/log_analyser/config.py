"""Config: load settings from a TOML file, validate them, and merge with CLI flags.

Precedence (later wins): built-in defaults -> config file -> command-line flags.
"""
import tomllib
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Optional

LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


class ConfigError(Exception):
    """The configuration is missing, unreadable or invalid."""


@dataclass(frozen=True)
class Config:
    """All settings, with their built-in defaults. frozen=True: cannot be changed after creation."""
    top_ips: int = 10
    top_endpoints: int = 5
    log_level: str = "WARNING"


KNOWN_KEYS = {f.name for f in fields(Config)}


def validate(values: dict, source: str) -> dict:
    """Check every key and value. Return a cleaned copy, or raise ConfigError naming `source`."""
    unknown = set(values) - KNOWN_KEYS
    if unknown:
        raise ConfigError(f"{source}: unknown setting(s): {', '.join(sorted(unknown))}")

    clean = {}
    for key, value in values.items():
        if key in ("top_ips", "top_endpoints"):
            # bool is a subclass of int in Python (True == 1), so reject it explicitly.
            if not isinstance(value, int) or isinstance(value, bool):
                raise ConfigError(f"{source}: {key} must be a whole number, got {value!r}")
            if value < 1:
                raise ConfigError(f"{source}: {key} must be at least 1, got {value}")
        elif key == "log_level":
            if not isinstance(value, str) or value.upper() not in LOG_LEVELS:
                raise ConfigError(f"{source}: log_level must be one of {', '.join(LOG_LEVELS)}, got {value!r}")
            value = value.upper()
        clean[key] = value
    return clean


def load_config_file(path: Path) -> dict:
    """Read and validate a TOML config file. Returns only the settings it contains."""
    try:
        with open(path, "rb") as f:          # tomllib requires the file opened in BINARY mode
            data = tomllib.load(f)
    except OSError as e:
        raise ConfigError(f"cannot read config file {path}: {e.strerror}") from e
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"config file {path} is not valid TOML: {e}") from e
    return validate(data, source=str(path))


def build_config(file_values: Optional[dict] = None, cli_values: Optional[dict] = None) -> Config:
    """Merge settings: defaults, then the config file, then CLI flags (flags win).

    CLI values that are None mean "flag not given" and are ignored.
    """
    config = Config()
    if file_values:
        config = replace(config, **file_values)
    if cli_values:
        given = {k: v for k, v in cli_values.items() if v is not None}
        config = replace(config, **validate(given, source="command line"))
    return config
