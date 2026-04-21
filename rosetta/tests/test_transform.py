"""Tests for rosetta run CLI (migrated from the old yarrrml-gen --run tests, Task 5)."""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path

import pytest
import rdflib
from click.testing import CliRunner
from rdflib.namespace import RDF

from rosetta.cli.transform import cli

# Fixture paths
_FIXTURES = Path("rosetta/tests/fixtures/nations")
_NOR_SCHEMA = _FIXTURES / "nor_radar.linkml.yaml"
_MC_SCHEMA = _FIXTURES / "master_cop.linkml.yaml"
_NOR_SSSOM = _FIXTURES / "sssom_nor_approved.sssom.tsv"


def _fixed_graph() -> rdflib.Graph:
    g = rdflib.Graph()
    g.add(
        (
            rdflib.URIRef("https://example.org/widget/1"),
            RDF.type,
            rdflib.URIRef("https://example.org/tiny/Widget"),
        )
    )
    return g


@contextlib.contextmanager
def _fake_runner_yielding(graph: rdflib.Graph) -> Iterator[rdflib.Graph]:
    yield graph


@pytest.fixture()
def dummy_yarrrml(tmp_path: Path) -> Path:
    """Write a minimal YARRRML placeholder file for run.py invocations."""
    p = tmp_path / "mapping.yarrrml.yaml"
    p.write_text("prefixes:\n  ex: http://example.org/\nmappings: {}\n", encoding="utf-8")
    return p


@pytest.fixture()
def dummy_data(tmp_path: Path) -> Path:
    """Write a minimal CSV data file."""
    p = tmp_path / "data.csv"
    p.write_text("id,label\n1,x\n", encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Positional arg / missing-arg tests
# ---------------------------------------------------------------------------


def test_run_missing_mapping_file_exits_2() -> None:
    """Missing MAPPING_FILE positional → Click exits 2."""
    result = CliRunner(mix_stderr=False).invoke(cli, [])
    assert result.exit_code == 2


def test_run_missing_source_file_exits_2(dummy_yarrrml: Path) -> None:
    """MAPPING_FILE present but SOURCE_FILE missing → Click exits 2."""
    result = CliRunner(mix_stderr=False).invoke(
        cli,
        [str(dummy_yarrrml), "--master-schema", str(_MC_SCHEMA)],
    )
    assert result.exit_code == 2


def test_run_with_nonexistent_source_file_exits_2(dummy_yarrrml: Path, tmp_path: Path) -> None:
    """SOURCE_FILE that does not exist → Click exits 2 (Path(exists=True))."""
    bogus = tmp_path / "no_such_file.csv"
    result = CliRunner(mix_stderr=False).invoke(
        cli,
        [str(dummy_yarrrml), str(bogus), "--master-schema", str(_MC_SCHEMA)],
    )
    assert result.exit_code == 2


# ---------------------------------------------------------------------------
# Happy path — monkeypatched runner + framer
# ---------------------------------------------------------------------------


def test_run_happy_path_writes_jsonld_to_stdout(
    tmp_path: Path,
    dummy_yarrrml: Path,
    dummy_data: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Monkeypatched runner + framer: JSON-LD bytes reach stdout."""
    fixed_bytes = b'{"@context": {}, "@graph": []}'

    monkeypatch.setattr(
        "rosetta.cli.transform.run_materialize",
        lambda *a, **kw: _fake_runner_yielding(_fixed_graph()),
    )
    monkeypatch.setattr(
        "rosetta.cli.transform.graph_to_jsonld",
        lambda *a, **kw: fixed_bytes,
    )
    result = CliRunner(mix_stderr=False).invoke(
        cli,
        [str(dummy_yarrrml), str(dummy_data), "--master-schema", str(_MC_SCHEMA)],
    )
    assert result.exit_code == 0, result.stderr + (result.exception and str(result.exception) or "")
    assert fixed_bytes.decode("utf-8") in result.stdout


def test_run_with_output_flag_writes_file(
    tmp_path: Path,
    dummy_yarrrml: Path,
    dummy_data: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """-o/--output redirects bytes to file; stdout has no JSON-LD payload."""
    jsonld_out = tmp_path / "out.jsonld"
    fixed_bytes = b'{"@context": {"ex": "https://ex.org/"}, "@graph": []}'

    monkeypatch.setattr(
        "rosetta.cli.transform.run_materialize",
        lambda *a, **kw: _fake_runner_yielding(_fixed_graph()),
    )
    monkeypatch.setattr(
        "rosetta.cli.transform.graph_to_jsonld",
        lambda *a, **kw: fixed_bytes,
    )
    result = CliRunner(mix_stderr=False).invoke(
        cli,
        [
            str(dummy_yarrrml),
            str(dummy_data),
            "--master-schema",
            str(_MC_SCHEMA),
            "-o",
            str(jsonld_out),
        ],
    )
    assert result.exit_code == 0, result.stderr
    assert jsonld_out.read_bytes() == fixed_bytes
    assert "@context" not in result.stdout


def test_run_with_runner_error_exits_1(
    tmp_path: Path,
    dummy_yarrrml: Path,
    dummy_data: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A runtime error from run_materialize produces exit 1."""

    @contextlib.contextmanager
    def _boom(*args: object, **kwargs: object) -> Iterator[rdflib.Graph]:
        raise RuntimeError("materialize failed")
        yield rdflib.Graph()  # unreachable  # pragma: no cover

    monkeypatch.setattr("rosetta.cli.transform.run_materialize", _boom)
    result = CliRunner(mix_stderr=False).invoke(
        cli,
        [str(dummy_yarrrml), str(dummy_data), "--master-schema", str(_MC_SCHEMA)],
    )
    assert result.exit_code == 1
    assert "@context" not in result.stdout


# ---------------------------------------------------------------------------
# --workdir
# ---------------------------------------------------------------------------


def test_run_with_workdir_supplied(
    tmp_path: Path,
    dummy_yarrrml: Path,
    dummy_data: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--workdir path is honored; morph artifact persists after run."""
    wd = tmp_path / "wd"
    captured: dict[str, object] = {}

    @contextlib.contextmanager
    def _capture(
        yarrrml_text: str, data_path: Path, work_dir: Path | None
    ) -> Iterator[rdflib.Graph]:
        captured["work_dir"] = work_dir
        if work_dir is not None:
            work_dir.mkdir(parents=True, exist_ok=True)
            (work_dir / "mapping.yml").write_text("mock mapping\n", encoding="utf-8")
        yield _fixed_graph()

    monkeypatch.setattr("rosetta.cli.transform.run_materialize", _capture)
    monkeypatch.setattr(
        "rosetta.cli.transform.graph_to_jsonld",
        lambda *a, **kw: b'{"@context": {}, "@graph": []}',
    )
    result = CliRunner(mix_stderr=False).invoke(
        cli,
        [
            str(dummy_yarrrml),
            str(dummy_data),
            "--master-schema",
            str(_MC_SCHEMA),
            "--workdir",
            str(wd),
        ],
    )
    assert result.exit_code == 0, result.stderr
    assert captured["work_dir"] == wd.resolve()
    assert (wd / "mapping.yml").is_file()


# ---------------------------------------------------------------------------
# --context-output
# ---------------------------------------------------------------------------


def test_run_with_context_output_forwarded(
    tmp_path: Path,
    dummy_yarrrml: Path,
    dummy_data: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--context-output path is forwarded to graph_to_jsonld."""
    ctx_out = tmp_path / "ctx.json"
    captured: dict[str, object] = {}

    def _capture_jsonld(
        graph: rdflib.Graph,
        master: Path,
        context_output: Path | None = None,
    ) -> bytes:
        captured["context_output"] = context_output
        if context_output is not None:
            context_output.write_text('{"ex": "https://ex.org/"}', encoding="utf-8")
        return b'{"@context": {}, "@graph": []}'

    monkeypatch.setattr(
        "rosetta.cli.transform.run_materialize",
        lambda *a, **kw: _fake_runner_yielding(_fixed_graph()),
    )
    monkeypatch.setattr("rosetta.cli.transform.graph_to_jsonld", _capture_jsonld)
    result = CliRunner(mix_stderr=False).invoke(
        cli,
        [
            str(dummy_yarrrml),
            str(dummy_data),
            "--master-schema",
            str(_MC_SCHEMA),
            "--context-output",
            str(ctx_out),
        ],
    )
    assert result.exit_code == 0, result.stderr
    assert captured["context_output"] == ctx_out.resolve()
    assert ctx_out.is_file()


# ---------------------------------------------------------------------------
# Empty graph warning
# ---------------------------------------------------------------------------


def test_run_empty_graph_warns_and_exits_0(
    tmp_path: Path,
    dummy_yarrrml: Path,
    dummy_data: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty materialized graph warns on stderr but still exits 0."""
    monkeypatch.setattr(
        "rosetta.cli.transform.run_materialize",
        lambda *a, **kw: _fake_runner_yielding(rdflib.Graph()),
    )
    monkeypatch.setattr(
        "rosetta.cli.transform.graph_to_jsonld",
        lambda *a, **kw: b'{"@context": {}, "@graph": []}',
    )
    result = CliRunner(mix_stderr=False).invoke(
        cli,
        [str(dummy_yarrrml), str(dummy_data), "--master-schema", str(_MC_SCHEMA)],
    )
    assert result.exit_code == 0, result.stderr
    assert "produced 0 triples" in result.stderr
    assert "@context" in result.stdout


# ---------------------------------------------------------------------------
# --validate pass and fail paths
# ---------------------------------------------------------------------------


def test_run_validate_pass_exits_0_and_emits_jsonld(
    tmp_path: Path,
    dummy_yarrrml: Path,
    dummy_data: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--validate with conforming shapes → exit 0, JSON-LD emitted."""
    from rosetta.core.models import ValidationReport, ValidationSummary

    shapes_dir = tmp_path / "shapes"
    shapes_dir.mkdir()

    fixed_bytes = b'{"@context": {}, "@graph": []}'
    conforming_report = ValidationReport(
        findings=[],
        summary=ValidationSummary(violation=0, warning=0, info=0, conforms=True),
    )

    monkeypatch.setattr(
        "rosetta.cli.transform.run_materialize",
        lambda *a, **kw: _fake_runner_yielding(_fixed_graph()),
    )
    monkeypatch.setattr(
        "rosetta.cli.transform.graph_to_jsonld",
        lambda *a, **kw: fixed_bytes,
    )
    monkeypatch.setattr(
        "rosetta.core.shacl_validate.validate_graph",
        lambda *a, **kw: conforming_report,
    )
    monkeypatch.setattr(
        "rosetta.core.shapes_loader.load_shapes_from_dir",
        lambda _p: rdflib.Graph(),
    )

    result = CliRunner(mix_stderr=False).invoke(
        cli,
        [
            str(dummy_yarrrml),
            str(dummy_data),
            "--master-schema",
            str(_MC_SCHEMA),
            "--validate",
            str(shapes_dir),
        ],
    )
    assert result.exit_code == 0, result.stderr + (
        str(result.exception) if result.exception else ""
    )
    assert fixed_bytes.decode("utf-8") in result.stdout


def test_run_validate_fail_exits_1_no_jsonld(
    tmp_path: Path,
    dummy_yarrrml: Path,
    dummy_data: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--validate with violations → exit 1, no JSON-LD, report written to file."""
    from rosetta.core.models import ValidationFinding, ValidationReport, ValidationSummary

    shapes_dir = tmp_path / "shapes"
    shapes_dir.mkdir()
    report_path = tmp_path / "report.json"

    failing_report = ValidationReport(
        findings=[
            ValidationFinding(
                focus_node="https://example.org/widget/1",
                severity="Violation",
                constraint="sh:MinCountConstraintComponent",
                source_shape=None,
                message="Missing required property",
            )
        ],
        summary=ValidationSummary(violation=1, warning=0, info=0, conforms=False),
    )

    monkeypatch.setattr(
        "rosetta.cli.transform.run_materialize",
        lambda *a, **kw: _fake_runner_yielding(_fixed_graph()),
    )
    monkeypatch.setattr(
        "rosetta.cli.transform.graph_to_jsonld",
        lambda *a, **kw: b'{"@context": {}, "@graph": []}',
    )
    monkeypatch.setattr(
        "rosetta.core.shacl_validate.validate_graph",
        lambda *a, **kw: failing_report,
    )
    monkeypatch.setattr(
        "rosetta.core.shapes_loader.load_shapes_from_dir",
        lambda _p: rdflib.Graph(),
    )

    result = CliRunner(mix_stderr=False).invoke(
        cli,
        [
            str(dummy_yarrrml),
            str(dummy_data),
            "--master-schema",
            str(_MC_SCHEMA),
            "--validate",
            str(shapes_dir),
            "--validate-report",
            str(report_path),
        ],
    )
    assert result.exit_code == 1, f"expected exit 1; got {result.exit_code}: {result.stderr}"
    assert "@context" not in result.stdout, "JSON-LD must not be emitted on validation failure"
    assert report_path.exists(), "validation report file must be written"
    import json as _json

    written = _json.loads(report_path.read_text(encoding="utf-8"))
    assert written["summary"]["violation"] == 1


# ---------------------------------------------------------------------------
# stdout collision guard
# ---------------------------------------------------------------------------


def test_run_stdout_collision_output_and_validate_report(
    tmp_path: Path,
    dummy_yarrrml: Path,
    dummy_data: Path,
) -> None:
    """--output (stdout) and --validate-report - both target stdout → exit 2."""
    result = CliRunner(mix_stderr=False).invoke(
        cli,
        [
            str(dummy_yarrrml),
            str(dummy_data),
            "--master-schema",
            str(_MC_SCHEMA),
            "--validate-report",
            "-",
        ],
    )
    assert result.exit_code == 2, (
        f"expected exit 2 from stdout-collision UsageError; got {result.exit_code}: "
        f"stderr={result.stderr!r}"
    )
    assert "stdout" in result.stderr.lower()
