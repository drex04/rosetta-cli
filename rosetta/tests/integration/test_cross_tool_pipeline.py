"""Cross-tool integration tests for format compatibility across tool boundaries.

Validates that the output of each tool is consumable by the next tool in
the pipeline. Catches seam bugs like the '/' vs ':' CURIE separator
mismatch where embed produced 'nor_radar/Observation' but yarrrml-gen
expected 'nor_radar:Observation'.

Seams tested:
  - ingest -> embed
  - ingest -> translate -> embed
  - embed -> suggest -> yarrrml-gen
  - suggest -> accredit
  - suggest -> lint
  - shacl-gen -> validate
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from click.testing import CliRunner

from rosetta.cli.accredit import cli as accredit_cli
from rosetta.cli.embed import cli as embed_cli
from rosetta.cli.ingest import cli as ingest_cli
from rosetta.cli.lint import cli as lint_cli
from rosetta.cli.shacl_gen import cli as shacl_gen_cli
from rosetta.cli.suggest import cli as suggest_cli
from rosetta.cli.translate import cli as translate_cli
from rosetta.cli.validate import cli as validate_cli
from rosetta.cli.yarrrml_gen import cli as yarrrml_cli
from rosetta.core.accredit import AUDIT_LOG_COLUMNS, SSSOM_HEADER, parse_sssom_tsv
from rosetta.core.models import LintReport

pytestmark = [pytest.mark.integration, pytest.mark.slow]


class _FakeModel:
    """Deterministic 4-dim fake for sentence-transformers."""

    def encode(self, texts: list[str]) -> np.ndarray:
        return np.random.default_rng(42).random((len(texts), 4)).astype(np.float32)


@pytest.fixture()
def mock_model(monkeypatch: pytest.MonkeyPatch) -> None:
    import sentence_transformers

    monkeypatch.setattr(sentence_transformers, "SentenceTransformer", lambda name: _FakeModel())


def test_embed_suggest_yarrrml_gen_format_compatibility(
    tmp_path: Path,
    nor_linkml_path: Path,
    master_schema_path: Path,
    mock_model: None,
) -> None:
    """Chain embed -> suggest -> yarrrml-gen with real tool output at every seam.

    No hand-crafted intermediates. Suggest SSSOM rows are promoted to
    HumanCuration (simulating accreditor approval) and fed to yarrrml-gen.
    The primary assertion is that yarrrml-gen's prefix filter accepts the
    suggest output format -- not that the mock model produces meaningful mappings.
    """
    runner = CliRunner(mix_stderr=False)

    # 1. Embed both schemas
    src_embed = tmp_path / "src.embed.json"
    result = runner.invoke(embed_cli, ["--input", str(nor_linkml_path), "--output", str(src_embed)])
    assert result.exit_code == 0, f"embed(src) failed: {result.stderr}"

    mst_embed = tmp_path / "master.embed.json"
    result = runner.invoke(
        embed_cli, ["--input", str(master_schema_path), "--output", str(mst_embed)]
    )
    assert result.exit_code == 0, f"embed(master) failed: {result.stderr}"

    # 2. Verify embed output keys use CURIE format (colon separator)
    src_keys = list(json.loads(src_embed.read_text()).keys())
    non_curie = [k for k in src_keys if ":" not in k]
    assert not non_curie, f"embed keys missing CURIE ':' separator: {non_curie}"

    # 3. Suggest
    suggest_sssom = tmp_path / "suggest.sssom.tsv"
    result = runner.invoke(
        suggest_cli,
        [str(src_embed), str(mst_embed), "--output", str(suggest_sssom), "--top-k", "1"],
    )
    assert result.exit_code == 0, f"suggest failed: {result.stderr}"

    # 4. Verify suggest subject_ids use CURIE format
    suggest_rows = parse_sssom_tsv(suggest_sssom)
    assert suggest_rows, "suggest produced no rows"
    bad_ids = [r.subject_id for r in suggest_rows if ":" not in r.subject_id]
    assert not bad_ids, f"suggest subject_ids missing ':' separator: {bad_ids}"

    # 5. Promote to HC and write approved SSSOM (simulates accreditor approval)
    approved = tmp_path / "approved.sssom.tsv"
    with approved.open("w", encoding="utf-8", newline="") as fh:
        fh.write(SSSOM_HEADER)
        writer = csv.writer(fh, delimiter="\t", lineterminator="\n")
        writer.writerow(AUDIT_LOG_COLUMNS)
        for row in suggest_rows:
            writer.writerow(
                [
                    row.subject_id,
                    "skos:exactMatch",
                    row.object_id,
                    "semapv:HumanCuration",
                    row.confidence,
                    row.subject_label,
                    row.object_label,
                    row.mapping_date.isoformat() if row.mapping_date else "",
                    row.record_id or "",
                    "",
                    "",
                    "",
                    "",
                ]
            )

    # 6. Feed to yarrrml-gen -- prefix filter must accept the format
    result = runner.invoke(
        yarrrml_cli,
        [
            "--sssom",
            str(approved),
            "--source-schema",
            str(nor_linkml_path),
            "--master-schema",
            str(master_schema_path),
            "--force",
        ],
    )
    combined = result.output + result.stderr
    assert "no rows after filtering" not in combined, (
        "yarrrml-gen rejected all rows -- format mismatch between suggest output "
        "and yarrrml-gen prefix filter. This indicates embed/suggest produce "
        "subject_ids in a format yarrrml-gen does not expect."
    )


def _run_embed_suggest(
    runner: CliRunner,
    tmp_path: Path,
    nor_linkml_path: Path,
    master_schema_path: Path,
) -> Path:
    """Shared helper: embed both schemas, run suggest, return suggest SSSOM path."""
    src_embed = tmp_path / "src.embed.json"
    runner.invoke(embed_cli, ["--input", str(nor_linkml_path), "--output", str(src_embed)])
    mst_embed = tmp_path / "master.embed.json"
    runner.invoke(embed_cli, ["--input", str(master_schema_path), "--output", str(mst_embed)])
    suggest_sssom = tmp_path / "suggest.sssom.tsv"
    result = runner.invoke(
        suggest_cli,
        [str(src_embed), str(mst_embed), "--output", str(suggest_sssom), "--top-k", "1"],
    )
    assert result.exit_code == 0, f"suggest failed: {result.stderr}"
    return suggest_sssom


def test_suggest_to_accredit_ingest(
    tmp_path: Path,
    nor_linkml_path: Path,
    master_schema_path: Path,
    tmp_rosetta_toml: Path,
    mock_model: None,
) -> None:
    """Suggest SSSOM output can be ingested by accredit without errors.

    Tests the suggest -> accredit seam: column format, header parsing,
    and justification values must be compatible.
    """
    runner = CliRunner(mix_stderr=False)
    suggest_sssom = _run_embed_suggest(runner, tmp_path, nor_linkml_path, master_schema_path)

    result = runner.invoke(
        accredit_cli,
        ["--config", str(tmp_rosetta_toml), "ingest", str(suggest_sssom)],
    )
    assert result.exit_code == 0, (
        f"accredit ingest failed on suggest output: {result.stderr}\n"
        "This indicates a format mismatch between suggest SSSOM and accredit parser."
    )


def test_suggest_to_lint(
    tmp_path: Path,
    nor_linkml_path: Path,
    master_schema_path: Path,
    mock_model: None,
) -> None:
    """Suggest SSSOM output can be linted without parse errors.

    Tests the suggest -> lint seam: column format and header must be
    compatible with the lint parser.
    """
    runner = CliRunner(mix_stderr=False)
    suggest_sssom = _run_embed_suggest(runner, tmp_path, nor_linkml_path, master_schema_path)

    no_accredit_toml = tmp_path / "rosetta.toml"
    no_accredit_toml.write_text("[suggest]\ntop_k = 5\n")

    result = runner.invoke(
        lint_cli,
        ["--sssom", str(suggest_sssom), "--config", str(no_accredit_toml)],
    )
    assert result.exit_code == 0, (
        f"lint failed on suggest output: {result.stderr}\n"
        "This indicates a format mismatch between suggest SSSOM and lint parser."
    )
    report = LintReport.model_validate_json(result.stdout)
    assert report.summary.block == 0, (
        f"lint produced BLOCK findings on suggest output: "
        f"{[f.rule for f in report.findings if f.severity == 'BLOCK']}"
    )


# ---------------------------------------------------------------------------
# Seam: ingest -> embed
# ---------------------------------------------------------------------------


def test_ingest_to_embed(
    tmp_path: Path,
    nor_csv_path: Path,
    mock_model: None,
) -> None:
    """Ingest CSV -> embed: ingest output is consumable by embed.

    Tests that ingest's LinkML YAML format (schema name, prefix, slot
    structure) produces valid embed keys in CURIE format.
    """
    runner = CliRunner(mix_stderr=False)

    linkml = tmp_path / "nor_radar.linkml.yaml"
    result = runner.invoke(
        ingest_cli,
        ["--input", str(nor_csv_path), "--format", "csv", "--output", str(linkml)],
    )
    assert result.exit_code == 0, f"ingest failed: {result.stderr}"

    embed_out = tmp_path / "embed.json"
    result = runner.invoke(embed_cli, ["--input", str(linkml), "--output", str(embed_out)])
    assert result.exit_code == 0, f"embed failed on ingest output: {result.stderr}"

    keys = list(json.loads(embed_out.read_text()).keys())
    assert keys, "embed produced no keys from ingest output"
    non_curie = [k for k in keys if ":" not in k]
    assert not non_curie, f"embed keys missing CURIE ':' separator: {non_curie}"


# ---------------------------------------------------------------------------
# Seam: ingest -> translate -> embed
# ---------------------------------------------------------------------------


def test_ingest_translate_embed(
    tmp_path: Path,
    nor_csv_path: Path,
    fake_deepl: Any,
    mock_model: None,
) -> None:
    """Ingest CSV -> translate -> embed: full upstream pipeline produces valid embed keys.

    Uses fake_deepl to mock the DeepL API. Tests that translate's
    output (re-serialized LinkML YAML) is consumable by embed.
    """
    fake_deepl({})
    runner = CliRunner(mix_stderr=False)

    linkml = tmp_path / "nor_radar.linkml.yaml"
    result = runner.invoke(
        ingest_cli,
        ["--input", str(nor_csv_path), "--format", "csv", "--output", str(linkml)],
    )
    assert result.exit_code == 0, f"ingest failed: {result.stderr}"

    translated = tmp_path / "nor_radar_en.linkml.yaml"
    result = runner.invoke(
        translate_cli,
        [
            "--input",
            str(linkml),
            "--source-lang",
            "NO",
            "--output",
            str(translated),
            "--deepl-key",
            "fake-key",
        ],
    )
    assert result.exit_code == 0, f"translate failed: {result.stderr}"

    embed_out = tmp_path / "embed.json"
    result = runner.invoke(embed_cli, ["--input", str(translated), "--output", str(embed_out)])
    assert result.exit_code == 0, f"embed failed on translate output: {result.stderr}"

    keys = list(json.loads(embed_out.read_text()).keys())
    assert keys, "embed produced no keys from translated schema"
    non_curie = [k for k in keys if ":" not in k]
    assert not non_curie, f"embed keys missing CURIE ':' separator: {non_curie}"


# ---------------------------------------------------------------------------
# Seam: shacl-gen -> validate
# ---------------------------------------------------------------------------


def test_shacl_gen_to_validate(
    tmp_path: Path,
    master_schema_path: Path,
    master_ontology_path: Path,
) -> None:
    """shacl-gen -> validate: generated shapes are parseable by validate.

    Tests that shacl-gen's Turtle output is a valid SHACL shapes graph
    that validate can load and apply to RDF data.
    """
    runner = CliRunner(mix_stderr=False)

    shapes = tmp_path / "shapes.ttl"
    result = runner.invoke(
        shacl_gen_cli, ["--input", str(master_schema_path), "--output", str(shapes)]
    )
    assert result.exit_code == 0, f"shacl-gen failed: {result.stderr}"
    assert shapes.stat().st_size > 0, "shacl-gen produced empty shapes file"

    result = runner.invoke(
        validate_cli,
        [
            "--data",
            str(master_ontology_path),
            "--shapes",
            str(shapes),
        ],
    )
    assert result.exit_code in (0, 1), (
        f"validate crashed on shacl-gen output (exit {result.exit_code}): "
        f"{result.stderr}\nThis indicates shacl-gen output is not valid SHACL."
    )


# ---------------------------------------------------------------------------
# Seam: yarrrml-gen --run -> shacl-gen -> validate (full pipeline)
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_yarrrml_gen_jsonld_validated_by_shacl(
    tmp_path: Path,
    nor_linkml_path: Path,
    master_schema_path: Path,
    sssom_nor_path: Path,
    nor_csv_sample_path: Path,
) -> None:
    """Full pipeline: yarrrml-gen --run produces JSON-LD, shacl-gen produces
    shapes, validate checks the JSON-LD against the shapes.

    Tests the last untested seam: yarrrml-gen's materialized output uses
    namespace URIs and class/property structure that shacl-gen's shapes
    can parse and evaluate.
    """
    import shutil

    runner = CliRunner(mix_stderr=False)

    nor_schema = tmp_path / "nor_radar.linkml.yaml"
    mc_schema = tmp_path / "master_cop.linkml.yaml"
    sssom = tmp_path / "approved.sssom.tsv"
    csv_data = tmp_path / "nor_radar.csv"
    shutil.copy(nor_linkml_path, nor_schema)
    shutil.copy(master_schema_path, mc_schema)
    shutil.copy(sssom_nor_path, sssom)
    shutil.copy(nor_csv_sample_path, csv_data)

    # 1. Generate SHACL shapes from master schema
    shapes = tmp_path / "shapes.ttl"
    result = runner.invoke(shacl_gen_cli, ["--input", str(mc_schema), "--output", str(shapes)])
    assert result.exit_code == 0, f"shacl-gen failed: {result.stderr}"

    # 2. Materialize CSV → JSON-LD via yarrrml-gen --run
    jsonld_out = tmp_path / "output.jsonld"
    result = runner.invoke(
        yarrrml_cli,
        [
            "--sssom",
            str(sssom),
            "--source-schema",
            str(nor_schema),
            "--master-schema",
            str(mc_schema),
            "--force",
            "--run",
            "--data",
            str(csv_data),
            "--jsonld-output",
            str(jsonld_out),
            "--workdir",
            str(tmp_path / "wd"),
        ],
    )
    assert result.exit_code == 0, (
        f"yarrrml-gen --run failed (exit {result.exit_code}): {result.stderr}\n{result.exception!r}"
    )
    assert jsonld_out.exists() and jsonld_out.stat().st_size > 0, (
        "yarrrml-gen produced no JSON-LD output"
    )

    # 3. Validate JSON-LD against SHACL shapes
    result = runner.invoke(
        validate_cli,
        [
            "--data",
            str(jsonld_out),
            "--data-format",
            "json-ld",
            "--shapes",
            str(shapes),
        ],
    )
    # Exit 0 = conformant, 1 = violations found. Both are valid —
    # the assertion is that validate can parse the JSON-LD and apply
    # the shapes without crashing.
    assert result.exit_code in (0, 1), (
        f"validate crashed (exit {result.exit_code}): {result.stderr}\n"
        "This indicates format incompatibility between yarrrml-gen's "
        "JSON-LD output and shacl-gen's SHACL shapes."
    )
