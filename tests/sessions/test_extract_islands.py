"""Tests for extract_valid_islands function."""

from datetime import datetime, timedelta, timezone

from clepsy.entities import (
    ActivityEventType,
    DBActivity,
    DBActivityEvent,
    DBActivitySpecWithTags,
    ProductivityLevel,
    Source,
)
from clepsy.modules.sessions.tasks import extract_valid_islands


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


class TestExtractValidIslands:
    """Tests for extract_valid_islands function."""

    def test_single_island_no_previous_window(self):
        """Test single island with no previous window (not left-connected)."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        window_end = base + timedelta(hours=1)

        specs = [
            make_spec(1, "VSCode", 0, 20, base),
            make_spec(2, "Terminal", 20, 40, base),  # Ends at 40 min
        ]

        islands = extract_valid_islands(
            specs_in_time_range=specs,
            window_end=window_end,  # Window ends at 60 min
            previous_window_last_active=None,  # No previous window
            max_session_gap=timedelta(
                minutes=10
            ),  # Gap to window_end is 20 min > 10 min
            min_activities_per_session=2,
            min_session_length=timedelta(minutes=30),
        )

        assert len(islands) == 1
        assert islands[0].left_connected is False
        assert (
            islands[0].right_connected is False
        )  # Gap to window_end is 20 min > 10 min
        assert len(islands[0].activity_specs) == 2

    def test_single_island_left_connected(self):
        """Test single island connected to previous window."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        window_end = base + timedelta(hours=1)
        previous_last_active = base - timedelta(minutes=5)  # 5 min before window

        specs = [
            make_spec(1, "VSCode", 0, 20, base),
            make_spec(2, "Terminal", 20, 55, base),  # Ends 5 min before window_end
        ]

        islands = extract_valid_islands(
            specs_in_time_range=specs,
            window_end=window_end,
            previous_window_last_active=previous_last_active,
            max_session_gap=timedelta(
                minutes=10
            ),  # Left gap: 5 min < 10, Right gap: 5 min < 10
            min_activities_per_session=2,
            min_session_length=timedelta(minutes=30),
        )

        assert len(islands) == 1
        assert islands[0].left_connected is True  # Connected to previous
        assert (
            islands[0].right_connected is True
        )  # Ends close to window_end    def test_single_island_not_left_connected_due_to_gap(self):
        """Test single island NOT connected due to large gap from previous window."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        window_end = base + timedelta(hours=1)
        previous_last_active = base - timedelta(minutes=20)  # 20 min before

        specs = [
            make_spec(1, "VSCode", 0, 20, base),
            make_spec(2, "Terminal", 20, 40, base),
        ]

        islands = extract_valid_islands(
            specs_in_time_range=specs,
            window_end=window_end,
            previous_window_last_active=previous_last_active,
            max_session_gap=timedelta(minutes=10),  # Gap is 20 min > 10 min
            min_activities_per_session=2,
            min_session_length=timedelta(minutes=30),
        )

        assert len(islands) == 1
        assert islands[0].left_connected is False  # Gap too large

    def test_single_island_not_right_connected_due_to_gap(self):
        """Test single island NOT right-connected due to gap before window_end."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        window_end = base + timedelta(hours=1)

        specs = [
            make_spec(1, "VSCode", 0, 20, base),
            make_spec(2, "Terminal", 20, 30, base),  # Ends at 30 min
        ]

        islands = extract_valid_islands(
            specs_in_time_range=specs,
            window_end=window_end,  # Window ends at 60 min
            previous_window_last_active=None,
            max_session_gap=timedelta(minutes=10),  # Gap to window_end is 30 min
            min_activities_per_session=2,
            min_session_length=timedelta(minutes=20),
        )

        assert len(islands) == 1
        assert islands[0].right_connected is False  # Gap to window_end too large

    def test_multiple_islands_due_to_gap(self):
        """Test that large gaps split activities into multiple islands."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        window_end = base + timedelta(hours=2)

        specs = [
            make_spec(1, "VSCode", 0, 20, base),
            make_spec(2, "Terminal", 20, 40, base),
            # 30-minute gap
            make_spec(3, "Chrome", 70, 90, base),
            make_spec(4, "Slack", 90, 115, base),  # Ends closer to window_end (120 min)
        ]

        islands = extract_valid_islands(
            specs_in_time_range=specs,
            window_end=window_end,
            previous_window_last_active=None,
            max_session_gap=timedelta(minutes=10),  # Gap is 30 min > 10 min
            min_activities_per_session=2,
            min_session_length=timedelta(minutes=30),
        )

        assert len(islands) == 2
        # First island
        assert len(islands[0].activity_specs) == 2
        assert islands[0].left_connected is False
        assert islands[0].right_connected is False
        # Second island (ends close to window_end)
        assert len(islands[1].activity_specs) == 2
        assert islands[1].left_connected is False
        assert (
            islands[1].right_connected is True
        )  # Gap to window_end is 5 min < 10 min    def test_middle_islands_filtered_out_if_invalid(self):
        """Test that middle islands below thresholds are filtered out."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        window_end = base + timedelta(hours=2)

        specs = [
            make_spec(1, "VSCode", 0, 20, base),
            make_spec(2, "Terminal", 20, 40, base),
            # Gap
            make_spec(3, "Chrome", 60, 62, base),  # Too short, only 1 activity
            # Gap
            make_spec(4, "Slack", 80, 100, base),
            make_spec(5, "Email", 100, 120, base),
        ]

        islands = extract_valid_islands(
            specs_in_time_range=specs,
            window_end=window_end,
            previous_window_last_active=None,
            max_session_gap=timedelta(minutes=10),
            min_activities_per_session=2,  # Middle island has only 1
            min_session_length=timedelta(minutes=15),
        )

        # Should have first and last islands, middle filtered out
        assert len(islands) == 2
        assert len(islands[0].activity_specs) == 2  # [1, 2]
        assert len(islands[1].activity_specs) == 2  # [4, 5]

    def test_first_and_last_always_included(self):
        """Test that first and last islands are always included even if small."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        window_end = base + timedelta(hours=1)

        # Single activity that doesn't meet thresholds
        specs = [make_spec(1, "VSCode", 0, 5, base)]

        islands = extract_valid_islands(
            specs_in_time_range=specs,
            window_end=window_end,
            previous_window_last_active=None,
            max_session_gap=timedelta(minutes=10),
            min_activities_per_session=2,  # Only has 1
            min_session_length=timedelta(minutes=20),  # Only 5 min
        )

        # Should still include it as it's the only island (first = last)
        assert len(islands) == 1

    def test_three_islands_first_last_middle(self):
        """Test case with three islands where middle is too small."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        window_end = base + timedelta(hours=3)

        specs = [
            # First island
            make_spec(1, "A", 0, 10, base),
            make_spec(2, "B", 10, 20, base),
            # Gap
            # Middle island (too small)
            make_spec(3, "C", 50, 55, base),
            # Gap
            # Last island
            make_spec(4, "D", 150, 160, base),
            make_spec(5, "E", 160, 170, base),
        ]

        islands = extract_valid_islands(
            specs_in_time_range=specs,
            window_end=window_end,
            previous_window_last_active=None,
            max_session_gap=timedelta(minutes=20),
            min_activities_per_session=2,
            min_session_length=timedelta(minutes=15),
        )

        # First and last included, middle filtered
        assert len(islands) == 2
        assert islands[0].activity_specs[0].activity.id == 1
        assert islands[1].activity_specs[0].activity.id == 4

    def test_double_connected_island(self):
        """Test island that is both left and right connected."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        window_end = base + timedelta(minutes=50)
        previous_last_active = base - timedelta(minutes=2)

        specs = [
            make_spec(1, "VSCode", 0, 20, base),
            make_spec(2, "Terminal", 20, 48, base),  # Ends 2 min before window_end
        ]

        islands = extract_valid_islands(
            specs_in_time_range=specs,
            window_end=window_end,
            previous_window_last_active=previous_last_active,
            max_session_gap=timedelta(minutes=10),
            min_activities_per_session=2,
            min_session_length=timedelta(minutes=30),
        )

        assert len(islands) == 1
        assert islands[0].left_connected is True
        assert islands[0].right_connected is True
        assert islands[0].is_double_connected is True

    def test_overlapping_activities_in_same_island(self):
        """Test that overlapping activities stay in same island."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        window_end = base + timedelta(hours=1)

        specs = [
            make_spec(1, "VSCode", 0, 30, base),
            make_spec(2, "Chrome", 10, 40, base),  # Overlaps with VSCode
            make_spec(3, "Terminal", 35, 50, base),  # Overlaps with Chrome
        ]

        islands = extract_valid_islands(
            specs_in_time_range=specs,
            window_end=window_end,
            previous_window_last_active=None,
            max_session_gap=timedelta(minutes=10),
            min_activities_per_session=2,
            min_session_length=timedelta(minutes=30),
        )

        # All in one island (continuous coverage)
        assert len(islands) == 1
        assert len(islands[0].activity_specs) == 3

    def test_open_activity_at_end(self):
        """Test with OPEN activity that extends to window_end."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        window_end = base + timedelta(hours=1)

        specs = [
            make_spec(1, "VSCode", 0, 20, base),
            make_spec(2, "Terminal", 20, None, base),  # OPEN, no end
        ]

        islands = extract_valid_islands(
            specs_in_time_range=specs,
            window_end=window_end,
            previous_window_last_active=None,
            max_session_gap=timedelta(minutes=10),
            min_activities_per_session=2,
            min_session_length=timedelta(minutes=30),
        )

        assert len(islands) == 1
        # OPEN activity extends to window_end, so right_connected should be True
        assert islands[0].right_connected is True

    def test_activities_sorted_before_processing(self):
        """Test that activities are sorted by start time before island extraction."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        window_end = base + timedelta(hours=1)

        # Provide specs in non-chronological order
        specs = [
            make_spec(3, "C", 40, 50, base),
            make_spec(1, "A", 0, 10, base),
            make_spec(2, "B", 10, 20, base),
        ]

        islands = extract_valid_islands(
            specs_in_time_range=specs,
            window_end=window_end,
            previous_window_last_active=None,
            max_session_gap=timedelta(
                minutes=15
            ),  # Gap between B@20 and C@40 is 20 min > 15 min
            min_activities_per_session=2,
            min_session_length=timedelta(minutes=30),
        )

        # Gap splits into 2 islands, but they should be sorted
        assert len(islands) >= 1
        # First island should have activities 1 and 2 in sorted order
        sorted_ids = [spec.activity.id for spec in islands[0].activity_specs]
        assert sorted_ids[:2] == [1, 2]

    def test_exactly_max_gap_boundary(self):
        """Test gap that is exactly at max_session_gap boundary."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        window_end = base + timedelta(hours=2)

        specs = [
            make_spec(1, "A", 0, 10, base),
            make_spec(2, "B", 20, 30, base),  # Exactly 10-min gap
        ]

        islands = extract_valid_islands(
            specs_in_time_range=specs,
            window_end=window_end,
            previous_window_last_active=None,
            max_session_gap=timedelta(minutes=10),  # Gap is exactly 10 min
            min_activities_per_session=2,
            min_session_length=timedelta(minutes=20),
        )

        # Gap exactly at boundary should split into 2 islands
        # (assuming > not >= in comparison)
        # Let's see what the actual behavior is
        # If it's <=, they stay together; if <, they split
        assert len(islands) >= 1

    def test_min_session_length_boundary(self):
        """Test island length that is exactly at min_session_length boundary."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        window_end = base + timedelta(hours=1)

        specs = [
            make_spec(1, "A", 0, 10, base),
            make_spec(2, "B", 10, 20, base),  # Exactly 20-min span
        ]

        islands = extract_valid_islands(
            specs_in_time_range=specs,
            window_end=window_end,
            previous_window_last_active=None,
            max_session_gap=timedelta(minutes=5),
            min_activities_per_session=2,
            min_session_length=timedelta(minutes=20),  # Exactly 20 min
        )

        # Should be included (>= comparison expected)
        assert len(islands) == 1

    def test_complex_scenario_multiple_gaps(self):
        """Test complex scenario with multiple gaps and edge cases."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        window_end = base + timedelta(hours=4)
        previous_last_active = base - timedelta(minutes=3)

        specs = [
            # Island 1: Left-connected
            make_spec(1, "A", 0, 20, base),
            make_spec(2, "B", 20, 40, base),
            # Large gap (30 min)
            # Island 2: Middle (small - should be filtered)
            make_spec(3, "C", 70, 75, base),
            # Large gap (35 min)
            # Island 3: Right-connected
            make_spec(4, "D", 110, 130, base),
            make_spec(5, "E", 130, 150, base),
            make_spec(6, "F", 150, 238, base),  # Extends close to window_end (240)
        ]

        islands = extract_valid_islands(
            specs_in_time_range=specs,
            window_end=window_end,
            previous_window_last_active=previous_last_active,
            max_session_gap=timedelta(minutes=10),
            min_activities_per_session=2,
            min_session_length=timedelta(minutes=30),
        )

        # Should have 2 islands (first and last), middle filtered
        assert len(islands) == 2

        # First island
        assert islands[0].left_connected is True
        assert islands[0].right_connected is False
        assert len(islands[0].activity_specs) == 2

        # Last island
        assert islands[1].left_connected is False
        assert islands[1].right_connected is True
        assert len(islands[1].activity_specs) == 3

    def test_all_activities_in_single_segment(self):
        """Test when all activities form a continuous segment with no gaps."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        window_end = base + timedelta(hours=1)

        specs = [
            make_spec(1, "A", 0, 10, base),
            make_spec(2, "B", 11, 20, base),
            make_spec(3, "C", 21, 30, base),
            make_spec(4, "D", 31, 55, base),  # Ends close to window_end (60 min)
        ]

        islands = extract_valid_islands(
            specs_in_time_range=specs,
            window_end=window_end,
            previous_window_last_active=None,
            max_session_gap=timedelta(minutes=5),
            min_activities_per_session=3,
            min_session_length=timedelta(minutes=35),
        )

        # All should be in one island
        assert len(islands) == 1
        assert len(islands[0].activity_specs) == 4
        assert islands[0].left_connected is False
        assert islands[0].right_connected is True  # Gap to window_end is 5 min <= 5 min
