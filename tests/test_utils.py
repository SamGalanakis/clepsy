from datetime import datetime, timedelta, timezone

import pytest

from clepsy.entities import ActivityEvent, ActivityEventType, TimeSpan
from clepsy.utils import (
    calculate_activity_gaps,
    calculate_duration,
    extract_islands,
    overlapping_subarray_split,
    parse_mm_ss_string,
    truncate_words,
)


@pytest.mark.parametrize(
    ("text", "max_words", "expected"),
    [
        ("alpha beta gamma", 2, "alpha beta"),
        ("foo\tbar baz", 2, "foo\tbar"),
        ("multiple   spaces here", 2, "multiple   spaces"),
    ],
)
def test_truncate_words_truncates_at_word_limit(text, max_words, expected):
    assert truncate_words(text, max_words) == expected


def test_truncate_words_returns_original_when_under_limit():
    text = "alpha beta   "
    assert truncate_words(text, 5) == text


@pytest.mark.parametrize(
    ("text", "max_words"),
    [("alpha", 0), ("alpha", -1), ("", 1)],
)
def test_truncate_words_input_assertions(text, max_words):
    with pytest.raises(AssertionError):
        truncate_words(text, max_words)


@pytest.mark.parametrize(
    "input_str, expected_output",
    [
        ("02m30s", (2, 30)),
        ("2m30s", (2, 30)),
        ("2m3s", (2, 3)),
        ("0m0s", (0, 0)),
        ("59m59s", (59, 59)),
        ("7m7s", (7, 7)),
        ("59m0s", (59, 0)),
        ("0m59s", (0, 59)),
    ],
)
def test_parse_mm_ss_string_valid(input_str, expected_output):
    assert parse_mm_ss_string(input_str) == expected_output


@pytest.mark.parametrize(
    "invalid_input",
    [
        "230s",
        "2m30",
        "abc",
        "2m30s_extra",
        "60m00s",
        "00m60s",
        "-1m00s",
        "00m-1s",
        "1m 1s",
        "1m1 s",
        "1 m 1 s",
        "m1s",
        "1ms",
    ],
)
def test_parse_mm_ss_string_invalid(invalid_input):
    with pytest.raises(ValueError):
        parse_mm_ss_string(invalid_input)


def test_calculate_duration_basic():
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)

    def ts(minutes: int) -> datetime:
        return base + timedelta(minutes=minutes)

    events = [
        ActivityEvent(event_time=ts(0), event_type=ActivityEventType.OPEN),
        ActivityEvent(event_time=ts(5), event_type=ActivityEventType.CLOSE),
        ActivityEvent(event_time=ts(10), event_type=ActivityEventType.OPEN),
        ActivityEvent(event_time=ts(20), event_type=ActivityEventType.CLOSE),
    ]

    duration = calculate_duration(events, window_start=None, window_end=ts(25))

    assert duration == timedelta(minutes=15)


def test_calculate_duration_with_window_start():
    base = datetime(2024, 1, 2, tzinfo=timezone.utc)

    def ts(minutes: int) -> datetime:
        return base + timedelta(minutes=minutes)

    events = [
        ActivityEvent(event_time=ts(-10), event_type=ActivityEventType.OPEN),
        ActivityEvent(event_time=ts(5), event_type=ActivityEventType.CLOSE),
    ]

    duration = calculate_duration(events, window_start=ts(0), window_end=ts(10))

    assert duration == timedelta(minutes=5)


def test_calculate_duration_open_interval_to_window_end():
    base = datetime(2024, 1, 3, tzinfo=timezone.utc)

    def ts(minutes: int) -> datetime:
        return base + timedelta(minutes=minutes)

    events = [
        ActivityEvent(event_time=ts(0), event_type=ActivityEventType.OPEN),
    ]

    duration = calculate_duration(events, window_start=None, window_end=ts(30))

    assert duration == timedelta(minutes=30)


def test_calculate_duration_invalid_window():
    base = datetime(2024, 1, 4, tzinfo=timezone.utc)

    events = [
        ActivityEvent(event_time=base, event_type=ActivityEventType.OPEN),
        ActivityEvent(
            event_time=base + timedelta(minutes=5), event_type=ActivityEventType.CLOSE
        ),
    ]

    with pytest.raises(ValueError):
        calculate_duration(
            events,
            window_start=base + timedelta(minutes=10),
            window_end=base,
        )


def test_calculate_activity_gaps_basic():
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)

    def ts(minutes: int) -> datetime:
        return base + timedelta(minutes=minutes)

    def ev(minutes: int, event_type: ActivityEventType) -> ActivityEvent:
        return ActivityEvent(event_time=ts(minutes), event_type=event_type)

    events = [
        [
            ev(0, ActivityEventType.OPEN),
            ev(5, ActivityEventType.CLOSE),
            ev(10, ActivityEventType.OPEN),
            ev(15, ActivityEventType.CLOSE),
        ],
        [
            ev(2, ActivityEventType.OPEN),
            ev(3, ActivityEventType.CLOSE),
        ],
    ]

    max_gap, gap_percentage = calculate_activity_gaps(
        events,
        window_end=ts(15),
    )

    assert max_gap == timedelta(minutes=5)
    assert gap_percentage == pytest.approx(5 / 15)


def test_calculate_activity_gaps_with_window_bounds():
    base = datetime(2024, 2, 1, tzinfo=timezone.utc)

    def ts(minutes: int) -> datetime:
        return base + timedelta(minutes=minutes)

    def ev(minutes: int, event_type: ActivityEventType) -> ActivityEvent:
        return ActivityEvent(event_time=ts(minutes), event_type=event_type)

    events = [
        [
            ev(-30, ActivityEventType.OPEN),
            ev(3, ActivityEventType.CLOSE),
        ],
        [
            ev(7, ActivityEventType.OPEN),
            ev(9, ActivityEventType.CLOSE),
        ],
    ]

    window_start = ts(0)
    window_end = ts(10)

    max_gap, gap_percentage = calculate_activity_gaps(
        events,
        window_start=window_start,
        window_end=window_end,
    )

    assert max_gap == timedelta(minutes=4)
    assert gap_percentage == pytest.approx(0.5)


def test_calculate_activity_gaps_no_events_but_window():
    base = datetime(2024, 3, 1, tzinfo=timezone.utc)
    window_start = base
    window_end = base + timedelta(minutes=30)

    max_gap, gap_percentage = calculate_activity_gaps(
        [],
        window_start=window_start,
        window_end=window_end,
    )

    assert max_gap == timedelta(minutes=30)
    assert gap_percentage == pytest.approx(1.0)


def test_calculate_activity_gaps_invalid_window():
    base = datetime(2024, 4, 1, tzinfo=timezone.utc)

    events = [
        [
            ActivityEvent(
                event_time=base + timedelta(minutes=1),
                event_type=ActivityEventType.OPEN,
            ),
            ActivityEvent(
                event_time=base + timedelta(minutes=2),
                event_type=ActivityEventType.CLOSE,
            ),
        ]
    ]

    with pytest.raises(ValueError):
        calculate_activity_gaps(
            events,
            window_start=base + timedelta(minutes=10),
            window_end=base,
        )


def test_extract_islands_returns_no_indexes_without_gaps():
    base = datetime(2024, 5, 1, tzinfo=timezone.utc)

    def make_span(start: int, end: int) -> TimeSpan:
        return TimeSpan(
            start_time=base + timedelta(minutes=start),
            end_time=base + timedelta(minutes=end),
        )

    intervals = [
        make_span(0, 10),
        make_span(11, 20),
        make_span(21, 30),
    ]

    assert (
        extract_islands(
            intervals,
            max_gap=timedelta(minutes=2),
            assume_sorted=False,
        )
        == []
    )


def test_extract_islands_detects_multiple_splits():
    base = datetime(2024, 5, 2, tzinfo=timezone.utc)

    def make_span(start: int, end: int) -> TimeSpan:
        return TimeSpan(
            start_time=base + timedelta(minutes=start),
            end_time=base + timedelta(minutes=end),
        )

    intervals = [
        make_span(0, 5),
        make_span(6, 10),
        make_span(20, 25),
        make_span(40, 45),
    ]

    assert extract_islands(
        intervals,
        max_gap=timedelta(minutes=3),
        assume_sorted=False,
    ) == [2, 3]


def test_extract_islands_sorts_when_not_assumed_sorted():
    base = datetime(2024, 5, 3, tzinfo=timezone.utc)

    def make_span(start: int, end: int) -> TimeSpan:
        return TimeSpan(
            start_time=base + timedelta(minutes=start),
            end_time=base + timedelta(minutes=end),
        )

    intervals = [
        make_span(20, 25),
        make_span(0, 5),
        make_span(6, 10),
    ]

    assert extract_islands(
        intervals,
        max_gap=timedelta(minutes=2),
        assume_sorted=False,
    ) == [2]


def test_extract_islands_assume_sorted_bypasses_sorting():
    base = datetime(2024, 5, 4, tzinfo=timezone.utc)

    def make_span(start: int, end: int) -> TimeSpan:
        return TimeSpan(
            start_time=base + timedelta(minutes=start),
            end_time=base + timedelta(minutes=end),
        )

    intervals = [
        make_span(0, 5),
        make_span(10, 15),
        make_span(25, 30),
    ]

    # With assume_sorted=True, the pre-order is used directly
    assert extract_islands(
        intervals, max_gap=timedelta(minutes=7), assume_sorted=True
    ) == [2]


def test_overlapping_subarray_split_basic():
    array = list(range(10))

    result = overlapping_subarray_split(
        array, max_subarray_length=4, overlap_percentage=0.25
    )

    assert result == [
        [0, 1, 2, 3],
        [3, 4, 5, 6],
        [6, 7, 8, 9],
    ]


def test_overlapping_subarray_split_small_input_returns_original():
    array = [1, 2]

    result = overlapping_subarray_split(
        array, max_subarray_length=5, overlap_percentage=0.5
    )

    assert result == [[1, 2]]


def test_overlapping_subarray_split_handles_tail_segment():
    array = list(range(9))

    result = overlapping_subarray_split(
        array, max_subarray_length=4, overlap_percentage=0.5
    )

    assert result == [
        [0, 1, 2, 3],
        [2, 3, 4, 5],
        [4, 5, 6, 7],
        [6, 7, 8],
    ]


def test_overlapping_subarray_split_zero_overlap():
    array = list(range(6))

    result = overlapping_subarray_split(
        array, max_subarray_length=3, overlap_percentage=0.0
    )

    assert result == [[0, 1, 2], [3, 4, 5]]


def test_overlapping_subarray_split_high_overlap():
    array = list(range(5))

    result = overlapping_subarray_split(
        array, max_subarray_length=3, overlap_percentage=0.9
    )

    assert result == [
        [0, 1, 2],
        [2, 3, 4],
    ]
