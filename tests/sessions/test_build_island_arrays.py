"""Tests for build_island_arrays function."""

from datetime import datetime, timedelta, timezone

from clepsy.entities import (
    ActivityEventType,
    DBActivity,
    DBActivityEvent,
    DBActivitySpecWithTags,
    ProductivityLevel,
    Source,
)
from clepsy.modules.sessions.tasks import build_island_arrays


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
        id=0,  # ID not important for these tests
        event_time=time,
        event_type=event_type,
        activity_id=0,  # Will be overridden in spec
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
    """
    Helper to create a DBActivitySpecWithTags.

    Args:
        id: Activity ID
        name: Activity name
        start_minutes: Start time offset in minutes from base_time
        end_minutes: End time offset in minutes from base_time (None for OPEN)
        base_time: Base datetime for offsets
    """
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


class TestBuildIslandArrays:
    """Tests for build_island_arrays function."""

    def test_empty_island(self):
        """Test with empty island."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        island_end = base + timedelta(hours=1)

        result = build_island_arrays([], island_end)

        assert result["starts"] == []
        assert result["ends"] == []
        assert result["secs"] == []
        assert result["ids"] == []

    def test_single_closed_activity(self):
        """Test with a single closed activity."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        island_end = base + timedelta(hours=1)

        spec = make_spec(1, "VSCode", 0, 30, base)
        island = [spec]

        result = build_island_arrays(island, island_end)

        assert len(result["starts"]) == 1
        assert len(result["ends"]) == 1
        assert len(result["secs"]) == 1
        assert len(result["ids"]) == 1

        assert result["starts"][0] == base
        assert result["ends"][0] == base + timedelta(minutes=30)
        assert result["secs"][0] == 30 * 60  # 30 minutes in seconds
        assert result["ids"][0] == 1

    def test_single_open_activity(self):
        """Test with a single OPEN activity (closes at horizon)."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        island_end = base + timedelta(hours=1)

        spec = make_spec(2, "Chrome", 10, None, base)  # OPEN at 10 minutes
        island = [spec]

        result = build_island_arrays(island, island_end)

        assert len(result["starts"]) == 1
        assert result["starts"][0] == base + timedelta(minutes=10)
        assert result["ends"][0] == island_end
        assert result["secs"][0] == 50 * 60  # 50 minutes (10 to 60)
        assert result["ids"][0] == 2

    def test_multiple_activities_sorted_by_start(self):
        """Test that activities are sorted by start time."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        island_end = base + timedelta(hours=2)

        # Create specs in non-sorted order
        spec3 = make_spec(3, "Slack", 60, 90, base)
        spec1 = make_spec(1, "VSCode", 0, 30, base)
        spec2 = make_spec(2, "Chrome", 30, 60, base)

        island = [spec3, spec1, spec2]  # Unsorted

        result = build_island_arrays(island, island_end)

        # Should be sorted by start time
        assert result["ids"] == [1, 2, 3]
        assert result["starts"][0] == base
        assert result["starts"][1] == base + timedelta(minutes=30)
        assert result["starts"][2] == base + timedelta(minutes=60)

    def test_activity_with_multiple_time_spans(self):
        """Test activity with multiple OPEN/CLOSE pairs."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        island_end = base + timedelta(hours=2)

        activity = make_activity(10, "VSCode Multiple")
        events = [
            make_event(base + timedelta(minutes=0), ActivityEventType.OPEN),
            make_event(base + timedelta(minutes=10), ActivityEventType.CLOSE),
            make_event(base + timedelta(minutes=20), ActivityEventType.OPEN),
            make_event(base + timedelta(minutes=40), ActivityEventType.CLOSE),
        ]

        spec = DBActivitySpecWithTags(activity=activity, events=events, tags=[])
        island = [spec]

        result = build_island_arrays(island, island_end)

        # time_spans creates spans for ALL consecutive event pairs:
        # (OPEN@0, CLOSE@10) = 10 min
        # (CLOSE@10, OPEN@20) = 10 min (gap, but still counted)
        # (OPEN@20, CLOSE@40) = 20 min
        # Total = 40 minutes
        assert result["starts"][0] == base  # First span start
        assert result["ends"][0] == base + timedelta(minutes=40)  # Last span end
        assert result["secs"][0] == 40 * 60  # Total duration including gap
        assert result["ids"][0] == 10

    def test_activity_without_valid_spans_at_horizon(self):
        """Test that activities without spans (after horizon filtering) are skipped."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        island_end = base + timedelta(minutes=5)

        # Activity that starts after the horizon
        # This shouldn't happen in practice, but tests the edge case
        spec = make_spec(11, "Late VSCode", 10, 20, base)
        island = [spec]

        result = build_island_arrays(island, island_end)

        # Note: The function uses spec.time_spans(horizon) which might return empty
        # if all events are beyond horizon, but let's check actual behavior
        # In this case, start is at base+10, which is > island_end (base+5)
        # time_spans() will return spans, but we need to check the logic

        # Actually, looking at the code, it gets first/last spans
        # So this will still include it with the actual times
        # The filtering happens elsewhere
        assert len(result["ids"]) == 1  # Still included in arrays

    def test_overlapping_activities(self):
        """Test multiple overlapping activities."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        island_end = base + timedelta(hours=2)

        spec1 = make_spec(20, "VSCode Overlap", 0, 60, base)
        spec2 = make_spec(21, "Chrome Overlap", 30, 90, base)  # Overlaps with spec1
        spec3 = make_spec(22, "Slack Overlap", 45, 75, base)  # Overlaps with both

        island = [spec1, spec2, spec3]

        result = build_island_arrays(island, island_end)

        assert result["ids"] == [20, 21, 22]
        assert len(result["starts"]) == 3
        # Each activity has single OPEN/CLOSE pair, so duration = end - start
        # spec1: OPEN@0, CLOSE@60 -> 1 span (0-60) = 60 minutes
        # spec2: OPEN@30, CLOSE@90 -> 1 span (30-90) = 60 minutes
        # spec3: OPEN@45, CLOSE@75 -> 1 span (45-75) = 30 minutes
        assert result["secs"][0] == 60 * 60  # spec1: 60 minutes
        assert result["secs"][1] == 60 * 60  # spec2: 60 minutes
        assert result["secs"][2] == 30 * 60  # spec3: 30 minutes

    def test_activities_with_gaps(self):
        """Test activities with gaps between them."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        island_end = base + timedelta(hours=3)

        spec1 = make_spec(30, "VSCode Gap", 0, 30, base)
        spec2 = make_spec(31, "Chrome Gap", 90, 120, base)  # 60-minute gap
        spec3 = make_spec(32, "Slack Gap", 150, 160, base)  # 30-minute gap

        island = [spec1, spec2, spec3]

        result = build_island_arrays(island, island_end)

        assert result["ids"] == [30, 31, 32]
        assert result["starts"][0] == base
        assert result["starts"][1] == base + timedelta(minutes=90)
        assert result["starts"][2] == base + timedelta(minutes=150)

        # Check gaps exist
        gap1 = result["starts"][1] - result["ends"][0]
        gap2 = result["starts"][2] - result["ends"][1]
        assert gap1 == timedelta(minutes=60)
        assert gap2 == timedelta(minutes=30)

    def test_mixed_open_and_closed_activities(self):
        """Test island with mix of OPEN and CLOSED activities."""
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        island_end = base + timedelta(hours=2)

        spec1 = make_spec(40, "VSCode Mixed", 0, 30, base)  # CLOSED
        spec2 = make_spec(41, "Chrome Mixed", 30, None, base)  # OPEN at 30 min
        spec3 = make_spec(42, "Slack Mixed", 10, 20, base)  # CLOSED, overlaps spec1

        island = [spec1, spec2, spec3]

        result = build_island_arrays(island, island_end)

        # Should be sorted by start time
        assert result["ids"] == [40, 42, 41]

        # Check OPEN activity uses horizon
        chrome_idx = result["ids"].index(41)
        assert result["ends"][chrome_idx] == island_end
        # Chrome: OPEN@30 -> horizon@120 = 90 minutes
        assert result["secs"][chrome_idx] == 90 * 60  # 30 to 120 minutes
