"""Integration tests: rosetta-yarrrml-gen TransformSpec → fork's YarrrmlCompiler round-trip.

Tests 1-2 are fast (in-process).
Tests 3-4 invoke the fork's CLI via subprocess and are marked @pytest.mark.slow.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import cast

import pytest
import yaml
from click.testing import CliRunner
from linkml_runtime.linkml_model import ClassDefinition, SchemaDefinition, SlotDefinition
from linkml_runtime.loaders import yaml_loader  # type: ignore[import-untyped]
from linkml_runtime.utils.schemaview import SchemaView

from rosetta.cli.yarrrml_gen import cli as yarrrml_gen_cli
from rosetta.core.accredit import parse_sssom_tsv
from rosetta.core.transform_builder import build_spec

pytestmark = [pytest.mark.integration]

# ---------------------------------------------------------------------------
# Shared paths
# ---------------------------------------------------------------------------
_ROSETTA_CWD = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Helper builders (mirrors test_yarrrml_gen.py pattern)
# ---------------------------------------------------------------------------


def _mkrow(**overrides: object) -> object:
    """Build a SSSOMRow with defaults; import lazily to avoid top-level coupling."""
    from rosetta.core.models import SSSOMRow

    defaults: dict[str, object] = {
        "subject_id": "nor_radar:x",
        "predicate_id": "skos:exactMatch",
        "object_id": "mc:X",
        "mapping_justification": "semapv:HumanCuration",
        "confidence": 0.9,
        "subject_label": "",
        "object_label": "",
        "mapping_date": None,
        "record_id": "r",
        "subject_type": None,
        "object_type": None,
        "mapping_group_id": None,
        "composition_expr": None,
    }
    defaults.update(overrides)
    return SSSOMRow(**defaults)  # pyright: ignore[reportArgumentType]


def _mkschema(
    prefix: str,
    classes: dict[str, list[str]],
    slots: dict[str, str],
    annotations: dict[str, dict[str, str]] | None = None,
) -> SchemaDefinition:
    """Build a minimal SchemaDefinition.

    annotations maps slot_name → {key: value} for slot annotations.
    """
    slot_defs: dict[str, SlotDefinition] = {}
    for sname, srange in slots.items():
        sd = SlotDefinition(name=sname, slot_uri=f"{prefix}:{sname}", range=srange)
        if annotations and sname in annotations:
            from linkml_runtime.linkml_model import Annotation

            for ann_key, ann_val in annotations[sname].items():
                sd.annotations[ann_key] = Annotation(tag=ann_key, value=ann_val)  # pyright: ignore[reportCallIssue,reportArgumentType,reportOptionalSubscript]
        slot_defs[sname] = sd
    return SchemaDefinition(
        id=f"https://ex/{prefix}",
        name=prefix,
        default_prefix=prefix,
        prefixes={prefix: {"prefix_prefix": prefix, "prefix_reference": f"https://ex/{prefix}/"}},
        classes={
            cname: ClassDefinition(name=cname, class_uri=f"{prefix}:{cname}", slots=cslots)
            for cname, cslots in classes.items()
        },
        slots=slot_defs,  # pyright: ignore[reportArgumentType]
    )  # pyright: ignore[reportCallIssue]


def _build_nor_spec(nor_schema: Path, mc_schema: Path, nor_sssom: Path) -> object:
    """Build a TransformationSpecification from the nor_radar fixtures."""
    rows = parse_sssom_tsv(nor_sssom)
    src = cast(
        SchemaDefinition,
        yaml_loader.load(str(nor_schema), target_class=SchemaDefinition),  # pyright: ignore[reportUnknownMemberType]
    )
    mst = cast(
        SchemaDefinition,
        yaml_loader.load(str(mc_schema), target_class=SchemaDefinition),  # pyright: ignore[reportUnknownMemberType]
    )
    spec, _ = build_spec(
        rows,
        src,
        mst,
        source_schema_path=str(nor_schema.resolve()),
        target_schema_path=str(mc_schema.resolve()),
        force=True,
    )
    spec.comments = ["rosetta:source_format=csv"]
    return spec


# ---------------------------------------------------------------------------
# Test 1 — compile produces valid YARRRML YAML with required top-level keys
# ---------------------------------------------------------------------------


def test_yarrrml_compile_produces_valid_yaml(
    tmp_path: Path,
    nor_linkml_path: Path,
    master_schema_path: Path,
    sssom_nor_path: Path,
) -> None:
    """Round-trip nor_radar spec through YarrrmlCompiler; output must be valid YAML."""
    from linkml_map.compiler.yarrrml_compiler import YarrrmlCompiler

    spec = _build_nor_spec(nor_linkml_path, master_schema_path, sssom_nor_path)

    compiler = YarrrmlCompiler(
        source_schemaview=SchemaView(str(nor_linkml_path.resolve())),
        target_schemaview=SchemaView(str(master_schema_path.resolve())),
    )
    rendered = compiler.compile(spec).serialization  # pyright: ignore[reportArgumentType]  # noqa: FURB184

    parsed = yaml.safe_load(rendered)
    assert isinstance(parsed, dict), "YARRRML output must be a YAML dict"
    assert "prefixes" in parsed, "YARRRML must have a 'prefixes' key"
    assert "mappings" in parsed, "YARRRML must have a 'mappings' key"
    # mappings is a dict-of-dicts in this YARRRML dialect
    mappings = parsed["mappings"]
    assert isinstance(mappings, (dict, list)) and len(mappings) >= 1, (
        "At least one mapping block must be emitted"
    )


# ---------------------------------------------------------------------------
# Test 2 — CSV column references match rosetta_csv_column annotations
# ---------------------------------------------------------------------------


def test_yarrrml_compile_csv_references_match_annotations(
    tmp_path: Path,
    nor_linkml_path: Path,
    master_schema_path: Path,
    sssom_nor_path: Path,
) -> None:
    """Slots with rosetta_csv_column annotations must appear as $(col) in YARRRML po."""
    from linkml_map.compiler.yarrrml_compiler import YarrrmlCompiler

    spec = _build_nor_spec(nor_linkml_path, master_schema_path, sssom_nor_path)

    compiler = YarrrmlCompiler(
        source_schemaview=SchemaView(str(nor_linkml_path.resolve())),
        target_schemaview=SchemaView(str(master_schema_path.resolve())),
    )
    raw_yaml = compiler.compile(spec).serialization  # pyright: ignore[reportArgumentType]  # noqa: FURB184
    # breddegrad and lengdegrad slots have rosetta_csv_column annotations — the compiler
    # must emit $(breddegrad) / $(lengdegrad), not the bare slot names.
    assert "$(breddegrad)" in raw_yaml, (
        "Expected $(breddegrad) reference from rosetta_csv_column annotation"
    )
    assert "$(lengdegrad)" in raw_yaml, (
        "Expected $(lengdegrad) reference from rosetta_csv_column annotation"
    )
    # Fork-drift guard (Plan 16-03): the compiler must emit the $(DATA_FILE)
    # placeholder verbatim so rosetta/core/rml_runner.py's _substitute_data_path
    # can swap in the concrete data path at --run time.
    assert "$(DATA_FILE)" in raw_yaml, (
        "Expected $(DATA_FILE) placeholder in YARRRML sources block — "
        "rml_runner._substitute_data_path relies on it."
    )

    # YARRRML output uses mappings as a dict-of-dicts with 'po' lists.
    # Collect all object values (second element of [predicate, object] pairs) across all mappings.
    mappings_block = yaml.safe_load(raw_yaml).get("mappings", {})  # noqa: FURB184
    all_po_values: list[str] = []
    # mappings_block is a dict: {mapping_name: {sources, s, po, ...}}
    for _name, mapping in mappings_block.items() if isinstance(mappings_block, dict) else []:
        for po in mapping.get("po", []) or []:
            if isinstance(po, list) and len(po) >= 2:
                all_po_values.append(str(po[1]))
            elif isinstance(po, dict):
                for o_entry in po.get("o", []) or []:
                    if isinstance(o_entry, str):
                        all_po_values.append(o_entry)
    assert any("breddegrad" in v for v in all_po_values), (
        f"No po entry references breddegrad; found: {all_po_values}"
    )


# ---------------------------------------------------------------------------
# Test 3 — CLI end-to-end: rosetta-yarrrml-gen → linkml-map compile
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_yarrrml_compile_cli_end_to_end(
    tmp_path: Path,
    nor_linkml_path: Path,
    master_schema_path: Path,
    sssom_nor_path: Path,
) -> None:
    """rosetta-yarrrml-gen writes spec.yaml; linkml-map compile --target yarrrml reads it."""
    spec_out = tmp_path / "spec.yaml"
    yarrrml_out = tmp_path / "output.yarrrml.yaml"

    # Step 1: produce TransformSpec via rosetta-yarrrml-gen CLI
    runner = CliRunner()
    result = runner.invoke(  # noqa: FURB184
        yarrrml_gen_cli,
        [
            "--sssom",
            str(sssom_nor_path),
            "--source-schema",
            str(nor_linkml_path),
            "--master-schema",
            str(master_schema_path),
            "--output",
            str(spec_out),
            "--force",
        ],
    )
    assert result.exit_code == 0, f"rosetta-yarrrml-gen failed:\n{result.output}" + (
        f"\n{result.exception}" if result.exception else ""
    )
    assert spec_out.exists(), "spec.yaml not written"

    # Step 2: compile via fork's linkml-map CLI
    rc = subprocess.run(
        [
            "uv",
            "run",
            "linkml-map",
            "compile",
            "-T",
            str(spec_out),
            "-s",
            str(nor_linkml_path.resolve()),
            "--target",
            "yarrrml",
            "--target-schema",
            str(master_schema_path.resolve()),
            "-o",
            str(yarrrml_out),
        ],
        cwd=str(_ROSETTA_CWD),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert rc.returncode == 0, (
        f"linkml-map compile failed (exit {rc.returncode}):\n"
        f"stdout: {rc.stdout}\nstderr: {rc.stderr}"
    )
    assert yarrrml_out.exists(), "YARRRML output file not created"

    parsed = yaml.safe_load(yarrrml_out.read_text())
    assert isinstance(parsed, dict), "YARRRML output is not a dict"
    assert "mappings" in parsed, "YARRRML output missing 'mappings' key"


# ---------------------------------------------------------------------------
# Test 4 — self-describing invocation: --target-schema inferred from spec
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_yarrrml_compile_cli_self_describing(
    tmp_path: Path,
    nor_linkml_path: Path,
    master_schema_path: Path,
    sssom_nor_path: Path,
) -> None:
    """Omitting --target-schema forces compiler to use spec.target_schema path."""
    spec_out = tmp_path / "spec.yaml"
    yarrrml_out = tmp_path / "output_self.yarrrml.yaml"

    # Produce spec with embedded source/target schema paths
    runner = CliRunner()
    result = runner.invoke(  # noqa: FURB184
        yarrrml_gen_cli,
        [
            "--sssom",
            str(sssom_nor_path),
            "--source-schema",
            str(nor_linkml_path),
            "--master-schema",
            str(master_schema_path),
            "--output",
            str(spec_out),
            "--force",
        ],
    )
    assert result.exit_code == 0, f"rosetta-yarrrml-gen failed:\n{result.output}" + (
        f"\n{result.exception}" if result.exception else ""
    )

    # Verify spec carries embedded paths
    spec_data = yaml.safe_load(spec_out.read_text())
    assert spec_data.get("source_schema"), "spec.source_schema must be populated"
    assert spec_data.get("target_schema"), "spec.target_schema must be populated"

    # Invoke without --target-schema; compiler reads it from spec
    rc = subprocess.run(
        [
            "uv",
            "run",
            "linkml-map",
            "compile",
            "-T",
            str(spec_out),
            "-s",
            str(nor_linkml_path.resolve()),
            "--target",
            "yarrrml",
            # intentionally omit --target-schema
            "-o",
            str(yarrrml_out),
        ],
        cwd=str(_ROSETTA_CWD),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert rc.returncode == 0, (
        f"linkml-map compile (self-describing) failed (exit {rc.returncode}):\n"
        f"stdout: {rc.stdout}\nstderr: {rc.stderr}"
    )
    assert yarrrml_out.exists(), "YARRRML output file not created in self-describing mode"

    parsed = yaml.safe_load(yarrrml_out.read_text())
    assert isinstance(parsed, dict), "YARRRML output is not a dict"
    assert "mappings" in parsed, "YARRRML output missing 'mappings' key"
