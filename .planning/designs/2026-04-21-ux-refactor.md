# UX Refactor Design — CLI Standardization

**Date:** 2026-04-21
**Phase:** 20 (UX Refactor)
**Status:** Approved

## Principles

- Unix philosophy: do one thing well, compose via pipes
- Text streams as universal interface (stdin/stdout/stderr)
- Positional args for primary pipeline data, named flags for reference context
- Consistent option names across all commands
- Config hierarchy: flags > env vars > config file > defaults
- Fail loudly, fail early
- Exit codes: 0 success, 1 operational failure, 2 usage error (Click default)

## Command Surface

### Single-input pipeline stages

```bash
rosetta ingest <schema-file> [-o output.yaml] [--schema-format ...]
rosetta translate <schema.yaml> [-o output.yaml] [--source-lang ...]
rosetta embed <schema.yaml> [-o embeddings.json] [--model ...] [--include-*]
rosetta shacl-gen <master.yaml> [-o shapes.ttl] [--open]
```

### Multi-input stages

```bash
rosetta suggest <source.json> <master.json> --audit-log <log.tsv> [-o mappings.sssom.tsv]
rosetta lint <sssom.tsv> --audit-log <log.tsv> --source-schema <s.yaml> --master-schema <m.yaml> [-o report.json] [--strict]
rosetta compile <sssom.tsv> --source-schema <s.yaml> --master-schema <m.yaml> [-o mapping.yarrrml.yml]
rosetta run <mapping.yarrrml.yml> <source-file> [-o output.jsonld] [--validate <shapes-dir>]
rosetta validate <data.jsonld> <shapes-dir> [-o report]
```

### Governance

```bash
rosetta accredit append <sssom-file> [--audit-log <log.tsv>]
rosetta accredit review [--audit-log <log.tsv>] [-o ...]
rosetta accredit dump [--audit-log <log.tsv>] [-o ...]
```

### Universal flags (every command)

- `-o` / `--output` — output path (default: stdout)
- `-c` / `--config` — rosetta.toml path
- `-v` / `--verbose` — increase verbosity (stderr)
- `-q` / `--quiet` — suppress non-essential output
- `--help` — command help with examples
- `--version` — version from pyproject.toml

## Breaking Changes from Current State

| Change | Rationale |
|--------|-----------|
| All `rosetta-*` hyphenated entry points dropped | Single `rosetta` parent group; no backward compat needed |
| `rosetta-provenance` deleted entirely | Not needed |
| `accredit status` subcommand deleted | Not needed |
| `accredit ingest` renamed to `accredit append` | Avoids collision with top-level `rosetta ingest` |
| `--log` on accredit renamed to `--audit-log` | Consistent with suggest/lint |
| `rosetta-yarrrml-gen` split into `compile` + `run` | Single-responsibility; compose via pipes |
| `--input` flags everywhere become positional args | Required data should be positional |
| `--schema-name` deleted from ingest | Always use filename stem |
| `--format` on ingest renamed to `--schema-format` | Disambiguate from output format |
| `--data-format` removed from validate | JSON-LD only |
| `--data` on run becomes positional arg | Required data should be positional |
| shapes-dir on validate becomes positional arg | Always required |
| `--sssom` on lint becomes positional arg | Primary input should be positional |
| audit log required on suggest, lint | Always needed for filtering/checking |
| source-schema + master-schema required on lint | Always needed for structural checks |
| `-o`/`--output` default stdout on ingest, translate | Were required file-only; now consistent |
| `--validate` on run takes shapes-dir path directly | Replaces `--validate` + `--shapes-dir` pair |

## Option Migration from yarrrml-gen

| Current yarrrml-gen flag | New location | Notes |
|--------------------------|-------------|-------|
| `--sssom` | `compile` positional | Primary input |
| `--source-schema` | `compile --source-schema` | Required flag |
| `--master-schema` | `compile --master-schema` | Required flag |
| `--source-format` | **deleted** | Always read from schema annotation `rosetta_source_format` |
| `--output` | `compile -o` | YARRRML (.yarrrml.yml) — the executable artifact `run` consumes |
| `--coverage-report` | `compile --coverage-report` | Optional |
| `--include-manual` | **deleted** | HC-only is the correct default; undocumented flag |
| `--allow-empty` | **deleted** | Empty spec is always an error |
| `--force` | **deleted** | Unresolvable CURIEs should always fail loudly |
| `--run` | deleted | Separate `rosetta run` command |
| `--data` | `run` positional | Source data file |
| `--jsonld-output` | `run -o` | Default stdout |
| `--workdir` | `run --workdir` | Optional |
| `--context-output` | `run --context-output` | Optional |
| `--validate` | `run --validate <shapes-dir>` | Combined flag+path |
| `--shapes-dir` | `run --validate` absorbs this | Merged |
| `--validate-report` | `run --validate-report` | Optional |

## Scope Decomposition (4 plans)

1. **Entry point unification** — Parent Click group, pyproject.toml, `rosetta <cmd>` structure
2. **Command cleanup** — Delete provenance, remove accredit status, rename accredit ingest→append, split yarrrml-gen into compile+run
3. **Option standardization** — Positional args, universal flags, audit-log required, schema flags required, --schema-format rename, --data-format removal
4. **Pipeline citizenship & docs** — SIGPIPE, TTY/NO_COLOR, help text examples, README, docs/, pipeline-demo.sh
