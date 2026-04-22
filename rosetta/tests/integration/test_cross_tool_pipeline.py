"""Cross-tool integration tests for format compatibility across tool boundaries.

Validates that the output of each tool is consumable by the next tool in
the pipeline. Catches seam bugs like the '/' vs ':' CURIE separator
mismatch where suggest produced 'nor_radar/Observation' but compile
expected 'nor_radar:Observation'.

Seams tested:
  - ingest -> suggest -> compile
  - suggest -> accredit (ledger append)
  - suggest -> lint (ledger append --dry-run)
  - ingest --master -> transform (shacl-gen via ingest, validate via transform)
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pytest
from click.testing import CliRunner

from rosetta.cli.compile import cli as compile_cli
from rosetta.cli.ingest import cli as ingest_cli
from rosetta.cli.ledger import cli as accredit_cli
from rosetta.cli.ledger import cli as ledger_cli
from rosetta.cli.suggest import cli as suggest_cli
from rosetta.core.ledger import AUDIT_LOG_COLUMNS, SSSOM_HEADER, parse_sssom_tsv
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


def test_embed_suggest_compile_format_compatibility(
    tmp_path: Path,
    nor_linkml_path: Path,
    master_schema_path: Path,
    mock_model: None,
) -> None:
    """Chain suggest -> compile with real tool output at every seam.

    No hand-crafted intermediates. Suggest SSSOM rows are promoted to
    HumanCuration (simulating accreditor approval) and fed to compile.
    The primary assertion is that compile's prefix filter accepts the
    suggest output format -- not that the mock model produces meaningful mappings.
    """
    runner = CliRunner(mix_stderr=False)

    # 1. Suggest directly from schemas
    suggest_sssom = tmp_path / "suggest.sssom.tsv"
    empty_log = tmp_path / "empty-audit-log.sssom.tsv"
    from rosetta.core.ledger import append_log as _append_log_tmp

    _append_log_tmp([], empty_log)
    result = runner.invoke(
        suggest_cli,
        [
            str(nor_linkml_path),
            str(master_schema_path),
            "--output",
            str(suggest_sssom),
            "--top-k",
            "1",
            "--audit-log",
            str(empty_log),
        ],
    )
    assert result.exit_code == 0, f"suggest failed: {result.stderr}"

    # 2. Verify suggest subject_ids use CURIE format
    suggest_rows = parse_sssom_tsv(suggest_sssom)
    assert suggest_rows, "suggest produced no rows"
    bad_ids = [r.subject_id for r in suggest_rows if ":" not in r.subject_id]
    assert not bad_ids, f"suggest subject_ids missing ':' separator: {bad_ids}"

    # 3. Promote to HC and write approved SSSOM (simulates accreditor approval)
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

    # 4. Feed to compile -- prefix filter must accept the format
    result = runner.invoke(
        compile_cli,
        [
            str(approved),
            "--source-schema",
            str(nor_linkml_path),
            "--master-schema",
            str(master_schema_path),
        ],
    )
    combined = result.output + result.stderr
    assert "no rows after filtering" not in combined, (
        "compile rejected all rows -- format mismatch between suggest output "
        "and compile prefix filter. This indicates embed/suggest produce "
        "subject_ids in a format compile does not expect."
    )


def _run_embed_suggest(
    runner: CliRunner,
    tmp_path: Path,
    nor_linkml_path: Path,
    master_schema_path: Path,
) -> Path:
    """Shared helper: run suggest directly from schemas, return suggest SSSOM path."""
    from rosetta.core.ledger import append_log as _append_log_helper

    suggest_sssom = tmp_path / "suggest.sssom.tsv"
    helper_log = tmp_path / "helper-audit-log.sssom.tsv"
    _append_log_helper([], helper_log)
    result = runner.invoke(
        suggest_cli,
        [
            str(nor_linkml_path),
            str(master_schema_path),
            "--output",
            str(suggest_sssom),
            "--top-k",
            "1",
            "--audit-log",
            str(helper_log),
        ],
    )
    assert result.exit_code == 0, f"suggest failed: {result.stderr}"
    return suggest_sssom


def test_suggest_to_accredit_append(
    tmp_path: Path,
    nor_linkml_path: Path,
    master_schema_path: Path,
    mock_model: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Suggest SSSOM output can be appended by accredit without errors.

    Tests the suggest -> accredit seam: column format, header parsing,
    and justification values must be compatible.
    """
    from rosetta.core.models import LintReport, LintSummary

    monkeypatch.setattr(
        "rosetta.cli.ledger.run_lint",
        lambda *a, **kw: LintReport(findings=[], summary=LintSummary(block=0, warning=0, info=0)),
    )
    runner = CliRunner(mix_stderr=False)
    suggest_sssom = _run_embed_suggest(runner, tmp_path, nor_linkml_path, master_schema_path)
    accredit_log = tmp_path / "accredit-audit-log.sssom.tsv"

    result = runner.invoke(
        accredit_cli,
        [
            "--audit-log",
            str(accredit_log),
            "append",
            "--role",
            "analyst",
            "--source-schema",
            str(nor_linkml_path),
            "--master-schema",
            str(master_schema_path),
            str(suggest_sssom),
        ],
    )
    assert result.exit_code == 0, (
        f"accredit append failed on suggest output: {result.stderr}\n"
        "This indicates a format mismatch between suggest SSSOM and accredit parser."
    )


def test_suggest_to_lint(
    tmp_path: Path,
    nor_linkml_path: Path,
    master_schema_path: Path,
    mock_model: None,
) -> None:
    """Suggest SSSOM output can be linted via ledger append --dry-run without parse errors.

    Tests the suggest -> lint seam: column format and header must be
    compatible with the ledger/lint parser.
    """
    runner = CliRunner(mix_stderr=False)
    suggest_sssom = _run_embed_suggest(runner, tmp_path, nor_linkml_path, master_schema_path)

    audit_log = tmp_path / "audit-log.sssom.tsv"
    from rosetta.core.ledger import append_log

    append_log([], audit_log)

    result = runner.invoke(
        ledger_cli,
        [
            "--audit-log",
            str(audit_log),
            "append",
            "--dry-run",
            "--role",
            "analyst",
            "--source-schema",
            str(nor_linkml_path),
            "--master-schema",
            str(master_schema_path),
            str(suggest_sssom),
        ],
    )
    assert result.exit_code == 0, (
        f"ledger append --dry-run failed on suggest output: {result.stderr}\n"
        "This indicates a format mismatch between suggest SSSOM and lint parser."
    )
    report = LintReport.model_validate_json(result.stdout)
    assert report.summary.block == 0, (
        f"lint produced BLOCK findings on suggest output: "
        f"{[f.rule for f in report.findings if f.severity == 'BLOCK']}"
    )


# ---------------------------------------------------------------------------
# Seam: ingest -> suggest (embed is internal to suggest)
# ---------------------------------------------------------------------------


def test_ingest_to_suggest(
    tmp_path: Path,
    nor_csv_path: Path,
    master_schema_path: Path,
    mock_model: None,
) -> None:
    """Ingest CSV -> suggest: ingest output is consumable by suggest (which embeds internally).

    Tests that ingest's LinkML YAML format (schema name, prefix, slot
    structure) produces valid suggest output with CURIE-format subject_ids.
    """
    runner = CliRunner(mix_stderr=False)

    linkml = tmp_path / "nor_radar.linkml.yaml"
    result = runner.invoke(
        ingest_cli,
        [str(nor_csv_path), "--schema-format", "csv", "--output", str(linkml)],
    )
    assert result.exit_code == 0, f"ingest failed: {result.stderr}"

    from rosetta.core.ledger import append_log as _al

    empty_log = tmp_path / "empty-audit-log.sssom.tsv"
    _al([], empty_log)
    sssom_out = tmp_path / "suggest.sssom.tsv"
    result = runner.invoke(
        suggest_cli,
        [
            str(linkml),
            str(master_schema_path),
            "--output",
            str(sssom_out),
            "--audit-log",
            str(empty_log),
            "--top-k",
            "1",
        ],
    )
    assert result.exit_code == 0, f"suggest failed on ingest output: {result.stderr}"

    rows = parse_sssom_tsv(sssom_out)
    assert rows, "suggest produced no rows from ingest output"
    non_curie = [r.subject_id for r in rows if ":" not in r.subject_id]
    assert not non_curie, f"suggest subject_ids missing CURIE ':' separator: {non_curie}"


# ---------------------------------------------------------------------------
# Seam: ingest --master (shacl-gen) -> transform (validate)
# ---------------------------------------------------------------------------


def test_shacl_gen_to_transform_validate(
    tmp_path: Path,
    nor_linkml_path: Path,
    master_schema_path: Path,
    sssom_nor_path: Path,
    nor_csv_sample_path: Path,
) -> None:
    """generate_shacl → transform --shapes-dir: shapes validate materialized JSON-LD.

    Tests the shacl-gen -> validate seam using the consolidated commands:
    `generate_shacl` (core, same logic as `ingest --master`) for SHACL generation,
    `transform --shapes-dir` for validation.
    Exit 0 (conformant) or 1 (violations) are both valid — the assertion is
    that transform can parse the generated SHACL without crashing.
    """
    import shutil

    from rosetta.cli.transform import cli as run_cli
    from rosetta.core.shacl_generator import generate_shacl

    runner = CliRunner(mix_stderr=False)

    # 1. Generate SHACL shapes from master schema via core
    shapes_dir = tmp_path / "shapes"
    shapes_dir.mkdir()
    ttl_content = generate_shacl(master_schema_path)
    (shapes_dir / "shapes.ttl").write_text(ttl_content, encoding="utf-8")

    # 2. Compile the NOR SSSOM → YARRRML
    sssom = tmp_path / "approved.sssom.tsv"
    nor_schema = tmp_path / "nor_radar.linkml.yaml"
    mc_schema = tmp_path / "master_cop.linkml.yaml"
    csv_data = tmp_path / "nor_radar.csv"
    shutil.copy(sssom_nor_path, sssom)
    shutil.copy(nor_linkml_path, nor_schema)
    shutil.copy(nor_csv_sample_path, csv_data)

    # Patch dateTime typo for morph-kgc
    mc_text = master_schema_path.read_text(encoding="utf-8")
    mc_schema.write_text(mc_text.replace("dateTime", "datetime"), encoding="utf-8")

    yarrrml_out = tmp_path / "mapping.yarrrml.yaml"
    compile_result = runner.invoke(
        compile_cli,
        [
            str(sssom),
            "--source-schema",
            str(nor_schema),
            "--master-schema",
            str(mc_schema),
            "-o",
            str(yarrrml_out),
        ],
    )
    assert compile_result.exit_code == 0, (
        f"compile failed (exit {compile_result.exit_code}): {compile_result.stderr}"
    )

    # 3. Transform CSV → JSON-LD with inline SHACL validation
    jsonld_out = tmp_path / "output.jsonld"
    result = runner.invoke(
        run_cli,
        [
            str(yarrrml_out),
            str(csv_data),
            "--master-schema",
            str(mc_schema),
            "-o",
            str(jsonld_out),
            "--shapes-dir",
            str(shapes_dir),
            "--workdir",
            str(tmp_path / "wd"),
        ],
    )
    # Exit 0 = conformant, 1 = violations found. Both are valid — the assertion
    # is that transform can parse the generated SHACL and apply it without crashing.
    assert result.exit_code in (0, 1), (
        f"transform crashed (exit {result.exit_code}): {result.stderr}\n"
        "This indicates format incompatibility between generate_shacl output "
        "and transform's validation step."
    )
