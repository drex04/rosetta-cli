"""Tests for rosetta-ingest CLI — LinkML YAML output."""

from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from rosetta.cli.ingest import cli

FIXTURES = Path(__file__).parent / "fixtures" / "nations"


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


# ---------------------------------------------------------------------------
# Task 6 — Prefix collision lint
# ---------------------------------------------------------------------------


def test_ingest_prefix_collision_default_prefix(tmp_path: Path) -> None:
    """Two ingests into the same directory with the same --schema-name fail on the second."""
    runner = CliRunner()
    out_dir = tmp_path / "nor_schema"
    out_dir.mkdir()

    # First ingest succeeds.
    result1 = runner.invoke(
        cli,
        [
            "--input",
            str(FIXTURES / "nor_radar.csv"),
            "--schema-name",
            "nor_schema",
            "--output",
            str(out_dir / "nor.linkml.yaml"),
        ],
    )
    assert result1.exit_code == 0, f"First ingest failed: {result1.output}"

    # Second ingest with same schema-name into same dir should fail.
    result2 = runner.invoke(
        cli,
        [
            "--input",
            str(FIXTURES / "nor_radar.csv"),
            "--schema-name",
            "nor_schema",
            "--output",
            str(out_dir / "other.linkml.yaml"),
        ],
    )
    assert result2.exit_code == 1
    assert "nor_schema" in result2.output or "nor_schema" in (result2.output or "")


def test_ingest_prefix_collision_allows_unique_names(tmp_path: Path) -> None:
    """Two ingests with different --schema-name into the same directory both succeed."""
    runner = CliRunner()
    out_dir = tmp_path / "schemas"
    out_dir.mkdir()

    result1 = runner.invoke(
        cli,
        [
            "--input",
            str(FIXTURES / "nor_radar.csv"),
            "--schema-name",
            "schema_alpha",
            "--output",
            str(out_dir / "alpha.linkml.yaml"),
        ],
    )
    assert result1.exit_code == 0, f"First ingest failed: {result1.output}"

    result2 = runner.invoke(
        cli,
        [
            "--input",
            str(FIXTURES / "nor_radar.csv"),
            "--schema-name",
            "schema_beta",
            "--output",
            str(out_dir / "beta.linkml.yaml"),
        ],
    )
    assert result2.exit_code == 0, f"Second ingest failed: {result2.output}"


def test_ingest_prefix_collision_id_field(tmp_path: Path) -> None:
    """A sibling with a clashing `id` (namespace IRI) is detected even if default_prefix differs."""
    runner = CliRunner()
    out_dir = tmp_path / "schemas"
    out_dir.mkdir()

    # First ingest to discover what id gets generated.
    out1 = out_dir / "first.linkml.yaml"
    result1 = runner.invoke(
        cli,
        [
            "--input",
            str(FIXTURES / "nor_radar.csv"),
            "--schema-name",
            "nor_schema",
            "--output",
            str(out1),
        ],
    )
    assert result1.exit_code == 0, f"First ingest failed: {result1.output}"

    clashing_id = yaml.safe_load(out1.read_text()).get("id", "https://example.org/nor_schema")

    # Write a handcrafted sibling with a different default_prefix but the same id.
    sibling = out_dir / "handcrafted.linkml.yaml"
    sibling.write_text(
        f"id: {clashing_id}\nname: other_schema\ndefault_prefix: completely_different\n"
    )

    # Now ingest with a different prefix but the same id should fail.
    result2 = runner.invoke(
        cli,
        [
            "--input",
            str(FIXTURES / "nor_radar.csv"),
            "--schema-name",
            "nor_schema",
            "--output",
            str(out_dir / "second.linkml.yaml"),
        ],
    )
    assert result2.exit_code == 1
    assert "id" in result2.output or "already used" in result2.output


def test_ingest_prefix_collision_malformed_sibling_warns(tmp_path: Path) -> None:
    """A malformed (non-YAML) sibling is skipped with a stderr warning; ingest succeeds."""
    runner = CliRunner(mix_stderr=True)
    out_dir = tmp_path / "schemas"
    out_dir.mkdir()

    # Place a malformed YAML sibling.
    bad = out_dir / "bad.linkml.yaml"
    bad.write_text("{{{")

    result = runner.invoke(
        cli,
        [
            "--input",
            str(FIXTURES / "nor_radar.csv"),
            "--schema-name",
            "nor_schema",
            "--output",
            str(out_dir / "nor.linkml.yaml"),
        ],
    )
    assert result.exit_code == 0, f"Ingest should succeed despite bad sibling: {result.output}"
    # CliRunner mixes stdout+stderr into result.output by default.
    assert "WARNING: prefix-collision check could not read" in result.output


# ---------------------------------------------------------------------------
# Task 7 — Source-format + per-slot path annotations
# ---------------------------------------------------------------------------


def test_ingest_stamps_rosetta_source_format_csv(tmp_path: Path) -> None:
    """CSV ingest writes annotations.rosetta_source_format = 'csv' on the output schema."""
    runner = CliRunner()
    out = tmp_path / "out.linkml.yaml"
    result = runner.invoke(
        cli,
        [
            "--input",
            str(FIXTURES / "nor_radar.csv"),
            "--output",
            str(out),
        ],
    )
    assert result.exit_code == 0, f"CLI failed: {result.output}"
    data = yaml.safe_load(out.read_text())
    annotations = data.get("annotations") or {}
    assert annotations.get("rosetta_source_format") == "csv", f"Expected 'csv', got: {annotations}"


def test_ingest_stamps_rosetta_csv_column_per_slot(tmp_path: Path) -> None:
    """Every generated slot has annotations.rosetta_csv_column equal to its name."""
    runner = CliRunner()
    out = tmp_path / "out.linkml.yaml"
    result = runner.invoke(
        cli,
        [
            "--input",
            str(FIXTURES / "nor_radar.csv"),
            "--output",
            str(out),
        ],
    )
    assert result.exit_code == 0, f"CLI failed: {result.output}"
    data = yaml.safe_load(out.read_text())
    slots: dict[str, object] = data.get("slots") or {}
    assert slots, "Expected at least one slot in CSV schema"
    for slot_name, slot_def in slots.items():
        if not isinstance(slot_def, dict):
            continue
        annotations = slot_def.get("annotations") or {}
        assert annotations.get("rosetta_csv_column") == slot_name, (
            f"Slot {slot_name!r} missing rosetta_csv_column annotation"
        )


def test_ingest_rdfs_ingest_does_not_stamp_source_format(tmp_path: Path) -> None:
    """RDFS-sourced schemas (master ontologies) have no rosetta_source_format annotation."""
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
        ["--input", str(ttl_file), "--output", str(out)],
    )
    assert result.exit_code == 0, f"CLI failed: {result.output}"
    data = yaml.safe_load(out.read_text())
    annotations = data.get("annotations") or {}
    assert "rosetta_source_format" not in annotations, (
        f"RDFS schema should not have rosetta_source_format; got: {annotations}"
    )
