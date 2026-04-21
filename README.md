# rosetta-cli

**Map partner-nation schemas to a shared ontology — systematically, transparently, and with auditable human review.**

Defense coalitions speak in many tongues. Norwegian radar tracks, German Patriot telemetry, US C2 feeds — each schema has its own language, units, field names, and structure. `rosetta-cli` is a composable Unix toolkit that takes heterogeneous partner schemas and produces a materialised, standards-compliant RDF knowledge graph aligned to a master ontology. Every step is a discrete tool you can script, pipe, inspect, and audit.

## Key capabilities

- **Ingest** schemas in seven formats (CSV, TSV, JSON Schema, OpenAPI, XSD, RDFS/OWL, JSON samples) and normalise to [LinkML](https://linkml.io/)
- **Translate** non-English titles via DeepL so multilingual schemas embed in a common semantic space
- **Embed** every class and slot with multilingual sentence transformers, blending lexical and structural similarity
- **Suggest** candidate mappings ranked by cosine similarity, boosted by prior approvals and deranked by rejections
- **Lint** proposals against physical-unit dimensionality, datatype compatibility, and audit-log conflicts
- **Record** every decision in an append-only [SSSOM](https://mapping-commons.github.io/sssom/) audit log
- **Compile** approved mappings into [YARRRML](https://rml.io/yarrrml/) and materialise JSON-LD via [morph-kgc](https://morph-kgc.readthedocs.io/)
- **Validate** the resulting RDF against [SHACL](https://www.w3.org/TR/shacl/) shapes

## Installation

```bash
uv sync
```

All tools are available via `uv run rosetta <command>` after syncing.

## Tools

| Command     | Purpose                                                      |
| ----------- | ------------------------------------------------------------ |
| `ingest`    | Parse a schema file → LinkML YAML                            |
| `translate` | Translate non-English titles to English via DeepL            |
| `embed`     | Compute embeddings for schema slots                          |
| `suggest`   | Rank candidate mappings by similarity                        |
| `lint`      | Validate proposals before accreditor review                  |
| `ledger`    | Manage the append-only audit log (append, review, dump)      |
| `compile`   | Compile approved mappings → YARRRML                          |
| `transform` | Materialise YARRRML → JSON-LD with optional SHACL validation |
| `validate`  | Validate RDF against SHACL shapes                            |
| `shapes`    | Auto-generate SHACL shapes from a master LinkML schema       |

Run `uv run rosetta <command> --help` for options and usage.

## Documentation

Full documentation — CLI reference, pipeline walkthrough, accreditation guide, and configuration:

**[drex04.github.io/rosetta-cli](https://drex04.github.io/rosetta-cli/)**

## Running tests

```bash
uv run pytest                       # run all tests
```

## License

See [LICENSE](LICENSE).
