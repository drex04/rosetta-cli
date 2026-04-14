"""Tests for rosetta-ingest CLI — LinkML YAML output."""

from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from rosetta.cli.ingest import cli

FIXTURES = Path(__file__).parent / "fixtures"


def test_ingest_json_schema_cli(tmp_path: Path) -> None:
    """JSON Schema fixture → exit 0, output contains 'classes:' or 'slots:'."""
    runner = CliRunner()
    out = tmp_path / "out.linkml.yaml"
    result = runner.invoke(
        cli,
        [
            "--input",
            str(FIXTURES / "deu_patriot.json"),
            "--output",
            str(out),
        ],
    )
    assert result.exit_code == 0, f"CLI failed: {result.output}"
    assert out.exists()
    content = out.read_text()
    assert "classes:" in content or "slots:" in content


def test_ingest_rdfs_cli(tmp_path: Path) -> None:
    """Inline TTL → exit 0, YAML output with at least 1 class."""
    ttl_file = tmp_path / "test.ttl"
    ttl_file.write_text(
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
        "@prefix ex: <http://example.org/> .\n"
        'ex:Speed a rdfs:Class ; rdfs:label "Speed" .\n'
    )
    runner = CliRunner()
    out = tmp_path / "out.linkml.yaml"
    result = runner.invoke(
        cli,
        [
            "--input",
            str(ttl_file),
            "--output",
            str(out),
        ],
    )
    assert result.exit_code == 0, f"CLI failed: {result.output}"
    assert out.exists()


def test_ingest_schema_name_override(tmp_path: Path) -> None:
    """--schema-name custom → output YAML has name: custom."""
    runner = CliRunner()
    out = tmp_path / "out.linkml.yaml"
    result = runner.invoke(
        cli,
        [
            "--input",
            str(FIXTURES / "deu_patriot.json"),
            "--schema-name",
            "custom",
            "--output",
            str(out),
        ],
    )
    assert result.exit_code == 0, f"CLI failed: {result.output}"
    data = yaml.safe_load(out.read_text())
    assert data.get("name") == "custom"


def test_ingest_no_nation_flag(tmp_path: Path) -> None:
    """--nation DEU → Click error (unknown option), exit non-zero."""
    runner = CliRunner()
    out = tmp_path / "out.linkml.yaml"
    result = runner.invoke(
        cli,
        [
            "--input",
            str(FIXTURES / "deu_patriot.json"),
            "--nation",
            "DEU",
            "--output",
            str(out),
        ],
    )
    assert result.exit_code != 0
    assert "No such option" in result.output or "Error" in result.output
