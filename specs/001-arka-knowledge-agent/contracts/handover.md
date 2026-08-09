# Module Handover Contracts

**Date**: 2026-08-09 · **Plan**: [../plan.md](../plan.md)

ARKA has no framework and no message bus. Modules hand over through two things:
a session-state key and a typed object. That is the whole contract surface, and
keeping it that small is what makes each module replaceable.

---

## `scout → investigator`

**Medium**: session state, key `kasus_terpilih`

**Payload**: list of open failure identifiers, ranked, each with the score that
earned its place.

```python
[
    {
        "failure_event_id": "FE-KASUS-HIDUP-UTARA",
        "equipment_tag": "PLT-U/FIL-207",
        "plant": "Pabrik Utara",
        "top_score": Decimal("0.9230"),
        "decision": "escalate",
    },
]
```

**Rules**

- Scout never explains *why* a cause is likely — that is the investigator's work.
  It reports only that a case clears the bar.
- Cases scoring below `THRESHOLD_IGNORE` are omitted, and the count of omitted
  cases is reported. Silence about what was skipped would make the filter
  unfalsifiable.
- An empty list is a valid, successful outcome. A quiet fleet is good news, not
  a failure to find something.

---

## `investigator → reporter`

**Medium**: session state, key `finding`

**Payload**: `app/reporting/finding.py::Finding`, serialised with
`model_dump(mode="json")`.

**Rules**

- The reporter already reads this key and requires no change (proven in
  production on Cloud Run). Anything that breaks this contract breaks a working
  system — treat the key name as fixed.
- Every number in `Finding` originates from `app/detection/`. The investigator
  may choose *which* candidates to include; it may not adjust their scores.
- `alasan_eskalasi` is written in Indonesian because it is printed verbatim in
  the memo. This is the documented exception to the English-everywhere rule.
- If a section cannot be gathered — no spare part linked, no document found — the
  field is left empty rather than guessed (FR-019). The document simply omits the
  block, since empty blocks are filtered downstream.

---

## `investigator → human` (escalation)

**Medium**: the published document itself.

Escalation is not a separate channel. When `Verdict.needs_human` is true, the
finding carries `perlu_eskalasi=True` and the reporter is instructed to lead with
the competing candidates. The reader sees the disagreement at the top of the
memo, with both candidates' evidence and citations intact.

There is deliberately no "auto-resolve after N hours" path. An unresolved
escalation stays unresolved until a person decides.
