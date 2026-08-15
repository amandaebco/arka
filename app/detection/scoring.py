"""Detection scoring — deterministic, explainable, and never touched by a model.

This module is the foundation of ARKA's credibility. Every number a document
shows about *why* a case was raised originates here, computed from graph facts
alone. A language model may decide which path to explore next; it never decides
how strong the evidence is.

The formula is fixed in CLAUDE.md and must stay explainable on a whiteboard:

    symptom_overlap  0.50   |current symptoms ∩ historical| / |historical|
    component_match  0.20   1.0 same component · 0.5 same subsystem
    corroboration    0.20   min(similar cases / 3, 1.0)
    recency          0.10   decay by case age

    >= 0.65 report · gap between top two <= 0.05 escalate · < 0.50 ignore

`Decimal` is used throughout rather than `float`: these values are printed in
official documents, and a score that renders as 0.6499999 undermines the whole
claim that numbers come straight from data.

Traceability: spec 001 FR-002, FR-003 · tasks T002, T003.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum

# Component weights. They sum to 1.0 — asserted below so a future edit that
# breaks the sum fails at import time rather than silently skewing every score.
WEIGHT_SYMPTOM_OVERLAP = Decimal("0.50")
WEIGHT_COMPONENT_MATCH = Decimal("0.20")
WEIGHT_CORROBORATION = Decimal("0.20")
WEIGHT_RECENCY = Decimal("0.10")

_WEIGHTS = (
    WEIGHT_SYMPTOM_OVERLAP,
    WEIGHT_COMPONENT_MATCH,
    WEIGHT_CORROBORATION,
    WEIGHT_RECENCY,
)
assert sum(_WEIGHTS) == Decimal("1.00"), "detection weights must sum to 1.00"

# Decision thresholds.
THRESHOLD_REPORT = Decimal("0.65")
THRESHOLD_IGNORE = Decimal("0.50")
# Two candidates this close cannot be told apart by the evidence available.
# Guessing between them is worse than admitting it: they usually imply
# different repairs, and the wrong repair costs a shutdown.
THRESHOLD_AMBIGUITY = Decimal("0.05")

# Corroboration saturates here: three independent cases already establish a
# pattern, and a fourth adds little to the argument.
CORROBORATION_SATURATION = 3

# Age at which a case retains half its recency weight.
RECENCY_HALF_LIFE_DAYS = 365

# Same component scores full; same subsystem scores half. Anything else is
# treated as unrelated — a bearing failure says nothing about a filling valve.
COMPONENT_EXACT = Decimal("1.0")
COMPONENT_SUBSYSTEM = Decimal("0.5")
COMPONENT_UNRELATED = Decimal("0.0")

_QUANTUM = Decimal("0.0001")


class Decision(StrEnum):
    """What the detector concluded. Owned by code, never by a model."""

    REPORT = "report"
    ESCALATE = "escalate"
    IGNORE = "ignore"


def _clamp(value: Decimal) -> Decimal:
    """Keep a component within [0, 1] and at a fixed precision."""
    if value < 0:
        value = Decimal(0)
    elif value > 1:
        value = Decimal(1)
    return value.quantize(_QUANTUM)


def symptom_overlap(current: Iterable[str], historical: Iterable[str]) -> Decimal:
    """Share of the historical case's symptoms that are present now.

    The denominator is the *historical* set, not the union, and that choice
    carries meaning: a past case whose every symptom reappears today is a
    strong match even if today's failure shows extra symptoms as well. Using
    the union would punish richer current observations, which is backwards.

    A historical case with no recorded symptoms scores zero rather than raising:
    missing data is common in maintenance records and must not stop detection.
    """
    past = {s.strip().upper() for s in historical if s and s.strip()}
    if not past:
        return Decimal("0.0000")
    now = {s.strip().upper() for s in current if s and s.strip()}
    return _clamp(Decimal(len(now & past)) / Decimal(len(past)))


def component_match(
    current: str | None,
    historical: str | None,
    subsystem_of: dict[str, str] | None = None,
) -> Decimal:
    """How closely the affected components correspond.

    Args:
        current: Component identifier for the open failure.
        historical: Component identifier for the past case.
        subsystem_of: Maps component identifier to the subsystem it belongs to.
            Without it, only exact matches can be recognised.
    """
    if not current or not historical:
        return COMPONENT_UNRELATED
    if current.strip().upper() == historical.strip().upper():
        return COMPONENT_EXACT

    if subsystem_of:
        lookup = {k.strip().upper(): v.strip().upper() for k, v in subsystem_of.items()}
        here = lookup.get(current.strip().upper())
        there = lookup.get(historical.strip().upper())
        if here and there and here == there:
            return COMPONENT_SUBSYSTEM
    return COMPONENT_UNRELATED


def corroboration(similar_case_count: int) -> Decimal:
    """How many independent cases support the same explanation."""
    if similar_case_count <= 0:
        return Decimal("0.0000")
    return _clamp(Decimal(similar_case_count) / Decimal(CORROBORATION_SATURATION))


def recency(age_days: int, half_life_days: int = RECENCY_HALF_LIFE_DAYS) -> Decimal:
    """Decay a case's weight by its age.

    Older evidence still counts — equipment does not forget how it fails — but
    a failure from last month says more about the current fleet than one from
    three years ago, when the maintenance regime may have been different.

    Halving per `half_life_days` is used instead of a cliff so that no case
    changes category simply because a demo ran a day later.
    """
    if age_days <= 0:
        return Decimal("1.0000")
    try:
        decayed = Decimal(2) ** (Decimal(-age_days) / Decimal(half_life_days))
    except (InvalidOperation, OverflowError):  # pragma: no cover — extreme ages
        return Decimal("0.0000")
    return _clamp(decayed)


@dataclass(frozen=True)
class ScoreBreakdown:
    """A candidate's score, component by component.

    Kept as a breakdown rather than a single number because the document shows
    every part: a reader who disagrees with the conclusion must be able to see
    which component carried it.
    """

    symptom_overlap: Decimal
    component_match: Decimal
    corroboration: Decimal
    recency: Decimal

    @property
    def total(self) -> Decimal:
        weighted = (
            self.symptom_overlap * WEIGHT_SYMPTOM_OVERLAP
            + self.component_match * WEIGHT_COMPONENT_MATCH
            + self.corroboration * WEIGHT_CORROBORATION
            + self.recency * WEIGHT_RECENCY
        )
        return weighted.quantize(_QUANTUM)

    @property
    def weighted_parts(self) -> dict[str, Decimal]:
        """Each component's contribution to the total, as printed in documents."""
        return {
            "symptom_overlap": (self.symptom_overlap * WEIGHT_SYMPTOM_OVERLAP).quantize(_QUANTUM),
            "component_match": (self.component_match * WEIGHT_COMPONENT_MATCH).quantize(_QUANTUM),
            "corroboration": (self.corroboration * WEIGHT_CORROBORATION).quantize(_QUANTUM),
            "recency": (self.recency * WEIGHT_RECENCY).quantize(_QUANTUM),
        }


@dataclass(frozen=True)
class Verdict:
    """The detector's conclusion, with the reason stated in plain terms."""

    decision: Decision
    top_score: Decimal
    runner_up_score: Decimal | None
    margin: Decimal | None
    reason: str

    # Whether there was anything to judge at all. Without this the two reasons
    # for ignoring a case collapse into one number: a case with no candidates
    # scores 0.0000, and so does nothing else — so a reader sees "assessed,
    # risk nil" where the truth is "nothing to assess".
    #
    # The distinction is not cosmetic. Absence of evidence reads as health, and
    # the equipment nobody records is exactly the equipment nobody is watching.
    assessable: bool = True

    @property
    def needs_human(self) -> bool:
        return self.decision is Decision.ESCALATE


def decide(scores: Sequence[Decimal]) -> Verdict:
    """Turn candidate scores into one of three outcomes.

    Order of checks matters. Ambiguity is tested **before** the report
    threshold, because two strong candidates that cannot be separated are
    precisely the case a human must rule on — reporting one of them as the
    answer would hide the disagreement.
    """
    if not scores:
        return Verdict(
            decision=Decision.IGNORE,
            top_score=Decimal("0.0000"),
            runner_up_score=None,
            margin=None,
            reason="Tidak ada kandidat penyebab yang dapat dinilai.",
            assessable=False,
        )

    ranked = sorted((Decimal(s).quantize(_QUANTUM) for s in scores), reverse=True)
    top = ranked[0]
    runner_up = ranked[1] if len(ranked) > 1 else None
    margin = (top - runner_up) if runner_up is not None else None

    if top < THRESHOLD_IGNORE:
        return Verdict(
            decision=Decision.IGNORE,
            top_score=top,
            runner_up_score=runner_up,
            margin=margin,
            reason="Kandidat terkuat berada di bawah ambang pengabaian.",
        )

    if margin is not None and margin <= THRESHOLD_AMBIGUITY and runner_up >= THRESHOLD_IGNORE:
        return Verdict(
            decision=Decision.ESCALATE,
            top_score=top,
            runner_up_score=runner_up,
            margin=margin,
            reason=(
                "Dua kandidat teratas berselisih di bawah ambang keyakinan dan "
                "menuntut tindakan berbeda."
            ),
        )

    if top >= THRESHOLD_REPORT:
        return Verdict(
            decision=Decision.REPORT,
            top_score=top,
            runner_up_score=runner_up,
            margin=margin,
            reason="Kandidat terkuat melewati ambang pelaporan tanpa pesaing dekat.",
        )

    # Between the two thresholds and unambiguous: real but not yet conclusive.
    return Verdict(
        decision=Decision.ESCALATE,
        top_score=top,
        runner_up_score=runner_up,
        margin=margin,
        reason="Bukti cukup untuk diperhatikan, belum cukup untuk disimpulkan.",
    )
