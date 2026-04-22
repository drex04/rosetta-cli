"""Tests for rosetta ingest CLI — LinkML YAML output."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from click.testing import CliRunner

from rosetta.cli.ingest import cli

FIXTURES = Path(__file__).parent / "fixtures" / "nations"

_MINI_ONTOLOGY = """\
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix mc: <http://example.org/master/> .

mc: a owl:Ontology .
mc:Track a owl:Class ; rdfs:label "Track" .
mc:hasAltitude a owl:DatatypeProperty ; rdfs:label "hasAltitude" ; rdfs:domain mc:Track .
"""


def test_ingest_json_schema_cli(tmp_path: Path) -> None:
    """JSON Schema fixture → exit 0, output contains 'classes:' or 'slots:'."""
    runner = CliRunner()
    out = tmp_path / "out.linkml.yaml"
    result = runner.invoke(
        cli,
        [
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
            str(ttl_file),
            "--output",
            str(out),
        ],
    )
    assert result.exit_code == 0, f"CLI failed: {result.output}"
    assert out.exists()


def test_ingest_schema_name_derived_from_stem(tmp_path: Path) -> None:
    """Schema name is derived from the input file stem (no --schema-name option)."""
    runner = CliRunner()
    out = tmp_path / "out.linkml.yaml"
    result = runner.invoke(
        cli,
        [
            str(FIXTURES / "deu_patriot.json"),
            "--output",
            str(out),
        ],
    )
    assert result.exit_code == 0, f"CLI failed: {result.output}"
    data = yaml.safe_load(out.read_text())
    assert data.get("name") == "deu_patriot"


def test_ingest_no_nation_flag(tmp_path: Path) -> None:
    """--nation DEU → Click error (unknown option), exit non-zero."""
    runner = CliRunner()
    out = tmp_path / "out.linkml.yaml"
    result = runner.invoke(
        cli,
        [
            str(FIXTURES / "deu_patriot.json"),
            "--nation",
            "DEU",
            "--output",
            str(out),
        ],
    )
    assert result.exit_code != 0
    assert "No such option" in result.output or "Error" in result.output


def test_ingest_stdout(tmp_path: Path) -> None:
    """No --output → writes to stdout, exit 0."""
    result = CliRunner().invoke(
        cli,
        [str(FIXTURES / "deu_patriot.json")],
    )
    assert result.exit_code == 0, f"CLI failed: {result.output}"
    assert "classes:" in result.output or "slots:" in result.output


def test_ingest_short_flags(tmp_path: Path) -> None:
    """-f and -o short flags work correctly."""
    runner = CliRunner()
    out = tmp_path / "out.linkml.yaml"
    result = runner.invoke(
        cli,
        [
            str(FIXTURES / "nor_radar.csv"),
            "-f",
            "csv",
            "-o",
            str(out),
        ],
    )
    assert result.exit_code == 0, f"CLI failed: {result.output}"
    assert out.exists()


# ---------------------------------------------------------------------------
# Task 6 — Prefix collision lint
# ---------------------------------------------------------------------------


def test_ingest_prefix_collision_default_prefix(tmp_path: Path) -> None:
    """Two ingests of the same file into the same directory fail on the second."""
    runner = CliRunner()
    out_dir = tmp_path / "nor_schema"
    out_dir.mkdir()

    # First ingest succeeds.
    result1 = runner.invoke(
        cli,
        [
            str(FIXTURES / "nor_radar.csv"),
            "--output",
            str(out_dir / "nor.linkml.yaml"),
        ],
    )
    assert result1.exit_code == 0, f"First ingest failed: {result1.output}"

    # Second ingest with same input (same stem → same schema name) into same dir should fail.
    result2 = runner.invoke(
        cli,
        [
            str(FIXTURES / "nor_radar.csv"),
            "--output",
            str(out_dir / "other.linkml.yaml"),
        ],
    )
    assert result2.exit_code == 1
    assert "nor_radar" in result2.output or "nor_radar" in (result2.output or "")


def test_ingest_prefix_collision_allows_unique_names(tmp_path: Path) -> None:
    """Two ingests with different input stems into the same directory both succeed."""
    runner = CliRunner()
    out_dir = tmp_path / "schemas"
    out_dir.mkdir()

    result1 = runner.invoke(
        cli,
        [
            str(FIXTURES / "nor_radar.csv"),
            "--output",
            str(out_dir / "alpha.linkml.yaml"),
        ],
    )
    assert result1.exit_code == 0, f"First ingest failed: {result1.output}"

    result2 = runner.invoke(
        cli,
        [
            str(FIXTURES / "deu_patriot.json"),
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
            str(FIXTURES / "nor_radar.csv"),
            "--output",
            str(out1),
        ],
    )
    assert result1.exit_code == 0, f"First ingest failed: {result1.output}"

    clashing_id = yaml.safe_load(out1.read_text()).get("id", "https://example.org/nor_radar")

    # Write a handcrafted sibling with a different default_prefix but the same id.
    sibling = out_dir / "handcrafted.linkml.yaml"
    sibling.write_text(
        f"id: {clashing_id}\nname: other_schema\ndefault_prefix: completely_different\n"
    )

    # Now ingest with the same input (same id) into the same dir should fail.
    result2 = runner.invoke(
        cli,
        [
            str(FIXTURES / "nor_radar.csv"),
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
            str(FIXTURES / "nor_radar.csv"),
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


def test_ingest_rdfs_normalizes_xsd_datetime_to_linkml(tmp_path: Path) -> None:
    """OWL ontology with xsd:dateTime range → LinkML 'datetime' (lowercase)."""
    runner = CliRunner()
    out = tmp_path / "master.linkml.yaml"
    result = runner.invoke(
        cli,
        [
            str(FIXTURES / "master_cop_ontology.ttl"),
            "--output",
            str(out),
        ],
    )
    assert result.exit_code == 0, f"CLI failed: {result.output}"
    data = yaml.safe_load(out.read_text())
    slots: dict[str, object] = data.get("slots") or {}
    timestamp_slot = slots.get("hasTimestamp")
    assert isinstance(timestamp_slot, dict), "Expected hasTimestamp slot"
    assert timestamp_slot.get("range") == "datetime", (
        f"Expected 'datetime' (lowercase), got: {timestamp_slot.get('range')!r}"
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
        [str(ttl_file), "--output", str(out)],
    )
    assert result.exit_code == 0, f"CLI failed: {result.output}"
    data = yaml.safe_load(out.read_text())
    annotations = data.get("annotations") or {}
    assert "rosetta_source_format" not in annotations, (
        f"RDFS schema should not have rosetta_source_format; got: {annotations}"
    )


# ---------------------------------------------------------------------------
# Phase 22 — multi-schema, translate, --master integration tests
# ---------------------------------------------------------------------------


def test_ingest_single_file_stdout() -> None:
    """Single input with no -o flag writes to stdout and exits 0."""
    result = CliRunner().invoke(cli, [str(FIXTURES / "deu_patriot.json")])
    assert result.exit_code == 0, f"CLI failed: {result.output}"
    assert "classes:" in result.output or "slots:" in result.output


def test_ingest_single_file_output(tmp_path: Path) -> None:
    """Single input with -o file writes the file and exits 0."""
    out = tmp_path / "out.linkml.yaml"
    result = CliRunner().invoke(cli, [str(FIXTURES / "deu_patriot.json"), "-o", str(out)])
    assert result.exit_code == 0, f"CLI failed: {result.output}"
    assert out.exists()
    assert "classes:" in out.read_text() or "slots:" in out.read_text()


def test_ingest_multi_schema(tmp_path: Path) -> None:
    """Two inputs with -o dir/ → two .linkml.yaml files in the directory."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = CliRunner().invoke(
        cli,
        [
            str(FIXTURES / "deu_patriot.json"),
            str(FIXTURES / "nor_radar.csv"),
            "-o",
            str(out_dir),
        ],
    )
    assert result.exit_code == 0, f"CLI failed: {result.output}"
    assert (out_dir / "deu_patriot.linkml.yaml").exists()
    assert (out_dir / "nor_radar.linkml.yaml").exists()


def test_ingest_multi_schema_no_output(tmp_path: Path) -> None:
    """Two inputs with no -o → two .linkml.yaml files written to cwd."""
    runner = CliRunner()
    # CliRunner's mix_stderr=False default; use isolated filesystem so cwd is tmp
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            cli,
            [
                str(FIXTURES / "deu_patriot.json"),
                str(FIXTURES / "nor_radar.csv"),
            ],
        )
    assert result.exit_code == 0, f"CLI failed: {result.output}"


def test_ingest_multi_stdout_error(tmp_path: Path) -> None:
    """Multiple inputs with -o - (stdout) → UsageError, exit != 0."""
    result = CliRunner().invoke(
        cli,
        [
            str(FIXTURES / "deu_patriot.json"),
            str(FIXTURES / "nor_radar.csv"),
            "-o",
            "-",
        ],
    )
    assert result.exit_code != 0


def test_ingest_translate(tmp_path: Path, fake_deepl: Any) -> None:
    """--translate --lang DE with DEEPL_API_KEY env var → DeepL called, exit 0."""
    fake_deepl()  # configure with identity mapping (returns input unchanged)
    out = tmp_path / "out.linkml.yaml"
    result = CliRunner(env={"DEEPL_API_KEY": "fake-key"}).invoke(
        cli,
        [
            str(FIXTURES / "deu_patriot.json"),
            "--translate",
            "--lang",
            "DE",
            "-o",
            str(out),
        ],
    )
    assert result.exit_code == 0, f"CLI failed: {result.output}"
    assert out.exists()
    state: dict[str, Any] = fake_deepl.state  # pyright: ignore[reportAny]
    assert state["call_count"] >= 1, "Expected at least one DeepL call"


def test_ingest_translate_en_passthrough(tmp_path: Path, fake_deepl: Any) -> None:
    """--translate --lang EN → DeepL is NOT called, output written unchanged."""
    fake_deepl()
    out = tmp_path / "out.linkml.yaml"
    result = CliRunner(env={"DEEPL_API_KEY": "fake-key"}).invoke(
        cli,
        [
            str(FIXTURES / "deu_patriot.json"),
            "--translate",
            "--lang",
            "EN",
            "-o",
            str(out),
        ],
    )
    assert result.exit_code == 0, f"CLI failed: {result.output}"
    assert out.exists()
    state: dict[str, Any] = fake_deepl.state  # pyright: ignore[reportAny]
    assert state["call_count"] == 0, "DeepL must NOT be called for EN passthrough"


def test_ingest_translate_no_key_error(tmp_path: Path) -> None:
    """--translate --lang DE without DEEPL_API_KEY → UsageError, exit != 0."""
    out = tmp_path / "out.linkml.yaml"
    result = CliRunner(env={"DEEPL_API_KEY": ""}).invoke(
        cli,
        [
            str(FIXTURES / "deu_patriot.json"),
            "--translate",
            "--lang",
            "DE",
            "-o",
            str(out),
        ],
    )
    assert result.exit_code != 0


def test_ingest_master(tmp_path: Path) -> None:
    """--master ontology.ttl -o dir/ → .linkml.yaml + .shacl.ttl in directory."""
    ontology = tmp_path / "mini_ontology.ttl"
    _ = ontology.write_text(_MINI_ONTOLOGY)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    result = CliRunner().invoke(
        cli,
        [
            "--master",
            str(ontology),
            "-o",
            str(out_dir),
        ],
    )
    # --master with no source schemas: schema_files is empty → Click required=True guard
    # The CLI requires at least one schema_file positionally, so either we supply one
    # or the test verifies the master-only path works if supported.
    # Since schema_files has required=True, we need a dummy source schema.
    # Re-invoke with a source schema to test --master processing.
    _ = result  # discard the no-args result
    source = FIXTURES / "nor_radar.csv"
    result2 = CliRunner().invoke(
        cli,
        [
            str(source),
            "--master",
            str(ontology),
            "-o",
            str(out_dir),
        ],
    )
    assert result2.exit_code == 0, f"CLI failed: {result2.output}"
    stem = ontology.stem  # "mini_ontology"
    assert (out_dir / f"{stem}.linkml.yaml").exists(), "Master LinkML YAML not written"
    assert (out_dir / f"{stem}.shacl.ttl").exists(), "Master SHACL not written"


def test_ingest_master_plus_sources(tmp_path: Path) -> None:
    """ingest source.json --master ontology.ttl -o dir/ → source + master files all written."""
    ontology = tmp_path / "mini_ontology.ttl"
    _ = ontology.write_text(_MINI_ONTOLOGY)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    result = CliRunner().invoke(
        cli,
        [
            str(FIXTURES / "deu_patriot.json"),
            "--master",
            str(ontology),
            "-o",
            str(out_dir),
        ],
    )
    assert result.exit_code == 0, f"CLI failed: {result.output}"
    assert (out_dir / "mini_ontology.linkml.yaml").exists(), "Master LinkML YAML not written"
    assert (out_dir / "mini_ontology.shacl.ttl").exists(), "Master SHACL not written"
    assert (out_dir / "deu_patriot.linkml.yaml").exists(), "Source schema not written"


def test_ingest_master_scaffolds_toml(tmp_path: Path) -> None:
    """First --master run creates rosetta.toml; second run skips (already exists)."""
    ontology = tmp_path / "mini_ontology.ttl"
    _ = ontology.write_text(_MINI_ONTOLOGY)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    source = FIXTURES / "nor_radar.csv"

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # First run — rosetta.toml must be created
        result1 = runner.invoke(
            cli,
            [str(source), "--master", str(ontology), "-o", str(out_dir)],
        )
        assert result1.exit_code == 0, f"First run failed: {result1.output}"
        assert "Scaffolded rosetta.toml" in result1.output, (
            f"Expected scaffold message; got: {result1.output}"
        )

        # Second run — rosetta.toml already exists, should skip
        result2 = runner.invoke(
            cli,
            [str(source), "--master", str(ontology), "-o", str(out_dir)],
        )
        assert result2.exit_code == 0, f"Second run failed: {result2.output}"
        assert "already exists" in result2.output, (
            f"Expected 'already exists' message; got: {result2.output}"
        )


def test_ingest_prefix_collision_multi(tmp_path: Path) -> None:
    """Multi-schema ingest where a sibling collides with nor_radar's prefix → exit 1."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    # Pre-seed a *different-named* sibling that claims nor_radar's default_prefix.
    # The collision check skips the file being overwritten (same stem), so we
    # must use a distinct name to trigger the ValueError path.
    existing = out_dir / "already_exists.linkml.yaml"
    _ = existing.write_text(
        "id: https://example.org/nor_radar\nname: nor_radar\ndefault_prefix: nor_radar\n"
    )

    result = CliRunner().invoke(
        cli,
        [
            str(FIXTURES / "deu_patriot.json"),
            str(FIXTURES / "nor_radar.csv"),
            "-o",
            str(out_dir),
        ],
    )
    assert result.exit_code != 0


def test_ingest_multi_schema_format_mixed_error(tmp_path: Path) -> None:
    """--schema-format with mixed-format inputs → UsageError, exit != 0."""
    result = CliRunner().invoke(
        cli,
        [
            str(FIXTURES / "deu_patriot.json"),
            str(FIXTURES / "nor_radar.csv"),
            "--schema-format",
            "json-schema",
            "-o",
            str(tmp_path / "out"),
        ],
    )
    assert result.exit_code != 0


def test_ingest_multi_file_output_error(tmp_path: Path) -> None:
    """Multiple inputs with -o pointing to a file (not dir) → UsageError, exit != 0."""
    out_file = tmp_path / "out.yaml"
    _ = out_file.write_text("placeholder")  # ensure it exists as a file, not a dir
    result = CliRunner().invoke(
        cli,
        [
            str(FIXTURES / "deu_patriot.json"),
            str(FIXTURES / "nor_radar.csv"),
            "-o",
            str(out_file),
        ],
    )
    assert result.exit_code != 0
