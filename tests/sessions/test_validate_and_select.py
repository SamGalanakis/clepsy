"""Tests for validate_and_select_sessions function."""

from datetime import datetime, timedelta, timezone

from clepsy.entities import (
    ActivityEventType,
    CandidateSession,
    CandidateSessionSpec,
    DBActivity,
    DBActivityEvent,
    DBActivitySpecWithTags,
    ProductivityLevel,
    Source,
)
from clepsy.modules.sessions.tasks import validate_and_select_sessions


def make_activity(id: int, name: str) -> DBActivity:
    """Helper to create a DBActivity."""
    return DBActivity(
        id=id,
        name=name,
        description=f"Test activity {name}",
        productivity_level=ProductivityLevel.NEUTRAL,
        last_manual_action_time=None,
        source=Source.AUTO,
    )


def make_event(time: datetime, event_type: ActivityEventType) -> DBActivityEvent:
    """Helper to create a DBActivityEvent."""
    return DBActivityEvent(
        id=0,
        event_time=time,
        event_type=event_type,
        activity_id=0,
        aggregation_id=None,
        last_manual_action_time=None,
    )


def make_spec(
    id: int,
    name: str,
    start_minutes: int,
    end_minutes: int | None,
    base_time: datetime,
) -> DBActivitySpecWithTags:
    """Helper to create a DBActivitySpecWithTags."""
    activity = make_activity(id, name)
    events = [
        make_event(base_time + timedelta(minutes=start_minutes), ActivityEventType.OPEN)
    ]
    if end_minutes is not None:
        events.append(
            make_event(
                base_time + timedelta(minutes=end_minutes), ActivityEventType.CLOSE
            )
        )
    return DBActivitySpecWithTags(activity=activity, events=events, tags=[])


class TestValidateAndSelectSessions:
    """Tests for validate_and_select_sessions function."""

    def test_empty_candidates(self):
        """Test with no candidate sessions."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        island = [make_spec(1, "VSCode", 0, 30, base)]

        result = validate_and_select_sessions(
            island=island,
            island_end=base + timedelta(hours=1),
            candidate_specs=[],
            min_activities=1,
            min_purity=0.7,
            min_length=timedelta(minutes=10),
            max_gap=timedelta(minutes=5),
        )

        assert result == []

    def test_empty_island(self):
        """Test with no activities in island."""
        result = validate_and_select_sessions(
            island=[],
            island_end=datetime(2024, 1, 1, tzinfo=timezone.utc),
            candidate_specs=[
                CandidateSessionSpec(
                    session=CandidateSession(name="Session 1", llm_id="s1"),
                    activity_ids=[1, 2],
                )
            ],
            min_activities=1,
            min_purity=0.7,
            min_length=timedelta(minutes=10),
            max_gap=timedelta(minutes=5),
        )

        assert result == []

    def test_single_valid_candidate(self):
        """Test with one candidate that meets all criteria."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        island = [
            make_spec(1, "VSCode", 0, 20, base),
            make_spec(2, "Terminal", 20, 40, base),
        ]

        candidate = CandidateSessionSpec(
            session=CandidateSession(name="Coding", llm_id="coding1"),
            activity_ids=[1, 2],
        )

        result = validate_and_select_sessions(
            island=island,
            island_end=base + timedelta(hours=1),
            candidate_specs=[candidate],
            min_activities=2,
            min_purity=0.9,
            min_length=timedelta(minutes=30),
            max_gap=timedelta(minutes=5),
        )

        assert len(result) == 1
        assert result[0].session.name == "Coding"
        assert result[0].activity_ids == [1, 2]

    def test_candidate_fails_min_activities(self):
        """Test candidate rejected for having too few activities."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        island = [make_spec(1, "VSCode", 0, 20, base)]

        candidate = CandidateSessionSpec(
            session=CandidateSession(name="Coding", llm_id="coding1"),
            activity_ids=[1],
        )

        result = validate_and_select_sessions(
            island=island,
            island_end=base + timedelta(hours=1),
            candidate_specs=[candidate],
            min_activities=2,  # Requires 2 but candidate has 1
            min_purity=0.7,
            min_length=timedelta(minutes=10),
            max_gap=timedelta(minutes=5),
        )

        assert result == []

    def test_candidate_fails_purity(self):
        """Test candidate rejected for low purity."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        island = [
            make_spec(1, "VSCode", 0, 10, base),  # 10 min
            make_spec(2, "Slack", 10, 30, base),  # 20 min (non-productive gap)
            make_spec(3, "VSCode", 30, 40, base),  # 10 min
        ]

        candidate = CandidateSessionSpec(
            session=CandidateSession(name="Coding", llm_id="coding1"),
            activity_ids=[1, 3],  # Only 20 min out of 40 min span
        )

        result = validate_and_select_sessions(
            island=island,
            island_end=base + timedelta(hours=1),
            candidate_specs=[candidate],
            min_activities=2,
            min_purity=0.7,  # Purity is 20/40 = 0.5 < 0.7
            min_length=timedelta(minutes=30),
            max_gap=timedelta(minutes=25),
        )

        assert result == []

    def test_candidate_fails_min_length(self):
        """Test candidate rejected for being too short."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        island = [
            make_spec(1, "VSCode", 0, 5, base),
            make_spec(2, "Terminal", 5, 10, base),
        ]

        candidate = CandidateSessionSpec(
            session=CandidateSession(name="Coding", llm_id="coding1"),
            activity_ids=[1, 2],
        )

        result = validate_and_select_sessions(
            island=island,
            island_end=base + timedelta(hours=1),
            candidate_specs=[candidate],
            min_activities=2,
            min_purity=0.9,
            min_length=timedelta(minutes=15),  # Span is only 10 min
            max_gap=timedelta(minutes=5),
        )

        assert result == []

    def test_candidate_fails_max_gap(self):
        """Test candidate rejected for having gaps that are too large."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        island = [
            make_spec(1, "VSCode", 0, 10, base),
            make_spec(2, "Terminal", 30, 40, base),  # 20-minute gap
        ]

        candidate = CandidateSessionSpec(
            session=CandidateSession(name="Coding", llm_id="coding1"),
            activity_ids=[1, 2],
        )

        result = validate_and_select_sessions(
            island=island,
            island_end=base + timedelta(hours=1),
            candidate_specs=[candidate],
            min_activities=2,
            min_purity=0.5,
            min_length=timedelta(minutes=20),
            max_gap=timedelta(minutes=10),  # Gap is 20 min > 10 min
        )

        assert result == []

    def test_multiple_non_overlapping_candidates_all_selected(self):
        """Test that multiple non-overlapping candidates are all selected."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        island = [
            make_spec(1, "VSCode", 0, 20, base),
            make_spec(2, "Terminal", 20, 40, base),
            make_spec(3, "Chrome", 50, 70, base),
            make_spec(4, "Slack", 70, 90, base),
        ]

        candidates = [
            CandidateSessionSpec(
                session=CandidateSession(name="Coding", llm_id="coding1"),
                activity_ids=[1, 2],
            ),
            CandidateSessionSpec(
                session=CandidateSession(name="Browsing", llm_id="browse1"),
                activity_ids=[3, 4],
            ),
        ]

        result = validate_and_select_sessions(
            island=island,
            island_end=base + timedelta(hours=2),
            candidate_specs=candidates,
            min_activities=2,
            min_purity=0.9,
            min_length=timedelta(minutes=30),
            max_gap=timedelta(minutes=5),
        )

        assert len(result) == 2
        result_names = {r.session.name for r in result}
        assert result_names == {"Coding", "Browsing"}

    def test_overlapping_candidates_greedy_selection_by_duration(self):
        """Test greedy selection chooses candidate with longest duration."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        island = [
            make_spec(1, "VSCode", 0, 20, base),
            make_spec(2, "Terminal", 20, 40, base),
            make_spec(3, "Debugger", 40, 60, base),
        ]

        candidates = [
            CandidateSessionSpec(
                session=CandidateSession(name="Short", llm_id="short1"),
                activity_ids=[1, 2],  # 40-minute span
            ),
            CandidateSessionSpec(
                session=CandidateSession(name="Long", llm_id="long1"),
                activity_ids=[1, 2, 3],  # 60-minute span - should win
            ),
        ]

        result = validate_and_select_sessions(
            island=island,
            island_end=base + timedelta(hours=2),
            candidate_specs=candidates,
            min_activities=2,
            min_purity=0.9,
            min_length=timedelta(minutes=30),
            max_gap=timedelta(minutes=5),
        )

        assert len(result) == 1
        assert result[0].session.name == "Long"
        assert result[0].activity_ids == [1, 2, 3]

    def test_overlapping_candidates_purity_tiebreaker(self):
        """Test that when durations are equal, higher purity wins."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        island = [
            make_spec(1, "VSCode", 0, 30, base),
            make_spec(2, "Slack", 30, 60, base),
        ]

        # Both candidates have same span (60 min) but different purity
        candidates = [
            CandidateSessionSpec(
                session=CandidateSession(name="Low Purity", llm_id="low1"),
                activity_ids=[1],  # Only 30 min of 60 min span = 0.5 purity
            ),
            CandidateSessionSpec(
                session=CandidateSession(name="High Purity", llm_id="high1"),
                activity_ids=[1, 2],  # 60 min of 60 min span = 1.0 purity
            ),
        ]

        result = validate_and_select_sessions(
            island=island,
            island_end=base + timedelta(hours=2),
            candidate_specs=candidates,
            min_activities=1,
            min_purity=0.4,
            min_length=timedelta(minutes=30),
            max_gap=timedelta(minutes=35),
        )

        assert len(result) == 1
        assert result[0].session.name == "High Purity"

    def test_greedy_selection_maximizes_coverage(self):
        """Test that greedy algorithm maximizes activity coverage."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        island = [
            make_spec(1, "A", 0, 10, base),
            make_spec(2, "B", 10, 20, base),
            make_spec(3, "C", 20, 30, base),
            make_spec(4, "D", 30, 40, base),
        ]

        candidates = [
            CandidateSessionSpec(
                session=CandidateSession(name="S1", llm_id="s1"),
                activity_ids=[1, 2, 3, 4],  # All activities
            ),
            CandidateSessionSpec(
                session=CandidateSession(name="S2", llm_id="s2"),
                activity_ids=[1, 2],  # Subset
            ),
            CandidateSessionSpec(
                session=CandidateSession(name="S3", llm_id="s3"),
                activity_ids=[3, 4],  # Other subset
            ),
        ]

        result = validate_and_select_sessions(
            island=island,
            island_end=base + timedelta(hours=2),
            candidate_specs=candidates,
            min_activities=2,
            min_purity=0.9,
            min_length=timedelta(minutes=15),
            max_gap=timedelta(minutes=5),
        )

        # Should select S1 which covers all activities
        assert len(result) == 1
        assert result[0].session.name == "S1"

    def test_multiple_windows_per_candidate(self):
        """Test that a candidate can produce multiple disjoint windows."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        island = [
            make_spec(1, "A", 0, 10, base),
            make_spec(2, "B", 10, 20, base),
            # Large gap
            make_spec(3, "C", 100, 110, base),
            make_spec(4, "D", 110, 120, base),
        ]

        # Single candidate claims all 4 activities
        candidate = CandidateSessionSpec(
            session=CandidateSession(name="Session", llm_id="s1"),
            activity_ids=[1, 2, 3, 4],
        )

        result = validate_and_select_sessions(
            island=island,
            island_end=base + timedelta(hours=3),
            candidate_specs=[candidate],
            min_activities=2,
            min_purity=0.9,
            min_length=timedelta(minutes=15),
            max_gap=timedelta(minutes=5),  # Gap of 80 min will split them
        )

        # Should generate 2 separate sessions from the same candidate
        assert len(result) == 2
        assert all(r.session.name == "Session" for r in result)

        # One session should have [1, 2], other should have [3, 4]
        activity_sets = [set(r.activity_ids) for r in result]
        assert {1, 2} in activity_sets
        assert {3, 4} in activity_sets

    def test_partial_activity_selection(self):
        """Test that candidate activities can be trimmed to valid windows."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        island = [
            make_spec(1, "A", 0, 10, base),
            make_spec(2, "B", 10, 20, base),
            make_spec(3, "C", 20, 30, base),
            # Large gap
            make_spec(4, "D", 100, 110, base),
        ]

        # Candidate claims all 4, but 4 is too far
        candidate = CandidateSessionSpec(
            session=CandidateSession(name="Session", llm_id="s1"),
            activity_ids=[1, 2, 3, 4],
        )

        result = validate_and_select_sessions(
            island=island,
            island_end=base + timedelta(hours=3),
            candidate_specs=[candidate],
            min_activities=2,
            min_purity=0.9,
            min_length=timedelta(minutes=20),
            max_gap=timedelta(minutes=5),
        )

        # Should only select the first 3 activities (4 is isolated)
        assert len(result) == 1
        assert set(result[0].activity_ids) == {1, 2, 3}

    def test_activity_in_time_order(self):
        """Test that result activity_ids are in chronological order."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        island = [
            make_spec(3, "C", 20, 30, base),
            make_spec(1, "A", 0, 10, base),
            make_spec(2, "B", 10, 20, base),
        ]

        # Provide activities in non-chronological order
        candidate = CandidateSessionSpec(
            session=CandidateSession(name="Session", llm_id="s1"),
            activity_ids=[3, 1, 2],  # Out of time order
        )

        result = validate_and_select_sessions(
            island=island,
            island_end=base + timedelta(hours=2),
            candidate_specs=[candidate],
            min_activities=3,
            min_purity=0.9,
            min_length=timedelta(minutes=25),
            max_gap=timedelta(minutes=5),
        )

        assert len(result) == 1
        # Should be reordered by time
        assert result[0].activity_ids == [1, 2, 3]
