# Implementation Plan: Detection and Investigation Chain

**Branch**: `feat/rantai-pelaporan` | **Date**: 2026-08-09 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-arka-knowledge-agent/spec.md`

**Scope note**: This plan covers only the slice that does not exist yet — detection
scoring, the graph query layer, `investigator`, and `scout`. The reporting layer,
`reporter`, and `designer` are installed and documented as-is under the brownfield
table in the spec; they are not re-planned here.

## Summary

`Finding` can currently only be produced by hand (`app/synthetic/finding_contoh.py`).
Everything downstream of it is finished and proven in production on Cloud Run.
What is missing is the head of the chain: something that reads open failures from
the graph, scores them against historical cases in other plants, and decides which
deserve a human's attention.

The approach keeps the split the constitution demands. A deterministic core
(`app/detection/`) computes every number and every decision boundary; the agents
above it decide only where to look next and when to stop. `investigator` writes a
`Finding` into session state under the key `reporter` already reads, so the chain
closes without touching a line of reporting code.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: Google ADK 2.x · SQLAlchemy 2 (async) · psycopg 3 ·
Pydantic 2 · google-genai (Vertex AI)

**Storage**: PostgreSQL 16 + Apache AGE + pgvector — canonical tables are the
source of truth; AGE holds a projection for multi-hop traversal

**Testing**: pytest (asyncio auto). Deterministic core tested without a database
and without a model; query layer tested against the seeded golden path

**Target Platform**: Cloud Run (live) and Vertex AI Agent Engine, same image

**Project Type**: Single Python package with an agent runtime layer

**Performance Goals**: One investigation completes within a single interactive
turn — target under 30 s wall clock, bounded by traversal limits rather than by
model latency

**Constraints**: Traversal depth and breadth must be bounded so an investigation
always terminates (FR-005). A failing data source degrades that section to empty
rather than failing the run (FR-019)

**Scale/Scope**: 5 plants on the golden path today; background volume of ~5,000
equipment and ~20,000 work orders is planned but not required for the chain to work

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | How this design satisfies it | Verdict |
|---|---|---|
| I. Deterministic numbers | All scores come from `app/detection/scoring.py`. Agents receive scores as data and may not recompute them. Tools return values already quantised to `Decimal`. | PASS |
| II. Every claim traceable | Candidates and precedents carry `Sitasi` built from `documents`/`document_chunks`. A candidate with no supporting document is still reported, but the citation list is what the memo prints — and publication without any citation is already refused downstream. | PASS |
| III. Agents never write facts | The chain is read-only against the graph. `Finding` lives in session state and becomes an artifact; nothing is written back. Curator remains out of scope here. | PASS |
| IV. Uncertainty escalates | `decide()` tests ambiguity **before** the report threshold, so two strong candidates that cannot be separated escalate rather than being resolved by rank. | PASS |
| V. Single-decision modules | `scout` decides what is worth investigating; `investigator` decides where to look next and when to stop. Neither owns block selection or visual emphasis. | PASS |
| VI. Zero client data | Synthetic only; the golden path is fictional by construction. | PASS |

**Post-design re-check**: no new violations. The one judgement call is that
`scout` and `investigator` share the same scoring module rather than each holding
a copy — this is shared *computation*, not a shared decision, so Principle V holds.

## Project Structure

### Documentation (this feature)

```text
specs/001-arka-knowledge-agent/
├── spec.md              # Existing
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── contracts/           # Phase 1 — handover contracts between modules
├── quickstart.md        # Phase 1 — how to prove the chain works
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
app/
├── detection/               # Deterministic core — no model, no agent
│   ├── scoring.py           # DONE: components, weights, decide()
│   ├── repository.py        # NEW: read open failures and historical cases
│   └── investigation.py     # NEW: assemble scored candidates into a Finding
├── agents/
│   ├── scout.py             # NEW: which failures deserve investigation
│   ├── investigator.py      # NEW: traversal steps, escalation, handover
│   ├── reporter.py          # Installed
│   ├── designer.py          # Installed
│   └── qa.py                # Installed
├── reporting/               # Installed — Finding is its only input
└── graph/                   # Installed — projection and traversal helpers

tests/
├── test_detection_scoring.py    # DONE: 30 tests, no DB, no model
├── test_detection_repository.py # NEW: against the seeded golden path
├── test_investigation.py        # NEW: Finding assembly from fixtures
└── test_scout_agent.py          # NEW: tool behaviour without a model
```

**Structure Decision**: The deterministic core lives in `app/detection/`, separate
from `app/agents/`. That boundary is the point: everything in `detection/` can be
tested without a database mock or a model call, and everything an assessor might
question about a number can be pointed at a pure function.

## Phase 0 — Research

See [research.md](./research.md). Two unknowns were resolved:

1. **Where traversal happens** — canonical SQL versus AGE Cypher for this slice.
2. **How the ambiguous pair is calibrated** — deferred from D2 on purpose, now
   measurable because the scorer exists.

## Phase 1 — Design

- [data-model.md](./data-model.md) — the entities the chain reads and the shape it
  hands over.
- [contracts/](./contracts/) — module handover contracts: `scout → investigator`
  and `investigator → reporter`.
- [quickstart.md](./quickstart.md) — the commands that prove the chain works,
  end to end, against the seeded database.

## Complexity Tracking

No constitution violations require justification.

One deliberate simplification is worth recording: this slice queries **canonical
tables** rather than the AGE projection. The projection exists and works, but the
golden path's relationships are all reachable by joins, and adding a Cypher
dependency to the critical path two days before submission buys traversal power
the demo does not use. The graph projection remains the story for multi-hop depth
beyond this slice — see research.md for the full reasoning.
