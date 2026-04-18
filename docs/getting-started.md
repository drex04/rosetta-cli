# Getting started

## Install

```bash
git clone https://github.com/drex04/rosetta-cli.git
cd rosetta-cli
uv sync
```

All nine commands are then available via `uv run <tool>`:

```bash
uv run rosetta-ingest --help
uv run rosetta-embed --help
uv run rosetta-suggest --help
# ...
```

!!! tip "First embed run"
    The default embedding model (`intfloat/e5-large-v2`, ~1.2 GB) downloads from HuggingFace on the first `rosetta-embed` invocation. Subsequent runs use the local cache.

## Run the bundled demo

The repo ships with a full accreditation walkthrough against fixture schemas from three partner nations:

```bash
bash scripts/pipeline-demo.sh          # writes to demo_out/
bash scripts/pipeline-demo.sh my_run   # custom output directory
```

The script pauses at each human-in-the-loop step so you can inspect and edit intermediate files. It covers:

1. **Ingest** — three partner schemas (CSV, JSON, YAML) plus a master Turtle ontology.
2. **Translate** — Norwegian schema titles to English via DeepL (set `DEEPL_API_KEY`; pass-through if unset for English sources).
3. **Embed** — produce per-slot vectors for each schema.
4. **Suggest** — rank candidate mappings by cosine similarity.
5. **Lint** — validate analyst proposals for unit dimensionality and audit-log conflicts.
6. **Accredit** — ingest analyst proposals, generate the accreditor work list, ingest decisions.
7. **Generate & materialise** — `rosetta-yarrrml-gen --run` compiles an approved SSSOM log into a YARRRML mapping and produces JSON-LD aligned to the master ontology.

## Minimal pipeline

For the impatient — a three-command pipeline that goes from two partner schemas to a ranked candidate list:

```bash
# 1. Ingest both sides to LinkML
uv run rosetta-ingest --input partner.csv       --output partner.linkml.yaml
uv run rosetta-ingest --input master.ttl        --output master.linkml.yaml --format rdfs

# 2. Embed each schema
uv run rosetta-embed   --input partner.linkml.yaml --output partner.emb.json
uv run rosetta-embed   --input master.linkml.yaml  --output master.emb.json

# 3. Rank candidate mappings
uv run rosetta-suggest partner.emb.json master.emb.json --output candidates.sssom.tsv
```

Open `candidates.sssom.tsv` in any TSV viewer — the top-K candidates per source field, ranked by cosine score, ready for analyst review.

## Configure

`rosetta.toml` controls defaults for every tool. Precedence is **CLI flag > env var > config file**. Environment variables use the pattern `ROSETTA_<SECTION>_<KEY>` (uppercase).

See [Configuration](configuration.md) for the full schema.

## Where to go next

- [The pipeline](concepts/pipeline.md) — conceptual flow.
- [Accreditation workflow](concepts/accreditation.md) — the Analyst/Accreditor state machine.
- [CLI reference](cli/index.md) — every option, every exit code.
