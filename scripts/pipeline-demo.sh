#!/usr/bin/env bash
# scripts/pipeline-demo.sh
#
# Interactive walkthrough of the full accreditation pipeline:
#   ingest → translate → suggest
#   → [analyst edits candidates.sssom.tsv]
#   → lint (with retry loop)
#   → accredit append (analyst proposals)
#   → accredit review
#   → [accreditor edits review.sssom.tsv]
#   → accredit append (accreditor decisions)
#   → compile (YARRRML mapping artifact)
#   → run (JSON-LD materialization)
#   → validate (SHACL constraint checking)
#
# Usage: bash scripts/pipeline-demo.sh [OUTPUT_DIR]
#   OUTPUT_DIR  Directory for generated files (default: demo_out)
#
# Requirements:
#   uv sync            Install dependencies before running.
#   DEEPL_API_KEY      Only needed for non-English source schemas.
#
# The audit log is written to $OUTPUT_DIR/audit-log.sssom.tsv.
# Re-running the script will accumulate entries in the same log.

set -euo pipefail

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
SHAPES_DIR="rosetta/policies/shacl"

mkdir -p "$OUT"

echo ""
echo "Pipeline demo"
echo "  Output dir  : $OUT"
echo "  Audit log   : $LOG"
echo "  SHACL shapes: $SHAPES_DIR"

# ── Step 1: Ingest ────────────────────────────────────────────────────────────

info "Step 1 — Ingest schemas → LinkML YAML"

run_cmd uv run rosetta ingest \
    "$SRC_FIXTURE" \
    -o "$OUT/nor_radar.linkml.yaml"
ok "$OUT/nor_radar.linkml.yaml"

run_cmd uv run rosetta ingest \
    "$MASTER_FIXTURE" \
    --schema-format rdfs \
    -o "$OUT/master_cop.linkml.yaml"
ok "$OUT/master_cop.linkml.yaml"

# ── Step 2: Translate ─────────────────────────────────────────────────────────

info "Step 2 — Translate schemas to English"

run_cmd uv run rosetta translate \
    "$OUT/nor_radar.linkml.yaml" \
    --source-lang NB \
    -o "$OUT/nor_radar_en.linkml.yaml"
ok "$OUT/nor_radar_en.linkml.yaml"

run_cmd uv run rosetta translate \
    "$OUT/master_cop.linkml.yaml" \
    --source-lang EN \
    -o "$OUT/master_cop_en.linkml.yaml"
ok "$OUT/master_cop_en.linkml.yaml"

# ── Step 3: Suggest ───────────────────────────────────────────────────────────

info "Step 3 — Generate mapping candidates"
echo "  (First run downloads the embedding model ~1.2 GB from HuggingFace; subsequent runs use cache)"

run_cmd uv run rosetta suggest \
    "$OUT/nor_radar_en.linkml.yaml" \
    "$OUT/master_cop_en.linkml.yaml" \
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

# ── Step 5: Lint (with retry loop) ───────────────────────────────────────────

info "Step 5 — Lint SSSOM proposals"

while true; do
    if run_cmd uv run rosetta lint "$OUT/candidates.sssom.tsv" \
        --source-schema "$OUT/nor_radar_en.linkml.yaml" \
        --master-schema "$OUT/master_cop_en.linkml.yaml" \
        --audit-log "$LOG"; then
        ok "Lint passed — no errors."
        break
    fi

    box "LINT ERRORS — Fix $OUT/candidates.sssom.tsv then re-run" \
        "Common fixes:" \
        "  slot_class_unreachable    Map the source class to the correct target class (one that owns the slot)" \
        "  MaxOneMmcPerPair          Remove duplicate ManualMappingCuration rows for the same pair" \
        "  NoHumanCurationReproposal Pair already has a final decision — remove the row" \
        "  ValidPredicate            Use a recognised skos: or owl: predicate"

    if confirm "Re-run lint after fixing? (yes to retry, skip to proceed anyway, quit to abort)"; then
        : # loop again
    else
        echo "  Proceeding despite lint errors."
        break
    fi
done

# ── Step 6: Accredit append (analyst proposals) ───────────────────────────────

info "Step 6 — Stage analyst proposals into audit log"

run_cmd uv run rosetta ledger --audit-log "$LOG" append "$OUT/candidates.sssom.tsv"

# ── Step 7: Generate accreditor work list ─────────────────────────────────────

info "Step 7 — Generate accreditor review list"

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

# ── Step 8: Accredit append (accreditor decisions) ────────────────────────────

info "Step 8 — Append accreditor decisions"

run_cmd uv run rosetta ledger --audit-log "$LOG" append "$OUT/review.sssom.tsv"

# ── Step 9: Compile YARRRML mapping artifact ─────────────────────────────────

info "Step 9 — Compile SSSOM audit log to YARRRML mapping"
echo "  (Requires approved mappings in the audit log from steps 6–8)"

COMPILE_OK=false
if run_cmd uv run rosetta compile "$LOG" \
    --source-schema "$OUT/nor_radar_en.linkml.yaml" \
    --master-schema "$OUT/master_cop_en.linkml.yaml" \
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
    echo "     Skipping run and validation steps."
fi

# ── Step 10: Materialize JSON-LD ──────────────────────────────────────────────

JSONLD_OK=false
if $COMPILE_OK; then
    info "Step 10 — Materialize JSON-LD from YARRRML mapping"

    if run_cmd uv run rosetta transform \
        "$OUT/nor_to_mc.yarrrml.yaml" \
        "$SRC_FIXTURE" \
        --master-schema "$OUT/master_cop_en.linkml.yaml" \
        -o "$OUT/output.jsonld" \
        --workdir "$OUT/morph_workdir"; then
        ok "$OUT/output.jsonld  (materialized JSON-LD)"
        JSONLD_OK=true
    else
        echo "  ⚠  run failed — check mapping and source data."
        echo "     Skipping validation step."
    fi
else
    info "Step 10 — Materialize JSON-LD (skipped — compile did not produce a mapping)"
fi

# ── Step 11: Validate JSON-LD ────────────────────────────────────────────────

if $JSONLD_OK; then
    info "Step 11 — Validate materialized output against SHACL shapes"

    if run_cmd uv run rosetta validate \
        "$OUT/output.jsonld" \
        "$SHAPES_DIR" \
        -o "$OUT/validation-report.json"; then
        ok "Validation passed — output conforms to SHACL shapes."
        ok "$OUT/validation-report.json"
    else
        echo "  ⚠  Validation found constraint violations."
        echo "     See: $OUT/validation-report.json"
        echo "     (This is expected if the sample data does not fully"
        echo "      populate all properties required by the SHACL shapes.)"
    fi
else
    info "Step 11 — Validate (skipped — no JSON-LD produced)"
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
fi
if $JSONLD_OK; then
echo "  JSON-LD     : $OUT/output.jsonld"
echo "  Validation  : $OUT/validation-report.json"
fi
echo ""
echo "  Next steps:"
echo "    uv run rosetta ledger --audit-log '$LOG' dump     # export approved mappings"
echo "    uv run rosetta suggest nor_radar_en.linkml.yaml master_cop_en.linkml.yaml --audit-log '$LOG' -o candidates2.sssom.tsv  # re-run suggest"
