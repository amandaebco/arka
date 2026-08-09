"""Detection scoring — the numbers a document prints must be defensible.

No model is involved here, and none ever should be. These tests pin the
formula from CLAUDE.md so a well-meaning refactor cannot quietly change what
ARKA considers worth reporting.
"""

from decimal import Decimal

from app.detection.scoring import (
    THRESHOLD_AMBIGUITY,
    THRESHOLD_IGNORE,
    THRESHOLD_REPORT,
    Decision,
    ScoreBreakdown,
    component_match,
    corroboration,
    decide,
    recency,
    symptom_overlap,
)


class TestSymptomOverlap:
    def test_full_overlap(self):
        assert symptom_overlap(["a", "b"], ["a", "b"]) == Decimal("1.0000")

    def test_partial_overlap(self):
        assert symptom_overlap(["a"], ["a", "b"]) == Decimal("0.5000")

    def test_extra_current_symptoms_do_not_penalise(self):
        # The denominator is the historical set on purpose: a past case whose
        # every symptom reappears today is a strong match even if today shows
        # more besides.
        assert symptom_overlap(["a", "b", "c"], ["a", "b"]) == Decimal("1.0000")

    def test_no_overlap(self):
        assert symptom_overlap(["x"], ["a", "b"]) == Decimal("0.0000")

    def test_empty_history_scores_zero_not_error(self):
        # Missing symptom records are common; they must not stop detection.
        assert symptom_overlap(["a"], []) == Decimal("0.0000")

    def test_case_and_whitespace_insensitive(self):
        assert symptom_overlap([" a "], ["A"]) == Decimal("1.0000")


class TestComponentMatch:
    def test_same_component(self):
        assert component_match("SEAL", "SEAL") == Decimal("1.0")

    def test_same_subsystem(self):
        peta = {"SEAL": "filling_head", "KATUP": "filling_head"}
        assert component_match("SEAL", "KATUP", peta) == Decimal("0.5")

    def test_unrelated_component(self):
        peta = {"SEAL": "filling_head", "BRG": "drive"}
        assert component_match("SEAL", "BRG", peta) == Decimal("0.0")

    def test_missing_component_is_unrelated(self):
        assert component_match(None, "SEAL") == Decimal("0.0")

    def test_without_subsystem_map_only_exact_matches(self):
        assert component_match("SEAL", "KATUP") == Decimal("0.0")


class TestCorroboration:
    def test_saturates_at_three_cases(self):
        assert corroboration(3) == Decimal("1.0000")
        assert corroboration(9) == Decimal("1.0000")

    def test_partial(self):
        assert corroboration(1) == Decimal("0.3333")
        assert corroboration(2) == Decimal("0.6667")

    def test_no_cases(self):
        assert corroboration(0) == Decimal("0.0000")


class TestRecency:
    def test_today_is_full_weight(self):
        assert recency(0) == Decimal("1.0000")

    def test_half_life(self):
        assert recency(365) == Decimal("0.5000")

    def test_decays_monotonically(self):
        assert recency(30) > recency(200) > recency(900)

    def test_old_evidence_still_counts(self):
        # Age reduces weight; it never disqualifies a case outright.
        assert recency(1095) > Decimal("0")


class TestScoreBreakdown:
    def test_perfect_case_scores_one(self):
        s = ScoreBreakdown(Decimal(1), Decimal(1), Decimal(1), Decimal(1))
        assert s.total == Decimal("1.0000")

    def test_weighted_parts_sum_to_total(self):
        s = ScoreBreakdown(
            Decimal("1.0"), Decimal("0.5"), Decimal("0.6667"), Decimal("0.8")
        )
        assert sum(s.weighted_parts.values()) == s.total

    def test_symptom_overlap_dominates(self):
        # Half the weight sits on symptom overlap; the demo narrative rests on
        # that, so a refactor that rebalances it should fail here.
        strong_symptoms = ScoreBreakdown(Decimal(1), Decimal(0), Decimal(0), Decimal(0))
        everything_else = ScoreBreakdown(Decimal(0), Decimal(1), Decimal(1), Decimal(1))
        assert strong_symptoms.total == Decimal("0.5000")
        assert everything_else.total == Decimal("0.5000")


class TestDecide:
    def test_clear_winner_is_reported(self):
        v = decide([Decimal("0.91"), Decimal("0.40")])
        assert v.decision is Decision.REPORT
        assert not v.needs_human

    def test_close_pair_escalates(self):
        v = decide([Decimal("0.91"), Decimal("0.87")])
        assert v.decision is Decision.ESCALATE
        assert v.margin == Decimal("0.0400")
        assert v.needs_human

    def test_margin_exactly_at_threshold_escalates(self):
        v = decide([Decimal("0.90"), Decimal("0.85")])
        assert v.margin == THRESHOLD_AMBIGUITY
        assert v.decision is Decision.ESCALATE

    def test_weak_candidates_are_ignored(self):
        v = decide([Decimal("0.40"), Decimal("0.38")])
        assert v.decision is Decision.IGNORE

    def test_close_but_both_weak_is_ignored_not_escalated(self):
        # Two equally poor explanations are not a dilemma worth a human's time.
        v = decide([Decimal("0.49"), Decimal("0.48")])
        assert v.decision is Decision.IGNORE

    def test_middle_band_escalates(self):
        v = decide([Decimal("0.60")])
        assert v.decision is Decision.ESCALATE

    def test_no_candidates(self):
        v = decide([])
        assert v.decision is Decision.IGNORE
        assert v.top_score == Decimal("0.0000")

    def test_single_strong_candidate_reports(self):
        v = decide([Decimal("0.80")])
        assert v.decision is Decision.REPORT
        assert v.runner_up_score is None
        assert v.margin is None

    def test_thresholds_match_documented_values(self):
        assert (THRESHOLD_REPORT, THRESHOLD_IGNORE, THRESHOLD_AMBIGUITY) == (
            Decimal("0.65"),
            Decimal("0.50"),
            Decimal("0.05"),
        )
