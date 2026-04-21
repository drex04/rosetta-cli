"""Tests for SHACL shapes loading, override merging, and loader edge-cases.

Covers:

1. Recursive merge of generated + override shapes via ``load_shapes_from_dir``.
2. Override constraint (``mc:AirTrackBearingRangeShape``) fires on invalid data.
3. Re-running ``rosetta-shacl-gen`` does NOT touch unrelated files.
4. ``load_shapes_from_dir`` is symlink-loop safe and parses each file once.
5. ``load_shapes_from_dir`` warns on Turtle files containing no SHACL shapes.
6. ``load_shapes_from_dir`` surfaces file path on malformed Turtle.
7. ``load_shapes_from_dir`` rejects non-directory paths.
"""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

import pytest
import rdflib
from click.testing import CliRunner
from rdflib.namespace import RDF

from rosetta.cli.shacl_gen import cli as shacl_gen_cli
from rosetta.core.shacl_validate import validate_graph
from rosetta.core.shapes_loader import load_shapes_from_dir

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SH = rdflib.Namespace("http://www.w3.org/ns/shacl#")
MC = rdflib.Namespace("https://ontology.nato.int/core/MasterCOP#")
XSD = rdflib.Namespace("http://www.w3.org/2001/XMLSchema#")

_NATIONS = Path(__file__).resolve().parent / "fixtures" / "nations"
_MASTER_SCHEMA = _NATIONS / "master_cop.linkml.yaml"
_GENERATED_SHAPES = _NATIONS / "master_cop.shapes.ttl"
_OVERRIDE_SHAPES = _NATIONS / "track_bearing_range.override.ttl"


# ---------------------------------------------------------------------------
# Test 1 — recursive merge of generated + override shapes
# ---------------------------------------------------------------------------


def test_shapes_dir_recursive_merge(tmp_path: Path) -> None:
    """``load_shapes_from_dir`` walks a dir and merges all .ttl shapes."""
    shapes_dir = tmp_path / "shapes"
    shapes_dir.mkdir()
    (shapes_dir / "generated").mkdir()

    import shutil

    shutil.copy(_GENERATED_SHAPES, shapes_dir / "generated" / "master.shacl.ttl")
    shutil.copy(_OVERRIDE_SHAPES, shapes_dir / "override.ttl")

    merged = load_shapes_from_dir(shapes_dir)

    assert (MC.AirTrack, RDF.type, SH.NodeShape) in merged
    assert (MC.AirTrack, SH.targetClass, MC.AirTrack) in merged

    assert (MC.AirTrackBearingRangeShape, RDF.type, SH.NodeShape) in merged
    assert (MC.AirTrackBearingRangeShape, SH.targetClass, MC.AirTrack) in merged

    n_node_shapes = sum(1 for _ in merged.triples((None, RDF.type, SH.NodeShape)))
    assert n_node_shapes >= 44, (
        f"Expected at least 44 NodeShapes (43 generated + 1 override), got {n_node_shapes}"
    )


# ---------------------------------------------------------------------------
# Test 2 — override constraint fires on a data graph
# ---------------------------------------------------------------------------


def test_override_constraint_fires_on_data(tmp_path: Path) -> None:
    """An mc:AirTrack with mc:hasBearing 400.0 must violate the override shape."""
    import shutil

    shapes_dir = tmp_path / "shapes"
    shapes_dir.mkdir()
    shutil.copy(_GENERATED_SHAPES, shapes_dir / "generated.ttl")
    shutil.copy(_OVERRIDE_SHAPES, shapes_dir / "override.ttl")

    merged = load_shapes_from_dir(shapes_dir)

    data_g = rdflib.Graph()
    data_g.bind("mc", MC)
    track = MC["track-bad-bearing"]
    data_g.add((track, RDF.type, MC.AirTrack))
    data_g.add((track, MC.hasBearing, rdflib.Literal("400.0", datatype=XSD.double)))

    report = validate_graph(data_g, merged)

    assert not report.summary.conforms, "Out-of-range bearing should violate the override shape"

    focus_nodes = {f.focus_node for f in report.findings}
    assert str(track) in focus_nodes, (
        f"Expected mc:track-bad-bearing in violation focus nodes; got {focus_nodes}"
    )


# ---------------------------------------------------------------------------
# Test 3 — override survives regen of generated shapes
# ---------------------------------------------------------------------------


def test_override_survives_regen(tmp_path: Path) -> None:
    """Re-running ``rosetta-shacl-gen`` writes to ``--output`` and never touches other files."""
    override_copy = tmp_path / "override.ttl"
    import shutil

    shutil.copy(_OVERRIDE_SHAPES, override_copy)
    pre_hash = hashlib.sha256(override_copy.read_bytes()).hexdigest()

    regen_output = tmp_path / "regen.shacl.ttl"
    result = CliRunner().invoke(
        shacl_gen_cli,
        ["--input", str(_MASTER_SCHEMA), "--output", str(regen_output)],
    )
    assert result.exit_code == 0, (
        f"shacl-gen failed: exit={result.exit_code} output={result.output!r} "
        f"exception={result.exception!r}"
    )
    assert regen_output.exists(), "regen --output file was not written"

    post_hash = hashlib.sha256(override_copy.read_bytes()).hexdigest()
    assert pre_hash == post_hash, (
        "Override file was modified by rosetta-shacl-gen — regen must only touch --output."
    )


# ---------------------------------------------------------------------------
# Test 4 — symlink-loop safety
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
    assert (ex.S, RDF.type, SH.NodeShape) in merged
    assert (ex.S, SH.targetClass, ex.T) in merged

    direct = rdflib.Graph()
    direct.parse(str(valid_ttl), format="turtle")
    assert len(merged) == len(direct), (
        f"Expected {len(direct)} triples (single parse), got {len(merged)} — "
        "symlink loop caused duplicate parses."
    )


# ---------------------------------------------------------------------------
# Test 5 — warn-and-merge on non-shape Turtle
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

    assert (ex.S, RDF.type, SH.NodeShape) in merged
    assert (ex.Foo, RDF.type, OWL.Class) in merged

    captured = capsys.readouterr()
    assert "ontology.ttl contains no SHACL shapes" in captured.err, (
        f"Expected warning for ontology.ttl in stderr; got: {captured.err!r}"
    )


# ---------------------------------------------------------------------------
# Test 6 — malformed Turtle surfaces a file-scoped error
# ---------------------------------------------------------------------------


def test_shapes_loader_surfaces_file_path_on_malformed_turtle(tmp_path: Path) -> None:
    """A syntactically broken ``.ttl`` file must raise ``ValueError`` naming the
    offending path."""
    (tmp_path / "valid.ttl").write_text(
        "@prefix sh: <http://www.w3.org/ns/shacl#> .\n"
        "@prefix ex: <http://example.org/> .\n"
        "ex:S a sh:NodeShape ; sh:targetClass ex:T .\n",
        encoding="utf-8",
    )
    bad = tmp_path / "broken.ttl"
    bad.write_text("@prefix ex: <http://example.org/> .\nex:S a ;;;\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"Failed to parse shapes file .*broken\.ttl"):
        load_shapes_from_dir(tmp_path)


def test_shapes_loader_rejects_non_directory(tmp_path: Path) -> None:
    """``load_shapes_from_dir`` must raise ``ValueError`` when pointed at a
    non-directory path."""
    missing = tmp_path / "does-not-exist"
    with pytest.raises(ValueError, match="not a directory"):
        load_shapes_from_dir(missing)

    as_file = tmp_path / "i-am-a-file.ttl"
    as_file.write_text("# not a dir\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not a directory"):
        load_shapes_from_dir(as_file)
