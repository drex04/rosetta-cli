"""Adversarial ingest tests — malformed / ill-encoded inputs (Plan 18-03 Task 2).

Each test follows the three-level assertion contract (D-18-08):
1. Exit code
2. Structured-output shape or stderr substring
3. One behavioral invariant (no partial file written / specific shape).

Stderr substrings are chosen to be CPython-version-stable — we assert on
project-wrapped tokens ("Error:", "line", "decode", "utf-8") rather than
exact repr strings from ``json.JSONDecodeError`` or ``xml.etree`` that may
drift across interpreter releases.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from rosetta.cli.ingest import cli as ingest_cli
from rosetta.cli.suggest import cli as suggest_cli

pytestmark = [pytest.mark.integration]


def test_ingest_malformed_json(adversarial_dir: Path, tmp_path: Path) -> None:
    """Malformed JSON with trailing comma → exit 1, JSON-related stderr, no output.

    Underlying exception: ``json.JSONDecodeError`` raised by schema-automator's
    ``JsonSchemaImportEngine.convert`` → wrapped by ``rosetta ingest`` into
    ``Error: <message>``. Observed message starts with "Illegal trailing comma"
    and includes a line number — we pin only the stable substrings.
    """
    out = tmp_path / "out.yaml"
    result = CliRunner(mix_stderr=False).invoke(
        ingest_cli,
        [
            str(adversarial_dir / "malformed_nested.json"),
            "--schema-format",
            "json-schema",
            "--output",
            str(out),
        ],
    )

    # 1. Exit code
    assert result.exit_code == 1, (
        f"expected exit 1, got {result.exit_code}; stderr={result.stderr!r}"
    )

    # 2. Stderr substring — "line" (line-number marker) is version-stable;
    #    "comma" appears because the JSON decoder's "Illegal trailing comma"
    #    message surfaces verbatim through the CLI wrapper.
    stderr_lc = result.stderr.lower()
    assert "line" in stderr_lc or "json" in stderr_lc or "comma" in stderr_lc, (
        f"expected JSON/line marker in stderr; got {result.stderr!r}"
    )

    # 3. Behavioral invariant: no partial output written
    assert not out.exists() or out.read_text() == "", (
        f"partial output written: {out.read_text()[:200]!r}"
    )


def test_ingest_truncated_xsd(adversarial_dir: Path, tmp_path: Path) -> None:
    """Truncated XSD (missing </xs:schema>) → exit 1, parse-error stderr, no output.

    Underlying exception: ``lxml.etree.XMLSyntaxError`` raised by
    schema-automator's ``XsdImportEngine`` (schema-automator uses lxml, not
    stdlib ``xml.etree``). Wrapped by ``rosetta ingest`` as
    ``Error: Premature end of data in tag ...``.
    """
    out = tmp_path / "out.yaml"
    result = CliRunner(mix_stderr=False).invoke(
        ingest_cli,
        [
            str(adversarial_dir / "truncated_complex.xsd"),
            "--schema-format",
            "xsd",
            "--output",
            str(out),
        ],
    )

    # 1. Exit code
    assert result.exit_code == 1, (
        f"expected exit 1, got {result.exit_code}; stderr={result.stderr!r}"
    )

    # 2. Stderr substring — parse/premature/end markers are stable across lxml versions
    stderr_lc = result.stderr.lower()
    assert (
        "premature" in stderr_lc
        or "parse" in stderr_lc
        or "end of data" in stderr_lc
        or "line" in stderr_lc
    ), f"expected XML parse marker in stderr; got {result.stderr!r}"

    # 3. Behavioral invariant: no partial output written
    assert not out.exists() or out.read_text() == "", (
        f"partial output written: {out.read_text()[:200]!r}"
    )


def test_ingest_wrong_encoding_csv(adversarial_dir: Path, tmp_path: Path) -> None:
    """latin-1 CSV (0xE6 byte) opened as UTF-8 → exit 1, decode stderr, no output.

    Underlying exception: ``UnicodeDecodeError`` raised when schema-automator's
    CSV importer opens the file as UTF-8. Wrapped as
    ``Error: 'utf-8' codec can't decode byte 0xe6 ...``.
    """
    out = tmp_path / "out.yaml"
    result = CliRunner(mix_stderr=False).invoke(
        ingest_cli,
        [
            str(adversarial_dir / "wrong_encoding.csv"),
            "--schema-format",
            "csv",
            "--output",
            str(out),
        ],
    )

    # 1. Exit code
    assert result.exit_code == 1, (
        f"expected exit 1, got {result.exit_code}; stderr={result.stderr!r}"
    )

    # 2. Stderr substring — "decode", "utf-8", or "codec" are all stable
    stderr_lc = result.stderr.lower()
    assert "decode" in stderr_lc or "utf-8" in stderr_lc or "codec" in stderr_lc, (
        f"expected encoding marker in stderr; got {result.stderr!r}"
    )

    # 3. Behavioral invariant: no partial output written
    assert not out.exists() or out.read_text() == "", (
        f"partial output written: {out.read_text()[:200]!r}"
    )


def test_ingest_csv_with_bom_inline(tmp_path: Path) -> None:
    """UTF-8-BOM CSV → exit 0, BOM stripped from slot names.

    ``rosetta.core.normalize._strip_bom_if_present`` detects the UTF-8 BOM
    (bytes ``\\xef\\xbb\\xbf``) and rewrites the file to a tmp copy before
    handing it to schema-automator. Result: slot names are clean, no
    ``\\ufeff`` prefix.
    """
    import yaml

    in_csv = tmp_path / "in.csv"
    # UTF-8 BOM (three bytes) + CSV payload.
    in_csv.write_bytes(b"\xef\xbb\xbf" + b"col1,col2\n1,foo\n2,bar\n")

    out = tmp_path / "out.yaml"
    result = CliRunner(mix_stderr=False).invoke(
        ingest_cli,
        [str(in_csv), "--schema-format", "csv", "--output", str(out)],
    )

    # 1. Exit code — ingestion succeeds.
    assert result.exit_code == 0, (
        f"expected exit 0, got {result.exit_code}; stderr={result.stderr!r}"
    )

    # 2. Structured output shape — valid LinkML YAML.
    assert out.exists()
    data = yaml.safe_load(out.read_text())
    assert isinstance(data, dict)

    # 3. Behavioural invariant — no slot name carries the BOM prefix.
    slot_names = list((data.get("slots") or {}).keys())
    assert slot_names, f"expected slots, got: {data!r}"
    for name in slot_names:
        assert not name.startswith("\ufeff"), f"BOM must be stripped from slot names; got {name!r}"
    assert "col1" in slot_names, f"expected 'col1' in stripped slots: {slot_names!r}"


def test_suggest_empty_sssom_master(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """LinkML master with zero classes/slots → suggest exits 1 ("No embeddable nodes").

    ``rosetta suggest`` embeds internally. An empty master schema (no classes or
    slots) fails during embedding with ``Error: No embeddable nodes found in schema.``
    The test pins exit 1 + the "no embeddable" stderr marker, and confirms no
    output file is written.
    """
    import numpy as np
    import sentence_transformers

    class _FakeLaBSE:
        def encode(self, texts: list[str]) -> np.ndarray:
            rows: list[list[float]] = []
            for i in range(len(texts)):
                v = np.zeros(4, dtype=np.float32)
                v[i % 4] = 1.0
                rows.append(v.tolist())
            return np.array(rows, dtype=np.float32)

    monkeypatch.setattr(sentence_transformers, "SentenceTransformer", lambda _name: _FakeLaBSE())

    # Minimal source schema with one slot so the src side is valid.
    src_yaml = tmp_path / "src.linkml.yaml"
    src_yaml.write_text(
        "id: https://w3id.org/rosetta/adversarial/src\n"
        "name: src\n"
        "default_prefix: src\n"
        "prefixes:\n"
        "  src: https://w3id.org/rosetta/adversarial/src/\n"
        "  linkml: https://w3id.org/linkml/\n"
        "classes:\n"
        "  Thing:\n"
        "    slots:\n"
        "      - field_a\n"
        "slots:\n"
        "  field_a:\n"
        "    range: string\n",
        encoding="utf-8",
    )

    # Master schema with no `classes:` or `slots:` block (valid LinkML, but empty).
    master_yaml = tmp_path / "master.linkml.yaml"
    master_yaml.write_text(
        "id: https://w3id.org/rosetta/adversarial/empty_master\n"
        "name: empty_master\n"
        "default_prefix: em\n"
        "prefixes:\n"
        "  em: https://w3id.org/rosetta/adversarial/empty_master/\n"
        "  linkml: https://w3id.org/linkml/\n",
        encoding="utf-8",
    )

    dummy_log = tmp_path / "audit-log.sssom.tsv"
    dummy_log.write_text("")
    sssom_out = tmp_path / "out.sssom.tsv"

    result = CliRunner(mix_stderr=False).invoke(
        suggest_cli,
        [
            str(src_yaml),
            str(master_yaml),
            "--output",
            str(sssom_out),
            "--audit-log",
            str(dummy_log),
        ],
    )

    # 1. Exit code
    assert result.exit_code == 1, (
        f"expected exit 1 for empty master, got {result.exit_code}; "
        f"stderr={result.stderr!r} stdout={result.output!r}"
    )

    # 2. Stderr substring — empty-schema error from suggest's embed step.
    # Observed: "No nodes found in master schema: ..." (suggest embeds internally).
    combined = (result.stderr or "") + (result.output or "")
    assert "no nodes found" in combined.lower() or "embeddable" in combined.lower(), (
        f"expected empty-schema error marker in output; got stderr={result.stderr!r}"
    )

    # 3. Behavioral invariant: no partial output written
    assert not sssom_out.exists() or sssom_out.read_text() == "", (
        f"partial output written: {sssom_out.read_text()[:200]!r}"
    )
