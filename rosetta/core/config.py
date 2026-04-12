"""Config loader for rosetta-cli.

Implements 3-tier precedence: config file < env var < CLI flag (CLI wins).
Env var format: ROSETTA_{SECTION}_{KEY} (uppercase).
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path


def load_config(config_path: Path | None = None) -> dict:
    """Load rosetta.toml from the given path or CWD/rosetta.toml.

    Returns an empty dict if the file is not found.
    Raises ValueError with a human-readable message if the TOML is malformed.
    """
    if config_path is None:
        config_path = Path.cwd() / "rosetta.toml"

    config_path = Path(config_path)

    if not config_path.exists():
        return {}

    try:
        with config_path.open("rb") as fh:
            return tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(
            f"Failed to parse config file '{config_path}': {exc}"
        ) from exc


def get_config_value(
    config: dict,
    section: str,
    key: str,
    cli_value=None,
    env_prefix: str = "ROSETTA",
):
    """Return a config value with 3-tier precedence (CLI > env var > config file).

    Args:
        config: Loaded config dict (from load_config).
        section: TOML section name (e.g. "embed").
        key: Key within the section (e.g. "model").
        cli_value: Value provided via CLI flag; if not None, it wins.
        env_prefix: Prefix for env vars (default "ROSETTA").

    Returns:
        The winning value, or None if not set anywhere.
    """
    # CLI wins
    if cli_value is not None:
        return cli_value

    # Env var beats config file
    env_var = f"{env_prefix}_{section.upper()}_{key.upper()}"
    env_value = os.environ.get(env_var)
    if env_value is not None:
        return env_value

    # Config file
    return config.get(section, {}).get(key)
