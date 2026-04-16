# CURIE Merge Scope: Truth #12 Gap Analysis

**Date:** 2026-04-16
**Author:** scoping review (post-16-01 ship)

## Context

The 16-01 spec diagram shows `curies.Converter` being built from a three-way merge
(source schema prefixes + master schema prefixes + `rosetta.toml [prefixes]`), and
`build_converter()` is listed in the spec's component table. What shipped instead is
`_local_name()` stripping the colon-delimited prefix and calling
`SchemaView.get_class(bare_name, strict=False)`. This works because
`SchemaView.all_classes()` keys on the element's bare `name` field — confirmed by
inspecting the source: `c = self.all_classes(imports=imports).get(class_name, None)`.
The `curies` dep is declared but `build_converter()` was never written. Two additional
findings sharpen the scope:

1. **`rosetta.toml` has no `[prefixes]` section today.** The third leg of the merge
   is entirely hypothetical at the current fixture level.
2. **The CONTEXT.md locked decision ("schema-as-registry") explicitly documents that
   prefix authority lives in the LinkML schemas and SSSOM `curie_map` is
   informational only.** The three-way merge is architecturally correct but the
   `curies.Converter` is only needed when emitting IRIs into RML/YARRRML output —
   that is precisely 16-02's job.

## Option A — Lock merge as 16-02 prerequisite

16-01 stands; truth #12 is downgraded to "bare-name resolution in 16-01; three-way
merge in 16-02." `YarrrmlCompiler` (16-02) will need full IRI expansion to write
RML `rr:predicateObjectMap` references — that is the first point where a
`curies.Converter` is load-bearing. Doing the merge there is not a deferral for
convenience; it is the correct seam. **Con:** the spec component table (`build_converter`)
goes unimplemented in the plan that declared it, creating a permanent divergence note.

## Option B — Scope a small Plan 16-01b

Add `build_curie_converter()` to `transform_builder.py`, thread it through
`classify_row`'s context object (replacing the bare-name strip), and record the
`curies.Converter` on `BuildContext`. Estimated 4–6 tasks, ~1 day. **Con:** the
converter is built but never used to expand anything in 16-01's output (YAML
transformer spec uses bare names throughout); this is plumbing work whose correctness
cannot be exercised until 16-02. It also risks introducing a regression surface right
before 16-02 brainstorm.

## Option C — Amend SUMMARY + CONTEXT with deferral note

Zero code. Document in `16-01-SUMMARY.md` that bare-name resolution is a deliberate
tactical choice consistent with the schema-as-registry decision, and add a line to
CONTEXT.md locked decisions pinning `build_converter()` as a 16-02 prerequisite.
**Con:** truth #12 remains technically partial and a future reviewer will still see it.

## Recommendation: Option C, with a 16-02 prerequisite pinned in CONTEXT.md

The evidence supports Option C as the lowest-risk path:

- `SchemaView.get_class` keys on bare names by design; the bare-name strip is
  correct behavior, not a hack.
- The locked "schema-as-registry" decision already implies that full IRI expansion
  is not needed until IRIs appear in output — which is 16-02.
- `rosetta.toml` has no `[prefixes]` to merge today, so Option B would test against
  an empty third leg.
- `build_converter()` is genuinely needed at the point `YarrrmlCompiler` writes
  `rr:class` / `rr:predicate` IRI values; scoping it there makes the dependency
  explicit rather than speculative.

**Concrete next step:** Before 16-02 brainstorm opens, amend
`.planning/phases/16-rml-gen-v2/CONTEXT.md` under "Locked decisions" with:

> `build_converter()` (three-way prefix merge using `curies.Converter`) is a
> **16-02 prerequisite**. `transform_builder` uses bare-name resolution
> (`_local_name()`) because `SchemaView.get_class` keys on element names, not IRIs.
> Full IRI expansion is deferred to `YarrrmlCompiler`, which is the first component
> that emits IRI-valued RML fields.

Also update `16-01-SUMMARY.md` truth #12 status from PARTIAL to DEFERRED with the
same rationale. No code change is required.
