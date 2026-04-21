"""Adversarial fixture-hygiene test for rosetta compile/run (Phase 18-03, Task 7).

Phase 16-03's e2e test (``test_yarrrml_run_e2e.py``) works around a LinkML
fixture typo — ``range: dateTime`` (capital T, invalid) instead of ``range:
datetime`` — by rewriting the schema text before invoking the CLI. This
adversarial test exercises the opposite contract: when the typo is present,
``rosetta run`` surfaces a clear diagnostic (via the wrapped
``RuntimeError`` / ``ValueError`` from
``linkml.generators.jsonldcontextgen.ContextGenerator``) rather than crashing
opaquely, and it does not leave partial JSON-LD output behind.

The test builds minimal inline LinkML schemas plus a 13-column SSSOM approval
log so the pipeline reaches the ContextGenerator stage where the typo bites.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import pytest
import yaml
from click.testing import CliRunner

from rosetta.cli.compile import cli as compile_cli
from rosetta.cli.run import cli as run_cli

pytestmark = [pytest.mark.integration, pytest.mark.slow]


_SSSOM_HEADER = """\
# sssom_version: https://w3id.org/sssom/spec/0.15
# mapping_set_id: http://rosetta.interop/audit-log/adv-datetime-typo
# curie_map:
#   src: http://rosetta.interop/src/
#   mc: http://rosetta.interop/mc/
#   skos: http://www.w3.org/2004/02/skos/core#
#   owl: http://www.w3.org/2002/07/owl#
#   semapv: https://w3id.org/semapv/vocab/
"""

_SSSOM_COLS = [
    "subject_id",
    "predicate_id",
    "object_id",
    "mapping_justification",
    "confidence",
    "subject_label",
    "object_label",
    "mapping_date",
    "record_id",
    "subject_type",
    "object_type",
    "mapping_group_id",
    "composition_expr",
]


def _write_sssom(path: Path, rows: list[dict[str, str]]) -> None:
    """Write a 13-column SSSOM TSV with the standard audit-log header."""
    with path.open("w", encoding="utf-8") as f:
        f.write(_SSSOM_HEADER)
        writer = csv.DictWriter(f, fieldnames=_SSSOM_COLS, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in _SSSOM_COLS})


def _source_schema_body() -> dict[str, Any]:
    """Tiny LinkML source schema with a CSV source-format annotation.

    Slots match the columns of the ``nor_radar_sample.csv`` fixture so
    morph-kgc can resolve references during materialization.
    """
    return {
        "name": "src",
        "id": "http://rosetta.interop/src",
        "annotations": {"rosetta_source_format": "csv"},
        "imports": ["linkml:types"],
        "prefixes": {
            "linkml": {
                "prefix_prefix": "linkml",
                "prefix_reference": "https://w3id.org/linkml/",
            },
            "src": {
                "prefix_prefix": "src",
                "prefix_reference": "http://rosetta.interop/src/",
            },
        },
        "default_prefix": "src",
        "classes": {
            "Observation": {
                "name": "Observation",
                "slots": ["sporings_id", "tidsstempel"],
            },
        },
        "slots": {
            "sporings_id": {
                "name": "sporings_id",
                "annotations": {"rosetta_csv_column": "sporings_id"},
                "identifier": True,
                "range": "string",
            },
            "tidsstempel": {
                "name": "tidsstempel",
                "annotations": {"rosetta_csv_column": "tidsstempel"},
                "range": "string",
            },
        },
    }


def _master_schema_body_with_datetime_typo() -> dict[str, Any]:
    """Tiny LinkML master schema with the Phase 16-03 dateTime typo.

    ``range: dateTime`` (capital T) is invalid — LinkML's built-in type is
    ``datetime`` (lowercase). ``ContextGenerator`` rejects this with a
    ValueError which the yarrrml-gen CLI converts to exit 1.
    """
    return {
        "name": "mc",
        "id": "http://rosetta.interop/mc",
        "imports": ["linkml:types"],
        "prefixes": {
            "linkml": {
                "prefix_prefix": "linkml",
                "prefix_reference": "https://w3id.org/linkml/",
            },
            "mc": {
                "prefix_prefix": "mc",
                "prefix_reference": "http://rosetta.interop/mc/",
            },
        },
        "default_prefix": "mc",
        "default_range": "string",
        "classes": {
            "Track": {
                "name": "Track",
                "slots": ["trackId", "observedAt"],
            },
        },
        "slots": {
            "trackId": {
                "name": "trackId",
                "slot_uri": "mc:trackId",
                "identifier": True,
                "range": "string",
            },
            "observedAt": {
                "name": "observedAt",
                "slot_uri": "mc:observedAt",
                # Intentional Phase 16-03 typo — should be "datetime" lowercase.
                "range": "dateTime",
            },
        },
    }


def test_compile_run_with_datetime_typo(tmp_path: Path, nor_csv_sample_path: Path) -> None:
    """Master schema with ``range: dateTime`` typo → exit 1 with a clear diagnostic.

    Pins the observable error surface when the Phase 16-03 fixture-hygiene typo
    is present: ``ContextGenerator`` rejects ``dateTime`` (capital T) with a
    ValueError, surfaced through the rosetta run CLI's generic-exception block
    as ``Error: {exc}`` on stderr. The substring check tolerates either
    ``dateTime``, ``ContextGenerator``, or ``@context`` — whichever the current
    error path emits — since LinkML's exact wording may drift.
    """
    # Inline master schema with the typo
    master_path = tmp_path / "master.linkml.yaml"
    master_path.write_text(
        yaml.safe_dump(_master_schema_body_with_datetime_typo(), sort_keys=False),
        encoding="utf-8",
    )

    # Inline source schema
    src_path = tmp_path / "src.linkml.yaml"
    src_path.write_text(yaml.safe_dump(_source_schema_body(), sort_keys=False), encoding="utf-8")

    # Inline SSSOM mapping: source slots → master slots, HumanCuration (approved).
    sssom_path = tmp_path / "approved.sssom.tsv"
    _write_sssom(
        sssom_path,
        [
            {
                "subject_id": "src:Observation",
                "predicate_id": "skos:exactMatch",
                "object_id": "mc:Track",
                "mapping_justification": "semapv:HumanCuration",
                "confidence": "0.9",
                "object_label": "Track",
                "mapping_date": "2026-04-18",
                "record_id": "r001",
            },
            {
                "subject_id": "src:sporings_id",
                "predicate_id": "skos:exactMatch",
                "object_id": "mc:trackId",
                "mapping_justification": "semapv:HumanCuration",
                "confidence": "0.9",
                "object_label": "trackId",
                "mapping_date": "2026-04-18",
                "record_id": "r002",
            },
            {
                "subject_id": "src:tidsstempel",
                "predicate_id": "skos:exactMatch",
                "object_id": "mc:observedAt",
                "mapping_justification": "semapv:HumanCuration",
                "confidence": "0.9",
                "object_label": "observedAt",
                "mapping_date": "2026-04-18",
                "record_id": "r003",
            },
        ],
    )

    spec_out = tmp_path / "transform_spec.yaml"
    jsonld_out = tmp_path / "out.jsonld"
    wd = tmp_path / "morph_wd"
    wd.mkdir()

    yarrrml_out = tmp_path / "mapping.yarrrml.yaml"
    compile_result = CliRunner(mix_stderr=False).invoke(
        compile_cli,
        [
            str(sssom_path),
            "--source-schema",
            str(src_path),
            "--master-schema",
            str(master_path),
            "-o",
            str(yarrrml_out),
            "--spec-output",
            str(spec_out),
        ],
    )
    # compile may succeed even with the typo (typo affects ContextGenerator at run time)
    # Proceed to run regardless to exercise the dateTime error surface.
    if compile_result.exit_code != 0:
        # If compile fails early (e.g., schema load error), check exit 1.
        assert compile_result.exit_code == 1, (
            f"expected exit 1 from compile; got {compile_result.exit_code}"
        )
        result = compile_result
    else:
        result = CliRunner(mix_stderr=False).invoke(
            run_cli,
            [
                str(yarrrml_out),
                str(nor_csv_sample_path),
                "--master-schema",
                str(master_path),
                "-o",
                str(jsonld_out),
                "--workdir",
                str(wd),
            ],
        )

    # 1. Exit code
    assert result.exit_code == 1, (
        f"expected exit 1 due to dateTime typo; got {result.exit_code}\n"
        f"stderr={result.stderr}\nexception={result.exception!r}"
    )
    # 2. Stderr substring: accept any of the three stable surfaces —
    #    the LinkML typename itself ("dateTime"), the generator class
    #    ("ContextGenerator"), or the JSON-LD marker ("@context").
    stderr_lower = result.stderr.lower()
    assert (
        "datetime" in stderr_lower
        or "contextgenerator" in stderr_lower
        or "@context" in stderr_lower
    ), (
        "expected one of 'dateTime' / 'ContextGenerator' / '@context' in stderr; "
        f"got: {result.stderr!r}"
    )
    # 3. Behavioral invariant: no JSON-LD output written (ContextGenerator
    #    fails before the write step in cli/run.py).
    assert not jsonld_out.exists() or jsonld_out.stat().st_size == 0, (
        "JSON-LD output must not be written when ContextGenerator rejects the schema"
    )
