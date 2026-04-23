#!/usr/bin/env bash
set -euo pipefail

# scripts/pipeline-demo.sh
#
# Interactive walkthrough of the full accreditation pipeline:
#   ingest → suggest
#   → [analyst edits candidates.sssom.tsv]
#   → ledger append (analyst proposals, with lint gate)
#   → ledger review
#   → [accreditor edits review.sssom.tsv]
#   → ledger append (accreditor decisions)
#   → compile (YARRRML mapping artifact)
#   → transform (JSON-LD materialization + SHACL validation)
#
# Usage: bash scripts/pipeline-demo.sh [OUTPUT_DIR]
#   OUTPUT_DIR  Directory for generated files (default: demo_out)
#
# Requirements:
#   uv sync            Install dependencies before running.
#   DEEPL_API_KEY      Only needed for non-English source schemas (--translate flag).
#
# The audit log is written to $OUTPUT_DIR/audit-log.sssom.tsv.
# Re-running the script will accumulate entries in the same log.

# ── Helpers ───────────────────────────────────────────────────────────────────

info() {
    echo ""
    echo "━━━  $*  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

ok() { echo "  ✓  $*"; }

run_cmd() {
    echo "  \$ $*"
    "$@"
}

box() {
    local title="$1"; shift
    echo ""
    echo "┌─────────────────────────────────────────────────────────────────────┐"
    printf "│  %s\n" "$title"
    echo "│"
    for line in "$@"; do
        printf "│  %s\n" "$line"
    done
    echo "└─────────────────────────────────────────────────────────────────────┘"
    echo ""
}

# Prompt until the user answers yes / skip / quit.
# Returns 0 for "yes", 1 for "skip", exits for "quit".
confirm() {
    local prompt="$1"
    while true; do
        printf "%s [yes/skip/quit]: " "$prompt"
        read -r reply
        case "$reply" in
            yes|y|Y)    return 0 ;;
            skip|s|S)   return 1 ;;
            quit|q|Q)   echo "Aborting."; exit 0 ;;
            *)          echo "  Type yes, skip, or quit." ;;
        esac
    done
}

# ── Config ────────────────────────────────────────────────────────────────────

OUT="${1:-demo_out}"
SRC_FIXTURE="rosetta/tests/fixtures/nations/nor_radar.csv"
MASTER_FIXTURE="rosetta/tests/fixtures/nations/master_cop_ontology.ttl"
LOG="$OUT/audit-log.sssom.tsv"

mkdir -p "$OUT"

echo ""
echo "Pipeline demo"
echo "  Output dir  : $OUT"
echo "  Audit log   : $LOG"

# ── Step 1: Ingest ────────────────────────────────────────────────────────────

info "Step 1 — Ingest schemas → LinkML YAML (with translation and master alignment)"

# Ingest source schema with translation, and process the master ontology
# (generates LinkML YAML + SHACL shapes for the master alongside the source).
# DEEPL_API_KEY must be set in the environment for --translate to work.
run_cmd uv run rosetta ingest \
    "$SRC_FIXTURE" \
    --translate --lang NB \
    --master "$MASTER_FIXTURE" \
    -o "$OUT/nor_radar.linkml.yaml"
ok "$OUT/nor_radar.linkml.yaml"
ok "$OUT/master_cop_ontology.linkml.yaml  (master schema)"
ok "$OUT/master_cop_ontology.shacl.ttl    (shapes from master ontology)"

# ── Step 2: Suggest ───────────────────────────────────────────────────────────

info "Step 2 — Generate mapping candidates"
echo "  (First run downloads the embedding model ~1.2 GB from HuggingFace; subsequent runs use cache)"

run_cmd uv run rosetta suggest \
    "$OUT/nor_radar.linkml.yaml" \
    "$OUT/master_cop_ontology.linkml.yaml" \
    --audit-log "$LOG" \
    -o "$OUT/candidates.sssom.tsv"
ok "$OUT/candidates.sssom.tsv"

# ── Pause: Analyst edits candidates ──────────────────────────────────────────

box "ANALYST STEP — Edit $OUT/candidates.sssom.tsv" \
    "For each mapping you want to propose:" \
    "  1. Change mapping_justification → semapv:ManualMappingCuration" \
    "  2. Set predicate_id to one of:" \
    "       skos:exactMatch  skos:closeMatch  skos:narrowMatch" \
    "       skos:broadMatch  skos:relatedMatch" \
    "     or owl:differentFrom to pre-reject" \
    "" \
    "Leave unedited rows as-is — they will be skipped at ingest."

confirm "Done editing? (yes to continue, skip to proceed without edits)" \
    || echo "  Skipping analyst edits — no proposals will be staged."

# ── Step 3: Ledger append (analyst proposals, with lint gate) ─────────────────

info "Step 3 — Stage analyst proposals into audit log (lint gate runs automatically)"
echo "  Use --dry-run to check for lint errors without appending:"
echo "    uv run rosetta ledger --audit-log $LOG append --role analyst --dry-run \\"
echo "      $OUT/candidates.sssom.tsv \\"
echo "      --source-schema $OUT/nor_radar.linkml.yaml --master-schema $OUT/master_cop_ontology.linkml.yaml"

run_cmd uv run rosetta ledger --audit-log "$LOG" append --role analyst "$OUT/candidates.sssom.tsv" \
    --source-schema "$OUT/nor_radar.linkml.yaml" \
    --master-schema "$OUT/master_cop_ontology.linkml.yaml"
ok "Analyst proposals appended to audit log."

# ── Step 4: Generate accreditor work list ─────────────────────────────────────

info "Step 4 — Generate accreditor review list"

run_cmd uv run rosetta ledger --audit-log "$LOG" review -o "$OUT/review.sssom.tsv"
ok "$OUT/review.sssom.tsv"

# ── Pause: Accreditor edits review ───────────────────────────────────────────

box "ACCREDITOR STEP — Edit $OUT/review.sssom.tsv" \
    "For each pending mapping:" \
    "  1. Change mapping_justification → semapv:HumanCuration" \
    "  2. Approve: keep predicate_id as-is (or refine to a more precise SKOS term)" \
    "     Reject:  set predicate_id → owl:differentFrom" \
    "" \
    "Leave unedited rows as-is — they will remain pending."

confirm "Done editing? (yes to append decisions, skip to finish without appending, quit to abort)" \
    || { echo "  Skipping accreditor append."; exit 0; }

# ── Step 5: Ledger append (accreditor decisions) ──────────────────────────────

info "Step 5 — Append accreditor decisions"

run_cmd uv run rosetta ledger --audit-log "$LOG" append --role accreditor "$OUT/review.sssom.tsv" \
    --source-schema "$OUT/nor_radar.linkml.yaml" \
    --master-schema "$OUT/master_cop_ontology.linkml.yaml"
ok "Accreditor decisions appended to audit log."

# ── Step 6: Compile YARRRML mapping artifact ─────────────────────────────────

info "Step 6 — Compile SSSOM audit log to YARRRML mapping"
echo "  (Requires approved mappings in the audit log from steps 3–5)"

COMPILE_OK=false
if run_cmd uv run rosetta compile "$LOG" \
    --source-schema "$OUT/nor_radar.linkml.yaml" \
    --master-schema "$OUT/master_cop_ontology.linkml.yaml" \
    --coverage-report "$OUT/coverage.json" \
    --spec-output "$OUT/nor_to_mc.transform.yaml" \
    -o "$OUT/nor_to_mc.yarrrml.yaml"; then
    ok "$OUT/nor_to_mc.yarrrml.yaml    (YARRRML mapping)"
    ok "$OUT/nor_to_mc.transform.yaml  (TransformSpec)"
    ok "$OUT/coverage.json             (coverage report)"
    COMPILE_OK=true
else
    echo "  ⚠  compile failed — the audit log may not contain approved mappings."
    echo "     If you skipped editing candidates/review, this is expected."
    echo "     Skipping transform step."
fi

# ── Step 7: Transform source data → JSON-LD (validates by default) ────────────

if $COMPILE_OK; then
    info "Step 7 — Transform source data to JSON-LD (SHACL validation runs by default)"
    echo "  Pass --no-validate to skip validation, or --shapes-dir for custom shapes."

    if run_cmd uv run rosetta transform \
        "$OUT/nor_to_mc.yarrrml.yaml" \
        "$SRC_FIXTURE" \
        --master-schema "$OUT/master_cop_ontology.linkml.yaml" \
        -o "$OUT/output.jsonld" \
        --workdir "$OUT/morph_workdir"; then
        ok "$OUT/output.jsonld  (materialized JSON-LD, validated against SHACL shapes)"
    else
        echo "  ⚠  transform failed — check mapping and source data."
        echo "     (Constraint violations are expected if sample data does not fully"
        echo "      populate all properties required by the shapes.)"
    fi
else
    info "Step 7 — Transform (skipped — compile did not produce a mapping)"
fi

# ── Done ──────────────────────────────────────────────────────────────────────

info "Pipeline complete"
echo ""
echo "  Candidates  : $OUT/candidates.sssom.tsv"
echo "  Review      : $OUT/review.sssom.tsv"
echo "  Audit log   : $LOG"
if $COMPILE_OK; then
echo "  YARRRML     : $OUT/nor_to_mc.yarrrml.yaml"
echo "  TransformSpec: $OUT/nor_to_mc.transform.yaml"
echo "  Coverage    : $OUT/coverage.json"
echo "  JSON-LD     : $OUT/output.jsonld"
fi
echo ""
echo "  Next steps:"
echo "    uv run rosetta ledger --audit-log '$LOG' dump     # export approved mappings"
echo "    uv run rosetta suggest '$OUT/nor_radar.linkml.yaml' '$OUT/master_cop_ontology.linkml.yaml' \\"
echo "      --audit-log '$LOG' -o candidates2.sssom.tsv     # re-run suggest"
