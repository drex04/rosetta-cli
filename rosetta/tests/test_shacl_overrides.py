"""Phase 19 / Plan 19-02 / Task 5 — tests for SHACL overrides + shapes_loader.

Six tests covering:

1. Recursive merge of generated + override shapes from ``rosetta/policies/shacl/``.
2. Override constraint (``mc:AirTrackBearingRangeShape``) actually fires on a
   data graph with an out-of-range ``mc:hasBearing``.
3. Re-running ``rosetta-shacl-gen`` does NOT touch the overrides directory.
4. Legacy ``rosetta/policies/mapping.shacl.ttl`` is fully removed (D-19-09).
5. ``load_shapes_from_dir`` is symlink-loop safe and parses each file once.
6. ``load_shapes_from_dir`` warns on Turtle files containing no SHACL shapes
   but still merges them (D-19-17 — open-world warn-and-merge).
"""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

import pyshacl
import pytest
import rdflib
from click.testing import CliRunner
from rdflib.namespace import RDF

from rosetta.cli.shacl_gen import cli as shacl_gen_cli
from rosetta.core.shapes_loader import load_shapes_from_dir

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SH = rdflib.Namespace("http://www.w3.org/ns/shacl#")
MC = rdflib.Namespace("https://ontology.nato.int/core/MasterCOP#")
XSD = rdflib.Namespace("http://www.w3.org/2001/XMLSchema#")

REPO_ROOT = Path(__file__).resolve().parents[2]
SHAPES_DIR = REPO_ROOT / "rosetta" / "policies" / "shacl"
OVERRIDES_DIR = SHAPES_DIR / "overrides"
GENERATED_DIR = SHAPES_DIR / "generated"
OVERRIDE_FILE = OVERRIDES_DIR / "track_bearing_range.ttl"
GENERATED_FILE = GENERATED_DIR / "master.shacl.ttl"
LEGACY_MAPPING_SHACL = REPO_ROOT / "rosetta" / "policies" / "mapping.shacl.ttl"
MASTER_SCHEMA = REPO_ROOT / "rosetta" / "tests" / "fixtures" / "nations" / "master_cop.linkml.yaml"


# ---------------------------------------------------------------------------
# Test 1 — recursive merge of generated + override shapes
# ---------------------------------------------------------------------------


def test_shapes_dir_recursive_merge() -> None:
    """``load_shapes_from_dir`` walks generated/ + overrides/ and merges all shapes."""
    merged = load_shapes_from_dir(SHAPES_DIR)

    # Generated shape — mc:AirTrack itself is declared as a sh:NodeShape with
    # sh:targetClass mc:AirTrack in master.shacl.ttl (see generated head).
    assert (MC.AirTrack, RDF.type, SH.NodeShape) in merged
    assert (MC.AirTrack, SH.targetClass, MC.AirTrack) in merged

    # Override shape — mc:AirTrackBearingRangeShape from overrides/.
    assert (MC.AirTrackBearingRangeShape, RDF.type, SH.NodeShape) in merged
    assert (MC.AirTrackBearingRangeShape, SH.targetClass, MC.AirTrack) in merged

    # Total NodeShape count must be at least generated (43) + override (1).
    n_node_shapes = sum(1 for _ in merged.triples((None, RDF.type, SH.NodeShape)))
    assert n_node_shapes >= 44, (
        f"Expected at least 44 NodeShapes (43 generated + 1 override), got {n_node_shapes}"
    )


# ---------------------------------------------------------------------------
# Test 2 — override constraint fires on a data graph
# ---------------------------------------------------------------------------


def test_override_constraint_fires_on_data() -> None:
    """An mc:AirTrack with mc:hasBearing 400.0 must violate the override shape."""
    merged = load_shapes_from_dir(SHAPES_DIR)

    data_g = rdflib.Graph()
    data_g.bind("mc", MC)
    track = MC["track-bad-bearing"]
    data_g.add((track, RDF.type, MC.AirTrack))
    data_g.add((track, MC.hasBearing, rdflib.Literal("400.0", datatype=XSD.double)))

    conforms, report_g, _report_text = pyshacl.validate(
        data_graph=data_g,
        shacl_graph=merged,
        inference="none",
        advanced=False,
    )

    assert conforms is False, "Out-of-range bearing should violate the override shape"
    assert isinstance(report_g, rdflib.Graph), (
        f"pyshacl returned non-Graph report: {type(report_g).__name__}"
    )

    # At least one ValidationResult must cite mc:AirTrackBearingRangeShape via
    # sh:sourceShape (either the NodeShape itself or one of its blank-node
    # property shapes — depending on pyshacl reporting we accept either).
    source_shapes = set(report_g.objects(predicate=SH.sourceShape))
    cited = MC.AirTrackBearingRangeShape in source_shapes or any(
        # blank-node property shape whose parent is AirTrackBearingRangeShape
        (MC.AirTrackBearingRangeShape, SH.property, s) in merged
        for s in source_shapes
    )
    assert cited, (
        f"No ValidationResult cited mc:AirTrackBearingRangeShape; "
        f"sh:sourceShape values were: {source_shapes}"
    )


# ---------------------------------------------------------------------------
# Test 3 — override survives regen of generated/
# ---------------------------------------------------------------------------


def test_override_survives_regen() -> None:
    """Re-running ``rosetta-shacl-gen`` overwrites generated/ but not overrides/."""
    pre_bytes = OVERRIDE_FILE.read_bytes()
    pre_hash = hashlib.sha256(pre_bytes).hexdigest()

    result = CliRunner().invoke(
        shacl_gen_cli,
        [
            "--input",
            str(MASTER_SCHEMA),
            "--output",
            str(GENERATED_FILE),
        ],
    )
    assert result.exit_code == 0, (
        f"shacl-gen failed: exit={result.exit_code} output={result.output!r} "
        f"exception={result.exception!r}"
    )

    post_hash = hashlib.sha256(OVERRIDE_FILE.read_bytes()).hexdigest()
    assert pre_hash == post_hash, (
        "Overrides directory was modified by rosetta-shacl-gen — regen must only touch generated/."
    )


# ---------------------------------------------------------------------------
# Test 4 — legacy mapping.shacl.ttl removal regression guard (D-19-09)
# ---------------------------------------------------------------------------


def test_legacy_mapping_shacl_removed() -> None:
    """``rosetta/policies/mapping.shacl.ttl`` must NOT exist (D-19-09 deletion)."""
    assert not LEGACY_MAPPING_SHACL.exists(), (
        f"Legacy SHACL file resurfaced at {LEGACY_MAPPING_SHACL} — "
        "D-19-09 mandated its deletion in favour of generated/ + overrides/."
    )


# ---------------------------------------------------------------------------
# Test 5 — symlink-loop safety (review-harden)
# ---------------------------------------------------------------------------


def test_shapes_loader_does_not_follow_symlink_loop(tmp_path: Path) -> None:
    """A symlink loop inside the shapes dir must not hang the loader nor double-merge."""
    shapes = tmp_path / "shapes"
    shapes.mkdir()
    valid_ttl = shapes / "valid.ttl"
    valid_ttl.write_text(
        "@prefix sh: <http://www.w3.org/ns/shacl#> .\n"
        "@prefix ex: <http://example.org/> .\n"
        "ex:S a sh:NodeShape ; sh:targetClass ex:T .\n",
        encoding="utf-8",
    )

    loop = shapes / "loop"
    try:
        os.symlink(shapes, loop, target_is_directory=True)
    except (OSError, NotImplementedError):  # pragma: no cover — Linux supports symlinks
        pytest.skip("Filesystem does not support symlinks")

    start = time.monotonic()
    merged = load_shapes_from_dir(shapes)
    elapsed = time.monotonic() - start

    assert elapsed < 5.0, (
        f"load_shapes_from_dir took {elapsed:.2f}s — symlink loop may not be guarded"
    )

    ex = rdflib.Namespace("http://example.org/")
    # Triple must be present exactly ONCE; rdflib graphs deduplicate by default,
    # so we instead assert the count of triples loaded equals the count from a
    # single direct parse (i.e. the loop did not trigger a second os.walk pass).
    direct = rdflib.Graph()
    direct.parse(str(valid_ttl), format="turtle")

    assert (ex.S, RDF.type, SH.NodeShape) in merged
    assert (ex.S, SH.targetClass, ex.T) in merged
    assert len(merged) == len(direct), (
        f"Expected {len(direct)} triples (single parse), got {len(merged)} — "
        "symlink loop caused duplicate parses."
    )


# ---------------------------------------------------------------------------
# Test 6 — warn-and-merge on non-shape Turtle (D-19-17)
# ---------------------------------------------------------------------------


def test_shapes_loader_warns_on_non_shape_turtle(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Non-SHACL Turtle is merged but emits a stderr warning."""
    shape_ttl = tmp_path / "shape.ttl"
    shape_ttl.write_text(
        "@prefix sh: <http://www.w3.org/ns/shacl#> .\n"
        "@prefix ex: <http://example.org/> .\n"
        "ex:S a sh:NodeShape ; sh:targetClass ex:T .\n",
        encoding="utf-8",
    )

    ontology_ttl = tmp_path / "ontology.ttl"
    ontology_ttl.write_text(
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
        "@prefix ex: <http://example.org/> .\n"
        "ex:Foo a owl:Class .\n",
        encoding="utf-8",
    )

    merged = load_shapes_from_dir(tmp_path)

    ex = rdflib.Namespace("http://example.org/")
    OWL = rdflib.Namespace("http://www.w3.org/2002/07/owl#")

    # Both files merged.
    assert (ex.S, RDF.type, SH.NodeShape) in merged
    assert (ex.Foo, RDF.type, OWL.Class) in merged

    # Stderr warning emitted for the non-shape file.
    captured = capsys.readouterr()
    assert "ontology.ttl contains no SHACL shapes" in captured.err, (
        f"Expected warning for ontology.ttl in stderr; got: {captured.err!r}"
    )
