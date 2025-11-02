from datetime import datetime, timezone

import pytest

from clepsy.entities import ViewMode
from clepsy.utils import calculate_date_based_on_view_mode


class TestCalculateDateBasedOnViewMode:
    # Use a fixed reference date with timezone for consistency
    # Wednesday, April 16th, 2025 10:30:00 UTC
    REFERENCE_DATE = datetime(2025, 4, 16, 10, 30, 0, tzinfo=timezone.utc)

    @pytest.mark.parametrize(
        "view_mode, offset, expected_start, expected_end",
        [
            # Daily View Mode Tests
            pytest.param(
                ViewMode.DAILY,
                0,
                datetime(2025, 4, 16, 0, 0, 0, tzinfo=timezone.utc),  # Start of Wed
                datetime(
                    2025, 4, 17, 0, 0, 0, tzinfo=timezone.utc
                ),  # Start of Thu (exclusive end)
                id="daily_offset_0",
            ),
            pytest.param(
                ViewMode.DAILY,
                1,
                datetime(2025, 4, 17, 0, 0, 0, tzinfo=timezone.utc),  # Start of Thu
                datetime(
                    2025, 4, 18, 0, 0, 0, tzinfo=timezone.utc
                ),  # Start of Fri (exclusive end)
                id="daily_offset_positive_1",
            ),
            pytest.param(
                ViewMode.DAILY,
                -1,
                datetime(2025, 4, 15, 0, 0, 0, tzinfo=timezone.utc),  # Start of Tue
                datetime(
                    2025, 4, 16, 0, 0, 0, tzinfo=timezone.utc
                ),  # Start of Wed (exclusive end)
                id="daily_offset_negative_1",
            ),
            # Weekly View Mode Tests (Assuming week starts on Monday)
            pytest.param(
                ViewMode.WEEKLY,
                0,
                datetime(
                    2025, 4, 14, 0, 0, 0, tzinfo=timezone.utc
                ),  # Start of Mon Apr 14
                datetime(
                    2025, 4, 21, 0, 0, 0, tzinfo=timezone.utc
                ),  # Start of Mon Apr 21 (exclusive end)
                id="weekly_offset_0",
            ),
            pytest.param(
                ViewMode.WEEKLY,
                1,
                datetime(
                    2025, 4, 21, 0, 0, 0, tzinfo=timezone.utc
                ),  # Start of Mon Apr 21
                datetime(
                    2025, 4, 28, 0, 0, 0, tzinfo=timezone.utc
                ),  # Start of Mon Apr 28 (exclusive end)
                id="weekly_offset_positive_1",
            ),
            pytest.param(
                ViewMode.WEEKLY,
                -1,
                datetime(
                    2025, 4, 7, 0, 0, 0, tzinfo=timezone.utc
                ),  # Start of Mon Apr 7
                datetime(
                    2025, 4, 14, 0, 0, 0, tzinfo=timezone.utc
                ),  # Start of Mon Apr 14 (exclusive end)
                id="weekly_offset_negative_1",
            ),
            # Monthly View Mode Tests
            pytest.param(
                ViewMode.MONTHLY,
                0,
                datetime(2025, 4, 1, 0, 0, 0, tzinfo=timezone.utc),  # Start of Apr 1
                datetime(
                    2025, 5, 1, 0, 0, 0, tzinfo=timezone.utc
                ),  # Start of May 1 (exclusive end)
                id="monthly_offset_0",
            ),
            pytest.param(
                ViewMode.MONTHLY,
                1,
                datetime(2025, 5, 1, 0, 0, 0, tzinfo=timezone.utc),  # Start of May 1
                datetime(
                    2025, 6, 1, 0, 0, 0, tzinfo=timezone.utc
                ),  # Start of Jun 1 (exclusive end)
                id="monthly_offset_positive_1",
            ),
            pytest.param(
                ViewMode.MONTHLY,
                -1,
                datetime(2025, 3, 1, 0, 0, 0, tzinfo=timezone.utc),  # Start of Mar 1
                datetime(
                    2025, 4, 1, 0, 0, 0, tzinfo=timezone.utc
                ),  # Start of Apr 1 (exclusive end)
                id="monthly_offset_negative_1",
            ),
        ],
    )
    def test_calculate_date_ranges(
        self,
        view_mode: ViewMode,
        offset: int,
        expected_start: datetime,
        expected_end: datetime,
    ):
        """
        Test calculate_date_based_on_view_mode with various view modes and offsets.
        """
        start_date, end_date = calculate_date_based_on_view_mode(
            self.REFERENCE_DATE, view_mode, offset
        )

        assert start_date == expected_start
        assert end_date == expected_end

    def test_invalid_view_mode_raises_error(self):
        """
        Test that an unsupported view mode raises a ValueError.
        """
        with pytest.raises(ValueError, match="Unsupported view mode"):
            # Simulate an invalid enum value or type
            calculate_date_based_on_view_mode(self.REFERENCE_DATE, "INVALID_MODE", 0)  # type: ignore
