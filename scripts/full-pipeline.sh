#!/usr/bin/env bash
# full-pipeline.sh — end-to-end governance pipeline using all 8 rosetta-cli tools
#
# Flow:
#   ingest → embed → suggest → lint → rml-gen → provenance stamp
#   → validate → accredit (submit/approve) → suggest with ledger → accredit (revoke)
#
# Uses the NOR fixture schema mapped against the USA schema as master ontology.
#
# Usage:
#   bash scripts/full-pipeline.sh
#
# Requirements:
#   uv sync   (first-time setup)
#   Note: rosetta-embed downloads the LaBSE model (~900 MB) on first run.

set -euo pipefail

FIXTURES="rosetta/tests/fixtures"
OUT="pipeline_output"
LEDGER="$OUT/ledger.json"
SHAPES="rosetta/policies/mapping.shacl.ttl"

echo "==> Output directory: $OUT"
mkdir -p "$OUT"

# ── 1. Ingest ───────────────────────────────────────────────────────────────

echo ""
echo "[1/9] Ingesting schemas"
uv run rosetta-ingest -i "$FIXTURES/nor_radar.csv" -n NOR -o "$OUT/nor.ttl"
uv run rosetta-ingest -i "$FIXTURES/usa_c2.yaml"   -n USA -o "$OUT/usa.ttl"
echo "      → $OUT/nor.ttl  $OUT/usa.ttl"

# ── 2. Embed ────────────────────────────────────────────────────────────────

echo ""
echo "[2/9] Embedding (LaBSE — first run downloads ~900 MB model)"
uv run rosetta-embed -i "$OUT/nor.ttl" -o "$OUT/nor_emb.json"
uv run rosetta-embed -i "$OUT/usa.ttl" -o "$OUT/usa_emb.json"
echo "      → $OUT/nor_emb.json  $OUT/usa_emb.json"

# ── 3. Suggest (no ledger) ──────────────────────────────────────────────────

echo ""
echo "[3/9] Generating initial suggestions (no accreditation ledger)"
uv run rosetta-suggest \
  --source "$OUT/nor_emb.json" \
  --master "$OUT/usa_emb.json" \
  --output "$OUT/suggestions.json"
echo "      → $OUT/suggestions.json"

echo ""
echo "      Top suggestions (preview):"
python3 - "$OUT/suggestions.json" <<'EOF'
import json, sys, pathlib
data = json.loads(pathlib.Path(sys.argv[1]).read_text())
for uri, entry in list(data.items())[:5]:
    field = uri.split("/")[-1]
    top = entry["suggestions"][0] if entry["suggestions"] else None
    score = f"{top['score']:.3f}" if top else "n/a"
    match = top["target_uri"].split("/")[-1] if top else "—"
    anomaly = " [ANOMALY]" if entry.get("anomaly") else ""
    print(f"      {field:<30} → {match:<22} ({score}){anomaly}")
EOF

# ── 4. Lint ─────────────────────────────────────────────────────────────────

echo ""
echo "[4/9] Linting unit/datatype compatibility"
uv run rosetta-lint \
  --source "$OUT/nor.ttl" \
  --master "$OUT/usa.ttl" \
  --suggestions "$OUT/suggestions.json" \
  --output "$OUT/lint.json" || true   # exit 1 on BLOCKs; capture output regardless

python3 - "$OUT/lint.json" <<'EOF'
import json, sys, pathlib
report = json.loads(pathlib.Path(sys.argv[1]).read_text())
s = report["summary"]
print(f"      BLOCKs: {s['block']}  WARNINGs: {s['warning']}  INFO: {s['info']}")
for f in report["findings"][:3]:
    print(f"      [{f['severity']}] {f['rule']}: {f['message'][:70]}")
EOF

# ── 5. Build decisions from top suggestions ─────────────────────────────────

echo ""
echo "[5/9] Building decisions JSON from top suggestions"
python3 - "$OUT/suggestions.json" "$OUT/decisions.json" <<'EOF'
import json, sys, pathlib

suggestions = json.loads(pathlib.Path(sys.argv[1]).read_text())
decisions = {}
for src_uri, entry in suggestions.items():
    if entry.get("anomaly"):
        continue  # skip low-confidence matches
    top = entry["suggestions"][0] if entry["suggestions"] else None
    if top and top["score"] >= 0.3:
        decisions[src_uri] = {"target_uri": top["target_uri"]}

pathlib.Path(sys.argv[2]).write_text(json.dumps(decisions, indent=2))
print(f"      {len(decisions)} mappings written to {sys.argv[2]}")
EOF

# ── 6. Generate RML ─────────────────────────────────────────────────────────

echo ""
echo "[6/9] Generating RML/FnML Turtle"
uv run rosetta-rml-gen \
  --decisions "$OUT/decisions.json" \
  --source-file "$FIXTURES/nor_radar.csv" \
  --source-format csv \
  --output "$OUT/mapping.rml.ttl"
echo "      → $OUT/mapping.rml.ttl"

# ── 7. Stamp provenance ─────────────────────────────────────────────────────

echo ""
echo "[7/9] Stamping provenance onto RML artifact"
uv run rosetta-provenance stamp "$OUT/mapping.rml.ttl" \
  --label "Initial NOR→USA mapping (full-pipeline.sh)"
echo "      Stamp complete (overwrote in-place)"

uv run rosetta-provenance query "$OUT/mapping.rml.ttl"

# ── 8. Validate ─────────────────────────────────────────────────────────────

echo ""
echo "[8/9] SHACL validation of RML output"
if [ -f "$SHAPES" ]; then
  uv run rosetta-validate \
    --data "$OUT/mapping.rml.ttl" \
    --shapes "$SHAPES" \
    --output "$OUT/validation.json" || true

  python3 - "$OUT/validation.json" <<'EOF'
import json, sys, pathlib
report = json.loads(pathlib.Path(sys.argv[1]).read_text())
s = report["summary"]
status = "CONFORMS" if s["conforms"] else "VIOLATIONS FOUND"
print(f"      {status} — Violations: {s['violation']}  Warnings: {s['warning']}  Info: {s['info']}")
EOF
else
  echo "      Skipping: $SHAPES not found"
fi

# ── 9. Accreditation lifecycle ───────────────────────────────────────────────

echo ""
echo "[9/9] Accreditation lifecycle"

# Pick the first non-anomaly source/target pair
python3 - "$OUT/suggestions.json" <<'EOF'
import json, pathlib, os
data = json.loads(pathlib.Path("pipeline_output/suggestions.json").read_text())
for src_uri, entry in data.items():
    if entry.get("anomaly"):
        continue
    top = entry["suggestions"][0] if entry["suggestions"] else None
    if top and top["score"] >= 0.3:
        with open("pipeline_output/.pair", "w") as f:
            f.write(f"{src_uri}\n{top['target_uri']}\n")
        break
EOF

SRC=$(sed -n '1p' "$OUT/.pair")
TGT=$(sed -n '2p' "$OUT/.pair")
rm "$OUT/.pair"

echo "      Source: $SRC"
echo "      Target: $TGT"

echo ""
echo "      submit →"
uv run rosetta-accredit submit \
  --source "$SRC" --target "$TGT" \
  --ledger "$LEDGER" \
  --actor "pipeline-demo" \
  --notes "Auto-submitted by full-pipeline.sh"

echo ""
echo "      approve →"
uv run rosetta-accredit approve \
  --source "$SRC" --target "$TGT" \
  --ledger "$LEDGER"

echo ""
echo "      suggest with ledger (accredited boost):"
uv run rosetta-suggest \
  --source "$OUT/nor_emb.json" \
  --master "$OUT/usa_emb.json" \
  --ledger "$LEDGER" \
  --output "$OUT/suggestions_accredited.json"

python3 - "$OUT/suggestions_accredited.json" "$SRC" <<'EOF'
import json, sys, pathlib
data = json.loads(pathlib.Path(sys.argv[1]).read_text())
src = sys.argv[2]
if src in data:
    entry = data[src]
    field = src.split("/")[-1]
    top = entry["suggestions"][0] if entry["suggestions"] else None
    score = f"{top['score']:.3f}" if top else "n/a"
    match = top["target_uri"].split("/")[-1] if top else "—"
    print(f"      {field:<30} → {match:<22} ({score})  ← boosted by ledger")
EOF

echo ""
echo "      revoke →"
uv run rosetta-accredit revoke \
  --source "$SRC" --target "$TGT" \
  --ledger "$LEDGER"

echo ""
echo "      suggest with ledger (revoked excluded):"
uv run rosetta-suggest \
  --source "$OUT/nor_emb.json" \
  --master "$OUT/usa_emb.json" \
  --ledger "$LEDGER" \
  --output "$OUT/suggestions_revoked.json"

python3 - "$OUT/suggestions_revoked.json" "$TGT" <<'EOF'
import json, sys, pathlib
data = json.loads(pathlib.Path(sys.argv[1]).read_text())
revoked_tgt = sys.argv[2]
found = False
for src_uri, entry in data.items():
    for s in entry["suggestions"]:
        if s["target_uri"] == revoked_tgt:
            found = True
            break
if found:
    print(f"      WARNING: revoked target still appears in suggestions")
else:
    print(f"      OK: revoked target excluded from all suggestions")
EOF

echo ""
echo "      Ledger status:"
uv run rosetta-accredit status --ledger "$LEDGER"

# ── Summary ─────────────────────────────────────────────────────────────────

echo ""
echo "==> Pipeline complete. Output files:"
ls -1 "$OUT/"
