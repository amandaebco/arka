# Phase 1 Data Model — Detection and Investigation Chain

**Date**: 2026-08-09 · **Plan**: [plan.md](./plan.md)

This slice **reads** existing canonical tables and **produces** one in-memory
object. No migration is required, and nothing is written back to the graph
(Principle III).

---

## Entities read

| Entity | Table | Fields the chain relies on |
|---|---|---|
| Failure event | `failure_events` | `id`, `equipment_id`, `component_id`, `started_at`, `status`, `downtime_minutes`, `description` |
| Symptom link | `failure_event_symptoms` | `failure_event_id`, `symptom_id`, `severity` |
| Symptom | `symptoms` | `code`, `name` |
| Verified cause | `failure_event_causes` | `failure_event_id`, `cause_id`, `verified_at`, `is_primary` |
| Cause | `causes` | `canonical_id`, `code`, `name`, `category` |
| Damage | `damages` | `failure_event_id`, `component_id`, `damage_type`, `description` |
| Equipment | `equipment` | `tag_number`, `model`, `production_line_id` |
| Plant | `plants` via `production_lines` | `name` |
| Work order | `work_orders` | `description`, `completed_at` — carries the resolution text |
| Spare part | `spare_parts` | `part_number`, `name`, `static_criticality`, `lead_time_weeks`, `vendor_count` |
| Document | `documents` + `document_versions` + `document_chunks` | `canonical_id`, `title`, `document_type`, `extracted_text` |

**Open case**: a `failure_events` row with `status` in (`open`, `under_investigation`).

**Historical case**: a `failure_events` row with `status` = `closed` **and** at
least one verified cause. A closed case without a verified cause teaches nothing
and is excluded — this is a deliberate filter, not an oversight.

---

## Entities produced

### `CandidateEvidence` (new, `app/detection/repository.py`)

Raw material for one candidate cause, gathered before scoring. Kept separate from
the scored form so that gathering and judging remain independently testable.

| Field | Type | Notes |
|---|---|---|
| `cause_canonical_id` | `str` | Groups historical cases into one candidate |
| `cause_name` | `str` | Printed verbatim; never rephrased by a model |
| `historical_cases` | `list[HistoricalCase]` | One per supporting failure event |
| `documents` | `list[DocumentRef]` | Deduplicated across the cases |

### `HistoricalCase`

| Field | Type | Notes |
|---|---|---|
| `failure_event_id` | `str` | |
| `plant` | `str` | The cross-plant claim rests on this |
| `equipment_tag` | `str` | |
| `occurred_on` | `date` | Feeds `recency` |
| `symptom_codes` | `list[str]` | Feeds `symptom_overlap` |
| `component_code` | `str \| None` | Feeds `component_match` |
| `resolution` | `str \| None` | The proven fix, from the work order |
| `downtime_minutes` | `int \| None` | |

### `ScoredCandidate` (new, `app/detection/investigation.py`)

`CandidateEvidence` plus its `ScoreBreakdown`. The bridge between the
deterministic core and the reporting contract.

**Validation rules**

- A candidate with zero historical cases is never constructed.
- Scores are `Decimal`, quantised to four places, in `[0, 1]`.
- Candidate order is by `total` descending, then `cause_canonical_id` ascending —
  the tiebreak exists so a demo run twice produces an identical document.

---

## Handover shape

The chain terminates in `Finding` (`app/reporting/finding.py`), which already
exists and does not change. The mapping is direct:

| `Finding` field | Source |
|---|---|
| `kandidat` | `ScoredCandidate` list, ranked |
| `preseden` | `HistoricalCase` list, cross-plant only |
| `rantai_kausal` | Symptom → Cause → Damage → Part, from the top candidate |
| `sparepart` | `spare_parts` joined through the damaged component |
| `perlu_eskalasi` | `Verdict.needs_human` |
| `alasan_eskalasi` | `Verdict.reason` — Indonesian, since it is printed in the memo |
| `jejak_penalaran` | Steps recorded by `investigator` as it traverses |
| `keyakinan` | Derived from `Verdict.top_score` against the thresholds |

**State transitions**: none persisted. An investigation exists for the duration of
a session; its durable outputs are the artifact documents.
