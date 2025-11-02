"""Tests for pick_best_window_for_candidate function."""

from datetime import datetime, timedelta, timezone

from clepsy.modules.sessions.tasks import pick_best_window_for_candidate


def ts(base: datetime, minutes: int) -> datetime:
    """Helper to create timestamp offset from base."""
    return base + timedelta(minutes=minutes)


class TestPickBestWindowForCandidate:
    """Tests for pick_best_window_for_candidate function."""

    def test_no_activities(self):
        """Test with empty activity arrays."""
        result = pick_best_window_for_candidate(
            starts=[],
            ends=[],
            secs=[],
            ids=[],
            candidate_ids={1, 2, 3},
            min_activities=2,
            min_purity=0.7,
            min_length=timedelta(minutes=10),
            max_gap=timedelta(minutes=5),
        )
        assert result is None

    def test_no_matching_candidate_activities(self):
        """Test when none of the activities match candidate_ids."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)

        result = pick_best_window_for_candidate(
            starts=[ts(base, 0), ts(base, 10)],
            ends=[ts(base, 10), ts(base, 20)],
            secs=[600.0, 600.0],  # 10 minutes each
            ids=[1, 2],
            candidate_ids={99, 100},  # No matching IDs
            min_activities=1,
            min_purity=0.5,
            min_length=timedelta(minutes=5),
            max_gap=timedelta(minutes=5),
        )
        assert result is None

    def test_single_valid_window(self):
        """Test with a single valid window meeting all constraints."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)

        result = pick_best_window_for_candidate(
            starts=[ts(base, 0), ts(base, 10), ts(base, 20)],
            ends=[ts(base, 10), ts(base, 20), ts(base, 30)],
            secs=[600.0, 600.0, 600.0],  # 10 min each
            ids=[1, 2, 3],
            candidate_ids={1, 2, 3},  # All match
            min_activities=3,
            min_purity=0.9,
            min_length=timedelta(minutes=25),
            max_gap=timedelta(minutes=5),
        )

        assert result is not None
        assert result.L == 0
        assert result.R == 2
        assert result.chosen_ids == [1, 2, 3]
        assert result.start == ts(base, 0)
        assert result.end == ts(base, 30)

    def test_purity_constraint(self):
        """Test that windows below purity threshold are rejected."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)

        # Window: 0-30 minutes
        # Candidate activities (1, 3): 10 + 10 = 20 minutes
        # Non-candidate activity (2): 10 minutes
        # Purity = 20/30 = 0.67 < 0.7
        result = pick_best_window_for_candidate(
            starts=[ts(base, 0), ts(base, 10), ts(base, 20)],
            ends=[ts(base, 10), ts(base, 20), ts(base, 30)],
            secs=[600.0, 600.0, 600.0],
            ids=[1, 2, 3],
            candidate_ids={1, 3},  # Missing 2
            min_activities=2,
            min_purity=0.7,  # Too high
            min_length=timedelta(minutes=20),
            max_gap=timedelta(minutes=5),
        )

        assert result is None

    def test_min_activities_constraint(self):
        """Test that windows with too few candidate activities are rejected."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)

        result = pick_best_window_for_candidate(
            starts=[ts(base, 0), ts(base, 10)],
            ends=[ts(base, 10), ts(base, 20)],
            secs=[600.0, 600.0],
            ids=[1, 2],
            candidate_ids={1},  # Only 1 activity
            min_activities=2,  # Requires 2
            min_purity=0.5,
            min_length=timedelta(minutes=5),
            max_gap=timedelta(minutes=5),
        )

        assert result is None

    def test_min_length_constraint(self):
        """Test that windows shorter than min_length are rejected."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)

        result = pick_best_window_for_candidate(
            starts=[ts(base, 0), ts(base, 5)],
            ends=[ts(base, 5), ts(base, 10)],
            secs=[300.0, 300.0],  # 5 min each
            ids=[1, 2],
            candidate_ids={1, 2},
            min_activities=2,
            min_purity=0.9,
            min_length=timedelta(minutes=15),  # Span is only 10 min
            max_gap=timedelta(minutes=5),
        )

        assert result is None

    def test_max_gap_constraint_violation(self):
        """Test that windows with gaps > max_gap between candidate activities are rejected."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)

        # Activities: 1 @ 0-10, 2 @ 20-30 (10-minute gap)
        result = pick_best_window_for_candidate(
            starts=[ts(base, 0), ts(base, 20)],
            ends=[ts(base, 10), ts(base, 30)],
            secs=[600.0, 600.0],
            ids=[1, 2],
            candidate_ids={1, 2},
            min_activities=2,
            min_purity=0.6,
            min_length=timedelta(minutes=20),
            max_gap=timedelta(minutes=5),  # Gap is 10 min > 5 min
        )

        assert result is None

    def test_max_gap_constraint_passing(self):
        """Test that windows with acceptable gaps pass."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)

        # Activities: 1 @ 0-10, 2 @ 12-22 (2-minute gap, acceptable)
        result = pick_best_window_for_candidate(
            starts=[ts(base, 0), ts(base, 12)],
            ends=[ts(base, 10), ts(base, 22)],
            secs=[600.0, 600.0],
            ids=[1, 2],
            candidate_ids={1, 2},
            min_activities=2,
            min_purity=0.8,
            min_length=timedelta(minutes=20),
            max_gap=timedelta(minutes=5),
        )

        assert result is not None
        assert result.chosen_ids == [1, 2]

    def test_selects_longest_duration_window(self):
        """Test that among valid windows, the longest duration is selected."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)

        # Two possible windows:
        # Window 1: activities 1-2 (0-20 min, 20 min span)
        # Window 2: activities 1-3 (0-30 min, 30 min span) - should win
        result = pick_best_window_for_candidate(
            starts=[ts(base, 0), ts(base, 10), ts(base, 20)],
            ends=[ts(base, 10), ts(base, 20), ts(base, 30)],
            secs=[600.0, 600.0, 600.0],
            ids=[1, 2, 3],
            candidate_ids={1, 2, 3},
            min_activities=2,
            min_purity=0.9,
            min_length=timedelta(minutes=15),
            max_gap=timedelta(minutes=5),
        )

        assert result is not None
        assert result.R == 2  # Includes all three activities
        assert result.dur_s == 30 * 60  # 30-minute span

    def test_purity_tiebreaker(self):
        """Test that when durations are equal, higher purity wins."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)

        # Window ending at activity 2: purity = 1200/1200 = 1.0
        # Window ending at activity 3: includes non-candidate 4, lower purity
        # Both have same span, but first has higher purity
        result = pick_best_window_for_candidate(
            starts=[ts(base, 0), ts(base, 10), ts(base, 20), ts(base, 30)],
            ends=[ts(base, 10), ts(base, 20), ts(base, 30), ts(base, 40)],
            secs=[600.0, 600.0, 600.0, 600.0],
            ids=[1, 2, 3, 4],
            candidate_ids={1, 2},  # Only first two are candidates
            min_activities=2,
            min_purity=0.5,
            min_length=timedelta(minutes=15),
            max_gap=timedelta(minutes=15),
        )

        assert result is not None
        # Should select window with just activities 1 and 2 (higher purity)
        assert result.chosen_ids == [1, 2]

    def test_partial_candidate_coverage(self):
        """Test window with mix of candidate and non-candidate activities."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)

        result = pick_best_window_for_candidate(
            starts=[ts(base, 0), ts(base, 10), ts(base, 20), ts(base, 30)],
            ends=[ts(base, 10), ts(base, 20), ts(base, 30), ts(base, 40)],
            secs=[600.0, 600.0, 600.0, 600.0],
            ids=[1, 2, 3, 4],
            candidate_ids={1, 3},  # 2 and 4 are not candidates
            min_activities=2,
            min_purity=0.4,  # Low enough to allow mix
            min_length=timedelta(minutes=25),
            max_gap=timedelta(minutes=15),
        )

        assert result is not None
        assert result.chosen_ids == [1, 3]
        # Should span from 0 to 30 (L=0, R=2) but only include ids 1 and 3

    def test_overlapping_activities(self):
        """Test with overlapping activity times."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)

        # Activity 2 overlaps with both 1 and 3
        result = pick_best_window_for_candidate(
            starts=[ts(base, 0), ts(base, 5), ts(base, 10)],
            ends=[ts(base, 10), ts(base, 15), ts(base, 20)],
            secs=[600.0, 600.0, 600.0],
            ids=[1, 2, 3],
            candidate_ids={1, 2, 3},
            min_activities=3,
            min_purity=0.9,
            min_length=timedelta(minutes=15),
            max_gap=timedelta(minutes=5),
        )

        assert result is not None
        assert result.chosen_ids == [1, 2, 3]

    def test_zero_duration_span_rejected(self):
        """Test that zero or negative duration spans are handled."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)

        # All activities at the same time (edge case)
        result = pick_best_window_for_candidate(
            starts=[ts(base, 10), ts(base, 10)],
            ends=[ts(base, 10), ts(base, 10)],
            secs=[0.0, 0.0],
            ids=[1, 2],
            candidate_ids={1, 2},
            min_activities=2,
            min_purity=0.5,
            min_length=timedelta(minutes=1),
            max_gap=timedelta(minutes=5),
        )

        # Should fail min_length constraint
        assert result is None

    def test_large_window_with_gaps(self):
        """Test window with multiple candidate activities and acceptable gaps."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)

        # Activities with 2-min gaps between them
        result = pick_best_window_for_candidate(
            starts=[ts(base, 0), ts(base, 12), ts(base, 24), ts(base, 36)],
            ends=[ts(base, 10), ts(base, 22), ts(base, 34), ts(base, 46)],
            secs=[600.0, 600.0, 600.0, 600.0],
            ids=[1, 2, 3, 4],
            candidate_ids={1, 2, 3, 4},
            min_activities=4,
            min_purity=0.85,
            min_length=timedelta(minutes=40),
            max_gap=timedelta(minutes=3),
        )

        assert result is not None
        assert result.chosen_ids == [1, 2, 3, 4]
        assert len(result.chosen_ids) == 4

    def test_gap_only_between_candidate_activities(self):
        """Test that gap checking only considers candidate activities."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)

        # Candidate 1 @ 0-10, Non-candidate 2 @ 10-20, Candidate 3 @ 20-30
        # Gap between candidates 1 and 3 is 10 min (through non-candidate)
        # But algorithm should only check gaps between consecutive CANDIDATE activities
        result = pick_best_window_for_candidate(
            starts=[ts(base, 0), ts(base, 10), ts(base, 20)],
            ends=[ts(base, 10), ts(base, 20), ts(base, 30)],
            secs=[600.0, 600.0, 600.0],
            ids=[1, 2, 3],
            candidate_ids={1, 3},  # Skip 2
            min_activities=2,
            min_purity=0.6,
            min_length=timedelta(minutes=20),
            max_gap=timedelta(minutes=5),  # Gap between 1 and 3 is 10 min
        )

        # Should fail because gap between candidate activities (1 end @ 10, 3 start @ 20) is 10 min
        assert result is None
