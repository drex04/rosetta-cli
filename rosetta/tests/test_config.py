"""Tests for rosetta/core/config.py."""

import pytest

from rosetta.core.config import get_config_value, load_config


def test_load_config(tmp_path):
    """load_config reads a valid rosetta.toml and returns the parsed dict."""
    toml_file = tmp_path / "rosetta.toml"
    toml_file.write_text('[embed]\nmodel = "sentence-transformers/LaBSE"\nmode = "lexical-only"\n')
    config = load_config(toml_file)
    assert config["embed"]["model"] == "sentence-transformers/LaBSE"
    assert config["embed"]["mode"] == "lexical-only"


def test_cli_overrides_config(tmp_path):
    """CLI value beats the value in the config file."""
    toml_file = tmp_path / "rosetta.toml"
    toml_file.write_text('[embed]\nmodel = "sentence-transformers/LaBSE"\n')
    config = load_config(toml_file)
    result = get_config_value(config, "embed", "model", cli_value="my-custom-model")
    assert result == "my-custom-model"


def test_env_overrides_config(tmp_path, monkeypatch):
    """Env var beats the config file value but loses to CLI."""
    toml_file = tmp_path / "rosetta.toml"
    toml_file.write_text('[embed]\nmodel = "sentence-transformers/LaBSE"\n')
    config = load_config(toml_file)

    monkeypatch.setenv("ROSETTA_EMBED_MODEL", "env-model")

    # Env var wins over config
    result = get_config_value(config, "embed", "model")
    assert result == "env-model"

    # CLI still wins over env var
    result_cli = get_config_value(config, "embed", "model", cli_value="cli-model")
    assert result_cli == "cli-model"


def test_missing_config_returns_empty(tmp_path):
    """load_config returns an empty dict when the file does not exist."""
    missing = tmp_path / "rosetta.toml"
    config = load_config(missing)
    assert config == {}


def test_load_config_malformed_toml(tmp_path):
    """Malformed TOML raises a ValueError with a human-readable message."""
    bad_toml = tmp_path / "rosetta.toml"
    bad_toml.write_text("this is [not valid\ntoml = !!!\n")
    with pytest.raises(ValueError, match="Failed to parse config file"):
        load_config(bad_toml)
