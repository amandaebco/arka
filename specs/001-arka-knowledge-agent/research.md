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

**Measured on 10 August**, after the chain ran against the seeded database:

| Candidate | Supporting cases | Total | Note |
|---|---|---|---|
| Seal degradation | Barat, Timur | 0.9073 | same component |
| Torque deviation | Barat, Selatan, Tengah | 0.8821 | same subsystem |

Margin **0.0252**, inside the escalation band. Reaching it required seeding a
third torque precedent: with two, the margin was 0.0919 and the escalation never
fired. The lever was the data, as planned — weights and thresholds untouched.

**Original expectation** (recorded before measurement):

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

## 3. Spec/implementation divergence — resolved

FR-015 required an alternative render path; the implementation had deliberately
removed it. **Resolved on 10 August by amending the requirement**, not by
restoring the fallback: evidence documents inform maintenance decisions, and an
HTML file that looks official but is not is more dangerous than a visible
failure. With Chromium in the image, PDF is available everywhere, so the
fallback had lost its reason to exist. See the amendment note in `spec.md`.
