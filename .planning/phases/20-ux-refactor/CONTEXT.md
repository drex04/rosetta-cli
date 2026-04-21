# Phase 20: UX Refactor — Locked Decisions

## D-20-01: Entry point structure
**Decision:** Single `rosetta` parent Click group. All hyphenated entry points (`rosetta-ingest`, etc.) dropped immediately. No backward compatibility aliases.
**Rationale:** Internal tool, no external users.

## D-20-02: yarrrml-gen split
**Decision:** `rosetta-yarrrml-gen` splits into `rosetta compile` (SSSOM → TransformSpec → YARRRML) and `rosetta run` (YARRRML + data → JSON-LD). `rosetta validate` remains unchanged for standalone validation.
**Rationale:** Single-responsibility; compile/run is intuitive to developers.

## D-20-03: Provenance deletion
**Decision:** Delete `rosetta-provenance` entirely (cli, core, tests, docs). No replacement.
**Rationale:** User decision — not needed.

## D-20-04: Accredit status deletion
**Decision:** Remove `accredit status` subcommand and `StatusEntry` Pydantic model.
**Rationale:** User decision — not needed.

## D-20-05: Accredit ingest rename
**Decision:** `accredit ingest` → `accredit append`. Avoids name collision with top-level `rosetta ingest`.

## D-20-06: Input convention
**Decision:** Required primary inputs are positional args. Reference/context data uses required named flags (e.g., `--source-schema`, `--master-schema`, `--audit-log`).
**Rationale:** Positional for pipeline data, named flags for disambiguation.

## D-20-07: Output convention
**Decision:** All commands use `-o`/`--output` defaulting to stdout. `ingest` and `translate` lose their required-file-only output.

## D-20-08: Universal flags
**Decision:** Every command inherits from parent group: `-o`/`--output`, `-c`/`--config`, `-v`/`--verbose`, `-q`/`--quiet`, `--help`, `--version`.
- `--verbose`: adds progress info to stderr
- `--quiet`: suppresses everything except errors on stderr

## D-20-09: Audit log required
**Decision:** `suggest` and `lint` require `--audit-log` flag (overridable via config hierarchy). Not optional/silently-skipped.

## D-20-10: Lint requires schemas
**Decision:** `lint` requires both `--source-schema` and `--master-schema` (currently optional).

## D-20-11: Flag renames/removals
- `--format` on ingest → `--schema-format`
- `--schema-name` on ingest → deleted (use filename stem)
- `--data-format` on validate → deleted (JSON-LD only)
- `--log` on accredit → `--audit-log`
- `--include-manual` on yarrrml-gen → deleted (HC-only default)
- `--allow-empty` on yarrrml-gen → deleted (empty spec is error)
- `--force` on yarrrml-gen → deleted (unresolvable CURIEs always fail)
- `--source-format` on yarrrml-gen → deleted (read from schema annotation)

## D-20-12: Validate simplification
**Decision:** `rosetta validate` accepts JSON-LD only. `--data-format` option removed. Shapes-dir becomes positional arg.

## D-20-13: Run --validate combined flag
**Decision:** `rosetta run --validate <shapes-dir>` replaces the `--validate` + `--shapes-dir` pair.

## D-20-14: stdin/stdout `-` convention
**Decision:** Deferred to future plan. Not in scope for Phase 20.

## D-20-15: --dry-run
**Decision:** Deferred. Not in scope for Phase 20.

---

## Review Decisions (2026-04-21)

## [review] D-20-16: compile output format
**Decision:** `rosetta compile -o` outputs YARRRML (the executable artifact `run` consumes), not TransformSpec YAML. Optional `--spec-output` writes the intermediate TransformSpec.
**Rationale:** Design doc originally said TransformSpec; plan body said YARRRML. Resolved in favor of YARRRML since that's what `run` needs.

## [review] D-20-17: Lazy imports in parent group
**Decision:** Use lazy imports via `importlib.import_module` deferral for all subcommands. Each subcommand module is imported only when invoked.
**Rationale:** Eager imports add ~1-2s startup for heavy deps (sentence-transformers, morph-kgc, linkml). Unacceptable for a CLI tool.

## [review] D-20-18: pipeline-demo.sh breakage window
**Decision:** Plan 20-01 includes a holding fix (mechanical `rosetta-*` → `rosetta *` rename). Full flag updates in Plan 20-04.

## [review] D-20-19: --audit-log path validation
**Decision:** Use `click.Path()` (no `exists=True`). Manual validation with clear error message pointing to `rosetta accredit append`.

## [review] D-20-20: Stale --force error messages
**Decision:** Update `transform_builder.py` error messages referencing `--force` as part of Plan 20-02.

## [review] D-20-21: SIGPIPE implementation
**Decision:** Use `BrokenPipeError` try/except wrapper (portable) rather than `signal.SIGPIPE` (not available on Windows).

## D-20-22: Command renames (Plan 20-05)
**Decision:** Three renames: `accredit` → `ledger`, `run` → `transform`, `shacl-gen` → `shapes`. No backward-compat aliases.
**Rationale:** `accredit` is opaque — `ledger` matches the append-only audit log metaphor. `run` is too generic — `transform` says what it does (data → graph). `shacl-gen` is implementation-leaky — `shapes` says what it produces.

## D-20-23: Ledger subcommand names unchanged
**Decision:** `ledger append`, `ledger review`, `ledger dump` — subcommand names stay the same.
**Rationale:** All three read naturally under `ledger`. No reason to rename.

---

## Deferred Ideas

- **Verbose/quiet wiring into subcommands:** Flags accepted on parent group and stored in context, but no subcommand actually emits verbose output yet. Wire in a future plan.
- **`build_spec()` dead parameters:** `force` and `include_manual` parameters remain on the function signature with safe defaults. Remove in a future cleanup if vulture flags them.
