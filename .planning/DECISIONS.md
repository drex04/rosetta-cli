# Decisions

## 2026-04-12: Python + uv as package manager

**Decision:** Use Python with uv (not pip/poetry) as the package manager.
**Why:** uv is fast, modern, handles Python version management, and has excellent lockfile support. Preferred by user.
**Impact:** All install/run commands use `uv run`, `uv add`, `uv sync`.

## 2026-04-12: Local-first file-based storage (no triple store)

**Decision:** Use directories of `.ttl` files as the RDF store for MVP.
**Why:** Sufficient for the scale of Milestones 1–3; same RDF format means migration to Fuseki/GraphDB is trivial by changing config — tool interfaces don't change.
**Impact:** No SPARQL endpoint required for MVP.

## 2026-04-12: Lexical-only embeddings for MVP

**Decision:** Start with LaBSE lexical embeddings; defer GCN structural embeddings to Milestone 4.
**Why:** Proves the pipeline works before investing in GCN complexity. `--mode lexical-only` flag makes this explicit.
**Impact:** rosetta-embed supports `--mode` flag; `full` mode deferred.

## 2026-04-12: Defer UI entirely

**Decision:** No web UI or REST API in v1.
**Why:** Not needed to prove core logic works. "User interface" for Phase 1 is the terminal.
**Impact:** All tools are CLI-only; composable via shell pipes and scripts.

# Phase 6 Autonomous Decisions

Decisions made without human review. Promote to `.planning/DECISIONS.md` after phase completion.

---

## D06-01: Decisions input format

**Decision:** `--decisions` accepts a JSON file keyed by source field URI. Each value is `{target_uri, field_ref?, fnml_function?, multiplier?, offset?}`. `field_ref` defaults to the last path segment of the source URI when omitted.

**Why:** The suggest output already uses source URIs as keys. This format is a natural superset — a user can take the top-1 suggestion and add FnML params without inventing a new schema. Keeps the pipeline composable.

---

## D06-02: RML generation via rdflib graph (not template strings)

**Decision:** Use `rdflib.Graph` with blank nodes for all RML structures. Serialize to Turtle via `g.serialize(format="turtle")`. Do not use f-string Turtle templates.

**Why:** Template strings break on special characters in URIs/literals. rdflib handles escaping correctly and produces valid, parseable output that's testable with SPARQL.

---

## D06-03: Source reference formulation determined by `--source-format`

**Decision:** `--source-format json` → `ql:JSONPath`, `csv` → `ql:CSV`. The field reference for JSON uses `$.fieldname` JSONPath syntax; for CSV uses the bare column name.

**Why:** RMLMapper distinguishes these at execution time. Two formats cover all three ingest formats (OpenAPI → JSON at runtime).

---

## D06-04: FnML parameter predicates use `rose:fn/param/` namespace

**Decision:** Function parameters use predicates `<http://rosetta.interop/fn/param/value>`, `<http://rosetta.interop/fn/param/multiplier>`, `<http://rosetta.interop/fn/param/offset>`. The `fno:executes` predicate points to the function URI.

**Why:** Keeps function parameters in the rosetta namespace (not FNO) so they are self-documenting. FNO is only used for the `fno:executes` triple, which is the standard FnML pattern.

---

## D06-05: `--from-suggest` convenience flag

**Decision:** Implement a `--from-suggest <suggest_json> [--lint <lint_json>]` mode that auto-builds decisions by taking top-1 suggestion per source URI and enriching with `fnml_suggestion` from lint when the source URI appears in both files.

**Why:** Most users won't hand-author decisions. This closes the pipeline: `ingest → embed → suggest → lint → rml-gen` without requiring a manual decisions authoring step.

# Pending Decisions — Phase 7: rosetta-provenance

Autonomous decisions made during planning (auto_advance=true). Review before merging to DECISIONS.md.

---

## D7-01: In-place graph augmentation (no sidecar)

**Decision:** `rosetta-provenance stamp` reads an existing Turtle artifact, adds PROV-O triples directly into the same graph, and writes the augmented graph back to the output path (or stdout). No separate `.prov.ttl` sidecar file.

**Rationale:** Keeps artifacts self-contained and maximizes Unix composability. A sidecar requires both files to travel together; augmenting in-place means any downstream tool (`rosetta-validate`, `rosetta-accredit`) can inspect provenance by loading a single file. Consistent with how `rosetta-ingest` outputs a single Turtle with `rose:stats` annotations co-located.

**Alternative rejected:** Sidecar `.prov.ttl` — avoids modifying source artifacts but breaks single-file pipelines and requires every downstream tool to merge two graphs.

---

## D7-02: Activity URI uses UUID, Agent URI defaults to rosetta-cli

**Decision:** Each `stamp` invocation generates a UUID-based activity URI: `rose:activity/{uuid4}`. The default agent URI is `rose:agent/rosetta-cli`. Users can override via `--agent <uri>`.

**Rationale:** UUIDs ensure uniqueness across runs without a central registry. The default agent covers the typical automated-pipeline case. Named override lets humans record their identity in manual review workflows.

---

## D7-03: Version tracked as rose:version integer literal

**Decision:** Each stamped artifact carries `<artifact_uri> rose:version <N>^^xsd:integer`. On each stamp, the core library reads the current maximum version (0 if absent), increments by 1, and writes the new value, replacing the old triple.

**Rationale:** Simple integer versioning is grep-friendly and sortable. Avoids the complexity of semver or timestamp-only versioning. The SPARQL MAX aggregate handles missing-version bootstrap cleanly.

**Alternative rejected:** Timestamp-only versioning — not human-countable, harder to assert in tests.

---

## D7-04: --query prints human-readable text; --format json emits ProvenanceRecord model

**Decision:** The `query` subcommand defaults to plain-text output (one line per stamp event). Adding `--format json` emits a JSON array of `ProvenanceRecord` Pydantic objects. No separate `--query` flag on the `stamp` subcommand.

**Rationale:** Separating `stamp` and `query` as subcommands (Click group) is cleaner than a `--query` flag on a single command. Matches the `rosetta-accredit submit/approve/status` pattern already planned for Phase 9.

---

## D7-05: PROV-O triples written: Activity + Entity + Agent relationships

**Decision:** Each stamp writes the following minimal PROV-O triple set:

```turtle
<activity>  a prov:Activity ;
            prov:startedAtTime  "<ISO8601>"^^xsd:dateTime ;
            prov:endedAtTime    "<ISO8601>"^^xsd:dateTime ;
            prov:wasAssociatedWith <agent> ;
            rdfs:label "<label>" .

<artifact>  a prov:Entity ;
            prov:wasGeneratedBy <activity> ;
            rose:version <N>^^xsd:integer .

<agent>     a prov:Agent .
```

**Rationale:** This is the minimal PROV-O core that satisfies REQ-18 (stamp) and REQ-19 (query). Full PROV-O (plans, bundles, collections) is out of scope for this phase.

# Phase 8 Autonomous Decisions

## D1 — Shapes source: --shapes and --shapes-dir are additive, not mutually exclusive

**Decision:** Both flags may be provided simultaneously; their graphs are merged. At least
one must be present (UsageError otherwise).

**Rationale:** Composable — a caller can supply a base shapes file plus a directory of
supplementary shapes without invoking the tool twice. Matches Unix composability intent.

---

## D2 — SHACL result parsing via SPARQL on results_graph (not results_text)

**Decision:** Parse `results_graph` returned by pySHACL using a SPARQL SELECT rather than
parsing the text report string.

**Rationale:** Text report format is not guaranteed stable across pySHACL versions.
`results_graph` is the normative RDF output and structurally matches the SHACL spec.

---

## D3 — Severity vocabulary: strip sh: prefix, use "Violation"/"Warning"/"Info"

**Decision:** `ValidationFinding.severity` is a `Literal["Violation", "Warning", "Info"]`
with the `sh:` IRI prefix stripped.

**Rationale:** Consistent with how rosetta-lint uses `"BLOCK"/"WARNING"/"INFO"` — plain
strings, not full IRIs. Avoids leaking namespace URIs into user-facing JSON.

---

## D4 — do_owl_imports=False, meta_shacl=False defaults

**Decision:** pySHACL is invoked with `do_owl_imports=False` and `meta_shacl=False`.

**Rationale:** OWL imports require network access or local file resolution, which is fragile
in offline/air-gapped NATO environments. SHACL meta-validation adds overhead without benefit
at this stage. Both can be made configurable in a future phase if needed.

---

## D5 — Sample shapes constrain rose:Field (not RML/PROV-O artifacts)

**Decision:** `mapping.shacl.ttl` constrains `rose:Field` and `rose:Mapping` classes, which
are produced by rosetta-ingest (Phase 2) — the earliest, most stable artifact type.

**Rationale:** rosetta-rml-gen (Phase 6) and rosetta-provenance (Phase 7) outputs may not
yet exist when validate is first used. Testing against ingest output ensures the shapes file
is immediately useful without requiring the full pipeline to be run.

# Phase 9 Pending Decisions (auto-decided, pending DECISIONS.md promotion)

## D-09-01: Ledger file location and format

**Decision:** `store/ledger.json` — JSON object with a `"mappings"` array of entry objects.
**Why:** Consistent with local-first file-based storage decision (DECISIONS.md 2026-04-12). JSON is human-readable and composable; no SPARQL endpoint needed.
**Entry schema:** `{source_uri, target_uri, status, timestamp, actor, notes}` where `status ∈ {pending, accredited, revoked}`.
**Key:** `(source_uri, target_uri)` pair — no duplicate pairs allowed.

## D-09-02: State machine transitions

**Decision:** Two paths to revoked: `pending → accredited → revoked` (approve then withdraw) and `pending → revoked` (denial by accreditation authority). No resurrection from revoked.
- `submit` creates a `pending` entry (errors if pair already exists in any state)
- `approve` moves `pending → accredited` (errors on wrong state)
- `revoke` moves `pending → revoked` or `accredited → revoked` (errors only if already revoked)
- `status` prints current state for a given pair (or all pairs if no filter)
**Why:** Accreditation authorities need to deny submissions outright without first approving them. Denial and post-approval withdrawal land in the same terminal state — both mean the mapping must not be used. Resurrection paths add complexity without clear requirement.

## D-09-03: Feedback loop mechanism in rosetta-suggest

**Decision:** Add `--ledger` optional flag to `rosetta-suggest`. When provided:
- **Accredited** pairs: if `source_uri` matches a field in the source embeddings and `target_uri` is a candidate, multiply its raw cosine score by `1.2` (boost factor), capped at `1.0`.
- **Revoked** pairs: remove `(source_uri, target_uri)` from the candidate list entirely before ranking.
- Boost factor `1.2` is hardcoded; future phases may expose it as config.
**Why:** Simple multiplicative boost is transparent and easy to test. Exclusion of revoked is categorical — no score is appropriate for a revoked mapping.

## D-09-04: Accredit CLI structure

**Decision:** Use Click group (`@click.group`) with four subcommands: `submit`, `approve`, `revoke`, `status`.
- Top-level group accepts `--ledger` (path, default: `store/ledger.json`) and `--config` flags.
- Each subcommand accepts `--source` and `--target` URIs (plus `--actor` for submit).
- `status` additionally accepts `--all` flag to list all entries.
**Why:** Click groups are idiomatic for multi-verb CLIs; matches pattern established by rosetta-validate and rosetta-provenance.

## D-09-05: Integration test approach

**Decision:** Single pytest integration test in `rosetta/tests/test_accredit_integration.py` that:
1. Creates a temp ledger, submits NOR→master mapping pair
2. Approves it; runs suggest with `--ledger` → asserts boosted score ≥ original
3. Revokes it; runs suggest with `--ledger` → asserts pair absent from results
**Why:** Directly validates the Milestone 3 test described in ROADMAP.md. Uses existing synthetic NOR fixtures rather than embedding model calls (mock embeddings with pre-known cosine scores).

# Phase 9 Plan 02 Review Decisions (plan-review Step B, 2026-04-13)

## D-09-R01: TYPE_CHECKING import for Ledger in similarity.py

**Decision:** Import `Ledger` under `TYPE_CHECKING` only — not as a forward-ref string, not via a local import inside the function body.
**Why:** basedpyright strict mode on `rosetta/core/` cannot resolve a forward-ref string `"Ledger"` that has no corresponding module-level import. `models.py` does not import from `similarity.py`, so a `TYPE_CHECKING` guard carries zero circular-import risk.
**Confidence:** HIGH (plan-review Step B)

## D-09-R02: Preserve all candidate dict keys in accredited branch

**Decision:** Use `{**c, "score": min(c["score"] * boost_factor, 1.0)}` in the accredited branch of `apply_ledger_feedback`, not `{"uri": target, "score": ...}`.
**Why:** `rank_suggestions` returns suggestions with three keys (`uri`, `score`, `rank`). The narrow dict drops `rank`, producing a mixed-shape list where accredited items lack `rank`. The spread pattern preserves all keys and only overrides `score`.
**Confidence:** HIGH (plan-review Step B)

## D-09-R03: Re-sort and re-rank after apply_ledger_feedback

**Decision:** After calling `apply_ledger_feedback` in `suggest.py`, immediately re-sort the suggestions list by score descending and re-assign 1-based `rank` values.
**Why:** Boosted items may overtake higher-ranked items; without re-sorting the output order misrepresents the new ranking. The `rank` values from `rank_suggestions` are stale after score mutation.
**Confidence:** HIGH (plan-review Step B)

### D-001: Speculative plan validated: phase 6
- **Category:** implementation
- **Status:** ACTIVE
- **Confidence:** HIGH
- **Context:** No file overlap with predecessor phases (none)
- **Decision:** Plan proceeds as-is (VALID)
- **Affects:** Phase 6

### D-002: Speculative plan validated: phase 6
- **Category:** implementation
- **Status:** ACTIVE
- **Confidence:** HIGH
- **Context:** No file overlap with predecessor phases (none)
- **Decision:** Plan proceeds as-is (VALID)
- **Affects:** Phase 6

### D-003: Speculative plan validated: phase 7
- **Category:** implementation
- **Status:** ACTIVE
- **Confidence:** HIGH
- **Context:** No file overlap with predecessor phases (6)
- **Decision:** Plan proceeds as-is (VALID)
- **Affects:** Phase 7

### D-004: Speculative plan validated: phase 8
- **Category:** implementation
- **Status:** ACTIVE
- **Confidence:** HIGH
- **Context:** No file overlap with predecessor phases (6, 7)
- **Decision:** Plan proceeds as-is (VALID)
- **Affects:** Phase 8

### D-005: Speculative plan validated: phase 9
- **Category:** implementation
- **Status:** ACTIVE
- **Confidence:** HIGH
- **Context:** No file overlap with predecessor phases (6, 7, 8)
- **Decision:** Plan proceeds as-is (VALID)
- **Affects:** Phase 9

### D-006: Speculative plan validated: phase 10
- **Category:** implementation
- **Status:** ACTIVE
- **Confidence:** HIGH
- **Context:** No file overlap with predecessor phases (6, 7, 8, 9)
- **Decision:** Plan proceeds as-is (VALID)
- **Affects:** Phase 10

### D-007: Speculative plan validated: phase 11
- **Category:** implementation
- **Status:** ACTIVE
- **Confidence:** HIGH
- **Context:** No file overlap with predecessor phases (6, 7, 8, 9, 10)
- **Decision:** Plan proceeds as-is (VALID)
- **Affects:** Phase 11
