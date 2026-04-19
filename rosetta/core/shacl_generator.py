"""Rosetta SHACL generator — wrapper around ``linkml.generators.shaclgen.ShaclGenerator``.

Phase 19 / Plan 19-01 / Task 1 (D-19-11, D-19-14).

Spike outcome (D-19-14):
    The upstream ``ShaclGenerator`` is a ``@dataclass`` whose
    ``closed: bool = True`` field is settable directly via constructor.
    ``as_graph() -> rdflib.Graph`` is the most direct entry point —
    ``serialize()`` just wraps it. The generator already attaches an
    ``sh:ignoredProperties`` rdf:List to every NodeShape (containing
    child-class slot URIs + ``rdf:type``). Our prov/dcterms additions
    therefore fit cleanly as a single ``as_graph()`` post-walk: append
    items to the existing list (or rebuild a fresh ``Collection`` and
    rewire the ``sh:ignoredProperties`` predicate). No ``ShaclGenerator``
    behaviour needs to change beyond what the constructor already
    exposes, so a thin wrapper module is sufficient — no subclass.

    Settable via constructor (kwargs), confirmed:
        closed, suffix, include_annotations, exclude_imports,
        use_class_uri_names, expand_subproperty_of

    Requires post-walk on the returned ``rdflib.Graph``:
        - extending ``sh:ignoredProperties`` with prov/dcterms IRIs
        - emitting unit-aware ``sh:property`` blocks per slot

Public API:
    ``generate_shacl(linkml_path, *, closed=True) -> str``  (Turtle)
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from linkml.generators.shaclgen import ShaclGenerator
from linkml_runtime.utils.schemaview import SchemaView
from rdflib import BNode, Graph, Namespace, URIRef
from rdflib.collection import Collection
from rdflib.namespace import DCTERMS, RDF, SH

from rosetta.core.unit_detect import detect_unit

if TYPE_CHECKING:
    from linkml_runtime.linkml_model import SlotDefinition

PROV: Namespace = Namespace("http://www.w3.org/ns/prov#")
QUDT: Namespace = Namespace("http://qudt.org/schema/qudt/")
UNIT: Namespace = Namespace("http://qudt.org/vocab/unit/")

# Properties that are universally permitted on every closed-world shape:
# provenance metadata + ``rdf:type`` + ``qudt:hasUnit`` (optional unit-dimension
# marker emitted by the ``_emit_unit_shapes`` pass; must be whitelisted so
# ``sh:closed true`` does not reject data that declares its unit).
_BAKED_IN_IGNORED: tuple[URIRef, ...] = (
    PROV.wasGeneratedBy,
    PROV.wasAttributedTo,
    DCTERMS.created,
    DCTERMS.source,
    RDF.type,
    QUDT.hasUnit,
)


def _curie_to_unit_iri(curie: str) -> URIRef:
    """Expand a ``unit:XXX`` CURIE from ``detect_unit`` into a full QUDT URIRef.

    ``detect_unit`` always returns the ``unit:`` prefix form (e.g. ``"unit:M"``);
    we never ask it to resolve via a SchemaView, so we expand against the
    canonical QUDT namespace ourselves.
    """
    if ":" not in curie:
        raise ValueError(f"detect_unit returned non-CURIE value: {curie!r}")
    prefix, local = curie.split(":", 1)
    if prefix != "unit":
        raise ValueError(f"unexpected prefix in unit CURIE: {curie!r}")
    return UNIT[local]


def _rebuild_ignored_properties(g: Graph) -> None:
    """Append baked-in prov/dcterms IRIs to every ``sh:ignoredProperties`` list.

    The upstream generator builds an rdf:List Collection of child-class slot
    URIs + ``rdf:type``. We extend each list in place by collecting its current
    members, removing the old list triples, and writing a fresh Collection
    from the union (deduped). This is simpler — and easier to reason about —
    than splicing a new tail onto the existing rdf:List.
    """
    # Snapshot pairs first; we'll mutate the graph mid-iteration otherwise.
    pairs: list[tuple[URIRef | BNode, BNode]] = [
        (shape, list_head)
        for shape, _, list_head in g.triples((None, SH.ignoredProperties, None))
        if isinstance(shape, (URIRef, BNode)) and isinstance(list_head, BNode)
    ]

    for shape, list_head in pairs:
        existing = list(Collection(g, list_head))
        # Delete old list nodes (rdf:first / rdf:rest) and the predicate triple.
        _delete_rdf_list(g, list_head)
        g.remove((shape, SH.ignoredProperties, list_head))

        # Dedupe while preserving order: existing first, then any baked-ins
        # not already present.
        seen: set[URIRef] = set()
        merged: list[URIRef] = []
        for item in existing:
            if isinstance(item, URIRef) and item not in seen:
                seen.add(item)
                merged.append(item)
        for item in _BAKED_IN_IGNORED:
            if item not in seen:
                seen.add(item)
                merged.append(item)

        new_head = BNode()
        # Collection() needs list[Node]; merged.copy() narrows to list[URIRef].
        Collection(g, new_head, list(merged))  # noqa: FURB123
        g.add((shape, SH.ignoredProperties, new_head))


def _delete_rdf_list(g: Graph, head: BNode) -> None:
    """Remove all rdf:first / rdf:rest triples for the rdf:List rooted at ``head``."""
    node: URIRef | BNode = head
    while node != RDF.nil:
        # Capture rest before we delete the triples.
        rest_obj: Any = g.value(subject=node, predicate=RDF.rest)
        for triple in list(g.triples((node, None, None))):
            g.remove(triple)
        if not isinstance(rest_obj, (URIRef, BNode)):
            break
        node = rest_obj


def _collect_unit_iris(induced: list[SlotDefinition]) -> list[URIRef]:
    """Return the de-duplicated QUDT unit IRIs detected across a class's slots."""
    unit_iris: list[URIRef] = []
    seen: set[URIRef] = set()
    for slot in induced:
        slot_name = slot.name or ""
        if not slot_name:
            continue
        unit_curie = detect_unit(slot_name, slot.description or "")
        if unit_curie is None:
            continue
        unit_iri = _curie_to_unit_iri(unit_curie)
        if unit_iri in seen:
            continue
        seen.add(unit_iri)
        unit_iris.append(unit_iri)
    return unit_iris


def _attach_unit_in_shape(g: Graph, class_uri: URIRef, unit_iris: list[URIRef]) -> None:
    """Attach one ``sh:property [sh:path qudt:hasUnit ; sh:in (…)]`` to ``class_uri``."""
    prop_node = BNode()
    g.add((class_uri, SH.property, prop_node))
    g.add((prop_node, SH.path, QUDT.hasUnit))
    in_list_head = BNode()
    # Collection() needs list[Node]; unit_iris narrows to list[URIRef].
    Collection(g, in_list_head, list(unit_iris))  # noqa: FURB123
    g.add((prop_node, SH["in"], in_list_head))


def _emit_unit_shapes(g: Graph, sv: SchemaView) -> None:
    """For each class whose slots map to one or more QUDT units, attach a
    single ``sh:property`` block constraining ``qudt:hasUnit`` values to the
    set of detected unit IRIs (``sh:path qudt:hasUnit ; sh:in (unit:A unit:B …)``).

    Design rationale (Phase 19 follow-up):
        An earlier iteration emitted one ``sh:hasValue unit:X`` shape per
        unit-mapped slot on the same class. ``sh:hasValue`` requires the
        specific value to be present, so a class with several unit-mapped
        slots (e.g. AirTrack's Bearing/Speed/Altitude) received mutually
        unsatisfiable constraints (each demanding its own unit). Switching
        to a single deduplicated ``sh:in`` set means: "IF this instance
        declares ``qudt:hasUnit``, that unit must be one the schema
        recognises for this class" — vacuously true when no
        ``qudt:hasUnit`` triples exist, validation otherwise.

    Parent class shape IRI = the class_uri (same URI the upstream generator
    uses as both ``sh:targetClass`` and shape subject when
    ``use_class_uri_names=True``, which is the default).
    """
    all_classes_obj: Any = sv.all_classes(imports=False)
    for class_name in all_classes_obj:
        induced: list[SlotDefinition] = list(sv.class_induced_slots(str(class_name)))
        if not induced:
            continue
        class_def: Any = all_classes_obj[class_name]
        class_uri_str: Any = sv.get_uri(class_def, expand=True)
        if not class_uri_str:
            continue
        unit_iris = _collect_unit_iris(induced)
        if not unit_iris:
            continue
        _attach_unit_in_shape(g, URIRef(str(class_uri_str)), unit_iris)


def _strip_abstract_mixin_shapes(g: Graph, sv: SchemaView) -> None:
    """Remove NodeShape triples for ``abstract`` and ``mixin`` LinkML classes.

    Abstract/mixin classes exist for schema composition (inheritance and
    trait-reuse) and have no instantiable RDF individuals. A closed-world
    shape on them would cause spurious validation failures — every concrete
    subclass would inherit an unsatisfiable closed shape from its abstract
    parent. We therefore strip the direct shape triples (the orphan BNode
    property-shape subtrees under them are inert because pyshacl only walks
    reachable ``sh:NodeShape`` subjects).
    """
    all_classes_obj: Any = sv.all_classes(imports=False)
    for class_name in all_classes_obj:
        class_def: Any = all_classes_obj[class_name]
        if not (getattr(class_def, "abstract", False) or getattr(class_def, "mixin", False)):
            continue
        class_uri_str: Any = sv.get_uri(class_def, expand=True)
        if not class_uri_str:
            continue
        shape_subject = URIRef(str(class_uri_str))
        for triple in list(g.triples((shape_subject, None, None))):
            g.remove(triple)


def _bind_prefixes(g: Graph) -> None:
    g.bind("qudt", QUDT)
    g.bind("prov", PROV)
    g.bind("dcterms", DCTERMS)
    g.bind("unit", UNIT)


def generate_shacl(linkml_path: str | Path, *, closed: bool = True) -> str:
    """Generate Rosetta SHACL Turtle from a LinkML schema.

    Wraps ``linkml.generators.shaclgen.ShaclGenerator`` with two Rosetta-specific
    post-walk passes (D-19-10, D-19-11):

    * Closed-world default — ``sh:closed true`` (set via constructor) and
      ``sh:ignoredProperties`` extended to permit ``prov:wasGeneratedBy``,
      ``prov:wasAttributedTo``, ``dcterms:created``, ``dcterms:source``,
      ``rdf:type``. Pass ``closed=False`` to emit open-world shapes (no
      ignored-properties extension is performed in that mode — the upstream
      generator emits ``sh:closed false`` and our extension would be inert).
    * Unit-aware shapes — for every slot whose name/description ``detect_unit``
      maps to a QUDT unit IRI, attach a ``sh:property`` block of the form
      ``sh:path qudt:hasUnit ; sh:hasValue unit:XXX`` to the parent class shape.
    """
    schema_path = str(linkml_path)
    g: Graph = ShaclGenerator(schema_path, closed=closed).as_graph()

    sv = SchemaView(schema_path)
    # Strip abstract/mixin shapes BEFORE the ignored-properties rebuild so we
    # don't waste work extending lists we're about to delete.
    _strip_abstract_mixin_shapes(g, sv)

    if closed:
        _rebuild_ignored_properties(g)

    _emit_unit_shapes(g, sv)

    _bind_prefixes(g)
    serialized: Any = g.serialize(format="turtle")
    return str(serialized)
