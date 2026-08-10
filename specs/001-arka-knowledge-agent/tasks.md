# Tasks: Detection and Investigation Chain

**Feature**: 001-arka-knowledge-agent · **Plan**: [plan.md](./plan.md) · **Date**: 2026-08-09

**Scope**: Only the missing slice. The reporting layer, `reporter`, `designer`, and
the quality reviewer are installed and proven in production; they generate no tasks
here. Every task below is written so it can be picked up without further context.

**Language**: New code, comments, and prompts in English. Strings that reach a
published document stay Indonesian — that exception is deliberate and load-bearing.

---

## Phase 1 — Setup

- [X] T001 Create `app/detection/` package with `__init__.py`
- [X] T002 Implement scoring components, weights, thresholds, and `decide()` in `app/detection/scoring.py`
- [X] T003 [P] Cover the scoring formula without a database or a model in `tests/test_detection_scoring.py`

## Phase 2 — Foundational (blocks every story below)

- [X] T004 Add async session helper for read-only detection queries in `app/detection/repository.py`, reusing `app/db/session.py` rather than opening a second engine
- [X] T005 Implement `find_open_cases()` in `app/detection/repository.py` returning open failure events with equipment tag, plant, symptom codes, and component code
- [X] T006 Implement `find_historical_cases()` in `app/detection/repository.py` returning closed events that have a verified cause, joined to plant, symptoms, component, resolution text from the work order, and downtime
- [X] T007 Implement `load_subsystem_map()` in `app/detection/repository.py` so `component_match` can award partial credit for same-subsystem components
- [X] T008 Implement `find_documents_for_cases()` in `app/detection/repository.py` returning citable documents per failure event, deduplicated by canonical id
- [X] T009 [P] Define `HistoricalCase` and `CandidateEvidence` dataclasses in `app/detection/repository.py` per [data-model.md](./data-model.md)
- [X] T010 Verify the query layer against the seeded golden path in `tests/test_detection_repository.py`, including the regression that symptom overlap must differ between candidates

## Phase 3 — User Story 1: Cross-plant precedent (P1)

**Goal**: An open failure is matched to resolved cases in other plants, with the
proven fix and its citation attached.

**Independent test**: Seed the database, run the investigation for the open case at
`PLT-U/FIL-207`, and confirm precedents from at least two other plants appear with
their resolutions and document references.

- [X] T011 [US1] Implement `group_candidates()` in `app/detection/investigation.py` grouping historical cases by verified cause into `CandidateEvidence`
- [X] T012 [US1] Implement `score_candidate()` in `app/detection/investigation.py` combining `CandidateEvidence` with `app/detection/scoring.py` into a `ScoredCandidate`, ranked by total then canonical id so repeated runs are identical
- [X] T013 [US1] Implement `build_finding()` in `app/detection/investigation.py` mapping scored candidates, precedents, and citations onto `app/reporting/finding.py::Finding`
- [X] T014 [P] [US1] Cover finding assembly from fixtures, without a database, in `tests/test_investigation.py`
- [X] T015 [US1] Create `app/agents/investigator.py` with tools `list_open_cases`, `investigate_case`, and `record_reasoning_step`, writing the result to session state key `finding`
- [X] T016 [US1] Write the investigator prompt in English, instructing traversal order and forbidding it from restating or recomputing any score
- [X] T017 [P] [US1] Cover investigator tool behaviour without a model in `tests/test_investigator_agent.py`, including the case where a section is unavailable and must degrade to empty rather than fail (FR-019)
- [X] T018 [US1] Add `scripts/run_chain.py` running investigator then reporter against the seeded database, printing the artifact path

**Checkpoint**: `Finding` is produced from real data; the existing reporter turns it
into a PDF with no change to reporting code. SC-001 and SC-006 become measurable.

## Phase 4 — User Story 3: Acknowledged uncertainty (P2)

**Goal**: When two candidates cannot be separated, ARKA says so instead of picking.

**Independent test**: Run the golden-path case and confirm the memo leads with both
competing candidates and carries the escalation banner.

- [X] T019 [US3] Measure the real margin between the top two candidates by running the chain, and record the observed values in [research.md](./research.md)
- [X] T020 [US3] Adjust seeded symptom sets or case dates in `app/synthetic/jalur_emas.py` until the margin falls within `THRESHOLD_AMBIGUITY` — never adjust weights or thresholds, which are published policy
- [X] T021 [US3] Assert the golden path escalates in `tests/test_investigation.py`, pinning the calibration so a later data edit cannot silently break the demo's most interesting moment
- [X] T022 [P] [US3] Add a case that is correctly ignored — scoring below `THRESHOLD_IGNORE` — to `app/synthetic/jalur_emas.py`, so the filter is falsifiable rather than merely permissive

**Checkpoint**: SC-004 is demonstrable, and ARKA can be shown declining to raise
something as readily as raising it.

## Phase 5 — User Story 1 continued: Scout (P1)

**Goal**: Nobody names the case. Scout scans the fleet and decides what is worth a
human's attention.

**Independent test**: Run scout against the seeded database and confirm it returns
the Pabrik Utara case, omits cases below threshold, and reports how many it skipped.

- [X] T023 [US1] Implement `screen_open_cases()` in `app/detection/investigation.py` scoring every open case and returning the ranked shortlist described in [contracts/handover.md](./contracts/handover.md)
- [X] T024 [US1] Create `app/agents/scout.py` with tools `scan_fleet` and `explain_skip`, writing the shortlist to session state key `kasus_terpilih`
- [X] T025 [US1] Write the scout prompt in English, making clear that an empty shortlist is a valid successful outcome and never grounds for lowering the bar
- [X] T026 [P] [US1] Cover scout tool behaviour without a model in `tests/test_scout_agent.py`, including the empty-shortlist case and the skipped-count report
- [X] T027 [US1] Chain scout ahead of investigator in `scripts/run_chain.py` and expose the chain through `adk_agents/` for the served runtime

**Checkpoint**: The demo can open on autonomous screening rather than on a
hand-picked case — the framing that answers "you planted the finding".

## Phase 6 — Polish & cross-cutting

- [X] T028 [P] Record observed scores and the calibration outcome in `CLAUDE.md` so the next session does not re-derive them
- [X] T029 [P] Resolve the FR-015 divergence noted in [research.md](./research.md): amend the requirement or restore the alternative render path
- [X] T030 Verify Level 4 of [quickstart.md](./quickstart.md) — one score in the published PDF matches the value printed by the investigation, character for character
- [X] T031 Deploy the updated image and confirm the chain produces identical numbers on Cloud Run (SC-007)

---

## Dependencies

```text
Phase 1 (done) → Phase 2 → Phase 3 (US1 core) → Phase 5 (Scout)
                                ↓
                          Phase 4 (US3 escalation)
                                ↓
                          Phase 6 (polish)
```

- Phase 2 blocks everything; nothing can be scored without data to score.
- Phase 4 depends on Phase 3 only because the margin cannot be measured until the
  chain runs. It does not depend on Scout.
- Phase 5 can start once T012 exists — screening reuses candidate scoring.

## Parallel opportunities

- T009 alongside T005–T008: dataclasses are independent of the queries that fill them.
- T014 and T017 alongside their implementation tasks: different files.
- T022 alongside T019–T021: seeding a new ignorable case touches only the golden-path
  constants.
- T028 and T029 are documentation and can proceed while T030 runs.

## Implementation strategy

**MVP is Phase 2 + Phase 3.** That alone closes the chain: an open failure in the
database becomes a published PDF with cross-plant precedent and citations, with no
human naming the case beyond starting the run. Everything after that sharpens the
story rather than creating it.

If time runs short, cut in this order: T031 (cloud parity), T022 (ignored case),
T027 (served chain). Do not cut T019–T021 — the escalation moment is the part of
the demo that cannot be reconstructed from a screenshot.
