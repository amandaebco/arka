"""Dynamic spare-part criticality — the number master data does not have.

Master data assigns a criticality once, when the material is registered, and it
is rarely revisited. ARKA recomputes it from what actually happened to the fleet:

    criticality = 0.40·failure_probability + 0.35·consequence + 0.25·supply_risk

The value on its own is unremarkable. What matters is the **difference** against
`static_criticality`, because that difference is the thing nobody is looking at:
a part the register calls unimportant, which the fleet's own history says will
stop five plants for six weeks.

Every input is a recorded fact. Nothing here consults a model.
"""

from __future__ import annotations

from decimal import Decimal

WEIGHT_FAILURE_PROBABILITY = Decimal("0.40")
WEIGHT_CONSEQUENCE = Decimal("0.35")
WEIGHT_SUPPLY_RISK = Decimal("0.25")

assert (
    WEIGHT_FAILURE_PROBABILITY + WEIGHT_CONSEQUENCE + WEIGHT_SUPPLY_RISK == Decimal("1.00")
), "criticality weights must sum to 1.00"

# A part implicated in this many failures across the fleet is treated as fully
# failure-prone. Three matches the corroboration saturation used in detection —
# the same reasoning applies: a pattern is established, not merely suggested.
FAILURE_SATURATION = 3

# Downtime at which consequence is considered total. Two full shifts of a filling
# line is already a serious production loss; beyond that the score should not
# keep climbing, or one catastrophic outlier would flatten every comparison.
CONSEQUENCE_SATURATION_MINUTES = 960

# Lead time at which supply risk is considered total. Six weeks is the golden
# path's single-vendor seal, and it is the point where a failure stops being a
# repair and becomes a shutdown.
SUPPLY_SATURATION_WEEKS = 6

_QUANTUM = Decimal("0.0001")


def _clamp(value: Decimal) -> Decimal:
    if value < 0:
        value = Decimal(0)
    elif value > 1:
        value = Decimal(1)
    return value.quantize(_QUANTUM)


def failure_probability(implicated_case_count: int) -> Decimal:
    """How often this part has actually been involved in failures."""
    if implicated_case_count <= 0:
        return Decimal("0.0000")
    return _clamp(Decimal(implicated_case_count) / Decimal(FAILURE_SATURATION))


def consequence(total_downtime_minutes: int | None) -> Decimal:
    """How much production was lost when it did fail."""
    if not total_downtime_minutes or total_downtime_minutes <= 0:
        return Decimal("0.0000")
    return _clamp(
        Decimal(total_downtime_minutes) / Decimal(CONSEQUENCE_SATURATION_MINUTES)
    )


def supply_risk(lead_time_weeks: int | None, vendor_count: int | None) -> Decimal:
    """How hard it is to obtain a replacement.

    Lead time and sole sourcing compound rather than average: a long lead time
    from one supplier is a different situation from a long lead time with three
    alternatives, and treating them alike is exactly the blind spot in static
    criticality that ARKA exists to expose.
    """
    lead = Decimal(lead_time_weeks or 0) / Decimal(SUPPLY_SATURATION_WEEKS)
    lead = _clamp(lead)

    # A single vendor carries full sourcing risk; each alternative halves it.
    count = max(int(vendor_count or 1), 1)
    sourcing = _clamp(Decimal(1) / Decimal(count))

    # Weighted so lead time leads: waiting is what actually stops the line.
    return _clamp(lead * Decimal("0.6") + sourcing * Decimal("0.4"))


def dynamic_criticality(
    *,
    implicated_case_count: int,
    total_downtime_minutes: int | None,
    lead_time_weeks: int | None,
    vendor_count: int | None,
) -> Decimal:
    """Combine the three components into the score ARKA publishes."""
    return (
        failure_probability(implicated_case_count) * WEIGHT_FAILURE_PROBABILITY
        + consequence(total_downtime_minutes) * WEIGHT_CONSEQUENCE
        + supply_risk(lead_time_weeks, vendor_count) * WEIGHT_SUPPLY_RISK
    ).quantize(_QUANTUM)


DAYS_PER_WEEK = 7


def procurement_shortfall(
    lead_time_weeks: int | None, days_until_window: int | None
) -> int | None:
    """Days by which procurement misses the next maintenance window.

    Returns a positive number when the part cannot arrive in time, zero or a
    negative number when it can, and None when the comparison cannot be made at
    all — no lead time recorded, or no maintenance scheduled.

    None is deliberately distinct from "no problem". Maintenance schedules and
    material lead times usually live in two systems that never speak, so the
    absence of a schedule is the normal case, not evidence of headroom. Reading
    it as safety is exactly how this conflict stays invisible until the window
    is missed.
    """
    if not lead_time_weeks or days_until_window is None:
        return None
    return lead_time_weeks * DAYS_PER_WEEK - days_until_window
