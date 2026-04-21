# rosetta embed

Reads a LinkML YAML schema and computes sentence embeddings for every class and slot. Outputs a JSON map of slot URI → embedding vector.

## Command reference

::: mkdocs-click
    :module: rosetta.cli.embed
    :command: cli
    :prog_name: rosetta embed
    :depth: 2

## Output format

Each entry carries:

| Field | Purpose |
|-------|---------|
| `label` | Human-readable class or slot name — used by `rosetta suggest` for SSSOM `subject_label` / `object_label` |
| `lexical` | Sentence-transformer embedding of the slot text |
| `structural` | 5-float array of schema-structural features: `is_class`, `hierarchy_depth`, `is_required`, `is_multivalued`, `slot_usage_count` — all normalised to `[0.0, 1.0]` |

Older embed files without `structural` still load; `rosetta suggest` falls back to lexical-only scoring automatically.

!!! info "E5 models"
    For `intfloat/multilingual-e5-*` models, the `"passage: "` prefix is applied automatically on indexed texts. No extra flags required.

!!! tip "First run downloads the model"
    The default model (`intfloat/e5-large-v2`, ~1.2 GB) downloads from HuggingFace on the first invocation. Subsequent runs use the local cache.

## Examples

```bash
# Minimal — lexical only, default model
uv run rosetta embed nor.linkml.yaml --output nor.emb.json

# Richer context — full ancestor chain plus slot definitions
uv run rosetta embed nor.linkml.yaml --output nor.emb.json \
                     --include-ancestors --include-definitions

# Swap to multilingual E5 for stronger non-English recall
uv run rosetta embed nor.linkml.yaml --output nor.emb.json \
                     --model intfloat/multilingual-e5-base
```

## Exit codes

- `0` — success.
- `1` — I/O or model-loading error.
