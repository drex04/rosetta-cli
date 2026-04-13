#!/usr/bin/env bash
# quickstart.sh — core pipeline: ingest → embed → suggest
#
# Uses the three bundled fixture schemas (NOR CSV, DEU JSON Schema, USA OpenAPI).
# USA is used as the master ontology; suggestions are generated for NOR and DEU.
#
# Usage:
#   bash scripts/quickstart.sh
#
# Requirements:
#   uv sync   (first-time setup)
#   Note: rosetta-embed downloads the LaBSE model (~900 MB) on first run.

set -euo pipefail

FIXTURES="rosetta/tests/fixtures"
OUT="quickstart_output"

echo "==> Output directory: $OUT"
mkdir -p "$OUT"

# ── Step 1: Ingest ─────────────────────────────────────────────────────────

echo ""
echo "[1/3] Ingesting national schemas"

uv run rosetta-ingest -i "$FIXTURES/nor_radar.csv"    -n NOR -o "$OUT/nor.ttl"
echo "      NOR (CSV)          → $OUT/nor.ttl"

uv run rosetta-ingest -i "$FIXTURES/deu_patriot.json" -n DEU -o "$OUT/deu.ttl"
echo "      DEU (JSON Schema)  → $OUT/deu.ttl"

uv run rosetta-ingest -i "$FIXTURES/usa_c2.yaml"      -n USA -o "$OUT/usa.ttl"
echo "      USA (OpenAPI)      → $OUT/usa.ttl"

# ── Step 2: Embed ──────────────────────────────────────────────────────────

echo ""
echo "[2/3] Computing LaBSE embeddings"
echo "      (first run downloads the model — ~900 MB; subsequent runs use cache)"

uv run rosetta-embed -i "$OUT/nor.ttl" -o "$OUT/nor_emb.json"
echo "      NOR → $OUT/nor_emb.json"

uv run rosetta-embed -i "$OUT/deu.ttl" -o "$OUT/deu_emb.json"
echo "      DEU → $OUT/deu_emb.json"

uv run rosetta-embed -i "$OUT/usa.ttl" -o "$OUT/usa_emb.json"
echo "      USA → $OUT/usa_emb.json"

# ── Step 3: Suggest ────────────────────────────────────────────────────────

echo ""
echo "[3/3] Generating mapping suggestions (NOR → USA master, DEU → USA master)"

uv run rosetta-suggest \
  --source "$OUT/nor_emb.json" \
  --master "$OUT/usa_emb.json" \
  --output "$OUT/nor_suggestions.json"
echo "      NOR → $OUT/nor_suggestions.json"

uv run rosetta-suggest \
  --source "$OUT/deu_emb.json" \
  --master "$OUT/usa_emb.json" \
  --output "$OUT/deu_suggestions.json"
echo "      DEU → $OUT/deu_suggestions.json"

# ── Preview ────────────────────────────────────────────────────────────────

echo ""
echo "==> Top NOR field suggestions (preview):"
python3 - "$OUT/nor_suggestions.json" <<'EOF'
import json, sys, pathlib

data = json.loads(pathlib.Path(sys.argv[1]).read_text())
for uri, entry in list(data.items())[:8]:
    field = uri.split("/")[-1]
    top = entry["suggestions"][0] if entry["suggestions"] else None
    score = f"{top['score']:.3f}" if top else "n/a"
    match = top["target_uri"].split("/")[-1] if top else "—"
    anomaly = " [ANOMALY]" if entry.get("anomaly") else ""
    print(f"  {field:<30} → {match:<22} ({score}){anomaly}")
EOF

echo ""
echo "==> Top DEU field suggestions (preview):"
python3 - "$OUT/deu_suggestions.json" <<'EOF'
import json, sys, pathlib

data = json.loads(pathlib.Path(sys.argv[1]).read_text())
for uri, entry in list(data.items())[:8]:
    field = uri.split("/")[-1]
    top = entry["suggestions"][0] if entry["suggestions"] else None
    score = f"{top['score']:.3f}" if top else "n/a"
    match = top["target_uri"].split("/")[-1] if top else "—"
    anomaly = " [ANOMALY]" if entry.get("anomaly") else ""
    print(f"  {field:<30} → {match:<22} ({score}){anomaly}")
EOF

echo ""
echo "==> Done. Output files:"
ls -1 "$OUT/"
