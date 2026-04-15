"""Shared pytest fixtures for the Rosetta CLI test suite."""

from __future__ import annotations

from pathlib import Path

import pytest
from rdflib import Graph

from rosetta.core.rdf_utils import ROSE_NS, bind_namespaces


@pytest.fixture()
def tmp_graph() -> Graph:
    """Return a fresh rdflib Graph with Rosetta namespaces bound."""
    g = Graph()
    bind_namespaces(g)
    return g


@pytest.fixture()
def sample_ttl(tmp_path: Path) -> Path:
    """Write a small Turtle file using ROSE_NS and return its Path."""
    ttl_content = f"""@prefix rose: <{ROSE_NS}> .

rose:SampleField a rose:Field ;
    rose:label "Sample Field" .
"""
    out = tmp_path / "sample.ttl"
    out.write_text(ttl_content, encoding="utf-8")
    return out


@pytest.fixture()
def tmp_rosetta_toml(tmp_path: Path) -> Path:
    """Write a minimal rosetta.toml with [accredit].log pointing to a temp file."""
    log_path = tmp_path / "audit-log.sssom.tsv"
    config = tmp_path / "rosetta.toml"
    config.write_text(f'[accredit]\nlog = "{log_path}"\n')
    return config


@pytest.fixture()
def config_dir(tmp_path: Path) -> Path:
    """Write a minimal rosetta.toml to tmp_path and return the directory."""
    toml_content = """\
[ingest]
default_format = "turtle"

[embed]
model = "sentence-transformers/LaBSE"
"""
    (tmp_path / "rosetta.toml").write_text(toml_content, encoding="utf-8")
    return tmp_path
