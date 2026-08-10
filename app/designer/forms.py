"""Which visual forms a card's data can actually carry.

The knowledge base has seventeen visualisation patterns, and each one already
states the data it needs — `requires_data`, `when_to_use`, `when_to_avoid`, all
written in terms of the data's shape rather than the block's name. Nothing read
any of it. The designer chose forms from its own judgement, and on the runs where
it hesitated it sent `{}`: seven of eight cards drawn as plain text lists.

So the fix is not a default form per block. That would be the same mistake the
section model already avoids — structure follows the data, not the label on the
box. Here the same rule applies one level down: a card's form is whatever its
own items can fill.

The filter is deliberately strict. A pattern whose fields the canvas cannot
supply is not offered at all, which is what keeps a page from inventing what it
lacks: `timeline` needs dates, and a causal chain that carries none stops being
offered a timeline — the exact trap that had a live page printing four invented
timestamps.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from app.designer.content import CanvasItem

# Patterns that furnish the page rather than fill a card. They are composed
# elsewhere — the identity chips under the title, the confidence marker in the
# footer — and offering them as a card form would draw them twice.
PAGE_FURNITURE = frozenset({"identity_band", "confidence_encoding"})


def _numeric(value: str) -> bool:
    """Whether a value is a number, not merely a non-empty string.

    A citation locator — "hlm. 3, §2.1" — is text that happens to contain digits.
    Treating it as numeric offered the citations card a KPI-card treatment, which
    would have drawn a page-number as a headline figure.
    """
    cleaned = value.strip().replace(".", "").replace(",", ".")
    try:
        float(cleaned)
    except ValueError:
        return False
    return True


# The knowledge base names the fields a pattern needs in its own vocabulary,
# because it was written to describe infographics rather than our canvas. Each
# name maps to a question about the items in hand.
#
# Names absent from this table are listed in UNSUPPLIED: the canvas genuinely has
# no such field. A comparison needs a baseline to compare against, a gauge needs
# the labels of every grade, a KPI target needs the target. Offering those anyway
# is how a page ends up drawing a scale nobody supplied — an absent field is a
# closed door, not a detail to fill in later.
FIELD_TESTS: dict[str, Callable[[Sequence[CanvasItem]], bool]] = {
    "measured": lambda items: all(_numeric(i.value) for i in items),
    "reference": lambda items: all(_numeric(i.reference) for i in items),
    "bucket_labels": lambda items: all(i.label for i in items),
    "counts": lambda items: all(_numeric(i.quantity) for i in items),
    "focus_statement": lambda items: all(i.text for i in items),
    "finding_label": lambda items: all(i.label for i in items),
    "finding_text": lambda items: all(i.text for i in items),
    "risk_name": lambda items: all(i.label for i in items),
    "level": lambda items: all(i.level for i in items),
    "dimension_label": lambda items: all(i.label for i in items),
    "status_value": lambda items: all(i.value or i.level for i in items),
    "date_or_period": lambda items: all(i.date for i in items),
    "current_or_planned": lambda items: all(_numeric(i.value) for i in items),
}

# Fields the canvas has no equivalent for at all.
UNSUPPLIED = frozenset(
    {"parts", "total", "current_rating", "scale_labels", "target", "direction"}
)


def _fits(pattern: dict[str, Any], items: Sequence[CanvasItem]) -> bool:
    needs = pattern.get("requires_data")
    if not needs:
        # A pattern that states no requirement makes no promise about the data
        # either; it is not a safe thing to offer sight unseen.
        return False

    count = len(items)
    if count < int(needs.get("min_items", 1)):
        return False
    if needs.get("max_items") is not None and count > int(needs["max_items"]):
        return False

    if needs.get("numeric_values") and not all(_numeric(i.value) for i in items):
        return False

    for field in needs.get("required_fields") or []:
        if field in UNSUPPLIED:
            return False
        test = FIELD_TESTS.get(field)
        if test is None or not test(items):
            return False

    return True


def applicable_forms(items: Sequence[CanvasItem], kb: Any) -> list[str]:
    """Every visual form this card's own data can fill, in knowledge-base order.

    Returns an empty list when nothing fits — a card with one bare sentence has
    no shape to take, and saying so is better than dressing it in one.
    """
    if not items:
        return []

    fits: list[str] = []
    for name in kb.list_visualizations():
        if name in PAGE_FURNITURE:
            continue
        try:
            pattern = kb.get_visualization(name)
        except KeyError:  # pragma: no cover — registry and files are validated on load
            continue
        if _fits(pattern, items):
            fits.append(name)

    return fits
