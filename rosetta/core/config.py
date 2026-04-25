"""Config loader for rosetta-cli.

Implements 3-tier precedence: config file < env var < CLI flag (CLI wins).
Env var format: ROSETTA_{SECTION}_{KEY} (uppercase).
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any


def load_config(config_path: Path | None = None) -> dict[str, Any]:
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
        raise ValueError(f"Failed to parse config file '{config_path}': {exc}") from exc


def get_config_value(
    config: dict[str, Any],
    section: str,
    key: str,
    cli_value: Any | None = None,  # Click injects this
    env_prefix: str = "ROSETTA",
) -> Any:
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


def load_function_config(config: dict[str, Any]) -> dict[str, list[Path]]:
    """Return custom FnO declaration and UDF file paths from ``[functions]``."""
    fns = config.get("functions", {})
    decls: list[Path] = []
    for p in fns.get("declarations", []):
        path = Path(p)
        if not path.exists():
            raise ValueError(f"Custom FnO declaration not found: {path}")
        decls.append(path)
    udfs: list[Path] = []
    for p in fns.get("udfs", []):
        path = Path(p)
        if not path.exists():
            raise ValueError(f"Custom UDF file not found: {path}")
        udfs.append(path)
    return {"declarations": decls, "udfs": udfs}


def build_function_library(config: dict[str, Any]) -> tuple[Any, dict[str, list[Path]]]:
    """Build a FunctionLibrary with builtins + custom declarations from config.

    Returns ``(library, fn_config)`` so callers can also access UDF paths.
    Raises ``ValueError`` on missing/malformed files.
    """
    from rosetta.core.function_library import FunctionLibrary

    fn_config = load_function_config(config)
    library = FunctionLibrary.load_builtins()
    for decl_path in fn_config["declarations"]:
        library.add_declarations(decl_path)
    return library, fn_config


def load_conversion_policies(config: dict[str, Any]) -> dict[str, str]:
    """Return a merged dict of type-pair and unit-pair conversion policies.

    Keys are "source:target" strings (e.g., "float:integer" or "unit:M:unit:FT").
    Values are FnO function CURIEs (e.g., "grel:math_round").
    """
    conversions = config.get("conversions", {})
    result: dict[str, str] = {}
    # Top-level pairs (skip sub-tables like "units" using isinstance check)
    for key, value in conversions.items():
        if isinstance(value, str):
            result[key] = value
    # Unit pairs from nested table
    unit_pairs = conversions.get("units", {})
    for key, value in unit_pairs.items():
        if isinstance(value, str):
            result[key] = value
    return result
