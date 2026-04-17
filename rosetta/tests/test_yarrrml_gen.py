"""Tests for rosetta-yarrrml-gen. Populated in Tasks 6 + 8."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
import yaml
from click.testing import CliRunner
from linkml_map.datamodel.transformer_model import TransformationSpecification
from linkml_runtime.linkml_model import (
    ClassDefinition,
    SchemaDefinition,
    SlotDefinition,
)
from pydantic import ValidationError

from rosetta.cli.yarrrml_gen import cli
from rosetta.core.models import CoverageReport, SSSOMRow
from rosetta.core.transform_builder import (
    ROSETTA_GLOBAL_PREFIXES,
    _build_slot_owner_index,
    _ClassifyContext,
    _ClassMapping,
    _SlotMapping,
    _Unresolved,
    build_composite_slot_derivation,
    build_spec,
    classify_row,
    filter_rows,
    group_composites,
)


# [review] Import-time shape check — guards the Plan 16-00 prerequisite.
def _verify_sssomrow_shape() -> None:
    required = {"subject_type", "object_type", "mapping_group_id", "composition_expr"}
    missing = required - set(SSSOMRow.model_fields)
    if missing:
        raise AssertionError(
            f"SSSOMRow is missing {missing}; Plan 16-00 must land before 16-01 coding. "
            "Blocked per Prerequisites."
        )


_verify_sssomrow_shape()


# ====== helper builders (not tests; underscore-prefixed) ======


def _mkrow(**overrides: object) -> SSSOMRow:
    """Build a valid SSSOMRow with sensible defaults; override specific fields via kwargs."""
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
) -> SchemaDefinition:
    """Build a SchemaDefinition with the given prefix.

    classes maps class_name → slot list; slots maps slot_name → range.
    class_uri is auto-generated as "{prefix}:{class_name}"; slot_uri as "{prefix}:{slot_name}".
    """
    return SchemaDefinition(
        id=f"https://ex/{prefix}",
        name=prefix,
        default_prefix=prefix,
        prefixes={prefix: {"prefix_prefix": prefix, "prefix_reference": f"https://ex/{prefix}/"}},
        classes={
            cname: ClassDefinition(name=cname, class_uri=f"{prefix}:{cname}", slots=cslots)
            for cname, cslots in classes.items()
        },
        slots={
            sname: SlotDefinition(name=sname, slot_uri=f"{prefix}:{sname}", range=srange)
            for sname, srange in slots.items()
        },
    )  # pyright: ignore[reportCallIssue]


# Fixture paths (repo-relative from cwd=project-root)
_FIXTURES = Path("rosetta/tests/fixtures")
_NOR_SCHEMA = _FIXTURES / "nor_radar.linkml.yaml"
_MC_SCHEMA = _FIXTURES / "master_cop.linkml.yaml"
_NOR_SSSOM = _FIXTURES / "sssom_nor_approved.sssom.tsv"


@pytest.fixture(scope="module")
def dummy_schema_paths(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """Write two empty placeholder YAML files once per test session; return (src, tgt) paths."""
    base = tmp_path_factory.mktemp("schema_paths")
    src = base / "src.yaml"
    tgt = base / "tgt.yaml"
    src.write_text("")
    tgt.write_text("")
    return src, tgt


# ====== Unit tests — filter_rows ======


def test_filter_rows_excludes_other_schema_prefixes() -> None:
    rows = [
        _mkrow(subject_id="nor_radar:Obs", predicate_id="skos:exactMatch"),
        _mkrow(subject_id="other:Obs", predicate_id="skos:exactMatch"),
    ]
    accepted, excluded = filter_rows(rows, "nor_radar", include_manual=False)
    assert len(accepted) == 1
    assert accepted[0].subject_id == "nor_radar:Obs"
    assert len(excluded["prefix"]) == 1
    assert excluded["prefix"][0].subject_id == "other:Obs"


def test_filter_rows_excludes_non_exact_predicates() -> None:
    rows = [_mkrow(subject_id="nor_radar:x", predicate_id="skos:narrowMatch")]
    accepted, excluded = filter_rows(rows, "nor_radar", include_manual=False)
    assert not accepted
    assert len(excluded["predicate"]) == 1
    assert excluded["predicate"][0].predicate_id == "skos:narrowMatch"


def test_filter_rows_drops_owl_different_from_silently() -> None:
    rows = [_mkrow(subject_id="nor_radar:x", predicate_id="owl:differentFrom")]
    accepted, excluded = filter_rows(rows, "nor_radar", include_manual=False)
    assert not accepted
    # Must NOT appear in any excluded bucket
    assert not excluded["prefix"]
    assert not excluded["predicate"]
    assert not excluded["justification"]


def test_filter_rows_default_rejects_mmc() -> None:
    rows = [_mkrow(mapping_justification="semapv:ManualMappingCuration")]
    accepted, excluded = filter_rows(rows, "nor_radar", include_manual=False)
    assert not accepted
    assert len(excluded["justification"]) == 1


def test_filter_rows_include_manual_accepts_mmc() -> None:
    rows = [_mkrow(mapping_justification="semapv:ManualMappingCuration")]
    accepted, excluded = filter_rows(rows, "nor_radar", include_manual=True)
    assert len(accepted) == 1
    assert not excluded["justification"]


# ====== Unit tests — classify_row ======


def test_classify_row_class_to_class() -> None:
    src = _mkschema("src", {"Widget": []}, {})
    mst = _mkschema("mst", {"Thing": []}, {})
    from linkml_runtime.utils.schemaview import SchemaView

    src_view = SchemaView(src)
    mst_view = SchemaView(mst)
    ctx = _ClassifyContext(
        src_view=src_view,
        master_view=mst_view,
        src_slot_owners=_build_slot_owner_index(src_view),
        mst_slot_owners=_build_slot_owner_index(mst_view),
    )
    row = _mkrow(subject_id="src:Widget", object_id="mst:Thing")
    result = classify_row(row, ctx)
    assert isinstance(result, _ClassMapping)
    assert result.source_class_name == "Widget"
    assert result.target_class_name == "Thing"


def test_classify_row_slot_to_slot() -> None:
    src = _mkschema("src", {"Widget": ["alpha"]}, {"alpha": "string"})
    mst = _mkschema("mst", {"Thing": ["beta"]}, {"beta": "string"})
    from linkml_runtime.utils.schemaview import SchemaView

    src_view = SchemaView(src)
    mst_view = SchemaView(mst)
    ctx = _ClassifyContext(
        src_view=src_view,
        master_view=mst_view,
        src_slot_owners=_build_slot_owner_index(src_view),
        mst_slot_owners=_build_slot_owner_index(mst_view),
    )
    row = _mkrow(subject_id="src:alpha", object_id="mst:beta")
    result = classify_row(row, ctx)
    assert isinstance(result, _SlotMapping)
    assert result.source_slot_name == "alpha"
    assert result.target_slot_name == "beta"
    assert result.source_owning_class == "Widget"
    assert result.target_owning_class == "Thing"


def test_classify_row_unresolved_subject() -> None:
    src = _mkschema("src", {}, {})
    mst = _mkschema("mst", {"Thing": []}, {})
    from linkml_runtime.utils.schemaview import SchemaView

    src_view = SchemaView(src)
    mst_view = SchemaView(mst)
    ctx = _ClassifyContext(
        src_view=src_view,
        master_view=mst_view,
        src_slot_owners=_build_slot_owner_index(src_view),
        mst_slot_owners=_build_slot_owner_index(mst_view),
    )
    row = _mkrow(subject_id="src:Ghost", object_id="mst:Thing")
    result = classify_row(row, ctx)
    assert isinstance(result, _Unresolved)
    assert result.side == "subject"


def test_classify_row_mixed_kinds_marked_mixed() -> None:
    src = _mkschema("src", {"Widget": []}, {})
    mst = _mkschema("mst", {"Thing": ["beta"]}, {"beta": "string"})
    from linkml_runtime.utils.schemaview import SchemaView

    src_view = SchemaView(src)
    mst_view = SchemaView(mst)
    ctx = _ClassifyContext(
        src_view=src_view,
        master_view=mst_view,
        src_slot_owners=_build_slot_owner_index(src_view),
        mst_slot_owners=_build_slot_owner_index(mst_view),
    )
    # subject is a class; object is a slot → mixed
    row = _mkrow(subject_id="src:Widget", object_id="mst:beta")
    result = classify_row(row, ctx)
    assert isinstance(result, _Unresolved)
    assert result.side == "mixed"


# ====== Unit tests — group_composites ======


def test_group_composites_splits_groups_and_singletons() -> None:
    r1 = _mkrow(record_id="r1", mapping_group_id="grp-1")
    r2 = _mkrow(record_id="r2", mapping_group_id="grp-1")
    r3 = _mkrow(record_id="r3", mapping_group_id=None)
    groups, singletons = group_composites([r1, r2, r3])
    assert "grp-1" in groups
    assert len(groups["grp-1"]) == 2
    assert len(singletons) == 1
    assert singletons[0].record_id == "r3"


# ====== Unit tests — build_composite_slot_derivation ======


def test_build_composite_slot_derivation_rejects_inconsistent_expr() -> None:
    r1 = _mkrow(record_id="r1", mapping_group_id="g", object_id="mc:X", composition_expr="[{a}]")
    r2 = _mkrow(record_id="r2", mapping_group_id="g", object_id="mc:X", composition_expr="[{b}]")
    with pytest.raises(ValueError, match="inconsistent composition_expr"):
        build_composite_slot_derivation("g", [r1, r2])


def test_build_composite_slot_derivation_rejects_all_none_expr() -> None:
    r1 = _mkrow(record_id="r1", mapping_group_id="g", object_id="mc:X", composition_expr=None)
    r2 = _mkrow(record_id="r2", mapping_group_id="g", object_id="mc:X", composition_expr=None)
    with pytest.raises(ValueError, match="no composition_expr"):
        build_composite_slot_derivation("g", [r1, r2])


def test_build_composite_slot_derivation_rejects_empty_string_expr() -> None:
    r1 = _mkrow(record_id="r1", mapping_group_id="g", object_id="mc:X", composition_expr="")
    r2 = _mkrow(record_id="r2", mapping_group_id="g", object_id="mc:X", composition_expr="")
    with pytest.raises(ValueError, match="no composition_expr"):
        build_composite_slot_derivation("g", [r1, r2])


def test_build_composite_slot_derivation_rejects_multi_target() -> None:
    r1 = _mkrow(record_id="r1", mapping_group_id="g", object_id="mc:X", composition_expr="[{a}]")
    r2 = _mkrow(record_id="r2", mapping_group_id="g", object_id="mc:Y", composition_expr="[{a}]")
    with pytest.raises(ValueError, match="multiple target slots"):
        build_composite_slot_derivation("g", [r1, r2])


# ====== Unit tests — build_spec ======


def test_build_spec_emits_valid_transformspec() -> None:
    from linkml_runtime.loaders import yaml_loader  # type: ignore[import-untyped]

    from rosetta.core.accredit import parse_sssom_tsv

    rows = parse_sssom_tsv(_NOR_SSSOM)
    src = cast(SchemaDefinition, yaml_loader.load(str(_NOR_SCHEMA), target_class=SchemaDefinition))  # pyright: ignore[reportUnknownMemberType]
    mst = cast(SchemaDefinition, yaml_loader.load(str(_MC_SCHEMA), target_class=SchemaDefinition))  # pyright: ignore[reportUnknownMemberType]
    spec, _cov = build_spec(
        rows,
        src,
        mst,
        source_schema_path=str(_NOR_SCHEMA.resolve()),
        target_schema_path=str(_MC_SCHEMA.resolve()),
        force=True,
    )
    # Round-trip via model_validate
    TransformationSpecification.model_validate(spec.model_dump())  # pyright: ignore[reportUnknownMemberType]


def test_build_spec_class_derivations_is_list() -> None:
    from linkml_runtime.loaders import yaml_loader  # type: ignore[import-untyped]

    from rosetta.core.accredit import parse_sssom_tsv

    rows = parse_sssom_tsv(_NOR_SSSOM)
    src = cast(SchemaDefinition, yaml_loader.load(str(_NOR_SCHEMA), target_class=SchemaDefinition))  # pyright: ignore[reportUnknownMemberType]
    mst = cast(SchemaDefinition, yaml_loader.load(str(_MC_SCHEMA), target_class=SchemaDefinition))  # pyright: ignore[reportUnknownMemberType]
    spec, _cov = build_spec(
        rows,
        src,
        mst,
        source_schema_path=str(_NOR_SCHEMA.resolve()),
        target_schema_path=str(_MC_SCHEMA.resolve()),
        force=True,
    )
    assert isinstance(spec.class_derivations, list)


def test_build_spec_errors_on_unresolvable_without_force(
    dummy_schema_paths: tuple[Path, Path],
) -> None:
    src_path, tgt_path = dummy_schema_paths
    src = _mkschema("src", {"Widget": []}, {})
    mst = _mkschema("mst", {"Thing": []}, {})
    rows = [
        _mkrow(subject_id="src:Widget", object_id="mst:Thing"),
        _mkrow(subject_id="src:Widget", object_id="mst:Ghost"),  # unresolvable object
    ]
    with pytest.raises(ValueError, match="Unresolvable CURIEs"):
        build_spec(
            rows, src, mst, source_schema_path=src_path, target_schema_path=tgt_path, force=False
        )


def test_build_spec_force_proceeds_with_unresolvable_logged(
    dummy_schema_paths: tuple[Path, Path],
) -> None:
    src_path, tgt_path = dummy_schema_paths
    src = _mkschema("src", {"Widget": []}, {})
    mst = _mkschema("mst", {"Thing": []}, {})
    rows = [
        _mkrow(subject_id="src:Widget", object_id="mst:Thing"),
        _mkrow(subject_id="src:Widget", object_id="mst:Ghost"),  # unresolvable object
    ]
    _spec, coverage = build_spec(
        rows, src, mst, source_schema_path=src_path, target_schema_path=tgt_path, force=True
    )
    assert len(coverage.unresolved_objects) == 1


def test_build_spec_force_does_not_bypass_mixed_kind(
    dummy_schema_paths: tuple[Path, Path],
) -> None:
    src_path, tgt_path = dummy_schema_paths
    src = _mkschema("src", {"Widget": []}, {})
    mst = _mkschema("mst", {"Thing": ["beta"]}, {"beta": "string"})
    rows = [
        _mkrow(subject_id="src:Widget", object_id="mst:beta"),  # mixed: class→slot
    ]
    with pytest.raises(ValueError, match="mixed-kind"):
        build_spec(
            rows, src, mst, source_schema_path=src_path, target_schema_path=tgt_path, force=True
        )


def test_build_spec_force_does_not_bypass_missing_class_mapping(
    dummy_schema_paths: tuple[Path, Path],
) -> None:
    src_path, tgt_path = dummy_schema_paths
    src = _mkschema("src", {"Widget": ["alpha"]}, {"alpha": "string"})
    mst = _mkschema("mst", {"Thing": ["beta"]}, {"beta": "string"})
    # Only a slot mapping — no class-level mapping row
    rows = [_mkrow(subject_id="src:alpha", object_id="mst:beta")]
    with pytest.raises(ValueError, match="no class-level mapping"):
        build_spec(
            rows, src, mst, source_schema_path=src_path, target_schema_path=tgt_path, force=True
        )


def test_build_spec_errors_on_missing_class_mapping_for_mapped_slot(
    dummy_schema_paths: tuple[Path, Path],
) -> None:
    src_path, tgt_path = dummy_schema_paths
    src = _mkschema("src", {"Widget": ["alpha"]}, {"alpha": "string"})
    mst = _mkschema("mst", {"Thing": ["beta"]}, {"beta": "string"})
    rows = [_mkrow(subject_id="src:alpha", object_id="mst:beta")]
    with pytest.raises(ValueError, match="no class-level mapping"):
        build_spec(
            rows, src, mst, source_schema_path=src_path, target_schema_path=tgt_path, force=False
        )


def test_build_spec_errors_on_missing_class_mapping_for_composite_only_owner(
    dummy_schema_paths: tuple[Path, Path],
) -> None:
    src_path, tgt_path = dummy_schema_paths
    src = _mkschema("src", {"Widget": ["alpha", "gamma"]}, {"alpha": "string", "gamma": "string"})
    mst = _mkschema("mst", {"Thing": ["beta"]}, {"beta": "string"})
    # Composite group only — no class-level mapping row for Thing
    r1 = _mkrow(
        subject_id="src:alpha",
        object_id="mst:beta",
        mapping_group_id="g1",
        composition_expr="[{alpha}]",
    )
    r2 = _mkrow(
        subject_id="src:gamma",
        object_id="mst:beta",
        mapping_group_id="g1",
        composition_expr="[{alpha}]",
    )
    with pytest.raises(ValueError, match="no class-level mapping"):
        build_spec(
            [r1, r2], src, mst, source_schema_path=src_path, target_schema_path=tgt_path, force=True
        )


def test_build_spec_datatype_warning_for_mismatched_ranges(
    dummy_schema_paths: tuple[Path, Path],
) -> None:
    src_path, tgt_path = dummy_schema_paths
    src = _mkschema("src", {"Widget": ["alpha"]}, {"alpha": "integer"})
    mst = _mkschema("mst", {"Thing": ["beta"]}, {"beta": "string"})
    rows = [
        _mkrow(subject_id="src:Widget", object_id="mst:Thing"),
        _mkrow(
            subject_id="src:alpha",
            object_id="mst:beta",
            subject_datatype="xsd:integer",
            object_datatype="xsd:string",
        ),
    ]
    _spec, coverage = build_spec(
        rows, src, mst, source_schema_path=src_path, target_schema_path=tgt_path, force=False
    )
    assert len(coverage.datatype_warnings) == 1


def test_build_spec_composite_group_flows_to_expr() -> None:
    from linkml_runtime.loaders import yaml_loader  # type: ignore[import-untyped]

    from rosetta.core.accredit import parse_sssom_tsv

    rows = parse_sssom_tsv(_NOR_SSSOM)
    src = cast(SchemaDefinition, yaml_loader.load(str(_NOR_SCHEMA), target_class=SchemaDefinition))  # pyright: ignore[reportUnknownMemberType]
    mst = cast(SchemaDefinition, yaml_loader.load(str(_MC_SCHEMA), target_class=SchemaDefinition))  # pyright: ignore[reportUnknownMemberType]
    spec, _cov = build_spec(
        rows,
        src,
        mst,
        source_schema_path=str(_NOR_SCHEMA.resolve()),
        target_schema_path=str(_MC_SCHEMA.resolve()),
        force=True,
    )
    # Find the composite SlotDerivation with expr
    found_expr: str | None = None
    cds = spec.class_derivations or []
    iter_cds: object = cds.values() if isinstance(cds, dict) else cds
    for cd in iter_cds:  # pyright: ignore[reportUnknownVariableType]
        sds = getattr(cd, "slot_derivations", None) or {}
        if isinstance(sds, dict):
            for sd in sds.values():
                if getattr(sd, "expr", None):
                    found_expr = str(sd.expr)
        else:
            for sd in sds:
                if getattr(sd, "expr", None):
                    found_expr = str(sd.expr)
    assert found_expr == "[{breddegrad},{lengdegrad}]"


def test_build_spec_populates_unmapped_required_master_slots(
    dummy_schema_paths: tuple[Path, Path],
) -> None:
    src_path, tgt_path = dummy_schema_paths
    src = _mkschema("src", {"Widget": ["alpha"]}, {"alpha": "string"})
    # Master class Thing has 3 required slots; we only map beta
    mst = SchemaDefinition(
        id="https://ex/mst",
        name="mst",
        default_prefix="mst",
        prefixes={"mst": {"prefix_prefix": "mst", "prefix_reference": "https://ex/mst/"}},
        classes={
            "Thing": ClassDefinition(
                name="Thing",
                class_uri="mst:Thing",
                slots=["beta", "gamma", "delta"],
            )
        },
        slots={
            "beta": SlotDefinition(name="beta", slot_uri="mst:beta", required=True),
            "gamma": SlotDefinition(name="gamma", slot_uri="mst:gamma", required=True),
            "delta": SlotDefinition(name="delta", slot_uri="mst:delta", required=True),
        },
    )  # pyright: ignore[reportCallIssue]
    rows = [
        _mkrow(subject_id="src:Widget", object_id="mst:Thing"),
        _mkrow(subject_id="src:alpha", object_id="mst:beta"),
    ]
    _spec, coverage = build_spec(
        rows, src, mst, source_schema_path=src_path, target_schema_path=tgt_path, force=False
    )
    assert len(coverage.unmapped_required_master_slots) == 2


def test_build_spec_coverage_datatype_warnings_populated(
    dummy_schema_paths: tuple[Path, Path],
) -> None:
    src_path, tgt_path = dummy_schema_paths
    src = _mkschema("src", {"Widget": ["alpha"]}, {"alpha": "integer"})
    mst = _mkschema("mst", {"Thing": ["beta"]}, {"beta": "string"})
    rows = [
        _mkrow(subject_id="src:Widget", object_id="mst:Thing"),
        _mkrow(
            subject_id="src:alpha",
            object_id="mst:beta",
            subject_datatype="xsd:integer",
            object_datatype="xsd:string",
        ),
    ]
    _spec, coverage = build_spec(
        rows, src, mst, source_schema_path=src_path, target_schema_path=tgt_path, force=False
    )
    assert len(coverage.datatype_warnings) == 1
    assert coverage.datatype_warnings[0]["subject_datatype"] == "xsd:integer"
    assert coverage.datatype_warnings[0]["object_datatype"] == "xsd:string"


def test_coverage_report_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        CoverageReport(  # pyright: ignore[reportCallIssue,reportArgumentType]
            **{"unknown_field": 1},  # pyright: ignore[reportArgumentType]
            source_schema_prefix="src",
            master_schema_prefix="mst",
            rows_total=0,
            rows_after_prefix_filter=0,
            rows_after_predicate_filter=0,
            rows_after_justification_filter=0,
        )


# ====== CLI integration tests ======


def test_cli_happy_path(tmp_path: Path) -> None:
    out_yaml = tmp_path / "spec.yaml"
    out_cov = tmp_path / "coverage.json"
    result = CliRunner().invoke(
        cli,
        [
            "--sssom",
            str(_NOR_SSSOM),
            "--source-schema",
            str(_NOR_SCHEMA),
            "--master-schema",
            str(_MC_SCHEMA),
            "--output",
            str(out_yaml),
            "--coverage-report",
            str(out_cov),
            "--force",
        ],
    )
    assert result.exit_code == 0, result.output + (result.exception and str(result.exception) or "")
    # Spec round-trips
    spec_data = yaml.safe_load(out_yaml.read_text())
    TransformationSpecification.model_validate(spec_data)  # pyright: ignore[reportUnknownMemberType]
    # Coverage validates
    cov_data = json.loads(out_cov.read_text())
    CoverageReport.model_validate(cov_data)


def test_cli_exit_1_on_unresolvable_without_force(tmp_path: Path) -> None:
    sssom_content = (
        "# sssom_version: https://w3id.org/sssom/spec/0.15\n"
        "# mapping_set_id: http://rosetta.interop/test\n"
        "# curie_map:\n"
        "#   nor_radar: http://rosetta.interop/nor_radar/\n"
        "#   mc: http://rosetta.interop/master-cop/\n"
        "#   skos: http://www.w3.org/2004/02/skos/core#\n"
        "#   semapv: https://w3id.org/semapv/vocab/\n"
        "subject_id\tpredicate_id\tobject_id\tmapping_justification\tconfidence\tsubject_label\tobject_label\tmapping_date\trecord_id\tsubject_type\tobject_type\tmapping_group_id\tcomposition_expr\n"
        "nor_radar:Observation\tskos:exactMatch\tmc:Track\tsemapv:HumanCuration\t0.9\t\tTrack\t2026-04-16\tr001\t\t\t\t\n"
        "nor_radar:breddegrad\tskos:exactMatch\tmc:DOES_NOT_EXIST\tsemapv:HumanCuration\t0.9\t\t\t2026-04-16\tr002\t\t\t\t\n"
    )
    sssom_file = tmp_path / "test.sssom.tsv"
    sssom_file.write_text(sssom_content)
    result = CliRunner().invoke(
        cli,
        [
            "--sssom",
            str(sssom_file),
            "--source-schema",
            str(_NOR_SCHEMA),
            "--master-schema",
            str(_MC_SCHEMA),
            "--source-format",
            "csv",
        ],
    )
    assert result.exit_code == 1
    assert "Unresolvable CURIEs" in (
        result.output + (result.exception and str(result.exception) or "")
    )


def test_cli_exit_1_on_empty_filtered(tmp_path: Path) -> None:
    # All rows have different prefix → filtered to empty
    sssom_content = (
        "# sssom_version: https://w3id.org/sssom/spec/0.15\n"
        "# mapping_set_id: http://rosetta.interop/test\n"
        "# curie_map:\n"
        "#   deu_radar: http://rosetta.interop/deu_radar/\n"
        "#   mc: http://rosetta.interop/master-cop/\n"
        "#   skos: http://www.w3.org/2004/02/skos/core#\n"
        "#   semapv: https://w3id.org/semapv/vocab/\n"
        "subject_id\tpredicate_id\tobject_id\tmapping_justification\tconfidence\tsubject_label\tobject_label\tmapping_date\trecord_id\tsubject_type\tobject_type\tmapping_group_id\tcomposition_expr\n"
        "deu_radar:foo\tskos:exactMatch\tmc:bar\tsemapv:HumanCuration\t0.9\t\tbar\t2026-04-16\tr010\t\t\t\t\n"
    )
    sssom_file = tmp_path / "empty.sssom.tsv"
    sssom_file.write_text(sssom_content)
    result = CliRunner().invoke(
        cli,
        [
            "--sssom",
            str(sssom_file),
            "--source-schema",
            str(_NOR_SCHEMA),
            "--master-schema",
            str(_MC_SCHEMA),
            "--source-format",
            "csv",
        ],
    )
    assert result.exit_code == 1
    assert "no rows after filtering" in (
        result.output + (result.exception and str(result.exception) or "")
    )


def test_cli_allow_empty_returns_0(tmp_path: Path) -> None:
    sssom_content = (
        "# sssom_version: https://w3id.org/sssom/spec/0.15\n"
        "# mapping_set_id: http://rosetta.interop/test\n"
        "# curie_map:\n"
        "#   deu_radar: http://rosetta.interop/deu_radar/\n"
        "#   mc: http://rosetta.interop/master-cop/\n"
        "#   skos: http://www.w3.org/2004/02/skos/core#\n"
        "#   semapv: https://w3id.org/semapv/vocab/\n"
        "subject_id\tpredicate_id\tobject_id\tmapping_justification\tconfidence\tsubject_label\tobject_label\tmapping_date\trecord_id\tsubject_type\tobject_type\tmapping_group_id\tcomposition_expr\n"
        "deu_radar:foo\tskos:exactMatch\tmc:bar\tsemapv:HumanCuration\t0.9\t\tbar\t2026-04-16\tr010\t\t\t\t\n"
    )
    sssom_file = tmp_path / "empty.sssom.tsv"
    sssom_file.write_text(sssom_content)
    result = CliRunner().invoke(
        cli,
        [
            "--sssom",
            str(sssom_file),
            "--source-schema",
            str(_NOR_SCHEMA),
            "--master-schema",
            str(_MC_SCHEMA),
            "--source-format",
            "csv",
            "--allow-empty",
        ],
    )
    assert result.exit_code == 0, result.output + (result.exception and str(result.exception) or "")


def test_cli_include_manual_accepts_mmc_rows(tmp_path: Path) -> None:
    sssom_content = (
        "# sssom_version: https://w3id.org/sssom/spec/0.15\n"
        "# mapping_set_id: http://rosetta.interop/test\n"
        "# curie_map:\n"
        "#   nor_radar: http://rosetta.interop/nor_radar/\n"
        "#   mc: http://rosetta.interop/master-cop/\n"
        "#   skos: http://www.w3.org/2004/02/skos/core#\n"
        "#   semapv: https://w3id.org/semapv/vocab/\n"
        "subject_id\tpredicate_id\tobject_id\tmapping_justification\tconfidence\tsubject_label\tobject_label\tmapping_date\trecord_id\tsubject_type\tobject_type\tmapping_group_id\tcomposition_expr\n"
        "nor_radar:Observation\tskos:exactMatch\tmc:Track\tsemapv:ManualMappingCuration\t0.9\t\tTrack\t2026-04-16\tr001\t\t\t\t\n"
    )
    sssom_file = tmp_path / "mmc.sssom.tsv"
    sssom_file.write_text(sssom_content)
    # Without --include-manual: filtered to empty → exit 1
    result_no = CliRunner().invoke(
        cli,
        [
            "--sssom",
            str(sssom_file),
            "--source-schema",
            str(_NOR_SCHEMA),
            "--master-schema",
            str(_MC_SCHEMA),
            "--source-format",
            "csv",
        ],
    )
    assert result_no.exit_code == 1

    # With --include-manual: accepted → exit 0 (single class row, no slots → valid)
    result_yes = CliRunner().invoke(
        cli,
        [
            "--sssom",
            str(sssom_file),
            "--source-schema",
            str(_NOR_SCHEMA),
            "--master-schema",
            str(_MC_SCHEMA),
            "--source-format",
            "csv",
            "--include-manual",
        ],
    )
    assert result_yes.exit_code == 0, result_yes.output + (
        result_yes.exception and str(result_yes.exception) or ""
    )


def test_cli_filters_by_source_prefix(tmp_path: Path) -> None:
    sssom_content = (
        "# sssom_version: https://w3id.org/sssom/spec/0.15\n"
        "# mapping_set_id: http://rosetta.interop/test\n"
        "# curie_map:\n"
        "#   nor_radar: http://rosetta.interop/nor_radar/\n"
        "#   deu_radar: http://rosetta.interop/deu_radar/\n"
        "#   mc: http://rosetta.interop/master-cop/\n"
        "#   skos: http://www.w3.org/2004/02/skos/core#\n"
        "#   semapv: https://w3id.org/semapv/vocab/\n"
        "subject_id\tpredicate_id\tobject_id\tmapping_justification\tconfidence\tsubject_label\tobject_label\tmapping_date\trecord_id\tsubject_type\tobject_type\tmapping_group_id\tcomposition_expr\n"
        "nor_radar:Observation\tskos:exactMatch\tmc:Track\tsemapv:HumanCuration\t0.9\t\tTrack\t2026-04-16\tr001\t\t\t\t\n"
        "deu_radar:Entity\tskos:exactMatch\tmc:Track\tsemapv:HumanCuration\t0.9\t\tTrack\t2026-04-16\tr002\t\t\t\t\n"
    )
    sssom_file = tmp_path / "mixed.sssom.tsv"
    sssom_file.write_text(sssom_content)
    out_yaml = tmp_path / "spec.yaml"
    result = CliRunner().invoke(
        cli,
        [
            "--sssom",
            str(sssom_file),
            "--source-schema",
            str(_NOR_SCHEMA),
            "--master-schema",
            str(_MC_SCHEMA),
            "--source-format",
            "csv",
            "--output",
            str(out_yaml),
        ],
    )
    # Should succeed processing only nor_radar rows
    assert result.exit_code == 0, result.output + (result.exception and str(result.exception) or "")
    spec_text = out_yaml.read_text()
    # deu_radar should not appear in the output spec
    assert "deu_radar" not in spec_text


def test_cli_source_format_falls_back_to_schema_annotation(tmp_path: Path) -> None:
    # nor_radar has annotation rosetta_source_format: csv; omit --source-format
    out_yaml = tmp_path / "spec.yaml"
    result = CliRunner().invoke(
        cli,
        [
            "--sssom",
            str(_NOR_SSSOM),
            "--source-schema",
            str(_NOR_SCHEMA),
            "--master-schema",
            str(_MC_SCHEMA),
            "--output",
            str(out_yaml),
            "--force",
        ],
    )
    assert result.exit_code == 0, result.output + (result.exception and str(result.exception) or "")
    spec_text = out_yaml.read_text()
    assert "rosetta:source_format=csv" in spec_text


def test_cli_source_format_exits_1_when_neither_flag_nor_annotation(tmp_path: Path) -> None:
    # master_cop.linkml.yaml has no rosetta_source_format annotation; use it as source
    out_yaml = tmp_path / "spec.yaml"
    result = CliRunner().invoke(
        cli,
        [
            "--sssom",
            str(_NOR_SSSOM),
            "--source-schema",
            str(_MC_SCHEMA),  # no annotation
            "--master-schema",
            str(_NOR_SCHEMA),
            "--output",
            str(out_yaml),
        ],
    )
    assert result.exit_code != 0
    assert "rosetta_source_format" in (
        result.output + (result.exception and str(result.exception) or "")
    )


def test_cli_stdout_mode_when_output_omitted(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        cli,
        [
            "--sssom",
            str(_NOR_SSSOM),
            "--source-schema",
            str(_NOR_SCHEMA),
            "--master-schema",
            str(_MC_SCHEMA),
            "--force",
        ],
    )
    assert result.exit_code == 0, result.output + (result.exception and str(result.exception) or "")
    # Output should be YAML
    assert result.output.startswith("comments:") or result.output.startswith("id:")


def test_cli_malformed_source_schema_exits_1_cleanly(tmp_path: Path) -> None:
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("{ broken yaml: [unclosed\n")
    result = CliRunner().invoke(
        cli,
        [
            "--sssom",
            str(_NOR_SSSOM),
            "--source-schema",
            str(bad_yaml),
            "--master-schema",
            str(_MC_SCHEMA),
            "--source-format",
            "csv",
        ],
    )
    assert result.exit_code == 1
    combined = result.output + (result.exception and str(result.exception) or "")
    assert "Error loading source schema" in combined
    assert "Traceback" not in combined


def test_cli_missing_master_schema_exits_1_cleanly(tmp_path: Path) -> None:
    nonexistent = tmp_path / "nonexistent_master.yaml"
    result = CliRunner().invoke(
        cli,
        [
            "--sssom",
            str(_NOR_SSSOM),
            "--source-schema",
            str(_NOR_SCHEMA),
            "--master-schema",
            str(nonexistent),
            "--source-format",
            "csv",
        ],
    )
    assert result.exit_code != 0


def test_cli_comments_carry_effective_source_format(tmp_path: Path) -> None:
    out_yaml = tmp_path / "spec.yaml"
    result = CliRunner().invoke(
        cli,
        [
            "--sssom",
            str(_NOR_SSSOM),
            "--source-schema",
            str(_NOR_SCHEMA),
            "--master-schema",
            str(_MC_SCHEMA),
            "--output",
            str(out_yaml),
            "--force",
        ],
    )
    assert result.exit_code == 0, result.output + (result.exception and str(result.exception) or "")
    spec_text = out_yaml.read_text()
    assert "rosetta:source_format=csv" in spec_text


def test_build_spec_accepts_prefiltered_tuple(
    dummy_schema_paths: tuple[Path, Path],
) -> None:
    """build_spec honours prefiltered= kwarg and skips internal filter_rows.

    Verifies that coverage filter-stage counts are consistent whether
    prefiltered is supplied or omitted.
    """
    src_path, tgt_path = dummy_schema_paths
    src = _mkschema("nor_radar", {"Observation": ["frequency"]}, {"frequency": "string"})
    mst = _mkschema("cop", {"Track": ["frequency"]}, {"frequency": "string"})

    rows = [
        _mkrow(subject_id="nor_radar:Observation", object_id="cop:Track"),
        _mkrow(subject_id="nor_radar:frequency", object_id="cop:frequency"),
        # Row from a different schema prefix — excluded at prefix stage
        _mkrow(subject_id="other:Foo", object_id="cop:Track"),
    ]

    # Call filter_rows once (as CLI would), then pass prefiltered= to build_spec
    remaining, excluded = filter_rows(rows, "nor_radar", include_manual=False)
    assert len(excluded["prefix"]) == 1  # the "other:Foo" row

    _, coverage_pre = build_spec(
        rows,
        src,
        mst,
        source_schema_path=src_path,
        target_schema_path=tgt_path,
        force=True,
        prefiltered=(remaining, excluded),
    )

    # Also call without prefiltered to confirm counts match
    _, coverage_plain = build_spec(
        rows, src, mst, source_schema_path=src_path, target_schema_path=tgt_path, force=True
    )

    assert coverage_pre.rows_after_prefix_filter == coverage_plain.rows_after_prefix_filter
    assert coverage_pre.rows_after_predicate_filter == coverage_plain.rows_after_predicate_filter
    assert (
        coverage_pre.rows_after_justification_filter
        == coverage_plain.rows_after_justification_filter
    )
    # Sanity: 3 total rows, 1 excluded by prefix → 2 pass
    assert coverage_pre.rows_after_prefix_filter == 2
    assert coverage_pre.rows_after_justification_filter == 2


# ====== New tests — schema paths + prefix population ======


def test_build_spec_populates_source_and_target_schema(
    dummy_schema_paths: tuple[Path, Path],
) -> None:
    src_path, tgt_path = dummy_schema_paths
    src = _mkschema("src", {"Widget": ["alpha"]}, {"alpha": "string"})
    mst = _mkschema("mst", {"Thing": ["alpha"]}, {"alpha": "string"})
    rows = [
        _mkrow(subject_id="src:Widget", object_id="mst:Thing"),
        _mkrow(subject_id="src:alpha", object_id="mst:alpha"),
    ]
    spec, _ = build_spec(
        rows, src, mst, source_schema_path=src_path, target_schema_path=tgt_path, force=False
    )
    assert spec.source_schema == str(src_path.resolve())
    assert spec.target_schema == str(tgt_path.resolve())


def test_build_spec_raises_on_missing_source_path(
    dummy_schema_paths: tuple[Path, Path],
) -> None:
    _src_path, tgt_path = dummy_schema_paths
    src = _mkschema("src", {"Widget": []}, {})
    mst = _mkschema("mst", {"Thing": []}, {})
    rows = [_mkrow(subject_id="src:Widget", object_id="mst:Thing")]
    with pytest.raises(ValueError, match="source_schema_path"):
        build_spec(rows, src, mst, source_schema_path="", target_schema_path=tgt_path, force=True)  # pyright: ignore[reportArgumentType]


def test_build_spec_raises_on_missing_target_path(
    dummy_schema_paths: tuple[Path, Path],
) -> None:
    src_path, _tgt_path = dummy_schema_paths
    src = _mkschema("src", {"Widget": []}, {})
    mst = _mkschema("mst", {"Thing": []}, {})
    rows = [_mkrow(subject_id="src:Widget", object_id="mst:Thing")]
    with pytest.raises(ValueError, match="target_schema_path"):
        build_spec(
            rows,
            src,
            mst,
            source_schema_path=src_path,
            target_schema_path="/nonexistent/file.yaml",
            force=True,
        )


def test_build_spec_prefixes_include_rosetta_globals(
    dummy_schema_paths: tuple[Path, Path],
) -> None:
    src_path, tgt_path = dummy_schema_paths
    src = _mkschema("ex", {"Widget": ["alpha"]}, {"alpha": "string"})
    mst = _mkschema("mc", {"Thing": ["alpha"]}, {"alpha": "string"})
    rows = [
        _mkrow(subject_id="ex:Widget", object_id="mc:Thing"),
        _mkrow(subject_id="ex:alpha", object_id="mc:alpha"),
    ]
    spec, _ = build_spec(
        rows, src, mst, source_schema_path=src_path, target_schema_path=tgt_path, force=False
    )
    prefixes = spec.prefixes or {}
    # Rosetta globals must be present
    for key, expected_iri in ROSETTA_GLOBAL_PREFIXES.items():
        assert key in prefixes, f"Global prefix '{key}' missing from spec.prefixes"
        kv = prefixes[key]
        assert kv.value == expected_iri, (
            f"prefix '{key}' IRI mismatch: {kv.value!r} != {expected_iri!r}"
        )
    # Schema-own prefixes
    assert "ex" in prefixes
    assert "mc" in prefixes


def test_build_spec_prefixes_source_wins_on_collision(
    dummy_schema_paths: tuple[Path, Path],
) -> None:
    src_path, tgt_path = dummy_schema_paths
    from linkml_runtime.linkml_model import ClassDefinition, SlotDefinition

    src = SchemaDefinition(
        id="https://ex/src",
        name="src",
        default_prefix="src",
        prefixes={
            "src": {"prefix_prefix": "src", "prefix_reference": "https://ex/src/"},
            "common": {
                "prefix_prefix": "common",
                "prefix_reference": "https://source.example/common/",
            },
        },
        classes={"Widget": ClassDefinition(name="Widget", class_uri="src:Widget", slots=["alpha"])},
        slots={"alpha": SlotDefinition(name="alpha", slot_uri="src:alpha", range="string")},
    )  # pyright: ignore[reportCallIssue]
    mst = SchemaDefinition(
        id="https://ex/mst",
        name="mst",
        default_prefix="mst",
        prefixes={
            "mst": {"prefix_prefix": "mst", "prefix_reference": "https://ex/mst/"},
            "common": {
                "prefix_prefix": "common",
                "prefix_reference": "https://master.example/common/",
            },
        },
        classes={"Thing": ClassDefinition(name="Thing", class_uri="mst:Thing", slots=["alpha"])},
        slots={"alpha": SlotDefinition(name="alpha", slot_uri="mst:alpha", range="string")},
    )  # pyright: ignore[reportCallIssue]
    rows = [
        _mkrow(subject_id="src:Widget", object_id="mst:Thing"),
        _mkrow(subject_id="src:alpha", object_id="mst:alpha"),
    ]
    spec, _ = build_spec(
        rows, src, mst, source_schema_path=src_path, target_schema_path=tgt_path, force=False
    )
    prefixes = spec.prefixes or {}
    assert "common" in prefixes
    # Source prefix must win
    assert prefixes["common"].value == "https://source.example/common/"


def test_cli_populates_spec_source_target_paths(tmp_path: Path) -> None:
    from linkml_runtime.dumpers import yaml_dumper  # type: ignore[import-untyped]  # noqa: F401

    out_yaml = tmp_path / "spec.yaml"
    result = CliRunner().invoke(
        cli,
        [
            "--sssom",
            str(_NOR_SSSOM),
            "--source-schema",
            str(_NOR_SCHEMA),
            "--master-schema",
            str(_MC_SCHEMA),
            "--output",
            str(out_yaml),
            "--force",
        ],
    )
    assert result.exit_code == 0, result.output + (result.exception and str(result.exception) or "")
    spec_data = yaml.safe_load(out_yaml.read_text())
    assert spec_data.get("source_schema") == str(_NOR_SCHEMA.resolve())
    assert spec_data.get("target_schema") == str(_MC_SCHEMA.resolve())
    prefixes = spec_data.get("prefixes") or {}
    # prefixes may be a list of dicts (YAML serialization of dict[str, KeyVal])
    # or a plain dict — handle both shapes
    if isinstance(prefixes, list):
        skos_entries = [
            p for p in prefixes if (p.get("key") if isinstance(p, dict) else None) == "skos"
        ]
        assert skos_entries, "skos prefix not found in spec prefixes list"
        assert skos_entries[0].get("value") == "http://www.w3.org/2004/02/skos/core#"
    else:
        assert "skos" in prefixes
        skos_val = prefixes["skos"]
        if isinstance(skos_val, dict):
            assert skos_val.get("value") == "http://www.w3.org/2004/02/skos/core#"
        else:
            assert skos_val == "http://www.w3.org/2004/02/skos/core#"
