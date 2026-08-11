"""Counts and scales derived from the canvas, never from the page.

Two visualisation patterns went unused because the canvas carried no shape they
could take. `donut_status` needs parts that sum to a whole; `gauge_rating` needs
every grade on the scale, not just the one in force. A card holding a flat list
of items supplies neither, so both stayed closed — correctly, because offering a
pattern whose data is missing is how a page ends up inventing a scale.

The way to open them is to compute the missing shape here rather than to relax
the filter. Counting how many recommendations fall in each horizon is
arithmetic, and arithmetic belongs in code: Principle I objects to a model
producing figures, not to figures existing.

Two rules keep these honest. A distribution must account for every item on the
card, because a donut whose parts do not sum to the whole misstates the split it
claims to show. And a scale must come from a vocabulary the system already
fixes — confidence has exactly three grades — never from grades invented to fill
the arc.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.designer.content import CanvasItem

# Categorical fields an item may be grouped by, in the order they are tried.
# `level` says how severe, `horizon` says how soon; both partition a card
# cleanly, while free text does not.
GROUPABLE = ("level", "horizon")

MIN_PARTS = 2
MAX_PARTS = 3

# Confidence is the one graded scale ARKA fixes. Ordered weakest to strongest so
# a gauge can be drawn without the page deciding which way the arc runs.
#
# These are the canvas keys, not the words printed on the page: the content layer
# translates the finding's Indonesian into this vocabulary, and the knowledge base
# keys its wording by the same names. Reading the finding's vocabulary here is how
# the first version of this silently returned None for every finding.
CONFIDENCE_GRADES = ("low", "medium", "high")


def distribution(items: Sequence[CanvasItem]) -> tuple[list[tuple[str, int]], int] | None:
    """Group a card's items into parts that sum to the whole card.

    Returns `(parts, total)` or None when no field groups the items cleanly.
    Every item must carry the field: a split that silently omits the items it
    could not classify would draw a whole that is not whole.
    """
    if len(items) < MIN_PARTS:
        return None

    for field in GROUPABLE:
        nilai = [getattr(one, field, "") for one in items]
        if not all(nilai):
            continue

        hitung: dict[str, int] = {}
        for satu in nilai:
            hitung[satu] = hitung.get(satu, 0) + 1

        if MIN_PARTS <= len(hitung) <= MAX_PARTS:
            parts = sorted(hitung.items(), key=lambda p: (-p[1], p[0]))
            return parts, len(items)

    return None


def confidence_scale(keyakinan: str) -> tuple[list[str], str] | None:
    """The full confidence scale and the grade currently in force.

    Returns None for a value outside the fixed vocabulary rather than inventing
    a place for it on the arc.
    """
    grade = (keyakinan or "").strip().lower()
    if grade not in CONFIDENCE_GRADES:
        return None
    return list(CONFIDENCE_GRADES), grade
