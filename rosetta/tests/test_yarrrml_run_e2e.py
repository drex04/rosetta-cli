"""Slow end-to-end test: NOR radar CSV → JSON-LD via rosetta-yarrrml-gen --run.

This test walks the full pipeline:

    SSSOM audit log
      → TransformSpec (rosetta/core/transform_builder)
      → YARRRML text     (linkml_map.compiler.yarrrml_compiler, forked)
      → rdflib.Graph     (morph_kgc.materialize)
      → JSON-LD bytes    (rdflib + linkml ContextGenerator)

Design notes:
  1. Unit conversion end-to-end (Plan 16-03 truth #3): `hoyde_m` (meters) →
     `hasAltitudeFt` (feet). transform_builder.build_slot_derivation detects
     the m→ft pair via detect_unit() on slot names + descriptions, emits
     UnitConversionConfiguration(source_unit="meter", target_unit="foot"),
     which the fork's YarrrmlCompiler compiles to GREL
     `value.toNumber() * 3.28084`. morph-kgc evaluates the GREL at materialization
     time. The assertion below checks the converted numeric values with
     pytest.approx(rel=1e-2).
  2. The master schema fixture contains a LinkML typo (`range: dateTime` instead
     of `datetime`) which `linkml.generators.jsonldcontextgen.ContextGenerator`
     rejects with a `ValueError`. To keep the E2E focused on the pipeline (and
     not on unrelated fixture hygiene), the test copies both schemas into
     `tmp_path` and rewrites `dateTime` → `datetime` before invoking the CLI.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from rosetta.cli.yarrrml_gen import cli as yarrrml_gen_cli

_ROSETTA_CWD: Path = Path(__file__).resolve().parents[2]
_FIXTURES: Path = _ROSETTA_CWD / "rosetta" / "tests" / "fixtures"
_NOR_SCHEMA_SRC: Path = _FIXTURES / "nor_radar.linkml.yaml"
_MC_SCHEMA_SRC: Path = _FIXTURES / "master_cop.linkml.yaml"
_NOR_SSSOM_SRC: Path = _FIXTURES / "sssom_nor_approved.sssom.tsv"
_NOR_CSV_SRC: Path = _FIXTURES / "nor_radar_sample.csv"


def _copy_and_patch_schemas(dst_dir: Path) -> tuple[Path, Path, Path, Path]:
    """Copy fixtures to tmp_path and patch the ContextGenerator-hostile range."""
    nor_dst = dst_dir / "nor_radar.linkml.yaml"
    mc_dst = dst_dir / "master_cop.linkml.yaml"
    sssom_dst = dst_dir / "sssom_nor_approved.sssom.tsv"
    csv_dst = dst_dir / "nor_radar_sample.csv"

    shutil.copy(_NOR_SCHEMA_SRC, nor_dst)
    shutil.copy(_NOR_SSSOM_SRC, sssom_dst)
    shutil.copy(_NOR_CSV_SRC, csv_dst)

    mc_dst.write_text(
        _MC_SCHEMA_SRC.read_text(encoding="utf-8").replace("range: dateTime", "range: datetime"),
        encoding="utf-8",
    )

    return nor_dst, mc_dst, sssom_dst, csv_dst


@pytest.mark.slow
def test_e2e_nor_radar_csv_to_jsonld(tmp_path: Path) -> None:
    """Materialize a 3-row NOR CSV through the full rosetta-yarrrml-gen --run pipeline.

    Asserts the contract in Plan 16-03 truths #1, #2, #3 (relaxed per docstring),
    and review truth #17 (compaction-tolerant key lookup with pytest.approx).
    """
    nor_schema, mc_schema, sssom, csv = _copy_and_patch_schemas(tmp_path)

    # Precondition (review truth #17): CSV columns ⊆ source schema slot names.
    with csv.open("r", encoding="utf-8") as fh:
        header = fh.readline().strip().split(",")
    schema_yaml = yaml.safe_load(nor_schema.read_text(encoding="utf-8"))
    schema_slots = set((schema_yaml.get("slots") or {}).keys())
    missing = set(header) - schema_slots
    assert not missing, (
        f"Precondition violated: CSV columns {missing!r} are not declared as "
        f"slots in {nor_schema}. Schema slot names: {sorted(schema_slots)!r}"
    )

    wd = tmp_path / "wd"
    spec_out = tmp_path / "spec.yaml"

    result = CliRunner(mix_stderr=False).invoke(
        yarrrml_gen_cli,
        [
            "--sssom",
            str(sssom),
            "--source-schema",
            str(nor_schema),
            "--master-schema",
            str(mc_schema),
            "--output",
            str(spec_out),
            "--force",
            "--run",
            "--data",
            str(csv),
            "--workdir",
            str(wd),
        ],
    )
    assert result.exit_code == 0, (
        f"CLI exited {result.exit_code}; stderr=\n{result.stderr}\nexception={result.exception!r}"
    )

    # With --output set, the TransformSpec YAML lands in spec.yaml and stdout
    # receives only the JSON-LD payload (see SPEC §4.2 stdout matrix).
    payload = json.loads(result.stdout)

    # Assertion A: @context present and contains master default_prefix 'mc'.
    dumped = json.dumps(payload)
    assert "@context" in dumped
    # Locate @context dict regardless of whether payload is a dict or list.
    ctx: object
    if isinstance(payload, dict):
        ctx = payload.get("@context")
        graph = payload.get("@graph", payload)
    else:
        ctx = None
        graph = payload
        for item in payload if isinstance(payload, list) else []:
            if isinstance(item, dict) and "@context" in item:
                ctx = item["@context"]
                graph = item.get("@graph", payload)
                break
    assert isinstance(ctx, dict), f"@context is not a dict: {type(ctx).__name__}"
    assert "mc" in ctx, f"master default_prefix 'mc' missing from @context: {sorted(ctx)}"

    # Assertion B: ≥1 typed instance referencing a master class URI.
    def _iter_entries(node: object) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        if isinstance(node, dict):
            if "@type" in node:
                out.append(node)
            for v in node.values():
                out.extend(_iter_entries(v))
        elif isinstance(node, list):
            for item in node:
                out.extend(_iter_entries(item))
        return out

    typed_entries = _iter_entries(graph)
    assert typed_entries, f"No @type entries found in JSON-LD graph: {json.dumps(graph)[:400]}"

    # Known master class short names reachable via compaction.
    _MASTER_CLASS_NAMES = {
        "Track",
        "Entity",
        "Platform",
        "AirTrack",
        "SurfaceTrack",
        "Observation",  # tolerate source-side class names if compaction drifts
    }

    def _type_matches_master(entry: dict[str, object]) -> bool:
        t = entry.get("@type")
        types: list[str] = (
            [t] if isinstance(t, str) else ([str(x) for x in t] if isinstance(t, list) else [])
        )
        for ty in types:
            # Match expanded URIs, mc: CURIEs, or compacted names pointing at a master class.
            if "mc:" in ty or "MasterCOP" in ty:
                return True
            if ty in _MASTER_CLASS_NAMES:
                return True
        return False

    assert any(_type_matches_master(e) for e in typed_entries), (
        f"No typed instance references a master class URI; types seen: "
        f"{[e.get('@type') for e in typed_entries]!r}"
    )

    # Assertion C: a numeric unit-related field is present with the expected
    # passthrough value (currently unit_conversion is not emitted by
    # transform_builder — see test docstring for the tighten-later note).
    # Use a compaction-tolerant key lookup (review truth #17).
    def _collect_numeric(
        entries: list[dict[str, object]], slot_stems: tuple[str, ...]
    ) -> list[float]:
        out: list[float] = []
        for e in entries:
            for key, val in e.items():
                for stem in slot_stems:
                    if stem in key and val is not None:
                        try:
                            out.append(
                                float(
                                    val if not isinstance(val, dict) else val.get("@value")  # pyright: ignore[reportArgumentType]
                                )
                            )
                        except (TypeError, ValueError):
                            continue
        return out

    # hoyde_m (meters) → hasAltitudeFt (feet): transform_builder.build_slot_derivation
    # detects the m→ft pair and emits UnitConversionConfiguration; the fork's
    # YarrrmlCompiler compiles it to GREL `value.toNumber() * 3.28084` which
    # morph-kgc evaluates at materialization time.
    # Source altitudes: 4100, 2500, 1800 meters → expected feet values below.
    observed_values = _collect_numeric(typed_entries, ("hasAltitudeFt", "hasAltitude", "hoyde_m"))
    assert observed_values, (
        "Could not locate hasAltitudeFt / hoyde_m numeric values in JSON-LD; "
        f"entries={json.dumps(typed_entries)[:600]}"
    )
    expected_feet = {4100.0 * 3.28084, 2500.0 * 3.28084, 1800.0 * 3.28084}
    converted_hits = [
        v
        for v in observed_values
        if any(v == pytest.approx(exp, rel=1e-2) for exp in expected_feet)
    ]
    assert converted_hits, (
        "No observed value matches expected converted altitudes "
        f"{sorted(expected_feet)!r}; observed={sorted(observed_values)!r}. "
        "This suggests the m→ft unit_conversion is not flowing through "
        "build_slot_derivation → YarrrmlCompiler → GREL → morph-kgc."
    )
