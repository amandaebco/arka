# Quickstart — Proving the Detection and Investigation Chain

**Date**: 2026-08-09 · **Plan**: [plan.md](./plan.md)

This is the validation guide, not an implementation guide. It states what must be
true for the chain to be considered working, and the commands that show it.

## Prerequisites

```bash
uv sync --all-extras
docker compose up -d                       # PostgreSQL 16 + AGE + pgvector
uv run alembic upgrade head                # 40 canonical tables
uv run python -m app.synthetic.generator --reset
```

The generator seeds the golden path: five plants running one filler model, four
resolved historical cases across four plants, one open case at Pabrik Utara, and
a single-vendor seal with a six-week lead time carrying a low static criticality.

## Level 1 — Deterministic core, no database, no model

```bash
uv run pytest tests/test_detection_scoring.py -q
```

**Expected**: all pass. This layer is the one an assessor is most likely to
challenge, and it must be provable without any infrastructure at all.

## Level 2 — Query layer against the seeded graph

```bash
uv run pytest tests/test_detection_repository.py -q
```

**Expected**:

- The open case at `PLT-U/FIL-207` is found.
- Candidate causes are grouped, each carrying its supporting historical cases
  from **other** plants.
- Symptom overlap differs between candidates — if every candidate scores an
  identical overlap, the seeded data has stopped discriminating and the demo's
  central claim is hollow. This was a real defect on 6 August; the test exists so
  it cannot return unnoticed.

## Level 3 — Finding assembly, no model

```bash
uv run pytest tests/test_investigation.py -q
```

**Expected**: a `Finding` whose candidates are ranked, whose precedents name
other plants, and whose `perlu_eskalasi` matches what `decide()` concluded.

## Level 4 — The chain, end to end

```bash
uv run python scripts/run_chain.py            # scout → investigator → reporter
```

**Expected**: a PDF artifact for the Pabrik Utara case, containing a candidate
table whose numbers match those printed by Level 3, and citations to the seeded
inspection documents.

**The check that matters**: open the document and compare one score against the
output of Level 3. They must be identical characters, not merely close. If they
differ, a number has passed through something it should not have.

## Level 5 — Cloud

```bash
# https://arka-110352541672.us-central1.run.app — already live
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
     https://arka-110352541672.us-central1.run.app/list-apps
```

**Expected**: the agent list includes the investigation entry point, and running
the same case there produces the same numbers as locally.

## What "done" means for this slice

- [ ] An open failure is discovered without anyone naming it.
- [ ] At least one candidate is supported by cases from more than one other plant.
- [ ] The ambiguous pair escalates, and the memo leads with both candidates.
- [ ] At least one case is correctly **ignored**, with the reason available.
- [ ] Every number in the document can be traced to `app/detection/`.
