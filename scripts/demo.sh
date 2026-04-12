#!/usr/bin/env bash
# demo.sh — end-to-end rosetta-cli walkthrough using bundled fixture files
#
# Runs:  ingest → embed → suggest
# for three nation schemas (USA, DEU, NOR), then ranks DEU and NOR fields
# against the USA schema used as the master ontology.
#
# Usage:
#   bash scripts/demo.sh
#
# Requirements:
#   uv sync   (first-time setup)

set -euo pipefail

FIXTURES="rosetta/tests/fixtures"
OUT="demo_output"

echo "==> Creating output directory: $OUT"
mkdir -p "$OUT"

# ── Step 1: Ingest ─────────────────────────────────────────────────────────

echo ""
echo "==> [1/3] Ingesting schemas"

echo "    USA  (OpenAPI YAML)"
uv run rosetta-ingest \
  -i "$FIXTURES/usa_c2.yaml" \
  -n USA \
  -o "$OUT/usa_c2.ttl"

echo "    DEU  (JSON Schema)"
uv run rosetta-ingest \
  -i "$FIXTURES/deu_patriot.json" \
  -n DEU \
  -o "$OUT/deu_patriot.ttl"

echo "    NOR  (CSV)"
uv run rosetta-ingest \
  -i "$FIXTURES/nor_radar.csv" \
  -n NOR \
  -o "$OUT/nor_radar.ttl"

echo "    Turtle files written to $OUT/"

# ── Step 2: Embed ──────────────────────────────────────────────────────────

echo ""
echo "==> [2/3] Embedding attributes (LaBSE — first run downloads the model)"

uv run rosetta-embed -i "$OUT/usa_c2.ttl"     -o "$OUT/usa_c2_emb.json"
uv run rosetta-embed -i "$OUT/deu_patriot.ttl" -o "$OUT/deu_patriot_emb.json"
uv run rosetta-embed -i "$OUT/nor_radar.ttl"   -o "$OUT/nor_radar_emb.json"

echo "    Embedding files written to $OUT/"

# ── Step 3: Suggest ────────────────────────────────────────────────────────

echo ""
echo "==> [3/3] Generating mapping suggestions (source → USA master ontology)"

echo "    DEU → USA"
uv run rosetta-suggest \
  --source "$OUT/deu_patriot_emb.json" \
  --master "$OUT/usa_c2_emb.json" \
  --output "$OUT/deu_to_usa_suggestions.json"

echo "    NOR → USA"
uv run rosetta-suggest \
  --source "$OUT/nor_radar_emb.json" \
  --master "$OUT/usa_c2_emb.json" \
  --output "$OUT/nor_to_usa_suggestions.json"

# ── Summary ────────────────────────────────────────────────────────────────

echo ""
echo "==> Done. Output files:"
ls -1 "$OUT/"

echo ""
echo "==> Top suggestions for DEU fields (preview):"
python3 - <<'EOF'
import json, pathlib

data = json.loads(pathlib.Path("demo_output/deu_to_usa_suggestions.json").read_text())
for uri, entry in data.items():
    field = uri.split("/")[-1]
    top = entry["suggestions"][0] if entry["suggestions"] else None
    score = f"{top['score']:.3f}" if top else "n/a"
    match = top["uri"].split("/")[-1] if top else "—"
    anomaly = " [ANOMALY]" if entry.get("anomaly") else ""
    print(f"  {field:<28} → {match:<20} ({score}){anomaly}")
EOF
