#!/usr/bin/env bash
# scripts/pipeline-demo.sh
#
# Interactive walkthrough of the full accreditation pipeline:
#   ingest → translate → embed → suggest
#   → [analyst edits candidates.sssom.tsv]
#   → lint (with retry loop)
#   → accredit ingest (analyst proposals)
#   → accredit review
#   → [accreditor edits review.sssom.tsv]
#   → accredit ingest (accreditor decisions)
#
# Usage: bash scripts/pipeline-demo.sh [OUTPUT_DIR]
#   OUTPUT_DIR  Directory for generated files (default: demo_out)
#
# Requirements:
#   uv sync            Install dependencies before running.
#   DEEPL_API_KEY      Only needed for non-English source schemas.
#                      This demo passes --source-lang EN so DeepL is not called.
#
# The audit log is written to store/audit-log.sssom.tsv (rosetta.toml default).
# Re-running the script will accumulate entries in the same log.

set -euo pipefail

# ── Helpers ───────────────────────────────────────────────────────────────────

info() {
    echo ""
    echo "━━━  $*  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

ok() { echo "  ✓  $*"; }

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
SRC_FIXTURE="rosetta/tests/fixtures/nor_radar.csv"
MASTER_FIXTURE="rosetta/tests/fixtures/master_cop_ontology.ttl"
LOG="store/audit-log.sssom.tsv"

mkdir -p "$OUT"
mkdir -p "$(dirname "$LOG")"

echo ""
echo "Pipeline demo"
echo "  Output dir : $OUT"
echo "  Audit log  : $LOG"

# ── Step 1: Ingest ────────────────────────────────────────────────────────────

info "Step 1 — Ingest schemas → LinkML YAML"

uv run rosetta-ingest \
    --input  "$SRC_FIXTURE" \
    --output "$OUT/nor_radar.linkml.yaml"
ok "$OUT/nor_radar.linkml.yaml"

uv run rosetta-ingest \
    --input  "$MASTER_FIXTURE" \
    --format rdfs \
    --output "$OUT/master_cop.linkml.yaml"
ok "$OUT/master_cop.linkml.yaml"

# ── Step 2: Translate ─────────────────────────────────────────────────────────

info "Step 2 — Translate schemas to English"
echo "  (--source-lang EN: passthrough — no DeepL API call required)"

uv run rosetta-translate \
    --input       "$OUT/nor_radar.linkml.yaml" \
    --output      "$OUT/nor_radar_en.linkml.yaml" \
    --source-lang EN
ok "$OUT/nor_radar_en.linkml.yaml"

uv run rosetta-translate \
    --input       "$OUT/master_cop.linkml.yaml" \
    --output      "$OUT/master_cop_en.linkml.yaml" \
    --source-lang EN
ok "$OUT/master_cop_en.linkml.yaml"

# ── Step 3: Embed ─────────────────────────────────────────────────────────────

info "Step 3 — Embed schemas"
echo "  (First run downloads the model ~1.2 GB from HuggingFace; subsequent runs use cache)"

uv run rosetta-embed \
    --input  "$OUT/nor_radar_en.linkml.yaml" \
    --output "$OUT/nor_radar_emb.json"
ok "$OUT/nor_radar_emb.json"

uv run rosetta-embed \
    --input  "$OUT/master_cop_en.linkml.yaml" \
    --output "$OUT/master_cop_emb.json"
ok "$OUT/master_cop_emb.json"

# ── Step 4: Suggest ───────────────────────────────────────────────────────────

info "Step 4 — Generate mapping candidates"

uv run rosetta-suggest \
    "$OUT/nor_radar_emb.json" \
    "$OUT/master_cop_emb.json" \
    --output "$OUT/candidates.sssom.tsv"
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
    if uv run rosetta-lint --sssom "$OUT/candidates.sssom.tsv"; then
        ok "Lint passed — no errors."
        break
    fi

    box "LINT ERRORS — Fix $OUT/candidates.sssom.tsv then re-run" \
        "Common fixes:" \
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

# ── Step 6: Accredit ingest (analyst proposals) ───────────────────────────────

info "Step 6 — Stage analyst proposals into audit log"

uv run rosetta-accredit --log "$LOG" ingest "$OUT/candidates.sssom.tsv"

# ── Step 7: Generate accreditor work list ─────────────────────────────────────

info "Step 7 — Generate accreditor review list"

uv run rosetta-accredit --log "$LOG" review --output "$OUT/review.sssom.tsv"
ok "$OUT/review.sssom.tsv"

# ── Pause: Accreditor edits review ───────────────────────────────────────────

box "ACCREDITOR STEP — Edit $OUT/review.sssom.tsv" \
    "For each pending mapping:" \
    "  1. Change mapping_justification → semapv:HumanCuration" \
    "  2. Approve: keep predicate_id as-is (or refine to a more precise SKOS term)" \
    "     Reject:  set predicate_id → owl:differentFrom" \
    "" \
    "Leave unedited rows as-is — they will remain pending."

confirm "Done editing? (yes to ingest decisions, skip to finish without ingesting, quit to abort)" \
    || { echo "  Skipping accreditor ingest."; exit 0; }

# ── Step 8: Accredit ingest (accreditor decisions) ────────────────────────────

info "Step 8 — Ingest accreditor decisions"

uv run rosetta-accredit --log "$LOG" ingest "$OUT/review.sssom.tsv"

# ── Done ──────────────────────────────────────────────────────────────────────

info "Pipeline complete"
echo ""
echo "  Candidates : $OUT/candidates.sssom.tsv"
echo "  Review     : $OUT/review.sssom.tsv"
echo "  Audit log  : $LOG"
echo ""
echo "  Next steps:"
echo "    uv run rosetta-accredit --log '$LOG' status   # view all decisions"
echo "    uv run rosetta-accredit --log '$LOG' dump     # export approved mappings"
echo "    uv run rosetta-suggest  ... --output candidates2.sssom.tsv  # re-run with boost/derank"
