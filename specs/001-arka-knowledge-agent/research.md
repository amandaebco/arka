# Phase 0 Research — Detection and Investigation Chain

**Date**: 2026-08-09 · **Plan**: [plan.md](./plan.md)

Two unknowns blocked the design. Both are resolved below; nothing in the plan
still carries a NEEDS CLARIFICATION marker.

---

## 1. Where traversal happens: canonical SQL or AGE Cypher

**Decision**: Query canonical tables with SQLAlchemy for this slice. Keep the AGE
projection for depth beyond it.

**Rationale**: Every relationship the golden path needs is one or two joins away —
failure → symptoms, failure → verified cause, failure → equipment → plant,
cause → damage → component → spare part. A cross-plant precedent query over these
tables was proven to return correct results on 6 August, before any agent existed.

Introducing Cypher on the critical path two days before submission adds a second
query dialect, a projection step that must run before every demo, and a failure
mode (stale projection) that produces *silently wrong* results rather than an
error. The traversal power it buys — arbitrary-depth paths — is not exercised by
the demo narrative.

**Alternatives considered**:

- *AGE Cypher for everything*: rejected for the reasons above. Reconsider when a
  question genuinely needs unbounded depth, e.g. "what else shares this batch of
  material across the fleet".
- *Hybrid, Cypher only for precedent search*: rejected as the worst of both — two
  dialects to maintain for one query that SQL already answers.

**Consequence recorded honestly**: the pitch should not claim graph traversal
depth the chain does not use. What ARKA does claim — cross-plant precedent
discovery over a knowledge graph — is true of the canonical layer as well, and
the AGE projection remains part of the system for questions beyond this slice.

---

## 2. Calibrating the ambiguous pair to a margin ≤ 0.05

**Decision**: Calibrate by measurement once the repository layer can produce real
candidate scores, then adjust the *data* in `app/synthetic/jalur_emas.py` — never
the weights — until the top two land within the escalation band.

**Rationale**: On 6 August this calibration was deliberately deferred, because
tuning data against a formula that had not been implemented would have meant
tuning against an assumption. The scorer now exists and is tested, so the numbers
can be observed rather than guessed.

Adjusting weights to force an escalation would be backwards: the weights encode
what ARKA believes matters about reliability evidence, and bending them to
produce a nicer demo would make every other score dishonest. The data is
synthetic by design and may legitimately be shaped; the scoring policy may not.

**Expected shape** (from the seeded golden path, to be confirmed by measurement):

| Candidate | Supporting cases | Component relation to open case |
|---|---|---|
| Seal degradation | Barat, Timur | same component (SEAL) |
| Torque deviation | Selatan, Tengah | same subsystem (KATUP) |

The seal candidate leads on component match; the torque candidate has equal
corroboration and better recency. Whether the resulting margin falls inside
0.05 is an empirical question — if it does not, the lever is the seeded symptom
sets and case dates.

**Alternatives considered**:

- *Hand-write the escalating pair into `Finding`*: rejected. It would make the
  most interesting moment of the demo a fixture rather than a result, and an
  assessor who asks "what if the dates were different" would get no answer.
- *Lower `THRESHOLD_AMBIGUITY` until the pair qualifies*: rejected for the same
  reason as reweighting — the threshold is policy, published in CLAUDE.md and the
  constitution.

---

## 3. Note on an existing spec/implementation divergence

FR-015 states the system MUST publish in an alternative form when the primary
renderer is unavailable. The implementation deliberately removed that fallback on
7 August: `terbitkan_dokumen` now fails loudly instead of handing a reader an
HTML file that looks official but is not.

That decision was later made moot — Chromium is baked into the image and PDF
rendering works on Cloud Run — but the requirement and the code still disagree.
This is out of scope for this plan and is recorded here so it is not lost:
**FR-015 should be amended or the fallback restored**, and the choice belongs to
the spec, not to a passing refactor.
