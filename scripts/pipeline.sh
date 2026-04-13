#!/usr/bin/env bash
# Rosetta CLI — Milestone 3 end-to-end pipeline demo
# Demonstrates: ingest → embed → suggest → accredit → suggest (with feedback)
set -euo pipefail

FIXTURES="rosetta/tests/fixtures"
STORE="store"
LEDGER="$STORE/pipeline-ledger.json"

# Preflight checks
[[ -f "$FIXTURES/nor_schema.csv" ]] || { echo "ERROR: missing $FIXTURES/nor_schema.csv"; exit 1; }
[[ -f "$STORE/master-ontology/master.ttl" ]] || { echo "ERROR: missing $STORE/master-ontology/master.ttl — run rosetta-ingest for master ontology first"; exit 1; }
mkdir -p "$STORE"

echo "=== 1. Ingest NOR schema ==="
uv run rosetta-ingest --input "$FIXTURES/nor_schema.csv" --format csv --output "$STORE/nor.ttl"

echo "=== 2. Embed NOR + master ==="
uv run rosetta-embed --input "$STORE/nor.ttl" --output "$STORE/nor-emb.json"
uv run rosetta-embed --input "$STORE/master-ontology/master.ttl" --output "$STORE/master-emb.json"

echo "=== 3. Suggest (no ledger) ==="
uv run rosetta-suggest --source "$STORE/nor-emb.json" --master "$STORE/master-emb.json" \
  --output "$STORE/suggestions-before.json"
echo "Suggestions written to $STORE/suggestions-before.json"

echo "=== 4. Accredit: submit + approve one mapping ==="
# Use first source URI from NOR embeddings as example
SOURCE_URI=$(uv run python -c "import json; d=json.load(open('$STORE/nor-emb.json')); print(list(d.keys())[0])")
TARGET_URI=$(uv run python -c "import json; d=json.load(open('$STORE/suggestions-before.json')); src=list(d.keys())[0]; print(d[src]['suggestions'][0]['target_uri'])")

uv run rosetta-accredit submit --source "$SOURCE_URI" --target "$TARGET_URI" --ledger "$LEDGER"
uv run rosetta-accredit approve --source "$SOURCE_URI" --target "$TARGET_URI" --ledger "$LEDGER"

echo "=== 5. Suggest with ledger (accredited boost) ==="
uv run rosetta-suggest --source "$STORE/nor-emb.json" --master "$STORE/master-emb.json" \
  --ledger "$LEDGER" --output "$STORE/suggestions-after.json"
echo "Boosted suggestions written to $STORE/suggestions-after.json"

echo "=== 6. Revoke the mapping ==="
uv run rosetta-accredit revoke --source "$SOURCE_URI" --target "$TARGET_URI" --ledger "$LEDGER"

echo "=== 7. Suggest with ledger (revoked excluded) ==="
uv run rosetta-suggest --source "$STORE/nor-emb.json" --master "$STORE/master-emb.json" \
  --ledger "$LEDGER" --output "$STORE/suggestions-revoked.json"
echo "Post-revocation suggestions written to $STORE/suggestions-revoked.json"

echo "=== Pipeline complete ==="
