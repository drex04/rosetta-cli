# Phase 15 Context

## Decisions

- [review] Error handling in cli(): wrap per-row findings loop in try/except Exception; on error append LintFinding(rule="parse_error", severity="INFO") and continue; JSON report is always written regardless of exception.
- [review] unit_not_detected rule used for both cases (detect_unit=None AND UNIT_STRING_TO_IRI=None) with distinct messages. Same rule name, different message text.
- [review] _DATETIME_MIN renamed to DATETIME_MIN (public) in accredit.py; Task 3 handles rename + suggest.py import update.
- [review] import rdflib is retained after RDF path deletion — required for _check_units type annotation.
- [review] All four check_sssom_proposals finding types use source_uri=row.subject_id, target_uri=row.object_id.
- [review] --sssom option: exists=True, file_okay=True, dir_okay=False.
- [review] The audit log (append_log) is intentionally 9-column; subject_datatype/object_datatype not persisted to audit log (by design).
- [review] _NUMERIC_LINKML = {"integer", "int", "float", "double", "decimal", "long", "short", "nonNegativeInteger", "positiveInteger"}.

## Deferred Ideas

- unit_no_iri_mapping as a distinct rule name for step 4 (UNIT_STRING_TO_IRI=None) — deferred, same rule+distinct messages is sufficient for v1.
- Persisting subject_datatype/object_datatype to the audit log — deferred, only proposal-file lint needs them.
- Additional lint rules (circular mappings, confidence thresholds, label language consistency) — deferred post-v2.
