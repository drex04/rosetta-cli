"""Generate test fixtures using real rosetta tooling.

Prevents format-mismatch bugs (e.g., CURIE separator '/' vs ':') by building
fixtures through the same models and serializers the pipeline uses at runtime.

Usage:
    uv run python rosetta/tests/fixtures/generate_fixtures.py [FLAGS]

Flags:
    --with-ingest  Regenerate LinkML schemas from source formats via rosetta-ingest.
    --with-embed   Regenerate embed JSONs (requires model download).
    --all          Regenerate everything.
"""

from __future__ import annotations

import csv
import sys
from datetime import UTC, datetime
from pathlib import Path

from rosetta.core.accredit import AUDIT_LOG_COLUMNS, parse_sssom_tsv
from rosetta.core.models import SSSOMRow

_NATIONS = Path(__file__).parent / "nations"
_NOR_SCHEMA = _NATIONS / "nor_radar.linkml.yaml"
_MC_SCHEMA = _NATIONS / "master_cop.linkml.yaml"

_SSSOM_HEADER = """\
# sssom_version: https://w3id.org/sssom/spec/0.15
# mapping_set_id: http://rosetta.interop/audit-log/test-nor
# curie_map:
#   nor_radar: http://rosetta.interop/nor_radar/
#   mc: http://rosetta.interop/master-cop/
#   deu_radar: http://rosetta.interop/deu_radar/
#   ex: http://example.org/
#   skos: http://www.w3.org/2004/02/skos/core#
#   owl: http://www.w3.org/2002/07/owl#
#   semapv: https://w3id.org/semapv/vocab/
"""

_DATE = datetime(2026, 4, 16, tzinfo=UTC)

_APPROVED: list[dict[str, object]] = [
    {
        "subject_id": "nor_radar:Observation",
        "object_id": "mc:Track",
        "object_label": "Track",
        "record_id": "r001",
    },
    {
        "subject_id": "nor_radar:breddegrad",
        "object_id": "mc:hasLatitude",
        "object_label": "hasLatitude",
        "record_id": "r002",
    },
    {
        "subject_id": "nor_radar:lengdegrad",
        "object_id": "mc:hasLongitude",
        "object_label": "hasLongitude",
        "record_id": "r003",
    },
    {
        "subject_id": "nor_radar:hoyde_m",
        "object_id": "mc:hasAltitudeFt",
        "object_label": "hasAltitudeFt",
        "record_id": "r004",
    },
    {
        "subject_id": "nor_radar:hastighet_kmh",
        "object_id": "mc:hasSpeed",
        "object_label": "hasSpeed",
        "record_id": "r005",
    },
    {
        "subject_id": "nor_radar:breddegrad",
        "object_id": "mc:hasLatitude",
        "object_label": "hasLatitude",
        "record_id": "r006a",
        "subject_type": "composed entity expression",
        "object_type": "composed entity expression",
        "mapping_group_id": "grp-geo-1",
        "composition_expr": "[{breddegrad},{lengdegrad}]",
    },
    {
        "subject_id": "nor_radar:lengdegrad",
        "object_id": "mc:hasLatitude",
        "object_label": "hasLatitude",
        "record_id": "r006b",
        "subject_type": "composed entity expression",
        "object_type": "composed entity expression",
        "mapping_group_id": "grp-geo-1",
        "composition_expr": "[{breddegrad},{lengdegrad}]",
    },
    {
        "subject_id": "nor_radar:avstand_km",
        "predicate_id": "skos:closeMatch",
        "object_id": "mc:hasRange",
        "object_label": "hasRange",
        "record_id": "r007",
    },
    {
        "subject_id": "nor_radar:peiling_grader",
        "predicate_id": "skos:narrowMatch",
        "object_id": "mc:hasBearing",
        "object_label": "hasBearing",
        "record_id": "r008",
    },
    {
        "subject_id": "nor_radar:signalstyrke_dbm",
        "predicate_id": "owl:differentFrom",
        "object_id": "mc:hasConfidence",
        "object_label": "hasConfidence",
        "record_id": "r009",
    },
    {
        "subject_id": "deu_radar:foo",
        "object_id": "mc:bar",
        "object_label": "bar",
        "record_id": "r010",
    },
]


def _build_row(overrides: dict[str, object]) -> SSSOMRow:
    defaults: dict[str, object] = {
        "predicate_id": "skos:exactMatch",
        "mapping_justification": "semapv:HumanCuration",
        "confidence": 0.9,
        "subject_label": "",
        "object_label": "",
        "mapping_date": _DATE,
        "subject_type": None,
        "object_type": None,
        "mapping_group_id": None,
        "composition_expr": None,
    }
    defaults.update(overrides)
    return SSSOMRow(**defaults)  # pyright: ignore[reportArgumentType]


def _cell(row: SSSOMRow, col: str) -> str:
    if col == "mapping_date":
        return row.mapping_date.strftime("%Y-%m-%d") if row.mapping_date else ""
    if col == "confidence":
        return str(row.confidence)
    val = getattr(row, col, None)
    return "" if val is None else str(val)


def generate_approved_sssom() -> Path:
    """Build the approved SSSOM fixture using real SSSOMRow models."""
    rows = [_build_row(m) for m in _APPROVED]
    out = _NATIONS / "sssom_nor_approved.sssom.tsv"
    with out.open("w", encoding="utf-8", newline="") as fh:
        fh.write(_SSSOM_HEADER)
        writer = csv.writer(fh, delimiter="\t", lineterminator="\n")
        writer.writerow(AUDIT_LOG_COLUMNS)
        for row in rows:
            writer.writerow([_cell(row, col) for col in AUDIT_LOG_COLUMNS])
    return out


def validate(path: Path) -> None:
    """Validate the generated SSSOM is parseable and uses CURIE format."""
    rows = parse_sssom_tsv(path)
    if not rows:
        raise ValueError(f"No rows parsed from {path}")
    for row in rows:
        if ":" not in row.subject_id:
            raise ValueError(f"subject_id {row.subject_id!r} missing CURIE ':' separator")


def generate_linkml_fixtures() -> None:
    """Run rosetta-ingest to generate LinkML schemas from source formats."""
    from click.testing import CliRunner

    from rosetta.cli.ingest import cli as ingest_cli

    runner = CliRunner()

    result = runner.invoke(
        ingest_cli,
        [
            str(_NATIONS / "nor_radar.csv"),
            "--schema-format",
            "csv",
            "--output",
            str(_NOR_SCHEMA),
        ],
    )
    if result.exit_code != 0:
        raise RuntimeError(f"ingest nor_radar.csv failed: {result.output}")
    print(f"  {_NOR_SCHEMA.name}")

    result = runner.invoke(
        ingest_cli,
        [
            str(_NATIONS / "master_cop_ontology.ttl"),
            "--schema-format",
            "rdfs",
            "--output",
            str(_MC_SCHEMA),
        ],
    )
    if result.exit_code != 0:
        raise RuntimeError(f"ingest master_cop_ontology.ttl failed: {result.output}")
    print(f"  {_MC_SCHEMA.name}")


def generate_shacl_fixtures() -> None:
    """Run rosetta-shacl-gen on master schema to produce SHACL shapes fixture."""
    from click.testing import CliRunner

    from rosetta.cli.shacl_gen import cli as shacl_gen_cli

    runner = CliRunner()
    out = _NATIONS / "master_cop.shapes.ttl"
    result = runner.invoke(shacl_gen_cli, ["--input", str(_MC_SCHEMA), "--output", str(out)])
    if result.exit_code != 0:
        raise RuntimeError(f"shacl-gen failed: {result.output}")
    print(f"  {out.name}")


def generate_embed_fixtures() -> None:
    """Run rosetta-embed on both schemas (requires sentence-transformers)."""
    from click.testing import CliRunner

    from rosetta.cli.embed import cli as embed_cli

    runner = CliRunner()
    for schema, name in (
        (_NOR_SCHEMA, "nor_radar.embed.json"),
        (_MC_SCHEMA, "master_cop.embed.json"),
    ):
        out = _NATIONS / name
        result = runner.invoke(embed_cli, [str(schema), "--output", str(out)])
        if result.exit_code != 0:
            raise RuntimeError(f"embed failed: {result.output}")
        print(f"  {out.name}")


def main() -> None:
    args = set(sys.argv[1:])
    run_all = "--all" in args

    if run_all or "--with-ingest" in args:
        print("Generating LinkML schemas via ingest...")
        generate_linkml_fixtures()

    print("Generating approved SSSOM fixture...")
    path = generate_approved_sssom()
    validate(path)
    print(f"  {path.name} ({len(parse_sssom_tsv(path))} rows, validated)")

    print("Generating SHACL shapes fixture...")
    generate_shacl_fixtures()

    if run_all or "--with-embed" in args:
        print("Generating embed fixtures...")
        generate_embed_fixtures()

    print("Done.")


if __name__ == "__main__":
    main()
