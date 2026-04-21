# SHACL overrides

Hand-authored SHACL shapes. Files here are never modified by `rosetta shacl-gen` and are merged with `../generated/` when validation runs against `rosetta validate <data> rosetta/policies/shacl/`.

## Naming convention

`<topic>.ttl` — e.g., `track_bearing_range.ttl`, `airtrack_required_fields.ttl`.

## Merge order

`rosetta validate --shapes-dir` walks recursively, sorts by path (alphabetical), and merges all `.ttl` files into a single shapes graph. Override IRIs are additive — they don't overwrite generated shapes; they add new constraints.
