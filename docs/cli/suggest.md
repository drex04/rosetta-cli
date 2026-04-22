# rosetta suggest

Compares source embeddings against master embeddings and ranks candidates by cosine similarity. Outputs [SSSOM](https://mapping-commons.github.io/sssom/) TSV. Requires an audit log (`--audit-log`) to filter out already-resolved subjects and suppress individually rejected pairs.

## Command reference

::: mkdocs-click
    :module: rosetta.cli.suggest
    :command: cli
    :prog_name: rosetta suggest
    :depth: 2

## Output — SSSOM TSV

Output is a 15-column SSSOM TSV with a YAML comment header:

```
# mapping_set_id: https://rosetta-cli/mappings
# mapping_tool: rosetta suggest
# license: https://creativecommons.org/licenses/by/4.0/
# curie_map:
#   skos: http://www.w3.org/2004/02/skos/core#
#   semapv: https://w3id.org/semapv/vocab/
subject_id	predicate_id	object_id	mapping_justification	confidence	...
http://rosetta.interop/ns/NOR/nor_radar/altitude_m	skos:relatedMatch	http://rosetta.interop/ns/master/altitude	semapv:LexicalMatching	0.94	Altitude M	Altitude	2026-04-16T00:00:00Z	<uuid>	xsd:float	xsd:float
```

| Column | Description |
|--------|-------------|
| `subject_id` | Source field URI |
| `predicate_id` | SKOS/OWL mapping predicate |
| `object_id` | Master ontology field URI |
| `mapping_justification` | SEMAPV justification CURIE |
| `confidence` | Cosine similarity score (0.0–1.0) |
| `subject_label` | Human-readable source field name |
| `object_label` | Human-readable target field name |
| `mapping_date` | ISO 8601 UTC timestamp (populated for audit-log rows; empty for fresh candidates) |
| `record_id` | UUID4 (populated for audit-log rows; empty for fresh candidates) |
| `subject_datatype` | XSD datatype of the source field, re-derived from the source LinkML schema |
| `object_datatype` | XSD datatype of the target field, re-derived from the master LinkML schema |
| `subject_type` | `"composed entity expression"` for composite mappings, else empty |
| `object_type` | `"composed entity expression"` for composite mappings, else empty |
| `mapping_group_id` | Shared identifier across rows composing one logical mapping |
| `composition_expr` | Python/GREL composition expression for 1:N or N:1 decomposition |

`mapping_date` and `record_id` are populated only for rows carried over from the audit log; they are empty for freshly computed candidates. `subject_datatype` and `object_datatype` are re-derived at suggest time from the source and master LinkML schemas — they are not stored in the audit log.

## Structural blending

When both embed files contain a `"structural"` array per node, `rosetta suggest` automatically blends lexical and structural cosine similarity. The blend weight is controlled by `--structural-weight` (default: `0.2`). Set it to `0.0` to disable blending. If either embed file lacks `"structural"` arrays, scoring falls back to lexical-only automatically.

When blending is active, `mapping_justification` is `semapv:CompositeMatching`; otherwise it is `semapv:LexicalMatching`.

## Audit-log filtering

`--audit-log` is required. `rosetta suggest` reads the log and applies two filtering rules before emitting candidates:

- **Approved mappings** — a `HumanCuration` row whose predicate is not `owl:differentFrom`. All suggestions for that subject are excluded from output. The subject is considered fully resolved.
- **Rejected mappings** — a `HumanCuration` row with `predicate_id = owl:differentFrom`. Only that specific (subject, object) pair is excluded; other candidates for the same subject are still shown.

If a subject has both approved and rejected `HumanCuration` rows in the log, approved wins — the subject is fully excluded.

Pending proposals (`ManualMappingCuration` rows, non-HC entries) are not filtered out; they appear in the output with freshly computed confidence values and updated metadata.

## Example

```bash
uv run rosetta suggest nor.emb.json master.emb.json \
  --audit-log audit.sssom.tsv \
  --output candidates.sssom.tsv
```

## Exit codes

- `0` — success.
- `1` — I/O error or malformed input.
