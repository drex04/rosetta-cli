# rosetta

**Map partner-nation schemas to a shared ontology — systematically, transparently, and with auditable human review.**

Defense coalitions speak in many tongues. Norwegian radar tracks, German Patriot telemetry, US C2 feeds — each schema has its own language, units, field names, and structure. `rosetta` is a composable Unix toolkit that takes heterogeneous partner schemas and produces a materialised, standards-compliant RDF knowledge graph aligned to a master ontology. Every step is a discrete tool you can script, pipe, inspect, and audit.

## Key capabilities

- **Ingest** schemas in seven formats (CSV, TSV, JSON Schema, OpenAPI, XSD, RDFS/OWL, JSON samples) and normalise to [LinkML](https://linkml.io/); optionally translate non-English labels via DeepL (`--translate --lang <code>`) and generate SHACL shapes from a master ontology (`--master`)
- **Suggest** candidate mappings ranked by cosine similarity, embedding schemas on-the-fly; filters out already-resolved subjects and suppresses individually rejected pairs
- **Record** every decision in an append-only [SSSOM](https://mapping-commons.github.io/sssom/) audit log via `ledger append`, with a built-in lint gate that checks unit dimensionality, datatype compatibility, and audit-log conflicts before writing
- **Compile** approved mappings into [YARRRML](https://rml.io/yarrrml/) and materialise JSON-LD via [morph-kgc](https://morph-kgc.readthedocs.io/)
- **Validate** the resulting RDF against [SHACL](https://www.w3.org/TR/shacl/) shapes — runs automatically inside `transform` (pass `--no-validate` to skip)

## Installation

```bash
uv sync
```

All tools are available via `uv run rosetta <command>` after syncing.

## Tools

| Command     | Purpose                                                      |
| ----------- | ------------------------------------------------------------ |
| `ingest`    | Parse one or more schemas → LinkML YAML; `--translate --lang <code>` for in-line DeepL translation; `--master <ontology>` to generate SHACL shapes |
| `suggest`   | Rank candidate mappings by similarity; embeds schemas on-the-fly (no pre-computed embedding files needed) |
| `ledger`    | Manage the append-only audit log: `append --role analyst\|accreditor` (with built-in lint gate), `review`, `dump` |
| `compile`   | Compile approved mappings from the audit log → YARRRML       |
| `transform` | Materialise YARRRML → JSON-LD; validates against SHACL by default (`--no-validate` to skip, `--shapes` for custom shapes) |

Run `uv run rosetta <command> --help` for options and usage.

## Pipeline

The standard 5-step workflow:

```bash
# 1. Ingest source schema (translate Norwegian → English) and master ontology
rosetta ingest nor_radar.csv --translate --lang NB -o output/nor_radar.linkml.yaml
rosetta ingest master.ttl --schema-format rdfs --master master.ttl -o output/master.linkml.yaml

# 2. Generate candidate mappings (embeds on-the-fly)
rosetta suggest output/nor_radar.linkml.yaml output/master.linkml.yaml \
  --audit-log output/audit-log.sssom.tsv -o output/candidates.sssom.tsv

# 3. Analyst edits candidates.sssom.tsv, then appends (lint gate runs automatically)
rosetta ledger --audit-log output/audit-log.sssom.tsv append \
  --role analyst output/candidates.sssom.tsv \
  --source-schema output/nor_radar.linkml.yaml \
  --master-schema output/master.linkml.yaml

# 4. Accreditor reviews and approves
rosetta ledger --audit-log output/audit-log.sssom.tsv review -o output/review.sssom.tsv
# (accreditor edits review.sssom.tsv)
rosetta ledger --audit-log output/audit-log.sssom.tsv append \
  --role accreditor output/review.sssom.tsv \
  --source-schema output/nor_radar.linkml.yaml \
  --master-schema output/master.linkml.yaml

# 5. Compile approved mappings and materialise JSON-LD (validates by default)
rosetta compile output/audit-log.sssom.tsv \
  --source-schema output/nor_radar.linkml.yaml --master-schema output/master.linkml.yaml \
  -o output/mapping.yarrrml.yaml
rosetta transform output/mapping.yarrrml.yaml source_data.json \
  --master-schema output/master.linkml.yaml -o output/result.jsonld
```

See `scripts/pipeline-demo.sh` for an interactive walkthrough with real fixtures.

## Migration from v1

| Old command | New equivalent |
| ----------- | -------------- |
| `rosetta translate` | `rosetta ingest --translate --lang <code>` |
| `rosetta embed` | Removed — `suggest` embeds internally |
| `rosetta lint` | `rosetta ledger append --dry-run` |
| `rosetta validate` | `rosetta transform` (validates by default) |
| `rosetta shapes` | `rosetta ingest --master <ontology>` |

## Documentation

Full documentation — CLI reference, pipeline walkthrough, accreditation guide, and configuration:

**[drex04.github.io/rosetta-cli](https://drex04.github.io/rosetta-cli/)**

## Running tests

```bash
uv run pytest                       # run all tests
```

## License

See [LICENSE](LICENSE).
