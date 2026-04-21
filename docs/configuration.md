# Configuration

`rosetta.toml` is the single config file for every tool. Precedence is always:

**CLI flag** > **env var** > **config file** > **built-in default**

Environment variables follow the pattern `ROSETTA_<SECTION>_<KEY>` (uppercase), so `top_k` under `[suggest]` becomes `ROSETTA_SUGGEST_TOP_K=10`.

## Example

```toml
[general]
store_path     = "store"
default_format = "turtle"

[embed]
model = "intfloat/e5-large-v2"
mode  = "lexical-only"

[suggest]
top_k             = 5
min_score         = 0.0
anomaly_threshold = 0.3
structural_weight = 0.2

[lint]
strict = false

[accredit]
log = "store/audit-log.sssom.tsv"
```

## Sections

### `[general]`

| Key | Default | Purpose |
|-----|---------|---------|
| `store_path` | `"store"` | Directory for the accreditation store |
| `default_format` | `"turtle"` | Default RDF serialisation for multi-format outputs |

### `[embed]`

| Key | Default | Purpose |
|-----|---------|---------|
| `model` | `"intfloat/e5-large-v2"` | Sentence-transformer model ID |
| `mode` | `"lexical-only"` | Embedding mode; reserved for future blending knobs |

### `[suggest]`

| Key | Default | Purpose |
|-----|---------|---------|
| `top_k` | `5` | Max suggestions per source field |
| `min_score` | `0.0` | Minimum cosine score for inclusion |
| `anomaly_threshold` | `0.3` | Score gap used to flag anomalous top-1 matches |
| `structural_weight` | `0.2` | Weight applied to structural cosine in blended scoring. Set to `0.0` to disable blending |

### `[lint]`

| Key | Default | Purpose |
|-----|---------|---------|
| `strict` | `false` | Upgrade WARNINGs to BLOCKs globally |

### `[accredit]`

| Key | Default | Purpose |
|-----|---------|---------|
| `log` | `"store/audit-log.sssom.tsv"` | Path to the append-only audit log |

`rosetta suggest` and `rosetta lint` both read `[accredit].log` automatically when it is set, providing boost/derank and conflict-checking without explicit flags.
