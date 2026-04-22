# Getting started

## Install

```bash
git clone https://github.com/drex04/rosetta-cli.git
cd rosetta-cli
uv sync
```

All five commands are then available via `uv run rosetta <cmd>`:

```bash
uv run rosetta ingest --help
uv run rosetta suggest --help
uv run rosetta ledger --help
uv run rosetta compile --help
uv run rosetta transform --help
```

!!! tip "First suggest run"
    The default embedding model (`intfloat/e5-large-v2`, ~1.2 GB) downloads from HuggingFace on the first `rosetta suggest` invocation. Subsequent runs use the local cache.

## Run the bundled demo

The repo ships with a full accreditation walkthrough against fixture schemas from three partner nations:

```bash
bash scripts/pipeline-demo.sh          # writes to demo_out/
bash scripts/pipeline-demo.sh my_run   # custom output directory
```

The script pauses at each human-in-the-loop step so you can inspect and edit intermediate files. It covers:

1. **Ingest** — three partner schemas (CSV, JSON, YAML) plus a master Turtle ontology; optional `--translate` for Norwegian titles via DeepL (set `DEEPL_API_KEY`).
2. **Suggest** — embed slots and rank candidate mappings by cosine similarity.
3. **Accredit** — `rosetta ledger append` (analyst proposals, with lint gate), generate accreditor work list, append decisions.
4. **Generate & materialise** — `rosetta compile` then `rosetta transform` compiles an approved SSSOM log into a YARRRML mapping and produces validated JSON-LD aligned to the master ontology.

## Minimal pipeline

For the impatient — a two-command pipeline that goes from two partner schemas to a ranked candidate list:

```bash
# 1. Ingest both sides to LinkML
uv run rosetta ingest partner.csv  -o partner.linkml.yaml
uv run rosetta ingest master.ttl   -o master.linkml.yaml --format rdfs

# 2. Embed slots and rank candidate mappings
uv run rosetta suggest partner.linkml.yaml master.linkml.yaml -o candidates.sssom.tsv
```

Open `candidates.sssom.tsv` in any TSV viewer — the top-K candidates per source field, ranked by cosine score, ready for analyst review.

## Configure

`rosetta.toml` controls defaults for every tool. Precedence is **CLI flag > env var > config file**. Environment variables use the pattern `ROSETTA_<SECTION>_<KEY>` (uppercase).

See [Configuration](configuration.md) for the full schema.

## Where to go next

- [The pipeline](concepts/pipeline.md) — conceptual flow.
- [Accreditation workflow](concepts/accreditation.md) — the Analyst/Accreditor state machine.
- [CLI reference](cli/index.md) — every option, every exit code.
