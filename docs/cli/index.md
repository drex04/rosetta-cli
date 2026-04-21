# CLI reference

Every command is auto-documented from its Click definition — options, arguments, help text, and command tree are pulled from the source. If the `--help` output drifts, the docs drift with it.

## The tools

| Tool | Purpose |
|------|---------|
| [`rosetta-ingest`](ingest.md) | Parse a source schema → emit LinkML YAML |
| [`rosetta-translate`](translate.md) | Normalise non-English titles via DeepL |
| [`rosetta-embed`](embed.md) | Compute per-slot sentence embeddings |
| [`rosetta-suggest`](suggest.md) | Rank candidate mappings by cosine similarity |
| [`rosetta-lint`](lint.md) | Validate analyst proposals against unit and log constraints |
| [`rosetta-accredit`](accredit.md) | Manage the two-role accreditation state machine |
| [`rosetta-validate`](validate.md) | SHACL-validate RDF data (Turtle or JSON-LD) |
| [`rosetta compile`](compile.md) | Compile approved mappings to YARRRML |
| [`rosetta run`](run.md) | Materialise a YARRRML mapping into JSON-LD |

## Conventions

All commands follow the same contract:

- **Input** — read from a file path (`--input`), a positional argument, or stdin where sensible.
- **Output** — write to `--output` (or `-o`), or stdout if omitted.
- **Exit codes** — `0` success/conformant, `1` error/violation, `2` Click validation error.
- **Config** — every default is overridable via `rosetta.toml` or `ROSETTA_<SECTION>_<KEY>` env vars, with CLI flags winning. See [Configuration](../configuration.md).
- **Formats** — RDF as Turtle (`.ttl`) for humans, N-Triples for machines; mappings as [SSSOM](https://mapping-commons.github.io/sssom/) TSV; schemas as [LinkML](https://linkml.io/) YAML.

The per-tool pages below render straight from the source — the option tables, flag semantics, and help strings you see are the same ones `--help` prints.
