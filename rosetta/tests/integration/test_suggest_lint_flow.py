"""Integration tests for suggest conversion_function wiring and ledger lint gate."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from click.testing import CliRunner

# ---------------------------------------------------------------------------
# Schema YAML strings
# ---------------------------------------------------------------------------

_SRC_SCHEMA = """\
id: https://example.org/source
name: source
prefixes:
  linkml: https://w3id.org/linkml/
  source: https://example.org/source/
imports:
  - linkml:types
default_range: string
classes:
  Record:
    slots:
      - temperature_c
      - altitude_m
slots:
  temperature_c:
    range: float
    description: "Temperature in Celsius"
  altitude_m:
    range: float
    description: "Altitude in meters"
"""

_MST_SCHEMA = """\
id: https://example.org/master
name: master
prefixes:
  linkml: https://w3id.org/linkml/
  master: https://example.org/master/
imports:
  - linkml:types
default_range: string
classes:
  Observation:
    slots:
      - temperature_value
      - altitude_ft
slots:
  temperature_value:
    range: integer
    description: "Temperature value"
  altitude_ft:
    range: float
    description: "Altitude in feet"
"""

_ROSETTA_TOML = """\
[conversions]
"float:integer" = "grel:math_round"

[conversions.units]
"unit:M:unit:FT" = "rfns:meterToFoot"
"""

# Minimal schemas for ledger lint tests (no unit fields, just datatype mismatch)
_LEDGER_SRC_SCHEMA = """\
id: https://example.org/lsrc
name: lsrc
prefixes:
  linkml: https://w3id.org/linkml/
  lsrc: https://example.org/lsrc/
imports:
  - linkml:types
default_range: string
classes:
  LRecord:
    slots:
      - value_f
slots:
  value_f:
    range: float
    description: "A float value"
"""

_LEDGER_MST_SCHEMA = """\
id: https://example.org/lmst
name: lmst
prefixes:
  linkml: https://w3id.org/linkml/
  lmst: https://example.org/lmst/
imports:
  - linkml:types
default_range: string
classes:
  LObservation:
    slots:
      - value_i
slots:
  value_i:
    range: integer
    description: "An integer value"
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_encode(texts: list[str]) -> list[list[float]]:
    result = []
    for text in texts:
        h = hashlib.md5(text.encode()).hexdigest()
        vec = [int(c, 16) / 15.0 for c in h[:16]]
        result.append(vec)
    return result


class _FakeEmbeddingModel:
    def __init__(self, model_name: str = "intfloat/e5-large-v2") -> None:
        self.model_name = model_name

    def encode(self, texts: list[str]) -> list[list[float]]:
        return _fake_encode(texts)

    def encode_query(self, texts: list[str]) -> list[list[float]]:
        return _fake_encode(texts)


def _runner() -> CliRunner:
    return CliRunner(mix_stderr=False)


def _data_rows(output: str) -> list[str]:
    return [
        ln
        for ln in output.splitlines()
        if ln.strip() and "\t" in ln and not ln.startswith(("#", "subject_id"))
    ]


def _parse_tsv(output: str) -> tuple[list[str], list[dict[str, str]]]:
    """Return (columns, rows-as-dicts) from SSSOM TSV output."""
    lines = [ln for ln in output.splitlines() if ln.strip() and not ln.startswith("#")]
    if not lines:
        return [], []
    cols = lines[0].split("\t")
    rows = []
    for ln in lines[1:]:
        if "\t" in ln:
            fields = ln.split("\t")
            rows.append(dict(zip(cols, fields)))
    return cols, rows


def _make_proposals_tsv(tmp_path: Path, rows: list[dict[str, str]]) -> Path:
    """Write a valid SSSOM TSV proposals file."""
    from rosetta.core.models import SSSOM_COLUMNS

    p = tmp_path / "proposals.sssom.tsv"
    lines = [
        "# mapping_set_id: https://rosetta-cli/mappings",
        "# mapping_tool: rosetta suggest",
        "# license: https://creativecommons.org/licenses/by/4.0/",
        "# curie_map:",
        "#   skos: http://www.w3.org/2004/02/skos/core#",
        "#   semapv: https://w3id.org/semapv/vocab/",
        "\t".join(SSSOM_COLUMNS),
    ]
    for row in rows:
        lines.append("\t".join(row.get(c, "") for c in SSSOM_COLUMNS))
    p.write_text("\n".join(lines) + "\n")
    return p


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestSuggestLintFlow:
    def test_suggest_populates_conversion_function(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """suggest auto-fills conversion_function for float→integer pairs from rosetta.toml."""
        src_f = tmp_path / "source.yaml"
        src_f.write_text(_SRC_SCHEMA)
        mst_f = tmp_path / "master.yaml"
        mst_f.write_text(_MST_SCHEMA)
        (tmp_path / "rosetta.toml").write_text(_ROSETTA_TOML)

        # Patch embedding model
        monkeypatch.setattr("rosetta.cli.suggest.EmbeddingModel", _FakeEmbeddingModel)
        # Patch load_config to load from tmp_path/rosetta.toml
        import tomllib

        with (tmp_path / "rosetta.toml").open("rb") as fh:
            cfg = tomllib.load(fh)
        monkeypatch.setattr("rosetta.cli.suggest.load_config", lambda: cfg)

        from rosetta.cli.suggest import cli

        result = _runner().invoke(
            cli,
            [str(src_f), str(mst_f), "--audit-log", str(tmp_path / "audit.tsv")],
        )
        assert result.exit_code == 0, result.output + str(result.exception)

        _, rows = _parse_tsv(result.output)
        assert rows, "Expected at least one suggestion row"

        # Find rows where subject_datatype=float and object_datatype=integer
        float_to_int = [
            r
            for r in rows
            if r.get("subject_datatype") == "float" and r.get("object_datatype") == "integer"
        ]
        assert float_to_int, "Expected at least one float→integer row"
        for r in float_to_int:
            assert r.get("conversion_function") == "grel:math_round", (
                f"Expected grel:math_round for float→integer, got {r.get('conversion_function')!r}"
            )

    def test_suggest_unit_pair_populates_conversion_function(self, tmp_path: Path) -> None:
        """populate_conversion_functions fills rfns:meterToFoot for unit:M→unit:FT rows.

        Note: detect_unit relies on the slot *name* (not the title-cased label that
        suggest emits).  We therefore test the wiring directly via
        populate_conversion_functions with empty labels, so unit_label falls back to
        the local part of subject_id / object_id — the same path used by lint.
        """
        import tomllib

        from rosetta.core.config import load_conversion_policies
        from rosetta.core.function_library import FunctionLibrary
        from rosetta.core.lint import populate_conversion_functions
        from rosetta.core.models import SSSOMRow

        toml_path = tmp_path / "rosetta.toml"
        toml_path.write_text(_ROSETTA_TOML)
        with toml_path.open("rb") as fh:
            cfg = tomllib.load(fh)

        library = FunctionLibrary.load_builtins()
        policies = load_conversion_policies(cfg)

        row = SSSOMRow(
            subject_id="source:altitude_m",
            predicate_id="skos:relatedMatch",
            object_id="master:altitude_ft",
            mapping_justification="semapv:LexicalMatching",
            confidence=0.8,
            subject_label="",
            object_label="",
            subject_datatype="float",
            object_datatype="float",
        )
        populate_conversion_functions([row], policies, library)
        assert row.conversion_function == "rfns:meterToFoot", (
            f"Expected rfns:meterToFoot for unit:M→unit:FT, got {row.conversion_function!r}"
        )

    def test_lint_gate_passes_with_covered_conversion(self, tmp_path: Path) -> None:
        """ledger append passes when float→integer mismatch has grel:math_round declared."""
        src_f = tmp_path / "src.yaml"
        src_f.write_text(_LEDGER_SRC_SCHEMA)
        mst_f = tmp_path / "mst.yaml"
        mst_f.write_text(_LEDGER_MST_SCHEMA)
        log_f = tmp_path / "log.tsv"

        proposals = _make_proposals_tsv(
            tmp_path,
            [
                {
                    "subject_id": "lsrc:value_f",
                    "predicate_id": "skos:exactMatch",
                    "object_id": "lmst:value_i",
                    "mapping_justification": "semapv:ManualMappingCuration",
                    "confidence": "0.9",
                    "subject_label": "value_f",
                    "object_label": "value_i",
                    "subject_datatype": "float",
                    "object_datatype": "integer",
                    "conversion_function": "grel:math_round",
                }
            ],
        )

        from rosetta.cli.ledger import cli

        result = _runner().invoke(
            cli,
            [
                "--audit-log",
                str(log_f),
                "append",
                "--role",
                "analyst",
                str(proposals),
                "--source-schema",
                str(src_f),
                "--master-schema",
                str(mst_f),
            ],
        )
        assert result.exit_code == 0, (
            f"Expected exit 0 (conversion covered), got {result.exit_code}.\n"
            f"stdout: {result.output}\nstderr: {getattr(result, 'stderr', '')}"
        )

    def test_lint_gate_blocks_undeclared_function(self, tmp_path: Path) -> None:
        """ledger append blocks when conversion_function is not in the function library."""
        src_f = tmp_path / "src.yaml"
        src_f.write_text(_LEDGER_SRC_SCHEMA)
        mst_f = tmp_path / "mst.yaml"
        mst_f.write_text(_LEDGER_MST_SCHEMA)
        log_f = tmp_path / "log.tsv"

        proposals = _make_proposals_tsv(
            tmp_path,
            [
                {
                    "subject_id": "lsrc:value_f",
                    "predicate_id": "skos:exactMatch",
                    "object_id": "lmst:value_i",
                    "mapping_justification": "semapv:ManualMappingCuration",
                    "confidence": "0.9",
                    "subject_label": "value_f",
                    "object_label": "value_i",
                    "subject_datatype": "float",
                    "object_datatype": "integer",
                    "conversion_function": "rfns:nonexistent",
                }
            ],
        )

        from rosetta.cli.ledger import cli

        result = _runner().invoke(
            cli,
            [
                "--audit-log",
                str(log_f),
                "append",
                "--role",
                "analyst",
                str(proposals),
                "--source-schema",
                str(src_f),
                "--master-schema",
                str(mst_f),
            ],
        )
        assert result.exit_code == 1, (
            f"Expected exit 1 (undeclared function BLOCK), got {result.exit_code}.\n"
            f"stdout: {result.output}\nstderr: {getattr(result, 'stderr', '')}"
        )
        combined = result.output + getattr(result, "stderr", "")
        assert "undeclared_function" in combined or "nonexistent" in combined, (
            f"Expected undeclared_function finding in output, got: {combined}"
        )
